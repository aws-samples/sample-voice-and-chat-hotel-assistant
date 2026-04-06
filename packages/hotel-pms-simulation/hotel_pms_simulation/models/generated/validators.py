# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Custom validators for generated Pydantic models."""

from datetime import date
from typing import Any

from pydantic import field_validator

from .api_models import AvailabilityRequest, QuoteRequest, ReservationRequest


class QuoteRequestWithValidation(QuoteRequest):
    """Extended QuoteRequest with custom date validation."""

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: date) -> date:
        """Validate that check_in_date is today or in the future."""
        if v < date.today():
            raise ValueError("check_in_date must be today or in the future")
        return v

    @field_validator("check_out_date")
    @classmethod
    def validate_check_out_date(cls, v: date, info: Any) -> date:
        """Validate that check_out_date is after check_in_date."""
        check_in = info.data.get("check_in_date")
        if check_in and v <= check_in:
            raise ValueError("check_out_date must be after check_in_date")
        return v


class ReservationRequestWithValidation(ReservationRequest):
    """Extended ReservationRequest with validation.

    Reservation requests require a quote_id and guest details.
    All reservation details (hotel_id, room_type_id, dates, guests)
    are retrieved from the quote.
    """

    # No additional validation needed - all required fields are enforced by the base model
    pass


class AvailabilityRequestWithValidation(AvailabilityRequest):
    """Extended AvailabilityRequest with custom date validation."""

    @field_validator("check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: date) -> date:
        """Validate that check_in_date is today or in the future."""
        if v < date.today():
            raise ValueError("check_in_date must be today or in the future")
        return v

    @field_validator("check_out_date")
    @classmethod
    def validate_check_out_date(cls, v: date, info: Any) -> date:
        """Validate that check_out_date is after check_in_date."""
        check_in = info.data.get("check_in_date")
        if check_in and v <= check_in:
            raise ValueError("check_out_date must be after check_in_date")
        return v
