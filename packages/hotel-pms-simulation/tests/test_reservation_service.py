# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for simplified reservation service."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from hotel_pms_simulation.services.reservation_service import (
    ReservationService,
)


class TestReservationService:
    """Test cases for ReservationService."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked DynamoDB."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.return_value = mock_dynamodb

            # Mock table instances
            mock_reservations_table = MagicMock()
            mock_hotels_table = MagicMock()
            mock_room_types_table = MagicMock()

            mock_dynamodb.Table.side_effect = lambda table_name: {
                "hotel-reservations": mock_reservations_table,
                "hotel-hotels": mock_hotels_table,
                "hotel-room-types": mock_room_types_table,
            }.get(table_name)

            service = ReservationService()
            service.reservations_table = mock_reservations_table
            service.hotels_table = mock_hotels_table
            service.room_types_table = mock_room_types_table

            return service

    @pytest.fixture
    def sample_reservation_data(self):
        """Sample reservation creation data."""
        return {
            "hotel_id": "H-PVR-002",
            "room_type_id": "RT-STD",
            "guest_name": "John Doe",
            "guest_email": "john.doe@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-03-15",
            "check_out_date": "2024-03-17",
            "guests": 2,
            "package_type": "breakfast",
        }

    @pytest.fixture
    def sample_reservation_record(self):
        """Sample reservation database record."""
        return {
            "reservation_id": "CONF-1234567890123",
            "hotel_id": "H-PVR-002",
            "room_type_id": "RT-STD",
            "guest_name": "John Doe",
            "guest_email": "john.doe@example.com",
            "guest_phone": "+1234567890",
            "check_in_date": "2024-03-15",
            "check_out_date": "2024-03-17",
            "guests": 2,
            "package_type": "breakfast",
            "status": "confirmed",
            "created_at": "2024-03-01T10:00:00.000000",
            "updated_at": "2024-03-01T10:00:00.000000",
        }

    def test_create_reservation_success(self, service, sample_reservation_data):
        """Test successful reservation creation."""
        # Mock successful DynamoDB put_item
        service.reservations_table.put_item = Mock()

        # Mock time.time() to get predictable confirmation ID
        with patch("time.time", return_value=1234567890.123):
            with patch(
                "hotel_pms_simulation.services.reservation_service.datetime"
            ) as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2024-03-01T10:00:00.000000"
                )

                result = service.create_reservation(**sample_reservation_data)

        # Verify result
        assert result["reservation_id"] == "CONF-1234567890123"
        assert result["status"] == "confirmed"
        assert result["guest_name"] == "John Doe"
        assert result["guest_email"] == "john.doe@example.com"
        assert result["hotel_id"] == "H-PVR-002"
        assert result["room_type_id"] == "RT-STD"
        assert result["check_in_date"] == "2024-03-15"
        assert result["check_out_date"] == "2024-03-17"
        assert result["guests"] == 2
        assert result["package_type"] == "breakfast"
        assert result["created_at"] == "2024-03-01T10:00:00.000000"

        # Verify DynamoDB put_item was called
        service.reservations_table.put_item.assert_called_once()
        call_args = service.reservations_table.put_item.call_args[1]
        assert call_args["Item"]["reservation_id"] == "CONF-1234567890123"
        assert call_args["Item"]["guest_name"] == "John Doe"

    def test_create_reservation_dynamodb_error(self, service, sample_reservation_data):
        """Test reservation creation when DynamoDB fails."""
        # Mock DynamoDB error
        service.reservations_table.put_item = Mock(
            side_effect=Exception("DynamoDB error")
        )

        # Execute and verify exception
        with pytest.raises(
            Exception, match="Failed to create reservation: DynamoDB error"
        ):
            service.create_reservation(**sample_reservation_data)

    def test_get_reservation_success(self, service, sample_reservation_record):
        """Test successful reservation retrieval."""
        # Mock successful DynamoDB get_item
        service.reservations_table.get_item = Mock(
            return_value={"Item": sample_reservation_record}
        )

        result = service.get_reservation("CONF-1234567890123")

        # Verify result
        assert result == sample_reservation_record

        # Verify DynamoDB get_item was called correctly
        service.reservations_table.get_item.assert_called_once_with(
            Key={"reservation_id": "CONF-1234567890123"}
        )

    def test_get_reservation_not_found(self, service):
        """Test reservation retrieval when reservation doesn't exist."""
        # Mock DynamoDB returning no item
        service.reservations_table.get_item = Mock(return_value={})

        result = service.get_reservation("NONEXISTENT-ID")

        # Verify None is returned
        assert result is None

    def test_get_reservation_dynamodb_error(self, service):
        """Test reservation retrieval when DynamoDB fails."""
        # Mock DynamoDB error
        service.reservations_table.get_item = Mock(
            side_effect=Exception("DynamoDB error")
        )

        # Execute and verify exception
        with pytest.raises(
            Exception, match="Failed to retrieve reservation: DynamoDB error"
        ):
            service.get_reservation("CONF-1234567890123")

    def test_get_reservations_by_hotel_success(
        self, service, sample_reservation_record
    ):
        """Test successful retrieval of reservations by hotel."""
        # Mock successful DynamoDB scan
        service.reservations_table.scan = Mock(
            return_value={"Items": [sample_reservation_record]}
        )

        result = service.get_reservations_by_hotel("H-PVR-002")

        # Verify result
        assert len(result) == 1
        assert result[0] == sample_reservation_record

        # Verify DynamoDB scan was called correctly
        service.reservations_table.scan.assert_called_once_with(
            FilterExpression="hotel_id = :hotel_id",
            ExpressionAttributeValues={":hotel_id": "H-PVR-002"},
        )

    def test_get_reservations_by_hotel_with_limit(
        self, service, sample_reservation_record
    ):
        """Test retrieval of reservations by hotel with limit."""
        # Mock successful DynamoDB scan
        service.reservations_table.scan = Mock(
            return_value={"Items": [sample_reservation_record]}
        )

        result = service.get_reservations_by_hotel("H-PVR-002", limit=5)

        # Verify result
        assert len(result) == 1

        # Verify DynamoDB scan was called with limit
        service.reservations_table.scan.assert_called_once_with(
            FilterExpression="hotel_id = :hotel_id",
            ExpressionAttributeValues={":hotel_id": "H-PVR-002"},
            Limit=5,
        )

    def test_get_reservations_by_hotel_empty_result(self, service):
        """Test retrieval of reservations by hotel when no reservations exist."""
        # Mock DynamoDB returning empty result
        service.reservations_table.scan = Mock(return_value={"Items": []})

        result = service.get_reservations_by_hotel("H-EMPTY-001")

        # Verify empty list is returned
        assert result == []

    def test_get_reservations_by_hotel_dynamodb_error(self, service):
        """Test retrieval of reservations by hotel when DynamoDB fails."""
        # Mock DynamoDB error
        service.reservations_table.scan = Mock(side_effect=Exception("DynamoDB error"))

        # Execute and verify exception
        with pytest.raises(
            Exception, match="Failed to retrieve reservations by hotel: DynamoDB error"
        ):
            service.get_reservations_by_hotel("H-PVR-002")

    def test_get_reservations_by_guest_email_success(
        self, service, sample_reservation_record
    ):
        """Test successful retrieval of reservations by guest email."""
        # Mock successful DynamoDB scan
        service.reservations_table.scan = Mock(
            return_value={"Items": [sample_reservation_record]}
        )

        result = service.get_reservations_by_guest_email("john.doe@example.com")

        # Verify result
        assert len(result) == 1
        assert result[0] == sample_reservation_record

        # Verify DynamoDB scan was called correctly
        service.reservations_table.scan.assert_called_once_with(
            FilterExpression="guest_email = :guest_email",
            ExpressionAttributeValues={":guest_email": "john.doe@example.com"},
        )

    def test_get_reservations_by_guest_email_empty_result(self, service):
        """Test retrieval of reservations by guest email when no reservations exist."""
        # Mock DynamoDB returning empty result
        service.reservations_table.scan = Mock(return_value={"Items": []})

        result = service.get_reservations_by_guest_email("nonexistent@example.com")

        # Verify empty list is returned
        assert result == []

    def test_get_reservations_by_guest_email_dynamodb_error(self, service):
        """Test retrieval of reservations by guest email when DynamoDB fails."""
        # Mock DynamoDB error
        service.reservations_table.scan = Mock(side_effect=Exception("DynamoDB error"))

        # Execute and verify exception
        with pytest.raises(
            Exception,
            match="Failed to retrieve reservations by guest email: DynamoDB error",
        ):
            service.get_reservations_by_guest_email("john.doe@example.com")

    def test_update_reservation_success(self, service, sample_reservation_record):
        """Test successful reservation update."""
        # Mock get_reservation to return existing reservation
        service.get_reservation = Mock(return_value=sample_reservation_record)

        # Mock successful DynamoDB update_item
        updated_record = sample_reservation_record.copy()
        updated_record["guest_name"] = "Jane Doe"
        updated_record["updated_at"] = "2024-03-01T11:00:00.000000"

        service.reservations_table.update_item = Mock(
            return_value={"Attributes": updated_record}
        )

        with patch(
            "hotel_pms_simulation.services.reservation_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-03-01T11:00:00.000000"
            )

            result = service.update_reservation(
                "CONF-1234567890123", {"guest_name": "Jane Doe"}
            )

        # Verify result
        assert result["guest_name"] == "Jane Doe"
        assert result["updated_at"] == "2024-03-01T11:00:00.000000"

        # Verify DynamoDB update_item was called correctly
        service.reservations_table.update_item.assert_called_once()
        call_args = service.reservations_table.update_item.call_args[1]
        assert call_args["Key"] == {"reservation_id": "CONF-1234567890123"}
        assert "guest_name = :guest_name" in call_args["UpdateExpression"]
        assert call_args["ExpressionAttributeValues"][":guest_name"] == "Jane Doe"

    def test_update_reservation_not_found(self, service):
        """Test updating a reservation that doesn't exist."""
        # Mock get_reservation to return None
        service.get_reservation = Mock(return_value=None)

        result = service.update_reservation(
            "NONEXISTENT-ID", {"guest_name": "Jane Doe"}
        )

        # Verify None is returned
        assert result is None

    def test_update_reservation_dynamodb_error(
        self, service, sample_reservation_record
    ):
        """Test reservation update when DynamoDB fails."""
        # Mock get_reservation to return existing reservation
        service.get_reservation = Mock(return_value=sample_reservation_record)

        # Mock DynamoDB error
        service.reservations_table.update_item = Mock(
            side_effect=Exception("DynamoDB error")
        )

        # Execute and verify exception
        with pytest.raises(
            Exception, match="Failed to update reservation: DynamoDB error"
        ):
            service.update_reservation("CONF-1234567890123", {"guest_name": "Jane Doe"})

    def test_checkout_guest_success(self, service):
        """Test successful guest checkout."""
        # Mock update_reservation to return updated record
        updated_record = {
            "reservation_id": "CONF-1234567890123",
            "guest_name": "John Doe",
            "status": "checked_out",
            "checkout_time": "2024-03-17T11:00:00.000000",
            "final_amount": 350.0,
            "payment_status": "completed",
            "updated_at": "2024-03-17T11:00:00.000000",
        }

        service.update_reservation = Mock(return_value=updated_record)

        with patch(
            "hotel_pms_simulation.services.reservation_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-03-17T11:00:00.000000"
            )

            result = service.checkout_guest("CONF-1234567890123", final_amount=350.0)

        # Verify result
        assert result["status"] == "checked_out"
        assert result["checkout_time"] == "2024-03-17T11:00:00.000000"
        assert result["final_amount"] == 350.0
        assert result["payment_status"] == "completed"

        # Verify update_reservation was called with correct fields
        service.update_reservation.assert_called_once()
        call_args = service.update_reservation.call_args[0]
        assert call_args[0] == "CONF-1234567890123"
        update_fields = call_args[1]
        assert update_fields["status"] == "checked_out"
        assert update_fields["checkout_time"] == "2024-03-17T11:00:00.000000"
        assert update_fields["final_amount"] == 350.0
        assert update_fields["payment_status"] == "completed"

    def test_checkout_guest_without_final_amount(self, service):
        """Test guest checkout without final amount."""
        # Mock update_reservation to return updated record
        updated_record = {
            "reservation_id": "CONF-1234567890123",
            "guest_name": "John Doe",
            "status": "checked_out",
            "checkout_time": "2024-03-17T11:00:00.000000",
            "updated_at": "2024-03-17T11:00:00.000000",
        }

        service.update_reservation = Mock(return_value=updated_record)

        with patch(
            "hotel_pms_simulation.services.reservation_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-03-17T11:00:00.000000"
            )

            result = service.checkout_guest("CONF-1234567890123")

        # Verify result
        assert result["status"] == "checked_out"
        assert result["checkout_time"] == "2024-03-17T11:00:00.000000"
        assert "final_amount" not in result
        assert (
            "payment_status" not in result
            or result.get("payment_status") != "completed"
        )

        # Verify update_reservation was called with correct fields
        service.update_reservation.assert_called_once()
        call_args = service.update_reservation.call_args[0]
        update_fields = call_args[1]
        assert update_fields["status"] == "checked_out"
        assert "final_amount" not in update_fields
        assert "payment_status" not in update_fields

    def test_checkout_guest_not_found(self, service):
        """Test checkout when reservation doesn't exist."""
        # Mock update_reservation to return None
        service.update_reservation = Mock(return_value=None)

        result = service.checkout_guest("NONEXISTENT-ID")

        # Verify None is returned
        assert result is None

    def test_checkout_guest_update_error(self, service):
        """Test checkout when update fails."""
        # Mock update_reservation to raise exception
        service.update_reservation = Mock(side_effect=Exception("Update failed"))

        # Execute and verify exception
        with pytest.raises(Exception, match="Failed to checkout guest: Update failed"):
            service.checkout_guest("CONF-1234567890123")

    def test_confirmation_id_generation_uniqueness(
        self, service, sample_reservation_data
    ):
        """Test that confirmation IDs are unique across multiple reservations."""
        # Mock successful DynamoDB put_item
        service.reservations_table.put_item = Mock()

        # Create multiple reservations with different timestamps
        confirmation_ids = []

        for i in range(3):
            with patch("time.time", return_value=1234567890.123 + i):
                with patch(
                    "hotel_pms_simulation.services.reservation_service.datetime"
                ) as mock_datetime:
                    mock_datetime.now.return_value.isoformat.return_value = (
                        f"2024-03-01T10:0{i}:00.000000"
                    )

                    result = service.create_reservation(**sample_reservation_data)
                    confirmation_ids.append(result["reservation_id"])

        # Verify all confirmation IDs are unique
        assert len(set(confirmation_ids)) == 3
        assert confirmation_ids[0] == "CONF-1234567890123"
        assert confirmation_ids[1] == "CONF-1234567891123"
        assert confirmation_ids[2] == "CONF-1234567892123"


class TestReservationServiceIntegration:
    """Integration test scenarios for ReservationService."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked DynamoDB."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.return_value = mock_dynamodb

            # Mock table instances
            mock_reservations_table = MagicMock()
            mock_hotels_table = MagicMock()
            mock_room_types_table = MagicMock()

            mock_dynamodb.Table.side_effect = lambda table_name: {
                "hotel-reservations": mock_reservations_table,
                "hotel-hotels": mock_hotels_table,
                "hotel-room-types": mock_room_types_table,
            }.get(table_name)

            service = ReservationService()
            service.reservations_table = mock_reservations_table
            service.hotels_table = mock_hotels_table
            service.room_types_table = mock_room_types_table

            return service

    def test_complete_reservation_lifecycle(self, service):
        """Test complete reservation lifecycle from creation to checkout."""
        # Step 1: Create reservation
        service.reservations_table.put_item = Mock()

        with patch("time.time", return_value=1234567890.123):
            with patch(
                "hotel_pms_simulation.services.reservation_service.datetime"
            ) as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2024-03-01T10:00:00.000000"
                )

                created_reservation = service.create_reservation(
                    hotel_id="H-PVR-002",
                    room_type_id="RT-STD",
                    guest_name="Alice Johnson",
                    guest_email="alice@example.com",
                    guest_phone="+1234567890",
                    check_in_date="2024-03-15",
                    check_out_date="2024-03-17",
                    guests=2,
                    package_type="breakfast",
                )

        assert created_reservation["reservation_id"] == "CONF-1234567890123"
        assert created_reservation["status"] == "confirmed"

        # Step 2: Retrieve reservation
        service.reservations_table.get_item = Mock(
            return_value={"Item": created_reservation}
        )

        retrieved_reservation = service.get_reservation("CONF-1234567890123")
        assert retrieved_reservation["guest_name"] == "Alice Johnson"

        # Step 3: Update reservation
        service.get_reservation = Mock(return_value=created_reservation)

        updated_record = created_reservation.copy()
        updated_record["guest_phone"] = "+0987654321"
        updated_record["updated_at"] = "2024-03-01T11:00:00.000000"

        service.reservations_table.update_item = Mock(
            return_value={"Attributes": updated_record}
        )

        with patch(
            "hotel_pms_simulation.services.reservation_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-03-01T11:00:00.000000"
            )

            updated_reservation = service.update_reservation(
                "CONF-1234567890123", {"guest_phone": "+0987654321"}
            )

        assert updated_reservation["guest_phone"] == "+0987654321"

        # Step 4: Checkout guest
        checkout_record = updated_reservation.copy()
        checkout_record.update(
            {
                "status": "checked_out",
                "checkout_time": "2024-03-17T11:00:00.000000",
                "final_amount": 350.0,
                "payment_status": "completed",
                "updated_at": "2024-03-17T11:00:00.000000",
            }
        )

        service.update_reservation = Mock(return_value=checkout_record)

        with patch(
            "hotel_pms_simulation.services.reservation_service.datetime"
        ) as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = (
                "2024-03-17T11:00:00.000000"
            )

            final_reservation = service.checkout_guest(
                "CONF-1234567890123", final_amount=350.0
            )

        assert final_reservation["status"] == "checked_out"
        assert final_reservation["final_amount"] == 350.0
        assert final_reservation["payment_status"] == "completed"
