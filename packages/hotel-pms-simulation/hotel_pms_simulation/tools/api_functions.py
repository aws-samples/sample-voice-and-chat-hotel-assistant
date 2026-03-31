# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Direct function interfaces for API Gateway handler."""

from typing import Any

from pydantic import ValidationError

from ..models.generated.validators import (
    AvailabilityRequestWithValidation,
    QuoteRequestWithValidation,
    ReservationRequestWithValidation,
)
from ..utils.validation_errors import format_validation_error
from .tools import HotelPMSTools

# Lazy initialization of tools instance
_tools = None


def _get_tools() -> HotelPMSTools:
    """Get or create the tools instance (lazy initialization)."""
    global _tools
    if _tools is None:
        _tools = HotelPMSTools()
    return _tools


def check_availability(**kwargs) -> dict[str, Any]:
    """Check room availability for a hotel on specific dates.

    Validates input using Pydantic before calling the underlying tool.
    """
    try:
        validated_request = AvailabilityRequestWithValidation(**kwargs)
        # Convert to dict for business logic (mode='json' serializes dates to strings)
        return _get_tools().check_availability(
            **validated_request.model_dump(mode="json")
        )
    except ValidationError as e:
        return format_validation_error(e)


def generate_quote(**kwargs) -> dict[str, Any]:
    """Generate a detailed pricing quote.

    Validates input using Pydantic before calling the underlying tool.
    """
    try:
        validated_request = QuoteRequestWithValidation(**kwargs)
        # Convert to dict for business logic (mode='json' serializes dates to strings)
        return _get_tools().generate_quote(**validated_request.model_dump(mode="json"))
    except ValidationError as e:
        return format_validation_error(e)


def create_reservation(**kwargs) -> dict[str, Any]:
    """Create a new hotel reservation.

    Validates input using Pydantic before calling the underlying tool.
    """
    try:
        validated_request = ReservationRequestWithValidation(**kwargs)
        # Convert to dict for business logic (mode='json' serializes dates to strings)
        return _get_tools().create_reservation(
            **validated_request.model_dump(mode="json")
        )
    except ValidationError as e:
        return format_validation_error(e)


def get_reservations(**kwargs) -> dict[str, Any]:
    """Retrieve reservations by hotel or guest email."""
    return _get_tools().get_reservations(**kwargs)


def get_reservation(**kwargs) -> dict[str, Any]:
    """Get details of a specific reservation."""
    return _get_tools().get_reservation(**kwargs)


def update_reservation(**kwargs) -> dict[str, Any]:
    """Update an existing reservation."""
    return _get_tools().update_reservation(**kwargs)


def checkout_guest(**kwargs) -> dict[str, Any]:
    """Process guest checkout and final billing."""
    return _get_tools().checkout_guest(**kwargs)


def get_hotels(**kwargs) -> dict[str, Any]:
    """Get a list of all available hotels."""
    return _get_tools().get_hotels(**kwargs)


def create_housekeeping_request(**kwargs) -> dict[str, Any]:
    """Create a housekeeping or maintenance request."""
    return _get_tools().create_housekeeping_request(**kwargs)
