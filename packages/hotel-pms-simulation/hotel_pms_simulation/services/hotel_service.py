# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""hotel information and service management for hotel operations."""

import os
import time
from datetime import datetime
from typing import Any

import boto3
from aws_lambda_powertools import Logger

logger = Logger()


class HotelService:
    """service for hotel information and housekeeping requests."""

    def __init__(self):
        """Initialize the service with DynamoDB connections."""
        self.dynamodb = boto3.resource("dynamodb")

        # Get table names from environment variables
        self.hotels_table_name = os.environ.get("HOTELS_TABLE_NAME", "hotel-hotels")
        self.requests_table_name = os.environ.get(
            "REQUESTS_TABLE_NAME", "hotel-requests"
        )

        # Initialize table references
        self.hotels_table = self.dynamodb.Table(self.hotels_table_name)
        self.requests_table = self.dynamodb.Table(self.requests_table_name)

    def get_hotels(self, limit: int | None = None) -> dict[str, Any]:
        """
        Query all hotels from DynamoDB with optional limit parameter.

        Args:
            limit: Optional limit on number of hotels to return

        Returns:
            Dictionary with hotel list and metadata
        """
        logger.info(
            "Retrieving hotels list",
            extra={"limit": limit},
        )

        try:
            # Scan hotels table to get all hotels
            scan_kwargs = {}
            if limit:
                scan_kwargs["Limit"] = limit

            response = self.hotels_table.scan(**scan_kwargs)
            hotels = response.get("Items", [])

            # Sort hotels by hotel_id for consistent ordering
            hotels.sort(key=lambda h: h.get("hotel_id", ""))

            logger.info(
                "Hotels retrieved successfully",
                extra={
                    "total_count": len(hotels),
                    "limit": limit,
                },
            )

            return {
                "hotels": hotels,
                "total_count": len(hotels),
                "limit_applied": limit is not None,
            }

        except Exception as e:
            logger.error(
                "Failed to retrieve hotels",
                extra={
                    "error": str(e),
                    "limit": limit,
                },
            )
            raise Exception(f"Failed to retrieve hotels: {str(e)}") from e

    def create_housekeeping_request(
        self,
        hotel_id: str,
        room_number: str,
        request_type: str,
        description: str | None = None,
        priority: str = "normal",
        guest_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Store service requests in DynamoDB with unique request IDs.

        Args:
            hotel_id: Hotel identifier
            room_number: Room number for the request
            request_type: Type of request (cleaning, maintenance, amenities, etc.)
            description: Optional detailed description of the request
            priority: Request priority (low, normal, high, urgent)
            guest_name: Optional guest name if request is from a guest

        Returns:
            Dictionary containing request confirmation details
        """
        logger.info(
            "Creating housekeeping request",
            extra={
                "hotel_id": hotel_id,
                "room_number": room_number,
                "request_type": request_type,
                "priority": priority,
            },
        )

        # Generate unique request ID using timestamp
        request_id = f"REQ-{int(time.time() * 1000)}"

        # Get current timestamp
        current_time = datetime.now().isoformat()

        # Create request record
        request_record = {
            "request_id": request_id,
            "hotel_id": hotel_id,
            "room_number": room_number,
            "request_type": request_type,
            "description": description or "",
            "priority": priority,
            "status": "pending",
            "created_at": current_time,
            "updated_at": current_time,
        }

        # Add guest name if provided
        if guest_name:
            request_record["guest_name"] = guest_name

        # Store request in DynamoDB
        try:
            self.requests_table.put_item(Item=request_record)

            logger.info(
                "Housekeeping request created successfully",
                extra={
                    "request_id": request_id,
                    "hotel_id": hotel_id,
                    "room_number": room_number,
                    "request_type": request_type,
                },
            )

            return {
                "request_id": request_id,
                "hotel_id": hotel_id,
                "room_number": room_number,
                "request_type": request_type,
                "description": description or "",
                "priority": priority,
                "status": "pending",
                "guest_name": guest_name,
                "created_at": current_time,
            }

        except Exception as e:
            logger.error(
                "Failed to create housekeeping request",
                extra={
                    "error": str(e),
                    "hotel_id": hotel_id,
                    "room_number": room_number,
                    "request_type": request_type,
                },
            )
            raise Exception(f"Failed to create housekeeping request: {str(e)}") from e

    def get_housekeeping_request(self, request_id: str) -> dict[str, Any] | None:
        """
        Retrieve a housekeeping request by ID.

        Args:
            request_id: Request ID

        Returns:
            Dictionary containing request details or None if not found
        """
        logger.info("Retrieving housekeeping request", extra={"request_id": request_id})

        try:
            response = self.requests_table.get_item(Key={"request_id": request_id})

            request_record = response.get("Item")
            if not request_record:
                logger.warning(
                    "Housekeeping request not found", extra={"request_id": request_id}
                )
                return None

            logger.info(
                "Housekeeping request retrieved successfully",
                extra={
                    "request_id": request_id,
                    "hotel_id": request_record.get("hotel_id"),
                    "room_number": request_record.get("room_number"),
                },
            )

            return request_record

        except Exception as e:
            logger.error(
                "Failed to retrieve housekeeping request",
                extra={
                    "error": str(e),
                    "request_id": request_id,
                },
            )
            raise Exception(f"Failed to retrieve housekeeping request: {str(e)}") from e

    def get_housekeeping_requests_by_hotel(
        self, hotel_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """
        Retrieve housekeeping requests by hotel ID.

        Args:
            hotel_id: Hotel identifier
            limit: Optional limit on number of results

        Returns:
            List of request dictionaries
        """
        logger.info(
            "Retrieving housekeeping requests by hotel",
            extra={"hotel_id": hotel_id, "limit": limit},
        )

        try:
            # Scan table filtering by hotel_id (in a real system, this would use a GSI)
            scan_kwargs = {
                "FilterExpression": "hotel_id = :hotel_id",
                "ExpressionAttributeValues": {":hotel_id": hotel_id},
            }

            if limit:
                scan_kwargs["Limit"] = limit

            response = self.requests_table.scan(**scan_kwargs)
            requests = response.get("Items", [])

            # Sort requests by created_at for consistent ordering
            requests.sort(key=lambda r: r.get("created_at", ""), reverse=True)

            logger.info(
                "Housekeeping requests retrieved by hotel",
                extra={
                    "hotel_id": hotel_id,
                    "count": len(requests),
                },
            )

            return requests

        except Exception as e:
            logger.error(
                "Failed to retrieve housekeeping requests by hotel",
                extra={
                    "error": str(e),
                    "hotel_id": hotel_id,
                },
            )
            raise Exception(
                f"Failed to retrieve housekeeping requests by hotel: {str(e)}"
            ) from e
