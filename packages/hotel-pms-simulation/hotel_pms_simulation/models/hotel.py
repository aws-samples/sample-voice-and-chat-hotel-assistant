# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Hotel data models."""

from datetime import datetime

from pydantic import BaseModel, Field

from .base import BaseEntity


class Hotel(BaseEntity):
    """Hotel entity model."""

    hotel_id: str = Field(..., description="Unique hotel identifier")
    name: str = Field(..., description="Hotel name")
    location: str = Field(..., description="Hotel location")
    timezone: str = Field(default="America/Mexico_City", description="Hotel timezone")


class HotelCreate(BaseModel):
    """Hotel creation model."""

    hotel_id: str = Field(..., description="Unique hotel identifier")
    name: str = Field(..., description="Hotel name")
    location: str = Field(..., description="Hotel location")
    timezone: str = Field(default="America/Mexico_City", description="Hotel timezone")


class HotelResponse(BaseModel):
    """Hotel response model."""

    hotel_id: str
    name: str
    location: str
    timezone: str
    created_at: datetime | None = None
