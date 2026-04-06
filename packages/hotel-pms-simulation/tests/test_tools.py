# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for simplified Hotel PMS tool interfaces."""

from unittest.mock import patch

import pytest

from hotel_pms_simulation.tools.tools import HotelPMSTools


class TestHotelPMSTools:
    """Test class for HotelPMSTools."""

    @pytest.fixture
    def tools(self):
        """Create HotelPMSTools instance with mocked services."""
        with (
            patch(
                "hotel_pms_simulation.tools.tools.AvailabilityService"
            ) as mock_availability,
            patch(
                "hotel_pms_simulation.tools.tools.ReservationService"
            ) as mock_reservation,
            patch("hotel_pms_simulation.tools.tools.HotelService") as mock_hotel,
        ):
            tools = HotelPMSTools()
            tools.availability_service = mock_availability.return_value
            tools.reservation_service = mock_reservation.return_value
            tools.hotel_service = mock_hotel.return_value
            return tools

    def test_check_availability_success(self, tools):
        """Test successful availability check."""
        # Mock service response
        tools.availability_service.check_availability.return_value = {
            "hotel_id": "H-TEST-001",
            "available": True,
            "available_room_types": [
                {
                    "room_type_id": "RT-STD",
                    "available_rooms": 5,
                    "base_rate": 150.0,
                }
            ],
        }

        result = tools.check_availability(
            hotel_id="H-TEST-001",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        assert result["hotel_id"] == "H-TEST-001"
        assert result["check_in_date"] == "2024-03-15"
        assert result["check_out_date"] == "2024-03-17"
        assert result["guests"] == 2
        assert len(result["available_room_types"]) == 1
        assert result["available_room_types"][0]["room_type_id"] == "RT-STD"

    def test_check_availability_validation_errors(self, tools):
        """Test validation errors in check_availability."""
        # Test empty hotel_id
        result = tools.check_availability("", "2024-03-15", "2024-03-17", 2)
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "hotel_id" in result["message"]

        # Test invalid guests
        result = tools.check_availability("H-TEST-001", "2024-03-15", "2024-03-17", 0)
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "guests" in result["message"]

        # Test invalid date format
        result = tools.check_availability("H-TEST-001", "invalid-date", "2024-03-17", 2)
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "date format" in result["message"]

    def test_check_availability_service_error(self, tools):
        """Test service error handling in check_availability."""
        tools.availability_service.check_availability.return_value = {
            "available": False,
            "message": "Hotel not found",
        }

        result = tools.check_availability("H-INVALID", "2024-03-15", "2024-03-17", 2)
        assert result["error"] is True
        assert result["error_code"] == "AVAILABILITY_ERROR"
        assert "Hotel not found" in result["message"]

    def test_check_availability_detailed_package(self, tools):
        """Test detailed package type in check_availability."""
        # Mock availability service response
        tools.availability_service.check_availability.return_value = {
            "hotel_id": "H-TEST-001",
            "available": True,
            "available_room_types": [
                {
                    "room_type_id": "RT-STD",
                    "available_rooms": 5,
                    "base_rate": 150.0,
                }
            ],
        }

        # Mock quote service response
        tools.availability_service.generate_quote.return_value = {
            "total_cost": 600.0,
        }

        result = tools.check_availability(
            hotel_id="H-TEST-001",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
            package_type="detailed",
        )

        assert result["available_room_types"][0]["total_cost"] == 600.0
        tools.availability_service.generate_quote.assert_called_once()

    def test_generate_quote_success(self, tools):
        """Test successful quote generation."""
        tools.availability_service.generate_quote.return_value = {
            "hotel_id": "H-TEST-001",
            "room_type_id": "RT-STD",
            "nights": 2,
            "base_rate": 150.0,
            "total_cost": 600.0,
            "guest_multiplier": 1.0,
            "pricing_breakdown": {
                "base_rate_per_night": 150.0,
                "nights": 2,
                "guest_multiplier": 1.0,
                "subtotal": 300.0,
                "total_with_guest_adjustment": 600.0,
            },
        }

        result = tools.generate_quote(
            hotel_id="H-TEST-001",
            room_type_id="RT-STD",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
        )

        assert result["hotel_id"] == "H-TEST-001"
        assert result["room_type_id"] == "RT-STD"
        assert result["total_cost"] == 600.0
        assert result["nights"] == 2

    def test_generate_quote_validation_errors(self, tools):
        """Test validation errors in generate_quote."""
        # Test empty room_type_id
        result = tools.generate_quote("H-TEST-001", "", "2024-03-15", "2024-03-17", 2)
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "room_type_id" in result["message"]

    def test_generate_quote_detailed_package(self, tools):
        """Test detailed package type in generate_quote."""
        tools.availability_service.generate_quote.return_value = {
            "hotel_id": "H-TEST-001",
            "room_type_id": "RT-STD",
            "nights": 2,
            "base_rate": 150.0,
            "total_cost": 600.0,
            "guest_multiplier": 1.0,
            "pricing_breakdown": {
                "base_rate_per_night": 150.0,
                "nights": 2,
                "guest_multiplier": 1.0,
                "subtotal": 300.0,
                "total_with_guest_adjustment": 600.0,
            },
        }

        result = tools.generate_quote(
            hotel_id="H-TEST-001",
            room_type_id="RT-STD",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
            package_type="detailed",
        )

        assert "pricing_breakdown" in result
        assert "guest_multiplier" in result

    def test_create_reservation_success(self, tools):
        """Test successful reservation creation with quote_id (only supported method)."""
        # Mock quote retrieval
        tools.availability_service.get_quote.return_value = {
            "quote_id": "Q-20240315-ABC123",
            "hotel_id": "H-TEST-001",
            "room_type_id": "RT-STD",
            "check_in_date": "2024-03-15",
            "check_out_date": "2024-03-17",
            "guests": 2,
            "total_cost": 300.0,
            "expires_at": "2024-03-15T18:00:00Z",
        }

        # Mock reservation creation
        tools.reservation_service.create_reservation.return_value = {
            "reservation_id": "CONF-123456789",
            "status": "confirmed",
            "guest_name": "John Doe",
            "guest_email": "john@example.com",
            "guest_phone": "+1-555-123-4567",
            "hotel_id": "H-TEST-001",
            "room_type_id": "RT-STD",
            "check_in_date": "2024-03-15",
            "check_out_date": "2024-03-17",
            "guests": 2,
            "package_type": "simple",
            "created_at": "2024-01-01T12:00:00",
        }

        result = tools.create_reservation(
            quote_id="Q-20240315-ABC123",
            guest_name="John Doe",
            guest_email="john@example.com",
            guest_phone="+1-555-123-4567",
        )

        assert result["reservation_id"] == "CONF-123456789"
        assert result["status"] == "confirmed"
        assert result["guest_name"] == "John Doe"
        tools.availability_service.get_quote.assert_called_once_with(
            "Q-20240315-ABC123"
        )

    def test_create_reservation_with_quote_id_success(self, tools):
        """Test successful reservation creation using quote_id."""
        # Mock quote retrieval
        tools.availability_service.get_quote.return_value = {
            "quote_id": "Q-20240315-ABC123",
            "hotel_id": "H-TEST-001",
            "room_type_id": "RT-STD",
            "check_in_date": "2024-03-15",
            "check_out_date": "2024-03-17",
            "guests": 2,
            "total_cost": 300.0,
            "expires_at": "2024-03-15T18:00:00Z",
        }

        # Mock reservation creation
        tools.reservation_service.create_reservation.return_value = {
            "reservation_id": "CONF-123456789",
            "status": "confirmed",
            "guest_name": "John Doe",
            "guest_email": "john@example.com",
            "guest_phone": "+1-555-123-4567",
            "hotel_id": "H-TEST-001",
            "room_type_id": "RT-STD",
            "check_in_date": "2024-03-15",
            "check_out_date": "2024-03-17",
            "guests": 2,
            "package_type": "simple",
            "created_at": "2024-01-01T12:00:00",
        }

        result = tools.create_reservation(
            quote_id="Q-20240315-ABC123",
            guest_name="John Doe",
            guest_email="john@example.com",
            guest_phone="+1-555-123-4567",
        )

        assert result["reservation_id"] == "CONF-123456789"
        assert result["status"] == "confirmed"
        assert result["guest_name"] == "John Doe"
        tools.availability_service.get_quote.assert_called_once_with(
            "Q-20240315-ABC123"
        )

    def test_create_reservation_with_quote_id_not_found(self, tools):
        """Test reservation creation with non-existent quote_id."""
        # Mock quote not found
        tools.availability_service.get_quote.return_value = None

        result = tools.create_reservation(
            quote_id="Q-INVALID",
            guest_name="John Doe",
            guest_email="john@example.com",
            guest_phone="+1-555-123-4567",
        )

        assert result["error"] is True
        assert result["error_code"] == "QUOTE_NOT_FOUND"
        assert "not found or has expired" in result["message"]

    def test_create_reservation_with_quote_id_expired(self, tools):
        """Test reservation creation with expired quote_id."""
        # Mock expired quote (get_quote returns None for expired quotes)
        tools.availability_service.get_quote.return_value = None

        result = tools.create_reservation(
            quote_id="Q-20240315-EXPIRED",
            guest_name="John Doe",
            guest_email="john@example.com",
            guest_phone="+1-555-123-4567",
        )

        assert result["error"] is True
        assert result["error_code"] == "QUOTE_NOT_FOUND"

    def test_create_reservation_validation_errors(self, tools):
        """Test validation errors in create_reservation."""
        # Test empty quote_id
        result = tools.create_reservation(
            quote_id="",
            guest_name="John Doe",
            guest_email="john@example.com",
            guest_phone="+1-555-123-4567",
        )
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "quote_id" in result["message"]

        # Test empty guest_name
        result = tools.create_reservation(
            quote_id="Q-20240315-ABC123",
            guest_name="",
            guest_email="john@example.com",
            guest_phone="+1-555-123-4567",
        )
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "guest_name" in result["message"]

        # Test empty guest_email
        result = tools.create_reservation(
            quote_id="Q-20240315-ABC123",
            guest_name="John Doe",
            guest_email="",
            guest_phone="+1-555-123-4567",
        )
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "guest_email" in result["message"]

        # Test empty guest_phone
        result = tools.create_reservation(
            quote_id="Q-20240315-ABC123",
            guest_name="John Doe",
            guest_email="john@example.com",
            guest_phone="",
        )
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "guest_phone" in result["message"]

    def test_get_reservation_success(self, tools):
        """Test successful reservation retrieval."""
        tools.reservation_service.get_reservation.return_value = {
            "reservation_id": "CONF-123456789",
            "status": "confirmed",
            "guest_name": "John Doe",
            "hotel_id": "H-TEST-001",
        }

        result = tools.get_reservation("CONF-123456789")

        assert result["reservation_id"] == "CONF-123456789"
        assert result["guest_name"] == "John Doe"

    def test_get_reservation_not_found(self, tools):
        """Test reservation not found."""
        tools.reservation_service.get_reservation.return_value = None

        result = tools.get_reservation("CONF-INVALID")

        assert result["error"] is True
        assert result["error_code"] == "NOT_FOUND"

    def test_get_reservations_by_hotel(self, tools):
        """Test getting reservations by hotel."""
        tools.reservation_service.get_reservations_by_hotel.return_value = [
            {"reservation_id": "CONF-1", "guest_name": "John Doe"},
            {"reservation_id": "CONF-2", "guest_name": "Jane Smith"},
        ]

        result = tools.get_reservations(hotel_id="H-TEST-001")

        assert result["total_count"] == 2
        assert len(result["reservations"]) == 2

    def test_get_reservations_by_guest_email(self, tools):
        """Test getting reservations by guest email."""
        tools.reservation_service.get_reservations_by_guest_email.return_value = [
            {"reservation_id": "CONF-1", "guest_name": "John Doe"},
        ]

        result = tools.get_reservations(guest_email="john@example.com")

        assert result["total_count"] == 1
        assert len(result["reservations"]) == 1

    def test_get_reservations_validation_error(self, tools):
        """Test validation error when neither hotel_id nor guest_email provided."""
        result = tools.get_reservations()

        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "Either hotel_id or guest_email is required" in result["message"]

    def test_update_reservation_success(self, tools):
        """Test successful reservation update."""
        tools.reservation_service.update_reservation.return_value = {
            "reservation_id": "CONF-123456789",
            "status": "checked_in",
            "guest_name": "John Doe Updated",
        }

        result = tools.update_reservation(
            reservation_id="CONF-123456789",
            guest_name="John Doe Updated",
            status="checked_in",
        )

        assert result["reservation_id"] == "CONF-123456789"
        assert result["status"] == "checked_in"
        assert result["guest_name"] == "John Doe Updated"

    def test_update_reservation_not_found(self, tools):
        """Test update reservation not found."""
        tools.reservation_service.update_reservation.return_value = None

        result = tools.update_reservation(
            reservation_id="CONF-INVALID",
            status="checked_in",
        )

        assert result["error"] is True
        assert result["error_code"] == "NOT_FOUND"

    def test_checkout_guest_success(self, tools):
        """Test successful guest checkout."""
        tools.reservation_service.checkout_guest.return_value = {
            "reservation_id": "CONF-123456789",
            "status": "checked_out",
            "guest_name": "John Doe",
            "checkout_time": "2024-03-17T11:00:00",
        }

        result = tools.checkout_guest(
            reservation_id="CONF-123456789",
            additional_charges=50.0,
            payment_method="card",
        )

        assert result["reservation_id"] == "CONF-123456789"
        assert result["status"] == "checked_out"
        assert result["payment_method"] == "card"

    def test_checkout_guest_validation_errors(self, tools):
        """Test validation errors in checkout_guest."""
        # Test negative additional_charges
        result = tools.checkout_guest(
            reservation_id="CONF-123456789",
            additional_charges=-10.0,
        )
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "additional_charges cannot be negative" in result["message"]

    def test_get_hotels_success(self, tools):
        """Test successful hotels retrieval."""
        tools.hotel_service.get_hotels.return_value = {
            "hotels": [
                {"hotel_id": "H-TEST-001", "name": "Test Hotel 1"},
                {"hotel_id": "H-TEST-002", "name": "Test Hotel 2"},
            ],
            "total_count": 2,
        }

        result = tools.get_hotels()

        assert result["total_count"] == 2
        assert len(result["hotels"]) == 2

    def test_get_hotels_with_limit(self, tools):
        """Test hotels retrieval with limit."""
        tools.hotel_service.get_hotels.return_value = {
            "hotels": [
                {"hotel_id": "H-TEST-001", "name": "Test Hotel 1"},
            ],
            "total_count": 1,
        }

        result = tools.get_hotels(limit=1)

        assert result["total_count"] == 1
        tools.hotel_service.get_hotels.assert_called_once_with(1)

    def test_get_hotels_validation_error(self, tools):
        """Test validation error in get_hotels."""
        result = tools.get_hotels(limit=0)

        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "limit must be a positive integer" in result["message"]

    def test_create_housekeeping_request_success(self, tools):
        """Test successful housekeeping request creation."""
        tools.hotel_service.create_housekeeping_request.return_value = {
            "request_id": "REQ-123456789",
            "hotel_id": "H-TEST-001",
            "room_number": "101",
            "request_type": "cleaning",
            "description": "Need fresh towels",
            "status": "pending",
            "guest_name": "John Doe",
            "created_at": "2024-01-01T12:00:00",
        }

        result = tools.create_housekeeping_request(
            hotel_id="H-TEST-001",
            room_number="101",
            guest_name="John Doe",
            request_type="cleaning",
            description="Need fresh towels",
        )

        assert result["request_id"] == "REQ-123456789"
        assert result["request_type"] == "cleaning"
        assert result["status"] == "pending"

    def test_create_housekeeping_request_validation_errors(self, tools):
        """Test validation errors in create_housekeeping_request."""
        # Test empty room_number
        result = tools.create_housekeeping_request(
            hotel_id="H-TEST-001",
            room_number="",
            guest_name="John Doe",
            request_type="cleaning",
        )
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "room_number" in result["message"]

        # Test invalid request_type
        result = tools.create_housekeeping_request(
            hotel_id="H-TEST-001",
            room_number="101",
            guest_name="John Doe",
            request_type="invalid_type",
        )
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert "request_type must be one of" in result["message"]

    def test_exception_handling(self, tools):
        """Test exception handling in all tools."""
        # Mock service to raise exception
        tools.availability_service.check_availability.side_effect = Exception(
            "Service error"
        )

        result = tools.check_availability("H-TEST-001", "2024-03-15", "2024-03-17", 2)

        assert result["error"] is True
        assert result["error_code"] == "INTERNAL_ERROR"
        assert "Service error" in result["message"]
