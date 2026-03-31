# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Housekeeping request data models."""

from datetime import datetime

from pydantic import BaseModel, Field

from .base import BaseEntity


class HousekeepingRequest(BaseEntity):
    """Housekeeping request entity model."""

    request_id: str = Field(..., description="Unique request identifier")
    hotel_id: str = Field(..., description="Hotel identifier")
    room_number: str = Field(..., description="Room number")
    guest_name: str = Field(..., description="Guest name")
    request_type: str = Field(..., description="Type of request")
    description: str | None = Field(None, description="Request description")
    priority: str = Field(default="normal", description="Request priority")
    status: str = Field(default="pending", description="Request status")
    requested_at: datetime | None = Field(None, description="Request timestamp")
    completed_at: datetime | None = Field(None, description="Completion timestamp")
    notes: str | None = Field(None, description="Additional notes")


class HousekeepingRequestCreate(BaseModel):
    """Housekeeping request creation model."""

    hotel_id: str = Field(..., description="Hotel identifier")
    room_number: str = Field(..., description="Room number")
    guest_name: str = Field(..., description="Guest name")
    request_type: str = Field(..., description="Type of request")
    description: str | None = Field(None, description="Request description")
    priority: str = Field(default="normal", description="Request priority")


class HousekeepingRequestUpdate(BaseModel):
    """Housekeeping request update model."""

    status: str | None = Field(None, description="Request status")
    notes: str | None = Field(None, description="Additional notes")
    completed_at: datetime | None = Field(None, description="Completion timestamp")


class HousekeepingRequestResponse(BaseModel):
    """Housekeeping request response model."""

    request_id: str
    hotel_id: str
    room_number: str
    guest_name: str
    request_type: str
    description: str | None = None
    priority: str
    status: str
    requested_at: datetime | None = None
    completed_at: datetime | None = None
    notes: str | None = None


class RequestType:
    """Request type constants."""

    CLEANING = "cleaning"
    TOWELS = "towels"
    AMENITIES = "amenities"
    PILLOWS = "pillows"
    MAINTENANCE = "maintenance"
    ROOM_SERVICE = "room_service"


class RequestPriority:
    """Request priority constants."""

    LOW = "low"
    NORMAL = (
        "medium"  # Database uses 'medium' but we expose as 'NORMAL' for API consistency
    )
    MEDIUM = "medium"  # Alias for backward compatibility
    HIGH = "high"
    URGENT = "urgent"


class RequestStatus:
    """Request status constants."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
