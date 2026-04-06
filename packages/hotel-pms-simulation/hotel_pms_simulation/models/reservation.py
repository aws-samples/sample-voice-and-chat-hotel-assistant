# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Reservation data models."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field, computed_field

from .base import BaseEntity


class Reservation(BaseEntity):
    """Reservation entity model."""

    reservation_id: str = Field(..., description="Unique reservation identifier")
    hotel_id: str = Field(..., description="Hotel identifier")
    room_id: str | None = Field(None, description="Assigned room identifier")
    room_type_id: str = Field(..., description="Room type identifier")
    guest_name: str = Field(..., description="Guest name")
    guest_email: str | None = Field(None, description="Guest email")
    guest_phone: str | None = Field(None, description="Guest phone")
    check_in_date: date = Field(..., description="Check-in date")
    check_out_date: date = Field(..., description="Check-out date")
    guests: int = Field(..., description="Number of guests")
    package_type: str = Field(..., description="Package type")
    base_amount: Decimal = Field(..., description="Base amount before modifiers")
    total_amount: Decimal = Field(..., description="Total amount")
    status: str = Field(default="pending", description="Reservation status")
    payment_status: str = Field(default="pending", description="Payment status")

    @computed_field
    @property
    def nights(self) -> int:
        """Calculate number of nights."""
        return (self.check_out_date - self.check_in_date).days


class ReservationCreate(BaseModel):
    """Reservation creation model."""

    hotel_id: str = Field(..., description="Hotel identifier")
    room_type_id: str = Field(..., description="Room type identifier")
    guest_name: str = Field(..., description="Guest name")
    guest_email: str | None = Field(None, description="Guest email")
    guest_phone: str | None = Field(None, description="Guest phone")
    check_in_date: date = Field(..., description="Check-in date")
    check_out_date: date = Field(..., description="Check-out date")
    guests: int = Field(..., description="Number of guests")
    package_type: str = Field(..., description="Package type")


class ReservationUpdate(BaseModel):
    """Reservation update model."""

    guest_name: str | None = Field(None, description="Guest name")
    guest_email: str | None = Field(None, description="Guest email")
    guest_phone: str | None = Field(None, description="Guest phone")
    check_in_date: date | None = Field(None, description="Check-in date")
    check_out_date: date | None = Field(None, description="Check-out date")
    guests: int | None = Field(None, description="Number of guests")
    package_type: str | None = Field(None, description="Package type")
    status: str | None = Field(None, description="Reservation status")
    payment_status: str | None = Field(None, description="Payment status")


class ReservationResponse(BaseModel):
    """Reservation response model."""

    reservation_id: str
    hotel_id: str
    room_id: str | None = None
    room_number: str | None = None
    room_type_id: str
    guest_name: str
    guest_email: str | None = None
    guest_phone: str | None = None
    check_in_date: date
    check_out_date: date
    guests: int
    package_type: str
    nights: int
    base_amount: Decimal
    total_amount: Decimal
    status: str
    payment_status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PackageType:
    """Package type constants."""

    SIMPLE = "simple"
    BREAKFAST = "breakfast"
    ALL_INCLUSIVE = "all_inclusive"


class ReservationStatus:
    """Reservation status constants."""

    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"


class PaymentStatus:
    """Payment status constants."""

    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"
    REFUNDED = "refunded"
