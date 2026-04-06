# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Validation error formatting utilities for Pydantic validation errors."""

from typing import Any

from pydantic import ValidationError


def format_validation_error(error: ValidationError) -> dict[str, Any]:
    """Format Pydantic validation error into API error response.

    Converts Pydantic ValidationError into a structured error response that follows
    the standard error format with field-level details. This ensures consistent
    error responses across all API operations.

    Args:
        error: Pydantic ValidationError containing one or more validation failures

    Returns:
        Structured error response dictionary with the following structure:
        {
            'error': True,
            'error_code': 'VALIDATION_ERROR',
            'message': 'Request validation failed',
            'details': [
                {
                    'field': 'field.path',
                    'message': 'Human-readable error message',
                    'type': 'error_type',
                    'input': <the invalid input value>
                },
                ...
            ]
        }

    Example:
        >>> from pydantic import BaseModel, ValidationError
        >>> class Model(BaseModel):
        ...     age: int
        >>> try:
        ...     Model(age="not a number")
        ... except ValidationError as e:
        ...     result = format_validation_error(e)
        >>> result['error']
        True
        >>> result['error_code']
        'VALIDATION_ERROR'
        >>> len(result['details'])
        1
    """
    errors = []
    for err in error.errors():
        # Build field path from location tuple (e.g., ('guests',) -> 'guests')
        field_path = ".".join(str(loc) for loc in err["loc"])

        errors.append(
            {
                "field": field_path,
                "message": err["msg"],
                "type": err["type"],
                "input": err.get("input"),
            }
        )

    return {
        "error": True,
        "error_code": "VALIDATION_ERROR",
        "message": "Request validation failed",
        "details": errors,
    }
