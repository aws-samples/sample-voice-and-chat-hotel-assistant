# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""End-to-end integration tests for Hotel PMS MCP server via AgentCore Gateway.

This test suite validates the complete reservation workflow:
1. List hotels and choose one
2. Check availability for dates and guests
3. Generate a quote for an available room
4. Create a reservation with the quote_id
5. Get reservation by guest email
6. Get reservation by reservation_id
7. Update the reservation
8. Checkout the guest
9. Create a housekeeping request

Note: With the response interceptor enabled, all HTTP responses return status code 200.
Success is indicated by the presence of expected data fields in the response body.
Errors are indicated by error=True and error_code fields in the response body.

Prerequisites:
- HotelPmsStack deployed with AgentCore Gateway and response interceptor
- AWS credentials configured
- DynamoDB tables populated with hotel data

Usage:
    pytest tests/post_deploy/test_mcp_e2e_reservation_flow.py -v -s -m integration
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


@pytest.fixture(scope="module")
def dynamodb_tables(stack_outputs):
    """Get DynamoDB table references."""
    cloudformation = boto3.client("cloudformation")
    response = cloudformation.describe_stacks(StackName="HotelPmsStack")
    stack = response["Stacks"][0]
    outputs = {
        output["OutputKey"]: output["OutputValue"]
        for output in stack.get("Outputs", [])
    }

    dynamodb = boto3.resource("dynamodb")

    return {
        "quotes": dynamodb.Table(outputs["QuotesTableName"]),
        "reservations": dynamodb.Table(outputs["ReservationsTableName"]),
        "requests": dynamodb.Table(outputs["RequestsTableName"]),
    }


@pytest.fixture(scope="module")
def test_data():
    """Shared test data for cleanup tracking."""
    return {
        "quote_ids": [],
        "reservation_ids": [],
        "request_ids": [],
    }


@pytest.mark.integration
@pytest.mark.asyncio
async def test_e2e_reservation_workflow(
    gateway_config, access_token, dynamodb_tables, test_data
):
    """Test complete end-to-end reservation workflow via AgentCore Gateway.

    This test validates the entire guest journey from hotel selection through checkout.

    With response interceptor: All HTTP responses return status code 200.
    Success is indicated by the presence of expected data fields in response body.
    Validates: Requirements 6.1, 6.2, 6.3, 6.4, 6.5
    """
    gateway_url = gateway_config["gateway_url"]

    # Step 1: List hotels and choose one
    print("\n📋 Step 1: Listing hotels...")
    hotels_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___get_hotels",
        arguments={},
    )

    hotels_data = parse_mcp_result(hotels_result)
    assert "hotels" in hotels_data
    assert len(hotels_data["hotels"]) > 0

    # Choose first hotel
    hotel = hotels_data["hotels"][0]
    hotel_id = hotel["hotel_id"]
    hotel_name = hotel["name"]

    print(f"✅ Found {len(hotels_data['hotels'])} hotels")
    print(f"   Selected: {hotel_name} (ID: {hotel_id})")

    # Step 2: Check availability
    print("\n🔍 Step 2: Checking availability...")
    future_date = date.today() + timedelta(days=30)
    checkout_date = future_date + timedelta(days=2)

    availability_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___check_availability",
        arguments={
            "hotel_id": hotel_id,
            "check_in_date": future_date.isoformat(),
            "check_out_date": checkout_date.isoformat(),
            "guests": 2,
            "package_type": "simple",
        },
    )

    availability_data = parse_mcp_result(availability_result)
    assert "available_room_types" in availability_data
    assert len(availability_data["available_room_types"]) > 0

    # Choose first available room type
    room_type = availability_data["available_room_types"][0]
    room_type_id = room_type["room_type_id"]
    available_rooms = room_type["available_rooms"]

    print(f"✅ Found {len(availability_data['available_room_types'])} room types")
    print(f"   Selected: {room_type_id} ({available_rooms} available)")

    # Step 3: Generate quote
    print("\n💰 Step 3: Generating quote...")
    quote_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___generate_quote",
        arguments={
            "hotel_id": hotel_id,
            "room_type_id": room_type_id,
            "check_in_date": future_date.isoformat(),
            "check_out_date": checkout_date.isoformat(),
            "guests": 2,
            "package_type": "detailed",
        },
    )

    quote_data = parse_mcp_result(quote_result)
    assert "quote_id" in quote_data
    assert "total_cost" in quote_data
    assert "expires_at" in quote_data

    quote_id = quote_data["quote_id"]
    total_cost = quote_data["total_cost"]
    test_data["quote_ids"].append(quote_id)

    print(f"✅ Quote generated: {quote_id}")
    print(f"   Total cost: ${total_cost}")
    print(f"   Expires at: {quote_data['expires_at']}")

    # Verify quote in DynamoDB
    db_quote = dynamodb_tables["quotes"].get_item(Key={"quote_id": quote_id})
    assert "Item" in db_quote
    assert db_quote["Item"]["hotel_id"] == hotel_id
    print("   ✓ Quote verified in DynamoDB")

    # Step 4: Create reservation
    print("\n📝 Step 4: Creating reservation...")
    guest_email = f"e2e-test-{quote_id}@example.com"

    reservation_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___create_reservation",
        arguments={
            "quote_id": quote_id,
            "guest_name": "E2E Test Guest",
            "guest_email": guest_email,
            "guest_phone": "+1-555-999-0001",
        },
    )

    reservation_data = parse_mcp_result(reservation_result)
    assert "reservation_id" in reservation_data
    assert reservation_data["status"] == "confirmed"
    assert reservation_data["guest_email"] == guest_email

    reservation_id = reservation_data["reservation_id"]
    test_data["reservation_ids"].append(reservation_id)

    print(f"✅ Reservation created: {reservation_id}")
    print(f"   Status: {reservation_data['status']}")
    print(f"   Guest: {reservation_data['guest_name']}")

    # Verify reservation in DynamoDB
    db_reservation = dynamodb_tables["reservations"].get_item(
        Key={"reservation_id": reservation_id}
    )
    assert "Item" in db_reservation
    assert db_reservation["Item"]["guest_email"] == guest_email
    print("   ✓ Reservation verified in DynamoDB")

    # Step 5: Get reservation by guest email
    print("\n🔎 Step 5: Getting reservation by guest email...")
    get_by_email_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___get_reservations",
        arguments={
            "guest_email": guest_email,
            "limit": 10,
        },
    )

    email_search_data = parse_mcp_result(get_by_email_result)
    assert "reservations" in email_search_data
    assert len(email_search_data["reservations"]) > 0

    found_reservation = next(
        (
            r
            for r in email_search_data["reservations"]
            if r["reservation_id"] == reservation_id
        ),
        None,
    )
    assert found_reservation is not None
    assert found_reservation["guest_email"] == guest_email

    print("✅ Found reservation by email")
    print(
        f"   Reservations for {guest_email}: {len(email_search_data['reservations'])}"
    )

    # Step 6: Get reservation by reservation_id
    print("\n🔎 Step 6: Getting reservation by ID...")
    get_by_id_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___get_reservation",
        arguments={
            "reservation_id": reservation_id,
        },
    )

    id_search_data = parse_mcp_result(get_by_id_result)
    assert id_search_data["reservation_id"] == reservation_id
    assert id_search_data["guest_email"] == guest_email
    assert id_search_data["status"] == "confirmed"

    print("✅ Retrieved reservation by ID")
    print(f"   Status: {id_search_data['status']}")

    # Step 7: Update reservation
    print("\n✏️  Step 7: Updating reservation...")
    updated_phone = "+1-555-999-0002"

    update_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___update_reservation",
        arguments={
            "reservation_id": reservation_id,
            "guest_phone": updated_phone,
            "status": "checked_in",
        },
    )

    update_data = parse_mcp_result(update_result)
    assert update_data["reservation_id"] == reservation_id
    assert update_data["guest_phone"] == updated_phone
    assert update_data["status"] == "checked_in"

    print("✅ Reservation updated")
    print(f"   New status: {update_data['status']}")
    print(f"   New phone: {update_data['guest_phone']}")

    # Verify update in DynamoDB
    db_updated = dynamodb_tables["reservations"].get_item(
        Key={"reservation_id": reservation_id}
    )
    assert db_updated["Item"]["status"] == "checked_in"
    assert db_updated["Item"]["guest_phone"] == updated_phone
    print("   ✓ Update verified in DynamoDB")

    # Step 8: Checkout
    print("\n🚪 Step 8: Checking out guest...")
    checkout_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___checkout_guest",
        arguments={
            "reservation_id": reservation_id,
            "additional_charges": 75.50,
            "payment_method": "card",
        },
    )

    checkout_data = parse_mcp_result(checkout_result)
    assert checkout_data["reservation_id"] == reservation_id
    assert checkout_data["status"] == "checked_out"
    assert "checkout_time" in checkout_data

    print("✅ Guest checked out")
    print(f"   Checkout time: {checkout_data['checkout_time']}")

    # Verify checkout in DynamoDB
    db_checkout = dynamodb_tables["reservations"].get_item(
        Key={"reservation_id": reservation_id}
    )
    assert db_checkout["Item"]["status"] == "checked_out"
    print("   ✓ Checkout verified in DynamoDB")

    # Step 9: Create housekeeping request
    print("\n🧹 Step 9: Creating housekeeping request...")
    housekeeping_result = await call_mcp_tool_via_gateway(
        gateway_url=gateway_url,
        access_token=access_token,
        tool_name="HotelPMS___create_housekeeping_request",
        arguments={
            "hotel_id": hotel_id,
            "room_number": "101",
            "guest_name": "E2E Test Guest",
            "request_type": "cleaning",
            "description": "E2E test - please clean the room",
        },
    )

    housekeeping_data = parse_mcp_result(housekeeping_result)
    assert "request_id" in housekeeping_data
    assert housekeeping_data["status"] == "pending"
    assert housekeeping_data["request_type"] == "cleaning"

    request_id = housekeeping_data["request_id"]
    test_data["request_ids"].append(request_id)

    print(f"✅ Housekeeping request created: {request_id}")
    print(f"   Type: {housekeeping_data['request_type']}")
    print(f"   Status: {housekeeping_data['status']}")

    # Verify request in DynamoDB
    db_request = dynamodb_tables["requests"].get_item(Key={"request_id": request_id})
    assert "Item" in db_request
    assert db_request["Item"]["hotel_id"] == hotel_id
    print("   ✓ Request verified in DynamoDB")

    print("\n🎉 All steps completed successfully!")


@pytest.fixture(scope="module", autouse=True)
def cleanup(test_data, dynamodb_tables):
    """Cleanup test data after all tests complete."""
    yield

    print("\n🧹 Cleaning up test data...")

    # Delete quotes
    for quote_id in test_data["quote_ids"]:
        try:
            dynamodb_tables["quotes"].delete_item(Key={"quote_id": quote_id})
            print(f"   ✓ Deleted quote: {quote_id}")
        except Exception as e:
            print(f"   ⚠ Failed to delete quote {quote_id}: {e}")

    # Delete reservations
    for reservation_id in test_data["reservation_ids"]:
        try:
            dynamodb_tables["reservations"].delete_item(
                Key={"reservation_id": reservation_id}
            )
            print(f"   ✓ Deleted reservation: {reservation_id}")
        except Exception as e:
            print(f"   ⚠ Failed to delete reservation {reservation_id}: {e}")

    # Delete requests
    for request_id in test_data["request_ids"]:
        try:
            dynamodb_tables["requests"].delete_item(Key={"request_id": request_id})
            print(f"   ✓ Deleted request: {request_id}")
        except Exception as e:
            print(f"   ⚠ Failed to delete request {request_id}: {e}")

    print("✅ Cleanup complete")
