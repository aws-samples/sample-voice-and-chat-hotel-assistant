# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for simplified hotel service."""

from unittest.mock import MagicMock, Mock, patch

import pytest

from hotel_pms_simulation.services.hotel_service import HotelService


class TestHotelService:
    """Test cases for HotelService."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked DynamoDB."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.return_value = mock_dynamodb

            # Mock table instances
            mock_hotels_table = MagicMock()
            mock_requests_table = MagicMock()

            mock_dynamodb.Table.side_effect = lambda table_name: {
                "hotel-hotels": mock_hotels_table,
                "hotel-requests": mock_requests_table,
            }.get(table_name)

            service = HotelService()
            service.hotels_table = mock_hotels_table
            service.requests_table = mock_requests_table

            return service

    @pytest.fixture
    def sample_hotels(self):
        """Sample hotels data."""
        return [
            {
                "hotel_id": "H-PVR-002",
                "name": "Paraiso Vallarta",
                "location": "Puerto Vallarta, Mexico",
                "timezone": "America/Mexico_City",
                "description": "Luxury beachfront resort",
            },
            {
                "hotel_id": "H-TUL-001",
                "name": "Paraiso Tulum",
                "location": "Tulum, Mexico",
                "timezone": "America/Cancun",
                "description": "Eco-luxury resort in the jungle",
            },
            {
                "hotel_id": "H-CAB-003",
                "name": "Paraiso Los Cabos",
                "location": "Los Cabos, Mexico",
                "timezone": "America/Mazatlan",
                "description": "Desert meets ocean luxury",
            },
            {
                "hotel_id": "H-CAN-004",
                "name": "Grand Paraiso Resort & Spa",
                "location": "Cancun, Mexico",
                "timezone": "America/Cancun",
                "description": "All-inclusive family resort",
            },
        ]

    @pytest.fixture
    def sample_housekeeping_request_data(self):
        """Sample housekeeping request creation data."""
        return {
            "hotel_id": "H-PVR-002",
            "room_number": "101",
            "request_type": "cleaning",
            "description": "Extra towels needed",
            "priority": "normal",
            "guest_name": "John Doe",
        }

    @pytest.fixture
    def sample_housekeeping_request_record(self):
        """Sample housekeeping request database record."""
        return {
            "request_id": "REQ-1234567890123",
            "hotel_id": "H-PVR-002",
            "room_number": "101",
            "request_type": "cleaning",
            "description": "Extra towels needed",
            "priority": "normal",
            "status": "pending",
            "guest_name": "John Doe",
            "created_at": "2024-03-01T10:00:00.000000",
            "updated_at": "2024-03-01T10:00:00.000000",
        }

    def test_get_hotels_success(self, service, sample_hotels):
        """Test successful hotel listing retrieval."""
        # Mock successful DynamoDB scan
        service.hotels_table.scan = Mock(return_value={"Items": sample_hotels})

        result = service.get_hotels()

        # Verify result structure
        assert "hotels" in result
        assert "total_count" in result
        assert "limit_applied" in result

        # Verify hotel data
        assert len(result["hotels"]) == 4
        assert result["total_count"] == 4
        assert result["limit_applied"] is False

        # Verify hotels are sorted by hotel_id
        hotel_ids = [hotel["hotel_id"] for hotel in result["hotels"]]
        assert hotel_ids == sorted(hotel_ids)

        # Verify DynamoDB scan was called correctly
        service.hotels_table.scan.assert_called_once_with()

    def test_get_hotels_with_limit(self, service, sample_hotels):
        """Test hotel listing with limit parameter."""
        # Mock successful DynamoDB scan with limit
        limited_hotels = sample_hotels[:2]
        service.hotels_table.scan = Mock(return_value={"Items": limited_hotels})

        result = service.get_hotels(limit=2)

        # Verify result
        assert len(result["hotels"]) == 2
        assert result["total_count"] == 2
        assert result["limit_applied"] is True

        # Verify DynamoDB scan was called with limit
        service.hotels_table.scan.assert_called_once_with(Limit=2)

    def test_get_hotels_empty_result(self, service):
        """Test hotel listing when no hotels exist."""
        # Mock DynamoDB returning empty result
        service.hotels_table.scan = Mock(return_value={"Items": []})

        result = service.get_hotels()

        # Verify empty result
        assert result["hotels"] == []
        assert result["total_count"] == 0
        assert result["limit_applied"] is False

    def test_get_hotels_dynamodb_error(self, service):
        """Test hotel listing when DynamoDB fails."""
        # Mock DynamoDB error
        service.hotels_table.scan = Mock(side_effect=Exception("DynamoDB error"))

        # Execute and verify exception
        with pytest.raises(
            Exception, match="Failed to retrieve hotels: DynamoDB error"
        ):
            service.get_hotels()

    def test_get_hotels_sorting(self, service):
        """Test that hotels are sorted by hotel_id."""
        # Create unsorted hotels list
        unsorted_hotels = [
            {"hotel_id": "H-TUL-001", "name": "Paraiso Tulum"},
            {"hotel_id": "H-CAB-003", "name": "Paraiso Los Cabos"},
            {"hotel_id": "H-PVR-002", "name": "Paraiso Vallarta"},
        ]

        service.hotels_table.scan = Mock(return_value={"Items": unsorted_hotels})

        result = service.get_hotels()

        # Verify hotels are sorted
        hotel_ids = [hotel["hotel_id"] for hotel in result["hotels"]]
        assert hotel_ids == ["H-CAB-003", "H-PVR-002", "H-TUL-001"]

    def test_create_housekeeping_request_success(
        self, service, sample_housekeeping_request_data
    ):
        """Test successful housekeeping request creation."""
        # Mock successful DynamoDB put_item
        service.requests_table.put_item = Mock()

        # Mock time.time() to get predictable request ID
        with patch("time.time", return_value=1234567890.123):
            with patch(
                "hotel_pms_simulation.services.hotel_service.datetime"
            ) as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2024-03-01T10:00:00.000000"
                )

                result = service.create_housekeeping_request(
                    **sample_housekeeping_request_data
                )

        # Verify result
        assert result["request_id"] == "REQ-1234567890123"
        assert result["hotel_id"] == "H-PVR-002"
        assert result["room_number"] == "101"
        assert result["request_type"] == "cleaning"
        assert result["description"] == "Extra towels needed"
        assert result["priority"] == "normal"
        assert result["status"] == "pending"
        assert result["guest_name"] == "John Doe"
        assert result["created_at"] == "2024-03-01T10:00:00.000000"

        # Verify DynamoDB put_item was called
        service.requests_table.put_item.assert_called_once()
        call_args = service.requests_table.put_item.call_args[1]
        assert call_args["Item"]["request_id"] == "REQ-1234567890123"
        assert call_args["Item"]["hotel_id"] == "H-PVR-002"
        assert call_args["Item"]["room_number"] == "101"

    def test_create_housekeeping_request_minimal_data(self, service):
        """Test housekeeping request creation with minimal required data."""
        # Mock successful DynamoDB put_item
        service.requests_table.put_item = Mock()

        # Mock time.time() to get predictable request ID
        with patch("time.time", return_value=1234567890.123):
            with patch(
                "hotel_pms_simulation.services.hotel_service.datetime"
            ) as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2024-03-01T10:00:00.000000"
                )

                result = service.create_housekeeping_request(
                    hotel_id="H-PVR-002",
                    room_number="202",
                    request_type="maintenance",
                )

        # Verify result with defaults
        assert result["request_id"] == "REQ-1234567890123"
        assert result["hotel_id"] == "H-PVR-002"
        assert result["room_number"] == "202"
        assert result["request_type"] == "maintenance"
        assert result["description"] == ""  # Default empty string
        assert result["priority"] == "normal"  # Default priority
        assert result["status"] == "pending"
        assert result["guest_name"] is None  # Not provided

        # Verify DynamoDB put_item was called with correct defaults
        call_args = service.requests_table.put_item.call_args[1]
        assert call_args["Item"]["description"] == ""
        assert call_args["Item"]["priority"] == "normal"
        assert "guest_name" not in call_args["Item"]  # Should not be included if None

    def test_create_housekeeping_request_different_types(self, service):
        """Test housekeeping request creation with different request types."""
        service.requests_table.put_item = Mock()

        request_types = ["cleaning", "maintenance", "amenities", "laundry", "other"]

        for i, request_type in enumerate(request_types):
            with patch("time.time", return_value=1234567890.123 + i):
                with patch(
                    "hotel_pms_simulation.services.hotel_service.datetime"
                ) as mock_datetime:
                    mock_datetime.now.return_value.isoformat.return_value = (
                        f"2024-03-01T10:0{i}:00.000000"
                    )

                    result = service.create_housekeeping_request(
                        hotel_id="H-PVR-002",
                        room_number="101",
                        request_type=request_type,
                    )

                    assert result["request_type"] == request_type
                    assert (
                        result["request_id"]
                        == f"REQ-{int((1234567890.123 + i) * 1000)}"
                    )

    def test_create_housekeeping_request_different_priorities(self, service):
        """Test housekeeping request creation with different priority levels."""
        service.requests_table.put_item = Mock()

        priorities = ["low", "normal", "high", "urgent"]

        for priority in priorities:
            with patch("time.time", return_value=1234567890.123):
                with patch(
                    "hotel_pms_simulation.services.hotel_service.datetime"
                ) as mock_datetime:
                    mock_datetime.now.return_value.isoformat.return_value = (
                        "2024-03-01T10:00:00.000000"
                    )

                    result = service.create_housekeeping_request(
                        hotel_id="H-PVR-002",
                        room_number="101",
                        request_type="cleaning",
                        priority=priority,
                    )

                    assert result["priority"] == priority

    def test_create_housekeeping_request_dynamodb_error(self, service):
        """Test housekeeping request creation when DynamoDB fails."""
        # Mock DynamoDB error
        service.requests_table.put_item = Mock(side_effect=Exception("DynamoDB error"))

        # Execute and verify exception
        with pytest.raises(
            Exception, match="Failed to create housekeeping request: DynamoDB error"
        ):
            service.create_housekeeping_request(
                hotel_id="H-PVR-002",
                room_number="101",
                request_type="cleaning",
            )

    def test_get_housekeeping_request_success(
        self, service, sample_housekeeping_request_record
    ):
        """Test successful housekeeping request retrieval."""
        # Mock successful DynamoDB get_item
        service.requests_table.get_item = Mock(
            return_value={"Item": sample_housekeeping_request_record}
        )

        result = service.get_housekeeping_request("REQ-1234567890123")

        # Verify result
        assert result == sample_housekeeping_request_record

        # Verify DynamoDB get_item was called correctly
        service.requests_table.get_item.assert_called_once_with(
            Key={"request_id": "REQ-1234567890123"}
        )

    def test_get_housekeeping_request_not_found(self, service):
        """Test housekeeping request retrieval when request doesn't exist."""
        # Mock DynamoDB returning no item
        service.requests_table.get_item = Mock(return_value={})

        result = service.get_housekeeping_request("NONEXISTENT-ID")

        # Verify None is returned
        assert result is None

    def test_get_housekeeping_request_dynamodb_error(self, service):
        """Test housekeeping request retrieval when DynamoDB fails."""
        # Mock DynamoDB error
        service.requests_table.get_item = Mock(side_effect=Exception("DynamoDB error"))

        # Execute and verify exception
        with pytest.raises(
            Exception, match="Failed to retrieve housekeeping request: DynamoDB error"
        ):
            service.get_housekeeping_request("REQ-1234567890123")

    def test_get_housekeeping_requests_by_hotel_success(
        self, service, sample_housekeeping_request_record
    ):
        """Test successful retrieval of housekeeping requests by hotel."""
        # Create multiple requests for testing sorting
        requests = [
            {
                **sample_housekeeping_request_record,
                "request_id": "REQ-1234567890123",
                "created_at": "2024-03-01T10:00:00.000000",
            },
            {
                **sample_housekeeping_request_record,
                "request_id": "REQ-1234567890124",
                "created_at": "2024-03-01T11:00:00.000000",
            },
        ]

        # Mock successful DynamoDB scan
        service.requests_table.scan = Mock(return_value={"Items": requests})

        result = service.get_housekeeping_requests_by_hotel("H-PVR-002")

        # Verify result (should be sorted by created_at descending)
        assert len(result) == 2
        assert result[0]["request_id"] == "REQ-1234567890124"  # More recent first
        assert result[1]["request_id"] == "REQ-1234567890123"

        # Verify DynamoDB scan was called correctly
        service.requests_table.scan.assert_called_once_with(
            FilterExpression="hotel_id = :hotel_id",
            ExpressionAttributeValues={":hotel_id": "H-PVR-002"},
        )

    def test_get_housekeeping_requests_by_hotel_with_limit(
        self, service, sample_housekeeping_request_record
    ):
        """Test retrieval of housekeeping requests by hotel with limit."""
        # Mock successful DynamoDB scan
        service.requests_table.scan = Mock(
            return_value={"Items": [sample_housekeeping_request_record]}
        )

        result = service.get_housekeeping_requests_by_hotel("H-PVR-002", limit=5)

        # Verify result
        assert len(result) == 1

        # Verify DynamoDB scan was called with limit
        service.requests_table.scan.assert_called_once_with(
            FilterExpression="hotel_id = :hotel_id",
            ExpressionAttributeValues={":hotel_id": "H-PVR-002"},
            Limit=5,
        )

    def test_get_housekeeping_requests_by_hotel_empty_result(self, service):
        """Test retrieval of housekeeping requests by hotel when no requests exist."""
        # Mock DynamoDB returning empty result
        service.requests_table.scan = Mock(return_value={"Items": []})

        result = service.get_housekeeping_requests_by_hotel("H-EMPTY-001")

        # Verify empty list is returned
        assert result == []

    def test_get_housekeeping_requests_by_hotel_dynamodb_error(self, service):
        """Test retrieval of housekeeping requests by hotel when DynamoDB fails."""
        # Mock DynamoDB error
        service.requests_table.scan = Mock(side_effect=Exception("DynamoDB error"))

        # Execute and verify exception
        with pytest.raises(
            Exception,
            match="Failed to retrieve housekeeping requests by hotel: DynamoDB error",
        ):
            service.get_housekeeping_requests_by_hotel("H-PVR-002")

    def test_request_id_generation_uniqueness(self, service):
        """Test that request IDs are unique across multiple requests."""
        # Mock successful DynamoDB put_item
        service.requests_table.put_item = Mock()

        # Create multiple requests with different timestamps
        request_ids = []

        for i in range(3):
            with patch("time.time", return_value=1234567890.123 + i):
                with patch(
                    "hotel_pms_simulation.services.hotel_service.datetime"
                ) as mock_datetime:
                    mock_datetime.now.return_value.isoformat.return_value = (
                        f"2024-03-01T10:0{i}:00.000000"
                    )

                    result = service.create_housekeeping_request(
                        hotel_id="H-PVR-002",
                        room_number="101",
                        request_type="cleaning",
                    )
                    request_ids.append(result["request_id"])

        # Verify all request IDs are unique
        assert len(set(request_ids)) == 3
        assert request_ids[0] == "REQ-1234567890123"
        assert request_ids[1] == "REQ-1234567891123"
        assert request_ids[2] == "REQ-1234567892123"


class TestHotelServiceIntegration:
    """Integration test scenarios for HotelService."""

    @pytest.fixture
    def service(self):
        """Create service instance with mocked DynamoDB."""
        with patch("boto3.resource") as mock_boto3:
            mock_dynamodb = MagicMock()
            mock_boto3.return_value = mock_dynamodb

            # Mock table instances
            mock_hotels_table = MagicMock()
            mock_requests_table = MagicMock()

            mock_dynamodb.Table.side_effect = lambda table_name: {
                "hotel-hotels": mock_hotels_table,
                "hotel-requests": mock_requests_table,
            }.get(table_name)

            service = HotelService()
            service.hotels_table = mock_hotels_table
            service.requests_table = mock_requests_table

            return service

    def test_complete_housekeeping_request_lifecycle(self, service):
        """Test complete housekeeping request lifecycle from creation to retrieval."""
        # Step 1: Create housekeeping request
        service.requests_table.put_item = Mock()

        with patch("time.time", return_value=1234567890.123):
            with patch(
                "hotel_pms_simulation.services.hotel_service.datetime"
            ) as mock_datetime:
                mock_datetime.now.return_value.isoformat.return_value = (
                    "2024-03-01T10:00:00.000000"
                )

                created_request = service.create_housekeeping_request(
                    hotel_id="H-PVR-002",
                    room_number="305",
                    request_type="maintenance",
                    description="Air conditioning not working",
                    priority="high",
                    guest_name="Alice Johnson",
                )

        assert created_request["request_id"] == "REQ-1234567890123"
        assert created_request["status"] == "pending"
        assert created_request["priority"] == "high"

        # Step 2: Retrieve individual request
        service.requests_table.get_item = Mock(return_value={"Item": created_request})

        retrieved_request = service.get_housekeeping_request("REQ-1234567890123")
        assert retrieved_request["room_number"] == "305"
        assert retrieved_request["request_type"] == "maintenance"

        # Step 3: Retrieve requests by hotel
        service.requests_table.scan = Mock(return_value={"Items": [created_request]})

        hotel_requests = service.get_housekeeping_requests_by_hotel("H-PVR-002")
        assert len(hotel_requests) == 1
        assert hotel_requests[0]["request_id"] == "REQ-1234567890123"

    def test_hotel_listing_and_request_creation_workflow(self, service):
        """Test workflow of listing hotels and creating requests for specific hotels."""
        # Step 1: List available hotels
        sample_hotels = [
            {"hotel_id": "H-PVR-002", "name": "Paraiso Vallarta"},
            {"hotel_id": "H-TUL-001", "name": "Paraiso Tulum"},
        ]

        service.hotels_table.scan = Mock(return_value={"Items": sample_hotels})

        hotels_result = service.get_hotels()
        assert len(hotels_result["hotels"]) == 2

        # Step 2: Create requests for each hotel
        service.requests_table.put_item = Mock()

        created_requests = []
        for i, hotel in enumerate(hotels_result["hotels"]):
            with patch("time.time", return_value=1234567890.123 + i):
                with patch(
                    "hotel_pms_simulation.services.hotel_service.datetime"
                ) as mock_datetime:
                    mock_datetime.now.return_value.isoformat.return_value = (
                        f"2024-03-01T10:0{i}:00.000000"
                    )

                    request = service.create_housekeeping_request(
                        hotel_id=hotel["hotel_id"],
                        room_number=f"10{i + 1}",
                        request_type="cleaning",
                    )
                    created_requests.append(request)

        # Verify requests were created for each hotel
        assert len(created_requests) == 2
        assert created_requests[0]["hotel_id"] == "H-PVR-002"
        assert created_requests[1]["hotel_id"] == "H-TUL-001"
        assert created_requests[0]["room_number"] == "101"
        assert created_requests[1]["room_number"] == "102"
