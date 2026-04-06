# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""availability and pricing service for hotel room management with blackout date rules."""

import os
import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger

logger = Logger()


class AvailabilityService:
    """service for handling room availability and pricing calculations with blackout date rules."""

    def __init__(self):
        """Initialize the service with DynamoDB connections."""
        self.dynamodb = boto3.resource("dynamodb")

        # Get table names from environment variables
        self.hotels_table_name = os.environ.get("HOTELS_TABLE_NAME", "hotel-hotels")
        self.room_types_table_name = os.environ.get(
            "ROOM_TYPES_TABLE_NAME", "hotel-room-types"
        )
        self.quotes_table_name = os.environ.get("QUOTES_TABLE_NAME", "hotel-quotes")

        # Initialize table references
        self.hotels_table = self.dynamodb.Table(self.hotels_table_name)
        self.room_types_table = self.dynamodb.Table(self.room_types_table_name)
        self.quotes_table = self.dynamodb.Table(self.quotes_table_name)

    def check_availability(
        self, hotel_id: str, check_in_date: str, check_out_date: str, guests: int
    ) -> dict[str, Any]:
        """
        Check room availability for the specified criteria with blackout date rules.

        Args:
            hotel_id: Hotel identifier
            check_in_date: Check-in date in YYYY-MM-DD format
            check_out_date: Check-out date in YYYY-MM-DD format
            guests: Number of guests

        Returns:
            Dictionary with availability status and room counts
        """
        logger.info(
            "Checking availability with blackout date rules",
            extra={
                "hotel_id": hotel_id,
                "check_in": check_in_date,
                "check_out": check_out_date,
                "guests": guests,
            },
        )

        # Parse dates (handle both str and date objects)
        try:
            if isinstance(check_in_date, date):
                check_in = check_in_date
            else:
                check_in = datetime.strptime(check_in_date, "%Y-%m-%d").date()

            if isinstance(check_out_date, date):
                check_out = check_out_date
            else:
                check_out = datetime.strptime(check_out_date, "%Y-%m-%d").date()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {
                "available": False,
                "message": "Invalid date format. Use YYYY-MM-DD format.",
            }

        # Check if any date in the range falls on blackout dates (5th-7th of each month)
        if self._has_blackout_dates(check_in, check_out):
            logger.info("Dates fall within blackout period (5th-7th of month)")
            return {
                "hotel_id": hotel_id,
                "available": False,
                "message": "Fully booked during selected dates",
            }

        # Get hotel information
        hotel = self._get_hotel(hotel_id)
        if not hotel:
            return {"available": False, "message": f"Hotel {hotel_id} not found"}

        # Get available room types for this hotel
        available_room_types = self._get_available_room_types(hotel_id, guests)

        return {
            "hotel_id": hotel_id,
            "available": True,
            "available_room_types": available_room_types,
        }

    def _has_blackout_dates(self, check_in: date, check_out: date) -> bool:
        """
        Check if any date in the range falls on blackout dates (5th-7th of each month).

        Args:
            check_in: Check-in date
            check_out: Check-out date

        Returns:
            True if any date in range is a blackout date
        """
        current_date = check_in
        while current_date < check_out:
            if current_date.day in [5, 6, 7]:
                return True
            current_date += timedelta(days=1)
        return False

    def _get_hotel(self, hotel_id: str) -> dict[str, Any] | None:
        """Get hotel information from DynamoDB."""
        try:
            response = self.hotels_table.get_item(Key={"hotel_id": hotel_id})
            return response.get("Item")
        except Exception as e:
            logger.error(f"Error getting hotel {hotel_id}: {e}")
            return None

    def _get_room_type(self, room_type_id: str) -> dict[str, Any] | None:
        """Get room type information from DynamoDB."""
        try:
            response = self.room_types_table.get_item(
                Key={"room_type_id": room_type_id}
            )
            return response.get("Item")
        except Exception as e:
            logger.error(f"Error getting room type {room_type_id}: {e}")
            return None

    def _get_available_room_types(
        self, hotel_id: str, guests: int
    ) -> list[dict[str, Any]]:
        """
        Get available room types for the hotel with simple availability counts.

        Args:
            hotel_id: Hotel identifier
            guests: Number of guests

        Returns:
            List of available room types with counts and base rates
        """
        try:
            # Scan room types table for this hotel
            response = self.room_types_table.scan(
                FilterExpression="hotel_id = :hotel_id",
                ExpressionAttributeValues={":hotel_id": hotel_id},
            )

            room_types = response.get("Items", [])
            available_room_types = []

            for room_type in room_types:
                # Check if room type can accommodate the guests
                max_occupancy = int(room_type.get("max_occupancy", 0))
                if max_occupancy >= guests:
                    # For simplified demo, use fixed availability counts
                    available_count = self._get_demo_availability_count(
                        room_type["room_type_id"]
                    )
                    base_rate = float(room_type.get("base_rate", 0))

                    available_room_types.append(
                        {
                            "room_type_id": room_type["room_type_id"],
                            "available_rooms": available_count,
                            "base_rate": base_rate,
                        }
                    )

            return available_room_types

        except Exception as e:
            logger.error(f"Error getting room types for hotel {hotel_id}: {e}")
            return []

    def _get_demo_availability_count(self, room_type_id: str) -> int:
        """
        Get demo availability count based on room type.
        For simplified demo, return fixed counts based on room type.
        """
        # Simple demo logic - different availability by room type
        if "STD" in room_type_id or "standard" in room_type_id.lower():
            return 5
        elif "SUP" in room_type_id or "superior" in room_type_id.lower():
            return 3
        elif "STE" in room_type_id or "suite" in room_type_id.lower():
            return 1
        else:
            return 2  # Default availability

    def generate_quote(
        self,
        hotel_id: str,
        room_type_id: str,
        check_in_date: str,
        check_out_date: str,
        guests: int,
    ) -> dict[str, Any]:
        """
        Generate and store a pricing quote in DynamoDB with TTL expiration.

        Args:
            hotel_id: Hotel identifier
            room_type_id: Room type identifier
            check_in_date: Check-in date in YYYY-MM-DD format
            check_out_date: Check-out date in YYYY-MM-DD format
            guests: Number of guests

        Returns:
            Dictionary with pricing breakdown, total cost, and quote_id
        """
        logger.info(
            "Generating quote with DynamoDB persistence",
            extra={
                "hotel_id": hotel_id,
                "room_type_id": room_type_id,
                "check_in": check_in_date,
                "check_out": check_out_date,
                "guests": guests,
            },
        )

        # Parse dates (handle both str and date objects)
        try:
            if isinstance(check_in_date, date):
                check_in = check_in_date
            else:
                check_in = datetime.strptime(check_in_date, "%Y-%m-%d").date()

            if isinstance(check_out_date, date):
                check_out = check_out_date
            else:
                check_out = datetime.strptime(check_out_date, "%Y-%m-%d").date()
        except ValueError as e:
            logger.error(f"Invalid date format: {e}")
            return {
                "error": True,
                "message": "Invalid date format. Use YYYY-MM-DD format.",
            }

        # Calculate number of nights
        nights = (check_out - check_in).days
        if nights <= 0:
            return {
                "error": True,
                "message": "Check-out date must be after check-in date",
            }

        # Get room type information
        room_type = self._get_room_type(room_type_id)
        if not room_type:
            return {"error": True, "message": f"Room type {room_type_id} not found"}

        # Verify room type belongs to the hotel
        if room_type.get("hotel_id") != hotel_id:
            return {
                "error": True,
                "message": "Room type does not belong to the specified hotel",
            }

        # Calculate basic pricing
        base_rate = float(room_type.get("base_rate", 0))

        # Apply guest count multiplier (simple logic: additional guests beyond 2 cost 25% more per guest)
        guest_multiplier = self._calculate_guest_multiplier(guests)

        # Calculate total cost
        total_cost = base_rate * nights * guest_multiplier

        # Generate unique quote ID
        quote_id = (
            f"Q-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        )

        # Set expiration time (6 hours from now)
        expires_at = datetime.now() + timedelta(hours=6)
        expires_at_timestamp = int(expires_at.timestamp())

        # Create quote data
        quote_data = {
            "hotel_id": hotel_id,
            "room_type_id": room_type_id,
            "nights": nights,
            "base_rate": base_rate,
            "guests": guests,
            "guest_multiplier": guest_multiplier,
            "total_cost": total_cost,
            "pricing_breakdown": {
                "base_rate_per_night": base_rate,
                "nights": nights,
                "guest_multiplier": guest_multiplier,
                "subtotal": base_rate * nights,
                "total_with_guest_adjustment": total_cost,
            },
        }

        # Store quote in DynamoDB (convert floats to Decimal for DynamoDB compatibility)
        quote_item = {
            "quote_id": quote_id,
            "hotel_id": hotel_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "guests": guests,
            "nights": nights,
            "base_rate": Decimal(str(base_rate)),
            "guest_multiplier": Decimal(str(guest_multiplier)),
            "total_cost": Decimal(str(total_cost)),
            "pricing_breakdown": {
                "base_rate_per_night": Decimal(
                    str(quote_data["pricing_breakdown"]["base_rate_per_night"])
                ),
                "nights": quote_data["pricing_breakdown"]["nights"],
                "guest_multiplier": Decimal(
                    str(quote_data["pricing_breakdown"]["guest_multiplier"])
                ),
                "subtotal": Decimal(str(quote_data["pricing_breakdown"]["subtotal"])),
                "total_with_guest_adjustment": Decimal(
                    str(quote_data["pricing_breakdown"]["total_with_guest_adjustment"])
                ),
            },
            "expires_at": expires_at_timestamp,  # TTL timestamp
            "created_at": datetime.now().isoformat(),
        }

        try:
            self.quotes_table.put_item(Item=quote_item)
            logger.info(
                "Quote stored successfully in DynamoDB",
                extra={
                    "quote_id": quote_id,
                    "hotel_id": hotel_id,
                    "expires_at": expires_at.isoformat(),
                },
            )
        except Exception as e:
            logger.error(f"Error storing quote in DynamoDB: {e}")
            return {
                "error": True,
                "message": "Failed to store quote. Please try again.",
            }

        # Return quote with quote_id for reservation creation
        return {
            "quote_id": quote_id,
            "expires_at": expires_at.isoformat(),
            **quote_data,
        }

    def get_quote(self, quote_id: str) -> dict[str, Any] | None:
        """
        Retrieve a quote by ID (used during reservation creation).

        Args:
            quote_id: Unique quote identifier

        Returns:
            Quote data if found and not expired, None otherwise
        """
        try:
            response = self.quotes_table.get_item(Key={"quote_id": quote_id})
            quote_item = response.get("Item")

            if not quote_item:
                logger.info(f"Quote {quote_id} not found")
                return None

            # Check if quote has expired (DynamoDB TTL may not have cleaned it up yet)
            expires_at_timestamp = quote_item.get("expires_at")
            if (
                expires_at_timestamp
                and datetime.now().timestamp() > expires_at_timestamp
            ):
                logger.info(f"Quote {quote_id} has expired")
                return None

            # Convert Decimal values back to float for API consistency
            if quote_item.get("base_rate") is not None:
                quote_item["base_rate"] = float(quote_item["base_rate"])
            if quote_item.get("guest_multiplier") is not None:
                quote_item["guest_multiplier"] = float(quote_item["guest_multiplier"])
            if quote_item.get("total_cost") is not None:
                quote_item["total_cost"] = float(quote_item["total_cost"])

            # Convert pricing breakdown Decimal values
            if "pricing_breakdown" in quote_item:
                breakdown = quote_item["pricing_breakdown"]
                if breakdown.get("base_rate_per_night") is not None:
                    breakdown["base_rate_per_night"] = float(
                        breakdown["base_rate_per_night"]
                    )
                if breakdown.get("guest_multiplier") is not None:
                    breakdown["guest_multiplier"] = float(breakdown["guest_multiplier"])
                if breakdown.get("subtotal") is not None:
                    breakdown["subtotal"] = float(breakdown["subtotal"])
                if breakdown.get("total_with_guest_adjustment") is not None:
                    breakdown["total_with_guest_adjustment"] = float(
                        breakdown["total_with_guest_adjustment"]
                    )

            logger.info(
                "Quote retrieved successfully",
                extra={
                    "quote_id": quote_id,
                    "hotel_id": quote_item.get("hotel_id"),
                    "total_cost": quote_item.get("total_cost"),
                },
            )
            return quote_item

        except Exception as e:
            logger.error(f"Error retrieving quote {quote_id}: {e}")
            return None

    def _calculate_guest_multiplier(self, guests: int) -> float:
        """
        Calculate guest count multiplier for pricing.

        Args:
            guests: Number of guests

        Returns:
            Multiplier to apply to base rate
        """
        # Simple pricing logic: base rate for up to 2 guests, 25% more per additional guest
        if guests <= 2:
            return 1.0
        else:
            additional_guests = guests - 2
            return 1.0 + (additional_guests * 0.25)
