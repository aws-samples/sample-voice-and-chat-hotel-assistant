# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Base models and common schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BaseEntity(BaseModel):
    """Base entity with common fields."""

    model_config = ConfigDict(from_attributes=True)

    created_at: datetime | None = Field(None, description="Creation timestamp")
    updated_at: datetime | None = Field(None, description="Last update timestamp")


class ErrorResponse(BaseModel):
    """Standard error response format."""

    error: "ErrorDetail"


class ErrorDetail(BaseModel):
    """Error detail information."""

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Human-readable error message")
    details: dict | None = Field(None, description="Additional error details")


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="Service version")
