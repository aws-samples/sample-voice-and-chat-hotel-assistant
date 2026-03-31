# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Common validation utilities."""

import re
from datetime import date


def validate_email(email: str) -> bool:
    """Validate email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9-]+(?:\.[a-zA-Z0-9-]+)*\.[a-zA-Z]{2,}$"
    # Check for consecutive dots which are invalid
    if ".." in email:
        return False
    return bool(re.match(pattern, email))


def validate_phone(phone: str) -> bool:
    """Validate phone number format (basic validation)."""
    # Remove common separators
    cleaned = re.sub(r"[\s\-\(\)\+]", "", phone)
    # Check if it's all digits and reasonable length
    return cleaned.isdigit() and 10 <= len(cleaned) <= 15


def validate_date_range(check_in: date, check_out: date) -> bool:
    """Validate that check-out is after check-in."""
    return check_out > check_in


def validate_future_date(target_date: date) -> bool:
    """Validate that date is in the future."""
    return target_date >= date.today()


def sanitize_string(value: str | None, max_length: int = 255) -> str | None:
    """Sanitize and truncate string input."""
    if not value:
        return None

    # Strip whitespace and truncate
    sanitized = value.strip()[:max_length]
    return sanitized if sanitized else None
