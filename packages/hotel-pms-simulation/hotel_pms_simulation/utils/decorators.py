# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Decorators for consistent error handling and logging."""

import functools
import time
from collections.abc import Callable
from typing import Any

from aws_lambda_powertools import Logger, Metrics, Tracer
from aws_lambda_powertools.event_handler import Response
from aws_lambda_powertools.metrics import MetricUnit

from ..exceptions import DatabaseError, HotelPMSError
from .metrics import HotelPMSMetrics
from .responses import get_request_id_from_context

logger = Logger()
tracer = Tracer()
metrics = Metrics(namespace="HotelPMS")
hotel_metrics = HotelPMSMetrics(metrics)


def handle_errors(operation_name: str):
    """Decorator for consistent error handling across endpoints."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Response:
            start_time = time.time()
            request_id = get_request_id_from_context()

            try:
                # Execute the wrapped function
                result = func(*args, **kwargs)

                # Record success metrics
                response_time_ms = (time.time() - start_time) * 1000
                hotel_metrics.record_performance_metric(
                    metric_name=f"{operation_name}Duration",
                    value=response_time_ms,
                    unit=MetricUnit.Milliseconds,
                )

                logger.info(
                    f"{operation_name} completed successfully",
                    extra={
                        "operation": operation_name,
                        "request_id": request_id,
                        "response_time_ms": response_time_ms,
                    },
                )

                return result

            except HotelPMSError:
                # Re-raise custom exceptions to be handled by the global handler
                raise

            except Exception as e:
                # Convert unexpected exceptions to appropriate custom exceptions
                response_time_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"Unexpected error in {operation_name}",
                    extra={
                        "operation": operation_name,
                        "error_type": e.__class__.__name__,
                        "error_message": str(e),
                        "request_id": request_id,
                        "response_time_ms": response_time_ms,
                    },
                    exc_info=True,
                )

                # Record error metrics
                hotel_metrics.record_error_by_type(
                    error_type=e.__class__.__name__,
                    error_code="UNEXPECTED_ERROR",
                    endpoint=operation_name,
                    status_code=500,
                )

                # Convert to appropriate custom exception
                raise DatabaseError(
                    message=f"Failed to complete {operation_name} due to system error",
                    operation=operation_name,
                ) from e

        return wrapper

    return decorator


def validate_request_body(required_fields: list[str] | None = None):
    """Decorator to validate request body structure."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import json

            from aws_lambda_powertools.event_handler import APIGatewayRestResolver

            # Get the app instance from the function's globals
            app = func.__globals__.get("app")
            if not isinstance(app, APIGatewayRestResolver):
                return func(*args, **kwargs)

            try:
                body = json.loads(app.current_event.body or "{}")
            except json.JSONDecodeError as e:
                from ..exceptions import ValidationError

                raise ValidationError(
                    message="Invalid JSON in request body",
                    field="body",
                    constraint="must be valid JSON",
                ) from e

            # Check required fields
            if required_fields:
                missing_fields = [
                    field for field in required_fields if field not in body
                ]
                if missing_fields:
                    from ..exceptions import ValidationError

                    raise ValidationError(
                        message=f"Missing required fields: {', '.join(missing_fields)}",
                        details={"missing_fields": missing_fields},
                    )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def rate_limit(requests_per_minute: int = 60):
    """Decorator for basic rate limiting (placeholder for future implementation)."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # TODO: Implement rate limiting logic
            # For now, just pass through
            return func(*args, **kwargs)

        return wrapper

    return decorator


def cache_response(ttl_seconds: int = 300):
    """Decorator for response caching (placeholder for future implementation)."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # TODO: Implement response caching logic
            # For now, just pass through
            return func(*args, **kwargs)

        return wrapper

    return decorator
