# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
HTTP client with built-in retry logic for rate limiting and server errors.

This module provides RetryHTTPClient, an httpx.AsyncClient subclass that automatically
retries requests on rate limiting (HTTP 429) and server errors (HTTP 5xx) using
exponential backoff with jitter.
"""

import logging
from typing import Any

import httpx
from tenacity import (
    after_log,
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_random_exponential,
)

logger = logging.getLogger(__name__)


class RetryHTTPClient(httpx.AsyncClient):
    """
    HTTP client with built-in retry logic for rate limiting and server errors.

    This client automatically retries requests that fail with:
    - HTTP 429 (Too Many Requests / Rate Limiting)
    - HTTP 5xx (Server Errors)
    - Connection errors (httpx.ConnectError)
    - Timeout errors (httpx.TimeoutException)

    Retry configuration:
    - 5 attempts maximum
    - Exponential backoff with jitter (multiplier=2, min=1s, max=60s for send(), min=1s, max=30s for request())
    - Does not retry on HTTP 4xx errors (except 429)

    The client overrides both send() and request() methods to provide comprehensive
    coverage for different usage patterns.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def send(self, request: httpx.Request, **kwargs) -> httpx.Response:
        """
        Override send method to add retry logic for streaming requests.

        This method is called by httpx's stream() method, making it essential
        for libraries like MCP that use streaming HTTP requests.
        """

        @retry(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=2, min=1, max=60),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )
        async def _send_with_retry():
            response = await super(RetryHTTPClient, self).send(request, **kwargs)

            # Check if we should retry based on status code
            # We need to raise an exception to trigger retry, but the calling code
            # expects to handle the status codes itself via raise_for_status()
            if response.status_code == 429:  # Too Many Requests
                retry_after = response.headers.get("Retry-After")
                logger.warning(
                    f"HTTP 429 rate limit hit for {request.method} {request.url}, will retry",
                    extra={
                        "method": request.method,
                        "url": str(request.url),
                        "status_code": response.status_code,
                        "retry_after": retry_after,
                    },
                )
                # Close the response to free resources before retrying
                await response.aclose()
                # Raise HTTPStatusError to trigger retry
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code} rate limit", request=request, response=response
                )
            elif 500 <= response.status_code < 600:  # Server errors
                logger.warning(
                    f"HTTP {response.status_code} server error for {request.method} {request.url}, will retry",
                    extra={
                        "method": request.method,
                        "url": str(request.url),
                        "status_code": response.status_code,
                    },
                )
                # Close the response to free resources before retrying
                await response.aclose()
                # Raise HTTPStatusError to trigger retry
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code} server error", request=request, response=response
                )

            return response

        return await _send_with_retry()

    async def request(self, method: str, url: httpx.URL | str, **kwargs) -> httpx.Response:
        """
        Override request method to add retry logic for direct requests.

        This method provides retry logic for direct HTTP requests that don't
        go through the send() method.
        """

        @retry(
            stop=stop_after_attempt(5),
            wait=wait_random_exponential(multiplier=2, min=1, max=30),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
            before_sleep=before_sleep_log(logger, logging.WARNING),
            after=after_log(logger, logging.INFO),
            reraise=True,
        )
        async def _request_with_retry():
            response = await super(RetryHTTPClient, self).request(method, url, **kwargs)

            # Check if we should retry based on status code
            if response.status_code == 429:  # Too Many Requests
                retry_after = response.headers.get("Retry-After")
                logger.warning(
                    f"HTTP 429 rate limit hit for {method} {url}, will retry",
                    extra={
                        "method": method,
                        "url": str(url),
                        "status_code": response.status_code,
                        "retry_after": retry_after,
                    },
                )
                # Raise HTTPStatusError to trigger retry
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code} rate limit", request=response.request, response=response
                )
            elif 500 <= response.status_code < 600:  # Server errors
                logger.warning(
                    f"HTTP {response.status_code} server error for {method} {url}, will retry",
                    extra={
                        "method": method,
                        "url": str(url),
                        "status_code": response.status_code,
                    },
                )
                # Raise HTTPStatusError to trigger retry
                raise httpx.HTTPStatusError(
                    f"HTTP {response.status_code} server error", request=response.request, response=response
                )

            return response

        return await _request_with_retry()


def create_retry_http_client(
    headers: dict[str, str] | None = None,
    timeout: httpx.Timeout | None = None,
    auth: httpx.Auth | None = None,
    **kwargs: Any,
) -> RetryHTTPClient:
    """
    Create an HTTP client with retry logic.

    This factory function creates a RetryHTTPClient with sensible defaults
    and allows customization of common httpx parameters.

    Args:
        headers: Optional headers to include in all requests
        timeout: Optional timeout configuration
        auth: Optional authentication handler
        **kwargs: Additional arguments passed to RetryHTTPClient constructor

    Returns:
        Configured RetryHTTPClient instance

    Example:
        ```python
        # Basic usage
        client = create_retry_http_client()

        # With authentication
        client = create_retry_http_client(auth=my_auth_handler)

        # With custom timeout
        timeout = httpx.Timeout(30.0, read=60.0)
        client = create_retry_http_client(timeout=timeout)
        ```
    """
    logger.info(f"Creating RetryHTTPClient with auth={type(auth).__name__ if auth else None}")

    # Set sensible defaults
    client_kwargs: dict[str, Any] = {
        "follow_redirects": True,
        **kwargs,
    }

    # Handle timeout
    if timeout is None:
        client_kwargs["timeout"] = httpx.Timeout(30.0)
    else:
        client_kwargs["timeout"] = timeout

    # Handle headers
    if headers is not None:
        client_kwargs["headers"] = headers

    # Handle authentication
    if auth is not None:
        client_kwargs["auth"] = auth

    client = RetryHTTPClient(**client_kwargs)
    logger.info(f"Created RetryHTTPClient: {type(client).__name__}")
    return client
