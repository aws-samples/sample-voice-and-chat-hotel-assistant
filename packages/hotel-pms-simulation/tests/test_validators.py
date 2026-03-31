# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for custom date validators."""

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from hotel_pms_simulation.models.generated.validators import (
    AvailabilityRequestWithValidation,
    QuoteRequestWithValidation,
)


class TestQuoteRequestValidation:
    """Test custom validators for QuoteRequest."""

    def test_valid_future_check_in_date(self):
        """Test that future check_in_date is accepted."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        request = QuoteRequestWithValidation(
            hotel_id="H-PTL-003",
            room_type_id="JVIL-PTL",
            check_in_date=tomorrow,
            check_out_date=day_after,
            guests=2,
        )

        assert request.check_in_date == tomorrow
        assert request.check_out_date == day_after

    def test_valid_today_check_in_date(self):
        """Test that today's date is accepted for check_in_date."""
        today = date.today()
        tomorrow = date.today() + timedelta(days=1)

        request = QuoteRequestWithValidation(
            hotel_id="H-PTL-003",
            room_type_id="JVIL-PTL",
            check_in_date=today,
            check_out_date=tomorrow,
            guests=2,
        )

        assert request.check_in_date == today

    def test_past_check_in_date_rejected(self):
        """Test that past check_in_date is rejected."""
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PTL-003",
                room_type_id="JVIL-PTL",
                check_in_date=yesterday,
                check_out_date=tomorrow,
                guests=2,
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("check_in_date",)
        assert "must be today or in the future" in errors[0]["msg"]

    def test_check_out_before_check_in_rejected(self):
        """Test that check_out_date before check_in_date is rejected."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PTL-003",
                room_type_id="JVIL-PTL",
                check_in_date=day_after,
                check_out_date=tomorrow,
                guests=2,
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("check_out_date",)
        assert "must be after check_in_date" in errors[0]["msg"]

    def test_check_out_same_as_check_in_rejected(self):
        """Test that check_out_date equal to check_in_date is rejected."""
        tomorrow = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PTL-003",
                room_type_id="JVIL-PTL",
                check_in_date=tomorrow,
                check_out_date=tomorrow,
                guests=2,
            )

        errors = exc_info.value.errors()
        assert len(errors) == 1
        assert errors[0]["loc"] == ("check_out_date",)
        assert "must be after check_in_date" in errors[0]["msg"]

    def test_invalid_date_format_rejected(self):
        """Test that invalid date format is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PTL-003",
                room_type_id="JVIL-PTL",
                check_in_date="01/15/2025",  # Wrong format
                check_out_date="01/17/2025",
                guests=2,
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1
        # Should have date parsing errors

    def test_invalid_date_value_rejected(self):
        """Test that invalid date values are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            QuoteRequestWithValidation(
                hotel_id="H-PTL-003",
                room_type_id="JVIL-PTL",
                check_in_date="2025-02-30",  # Invalid date
                check_out_date="2025-03-01",
                guests=2,
            )

        errors = exc_info.value.errors()
        assert len(errors) >= 1
        # Should have date parsing errors


class TestReservationRequestValidation:
    """Test custom validators for ReservationRequest.

    Note: ReservationRequest now only supports quote-based reservations.
    Date validation is handled during quote generation, not at reservation time.
    """

    pass  # All tests removed - reservation now requires quote_id only


class TestAvailabilityRequestValidation:
    """Test custom validators for AvailabilityRequest."""

    def test_valid_dates(self):
        """Test that valid dates are accepted."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        request = AvailabilityRequestWithValidation(
            hotel_id="H-PTL-003",
            check_in_date=tomorrow,
            check_out_date=day_after,
            guests=2,
        )

        assert request.check_in_date == tomorrow
        assert request.check_out_date == day_after

    def test_past_check_in_date_rejected(self):
        """Test that past check_in_date is rejected."""
        yesterday = date.today() - timedelta(days=1)
        tomorrow = date.today() + timedelta(days=1)

        with pytest.raises(ValidationError) as exc_info:
            AvailabilityRequestWithValidation(
                hotel_id="H-PTL-003",
                check_in_date=yesterday,
                check_out_date=tomorrow,
                guests=2,
            )

        errors = exc_info.value.errors()
        assert any("must be today or in the future" in e["msg"] for e in errors)

    def test_check_out_before_check_in_rejected(self):
        """Test that check_out_date before check_in_date is rejected."""
        tomorrow = date.today() + timedelta(days=1)
        day_after = date.today() + timedelta(days=2)

        with pytest.raises(ValidationError) as exc_info:
            AvailabilityRequestWithValidation(
                hotel_id="H-PTL-003",
                check_in_date=day_after,
                check_out_date=tomorrow,
                guests=2,
            )

        errors = exc_info.value.errors()
        assert any("must be after check_in_date" in e["msg"] for e in errors)
