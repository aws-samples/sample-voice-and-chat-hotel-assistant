# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for simplified availability service with blackout date rules."""

from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from hotel_pms_simulation.services.availability_service import (
    AvailabilityService,
)


class TestAvailabilityService:
    """Test cases for AvailabilityService with blackout date logic."""

    @pytest.fixture
    def service(self):
        """Create simplified availability service instance with mocked DynamoDB."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.return_value = mock_dynamodb

            # Mock table instances
            mock_hotels_table = MagicMock()
            mock_room_types_table = MagicMock()
            mock_quotes_table = MagicMock()

            def table_side_effect(name):
                if "hotels" in name:
                    return mock_hotels_table
                elif "quotes" in name:
                    return mock_quotes_table
                else:
                    return mock_room_types_table

            mock_dynamodb.Table.side_effect = table_side_effect

            service = AvailabilityService()
            service.hotels_table = mock_hotels_table
            service.room_types_table = mock_room_types_table
            service.quotes_table = mock_quotes_table

            return service

    @pytest.fixture
    def sample_hotel(self):
        """Sample hotel data."""
        return {
            "hotel_id": "H-PVR-002",
            "name": "Paraiso Vallarta",
            "location": "Puerto Vallarta, Mexico",
            "timezone": "America/Mexico_City",
        }

    @pytest.fixture
    def sample_room_types(self):
        """Sample room types data."""
        return [
            {
                "room_type_id": "RT-STD",
                "hotel_id": "H-PVR-002",
                "name": "Standard Room",
                "max_occupancy": 2,
                "base_rate": 150.0,
            },
            {
                "room_type_id": "RT-SUP",
                "hotel_id": "H-PVR-002",
                "name": "Superior Room",
                "max_occupancy": 3,
                "base_rate": 200.0,
            },
            {
                "room_type_id": "RT-STE",
                "hotel_id": "H-PVR-002",
                "name": "Suite",
                "max_occupancy": 4,
                "base_rate": 350.0,
            },
        ]

    def test_check_availability_available_dates(
        self, service, sample_hotel, sample_room_types
    ):
        """Test availability check for dates that are not blackout dates."""
        # Setup mocks for available dates (not 5th-7th of month)
        service.hotels_table.get_item.return_value = {"Item": sample_hotel}
        service.room_types_table.scan.return_value = {"Items": sample_room_types}

        # Test dates that don't include blackout dates
        result = service.check_availability(
            hotel_id="H-PVR-002",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify availability
        assert result["available"] is True
        assert result["hotel_id"] == "H-PVR-002"
        assert (
            len(result["available_room_types"]) == 3
        )  # All room types available for 2 guests

        # Verify room type details
        room_types = result["available_room_types"]
        std_room = next(rt for rt in room_types if rt["room_type_id"] == "RT-STD")
        assert std_room["available_rooms"] == 5  # Standard rooms have 5 available
        assert std_room["base_rate"] == 150.0

    def test_check_availability_blackout_dates_5th(self, service):
        """Test availability check for blackout dates (5th of month)."""
        result = service.check_availability(
            hotel_id="H-PVR-002",
            check_in_date="2024-03-05",
            check_out_date="2024-03-07",
            guests=2,
        )

        # Verify unavailable due to blackout dates
        assert result["available"] is False
        assert result["hotel_id"] == "H-PVR-002"
        assert "Fully booked" in result["message"]

    def test_check_availability_blackout_dates_6th(self, service):
        """Test availability check for blackout dates (6th of month)."""
        result = service.check_availability(
            hotel_id="H-PVR-002",
            check_in_date="2024-03-06",
            check_out_date="2024-03-08",
            guests=2,
        )

        # Verify unavailable due to blackout dates
        assert result["available"] is False
        assert "Fully booked" in result["message"]

    def test_check_availability_blackout_dates_7th(self, service):
        """Test availability check for blackout dates (7th of month)."""
        result = service.check_availability(
            hotel_id="H-PVR-002",
            check_in_date="2024-03-07",
            check_out_date="2024-03-09",
            guests=2,
        )

        # Verify unavailable due to blackout dates
        assert result["available"] is False
        assert "Fully booked" in result["message"]

    def test_check_availability_spanning_blackout_dates(self, service):
        """Test availability check for date range that spans blackout dates."""
        result = service.check_availability(
            hotel_id="H-PVR-002",
            check_in_date="2024-03-04",
            check_out_date="2024-03-08",
            guests=2,
        )

        # Verify unavailable due to blackout dates in range
        assert result["available"] is False
        assert "Fully booked" in result["message"]

    def test_check_availability_invalid_date_format(self, service):
        """Test availability check with invalid date format."""
        result = service.check_availability(
            hotel_id="H-PVR-002",
            check_in_date="invalid-date",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error response
        assert result["available"] is False
        assert "Invalid date format" in result["message"]

    def test_check_availability_hotel_not_found(self, service):
        """Test availability check when hotel is not found."""
        service.hotels_table.get_item.return_value = {}  # No Item key

        result = service.check_availability(
            hotel_id="NONEXISTENT",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error response
        assert result["available"] is False
        assert "Hotel NONEXISTENT not found" in result["message"]

    def test_has_blackout_dates_no_blackout(self, service):
        """Test blackout date detection for dates without blackout dates."""
        check_in = date(2024, 3, 15)
        check_out = date(2024, 3, 17)

        result = service._has_blackout_dates(check_in, check_out)
        assert result is False

    def test_has_blackout_dates_with_blackout(self, service):
        """Test blackout date detection for dates with blackout dates."""
        # Test each blackout date
        for blackout_day in [5, 6, 7]:
            check_in = date(2024, 3, blackout_day)
            check_out = date(2024, 3, blackout_day + 1)

            result = service._has_blackout_dates(check_in, check_out)
            assert result is True, f"Should detect blackout on day {blackout_day}"

    def test_get_demo_availability_count(self, service):
        """Test demo availability count logic."""
        # Test standard room types
        assert service._get_demo_availability_count("RT-STD") == 5
        assert service._get_demo_availability_count("standard-room") == 5

        # Test superior room types
        assert service._get_demo_availability_count("RT-SUP") == 3
        assert service._get_demo_availability_count("superior-room") == 3

        # Test suite room types
        assert service._get_demo_availability_count("RT-STE") == 1
        assert service._get_demo_availability_count("suite-room") == 1

        # Test default case
        assert service._get_demo_availability_count("RT-OTHER") == 2

    def test_generate_quote_success(self, service, sample_room_types):
        """Test successful quote generation with DynamoDB storage."""
        room_type = sample_room_types[0]  # Standard room
        service.room_types_table.get_item.return_value = {"Item": room_type}
        service.quotes_table.put_item.return_value = {}  # Mock successful put

        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify quote details
        assert result["hotel_id"] == "H-PVR-002"
        assert result["room_type_id"] == "RT-STD"
        assert result["nights"] == 2
        assert result["base_rate"] == 150.0
        assert result["guests"] == 2
        assert result["guest_multiplier"] == 1.0  # No additional charge for 2 guests
        assert result["total_cost"] == 300.0  # 150 * 2 nights * 1.0 multiplier

        # Verify new fields for DynamoDB storage
        assert "quote_id" in result
        assert "expires_at" in result
        assert result["quote_id"].startswith("Q-")

        # Verify DynamoDB put_item was called
        service.quotes_table.put_item.assert_called_once()

    def test_generate_quote_with_guest_multiplier(self, service, sample_room_types):
        """Test quote generation with guest count multiplier."""
        room_type = sample_room_types[1]  # Superior room
        service.room_types_table.get_item.return_value = {"Item": room_type}
        service.quotes_table.put_item.return_value = {}  # Mock successful put

        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-SUP",
            check_in_date="2024-03-15",
            check_out_date="2024-03-18",
            guests=4,  # 2 additional guests beyond base 2
        )

        # Verify quote with guest multiplier
        assert result["guests"] == 4
        assert result["guest_multiplier"] == 1.5  # 1.0 + (2 * 0.25)
        assert result["nights"] == 3
        expected_total = 200.0 * 3 * 1.5  # base_rate * nights * guest_multiplier
        assert result["total_cost"] == expected_total

        # Verify DynamoDB storage fields
        assert "quote_id" in result
        assert "expires_at" in result

    def test_generate_quote_invalid_date_format(self, service):
        """Test quote generation with invalid date format."""
        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date="invalid-date",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error response
        assert result["error"] is True
        assert "Invalid date format" in result["message"]

    def test_generate_quote_invalid_date_order(self, service):
        """Test quote generation with check-out before check-in."""
        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date="2024-03-17",
            check_out_date="2024-03-15",  # Before check-in
            guests=2,
        )

        # Verify error response
        assert result["error"] is True
        assert "Check-out date must be after check-in date" in result["message"]

    def test_generate_quote_room_type_not_found(self, service):
        """Test quote generation when room type is not found."""
        service.room_types_table.get_item.return_value = {}  # No Item key

        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="NONEXISTENT",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error response
        assert result["error"] is True
        assert "Room type NONEXISTENT not found" in result["message"]

    def test_generate_quote_wrong_hotel(self, service, sample_room_types):
        """Test quote generation when room type belongs to different hotel."""
        room_type = sample_room_types[0].copy()
        room_type["hotel_id"] = "DIFFERENT-HOTEL"
        service.room_types_table.get_item.return_value = {"Item": room_type}

        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error response
        assert result["error"] is True
        assert "Room type does not belong to the specified hotel" in result["message"]

    def test_calculate_guest_multiplier(self, service):
        """Test guest count multiplier calculation."""
        # Test base case (1-2 guests)
        assert service._calculate_guest_multiplier(1) == 1.0
        assert service._calculate_guest_multiplier(2) == 1.0

        # Test additional guests
        assert service._calculate_guest_multiplier(3) == 1.25  # 1.0 + (1 * 0.25)
        assert service._calculate_guest_multiplier(4) == 1.5  # 1.0 + (2 * 0.25)
        assert service._calculate_guest_multiplier(5) == 1.75  # 1.0 + (3 * 0.25)

    def test_pricing_breakdown_structure(self, service, sample_room_types):
        """Test that pricing breakdown contains all required fields."""
        room_type = sample_room_types[2]  # Suite
        service.room_types_table.get_item.return_value = {"Item": room_type}
        service.quotes_table.put_item.return_value = {}  # Mock successful put

        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-STE",
            check_in_date="2024-03-15",
            check_out_date="2024-03-20",  # 5 nights
            guests=3,
        )

        # Verify pricing breakdown structure
        breakdown = result["pricing_breakdown"]
        assert "base_rate_per_night" in breakdown
        assert "nights" in breakdown
        assert "guest_multiplier" in breakdown
        assert "subtotal" in breakdown
        assert "total_with_guest_adjustment" in breakdown

        # Verify calculations
        assert breakdown["base_rate_per_night"] == 350.0
        assert breakdown["nights"] == 5
        assert breakdown["guest_multiplier"] == 1.25  # 3 guests = 1.0 + (1 * 0.25)
        assert breakdown["subtotal"] == 1750.0  # 350 * 5
        assert breakdown["total_with_guest_adjustment"] == 2187.5  # 1750 * 1.25

    def test_generate_quote_dynamodb_storage_error(self, service, sample_room_types):
        """Test quote generation when DynamoDB storage fails."""
        room_type = sample_room_types[0]  # Standard room
        service.room_types_table.get_item.return_value = {"Item": room_type}
        service.quotes_table.put_item.side_effect = Exception("DynamoDB error")

        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify error response
        assert result["error"] is True
        assert "Failed to store quote" in result["message"]

    def test_get_quote_success(self, service):
        """Test successful quote retrieval."""
        quote_id = "Q-20240315-ABC12345"
        mock_quote_item = {
            "quote_id": quote_id,
            "hotel_id": "H-PVR-002",
            "room_type_id": "RT-STD",
            "check_in_date": "2024-03-15",
            "check_out_date": "2024-03-17",
            "guests": 2,
            "nights": 2,
            "base_rate": 150.0,
            "total_cost": 300.0,
            "expires_at": 9999999999,  # Far future timestamp
            "created_at": "2024-03-15T12:00:00",
        }

        service.quotes_table.get_item.return_value = {"Item": mock_quote_item}

        result = service.get_quote(quote_id)

        # Verify quote retrieval
        assert result is not None
        assert result["quote_id"] == quote_id
        assert result["hotel_id"] == "H-PVR-002"
        assert result["total_cost"] == 300.0

        # Verify get_item was called with correct key
        service.quotes_table.get_item.assert_called_once_with(
            Key={"quote_id": quote_id}
        )

    def test_get_quote_not_found(self, service):
        """Test quote retrieval when quote doesn't exist."""
        quote_id = "Q-20240315-NOTFOUND"
        service.quotes_table.get_item.return_value = {}  # No Item key

        result = service.get_quote(quote_id)

        # Verify None returned for non-existent quote
        assert result is None

    def test_get_quote_expired(self, service):
        """Test quote retrieval when quote has expired."""
        quote_id = "Q-20240315-EXPIRED"
        mock_quote_item = {
            "quote_id": quote_id,
            "hotel_id": "H-PVR-002",
            "expires_at": 1000000000,  # Past timestamp (2001)
        }

        service.quotes_table.get_item.return_value = {"Item": mock_quote_item}

        result = service.get_quote(quote_id)

        # Verify None returned for expired quote
        assert result is None

    def test_get_quote_dynamodb_error(self, service):
        """Test quote retrieval when DynamoDB error occurs."""
        quote_id = "Q-20240315-ERROR"
        service.quotes_table.get_item.side_effect = Exception("DynamoDB error")

        result = service.get_quote(quote_id)

        # Verify None returned on error
        assert result is None

    @patch("uuid.uuid4")
    @patch("hotel_pms_simulation.services.availability_service.datetime")
    def test_quote_id_generation(
        self, mock_datetime, mock_uuid, service, sample_room_types
    ):
        """Test that quote IDs are generated correctly."""
        from datetime import datetime

        # Mock datetime and UUID
        mock_now = datetime(2024, 3, 15, 12, 0, 0)
        mock_datetime.now.return_value = mock_now
        mock_datetime.strptime = datetime.strptime  # Keep original strptime
        mock_uuid.return_value.hex = "abcdef1234567890"

        room_type = sample_room_types[0]
        service.room_types_table.get_item.return_value = {"Item": room_type}
        service.quotes_table.put_item.return_value = {}

        result = service.generate_quote(
            hotel_id="H-PVR-002",
            room_type_id="RT-STD",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        # Verify quote ID format
        expected_quote_id = "Q-20240315-ABCDEF12"
        assert result["quote_id"] == expected_quote_id
