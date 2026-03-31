# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Room type data models."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from .base import BaseEntity


class RoomType(BaseEntity):
    """Room type entity model."""

    room_type_id: str = Field(..., description="Unique room type identifier")
    hotel_id: str = Field(..., description="Hotel identifier")
    name: str = Field(..., description="Room type name")
    description: str | None = Field(None, description="Room type description")
    max_occupancy: int = Field(..., description="Maximum occupancy")
    total_rooms: int = Field(..., description="Total number of rooms of this type")
    base_rate: Decimal = Field(..., description="Base rate per night")
    breakfast_rate: Decimal = Field(..., description="Rate with breakfast included")
    all_inclusive_rate: Decimal = Field(..., description="All-inclusive rate")


class RoomTypeCreate(BaseModel):
    """Room type creation model."""

    room_type_id: str = Field(..., description="Unique room type identifier")
    hotel_id: str = Field(..., description="Hotel identifier")
    name: str = Field(..., description="Room type name")
    description: str | None = Field(None, description="Room type description")
    max_occupancy: int = Field(..., description="Maximum occupancy")
    total_rooms: int = Field(..., description="Total number of rooms of this type")
    base_rate: Decimal = Field(..., description="Base rate per night")
    breakfast_rate: Decimal = Field(..., description="Rate with breakfast included")
    all_inclusive_rate: Decimal = Field(..., description="All-inclusive rate")


class RoomTypeResponse(BaseModel):
    """Room type response model."""

    room_type_id: str
    hotel_id: str
    name: str
    description: str | None = None
    max_occupancy: int
    total_rooms: int
    base_rate: Decimal
    breakfast_rate: Decimal
    all_inclusive_rate: Decimal
    created_at: datetime | None = None


class RoomTypeAvailability(BaseModel):
    """Room type availability model."""

    room_type_id: str
    name: str
    description: str | None = None
    max_occupancy: int
    available_rooms: int
    rate_per_night: Decimal
    total_cost: Decimal
    package_type: str
