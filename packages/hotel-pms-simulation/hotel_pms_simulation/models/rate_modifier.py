# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Rate modifier data models."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from .base import BaseEntity


class RateModifier(BaseEntity):
    """Rate modifier entity model."""

    modifier_id: int = Field(..., description="Unique modifier identifier")
    hotel_id: str = Field(..., description="Hotel identifier")
    room_type_id: str | None = Field(
        None, description="Room type identifier (null for all room types)"
    )
    start_date: date = Field(..., description="Start date for modifier")
    end_date: date = Field(..., description="End date for modifier")
    multiplier: Decimal = Field(default=Decimal("1.00"), description="Rate multiplier")
    reason: str | None = Field(None, description="Reason for rate modification")


class RateModifierCreate(BaseModel):
    """Rate modifier creation model."""

    hotel_id: str = Field(..., description="Hotel identifier")
    room_type_id: str | None = Field(
        None, description="Room type identifier (null for all room types)"
    )
    start_date: date = Field(..., description="Start date for modifier")
    end_date: date = Field(..., description="End date for modifier")
    multiplier: Decimal = Field(default=Decimal("1.00"), description="Rate multiplier")
    reason: str | None = Field(None, description="Reason for rate modification")


class RateModifierResponse(BaseModel):
    """Rate modifier response model."""

    modifier_id: int
    hotel_id: str
    room_type_id: str | None = None
    start_date: date
    end_date: date
    multiplier: Decimal
    reason: str | None = None
    created_at: datetime | None = None


class SeasonType:
    """Season type constants for rate modifiers."""

    HIGH_SEASON = "high_season"
    LOW_SEASON = "low_season"
    PEAK_SEASON = "peak_season"
    SHOULDER_SEASON = "shoulder_season"
    SPECIAL_EVENT = "special_event"
