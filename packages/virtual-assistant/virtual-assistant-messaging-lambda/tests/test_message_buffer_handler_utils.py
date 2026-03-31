# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for message buffer handler utility functions."""

from decimal import Decimal

from virtual_assistant_messaging_lambda.handlers.message_buffer_handler import convert_floats_to_decimal


def test_convert_floats_to_decimal_simple_float():
    """Test converting a simple float value."""
    result = convert_floats_to_decimal(3.14)
    assert isinstance(result, Decimal)
    assert result == Decimal("3.14")


def test_convert_floats_to_decimal_dict_with_floats():
    """Test converting a dictionary containing float values."""
    input_dict = {"temperature": 0.2, "count": 5, "name": "test"}

    result = convert_floats_to_decimal(input_dict)

    assert isinstance(result["temperature"], Decimal)
    assert result["temperature"] == Decimal("0.2")
    assert result["count"] == 5  # int unchanged
    assert result["name"] == "test"  # string unchanged


def test_convert_floats_to_decimal_nested_dict():
    """Test converting nested dictionaries with floats."""
    input_dict = {"outer": {"inner": {"value": 1.5, "flag": True}, "score": 2.7}, "id": "abc"}

    result = convert_floats_to_decimal(input_dict)

    assert isinstance(result["outer"]["inner"]["value"], Decimal)
    assert result["outer"]["inner"]["value"] == Decimal("1.5")
    assert isinstance(result["outer"]["score"], Decimal)
    assert result["outer"]["score"] == Decimal("2.7")
    assert result["outer"]["inner"]["flag"] is True  # bool unchanged
    assert result["id"] == "abc"  # string unchanged


def test_convert_floats_to_decimal_list_with_floats():
    """Test converting a list containing float values."""
    input_list = [1.1, 2.2, 3, "text", True]

    result = convert_floats_to_decimal(input_list)

    assert isinstance(result[0], Decimal)
    assert result[0] == Decimal("1.1")
    assert isinstance(result[1], Decimal)
    assert result[1] == Decimal("2.2")
    assert result[2] == 3  # int unchanged
    assert result[3] == "text"  # string unchanged
    assert result[4] is True  # bool unchanged


def test_convert_floats_to_decimal_dict_with_list():
    """Test converting a dictionary containing lists with floats."""
    input_dict = {"scores": [1.5, 2.5, 3.5], "metadata": {"values": [0.1, 0.2]}}

    result = convert_floats_to_decimal(input_dict)

    assert all(isinstance(x, Decimal) for x in result["scores"])
    assert result["scores"][0] == Decimal("1.5")
    assert all(isinstance(x, Decimal) for x in result["metadata"]["values"])
    assert result["metadata"]["values"][0] == Decimal("0.1")


def test_convert_floats_to_decimal_preserves_none():
    """Test that None values are preserved."""
    input_dict = {"value": None, "nested": {"inner": None}}

    result = convert_floats_to_decimal(input_dict)

    assert result["value"] is None
    assert result["nested"]["inner"] is None


def test_convert_floats_to_decimal_preserves_empty_collections():
    """Test that empty collections are preserved."""
    input_dict = {"empty_list": [], "empty_dict": {}, "nested": {"empty": []}}

    result = convert_floats_to_decimal(input_dict)

    assert result["empty_list"] == []
    assert result["empty_dict"] == {}
    assert result["nested"]["empty"] == []


def test_convert_floats_to_decimal_message_event_structure():
    """Test converting a structure similar to MessageEvent.model_dump()."""
    # Simulate a MessageEvent structure with float temperature
    input_dict = {
        "message_id": "msg-123",
        "sender_id": "user-456",
        "content": "Hello",
        "temperature": 0.2,  # This is the float that needs conversion
        "timestamp": "2026-01-09T18:22:16.124Z",
        "platform": "aws-eum",
        "platform_metadata": {"score": 0.95, "confidence": 0.87},
        "processing": False,
    }

    result = convert_floats_to_decimal(input_dict)

    # Check that temperature is converted
    assert isinstance(result["temperature"], Decimal)
    assert result["temperature"] == Decimal("0.2")

    # Check that nested floats are converted
    assert isinstance(result["platform_metadata"]["score"], Decimal)
    assert result["platform_metadata"]["score"] == Decimal("0.95")
    assert isinstance(result["platform_metadata"]["confidence"], Decimal)
    assert result["platform_metadata"]["confidence"] == Decimal("0.87")

    # Check that other types are preserved
    assert result["message_id"] == "msg-123"
    assert result["processing"] is False


def test_convert_floats_to_decimal_zero_and_negative():
    """Test converting zero and negative float values."""
    input_dict = {"zero": 0.0, "negative": -1.5, "positive": 2.5}

    result = convert_floats_to_decimal(input_dict)

    assert isinstance(result["zero"], Decimal)
    assert result["zero"] == Decimal("0.0")
    assert isinstance(result["negative"], Decimal)
    assert result["negative"] == Decimal("-1.5")
    assert isinstance(result["positive"], Decimal)
    assert result["positive"] == Decimal("2.5")


def test_convert_floats_to_decimal_scientific_notation():
    """Test converting floats in scientific notation."""
    input_dict = {"small": 1e-10, "large": 1e10}

    result = convert_floats_to_decimal(input_dict)

    assert isinstance(result["small"], Decimal)
    assert isinstance(result["large"], Decimal)
    # Verify the values are preserved correctly
    assert float(result["small"]) == 1e-10
    assert float(result["large"]) == 1e10
