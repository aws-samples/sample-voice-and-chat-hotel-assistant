# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""reservation management service for hotel bookings."""

import os
import time
from datetime import datetime
from decimal import Decimal
from typing import Any

import boto3
from aws_lambda_powertools import Logger

logger = Logger()


class ReservationService:
    """service for managing hotel reservations using DynamoDB directly."""

    def __init__(self):
        """Initialize the service with DynamoDB resources."""
        self.dynamodb = boto3.resource("dynamodb")

        # Get table names from environment variables
        self.reservations_table_name = os.environ.get(
            "RESERVATIONS_TABLE_NAME", "hotel-reservations"
        )
        self.hotels_table_name = os.environ.get("HOTELS_TABLE_NAME", "hotel-hotels")
        self.room_types_table_name = os.environ.get(
            "ROOM_TYPES_TABLE_NAME", "hotel-room-types"
        )

        # Initialize table references
        self.reservations_table = self.dynamodb.Table(self.reservations_table_name)
        self.hotels_table = self.dynamodb.Table(self.hotels_table_name)
        self.room_types_table = self.dynamodb.Table(self.room_types_table_name)

    def create_reservation(
        self,
        hotel_id: str,
        room_type_id: str,
        guest_name: str,
        guest_email: str,
        guest_phone: str,
        check_in_date: str,
        check_out_date: str,
        guests: int,
        package_type: str = "simple",
    ) -> dict[str, Any]:
        """
        Create a new reservation with timestamp-based confirmation ID.

        Args:
            hotel_id: Hotel identifier
            room_type_id: Room type identifier
            guest_name: Guest name
            guest_email: Guest email address
            guest_phone: Guest phone number
            check_in_date: Check-in date (YYYY-MM-DD format)
            check_out_date: Check-out date (YYYY-MM-DD format)
            guests: Number of guests
            package_type: Package type (simple, breakfast, all_inclusive)

        Returns:
            Dictionary containing reservation confirmation details
        """
        logger.info(
            "Creating reservation",
            extra={
                "hotel_id": hotel_id,
                "room_type_id": room_type_id,
                "guest_name": guest_name,
                "check_in": check_in_date,
                "check_out": check_out_date,
                "guests": guests,
                "package_type": package_type,
            },
        )

        # Generate unique confirmation ID using timestamp
        confirmation_id = f"CONF-{int(time.time() * 1000)}"

        # Get current timestamp
        current_time = datetime.now().isoformat()

        # Create reservation record
        reservation = {
            "reservation_id": confirmation_id,
            "hotel_id": hotel_id,
            "room_type_id": room_type_id,
            "guest_name": guest_name,
            "guest_email": guest_email,
            "guest_phone": guest_phone,
            "check_in_date": check_in_date,
            "check_out_date": check_out_date,
            "guests": guests,
            "package_type": package_type,
            "status": "confirmed",
            "created_at": current_time,
            "updated_at": current_time,
        }

        # Store reservation in DynamoDB
        try:
            self.reservations_table.put_item(Item=reservation)

            logger.info(
                "Reservation created successfully",
                extra={
                    "reservation_id": confirmation_id,
                    "guest_email": guest_email,
                },
            )

            return {
                "reservation_id": confirmation_id,
                "status": "confirmed",
                "guest_name": guest_name,
                "guest_email": guest_email,
                "hotel_id": hotel_id,
                "room_type_id": room_type_id,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "guests": guests,
                "package_type": package_type,
                "created_at": current_time,
            }

        except Exception as e:
            logger.error(
                "Failed to create reservation",
                extra={
                    "error": str(e),
                    "guest_email": guest_email,
                },
            )
            raise Exception(f"Failed to create reservation: {str(e)}") from e

    def get_reservation(self, reservation_id: str) -> dict[str, Any] | None:
        """
        Retrieve a reservation by ID.

        Args:
            reservation_id: Reservation confirmation ID

        Returns:
            Dictionary containing reservation details or None if not found
        """
        logger.info("Retrieving reservation", extra={"reservation_id": reservation_id})

        try:
            response = self.reservations_table.get_item(
                Key={"reservation_id": reservation_id}
            )

            reservation = response.get("Item")
            if not reservation:
                logger.warning(
                    "Reservation not found", extra={"reservation_id": reservation_id}
                )
                return None

            logger.info(
                "Reservation retrieved successfully",
                extra={
                    "reservation_id": reservation_id,
                    "guest_name": reservation.get("guest_name"),
                },
            )

            return reservation

        except Exception as e:
            logger.error(
                "Failed to retrieve reservation",
                extra={
                    "error": str(e),
                    "reservation_id": reservation_id,
                },
            )
            raise Exception(f"Failed to retrieve reservation: {str(e)}") from e

    def get_reservations_by_hotel(
        self, hotel_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve reservations by hotel ID.

        Args:
            hotel_id: Hotel identifier
            limit: Optional limit on number of results

        Returns:
            List of reservation dictionaries
        """
        logger.info(
            "Retrieving reservations by hotel",
            extra={"hotel_id": hotel_id, "limit": limit},
        )

        try:
            # Scan table filtering by hotel_id (in a real system, this would use a GSI)
            scan_kwargs = {
                "FilterExpression": "hotel_id = :hotel_id",
                "ExpressionAttributeValues": {":hotel_id": hotel_id},
            }

            if limit:
                scan_kwargs["Limit"] = limit

            response = self.reservations_table.scan(**scan_kwargs)
            reservations = response.get("Items", [])

            logger.info(
                "Reservations retrieved by hotel",
                extra={
                    "hotel_id": hotel_id,
                    "count": len(reservations),
                },
            )

            return reservations

        except Exception as e:
            logger.error(
                "Failed to retrieve reservations by hotel",
                extra={
                    "error": str(e),
                    "hotel_id": hotel_id,
                },
            )
            raise Exception(
                f"Failed to retrieve reservations by hotel: {str(e)}"
            ) from e

    def get_reservations_by_guest_email(self, guest_email: str) -> list[dict[str, Any]]:
        """
        Retrieve reservations by guest email.

        Args:
            guest_email: Guest email address

        Returns:
            List of reservation dictionaries
        """
        logger.info(
            "Retrieving reservations by guest email", extra={"guest_email": guest_email}
        )

        try:
            # Scan table filtering by guest_email (in a real system, this would use a GSI)
            response = self.reservations_table.scan(
                FilterExpression="guest_email = :guest_email",
                ExpressionAttributeValues={":guest_email": guest_email},
            )

            reservations = response.get("Items", [])

            logger.info(
                "Reservations retrieved by guest email",
                extra={
                    "guest_email": guest_email,
                    "count": len(reservations),
                },
            )

            return reservations

        except Exception as e:
            logger.error(
                "Failed to retrieve reservations by guest email",
                extra={
                    "error": str(e),
                    "guest_email": guest_email,
                },
            )
            raise Exception(
                f"Failed to retrieve reservations by guest email: {str(e)}"
            ) from e

    def update_reservation(
        self, reservation_id: str, update_fields: dict[str, Any]
    ) -> dict[str, Any] | None:
        """
        Update an existing reservation with field updates.

        Args:
            reservation_id: Reservation confirmation ID
            update_fields: Dictionary of fields to update

        Returns:
            Updated reservation dictionary or None if not found
        """
        logger.info(
            "Updating reservation",
            extra={
                "reservation_id": reservation_id,
                "update_fields": list(update_fields.keys()),
            },
        )

        try:
            # First check if reservation exists
            existing_reservation = self.get_reservation(reservation_id)
            if not existing_reservation:
                logger.warning(
                    "Cannot update - reservation not found",
                    extra={"reservation_id": reservation_id},
                )
                return None

            # Prepare update expression with attribute names for reserved keywords
            update_expression_parts = []
            expression_attribute_values = {}
            expression_attribute_names = {}

            # Add updated_at timestamp
            update_fields["updated_at"] = datetime.now().isoformat()

            # DynamoDB reserved keywords that need expression attribute names
            reserved_keywords = {"status", "timestamp", "data", "name", "type", "value"}

            for field, value in update_fields.items():
                # Convert float to Decimal for DynamoDB compatibility
                if isinstance(value, float):
                    value = Decimal(str(value))

                if field.lower() in reserved_keywords:
                    # Use expression attribute name for reserved keywords
                    attr_name = f"#{field}"
                    attr_value = f":{field}"
                    update_expression_parts.append(f"{attr_name} = {attr_value}")
                    expression_attribute_names[attr_name] = field
                    expression_attribute_values[attr_value] = value
                else:
                    # Use field name directly for non-reserved keywords
                    update_expression_parts.append(f"{field} = :{field}")
                    expression_attribute_values[f":{field}"] = value

            update_expression = "SET " + ", ".join(update_expression_parts)

            # Build update_item parameters
            update_params = {
                "Key": {"reservation_id": reservation_id},
                "UpdateExpression": update_expression,
                "ExpressionAttributeValues": expression_attribute_values,
                "ReturnValues": "ALL_NEW",
            }

            # Only add ExpressionAttributeNames if we have reserved keywords
            if expression_attribute_names:
                update_params["ExpressionAttributeNames"] = expression_attribute_names

            # Update the reservation
            response = self.reservations_table.update_item(**update_params)

            updated_reservation = response.get("Attributes")

            logger.info(
                "Reservation updated successfully",
                extra={
                    "reservation_id": reservation_id,
                    "updated_fields": list(update_fields.keys()),
                },
            )

            return updated_reservation

        except Exception as e:
            logger.error(
                "Failed to update reservation",
                extra={
                    "error": str(e),
                    "reservation_id": reservation_id,
                },
            )
            raise Exception(f"Failed to update reservation: {str(e)}") from e

    def checkout_guest(
        self, reservation_id: str, final_amount: float | None = None
    ) -> dict[str, Any] | None:
        """
        Check out a guest with final billing.

        Args:
            reservation_id: Reservation confirmation ID
            final_amount: Optional final billing amount

        Returns:
            Updated reservation dictionary with checkout details or None if not found
        """
        logger.info(
            "Checking out guest",
            extra={
                "reservation_id": reservation_id,
                "final_amount": final_amount,
            },
        )

        try:
            # Prepare checkout update fields
            checkout_fields = {
                "status": "checked_out",
                "checkout_time": datetime.now().isoformat(),
            }

            if final_amount is not None:
                checkout_fields["final_amount"] = final_amount
                checkout_fields["payment_status"] = "completed"

            # Update reservation with checkout details
            updated_reservation = self.update_reservation(
                reservation_id, checkout_fields
            )

            if updated_reservation:
                logger.info(
                    "Guest checked out successfully",
                    extra={
                        "reservation_id": reservation_id,
                        "guest_name": updated_reservation.get("guest_name"),
                    },
                )

            return updated_reservation

        except Exception as e:
            logger.error(
                "Failed to checkout guest",
                extra={
                    "error": str(e),
                    "reservation_id": reservation_id,
                },
            )
            raise Exception(f"Failed to checkout guest: {str(e)}") from e
