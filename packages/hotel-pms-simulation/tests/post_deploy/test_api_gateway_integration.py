# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Integration tests for API Gateway handler with deployed infrastructure.

This test suite validates the complete workflow:
1. Availability check
2. Quote generation with DynamoDB storage
3. Reservation creation using quote_id
4. Quote expiration and TTL functionality
5. Error handling
6. AgentCore Gateway MCP integration

Prerequisites:
- HotelPmsStack deployed with DynamoDB tables
- AWS credentials configured
- COGNITO_CLIENT_SECRET environment variable set for AgentCore Gateway tests

Usage:
    pytest tests/post_deploy/test_api_gateway_integration.py -v -s -m integration
"""

import json
import os
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import boto3
import pytest
import requests

from hotel_pms_simulation.handlers.api_gateway_handler import lambda_handler

from .mcp_gateway_utils import (
    call_mcp_tool_via_gateway,
    fetch_access_token,
    parse_mcp_result,
)


@pytest.fixture(scope="session", autouse=True)
def setup_environment():
    """Set up environment variables before any tests run.

    This fixture runs automatically at session scope to ensure environment
    variables are set before any service classes are instantiated.
    """
    cloudformation = boto3.client("cloudformation")

    try:
        response = cloudformation.describe_stacks(StackName="HotelPmsStack")
        stack = response["Stacks"][0]
        outputs = {
            output["OutputKey"]: output["OutputValue"]
            for output in stack.get("Outputs", [])
        }

        # Set environment variables for DynamoDB tables
        if "HotelsTableName" in outputs:
            os.environ["HOTELS_TABLE_NAME"] = outputs["HotelsTableName"]
        if "RoomTypesTableName" in outputs:
            os.environ["ROOM_TYPES_TABLE_NAME"] = outputs["RoomTypesTableName"]
        if "RateModifiersTableName" in outputs:
            os.environ["RATE_MODIFIERS_TABLE_NAME"] = outputs["RateModifiersTableName"]
        if "ReservationsTableName" in outputs:
            os.environ["RESERVATIONS_TABLE_NAME"] = outputs["ReservationsTableName"]
        if "RequestsTableName" in outputs:
            os.environ["REQUESTS_TABLE_NAME"] = outputs["RequestsTableName"]
        if "QuotesTableName" in outputs:
            os.environ["QUOTES_TABLE_NAME"] = outputs["QuotesTableName"]

        # Verify all required tables are set
        required_tables = [
            "HOTELS_TABLE_NAME",
            "ROOM_TYPES_TABLE_NAME",
            "RATE_MODIFIERS_TABLE_NAME",
            "RESERVATIONS_TABLE_NAME",
            "REQUESTS_TABLE_NAME",
            "QUOTES_TABLE_NAME",
        ]

        missing_tables = [
            table for table in required_tables if not os.environ.get(table)
        ]
        if missing_tables:
            pytest.fail(
                f"Missing required table environment variables: {missing_tables}"
            )

        print("✅ Loaded configuration from HotelPmsStack")
        print(
            f"   Tables: {len([k for k in outputs.keys() if 'TableName' in k])} DynamoDB tables configured"
        )

        # Print table names for debugging
        for table in required_tables:
            print(f"   {table}: {os.environ.get(table)}")

        yield outputs

    except Exception as e:
        pytest.fail(f"Failed to get HotelPmsStack outputs: {e}")


@pytest.fixture(scope="module")
def stack_outputs(setup_environment):
    """Get stack outputs from the session-level setup fixture."""
    return setup_environment


def create_api_gateway_event(
    method: str, path: str, body: dict = None, query_params: dict = None
):
    """Create a mock API Gateway event."""
    event = {
        "httpMethod": method,
        "path": path,
        "headers": {
            "Content-Type": "application/json",
            "Authorization": "Bearer mock-jwt-token",
        },
        "requestContext": {
            "requestId": "test-request-id",
            "stage": "test",
            "accountId": "123456789012",
            "apiId": "test-api-id",
            "authorizer": {
                "claims": {
                    "sub": "test-user-id",
                    "email": "test@example.com",
                    "cognito:username": "testuser",
                }
            },
        },
        "queryStringParameters": query_params,
    }

    if body:
        event["body"] = json.dumps(body)

    return event


def create_lambda_context():
    """Create a mock Lambda context."""
    context = MagicMock()
    context.function_name = "HotelPMSAPIGateway"
    context.function_version = "$LATEST"
    context.invoked_function_arn = (
        "arn:aws:lambda:us-east-1:123456789012:function:HotelPMSAPIGateway"
    )
    context.memory_limit_in_mb = 512
    context.remaining_time_in_millis = lambda: 30000
    context.aws_request_id = "test-request-id"
    context.log_group_name = "/aws/lambda/HotelPMSAPIGateway"
    context.log_stream_name = "2025/01/01/[$LATEST]test-stream"
    return context


@pytest.mark.integration
def test_complete_workflow_availability_quote_reservation(stack_outputs):
    """Test complete workflow: availability -> quote (with DynamoDB) -> reservation.

    This test validates:
    - Availability check returns available room types
    - Quote generation stores quote in DynamoDB with TTL
    - Quote includes quote_id and expires_at
    - Reservation creation uses quote_id successfully
    - All responses are JSON serializable
    - OpenAPI spec compatibility

    Note: This test works with DynamoDB tables only and does not require Aurora database.
    """
    context = create_lambda_context()

    # Step 1: Check availability
    future_date = date.today() + timedelta(days=30)
    checkout_date = future_date + timedelta(days=2)

    availability_event = create_api_gateway_event(
        "POST",
        "/availability/check",
        {
            "hotel_id": "H-PVR-002",
            "check_in_date": future_date.isoformat(),
            "check_out_date": checkout_date.isoformat(),
            "guests": 2,
            "package_type": "simple",
        },
    )

    availability_response = lambda_handler(availability_event, context)
    assert availability_response["statusCode"] == 200

    availability_body = json.loads(availability_response["body"])
    assert "available_room_types" in availability_body
    assert len(availability_body["available_room_types"]) > 0

    # Verify OpenAPI spec compliance for availability
    assert "hotel_id" in availability_body
    assert "check_in_date" in availability_body
    assert "check_out_date" in availability_body
    assert "guests" in availability_body

    # Get first available room type
    room_type = availability_body["available_room_types"][0]
    room_type_id = room_type["room_type_id"]
    assert "available_rooms" in room_type
    assert "base_rate" in room_type

    print(
        f"✅ Step 1: Availability check passed - found {len(availability_body['available_room_types'])} room types"
    )

    # Step 2: Generate quote and verify DynamoDB storage
    quote_event = create_api_gateway_event(
        "POST",
        "/quotes/generate",
        {
            "hotel_id": "H-PVR-002",
            "room_type_id": room_type_id,
            "check_in_date": future_date.isoformat(),
            "check_out_date": checkout_date.isoformat(),
            "guests": 2,
            "package_type": "simple",
        },
    )

    quote_response = lambda_handler(quote_event, context)
    assert quote_response["statusCode"] == 200

    quote_body = json.loads(quote_response["body"])
    assert "quote_id" in quote_body
    assert "total_cost" in quote_body
    assert "expires_at" in quote_body
    assert quote_body["hotel_id"] == "H-PVR-002"
    assert quote_body["room_type_id"] == room_type_id

    # Verify OpenAPI spec compliance for quote
    assert "nights" in quote_body
    assert "base_rate" in quote_body
    assert isinstance(quote_body["nights"], int)
    assert isinstance(quote_body["expires_at"], str)
    datetime.fromisoformat(quote_body["expires_at"])  # Validate ISO format

    quote_id = quote_body["quote_id"]
    total_cost = quote_body["total_cost"]

    # Verify quote is stored in DynamoDB
    dynamodb = boto3.resource("dynamodb")
    quotes_table = dynamodb.Table(os.environ["QUOTES_TABLE_NAME"])
    db_response = quotes_table.get_item(Key={"quote_id": quote_id})

    assert "Item" in db_response
    db_item = db_response["Item"]
    assert db_item["quote_id"] == quote_id
    assert db_item["hotel_id"] == "H-PVR-002"
    assert "expires_at" in db_item
    # DynamoDB returns Decimal for numbers, convert to int for comparison
    assert isinstance(db_item["expires_at"], int | Decimal)
    assert int(db_item["expires_at"]) > int(time.time())  # Should be in the future

    print(
        f"✅ Step 2: Quote generated and stored in DynamoDB - quote_id: {quote_id}, total_cost: {total_cost}"
    )

    # Step 3: Create reservation using quote_id
    reservation_event = create_api_gateway_event(
        "POST",
        "/reservations",
        {
            "quote_id": quote_id,
            "guest_name": "Integration Test User",
            "guest_email": "integration.test@example.com",
            "guest_phone": "+1-555-123-4567",
        },
    )

    reservation_response = lambda_handler(reservation_event, context)
    assert reservation_response["statusCode"] == 200

    reservation_body = json.loads(reservation_response["body"])
    assert "reservation_id" in reservation_body
    assert reservation_body["status"] == "confirmed"
    assert reservation_body["guest_name"] == "Integration Test User"
    assert reservation_body["hotel_id"] == "H-PVR-002"

    reservation_id = reservation_body["reservation_id"]

    print(f"✅ Step 3: Reservation created - reservation_id: {reservation_id}")

    # Step 4: Verify reservation can be retrieved
    get_reservation_event = create_api_gateway_event(
        "GET", f"/reservations/{reservation_id}"
    )

    get_response = lambda_handler(get_reservation_event, context)
    assert get_response["statusCode"] == 200

    get_body = json.loads(get_response["body"])
    assert get_body["reservation_id"] == reservation_id
    assert get_body["guest_email"] == "integration.test@example.com"

    print("✅ Step 4: Reservation retrieved successfully")

    # Verify all responses are JSON serializable (round-trip test)
    for response_body in [availability_body, quote_body, reservation_body, get_body]:
        json_string = json.dumps(response_body)
        parsed_back = json.loads(json_string)
        assert parsed_back == response_body

    print("✅ Complete workflow test passed!")


@pytest.mark.integration
def test_quote_expiration_validation(stack_outputs):
    """Test that expired quotes cannot be used for reservations.

    This test validates:
    - Expired quotes are rejected
    - Proper error handling with 400 Bad Request
    - Error message indicates expiration
    """
    quotes_table_name = os.environ["QUOTES_TABLE_NAME"]

    dynamodb = boto3.resource("dynamodb")
    quotes_table = dynamodb.Table(quotes_table_name)

    context = create_lambda_context()

    # Create a quote with past expiration (simulate expired quote)
    expired_quote_id = f"EXPIRED-{int(time.time())}"
    past_expiration = int(time.time()) - 3600  # 1 hour ago

    quotes_table.put_item(
        Item={
            "quote_id": expired_quote_id,
            "hotel_id": "H-PVR-002",
            "room_type_id": "RT-STD",
            "check_in_date": "2024-06-01",
            "check_out_date": "2024-06-03",
            "guests": 2,
            "total_cost": Decimal("300.0"),  # Use Decimal for DynamoDB
            "expires_at": past_expiration,
        }
    )

    # Try to create reservation with expired quote
    reservation_event = create_api_gateway_event(
        "POST",
        "/reservations",
        {
            "quote_id": expired_quote_id,
            "guest_name": "Test User",
            "guest_email": "test@example.com",
        },
    )

    reservation_response = lambda_handler(reservation_event, context)

    # Should fail with 400 Bad Request
    assert reservation_response["statusCode"] == 400

    response_body = json.loads(reservation_response["body"])
    assert "message" in response_body
    message_lower = response_body["message"].lower()
    assert "expired" in message_lower or "invalid" in message_lower

    print("✅ Expired quote validation working correctly")


@pytest.mark.integration
def test_quote_ttl_functionality(stack_outputs):
    """Test that DynamoDB TTL is properly configured for quotes table.

    This test validates:
    - TTL is enabled on the quotes table
    - TTL attribute is set to 'expires_at'
    - Configuration matches infrastructure requirements
    """
    quotes_table_name = os.environ["QUOTES_TABLE_NAME"]

    dynamodb = boto3.client("dynamodb")

    # Check TTL configuration
    response = dynamodb.describe_time_to_live(TableName=quotes_table_name)

    assert "TimeToLiveDescription" in response
    ttl_description = response["TimeToLiveDescription"]

    # Verify TTL is enabled
    assert ttl_description["TimeToLiveStatus"] in ["ENABLED", "ENABLING"]
    assert ttl_description["AttributeName"] == "expires_at"

    print("✅ DynamoDB TTL configured correctly for quotes table")
    print(f"   Status: {ttl_description['TimeToLiveStatus']}")
    print(f"   Attribute: {ttl_description['AttributeName']}")


@pytest.mark.integration
def test_get_hotels(stack_outputs):
    """Test get_hotels endpoint returns list of hotels.

    This test validates:
    - GET /hotels endpoint works
    - Returns 200 OK
    - Response contains hotels list
    - Each hotel has required fields (hotel_id, name, location)
    - Hotels are loaded from DynamoDB
    """
    context = create_lambda_context()

    # Test without limit
    event = create_api_gateway_event("GET", "/hotels")

    response = lambda_handler(event, context)
    assert response["statusCode"] == 200

    body = json.loads(response["body"])
    assert "hotels" in body
    assert "total_count" in body
    assert isinstance(body["hotels"], list)
    assert len(body["hotels"]) > 0

    # Verify hotel structure
    first_hotel = body["hotels"][0]
    assert "hotel_id" in first_hotel
    assert "name" in first_hotel
    assert "location" in first_hotel

    print(f"✅ get_hotels test passed - found {len(body['hotels'])} hotels")
    print(f"   First hotel: {first_hotel['name']} (ID: {first_hotel['hotel_id']})")

    # Test with limit parameter
    event_with_limit = create_api_gateway_event(
        "GET", "/hotels", query_params={"limit": "2"}
    )

    response_with_limit = lambda_handler(event_with_limit, context)
    assert response_with_limit["statusCode"] == 200

    body_with_limit = json.loads(response_with_limit["body"])
    assert "hotels" in body_with_limit
    assert len(body_with_limit["hotels"]) <= 2

    print(
        f"✅ get_hotels with limit test passed - returned {len(body_with_limit['hotels'])} hotels"
    )


@pytest.mark.integration
def test_error_handling_invalid_dates(stack_outputs):
    """Test error handling for invalid date formats.

    This test validates:
    - Invalid date format detection
    - Returns 400 Bad Request
    - Error message mentions date/format issue
    """
    context = create_lambda_context()

    event = create_api_gateway_event(
        "POST",
        "/availability/check",
        {
            "hotel_id": "H-PVR-002",
            "check_in_date": "invalid-date",
            "check_out_date": "2024-03-17",
            "guests": 2,
        },
    )

    response = lambda_handler(event, context)
    assert response["statusCode"] == 400

    body = json.loads(response["body"])
    assert "message" in body
    assert body["message"] == "Request validation failed"

    # Check that validation details are provided
    assert "details" in body
    assert len(body["details"]) > 0

    # Check that the error is about the check_in_date field
    date_error = next(
        (e for e in body["details"] if e["field"] == "check_in_date"), None
    )
    assert date_error is not None
    assert (
        "date" in date_error["message"].lower()
        or "invalid" in date_error["message"].lower()
    )

    print("✅ Invalid date format handling test passed")


@pytest.mark.integration
def test_direct_api_gateway_with_client_credentials(stack_outputs):
    """Test calling API Gateway directly with OAuth2 client credentials.

    This test validates:
    - OAuth2 client credentials flow works with Cognito
    - API Gateway JWT authorizer accepts the token
    - get_hotels endpoint returns expected data
    - This is the same flow AgentCore Gateway should use

    This test helps diagnose whether the issue is with:
    1. Cognito token generation (if this fails)
    2. API Gateway JWT authorizer (if this fails)
    3. AgentCore Gateway outbound auth configuration (if this passes but Gateway test fails)
    """
    # Get configuration from stack outputs
    client_id = stack_outputs.get("CognitoClientId")
    user_pool_id = stack_outputs.get("CognitoUserPoolId")
    api_endpoint = stack_outputs.get("ApiEndpointUrl")

    if not all([client_id, user_pool_id, api_endpoint]):
        pytest.fail(
            f"Missing required stack outputs. Found: CognitoClientId={client_id}, "
            f"CognitoUserPoolId={user_pool_id}, ApiEndpointUrl={api_endpoint}"
        )

    # Get client secret from Cognito
    print("\n🔐 Retrieving client secret from Cognito User Pool Client")
    cognito_client = boto3.client("cognito-idp")

    try:
        client_response = cognito_client.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id,
        )
        client_secret = client_response["UserPoolClient"].get("ClientSecret")

        if not client_secret:
            pytest.fail("Cognito User Pool Client does not have a secret")

        print("✅ Retrieved client secret from Cognito")

        # Print client configuration for debugging
        client_config = client_response["UserPoolClient"]
        print(f"   Client Name: {client_config.get('ClientName')}")
        print(f"   Allowed OAuth Flows: {client_config.get('AllowedOAuthFlows')}")
        print(f"   Allowed OAuth Scopes: {client_config.get('AllowedOAuthScopes')}")
        print(
            f"   Allowed OAuth Flows User Pool Client: {client_config.get('AllowedOAuthFlowsUserPoolClient')}"
        )

    except Exception as e:
        pytest.fail(f"Failed to retrieve client secret from Cognito: {e}")

    # Get Cognito domain for token URL
    try:
        user_pool_response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
        domain = user_pool_response["UserPool"].get("Domain")

        if not domain:
            pytest.fail("Cognito User Pool does not have a domain configured")

        region = user_pool_id.split("_")[0]
        token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
        print(f"   Token URL: {token_url}")

    except Exception as e:
        pytest.fail(f"Failed to get Cognito domain: {e}")

    print(f"\n🔐 Fetching OAuth2 token from {token_url}")
    print(f"   Client ID: {client_id}")

    # Fetch access token using client credentials grant with resource server scopes
    try:
        # Include resource server scopes in the token request
        scope = "gateway-resource-server/read gateway-resource-server/write"
        access_token = fetch_access_token(
            client_id, client_secret, token_url, scope=scope
        )
        print("✅ Access token obtained")
        print(f"   Requested scopes: {scope}")

        # Decode token to inspect claims (without verification for debugging)
        import base64

        token_parts = access_token.split(".")
        if len(token_parts) >= 2:
            # Decode payload (add padding if needed)
            payload = token_parts[1]
            payload += "=" * (4 - len(payload) % 4)
            decoded = base64.b64decode(payload)
            token_claims = json.loads(decoded)
            print(f"   Token claims: {json.dumps(token_claims, indent=2)}")
            print(f"   Token scopes: {token_claims.get('scope')}")
            print(f"   Token client_id: {token_claims.get('client_id')}")
            print(f"   Token aud: {token_claims.get('aud')}")

    except Exception as e:
        pytest.fail(f"Failed to fetch access token: {e}")

    # Call API Gateway get_hotels endpoint with the token
    print(f"\n🌐 Calling API Gateway: {api_endpoint}hotels")

    try:
        response = requests.get(
            f"{api_endpoint}hotels",
            headers={"Authorization": f"Bearer {access_token}"},
        )

        print(f"   Response status: {response.status_code}")
        print(f"   Response headers: {dict(response.headers)}")

        if response.status_code != 200:
            print(f"   Response body: {response.text}")
            pytest.fail(f"API Gateway returned {response.status_code}: {response.text}")

        response_data = response.json()
        print(f"   Response data: {json.dumps(response_data, indent=2)}")

        # Verify expected structure
        assert "hotels" in response_data, "Response should contain 'hotels'"
        assert isinstance(response_data["hotels"], list), "Hotels should be a list"
        assert len(response_data["hotels"]) > 0, "Should return at least one hotel"

        # Verify hotel structure
        first_hotel = response_data["hotels"][0]
        assert "hotel_id" in first_hotel, "Hotel should have hotel_id"
        assert "name" in first_hotel, "Hotel should have name"
        assert "location" in first_hotel, "Hotel should have location"

        print(
            f"\n✅ Direct API Gateway test passed - found {len(response_data['hotels'])} hotels"
        )
        print(f"   First hotel: {first_hotel['name']} (ID: {first_hotel['hotel_id']})")

    except Exception as e:
        print(f"\n❌ API Gateway call failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error details: {str(e)}")
        pytest.fail(f"Failed to call API Gateway directly: {e}")


@pytest.mark.integration
@pytest.mark.asyncio
async def test_get_hotels_via_agentcore_gateway(stack_outputs):
    """Test calling get_hotels tool via AgentCore Gateway with OAuth2.

    This test validates:
    - OAuth2 client credentials flow works
    - AgentCore Gateway accepts the token
    - MCP session initialization succeeds
    - Tool listing works
    - get_hotels tool can be called
    - Tool returns expected data structure

    Prerequisites:
    - HotelPmsStack deployed with AgentCore Gateway
    """
    # Get configuration from stack outputs
    client_id = stack_outputs.get("CognitoClientId")
    gateway_id = stack_outputs.get("GatewayId")
    user_pool_id = stack_outputs.get("CognitoUserPoolId")

    if not all([client_id, gateway_id, user_pool_id]):
        pytest.fail(
            f"Missing required stack outputs. Found: CognitoClientId={client_id}, GatewayId={gateway_id}, CognitoUserPoolId={user_pool_id}"
        )

    # Construct URLs from stack outputs
    region = user_pool_id.split("_")[0]
    gateway_url = (
        f"https://{gateway_id}.gateway.bedrock-agentcore.{region}.amazonaws.com/mcp"
    )

    # Get client secret from Cognito
    print("\n🔐 Retrieving client secret from Cognito User Pool Client")
    cognito_client = boto3.client("cognito-idp")

    try:
        client_response = cognito_client.describe_user_pool_client(
            UserPoolId=user_pool_id,
            ClientId=client_id,
        )
        client_secret = client_response["UserPoolClient"].get("ClientSecret")

        if not client_secret:
            pytest.fail("Cognito User Pool Client does not have a secret")

        print("✅ Retrieved client secret from Cognito")

    except Exception as e:
        pytest.fail(f"Failed to retrieve client secret from Cognito: {e}")

    # Get Cognito domain for token URL
    try:
        user_pool_response = cognito_client.describe_user_pool(UserPoolId=user_pool_id)
        domain = user_pool_response["UserPool"].get("Domain")

        if not domain:
            pytest.fail("Cognito User Pool does not have a domain configured")

        token_url = f"https://{domain}.auth.{region}.amazoncognito.com/oauth2/token"
        print(f"   Token URL: {token_url}")

    except Exception as e:
        pytest.fail(f"Failed to get Cognito domain: {e}")

    print(f"\n🔐 Fetching OAuth2 token from {token_url}")
    print(f"   Client ID: {client_id}")

    # Fetch access token
    try:
        access_token = fetch_access_token(client_id, client_secret, token_url)
        print("✅ Access token obtained")
    except Exception as e:
        pytest.fail(f"Failed to fetch access token: {e}")

    print(f"\n🌐 Connecting to AgentCore Gateway: {gateway_url}")

    # Call get_hotels tool via gateway
    try:
        result = await call_mcp_tool_via_gateway(
            gateway_url=gateway_url,
            access_token=access_token,
            tool_name="HotelPMS___get_hotels",
            arguments={},
        )

        print("\n✅ Tool execution result received")
        print(f"   Result type: {type(result)}")
        print(f"   Result: {result}")

        # Parse the result content
        response_data = parse_mcp_result(result)
        print(f"   Parsed response: {response_data}")

        # Verify expected structure
        assert "hotels" in response_data, "Response should contain 'hotels'"
        assert isinstance(response_data["hotels"], list), "Hotels should be a list"
        assert len(response_data["hotels"]) > 0, "Should return at least one hotel"

        # Verify hotel structure
        first_hotel = response_data["hotels"][0]
        assert "hotel_id" in first_hotel, "Hotel should have hotel_id"
        assert "name" in first_hotel, "Hotel should have name"
        assert "location" in first_hotel, "Hotel should have location"

        print(
            f"\n✅ get_hotels via AgentCore Gateway test passed - found {len(response_data['hotels'])} hotels"
        )
        print(f"   First hotel: {first_hotel['name']} (ID: {first_hotel['hotel_id']})")

    except Exception as e:
        print(f"\n❌ Tool execution failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Error details: {str(e)}")
        pytest.fail(f"Failed to call get_hotels via AgentCore Gateway: {e}")
