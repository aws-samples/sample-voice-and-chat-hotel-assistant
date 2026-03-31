# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""API tool interfaces for Hotel PMS operations."""

from datetime import date, datetime
from typing import Any

from aws_lambda_powertools import Logger

from ..services.availability_service import AvailabilityService
from ..services.hotel_service import HotelService
from ..services.reservation_service import ReservationService

logger = Logger()


class HotelPMSTools:
    """tool wrappers for Hotel PMS API operations."""

    def __init__(self):
        """Initialize the tools with services."""
        self.availability_service = AvailabilityService()
        self.reservation_service = ReservationService()
        self.hotel_service = HotelService()

    def check_availability(
        self,
        hotel_id: str,
        check_in_date: str,
        check_out_date: str,
        guests: int,
        package_type: str = "simple",
    ) -> dict[str, Any]:
        """
        Check room availability tool wrapper.

        Args:
            hotel_id: Unique identifier for the hotel
            check_in_date: Check-in date in YYYY-MM-DD format
            check_out_date: Check-out date in YYYY-MM-DD format
            guests: Number of guests
            package_type: Package type (simple or detailed)

        Returns:
            Formatted availability response according to schema
        """
        logger.info(
            "Processing check_availability tool request",
            extra={
                "hotel_id": hotel_id,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "guests": guests,
                "package_type": package_type,
            },
        )

        # Validate input parameters
        if not hotel_id or not hotel_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "hotel_id is required and cannot be empty",
            }

        if not check_in_date or not check_out_date:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "check_in_date and check_out_date are required",
            }

        if guests <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "guests must be a positive integer",
            }

        # Validate date format (handle both str and date objects)
        try:
            if isinstance(check_in_date, date):
                pass  # Already a date object, no need to validate
            else:
                datetime.strptime(check_in_date, "%Y-%m-%d")

            if isinstance(check_out_date, date):
                pass  # Already a date object, no need to validate
            else:
                datetime.strptime(check_out_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid date format. Use YYYY-MM-DD format",
            }

        try:
            # Call availability logic
            result = self.availability_service.check_availability(
                hotel_id, check_in_date, check_out_date, guests
            )

            # Check if there was an error in the service response
            if not result.get("available", False) and "message" in result:
                return {
                    "error": True,
                    "error_code": "AVAILABILITY_ERROR",
                    "message": result["message"],
                }

            # Format response according to schema
            formatted_response = {
                "hotel_id": hotel_id,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "guests": guests,
                "available_room_types": [],
            }

            # Add room type information with pricing if available
            for room_type in result.get("available_room_types", []):
                room_info = {
                    "room_type_id": room_type["room_type_id"],
                    "available_rooms": room_type["available_rooms"],
                    "base_rate": room_type["base_rate"],
                }

                # Add total cost calculation if detailed package requested
                if package_type == "detailed":
                    # Calculate total cost using the pricing service
                    quote_result = self.availability_service.generate_quote(
                        hotel_id,
                        room_type["room_type_id"],
                        check_in_date,
                        check_out_date,
                        guests,
                    )
                    if not quote_result.get("error"):
                        room_info["total_cost"] = quote_result.get("total_cost", 0)

                formatted_response["available_room_types"].append(room_info)

            logger.info(
                "check_availability tool completed successfully",
                extra={
                    "hotel_id": hotel_id,
                    "available_room_types": len(
                        formatted_response["available_room_types"]
                    ),
                },
            )

            return formatted_response

        except Exception as e:
            logger.error(
                "Error in check_availability tool",
                extra={
                    "error": str(e),
                    "hotel_id": hotel_id,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to check availability: {str(e)}",
            }

    def generate_quote(
        self,
        hotel_id: str,
        room_type_id: str,
        check_in_date: str,
        check_out_date: str,
        guests: int,
        package_type: str = "simple",
    ) -> dict[str, Any]:
        """
        Generate pricing quote tool wrapper.

        Args:
            hotel_id: Unique identifier for the hotel
            room_type_id: Unique identifier for the room type
            check_in_date: Check-in date in YYYY-MM-DD format
            check_out_date: Check-out date in YYYY-MM-DD format
            guests: Number of guests
            package_type: Package type (simple or detailed)

        Returns:
            Formatted quote response with detailed pricing breakdown
        """
        logger.info(
            "Processing generate_quote tool request",
            extra={
                "hotel_id": hotel_id,
                "room_type_id": room_type_id,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "guests": guests,
                "package_type": package_type,
            },
        )

        # Validate input parameters
        if not hotel_id or not hotel_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "hotel_id is required and cannot be empty",
            }

        if not room_type_id or not room_type_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "room_type_id is required and cannot be empty",
            }

        if not check_in_date or not check_out_date:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "check_in_date and check_out_date are required",
            }

        if guests <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "guests must be a positive integer",
            }

        # Validate date format (handle both str and date objects)
        try:
            if isinstance(check_in_date, date):
                pass  # Already a date object, no need to validate
            else:
                datetime.strptime(check_in_date, "%Y-%m-%d")

            if isinstance(check_out_date, date):
                pass  # Already a date object, no need to validate
            else:
                datetime.strptime(check_out_date, "%Y-%m-%d")
        except (ValueError, TypeError):
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Invalid date format. Use YYYY-MM-DD format",
            }

        try:
            # Call pricing calculation
            result = self.availability_service.generate_quote(
                hotel_id, room_type_id, check_in_date, check_out_date, guests
            )

            # Check if there was an error in the service response
            if result.get("error"):
                return {
                    "error": True,
                    "error_code": "QUOTE_ERROR",
                    "message": result.get("message", "Failed to generate quote"),
                }

            # Format detailed quote response
            formatted_response = {
                "hotel_id": hotel_id,
                "room_type_id": room_type_id,
                "check_in_date": check_in_date,
                "check_out_date": check_out_date,
                "guests": guests,
                "nights": result.get("nights", 0),
                "base_rate": result.get("base_rate", 0),
                "total_cost": result.get("total_cost", 0),
                "quote_id": result.get(
                    "quote_id"
                ),  # Include quote_id for reservation creation
                "expires_at": result.get("expires_at"),  # Include expiration time
            }

            # Add detailed breakdown if requested
            if package_type == "detailed" and "pricing_breakdown" in result:
                formatted_response["pricing_breakdown"] = result["pricing_breakdown"]
                formatted_response["guest_multiplier"] = result.get(
                    "guest_multiplier", 1.0
                )

            logger.info(
                "generate_quote tool completed successfully",
                extra={
                    "hotel_id": hotel_id,
                    "room_type_id": room_type_id,
                    "total_cost": formatted_response["total_cost"],
                },
            )

            return formatted_response

        except Exception as e:
            logger.error(
                "Error in generate_quote tool",
                extra={
                    "error": str(e),
                    "hotel_id": hotel_id,
                    "room_type_id": room_type_id,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to generate quote: {str(e)}",
            }

    def create_reservation(
        self,
        quote_id: str,
        guest_name: str,
        guest_email: str,
        guest_phone: str,
        package_type: str = "simple",
    ) -> dict[str, Any]:
        """
        Create reservation tool wrapper (quote-based only).

        Args:
            quote_id: Quote ID from generate_quote (required)
            guest_name: Full name of the primary guest
            guest_email: Email address of the guest
            guest_phone: Phone number of the guest
            package_type: Package type (simple or detailed)

        Returns:
            Formatted reservation confirmation response
        """
        logger.info(
            "Processing create_reservation tool request",
            extra={
                "quote_id": quote_id,
                "guest_name": guest_name,
                "package_type": package_type,
            },
        )

        # Validate required parameters
        if not quote_id or not quote_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "quote_id is required and cannot be empty",
            }

        if not guest_name or not guest_name.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "guest_name is required and cannot be empty",
            }

        if not guest_email or not guest_email.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "guest_email is required and cannot be empty",
            }

        if not guest_phone or not guest_phone.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "guest_phone is required and cannot be empty",
            }

        try:
            # Retrieve quote from DynamoDB
            quote = self.availability_service.get_quote(quote_id)

            if not quote:
                return {
                    "error": True,
                    "error_code": "QUOTE_NOT_FOUND",
                    "message": f"Quote {quote_id} not found or has expired",
                }

            # Extract booking details from quote
            hotel_id = quote.get("hotel_id")
            room_type_id = quote.get("room_type_id")
            check_in_date = quote.get("check_in_date")
            check_out_date = quote.get("check_out_date")
            guests = quote.get("guests")

            logger.info(
                "Using quote-based reservation",
                extra={
                    "quote_id": quote_id,
                    "hotel_id": hotel_id,
                    "room_type_id": room_type_id,
                },
            )

            # Create reservation
            result = self.reservation_service.create_reservation(
                hotel_id=hotel_id,
                room_type_id=room_type_id,
                guest_name=guest_name,
                guest_email=guest_email,
                guest_phone=guest_phone,
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                guests=guests,
                package_type=package_type,
            )

            logger.info(
                "create_reservation tool completed successfully",
                extra={
                    "reservation_id": result.get("reservation_id"),
                    "guest_name": guest_name,
                    "quote_id": quote_id,
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error in create_reservation tool",
                extra={
                    "error": str(e),
                    "guest_name": guest_name,
                    "quote_id": quote_id,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to create reservation: {str(e)}",
            }

    def get_reservation(self, reservation_id: str) -> dict[str, Any]:
        """
        Get reservation by ID tool wrapper.

        Args:
            reservation_id: Unique identifier for the reservation

        Returns:
            Reservation details or error response
        """
        logger.info(
            "Processing get_reservation tool request",
            extra={"reservation_id": reservation_id},
        )

        # Validate required parameters
        if not reservation_id or not reservation_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "reservation_id is required and cannot be empty",
            }

        try:
            # Get reservation
            result = self.reservation_service.get_reservation(reservation_id)

            if result is None:
                return {
                    "error": True,
                    "error_code": "NOT_FOUND",
                    "message": f"Reservation {reservation_id} not found",
                }

            logger.info(
                "get_reservation tool completed successfully",
                extra={
                    "reservation_id": reservation_id,
                    "guest_name": result.get("guest_name"),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error in get_reservation tool",
                extra={
                    "error": str(e),
                    "reservation_id": reservation_id,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to get reservation: {str(e)}",
            }

    def get_reservations(
        self,
        hotel_id: str | None = None,
        guest_email: str | None = None,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """
        Get reservations by hotel or guest email tool wrapper.

        Args:
            hotel_id: Unique identifier for the hotel (use this OR guest_email)
            guest_email: Email address of the guest (use this OR hotel_id)
            limit: Maximum number of reservations to return

        Returns:
            List of reservations or error response
        """
        logger.info(
            "Processing get_reservations tool request",
            extra={
                "hotel_id": hotel_id,
                "guest_email": guest_email,
                "limit": limit,
            },
        )

        # Validate that either hotel_id or guest_email is provided
        if not hotel_id and not guest_email:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Either hotel_id or guest_email is required",
            }

        if hotel_id and guest_email:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "Provide either hotel_id or guest_email, not both",
            }

        try:
            # Get reservations based on criteria
            if hotel_id:
                reservations = self.reservation_service.get_reservations_by_hotel(
                    hotel_id, limit
                )
            else:
                reservations = self.reservation_service.get_reservations_by_guest_email(
                    guest_email
                )
                if limit and len(reservations) > limit:
                    reservations = reservations[:limit]

            result = {
                "reservations": reservations,
                "total_count": len(reservations),
            }

            logger.info(
                "get_reservations tool completed successfully",
                extra={
                    "hotel_id": hotel_id,
                    "guest_email": guest_email,
                    "count": len(reservations),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error in get_reservations tool",
                extra={
                    "error": str(e),
                    "hotel_id": hotel_id,
                    "guest_email": guest_email,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to get reservations: {str(e)}",
            }

    def update_reservation(
        self,
        reservation_id: str,
        guest_name: str | None = None,
        guest_email: str | None = None,
        guest_phone: str | None = None,
        check_in_date: str | None = None,
        check_out_date: str | None = None,
        guests: int | None = None,
        package_type: str | None = None,
        status: str | None = None,
        payment_status: str | None = None,
    ) -> dict[str, Any]:
        """
        Update reservation tool wrapper.

        Args:
            reservation_id: Unique identifier for the reservation
            guest_name: Updated guest name (optional)
            guest_email: Updated guest email (optional)
            guest_phone: Updated guest phone (optional)
            check_in_date: Updated check-in date in YYYY-MM-DD format (optional)
            check_out_date: Updated check-out date in YYYY-MM-DD format (optional)
            guests: Updated number of guests (optional)
            package_type: Updated package type (optional)
            status: Reservation status (optional)
            payment_status: Payment status (optional)

        Returns:
            Updated reservation details or error response
        """
        logger.info(
            "Processing update_reservation tool request",
            extra={
                "reservation_id": reservation_id,
                "update_fields": [
                    field
                    for field, value in {
                        "guest_name": guest_name,
                        "guest_email": guest_email,
                        "guest_phone": guest_phone,
                        "check_in_date": check_in_date,
                        "check_out_date": check_out_date,
                        "guests": guests,
                        "package_type": package_type,
                        "status": status,
                        "payment_status": payment_status,
                    }.items()
                    if value is not None
                ],
            },
        )

        # Validate required parameters
        if not reservation_id or not reservation_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "reservation_id is required and cannot be empty",
            }

        # Validate date formats if provided (handle both str and date objects)
        if check_in_date:
            try:
                if isinstance(check_in_date, date):
                    pass  # Already a date object, no need to validate
                else:
                    datetime.strptime(check_in_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Invalid check_in_date format. Use YYYY-MM-DD format",
                }

        if check_out_date:
            try:
                if isinstance(check_out_date, date):
                    pass  # Already a date object, no need to validate
                else:
                    datetime.strptime(check_out_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                return {
                    "error": True,
                    "error_code": "VALIDATION_ERROR",
                    "message": "Invalid check_out_date format. Use YYYY-MM-DD format",
                }

        # Validate guests if provided
        if guests is not None and guests <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "guests must be a positive integer",
            }

        try:
            # Build update fields dictionary
            update_fields = {}
            if guest_name is not None:
                update_fields["guest_name"] = guest_name
            if guest_email is not None:
                update_fields["guest_email"] = guest_email
            if guest_phone is not None:
                update_fields["guest_phone"] = guest_phone
            if check_in_date is not None:
                update_fields["check_in_date"] = check_in_date
            if check_out_date is not None:
                update_fields["check_out_date"] = check_out_date
            if guests is not None:
                update_fields["guests"] = guests
            if package_type is not None:
                update_fields["package_type"] = package_type
            if status is not None:
                update_fields["status"] = status
            if payment_status is not None:
                update_fields["payment_status"] = payment_status

            # Update reservation
            result = self.reservation_service.update_reservation(
                reservation_id, update_fields
            )

            if result is None:
                return {
                    "error": True,
                    "error_code": "NOT_FOUND",
                    "message": f"Reservation {reservation_id} not found",
                }

            logger.info(
                "update_reservation tool completed successfully",
                extra={
                    "reservation_id": reservation_id,
                    "updated_fields": list(update_fields.keys()),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error in update_reservation tool",
                extra={
                    "error": str(e),
                    "reservation_id": reservation_id,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to update reservation: {str(e)}",
            }

    def checkout_guest(
        self,
        reservation_id: str,
        additional_charges: float | None = None,
        payment_method: str = "card",
    ) -> dict[str, Any]:
        """
        Checkout guest tool wrapper.

        Args:
            reservation_id: Unique identifier for the reservation
            additional_charges: Additional charges to add to the bill (optional)
            payment_method: Payment method for final billing

        Returns:
            Checkout confirmation details or error response
        """
        logger.info(
            "Processing checkout_guest tool request",
            extra={
                "reservation_id": reservation_id,
                "additional_charges": additional_charges,
                "payment_method": payment_method,
            },
        )

        # Validate required parameters
        if not reservation_id or not reservation_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "reservation_id is required and cannot be empty",
            }

        # Validate additional_charges if provided
        if additional_charges is not None and additional_charges < 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "additional_charges cannot be negative",
            }

        try:
            # Checkout guest
            result = self.reservation_service.checkout_guest(
                reservation_id, additional_charges
            )

            if result is None:
                return {
                    "error": True,
                    "error_code": "NOT_FOUND",
                    "message": f"Reservation {reservation_id} not found",
                }

            # Add payment method to result
            result["payment_method"] = payment_method

            logger.info(
                "checkout_guest tool completed successfully",
                extra={
                    "reservation_id": reservation_id,
                    "guest_name": result.get("guest_name"),
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error in checkout_guest tool",
                extra={
                    "error": str(e),
                    "reservation_id": reservation_id,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to checkout guest: {str(e)}",
            }

    def get_hotels(self, limit: int | None = None) -> dict[str, Any]:
        """
        Get hotels list tool wrapper.

        Args:
            limit: Maximum number of hotels to return (optional)

        Returns:
            List of hotels with basic information or error response
        """
        logger.info(
            "Processing get_hotels tool request",
            extra={"limit": limit},
        )

        # Validate limit if provided
        if limit is not None and limit <= 0:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "limit must be a positive integer",
            }

        try:
            # Get hotels
            result = self.hotel_service.get_hotels(limit)

            logger.info(
                "get_hotels tool completed successfully",
                extra={
                    "total_count": result.get("total_count", 0),
                    "limit": limit,
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error in get_hotels tool",
                extra={
                    "error": str(e),
                    "limit": limit,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to get hotels: {str(e)}",
            }

    def create_housekeeping_request(
        self,
        hotel_id: str,
        room_number: str,
        guest_name: str,
        request_type: str,
        description: str | None = None,
    ) -> dict[str, Any]:
        """
        Create housekeeping request tool wrapper.

        Args:
            hotel_id: Unique identifier for the hotel
            room_number: Room number where service is needed
            guest_name: Name of the guest making the request
            request_type: Type of request (cleaning, maintenance, amenities, towels, other)
            description: Detailed description of the request (optional)

        Returns:
            Housekeeping request confirmation details or error response
        """
        logger.info(
            "Processing create_housekeeping_request tool request",
            extra={
                "hotel_id": hotel_id,
                "room_number": room_number,
                "guest_name": guest_name,
                "request_type": request_type,
            },
        )

        # Validate required parameters
        if not hotel_id or not hotel_id.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "hotel_id is required and cannot be empty",
            }

        if not room_number or not room_number.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "room_number is required and cannot be empty",
            }

        if not guest_name or not guest_name.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "guest_name is required and cannot be empty",
            }

        if not request_type or not request_type.strip():
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": "request_type is required and cannot be empty",
            }

        # Validate request_type against allowed values
        allowed_request_types = [
            "cleaning",
            "maintenance",
            "amenities",
            "towels",
            "other",
        ]
        if request_type not in allowed_request_types:
            return {
                "error": True,
                "error_code": "VALIDATION_ERROR",
                "message": f"request_type must be one of: {', '.join(allowed_request_types)}",
            }

        try:
            # Create housekeeping request
            result = self.hotel_service.create_housekeeping_request(
                hotel_id=hotel_id,
                room_number=room_number,
                request_type=request_type,
                description=description,
                guest_name=guest_name,
            )

            logger.info(
                "create_housekeeping_request tool completed successfully",
                extra={
                    "request_id": result.get("request_id"),
                    "hotel_id": hotel_id,
                    "room_number": room_number,
                    "request_type": request_type,
                },
            )

            return result

        except Exception as e:
            logger.error(
                "Error in create_housekeeping_request tool",
                extra={
                    "error": str(e),
                    "hotel_id": hotel_id,
                    "room_number": room_number,
                    "request_type": request_type,
                },
            )
            return {
                "error": True,
                "error_code": "INTERNAL_ERROR",
                "message": f"Failed to create housekeeping request: {str(e)}",
            }
