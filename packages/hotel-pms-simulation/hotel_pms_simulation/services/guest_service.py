# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Guest services functionality for checkout and housekeeping requests."""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from aws_lambda_powertools import Logger
from pydantic import BaseModel, Field

from ..database.repository import (
    HousekeepingRequestRepository,
    ReservationRepository,
    RoomRepository,
)
from ..exceptions import (
    GuestServiceError,
    InvalidCheckoutError,
    ReservationNotFoundError,
)
from ..models.housekeeping_request import (
    HousekeepingRequestResponse,
    RequestPriority,
    RequestStatus,
    RequestType,
)
from ..models.reservation import PaymentStatus, ReservationStatus

logger = Logger()


class CheckoutRequest(BaseModel):
    """Request model for guest checkout."""

    reservation_id: str = Field(..., description="Reservation ID to checkout")
    additional_charges: Decimal = Field(
        default=Decimal("0.00"),
        description="Additional charges (e.g., minibar, services)",
    )
    payment_method: str = Field(default="card", description="Payment method used")


class CheckoutResponse(BaseModel):
    """Response model for guest checkout."""

    reservation_id: str
    guest_name: str
    room_number: str | None = None
    check_out_date: str
    original_amount: Decimal
    additional_charges: Decimal
    final_amount: Decimal
    payment_status: str
    checkout_completed_at: datetime
    message: str


class HousekeepingRequestCreateRequest(BaseModel):
    """Request model for creating housekeeping requests."""

    hotel_id: str = Field(..., description="Hotel identifier")
    room_number: str = Field(..., description="Room number")
    guest_name: str = Field(..., description="Guest name")
    request_type: str = Field(..., description="Type of request")
    description: str | None = Field(None, description="Request description")


class GuestService:
    """Service for guest operations including checkout and housekeeping requests."""

    def __init__(self):
        self.reservation_repo = ReservationRepository()
        self.housekeeping_repo = HousekeepingRequestRepository()
        self.room_repo = RoomRepository()

    def checkout_guest(self, checkout_request: CheckoutRequest) -> CheckoutResponse:
        """
        Process guest checkout.

        Updates reservation status to checked_out and calculates final charges.
        """
        logger.info(
            f"Processing checkout for reservation {checkout_request.reservation_id}"
        )

        # Find the reservation
        reservation_data = self.reservation_repo.find_by_reservation_id(
            checkout_request.reservation_id
        )

        if not reservation_data:
            raise ReservationNotFoundError(
                f"Reservation {checkout_request.reservation_id} not found"
            )

        # Validate checkout is possible
        current_status = reservation_data.get("status")
        if current_status not in [
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        ]:
            raise InvalidCheckoutError(
                f"Cannot checkout reservation with status: {current_status}"
            )

        # Calculate final amount
        original_amount = Decimal(str(reservation_data.get("total_amount", "0.00")))
        final_amount = original_amount + checkout_request.additional_charges

        # Update reservation status
        update_data = {
            "status": ReservationStatus.CHECKED_OUT,
            "payment_status": PaymentStatus.PAID,
            "updated_at": datetime.now(UTC),
        }

        updated_reservation = self.reservation_repo.update(
            "reservation_id", checkout_request.reservation_id, update_data
        )

        if not updated_reservation:
            raise InvalidCheckoutError("Failed to update reservation status")

        # Get room number if available
        room_number = None
        if reservation_data.get("room_id"):
            # In a real implementation, we'd fetch room details
            # For now, we'll use a placeholder
            room_number = "TBD"  # This would be fetched from room repository

        logger.info(
            f"Checkout completed for reservation {checkout_request.reservation_id}"
        )

        return CheckoutResponse(
            reservation_id=checkout_request.reservation_id,
            guest_name=reservation_data["guest_name"],
            room_number=room_number,
            check_out_date=str(reservation_data["check_out_date"]),
            original_amount=original_amount,
            additional_charges=checkout_request.additional_charges,
            final_amount=final_amount,
            payment_status=PaymentStatus.PAID,
            checkout_completed_at=datetime.now(UTC),
            message="Checkout completed successfully",
        )

    def create_housekeeping_request(
        self, request: HousekeepingRequestCreateRequest
    ) -> HousekeepingRequestResponse:
        """
        Create a housekeeping request with automatic priority assignment.

        Priority is assigned based on request type:
        - cleaning: high priority
        - towels, amenities, pillows: normal priority
        - maintenance: urgent priority
        - room_service: high priority
        """
        logger.info(f"Creating housekeeping request for room {request.room_number}")

        # Generate unique request ID
        str(uuid.uuid4())

        # Determine priority based on request type
        priority = self._determine_priority(request.request_type)

        # Look up room_id from room_number
        room = self.room_repo.find_by_hotel_and_room_number(
            request.hotel_id, request.room_number
        )

        if not room:
            raise GuestServiceError(
                f"Room {request.room_number} not found in hotel {request.hotel_id}"
            )

        room_id = room["room_id"]

        # Create housekeeping request data
        # Note: request_id is SERIAL PRIMARY KEY, so we don't include it - DB will auto-generate
        housekeeping_data = {
            "hotel_id": request.hotel_id,
            "room_id": room_id,
            "request_type": request.request_type,
            "description": request.description,
            "priority": priority,
            "status": RequestStatus.PENDING,
            "requested_by": request.guest_name,
            "created_at": datetime.now(UTC),
        }

        # Save to database
        created_request = self.housekeeping_repo.create(housekeeping_data)

        if not created_request:
            raise GuestServiceError("Failed to create housekeeping request")

        logger.info(
            f"Housekeeping request {created_request['request_id']} created with priority {priority}"
        )

        return HousekeepingRequestResponse(
            request_id=str(created_request["request_id"]),  # Convert to string
            hotel_id=created_request["hotel_id"],
            room_number=request.room_number,  # Use from original request
            guest_name=request.guest_name,  # Use from original request
            request_type=created_request["request_type"],
            description=created_request.get("description"),
            priority=created_request["priority"],
            status=created_request["status"],
            requested_at=created_request.get(
                "created_at"
            ),  # Map created_at to requested_at
            completed_at=created_request.get("completed_at"),
            notes=created_request.get("notes"),
        )

    def get_housekeeping_requests(
        self, hotel_id: str, status: str | None = None
    ) -> list[HousekeepingRequestResponse]:
        """Get housekeeping requests for a hotel, optionally filtered by status."""
        logger.info(f"Fetching housekeeping requests for hotel {hotel_id}")

        if status:
            requests_data = self.housekeeping_repo.find_by_field("status", status)
            # Filter by hotel_id since find_by_field doesn't support multiple conditions
            requests_data = [r for r in requests_data if r.get("hotel_id") == hotel_id]
        else:
            requests_data = self.housekeeping_repo.find_by_hotel_id(hotel_id)

        return [
            HousekeepingRequestResponse(
                request_id=str(req["request_id"]),  # Convert to string
                hotel_id=req["hotel_id"],
                room_number=req["room_number"],
                guest_name=req["guest_name"],
                request_type=req["request_type"],
                description=req.get("description"),
                priority=req["priority"],
                status=req["status"],
                requested_at=req.get("requested_at"),
                completed_at=req.get("completed_at"),
                notes=req.get("notes"),
            )
            for req in requests_data
        ]

    def update_housekeeping_request_status(
        self, request_id: str, status: str, notes: str | None = None
    ) -> HousekeepingRequestResponse:
        """Update the status of a housekeeping request."""
        logger.info(f"Updating housekeeping request {request_id} to status {status}")

        # Prepare update data
        update_data: dict[str, Any] = {"status": status}

        if notes:
            update_data["notes"] = notes

        if status == RequestStatus.COMPLETED:
            update_data["completed_at"] = datetime.now(UTC)

        # Update the request
        updated_request = self.housekeeping_repo.update(
            "request_id", request_id, update_data
        )

        if not updated_request:
            raise GuestServiceError(f"Housekeeping request {request_id} not found")

        logger.info(f"Housekeeping request {request_id} updated successfully")

        return HousekeepingRequestResponse(
            request_id=str(updated_request["request_id"]),  # Convert to string
            hotel_id=updated_request["hotel_id"],
            room_number=updated_request["room_number"],
            guest_name=updated_request["guest_name"],
            request_type=updated_request["request_type"],
            description=updated_request.get("description"),
            priority=updated_request["priority"],
            status=updated_request["status"],
            requested_at=updated_request.get("requested_at"),
            completed_at=updated_request.get("completed_at"),
            notes=updated_request.get("notes"),
        )

    def _determine_priority(self, request_type: str) -> str:
        """
        Determine priority based on request type.

        Business rules:
        - cleaning: high priority (affects room availability)
        - towels, amenities, pillows: normal priority (guest comfort)
        - maintenance: urgent priority (safety/functionality)
        - room_service: high priority (guest satisfaction)
        - default: normal priority
        """
        priority_mapping = {
            RequestType.CLEANING: RequestPriority.HIGH,
            RequestType.TOWELS: RequestPriority.MEDIUM,  # Changed from NORMAL to MEDIUM
            RequestType.AMENITIES: RequestPriority.MEDIUM,  # Changed from NORMAL to MEDIUM
            RequestType.PILLOWS: RequestPriority.MEDIUM,  # Changed from NORMAL to MEDIUM
            RequestType.MAINTENANCE: RequestPriority.URGENT,
            RequestType.ROOM_SERVICE: RequestPriority.HIGH,
        }

        return priority_mapping.get(
            request_type, RequestPriority.MEDIUM
        )  # Changed from NORMAL to MEDIUM
