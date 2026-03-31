# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for Hotel PMS input validation via AgentCore Gateway.

This test suite validates input validation error handling:
- Type validation (float vs integer)
- Date validation (past dates, invalid formats)
- Enum validation
- Required field validation
- Multiple validation errors

Note: With the response interceptor enabled, all HTTP responses return status code 200.
Error information is preserved in the response body with error=True and error_code fields.

Prerequisites:
- HotelPmsStack deployed with AgentCore Gateway and response interceptor
- AWS credentials configured

Usage:
    pytest tests/post_deploy/test_input_validation.py -v -s -m integration
"""

import logging
from datetime import date, timedelta

import boto3
import pytest

from .mcp_gateway_utils import (
    call_mcp_tool_via_gateway,
    fetch_access_token,
    parse_mcp_result,
)

# Disable verbose logging from httpx and mcp libraries
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("mcp").setLevel(logging.WARNING)


@pytest.fixture(scope="module")
def stack_outputs():
    """Get stack outputs from HotelPmsStack."""
    cloudformation = boto3.client("cloudformation")

    try:
        response = cloudformation.describe_stacks(StackName="HotelPmsStack")
        stack = response["Stacks"][0]
        outputs = {
            output["OutputKey"]: output["OutputValue"]
            for output in stack.get("Outputs", [])
        }

        # Verify required outputs
        required_outputs = ["CognitoClientId", "GatewayId", "CognitoUserPoolId"]
        missing = [key for key in required_outputs if key not in outputs]
        if missing:
            pytest.fail(f"Missing required stack outputs: {missing}")

        return outputs

    except Exception as e:
        pytest.fail(f"Failed to get HotelPmsStack outputs: {e}")


@pytest.fixture(scope="module")
def gateway_config(stack_outputs):
    """Prepare AgentCore Gateway configuration."""
    client_id = stack_outputs["CognitoClientId"]
    gateway_id = stack_outputs["GatewayId"]
    user_pool_id = stack_outputs["CognitoUserPoolId"]

    region = user_pool_id.split("_")[0]
    gateway_url = (
        f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"
    )

    # Get client secret from Cognito
    cognito_client = boto3.client("cognito-idp")
    client_response = cognito_client.describe_user_pool_client(
        UserPoolId=user_pool_id,
        ClientId=client_id,
    )
    client_secret = client_response["UserPoolClient"].get("ClientSecret")

    if not client_secret:
        pytest.fail("Cognito User Pool Client does not have a secret")

    # Get Cognito domain for token URL
    user_pool_response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
    domain = user_pool_response["UserPool"].get("Domain")

    if not domain:
        pytest.fail("Cognito User Pool does not have a domain configured")

    token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"

    return {
        "gateway_url": gateway_url,
        "client_id": client_id,
        "client_secret": client_secret,
        "token_url": token_url,
    }


@pytest.fixture(scope="module")
def access_token(gateway_config):
    """Fetch OAuth2 access token for the test session."""
    token = fetch_access_token(
        gateway_config["client_id"],
        gateway_config["client_secret"],
        gateway_config["token_url"],
    )
    print("✅ Access token obtained")
    return token


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_coercible_float_guests(gateway_config, access_token):
    """Test that float values like 3.0 are coerced to integers successfully.

    With response interceptor: All responses return 200 status code.
    Success is indicated by presence of quote_id in response body.

    Property 1: Type validation errors are reported with field details
    Validates: Requirements 1.1, 4.1, 6.1, 6.3
    """
    gateway_url = gateway_config["gateway_url"]

    # Use dynamic date computation
    check_in_date = date.today() + timedelta(days=30)
    check_out_date = date.today() + timedelta(days=32)

    print("\n🧪 Testing coercible float guests (3.0 -> 3)...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": check_in_date.isoformat(),
            "check_out_date": check_out_date.isoformat(),
            "guests": 3.0,  # Should be coerced to 3
            "package_type": "simple",
        },
    )

    data = parse_mcp_result(result)

    # Should succeed - Pydantic coerces 3.0 to 3
    # Response interceptor returns 200, success indicated by quote_id in body
    assert "quote_id" in data, (
        "Expected successful quote generation with coercible float"
    )
    assert "total_price" in data or "total_cost" in data, "Expected price in response"

    print(f"✅ Coercible float accepted: quote_id={data.get('quote_id')}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_invalid_float_guests(gateway_config, access_token):
    """Test that non-integer float values like 3.5 are rejected with validation error.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Property 1: Type validation errors are reported with field details
    Validates: Requirements 1.1, 4.1, 6.1, 6.2
    """
    gateway_url = gateway_config["gateway_url"]

    # Use dynamic date computation
    check_in_date = date.today() + timedelta(days=30)
    check_out_date = date.today() + timedelta(days=32)

    print("\n🧪 Testing invalid float guests (3.5)...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": check_in_date.isoformat(),
            "check_out_date": check_out_date.isoformat(),
            "guests": 3.5,  # Invalid - non-integer float
            "package_type": "simple",
        },
    )

    data = parse_mcp_result(result)

    # Should fail with validation error
    # Response interceptor returns 200, but error details are in body
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )
    assert "details" in data, "Expected details array in error response"

    # Verify field-level error details
    guest_error = next((e for e in data["details"] if e["field"] == "guests"), None)
    assert guest_error is not None, "Expected error for 'guests' field"
    assert (
        "integer" in guest_error["message"].lower()
        or "int" in guest_error["message"].lower()
    ), "Expected error message to mention integer requirement"

    print(f"✅ Invalid float rejected: {guest_error['message']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_past_dates(gateway_config, access_token):
    """Test that past dates are rejected with clear error messages.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Property 2: Past dates are rejected with clear error messages
    Validates: Requirements 1.2, 5.1, 4.2, 6.1, 6.2
    """
    gateway_url = gateway_config["gateway_url"]

    print("\n🧪 Testing past dates...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": "2025-01-08",  # Past date
            "check_out_date": "2025-01-15",  # Past date
            "guests": 3,
            "package_type": "simple",
        },
    )

    data = parse_mcp_result(result)

    # Should fail with validation error
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )

    # Verify date validation error
    date_error = next(
        (e for e in data.get("details", []) if "check_in_date" in e["field"]), None
    )
    assert date_error is not None, "Expected error for check_in_date field"
    assert (
        "future" in date_error["message"].lower()
        or "today" in date_error["message"].lower()
    ), "Expected error message to explain date must be in future"

    print(f"✅ Past date rejected: {date_error['message']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_multiple_errors(gateway_config, access_token):
    """Test that validation errors are properly captured and reported.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Note: AgentCore Gateway performs OpenAPI schema validation first, which may
    stop at the first error. This test verifies that at least one validation error
    is properly reported with the correct structure.

    Property 8: All validation errors are captured
    Validates: Requirements 3.2, 7.4, 4.3, 6.1, 6.2, 6.4
    """
    gateway_url = gateway_config["gateway_url"]

    # Use dynamic date computation for past date
    past_date = date.today() - timedelta(days=7)

    print("\n🧪 Testing multiple validation errors...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": past_date.isoformat(),  # Past date (error 1)
            "check_out_date": (past_date + timedelta(days=2)).isoformat(),  # Also past
            "guests": 3.5,  # Invalid float (error 2)
            "package_type": "invalid",  # Invalid enum (error 3)
        },
    )

    data = parse_mcp_result(result)

    # Gateway validation errors are wrapped in {"message": "..."}
    # Check if this is a wrapped error message
    if "message" in data and "OpenAPIClientException" in data.get("message", ""):
        print("\n✅ Gateway validation error detected (wrapped in message)")
        # Gateway stops at first error, so we just verify an error was caught
        assert "validation failed" in data["message"].lower(), (
            "Expected validation error message"
        )
        print(f"✅ Validation error caught by Gateway: {data['message'][:100]}...")
        return

    # Otherwise, expect structured error response from backend
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )
    assert "details" in data, "Expected details array in error response"

    # Verify at least one error is captured with proper structure
    assert len(data["details"]) >= 1, (
        f"Expected at least 1 error, got {len(data['details'])}"
    )

    # Verify each error has required fields
    for error in data["details"]:
        assert "field" in error, "Each error should have 'field'"
        assert "message" in error, "Each error should have 'message'"
        assert "type" in error, "Each error should have 'type'"
        assert "input" in error, "Each error should have 'input'"

    print(f"✅ Validation errors captured: {len(data['details'])} error(s)")
    for error in data["details"]:
        print(f"   - {error['field']}: {error['message']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_missing_fields(gateway_config, access_token):
    """Test that missing required fields are all reported.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Property 3: Missing required fields are all reported
    Validates: Requirements 1.3, 4.4, 6.1, 6.2
    """
    gateway_url = gateway_config["gateway_url"]

    print("\n🧪 Testing missing required fields...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            # Missing: room_type_id, check_in_date, check_out_date, guests
        },
    )

    data = parse_mcp_result(result)

    # Gateway validation errors are wrapped in {"message": "..."}
    # Check if this is a wrapped error message
    if "message" in data and "OpenAPIClientException" in data.get("message", ""):
        print("\n✅ Gateway validation error detected (wrapped in message)")
        # Verify all required fields are mentioned in the error message
        required_fields = {"room_type_id", "check_in_date", "check_out_date", "guests"}
        for field in required_fields:
            assert field in data["message"], (
                f"Expected '{field}' mentioned in error message"
            )
        print(
            f"✅ All missing fields reported by Gateway: {', '.join(required_fields)}"
        )
        return

    # Otherwise, expect structured error response from backend
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )
    assert "details" in data, "Expected details array in error response"

    # Verify all missing fields are reported
    error_fields = {e["field"] for e in data["details"]}

    # Check for required fields
    required_fields = {"room_type_id", "check_in_date", "check_out_date", "guests"}
    missing_in_errors = required_fields - error_fields

    assert len(missing_in_errors) == 0, (
        f"Expected errors for all missing required fields, but missing: {missing_in_errors}"
    )

    print(f"✅ All missing fields reported: {len(data['details'])} errors")
    for error in data["details"]:
        print(f"   - {error['field']}: {error['message']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_invalid_enum(gateway_config, access_token):
    """Test that invalid enum values include list of valid options.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Property 4: Invalid enum values include valid options
    Validates: Requirements 1.4, 4.5, 6.1, 6.2
    """
    gateway_url = gateway_config["gateway_url"]

    # Use dynamic date computation
    check_in_date = date.today() + timedelta(days=30)
    check_out_date = date.today() + timedelta(days=32)

    print("\n🧪 Testing invalid enum value...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": check_in_date.isoformat(),
            "check_out_date": check_out_date.isoformat(),
            "guests": 3,
            "package_type": "invalid",  # Invalid enum value
        },
    )

    data = parse_mcp_result(result)

    # Gateway validation errors are wrapped in {"message": "..."}
    # Check if this is a wrapped error message
    if "message" in data and "OpenAPIClientException" in data.get("message", ""):
        print("\n✅ Gateway validation error detected (wrapped in message)")
        # This is expected - Gateway caught the invalid enum before sending to backend
        assert "package_type" in data["message"], (
            "Expected package_type mentioned in error message"
        )
        assert "enum" in data["message"], "Expected enum validation error"
        print(f"✅ Invalid enum rejected by Gateway: {data['message'][:100]}...")
        return

    # Otherwise, expect structured error response from backend
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )

    # Verify enum error includes valid options
    enum_error = next(
        (e for e in data.get("details", []) if e["field"] == "package_type"), None
    )
    assert enum_error is not None, "Expected error for 'package_type' field"

    # Check that error message mentions valid options
    error_msg = enum_error["message"].lower()
    assert "simple" in error_msg or "detailed" in error_msg, (
        "Expected error message to include valid enum options ('simple', 'detailed')"
    )

    print(f"✅ Invalid enum rejected: {enum_error['message']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_invalid_date_order(gateway_config, access_token):
    """Test that check_out_date before check_in_date is rejected.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Property 11: Check-out date must be after check-in date
    Validates: Requirements 5.2, 6.1, 6.2
    """
    gateway_url = gateway_config["gateway_url"]

    # Use dynamic date computation
    check_in_date = date.today() + timedelta(days=30)
    check_out_date = date.today() + timedelta(days=28)  # Before check-in

    print("\n🧪 Testing invalid date order (check_out before check_in)...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": check_in_date.isoformat(),
            "check_out_date": check_out_date.isoformat(),  # Before check_in_date
            "guests": 3,
            "package_type": "simple",
        },
    )

    data = parse_mcp_result(result)

    # Should fail with validation error
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )

    # Verify date ordering error
    date_error = next(
        (e for e in data.get("details", []) if "check_out_date" in e["field"]), None
    )
    assert date_error is not None, "Expected error for 'check_out_date' field"
    assert (
        "after" in date_error["message"].lower()
        or "before" in date_error["message"].lower()
    ), "Expected error message to explain date ordering constraint"

    print(f"✅ Invalid date order rejected: {date_error['message']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_invalid_date_format(gateway_config, access_token):
    """Test that dates in wrong format are rejected.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Property 14: Wrong date formats are rejected
    Validates: Requirements 5.5, 6.1, 6.2
    """
    gateway_url = gateway_config["gateway_url"]

    print("\n🧪 Testing invalid date format (MM/DD/YYYY)...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": "01/15/2026",  # Wrong format (should be YYYY-MM-DD)
            "check_out_date": "01/17/2026",  # Wrong format
            "guests": 3,
            "package_type": "simple",
        },
    )

    data = parse_mcp_result(result)

    # Should fail with validation error
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )

    # Verify date format error
    date_error = next(
        (
            e
            for e in data.get("details", [])
            if "check_in_date" in e["field"] or "check_out_date" in e["field"]
        ),
        None,
    )
    assert date_error is not None, "Expected error for date field"

    # Check that error mentions format or parsing issue
    error_msg = date_error["message"].lower()
    assert any(
        keyword in error_msg for keyword in ["format", "invalid", "parse", "date"]
    ), "Expected error message to indicate date format issue"

    print(f"✅ Invalid date format rejected: {date_error['message']}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_generate_quote_with_invalid_date_value(gateway_config, access_token):
    """Test that invalid date values like 2025-02-30 are rejected.

    With response interceptor: All responses return 200 status code.
    Errors are indicated by error=True and error_code in response body.

    Property 13: Invalid date strings are rejected
    Validates: Requirements 5.4, 6.1, 6.2
    """
    gateway_url = gateway_config["gateway_url"]

    print("\n🧪 Testing invalid date value (2025-02-30)...")
    result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": "H-PTL-003",
            "room_type_id": "JVIL-PTL",
            "check_in_date": "2025-02-30",  # Invalid date (February doesn't have 30 days)
            "check_out_date": "2025-03-02",
            "guests": 3,
            "package_type": "simple",
        },
    )

    data = parse_mcp_result(result)

    # Should fail with validation error
    assert data.get("error") is True, "Expected error=true in response"
    assert data.get("error_code") == "VALIDATION_ERROR", (
        "Expected VALIDATION_ERROR error code"
    )

    # Verify invalid date error
    date_error = next(
        (e for e in data.get("details", []) if "check_in_date" in e["field"]), None
    )
    assert date_error is not None, "Expected error for 'check_in_date' field"

    # Check that error indicates invalid date
    error_msg = date_error["message"].lower()
    assert any(keyword in error_msg for keyword in ["invalid", "date", "parse"]), (
        "Expected error message to indicate invalid date"
    )

    print(f"✅ Invalid date value rejected: {date_error['message']}")
