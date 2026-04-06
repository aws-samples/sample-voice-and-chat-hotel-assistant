# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Data models for the Hotel PMS API."""

from .base import BaseEntity, ErrorDetail, ErrorResponse, HealthResponse
from .hotel import Hotel, HotelCreate, HotelResponse
from .housekeeping_request import (
    HousekeepingRequest,
    HousekeepingRequestCreate,
    HousekeepingRequestResponse,
    HousekeepingRequestUpdate,
    RequestPriority,
    RequestStatus,
    RequestType,
)
from .rate_modifier import (
    RateModifier,
    RateModifierCreate,
    RateModifierResponse,
    SeasonType,
)
from .reservation import (
    PackageType,
    PaymentStatus,
    Reservation,
    ReservationCreate,
    ReservationResponse,
    ReservationStatus,
    ReservationUpdate,
)
from .room import Room, RoomCreate, RoomResponse, RoomStatus
from .room_type import RoomType, RoomTypeAvailability, RoomTypeCreate, RoomTypeResponse

__all__ = [
    # Base models
    "BaseEntity",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    # Hotel models
    "Hotel",
    "HotelCreate",
    "HotelResponse",
    # Room type models
    "RoomType",
    "RoomTypeCreate",
    "RoomTypeResponse",
    "RoomTypeAvailability",
    # Room models
    "Room",
    "RoomCreate",
    "RoomResponse",
    "RoomStatus",
    # Reservation models
    "Reservation",
    "ReservationCreate",
    "ReservationUpdate",
    "ReservationResponse",
    "PackageType",
    "ReservationStatus",
    "PaymentStatus",
    # Rate modifier models
    "RateModifier",
    "RateModifierCreate",
    "RateModifierResponse",
    "SeasonType",
    # Housekeeping request models
    "HousekeepingRequest",
    "HousekeepingRequestCreate",
    "HousekeepingRequestUpdate",
    "HousekeepingRequestResponse",
    "RequestType",
    "RequestPriority",
    "RequestStatus",
]
