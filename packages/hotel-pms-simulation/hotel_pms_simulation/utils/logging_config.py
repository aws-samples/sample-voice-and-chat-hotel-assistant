# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Logging configuration and utilities for structured logging."""

import logging
import os
from typing import Any

from aws_lambda_powertools import Logger


class StructuredLogger:
    """Enhanced structured logger with business context."""

    def __init__(self, service_name: str = "hotel-pms-api"):
        self.logger = Logger(service=service_name)
        self.service_name = service_name

    def log_business_event(
        self,
        event_type: str,
        event_data: dict[str, Any],
        level: str = "INFO",
        request_id: str | None = None,
        correlation_id: str | None = None,
    ) -> None:
        """Log business events with structured data."""
        extra_data = {
            "event_type": event_type,
            "event_data": event_data,
            "service": self.service_name,
        }

        if request_id:
            extra_data["request_id"] = request_id
        if correlation_id:
            extra_data["correlation_id"] = correlation_id

        log_method = getattr(self.logger, level.lower(), self.logger.info)
        log_method(f"Business event: {event_type}", extra=extra_data)

    def log_api_request(
        self,
        method: str,
        path: str,
        status_code: int,
        response_time_ms: float,
        request_id: str | None = None,
        user_agent: str | None = None,
        source_ip: str | None = None,
    ) -> None:
        """Log API request with performance metrics."""
        self.logger.info(
            "API request processed",
            extra={
                "api_request": {
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "response_time_ms": response_time_ms,
                    "user_agent": user_agent,
                    "source_ip": source_ip,
                },
                "request_id": request_id,
            },
        )

    def log_database_operation(
        self,
        operation: str,
        table: str,
        success: bool,
        duration_ms: float | None = None,
        affected_rows: int | None = None,
        error_message: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log database operations with performance data."""
        db_data = {
            "operation": operation,
            "table": table,
            "success": success,
        }

        if duration_ms is not None:
            db_data["duration_ms"] = duration_ms
        if affected_rows is not None:
            db_data["affected_rows"] = affected_rows
        if error_message:
            db_data["error_message"] = error_message

        level = "info" if success else "error"
        log_method = getattr(self.logger, level)
        log_method(
            f"Database {operation} on {table}",
            extra={"database_operation": db_data, "request_id": request_id},
        )

    def log_external_service_call(
        self,
        service_name: str,
        operation: str,
        success: bool,
        response_time_ms: float | None = None,
        status_code: int | None = None,
        error_message: str | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log external service calls."""
        service_data = {
            "service": service_name,
            "operation": operation,
            "success": success,
        }

        if response_time_ms is not None:
            service_data["response_time_ms"] = response_time_ms
        if status_code is not None:
            service_data["status_code"] = status_code
        if error_message:
            service_data["error_message"] = error_message

        level = "info" if success else "error"
        log_method = getattr(self.logger, level)
        log_method(
            f"External service call: {service_name}.{operation}",
            extra={"external_service": service_data, "request_id": request_id},
        )

    def log_security_event(
        self,
        event_type: str,
        severity: str,
        details: dict[str, Any],
        request_id: str | None = None,
        source_ip: str | None = None,
    ) -> None:
        """Log security-related events."""
        security_data = {
            "event_type": event_type,
            "severity": severity,
            "details": details,
            "source_ip": source_ip,
        }

        self.logger.warning(
            f"Security event: {event_type}",
            extra={"security_event": security_data, "request_id": request_id},
        )

    def log_performance_metric(
        self,
        metric_name: str,
        value: float,
        unit: str,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log performance metrics."""
        perf_data = {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "context": context or {},
        }

        self.logger.info(
            f"Performance metric: {metric_name}",
            extra={"performance_metric": perf_data, "request_id": request_id},
        )

    def log_error_with_context(
        self,
        error: Exception,
        operation: str,
        context: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> None:
        """Log errors with full context information."""
        error_data = {
            "error_type": error.__class__.__name__,
            "error_message": str(error),
            "operation": operation,
            "context": context or {},
        }

        self.logger.error(
            f"Error in {operation}: {error}",
            extra={"error_context": error_data, "request_id": request_id},
            exc_info=True,
        )


def configure_logging() -> StructuredLogger:
    """Configure logging for the application."""
    # Set log level from environment variable
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Configure the root logger
    logging.getLogger().setLevel(getattr(logging, log_level, logging.INFO))

    # Create and return structured logger
    return StructuredLogger()


def log_lambda_context(context, logger: Logger) -> None:
    """Log Lambda context information."""
    logger.info(
        "Lambda context",
        extra={
            "lambda_context": {
                "function_name": context.function_name,
                "function_version": context.function_version,
                "memory_limit_mb": context.memory_limit_in_mb,
                "remaining_time_ms": context.get_remaining_time_in_millis(),
                "request_id": context.aws_request_id,
            }
        },
    )


def sanitize_log_data(data: Any) -> Any:
    """Sanitize sensitive data from log entries."""
    if isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            if key.lower() in ["password", "token", "secret", "key", "authorization"]:
                sanitized[key] = "***REDACTED***"
            elif key.lower() in ["email", "phone", "credit_card"]:
                sanitized[key] = _mask_sensitive_value(str(value))
            else:
                sanitized[key] = sanitize_log_data(value)
        return sanitized
    elif isinstance(data, list):
        return [sanitize_log_data(item) for item in data]
    else:
        return data


def _mask_sensitive_value(value: str) -> str:
    """Mask sensitive values while preserving some information."""
    if "@" in value:  # Email
        parts = value.split("@")
        if len(parts) == 2:
            username = parts[0]
            domain = parts[1]
            masked_username = username[:2] + "*" * (len(username) - 2)
            return f"{masked_username}@{domain}"
    elif len(value) > 4:  # Phone or other sensitive data
        return value[:2] + "*" * (len(value) - 4) + value[-2:]
    else:
        return "*" * len(value)
