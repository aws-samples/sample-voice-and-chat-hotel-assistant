# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Property-based tests for validation using Hypothesis.

Feature: hotel-pms-input-validation
"""

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st
from pydantic import ValidationError

from hotel_pms_simulation.models.generated.validators import (
    AvailabilityRequestWithValidation,
    QuoteRequestWithValidation,
)
from hotel_pms_simulation.utils.validation_errors import format_validation_error


# Property 1: Type validation errors are reported with field details
# Validates: Requirements 1.1
@given(
    guests=st.one_of(
        st.floats(allow_nan=False, allow_infinity=False).filter(
            lambda x: x != int(x) if isinstance(x, float) else True
        ),  # Exclude floats that can be coerced to integers (like 1.0, 2.0)
        st.text().filter(
            lambda x: not (
                x.strip()
                .lstrip("-")
                .isdigit()  # Strip whitespace first (Pydantic does this)
                or (
                    x.strip().replace(".", "", 1).lstrip("-").isdigit()
                    and x.strip().count(".") == 1
                )
            )
        ),  # Exclude strings that can be coerced to integers or floats
        st.lists(st.integers()),
    )
)
def test_property_type_validation_errors_include_field_details(guests):
    """
    Feature: hotel-pms-input-validation, Property 1: Type validation errors are reported with field details
    Validates: Requirements 1.1

    For any API request with type mismatches (float for int, string for date, etc.),
    the error response should include the field name, expected type, and actual input value.
    """
    tomorrow = date.today() + timedelta(days=1)
    day_after = date.today() + timedelta(days=2)

    # Only test when guests is not an integer and not a coercible value
    if not isinstance(guests, int):
        try:
            QuoteRequestWithValidation(
                hotel_id="H-PVR-002",
                room_type_id="RT-STD",
                check_in_date=tomorrow,
                check_out_date=day_after,
                guests=guests,
                package_type="simple",
            )
            # If no error was raised, check if it's a coercible float
            if isinstance(guests, float) and guests == int(guests):
                # This is expected - Pydantic coerces floats like 1.0 to integers
                return
            # For other non-integer guests, this is unexpected
            raise AssertionError(f"Expected ValidationError for guests={guests}")
        except ValidationError as e:
            error_response = format_validation_error(e)

            # Verify error response structure
            assert error_response["error"] is True
            assert error_response["error_code"] == "VALIDATION_ERROR"
            assert "details" in error_response
            assert len(error_response["details"]) > 0

            # Verify field-level error details
            guest_error = next(
                (err for err in error_response["details"] if err["field"] == "guests"),
                None,
            )
            assert guest_error is not None, "Should have error for guests field"
            assert "field" in guest_error
            assert "message" in guest_error
            assert "type" in guest_error
            assert "input" in guest_error


# Property 2: Past dates are rejected with clear error messages
# Validates: Requirements 1.2, 5.1
@given(days_in_past=st.integers(min_value=1, max_value=365))
def test_property_past_dates_rejected_with_clear_messages(days_in_past):
    """
    Feature: hotel-pms-input-validation, Property 2: Past dates are rejected with clear error messages
    Validates: Requirements 1.2, 5.1

    For any API request with dates in the past, the system should return an error response
    indicating that dates must be in the future.
    """
    past_date = date.today() - timedelta(days=days_in_past)
    future_date = date.today() + timedelta(days=1)

    try:
        QuoteRequestWithValidation(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date=past_date,
            check_out_date=future_date,
            guests=2,
        )
        raise AssertionError(f"Expected ValidationError for past date {past_date}")
    except ValidationError as e:
        error_response = format_validation_error(e)

        # Verify error response structure
        assert error_response["error"] is True
        assert error_response["error_code"] == "VALIDATION_ERROR"

        # Verify date validation error
        date_error = next(
            (
                err
                for err in error_response["details"]
                if "check_in_date" in err["field"]
            ),
            None,
        )
        assert date_error is not None, "Should have error for check_in_date"
        assert (
            "future" in date_error["message"].lower()
            or "today" in date_error["message"].lower()
        )


# Property 5: Validation errors have consistent structure
# Validates: Requirements 1.5, 7.1, 7.2, 7.3
@given(
    guests=st.one_of(st.floats(), st.text()),
    package_type=st.text().filter(lambda x: x not in ["simple", "detailed"]),
)
def test_property_validation_errors_have_consistent_structure(guests, package_type):
    """
    Feature: hotel-pms-input-validation, Property 5: Validation errors have consistent structure
    Validates: Requirements 1.5, 7.1, 7.2, 7.3

    For any validation error, the response should have HTTP 400 status, error=true,
    error_code="VALIDATION_ERROR", and a non-empty message field.
    """
    tomorrow = date.today() + timedelta(days=1)
    day_after = date.today() + timedelta(days=2)

    try:
        QuoteRequestWithValidation(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date=tomorrow,
            check_out_date=day_after,
            guests=guests,
            package_type=package_type,
        )
        # If no error, skip this test case
    except ValidationError as e:
        error_response = format_validation_error(e)

        # Verify consistent error structure
        assert error_response["error"] is True
        assert error_response["error_code"] == "VALIDATION_ERROR"
        assert "message" in error_response
        assert len(error_response["message"]) > 0
        assert "details" in error_response
        assert isinstance(error_response["details"], list)


# Property 11: Check-out date must be after check-in date
# Validates: Requirements 5.2
@given(
    check_in_offset=st.integers(min_value=0, max_value=30),
    days_between=st.integers(min_value=-10, max_value=10),
)
def test_property_checkout_must_be_after_checkin(check_in_offset, days_between):
    """
    Feature: hotel-pms-input-validation, Property 11: Check-out date must be after check-in date
    Validates: Requirements 5.2

    For any request with both check_in_date and check_out_date, the system should reject
    requests where check_out_date is not strictly after check_in_date.
    """
    check_in = date.today() + timedelta(days=check_in_offset)
    check_out = check_in + timedelta(days=days_between)

    try:
        request = AvailabilityRequestWithValidation(
            hotel_id="H-PVR-002",
            check_in_date=check_in,
            check_out_date=check_out,
            guests=2,
        )

        # If validation passed, check_out must be after check_in
        if days_between <= 0:
            raise AssertionError(
                f"Expected ValidationError for check_out <= check_in (days_between={days_between})"
            )
        else:
            # Valid case - check_out is after check_in
            assert request.check_out_date > request.check_in_date

    except ValidationError as e:
        # If validation failed, check_out must not be after check_in
        if days_between > 0:
            # This should not happen - check_out is after check_in
            raise AssertionError(
                f"Unexpected ValidationError for valid dates (days_between={days_between})"
            )
        else:
            # Expected error for check_out <= check_in
            error_response = format_validation_error(e)
            assert any(
                "check_out_date" in err["field"] for err in error_response["details"]
            )
