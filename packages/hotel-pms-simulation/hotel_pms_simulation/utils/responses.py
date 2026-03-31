# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""HTTP response utilities."""

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from aws_lambda_powertools import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext

from ..exceptions import HotelPMSError

logger = Logger()


def create_response(
    status_code: int,
    body: Any,
    headers: dict[str, str] | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create standardized HTTP response."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS",
    }

    if headers:
        default_headers.update(headers)

    # Add request ID to response body if it's a dict
    if isinstance(body, dict) and request_id:
        body["request_id"] = request_id

    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body, default=str),
    }


def success_response(
    data: Any,
    status_code: int = 200,
    request_id: str | None = None,
) -> dict[str, Any]:
    """Create success response."""
    return create_response(status_code, data, request_id=request_id)


def error_response(
    error_code: str,
    message: str,
    status_code: int = 400,
    details: dict[str, Any] | None = None,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Create error response."""
    error_body = {
        "error": {
            "code": error_code,
            "message": message,
            "timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
    }

    if details:
        error_body["error"]["details"] = details

    if request_id:
        error_body["request_id"] = request_id

    if correlation_id:
        error_body["correlation_id"] = correlation_id

    # Add trace ID if available
    try:
        from aws_lambda_powertools import Tracer

        tracer = Tracer()
        if tracer.is_tracing_enabled():
            error_body["trace_id"] = tracer.get_trace_id()
    except Exception:
        # Ignore if tracing is not available
        pass

    logger.warning(
        "Error response created",
        extra={
            "error_code": error_code,
            "error_message": message,
            "status_code": status_code,
            "request_id": request_id,
            "correlation_id": correlation_id,
            "error_details": details,
        },
    )

    return create_response(status_code, error_body)


def error_response_from_exception(
    exception: HotelPMSError,
    request_id: str | None = None,
    correlation_id: str | None = None,
) -> dict[str, Any]:
    """Create error response from custom exception."""
    return error_response(
        error_code=exception.error_code,
        message=exception.message,
        status_code=exception.status_code,
        details=exception.details if exception.details else None,
        request_id=request_id,
        correlation_id=correlation_id,
    )


def get_request_id_from_context(context: LambdaContext | None = None) -> str:
    """Get request ID from Lambda context or generate a new one."""
    if context and hasattr(context, "aws_request_id"):
        return context.aws_request_id
    return str(uuid.uuid4())
