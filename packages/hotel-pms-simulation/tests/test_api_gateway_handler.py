# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for API Gateway handler."""

import json
from datetime import date, timedelta
from unittest.mock import patch

from aws_lambda_powertools.utilities.typing import LambdaContext

from hotel_pms_simulation.handlers.api_gateway_handler import app


class TestAPIGatewayHandler:
    """Test cases for API Gateway handler using Powertools."""

    def setup_method(self):
        """Set up test fixtures."""
        self.context = LambdaContext()
        self.context._aws_request_id = "test-request-id"

        # Use future dates for all tests
        self.tomorrow = (date.today() + timedelta(days=1)).isoformat()
        self.day_after = (date.today() + timedelta(days=2)).isoformat()

    def create_api_gateway_event(
        self, method: str, path: str, body: dict = None, query_params: dict = None
    ):
        """Create a mock API Gateway event."""
        event = {
            "httpMethod": method,
            "path": path,
            "headers": {"Content-Type": "application/json"},
            "requestContext": {
                "requestId": "test-request-id",
                "stage": "test",
                "accountId": "123456789012",
                "apiId": "test-api-id",
            },
            "queryStringParameters": query_params,
        }

        if body:
            event["body"] = json.dumps(body)

        return event

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.check_availability")
    def test_check_availability_success(self, mock_check_availability):
        """Test successful availability check."""
        # Arrange
        mock_check_availability.return_value = {
            "hotel_id": "H-PVR-002",
            "available_room_types": [
                {
                    "room_type_id": "RT-STD",
                    "available_rooms": 5,
                    "base_rate": 150.0,
                }
            ],
        }

        event = self.create_api_gateway_event(
            "POST",
            "/availability/check",
            {
                "hotel_id": "H-PVR-002",
                "check_in_date": self.tomorrow,
                "check_out_date": self.day_after,
                "guests": 2,
            },
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["hotel_id"] == "H-PVR-002"
        assert len(body["available_room_types"]) == 1
        mock_check_availability.assert_called_once()

    def test_check_availability_validation_error(self):
        """Test availability check with validation error (past date)."""
        # Arrange
        yesterday = (date.today() - timedelta(days=1)).isoformat()

        event = self.create_api_gateway_event(
            "POST",
            "/availability/check",
            {
                "hotel_id": "H-PVR-002",
                "check_in_date": yesterday,  # Past date - should fail validation
                "check_out_date": self.tomorrow,
                "guests": 2,
            },
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 400
        body = json.loads(response["body"])
        assert "validation failed" in body["message"].lower()

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.generate_quote")
    def test_generate_quote_success(self, mock_generate_quote):
        """Test successful quote generation."""
        # Arrange
        mock_generate_quote.return_value = {
            "hotel_id": "H-PVR-002",
            "room_type_id": "RT-STD",
            "total_cost": 300.0,
            "nights": 2,
            "base_rate": 150.0,
        }

        event = self.create_api_gateway_event(
            "POST",
            "/quotes/generate",
            {
                "hotel_id": "H-PVR-002",
                "room_type_id": "RT-STD",
                "check_in_date": self.tomorrow,
                "check_out_date": self.day_after,
                "guests": 2,
            },
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["total_cost"] == 300.0
        assert body["nights"] == 2
        mock_generate_quote.assert_called_once()

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.create_reservation")
    def test_create_reservation_success(self, mock_create_reservation):
        """Test successful reservation creation with quote_id."""
        # Arrange
        mock_create_reservation.return_value = {
            "reservation_id": "RES-123",
            "status": "confirmed",
            "guest_name": "John Doe",
        }

        event = self.create_api_gateway_event(
            "POST",
            "/reservations",
            {
                "quote_id": "Q-20240315-ABC123",
                "guest_name": "John Doe",
                "guest_email": "john@example.com",
                "guest_phone": "+1-555-123-4567",
            },
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["reservation_id"] == "RES-123"
        assert body["status"] == "confirmed"
        mock_create_reservation.assert_called_once()

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.get_reservations")
    def test_get_reservations_success(self, mock_get_reservations):
        """Test successful reservations retrieval."""
        # Arrange
        mock_get_reservations.return_value = {
            "reservations": [
                {
                    "reservation_id": "RES-123",
                    "guest_name": "John Doe",
                    "status": "confirmed",
                }
            ],
            "total_count": 1,
        }

        event = self.create_api_gateway_event(
            "GET", "/reservations", query_params={"hotel_id": "H-PVR-002"}
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["total_count"] == 1
        assert len(body["reservations"]) == 1
        mock_get_reservations.assert_called_once()

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.get_reservation")
    def test_get_reservation_success(self, mock_get_reservation):
        """Test successful single reservation retrieval."""
        # Arrange
        mock_get_reservation.return_value = {
            "reservation_id": "RES-123",
            "guest_name": "John Doe",
            "status": "confirmed",
        }

        event = self.create_api_gateway_event("GET", "/reservations/RES-123")

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["reservation_id"] == "RES-123"
        mock_get_reservation.assert_called_once_with(reservation_id="RES-123")

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.get_reservation")
    def test_get_reservation_not_found(self, mock_get_reservation):
        """Test reservation not found scenario."""
        # Arrange
        mock_get_reservation.return_value = {
            "error": True,
            "error_code": "NOT_FOUND",
            "message": "Reservation not found",
        }

        event = self.create_api_gateway_event("GET", "/reservations/INVALID-ID")

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 404
        body = json.loads(response["body"])
        assert "not found" in body["message"].lower()

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.update_reservation")
    def test_update_reservation_success(self, mock_update_reservation):
        """Test successful reservation update."""
        # Arrange
        mock_update_reservation.return_value = {
            "reservation_id": "RES-123",
            "guest_name": "Jane Doe",
            "status": "confirmed",
        }

        event = self.create_api_gateway_event(
            "PUT", "/reservations/RES-123", {"guest_name": "Jane Doe"}
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["guest_name"] == "Jane Doe"
        mock_update_reservation.assert_called_once()

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.checkout_guest")
    def test_checkout_guest_success(self, mock_checkout_guest):
        """Test successful guest checkout."""
        # Arrange
        mock_checkout_guest.return_value = {
            "reservation_id": "RES-123",
            "status": "checked_out",
            "final_bill": 350.0,
        }

        event = self.create_api_gateway_event(
            "POST",
            "/reservations/RES-123/checkout",
            {"additional_charges": 50.0, "payment_method": "card"},
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["status"] == "checked_out"
        assert body["final_bill"] == 350.0
        mock_checkout_guest.assert_called_once()

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.get_hotels")
    def test_get_hotels_success(self, mock_get_hotels):
        """Test successful hotels retrieval."""
        # Arrange
        mock_get_hotels.return_value = {
            "hotels": [
                {
                    "hotel_id": "H-PVR-002",
                    "name": "Paraiso Vallarta",
                    "location": "Puerto Vallarta, Mexico",
                }
            ],
            "total_count": 1,
        }

        event = self.create_api_gateway_event("GET", "/hotels")

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["total_count"] == 1
        assert len(body["hotels"]) == 1
        mock_get_hotels.assert_called_once()

    @patch(
        "hotel_pms_simulation.handlers.api_gateway_handler.create_housekeeping_request"
    )
    def test_create_housekeeping_request_success(self, mock_create_housekeeping):
        """Test successful housekeeping request creation."""
        # Arrange
        mock_create_housekeeping.return_value = {
            "request_id": "REQ-123",
            "status": "pending",
            "request_type": "cleaning",
        }

        event = self.create_api_gateway_event(
            "POST",
            "/requests/housekeeping",
            {
                "hotel_id": "H-PVR-002",
                "room_number": "101",
                "guest_name": "John Doe",
                "request_type": "cleaning",
                "description": "Need fresh towels",
            },
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 200
        body = json.loads(response["body"])
        assert body["request_id"] == "REQ-123"
        assert body["request_type"] == "cleaning"
        mock_create_housekeeping.assert_called_once()

    def test_invalid_path(self):
        """Test handling of invalid API path."""
        # Arrange
        event = self.create_api_gateway_event("GET", "/invalid/path")

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 404

    @patch("hotel_pms_simulation.handlers.api_gateway_handler.check_availability")
    def test_internal_server_error(self, mock_check_availability):
        """Test handling of internal server errors."""
        # Arrange
        mock_check_availability.side_effect = Exception("Database connection failed")

        event = self.create_api_gateway_event(
            "POST",
            "/availability/check",
            {
                "hotel_id": "H-PVR-002",
                "check_in_date": self.tomorrow,
                "check_out_date": self.day_after,
                "guests": 2,
            },
        )

        # Act
        response = app.resolve(event, self.context)

        # Assert
        assert response["statusCode"] == 500
        body = json.loads(response["body"])
        assert "Failed to check availability" in body["message"]

    def test_query_parameter_conversion(self):
        """Test that query parameters are properly converted."""
        # Arrange
        with patch(
            "hotel_pms_simulation.handlers.api_gateway_handler.get_reservations"
        ) as mock_get_reservations:
            mock_get_reservations.return_value = {"reservations": [], "total_count": 0}

            event = self.create_api_gateway_event(
                "GET",
                "/reservations",
                query_params={"hotel_id": "H-PVR-002", "limit": "10"},
            )

            # Act
            response = app.resolve(event, self.context)

            # Assert
            assert response["statusCode"] == 200
            # Verify that limit was converted to int
            call_args = mock_get_reservations.call_args[1]
            assert call_args["limit"] == 10
            assert isinstance(call_args["limit"], int)
