# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for hotel_pms_operations module."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from virtual_assistant_common.hotel_pms_operations import (
    check_availability,
    create_reservation,
    get_hotel_by_id,
    get_hotels,
    get_reservations,
    get_room_types,
)


class TestHotelPmsOperations:
    """Test cases for hotel PMS operations."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock ClientSession."""
        session = AsyncMock()
        return session

    @pytest.fixture
    def sample_hotels_data(self):
        """Sample hotel data for testing."""
        return [
            {
                "hotel_id": "1",
                "name": "Grand Hotel",
                "location": "New York, NY",
                "timezone": "America/New_York",
            },
            {
                "hotel_id": "2",
                "name": "Beach Resort",
                "location": "Miami, FL",
                "timezone": "America/New_York",
            },
        ]

    @pytest.mark.asyncio
    async def test_get_hotels_success(self, mock_session, sample_hotels_data):
        """Test successful hotel retrieval."""
        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___get_hotels"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(sample_hotels_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function
        result = await get_hotels(mock_session)

        # Verify the result
        assert result == sample_hotels_data
        mock_session.list_tools.assert_called_once()
        mock_session.call_tool.assert_called_once_with(name="HotelPMS___get_hotels", arguments={})

    @pytest.mark.asyncio
    async def test_get_hotels_tool_not_found(self, mock_session):
        """Test error when get_hotels tool is not available."""
        # Mock tools response with no get_hotels tool
        mock_tools_response = MagicMock()
        mock_other_tool = MagicMock()
        mock_other_tool.name = "SomeOtherTool"
        mock_tools_response.tools = [mock_other_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Call the function and expect ValueError
        with pytest.raises(ValueError, match="HotelPMS___get_hotels tool not found"):
            await get_hotels(mock_session)

    @pytest.mark.asyncio
    async def test_get_hotels_wrapped_response(self, mock_session):
        """Test handling of wrapped response format."""
        sample_data = [{"hotel_id": "1", "name": "Test Hotel"}]
        wrapped_response = {"hotels": sample_data}

        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___get_hotels"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response with wrapped data
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(wrapped_response)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function
        result = await get_hotels(mock_session)

        # Verify the result
        assert result == sample_data

    @pytest.mark.asyncio
    async def test_get_hotel_by_id_found(self, mock_session, sample_hotels_data):
        """Test successful hotel retrieval by ID."""
        # Mock the get_hotels call
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___get_hotels"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(sample_hotels_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function
        result = await get_hotel_by_id(mock_session, "1")

        # Verify the result
        assert result == sample_hotels_data[0]
        assert result["hotel_id"] == "1"
        assert result["name"] == "Grand Hotel"

    @pytest.mark.asyncio
    async def test_get_hotel_by_id_not_found(self, mock_session, sample_hotels_data):
        """Test hotel retrieval by ID when hotel is not found."""
        # Mock the get_hotels call
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___get_hotels"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(sample_hotels_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function with non-existent ID
        result = await get_hotel_by_id(mock_session, "999")

        # Verify the result
        assert result is None

    @pytest.mark.asyncio
    async def test_check_availability_success(self, mock_session):
        """Test successful availability check."""
        availability_data = {
            "hotel_id": "1",
            "available_rooms": [
                {"room_type": "Standard", "available": 5, "price": 150.00},
                {"room_type": "Deluxe", "available": 2, "price": 250.00},
            ],
        }

        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___check_availability"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(availability_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function
        result = await check_availability(mock_session, "1", "2024-03-15", "2024-03-17", guests=2)

        # Verify the result
        assert result == availability_data
        mock_session.call_tool.assert_called_once_with(
            name="HotelPMS___check_availability",
            arguments={
                "hotel_id": "1",
                "check_in_date": "2024-03-15",
                "check_out_date": "2024-03-17",
                "guests": 2,
            },
        )

    @pytest.mark.asyncio
    async def test_check_availability_tool_not_found(self, mock_session):
        """Test error when check_availability tool is not available."""
        # Mock tools response with no check_availability tool
        mock_tools_response = MagicMock()
        mock_other_tool = MagicMock()
        mock_other_tool.name = "SomeOtherTool"
        mock_tools_response.tools = [mock_other_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Call the function and expect ValueError
        with pytest.raises(ValueError, match="HotelPMS___check_availability tool not found"):
            await check_availability(mock_session, "1", "2024-03-15", "2024-03-17")

    @pytest.mark.asyncio
    async def test_get_room_types_success(self, mock_session):
        """Test successful room types retrieval."""
        room_types_data = [
            {"room_type_id": "1", "name": "Standard", "capacity": 2, "base_price": 150.00},
            {"room_type_id": "2", "name": "Deluxe", "capacity": 4, "base_price": 250.00},
        ]

        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___get_room_types"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(room_types_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function
        result = await get_room_types(mock_session, "hotel-123")

        # Verify the result
        assert result == room_types_data
        mock_session.call_tool.assert_called_once_with(
            name="HotelPMS___get_room_types", arguments={"hotel_id": "hotel-123"}
        )

    @pytest.mark.asyncio
    async def test_get_room_types_all_hotels(self, mock_session):
        """Test room types retrieval for all hotels."""
        room_types_data = [{"room_type_id": "1", "name": "Standard"}]

        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___get_room_types"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(room_types_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function without hotel_id
        result = await get_room_types(mock_session)

        # Verify the result
        assert result == room_types_data
        mock_session.call_tool.assert_called_once_with(name="HotelPMS___get_room_types", arguments={})

    @pytest.mark.asyncio
    async def test_get_reservations_success(self, mock_session):
        """Test successful reservations retrieval."""
        reservations_data = [
            {
                "reservation_id": "res-123",
                "hotel_id": "hotel-1",
                "guest_email": "guest@example.com",
                "status": "confirmed",
            }
        ]

        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___get_reservations"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(reservations_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function
        result = await get_reservations(mock_session, hotel_id="hotel-1", guest_email="guest@example.com")

        # Verify the result
        assert result == reservations_data
        mock_session.call_tool.assert_called_once_with(
            name="HotelPMS___get_reservations",
            arguments={"limit": 50, "hotel_id": "hotel-1", "guest_email": "guest@example.com"},
        )

    @pytest.mark.asyncio
    async def test_create_reservation_success(self, mock_session):
        """Test successful reservation creation."""
        reservation_data = {
            "reservation_id": "res-456",
            "hotel_id": "hotel-1",
            "guest_email": "newguest@example.com",
            "status": "confirmed",
        }

        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___create_reservation"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(reservation_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function
        result = await create_reservation(
            mock_session,
            hotel_id="hotel-1",
            guest_email="newguest@example.com",
            guest_name="Jane Doe",
            room_type="Deluxe",
            check_in_date="2024-04-01",
            check_out_date="2024-04-03",
            guests=2,
            special_requests="Ocean view",
        )

        # Verify the result
        assert result == reservation_data
        mock_session.call_tool.assert_called_once_with(
            name="HotelPMS___create_reservation",
            arguments={
                "hotel_id": "hotel-1",
                "guest_email": "newguest@example.com",
                "guest_name": "Jane Doe",
                "room_type": "Deluxe",
                "check_in_date": "2024-04-01",
                "check_out_date": "2024-04-03",
                "guests": 2,
                "special_requests": "Ocean view",
            },
        )

    @pytest.mark.asyncio
    async def test_create_reservation_without_special_requests(self, mock_session):
        """Test reservation creation without special requests."""
        reservation_data = {"reservation_id": "res-789", "status": "confirmed"}

        # Mock tools response
        mock_tools_response = MagicMock()
        mock_tool = MagicMock()
        mock_tool.name = "HotelPMS___create_reservation"
        mock_tools_response.tools = [mock_tool]
        mock_session.list_tools.return_value = mock_tools_response

        # Mock tool call response
        mock_call_result = MagicMock()
        mock_content_item = MagicMock()
        mock_content_item.text = json.dumps(reservation_data)
        mock_call_result.content = [mock_content_item]
        mock_session.call_tool.return_value = mock_call_result

        # Call the function without special requests
        result = await create_reservation(
            mock_session,
            hotel_id="hotel-2",
            guest_email="guest2@example.com",
            guest_name="John Smith",
            room_type="Standard",
            check_in_date="2024-05-01",
            check_out_date="2024-05-03",
        )

        # Verify the result
        assert result == reservation_data
        mock_session.call_tool.assert_called_once_with(
            name="HotelPMS___create_reservation",
            arguments={
                "hotel_id": "hotel-2",
                "guest_email": "guest2@example.com",
                "guest_name": "John Smith",
                "room_type": "Standard",
                "check_in_date": "2024-05-01",
                "check_out_date": "2024-05-03",
                "guests": 1,
            },
        )
