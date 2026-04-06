# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Phone number allow list validation service for WhatsApp messages."""

import os
import time

import boto3
from aws_lambda_powertools import Logger

logger = Logger()

# Cache for allow list to avoid repeated SSM calls
_allow_list_cache = {"value": None, "timestamp": 0}
_cache_ttl = 300  # 5 minutes


def get_allow_list() -> str:
    """Get allow list from SSM with caching.

    Retrieves the phone number allow list from SSM Parameter Store with
    5-minute caching to avoid repeated API calls. The parameter should
    contain comma-separated phone numbers or '*' for wildcard access.

    Returns:
        Allow list string from SSM parameter, empty string if not found or error
    """
    current_time = time.time()

    # Return cached value if still valid
    if _allow_list_cache["value"] is not None and current_time - _allow_list_cache["timestamp"] < _cache_ttl:
        logger.debug("Returning cached allow list")
        return _allow_list_cache["value"]

    try:
        ssm = boto3.client("ssm")
        parameter_name = os.environ.get("WHATSAPP_ALLOW_LIST_PARAMETER", "/virtual-assistant/whatsapp/allow-list")

        logger.debug(f"Retrieving allow list from SSM parameter: {parameter_name}")
        response = ssm.get_parameter(Name=parameter_name)

        allow_list_value = response["Parameter"]["Value"]

        # Update cache
        _allow_list_cache["value"] = allow_list_value
        _allow_list_cache["timestamp"] = current_time

        logger.debug(f"Successfully retrieved allow list from SSM (length: {len(allow_list_value)})")
        return allow_list_value

    except Exception as e:
        logger.error(f"Failed to retrieve allow list from SSM: {e}")
        # Don't cache errors, return empty string for security
        return ""


def is_phone_allowed(phone_number: str) -> bool:
    """Check if phone number is allowed based on SSM allow list.

    Validates a phone number against the allow list stored in SSM Parameter Store.
    Supports:
    - Wildcard '*' to allow all phone numbers
    - Comma-separated list of specific phone numbers
    - Returns False if allow list is empty or missing (secure by default)

    Args:
        phone_number: Phone number to validate (e.g., "+1234567890")

    Returns:
        True if phone number is allowed, False otherwise
    """
    if not phone_number:
        logger.debug("Empty phone number provided")
        return False

    allow_list = get_allow_list()
    if not allow_list:
        logger.info("Allow list is empty or missing, rejecting phone number for security")
        return False

    # Check for wildcard access
    if "*" in allow_list:
        logger.debug("Wildcard found in allow list, allowing phone number")
        return True

    # Parse comma-separated phone numbers
    allowed_numbers = [num.strip() for num in allow_list.split(",") if num.strip()]
    logger.debug(f"Allow list contains {len(allowed_numbers)} phone numbers")

    # Check if phone number is in the allowed list
    is_allowed = phone_number in allowed_numbers

    if is_allowed:
        logger.debug("Phone number found in allow list")
    else:
        logger.debug("Phone number not found in allow list")

    return is_allowed


def clear_allow_list_cache() -> None:
    """Clear the allow list cache.

    Useful for testing or when you want to force a fresh retrieval
    from SSM Parameter Store.
    """
    global _allow_list_cache
    _allow_list_cache = {"value": None, "timestamp": 0}
    logger.debug("Allow list cache cleared")
