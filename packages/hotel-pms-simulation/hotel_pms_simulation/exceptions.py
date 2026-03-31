# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Custom exception classes for Hotel PMS API."""

from typing import Any


class HotelPMSError(Exception):
    """Base exception for all Hotel PMS API errors."""

    def __init__(
        self,
        message: str,
        error_code: str = "HOTEL_PMS_ERROR",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}


class ValidationError(HotelPMSError):
    """Raised when request validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
        constraint: str | None = None,
    ):
        details = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)
        if constraint:
            details["constraint"] = constraint

        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details,
        )


class AuthenticationError(HotelPMSError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
        )


class AuthorizationError(HotelPMSError):
    """Raised when authorization fails."""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="AUTHORIZATION_ERROR",
            status_code=403,
        )


class ResourceNotFoundError(HotelPMSError):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_type: str, resource_id: str):
        message = f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(
            message=message,
            error_code="RESOURCE_NOT_FOUND",
            status_code=404,
            details={"resource_type": resource_type, "resource_id": resource_id},
        )


class ConflictError(HotelPMSError):
    """Raised when a resource conflict occurs."""

    def __init__(self, message: str, conflict_type: str | None = None):
        details = {}
        if conflict_type:
            details["conflict_type"] = conflict_type

        super().__init__(
            message=message,
            error_code="CONFLICT_ERROR",
            status_code=409,
            details=details,
        )


class BusinessLogicError(HotelPMSError):
    """Raised when business logic validation fails."""

    def __init__(self, message: str, business_rule: str | None = None):
        details = {}
        if business_rule:
            details["business_rule"] = business_rule

        super().__init__(
            message=message,
            error_code="BUSINESS_LOGIC_ERROR",
            status_code=422,
            details=details,
        )


class DatabaseError(HotelPMSError):
    """Raised when database operations fail."""

    def __init__(self, message: str, operation: str | None = None):
        details = {}
        if operation:
            details["operation"] = operation

        super().__init__(
            message=message,
            error_code="DATABASE_ERROR",
            status_code=500,
            details=details,
        )


class ExternalServiceError(HotelPMSError):
    """Raised when external service calls fail."""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} service error: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            status_code=502,
            details={"service": service},
        )


class RateLimitError(HotelPMSError):
    """Raised when rate limits are exceeded."""

    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            status_code=429,
        )


class ServiceUnavailableError(HotelPMSError):
    """Raised when service is temporarily unavailable."""

    def __init__(self, message: str = "Service temporarily unavailable"):
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
        )


# Specific Hotel PMS exceptions
class ReservationConflictError(ConflictError):
    """Raised when a reservation conflicts with existing bookings."""

    def __init__(self, message: str):
        super().__init__(message=message, conflict_type="reservation_conflict")


class InsufficientCapacityError(BusinessLogicError):
    """Raised when room cannot accommodate the requested number of guests."""

    def __init__(self, message: str):
        super().__init__(message=message, business_rule="room_capacity")


class RoomNotAvailableError(BusinessLogicError):
    """Raised when no rooms are available for the requested dates."""

    def __init__(self, message: str):
        super().__init__(message=message, business_rule="room_availability")


class ReservationNotFoundError(ResourceNotFoundError):
    """Raised when a reservation is not found."""

    def __init__(self, reservation_id: str):
        super().__init__(resource_type="Reservation", resource_id=reservation_id)


class InvalidReservationStatusError(BusinessLogicError):
    """Raised when attempting an invalid status transition."""

    def __init__(self, current_status: str, requested_status: str):
        message = f"Cannot transition from '{current_status}' to '{requested_status}'"
        super().__init__(
            message=message,
            business_rule="reservation_status_transition",
        )
        self.details.update(
            {
                "current_status": current_status,
                "requested_status": requested_status,
            }
        )


class GuestServiceError(BusinessLogicError):
    """Base exception for guest service operations."""

    def __init__(self, message: str):
        super().__init__(message=message, business_rule="guest_service")


class InvalidCheckoutError(GuestServiceError):
    """Raised when checkout cannot be performed."""

    def __init__(self, message: str):
        super().__init__(message)
        self.details["business_rule"] = "checkout_validation"


class HotelNotFoundError(ResourceNotFoundError):
    """Raised when a hotel is not found."""

    def __init__(self, hotel_id: str):
        super().__init__(resource_type="Hotel", resource_id=hotel_id)


class RoomTypeNotFoundError(ResourceNotFoundError):
    """Raised when a room type is not found."""

    def __init__(self, room_type_id: str):
        super().__init__(resource_type="RoomType", resource_id=room_type_id)


class RoomNotFoundError(ResourceNotFoundError):
    """Raised when a room is not found."""

    def __init__(self, room_id: str):
        super().__init__(resource_type="Room", resource_id=room_id)


class TimeoutError(HotelPMSError):
    """Raised when operations timeout."""

    def __init__(self, operation: str, timeout_seconds: int):
        message = f"Operation '{operation}' timed out after {timeout_seconds} seconds"
        super().__init__(
            message=message,
            error_code="TIMEOUT_ERROR",
            status_code=504,
            details={"operation": operation, "timeout_seconds": timeout_seconds},
        )


class ConfigurationError(HotelPMSError):
    """Raised when configuration is invalid or missing."""

    def __init__(self, config_key: str, message: str):
        super().__init__(
            message=f"Configuration error for '{config_key}': {message}",
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            details={"config_key": config_key},
        )


class DataIntegrityError(DatabaseError):
    """Raised when data integrity constraints are violated."""

    def __init__(self, message: str, constraint: str | None = None):
        details = {"operation": "data_integrity_check"}
        if constraint:
            details["constraint"] = constraint

        super().__init__(message=message, operation="data_integrity_check")
        self.details.update(details)


class ConcurrencyError(ConflictError):
    """Raised when concurrent operations conflict."""

    def __init__(self, resource: str, operation: str):
        message = f"Concurrent {operation} operation on {resource} detected"
        super().__init__(
            message=message,
            conflict_type="concurrency_conflict",
        )
        self.details.update({"resource": resource, "operation": operation})
