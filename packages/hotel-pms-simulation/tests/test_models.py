# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for Pydantic model validation."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from hotel_pms_simulation.models.generated.api_models import (
    CheckoutRequest,
    HousekeepingRequest,
    ReservationUpdateRequest,
)
from hotel_pms_simulation.models.generated.validators import (
    AvailabilityRequestWithValidation,
    QuoteRequestWithValidation,
    ReservationRequestWithValidation,
)


class TestQuoteRequestValidation:
    """Test validation for QuoteRequest model."""

    def test_valid_quote_request(self):
        """Test that a valid quote request passes validation."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        request = QuoteRequestWithValidation(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date=tomorrow,
            check_out_date=day_after,
            guests=2,
            package_type="simple",
        )

        assert request.hotel_id == "H-PVR-002"
        assert request.guests == 2

    def test_guests_minimum_constraint(self):
        """Test that guests field must be at least 1."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PVR-002",
                room_type_id="RT-STD",
                check_in_date=tomorrow,
                check_out_date=day_after,
                guests=0,  # Below minimum
                package_type="simple",
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("guests",) for err in errors)

    def test_guests_maximum_constraint(self):
        """Test that guests field must be at most 10."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PVR-002",
                room_type_id="RT-STD",
                check_in_date=tomorrow,
                check_out_date=day_after,
                guests=11,  # Above maximum
                package_type="simple",
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("guests",) for err in errors)

    def test_package_type_enum_validation(self):
        """Test that package_type must be a valid enum value."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PVR-002",
                room_type_id="RT-STD",
                check_in_date=tomorrow,
                check_out_date=day_after,
                guests=2,
                package_type="invalid",  # Invalid enum value
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("package_type",) for err in errors)

    def test_required_field_validation(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PVR-002",
                # Missing required fields
            )

        errors = exc_info.value.errors()
        # Should have errors for missing required fields
        assert len(errors) > 0

    def test_check_in_date_past_validation(self):
        """Test that check_in_date cannot be in the past."""
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PVR-002",
                room_type_id="RT-STD",
                check_in_date=yesterday,  # Past date
                check_out_date=tomorrow,
                guests=2,
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("check_in_date",) for err in errors)
        assert any("future" in err["msg"].lower() for err in errors)

    def test_check_out_date_ordering_validation(self):
        """Test that check_out_date must be after check_in_date."""
        tomorrow = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PVR-002",
                room_type_id="RT-STD",
                check_in_date=tomorrow,
                check_out_date=tomorrow,  # Same as check_in_date
                guests=2,
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("check_out_date",) for err in errors)
        assert any("after" in err["msg"].lower() for err in errors)


class TestAvailabilityRequestValidation:
    """Test validation for AvailabilityRequest model."""

    def test_valid_availability_request(self):
        """Test that a valid availability request passes validation."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        request = AvailabilityRequestWithValidation(
            hotel_id="H-PVR-002",
            check_in_date=tomorrow,
            check_out_date=day_after,
            guests=2,
        )

        assert request.hotel_id == "H-PVR-002"
        assert request.guests == 2

    def test_date_validation(self):
        """Test that date validation works for availability requests."""
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            AvailabilityRequestWithValidation(
                hotel_id="H-PVR-002",
                check_in_date=yesterday,
                check_out_date=tomorrow,
                guests=2,
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("check_in_date",) for err in errors)


class TestReservationRequestValidation:
    """Test validation for ReservationRequest model."""

    def test_valid_reservation_request_with_quote(self):
        """Test that a valid reservation request with quote_id passes validation."""
        request = ReservationRequestWithValidation(
            quote_id="Q-20240315-ABC123",
            guest_name="John Doe",
            guest_email="john.doe@example.com",
            guest_phone="+1-555-123-4567",
        )

        assert request.quote_id == "Q-20240315-ABC123"
        assert request.guest_name == "John Doe"

    def test_email_validation(self):
        """Test that guest_email must be a valid email address."""
        with pytest.raises(ValidationError) as exc_info:
            ReservationRequestWithValidation(
                quote_id="Q-20240315-ABC123",
                guest_name="John Doe",
                guest_email="not-an-email",  # Invalid email
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("guest_email",) for err in errors)


class TestReservationUpdateRequestValidation:
    """Test validation for ReservationUpdateRequest model."""

    def test_valid_update_request(self):
        """Test that a valid update request passes validation."""
        request = ReservationUpdateRequest(
            guest_name="Jane Doe",
            guest_email="jane.doe@example.com",
            status="checked_in",
        )

        assert request.guest_name == "Jane Doe"
        assert request.status == "checked_in"

    def test_status_enum_validation(self):
        """Test that status must be a valid enum value."""
        with pytest.raises(ValidationError) as exc_info:
            ReservationUpdateRequest(
                status="invalid_status",  # Invalid enum value
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("status",) for err in errors)


class TestCheckoutRequestValidation:
    """Test validation for CheckoutRequest model."""

    def test_valid_checkout_request(self):
        """Test that a valid checkout request passes validation."""
        request = CheckoutRequest(
            additional_charges=50.0,
            payment_method="card",
        )

        assert request.additional_charges == 50.0
        assert request.payment_method == "card"

    def test_payment_method_enum_validation(self):
        """Test that payment_method must be a valid enum value."""
        with pytest.raises(ValidationError) as exc_info:
            CheckoutRequest(
                payment_method="invalid_method",  # Invalid enum value
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("payment_method",) for err in errors)


class TestHousekeepingRequestValidation:
    """Test validation for HousekeepingRequest model."""

    def test_valid_housekeeping_request(self):
        """Test that a valid housekeeping request passes validation."""
        request = HousekeepingRequest(
            hotel_id="H-PVR-002",
            room_number="101",
            guest_name="John Doe",
            request_type="cleaning",
            description="Please clean the bathroom",
        )

        assert request.hotel_id == "H-PVR-002"
        assert request.request_type == "cleaning"

    def test_request_type_enum_validation(self):
        """Test that request_type must be a valid enum value."""
        with pytest.raises(ValidationError) as exc_info:
            HousekeepingRequest(
                hotel_id="H-PVR-002",
                room_number="101",
                guest_name="John Doe",
                request_type="invalid_type",  # Invalid enum value
            )

        errors = exc_info.value.errors()
        assert any(err["loc"] == ("request_type",) for err in errors)

    def test_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError) as exc_info:
            HousekeepingRequest(
                hotel_id="H-PVR-002",
                # Missing required fields
            )

        errors = exc_info.value.errors()
        assert len(errors) > 0
