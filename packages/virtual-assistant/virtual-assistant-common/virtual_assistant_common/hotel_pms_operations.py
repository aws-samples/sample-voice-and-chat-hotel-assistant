# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Hotel PMS operations using MCP ClientSession.

This module provides high-level operations for interacting with the Hotel PMS
MCP server using an existing ClientSession. These functions are designed to be
used within an existing MCP client context.
"""

import json
import logging
from typing import Any

from mcp.client.session import ClientSession

logger = logging.getLogger(__name__)


async def get_hotels(session: ClientSession) -> list[dict[str, Any]]:
    """
    Get a list of hotels using an existing MCP ClientSession.

    This function calls the HotelPMS___get_hotels tool and returns the parsed hotel data.
    It should be used within an existing MCP client session context.

    Args:
        session: An initialized MCP ClientSession

    Returns:
        List of hotel dictionaries containing hotel information

    Raises:
        ValueError: If the get_hotels tool is not available or returns invalid data
        Exception: If the MCP tool call fails

    Example:
        ```python
        from virtual_assistant_common import hotel_pms_mcp_client
        from virtual_assistant_common.hotel_pms_operations import get_hotels
        from mcp.client.session import ClientSession

        async with hotel_pms_mcp_client() as (read_stream, write_stream, get_session_id):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                # Get hotels using the existing session
                hotels = await get_hotels(session)
                for hotel in hotels:
                    print(f"Hotel: {hotel['name']} - {hotel['location']}")
        ```
    """
    logger.info("Getting hotels from Hotel PMS MCP server using existing session")

    # Call the tool using the helper function
    hotels_data = await _call_hotel_pms_tool(session, "HotelPMS___get_hotels", {})

    # Handle different response formats
    if isinstance(hotels_data, list):
        logger.info(f"Successfully retrieved {len(hotels_data)} hotels")
        return hotels_data
    elif isinstance(hotels_data, dict):
        # Check if it's wrapped in a response object
        if "hotels" in hotels_data:
            hotels_list = hotels_data["hotels"]
            if isinstance(hotels_list, list):
                logger.info(f"Successfully retrieved {len(hotels_list)} hotels from wrapped response")
                return hotels_list
        elif "data" in hotels_data:
            hotels_list = hotels_data["data"]
            if isinstance(hotels_list, list):
                logger.info(f"Successfully retrieved {len(hotels_list)} hotels from data field")
                return hotels_list

        # If it's a single hotel object, wrap it in a list
        logger.info("Received single hotel object, wrapping in list")
        return [hotels_data]
    else:
        logger.error(f"Unexpected data type: {type(hotels_data)}, data: {hotels_data}")
        raise ValueError(f"get_hotels tool returned unexpected data type: {type(hotels_data)}")


async def get_hotel_by_id(session: ClientSession, hotel_id: str) -> dict[str, Any] | None:
    """
    Get a specific hotel by ID using an existing MCP ClientSession.

    Args:
        session: An initialized MCP ClientSession
        hotel_id: The ID of the hotel to retrieve

    Returns:
        Hotel dictionary if found, None otherwise

    Raises:
        ValueError: If the operation fails or returns invalid data
        Exception: If the MCP tool call fails

    Example:
        ```python
        hotel = await get_hotel_by_id(session, "hotel-123")
        if hotel:
            print(f"Found hotel: {hotel['name']}")
        ```
    """
    logger.info(f"Getting hotel by ID: {hotel_id}")

    # Get all hotels and filter by ID
    # Note: This could be optimized if there's a specific get_hotel_by_id tool
    hotels = await get_hotels(session)

    for hotel in hotels:
        if hotel.get("hotel_id") == hotel_id or hotel.get("id") == hotel_id:
            logger.info(f"Found hotel with ID {hotel_id}: {hotel.get('name', 'Unknown')}")
            return hotel

    logger.warning(f"Hotel with ID {hotel_id} not found")
    return None


async def check_availability(
    session: ClientSession, hotel_id: str, check_in_date: str, check_out_date: str, guests: int = 1
) -> dict[str, Any]:
    """
    Check room availability for a hotel using an existing MCP ClientSession.

    Args:
        session: An initialized MCP ClientSession
        hotel_id: The ID of the hotel
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        guests: Number of guests (default: 1)

    Returns:
        Availability information dictionary

    Raises:
        ValueError: If the check_availability tool is not available or returns invalid data
        Exception: If the MCP tool call fails

    Example:
        ```python
        availability = await check_availability(
            session,
            "hotel-123",
            "2024-03-15",
            "2024-03-17",
            guests=2
        )
        print(f"Available rooms: {len(availability.get('available_rooms', []))}")
        ```
    """
    logger.info(f"Checking availability for hotel {hotel_id} from {check_in_date} to {check_out_date}")

    # Use the helper function to call the tool
    return await _call_hotel_pms_tool(
        session,
        "HotelPMS___check_availability",
        {
            "hotel_id": hotel_id,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "guests": guests,
        },
    )


async def get_room_types(session: ClientSession, hotel_id: str | None = None) -> list[dict[str, Any]]:
    """
    Get room types for a hotel or all hotels using an existing MCP ClientSession.

    Args:
        session: An initialized MCP ClientSession
        hotel_id: Optional hotel ID to filter room types (if None, returns all room types)

    Returns:
        List of room type dictionaries

    Raises:
        ValueError: If the get_room_types tool is not available or returns invalid data
        Exception: If the MCP tool call fails

    Example:
        ```python
        # Get all room types
        room_types = await get_room_types(session)

        # Get room types for a specific hotel
        room_types = await get_room_types(session, "hotel-123")
        ```
    """
    logger.info(f"Getting room types for hotel: {hotel_id or 'all hotels'}")

    arguments = {}
    if hotel_id:
        arguments["hotel_id"] = hotel_id

    return await _call_hotel_pms_tool(session, "HotelPMS___get_room_types", arguments)


async def get_reservations(
    session: ClientSession,
    hotel_id: str | None = None,
    guest_email: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Get reservations using an existing MCP ClientSession.

    Args:
        session: An initialized MCP ClientSession
        hotel_id: Optional hotel ID to filter reservations
        guest_email: Optional guest email to filter reservations
        status: Optional reservation status to filter by
        limit: Maximum number of reservations to return (default: 50)

    Returns:
        List of reservation dictionaries

    Raises:
        ValueError: If the get_reservations tool is not available or returns invalid data
        Exception: If the MCP tool call fails

    Example:
        ```python
        # Get all reservations
        reservations = await get_reservations(session)

        # Get reservations for a specific hotel
        reservations = await get_reservations(session, hotel_id="hotel-123")

        # Get reservations for a specific guest
        reservations = await get_reservations(session, guest_email="guest@example.com")
        ```
    """
    logger.info(f"Getting reservations with filters: hotel_id={hotel_id}, guest_email={guest_email}, status={status}")

    arguments = {"limit": limit}
    if hotel_id:
        arguments["hotel_id"] = hotel_id
    if guest_email:
        arguments["guest_email"] = guest_email
    if status:
        arguments["status"] = status

    return await _call_hotel_pms_tool(session, "HotelPMS___get_reservations", arguments)


async def create_reservation(
    session: ClientSession,
    hotel_id: str,
    guest_email: str,
    guest_name: str,
    room_type: str,
    check_in_date: str,
    check_out_date: str,
    guests: int = 1,
    special_requests: str | None = None,
) -> dict[str, Any]:
    """
    Create a new reservation using an existing MCP ClientSession.

    Args:
        session: An initialized MCP ClientSession
        hotel_id: The ID of the hotel
        guest_email: Guest's email address
        guest_name: Guest's full name
        room_type: Type of room to reserve
        check_in_date: Check-in date in YYYY-MM-DD format
        check_out_date: Check-out date in YYYY-MM-DD format
        guests: Number of guests (default: 1)
        special_requests: Optional special requests

    Returns:
        Created reservation dictionary

    Raises:
        ValueError: If the create_reservation tool is not available or returns invalid data
        Exception: If the MCP tool call fails

    Example:
        ```python
        reservation = await create_reservation(
            session,
            hotel_id="hotel-123",
            guest_email="guest@example.com",
            guest_name="John Doe",
            room_type="Standard",
            check_in_date="2024-03-15",
            check_out_date="2024-03-17",
            guests=2,
            special_requests="Late check-in"
        )
        print(f"Created reservation: {reservation['reservation_id']}")
        ```
    """
    logger.info(f"Creating reservation for {guest_name} at hotel {hotel_id}")

    arguments = {
        "hotel_id": hotel_id,
        "guest_email": guest_email,
        "guest_name": guest_name,
        "room_type": room_type,
        "check_in_date": check_in_date,
        "check_out_date": check_out_date,
        "guests": guests,
    }

    if special_requests:
        arguments["special_requests"] = special_requests

    return await _call_hotel_pms_tool(session, "HotelPMS___create_reservation", arguments)


# Helper function to reduce code duplication
async def _call_hotel_pms_tool(session: ClientSession, tool_name: str, arguments: dict[str, Any]) -> Any:
    """
    Helper function to call a Hotel PMS MCP tool and parse the response.

    Args:
        session: An initialized MCP ClientSession
        tool_name: Name of the tool to call
        arguments: Arguments to pass to the tool

    Returns:
        Parsed response data

    Raises:
        ValueError: If the tool is not available or returns invalid data
        Exception: If the MCP tool call fails
    """
    logger.debug(f"Calling tool {tool_name} with arguments: {arguments}")

    # List available tools to verify the tool is available
    tools_response = await session.list_tools()
    tools = tools_response.tools

    # Find the requested tool
    target_tool = None
    for tool in tools:
        if tool.name == tool_name:
            target_tool = tool
            break

    if not target_tool:
        available_tools = [tool.name for tool in tools]
        raise ValueError(f"{tool_name} tool not found. Available tools: {available_tools}")

    # Call the tool
    call_result = await session.call_tool(name=tool_name, arguments=arguments)

    if not call_result.content:
        raise ValueError(f"{tool_name} tool returned no content")

    # Parse the response content
    content = call_result.content
    if not isinstance(content, list) or len(content) == 0:
        raise ValueError(f"{tool_name} tool returned invalid content format")

    # Extract text content from the first content item
    text_content = content[0].text if hasattr(content[0], "text") else str(content[0])

    if not text_content:
        raise ValueError(f"{tool_name} tool returned empty text content")

    try:
        # Parse JSON response
        response_data = json.loads(text_content)
        logger.debug(f"Successfully called {tool_name}")
        return response_data

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {tool_name} JSON response: {e}")
        logger.error(f"Raw response content: {text_content}")
        raise ValueError(f"{tool_name} tool returned invalid JSON: {e}") from e
