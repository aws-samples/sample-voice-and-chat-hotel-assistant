# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from datetime import date
from enum import StrEnum
from typing import Any

from pydantic import AwareDatetime, BaseModel, EmailStr, Field


class PackageType(StrEnum):
    """
    Response detail level (simple or detailed)
    """

    simple = "simple"
    detailed = "detailed"


class AvailabilityRequest(BaseModel):
    hotel_id: str = Field(..., examples=["H-PVR-002"])
    """
    Unique identifier for the hotel
    """
    check_in_date: date = Field(..., examples=["2024-03-15"])
    """
    Check-in date in YYYY-MM-DD format
    """
    check_out_date: date = Field(..., examples=["2024-03-17"])
    """
    Check-out date in YYYY-MM-DD format
    """
    guests: int = Field(..., examples=[2], ge=1, le=10)
    """
    Number of guests
    """
    package_type: PackageType | None = "simple"
    """
    Response detail level (simple or detailed)
    """


class AvailableRoomType(BaseModel):
    room_type_id: str | None = None
    """
    Room type identifier
    """
    available_rooms: int | None = None
    """
    Number of available rooms
    """
    base_rate: float | None = None
    """
    Base rate per night
    """
    total_cost: float | None = None
    """
    Total cost for the stay (only in detailed package)
    """


class AvailabilityResponse(BaseModel):
    hotel_id: str | None = None
    """
    Hotel identifier
    """
    check_in_date: date | None = None
    """
    Check-in date
    """
    check_out_date: date | None = None
    """
    Check-out date
    """
    guests: int | None = None
    """
    Number of guests
    """
    available_room_types: list[AvailableRoomType] | None = None
    """
    List of available room types with pricing
    """


class QuoteRequest(BaseModel):
    hotel_id: str = Field(..., examples=["H-PVR-002"])
    """
    Unique identifier for the hotel
    """
    room_type_id: str = Field(..., examples=["RT-STD"])
    """
    Unique identifier for the room type
    """
    check_in_date: date = Field(..., examples=["2024-03-15"])
    """
    Check-in date in YYYY-MM-DD format
    """
    check_out_date: date = Field(..., examples=["2024-03-17"])
    """
    Check-out date in YYYY-MM-DD format
    """
    guests: int = Field(..., examples=[2], ge=1, le=10)
    """
    Number of guests
    """
    package_type: PackageType | None = "simple"
    """
    Response detail level (simple or detailed)
    """


class PricingBreakdown(BaseModel):
    """
    Detailed pricing breakdown (only in detailed package)
    """

    base_rate_per_night: float | None = None
    nights: int | None = None
    guest_multiplier: float | None = None
    subtotal: float | None = None
    total_with_guest_adjustment: float | None = None


class QuoteResponse(BaseModel):
    hotel_id: str | None = None
    """
    Hotel identifier
    """
    room_type_id: str | None = None
    """
    Room type identifier
    """
    check_in_date: date | None = None
    """
    Check-in date
    """
    check_out_date: date | None = None
    """
    Check-out date
    """
    guests: int | None = None
    """
    Number of guests
    """
    nights: int | None = None
    """
    Number of nights
    """
    base_rate: float | None = None
    """
    Base rate per night
    """
    total_cost: float | None = None
    """
    Total cost for the stay
    """
    quote_id: str | None = None
    """
    Unique quote identifier (required for reservation creation)
    """
    expires_at: AwareDatetime | None = None
    """
    Quote expiration timestamp
    """
    guest_multiplier: float | None = None
    """
    Guest count multiplier (only in detailed package)
    """
    pricing_breakdown: PricingBreakdown | None = None
    """
    Detailed pricing breakdown (only in detailed package)
    """


class ReservationRequest(BaseModel):
    quote_id: str = Field(..., examples=["Q-20240315-ABC123"])
    """
    Quote ID from generate_quote operation (required for reservation)
    """
    guest_name: str = Field(..., examples=["John Doe"])
    """
    Full name of the primary guest
    """
    guest_email: EmailStr = Field(..., examples=["john.doe@example.com"])
    """
    Email address of the guest
    """
    guest_phone: str = Field(..., examples=["+1-555-123-4567"])
    """
    Phone number of the guest (optional)
    """


class Status(StrEnum):
    """
    Reservation status
    """

    confirmed = "confirmed"
    checked_in = "checked_in"
    checked_out = "checked_out"
    cancelled = "cancelled"


class ReservationResponse(BaseModel):
    reservation_id: str | None = None
    """
    Unique reservation identifier
    """
    status: Status | None = None
    """
    Reservation status
    """
    hotel_id: str | None = None
    """
    Hotel identifier
    """
    guest_name: str | None = None
    """
    Guest name
    """
    guest_email: str | None = None
    """
    Guest email
    """
    guest_phone: str | None = None
    """
    Guest phone
    """
    check_in_date: date | None = None
    """
    Check-in date
    """
    check_out_date: date | None = None
    """
    Check-out date
    """
    room_type_id: str | None = None
    """
    Room type identifier
    """
    total_cost: float | None = None
    """
    Total reservation cost
    """
    created_at: AwareDatetime | None = None
    """
    Reservation creation timestamp
    """


class Status1(StrEnum):
    """
    Updated reservation status
    """

    confirmed = "confirmed"
    checked_in = "checked_in"
    checked_out = "checked_out"
    cancelled = "cancelled"


class ReservationUpdateRequest(BaseModel):
    guest_name: str | None = None
    """
    Updated guest name
    """
    guest_email: EmailStr | None = None
    """
    Updated guest email
    """
    guest_phone: str | None = None
    """
    Updated guest phone
    """
    status: Status1 | None = None
    """
    Updated reservation status
    """


class PaymentMethod(StrEnum):
    """
    Payment method for checkout
    """

    card = "card"
    cash = "cash"
    transfer = "transfer"


class CheckoutRequest(BaseModel):
    additional_charges: float | None = Field(default=None, examples=[50.0])
    """
    Additional charges (room service, minibar, etc.)
    """
    payment_method: PaymentMethod | None = Field(default=None, examples=["card"])
    """
    Payment method for checkout
    """


class Status2(StrEnum):
    """
    Updated reservation status
    """

    checked_out = "checked_out"


class CheckoutResponse(BaseModel):
    reservation_id: str | None = None
    """
    Reservation identifier
    """
    status: Status2 | None = None
    """
    Updated reservation status
    """
    final_bill: float | None = None
    """
    Final bill amount including additional charges
    """
    checkout_time: AwareDatetime | None = None
    """
    Checkout timestamp
    """


class Hotel(BaseModel):
    hotel_id: str | None = None
    """
    Hotel identifier
    """
    name: str | None = None
    """
    Hotel name
    """
    location: str | None = None
    """
    Hotel location
    """
    timezone: str | None = None
    """
    Hotel timezone
    """


class HotelsResponse(BaseModel):
    hotels: list[Hotel] | None = None
    """
    List of available hotels
    """


class RequestType(StrEnum):
    """
    Type of housekeeping request
    """

    cleaning = "cleaning"
    maintenance = "maintenance"
    amenities = "amenities"
    towels = "towels"
    other = "other"


class HousekeepingRequest(BaseModel):
    hotel_id: str = Field(..., examples=["H-PVR-002"])
    """
    Unique identifier for the hotel
    """
    room_number: str = Field(..., examples=["101"])
    """
    Room number where service is needed
    """
    guest_name: str = Field(..., examples=["John Doe"])
    """
    Name of the guest making the request
    """
    request_type: RequestType = Field(..., examples=["cleaning"])
    """
    Type of housekeeping request
    """
    description: str | None = Field(
        default=None, examples=["Please clean the bathroom and replace towels"]
    )
    """
    Detailed description of the request
    """


class Status3(StrEnum):
    """
    Request status
    """

    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"


class HousekeepingResponse(BaseModel):
    request_id: str | None = None
    """
    Unique request identifier
    """
    hotel_id: str | None = None
    """
    Hotel identifier
    """
    room_number: str | None = None
    """
    Room number
    """
    guest_name: str | None = None
    """
    Guest name
    """
    request_type: str | None = None
    """
    Request type
    """
    description: str | None = None
    """
    Request description
    """
    status: Status3 | None = None
    """
    Request status
    """
    created_at: AwareDatetime | None = None
    """
    Request creation timestamp
    """


class Detail(BaseModel):
    field: str
    """
    Field path that failed validation (e.g., "guests", "check_in_date")
    """
    message: str
    """
    Human-readable error message for this field
    """
    type: str
    """
    Error type (e.g., "int_type", "greater_than_equal", "value_error")
    """
    input: Any | None = None
    """
    The invalid input value that was provided
    """


class ErrorResponse(BaseModel):
    error: bool
    """
    Indicates an error occurred
    """
    error_code: str
    """
    Machine-readable error code (e.g., VALIDATION_ERROR, NOT_FOUND, INTERNAL_ERROR)
    """
    message: str
    """
    Human-readable error message
    """
    details: list[Detail] | None = None
    """
    Array of field-level validation errors (present for VALIDATION_ERROR)
    """
