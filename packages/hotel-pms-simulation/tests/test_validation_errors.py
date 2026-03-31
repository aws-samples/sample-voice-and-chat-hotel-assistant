# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for validation error formatting utilities."""

from datetime import date

import pytest
from pydantic import BaseModel, Field, ValidationError

from hotel_pms_simulation.utils.validation_errors import format_validation_error


class SimpleModel(BaseModel):
    """Simple test model for validation testing."""

    name: str
    age: int = Field(..., ge=0, le=120)


class ComplexModel(BaseModel):
    """Complex test model with multiple fields and constraints."""

    hotel_id: str
    room_type_id: str
    check_in_date: date
    check_out_date: date
    guests: int = Field(..., ge=1, le=10)
    package_type: str = Field(..., pattern="^(simple|detailed)$")


def test_format_single_validation_error():
    """Test formatting a single validation error."""
    # Create a validation error with invalid type
    try:
        SimpleModel(name="John", age="not a number")
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Verify error response structure
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert result["message"] == "Request validation failed"
        assert "details" in result
        assert isinstance(result["details"], list)
        assert len(result["details"]) == 1

        # Verify field-level error details
        error_detail = result["details"][0]
        assert error_detail["field"] == "age"
        assert (
            "int" in error_detail["message"].lower()
            or "integer" in error_detail["message"].lower()
        )
        assert error_detail["type"] == "int_parsing"
        assert error_detail["input"] == "not a number"


def test_format_multiple_validation_errors():
    """Test formatting multiple validation errors in a single request."""
    # Create multiple validation errors
    try:
        ComplexModel(
            hotel_id="H-PTL-003",
            room_type_id="JVIL-PTL",
            check_in_date="invalid-date",
            check_out_date="2025-03-17",
            guests=15,  # Exceeds maximum
            package_type="invalid",  # Invalid enum value
        )
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Verify error response structure
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert result["message"] == "Request validation failed"
        assert "details" in result
        assert isinstance(result["details"], list)
        assert len(result["details"]) >= 3  # At least 3 errors

        # Verify all errors are captured
        error_fields = {detail["field"] for detail in result["details"]}
        assert "check_in_date" in error_fields
        assert "guests" in error_fields
        assert "package_type" in error_fields


def test_preserve_field_names():
    """Test that field names are preserved correctly in error details."""
    try:
        ComplexModel(
            hotel_id="H-PTL-003",
            room_type_id="JVIL-PTL",
            check_in_date="2025-03-15",
            check_out_date="2025-03-17",
            guests=3.5,  # Float instead of int
            package_type="simple",
        )
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Find the guests error
        guests_error = next(
            (detail for detail in result["details"] if detail["field"] == "guests"),
            None,
        )

        assert guests_error is not None
        assert guests_error["field"] == "guests"
        assert guests_error["input"] == 3.5


def test_preserve_input_values():
    """Test that invalid input values are preserved in error details."""
    invalid_inputs = {
        "hotel_id": "H-PTL-003",
        "room_type_id": "JVIL-PTL",
        "check_in_date": "2025-03-15",
        "check_out_date": "2025-03-17",
        "guests": "three",  # String instead of int
        "package_type": "premium",  # Invalid enum
    }

    try:
        ComplexModel(**invalid_inputs)
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Verify input values are preserved
        for detail in result["details"]:
            field = detail["field"]
            if field in invalid_inputs:
                # Input value should be preserved
                assert "input" in detail
                # For some errors, input might be the original value
                assert detail["input"] is not None


def test_error_response_structure():
    """Test that error response follows the standard structure."""
    try:
        SimpleModel(name=123, age="invalid")  # Both fields invalid
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Verify top-level structure
        assert isinstance(result, dict)
        assert "error" in result
        assert "error_code" in result
        assert "message" in result
        assert "details" in result

        # Verify types
        assert isinstance(result["error"], bool)
        assert isinstance(result["error_code"], str)
        assert isinstance(result["message"], str)
        assert isinstance(result["details"], list)

        # Verify each detail has required fields
        for detail in result["details"]:
            assert "field" in detail
            assert "message" in detail
            assert "type" in detail
            assert "input" in detail

            assert isinstance(detail["field"], str)
            assert isinstance(detail["message"], str)
            assert isinstance(detail["type"], str)


def test_missing_required_field():
    """Test error formatting for missing required fields."""
    try:
        SimpleModel(name="John")  # Missing required 'age' field
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Verify error is captured
        assert len(result["details"]) == 1
        error_detail = result["details"][0]

        assert error_detail["field"] == "age"
        assert (
            "required" in error_detail["message"].lower()
            or "missing" in error_detail["message"].lower()
        )
        assert error_detail["type"] == "missing"


def test_constraint_violation():
    """Test error formatting for constraint violations."""
    try:
        SimpleModel(name="John", age=150)  # Exceeds maximum age
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Verify constraint error
        assert len(result["details"]) == 1
        error_detail = result["details"][0]

        assert error_detail["field"] == "age"
        assert error_detail["type"] == "less_than_equal"
        assert error_detail["input"] == 150


def test_nested_field_path():
    """Test that nested field paths are formatted correctly."""

    class Address(BaseModel):
        street: str
        city: str

    class Person(BaseModel):
        name: str
        address: Address

    try:
        Person(
            name="John", address={"street": "123 Main St", "city": 123}
        )  # Invalid city type
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Verify nested field path
        error_detail = result["details"][0]
        assert error_detail["field"] == "address.city"
        assert error_detail["input"] == 123


def test_empty_validation_error():
    """Test handling of validation error with no specific errors (edge case)."""
    # This is a theoretical edge case - Pydantic always provides error details
    # But we test the function handles it gracefully
    try:
        SimpleModel(name="", age=-1)  # Empty name and negative age
        pytest.fail("Expected ValidationError")
    except ValidationError as e:
        result = format_validation_error(e)

        # Should still have proper structure even if errors list is populated
        assert result["error"] is True
        assert result["error_code"] == "VALIDATION_ERROR"
        assert result["message"] == "Request validation failed"
        assert isinstance(result["details"], list)
