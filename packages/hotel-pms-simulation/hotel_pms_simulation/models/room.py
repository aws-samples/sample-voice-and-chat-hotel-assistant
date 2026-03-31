# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Room data models."""

from datetime import datetime

from pydantic import BaseModel, Field

from .base import BaseEntity


class Room(BaseEntity):
    """Room entity model."""

    room_id: str = Field(..., description="Unique room identifier")
    hotel_id: str = Field(..., description="Hotel identifier")
    room_number: str = Field(..., description="Room number")
    room_type_id: str = Field(..., description="Room type identifier")
    floor: int | None = Field(None, description="Floor number")
    status: str = Field(default="available", description="Room status")


class RoomCreate(BaseModel):
    """Room creation model."""

    room_id: str = Field(..., description="Unique room identifier")
    hotel_id: str = Field(..., description="Hotel identifier")
    room_number: str = Field(..., description="Room number")
    room_type_id: str = Field(..., description="Room type identifier")
    floor: int | None = Field(None, description="Floor number")
    status: str = Field(default="available", description="Room status")


class RoomResponse(BaseModel):
    """Room response model."""

    room_id: str
    hotel_id: str
    room_number: str
    room_type_id: str
    floor: int | None = None
    status: str
    created_at: datetime | None = None


class RoomStatus:
    """Room status constants."""

    AVAILABLE = "available"
    OCCUPIED = "occupied"
    CLEANING = "cleaning"
    MAINTENANCE = "maintenance"
    OUT_OF_ORDER = "out_of_order"
