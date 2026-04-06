# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared utilities for AgentCore Gateway MCP integration tests."""

import json

import requests
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


def fetch_access_token(
    client_id: str, client_secret: str, token_url: str, scope: str = None
) -> str:
    """Fetch OAuth2 access token using client credentials flow.

    Args:
        client_id: OAuth2 client ID
        client_secret: OAuth2 client secret
        token_url: Token endpoint URL
        scope: Optional OAuth2 scope

    Returns:
        Access token string
    """
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret,
    }

    if scope:
        data["scope"] = scope

    response = requests.post(
        token_url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


async def call_mcp_tool_via_gateway(
    gateway_url: str, access_token: str, tool_name: str, arguments: dict = None
) -> dict:
    """Call an MCP tool via AgentCore Gateway.

    Args:
        gateway_url: AgentCore Gateway URL
        access_token: OAuth2 access token
        tool_name: Name of the tool to call
        arguments: Tool arguments (optional)

    Returns:
        Tool execution result
    """
    headers = {"Authorization": f"Bearer {access_token}"}

    async with streamablehttp_client(
        url=gateway_url,
        headers=headers,
    ) as (read_stream, write_stream, _):
        async with ClientSession(read_stream, write_stream) as session:
            # Initialize MCP session
            await session.initialize()

            # Call the tool
            call_result = await session.call_tool(tool_name, arguments or {})

            return call_result


def parse_mcp_result(result) -> dict:
    """Parse MCP tool result into a dictionary.

    Args:
        result: MCP tool call result

    Returns:
        Parsed result as dictionary

    Raises:
        ValueError: If the result cannot be parsed or contains validation errors
    """
    if hasattr(result, "content") and result.content and len(result.content) > 0:
        first_content = result.content[0]
        if hasattr(first_content, "text"):
            text = first_content.text

            # Try to parse as JSON first
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                # If it's not JSON, check if it's an error message from AgentCore Gateway
                if (
                    "OpenAPIClientException" in text
                    or "Parameter validation failed" in text
                ):
                    # Parse error details and fail the test
                    error_details = _parse_gateway_validation_error(text)
                    raise ValueError(
                        f"AgentCore Gateway rejected tool call due to validation error. "
                        f"This indicates the MCP server response doesn't match the OpenAPI spec.\n"
                        f"Full response: {text}\n"
                        f"Parsed details: {json.dumps(error_details, indent=2)}"
                    )
                # For other non-JSON responses, raise the original error
                raise

    raise ValueError(f"Unable to parse MCP result: {result}")


def _parse_gateway_validation_error(error_text: str) -> list[dict]:
    """Parse AgentCore Gateway validation error text into structured details.

    Args:
        error_text: Error message from AgentCore Gateway

    Returns:
        List of error detail dictionaries
    """
    details = []

    # First, try to extract embedded JSON from OpenAPIClientException
    # Example: "OpenAPIClientException - Error executing HTTP request for ...: Client error: API request failed with status: 400 - {"error":true,...}"
    import re

    json_match = re.search(r"status: \d+ - (\{.+\})$", error_text)
    if json_match:
        try:
            embedded_json = json.loads(json_match.group(1))
            # If the embedded JSON has validation details, return those
            if embedded_json.get("error") and embedded_json.get("details"):
                return embedded_json["details"]
        except json.JSONDecodeError:
            pass  # Fall through to other parsing methods

    # Handle missing required fields
    if "Missing required field(s):" in error_text:
        # Extract field names from the error message
        # Example: "Missing required field(s): 'check_in_date', 'check_out_date', 'guests', 'room_type_id'"
        match = re.search(r"Missing required field\(s\): (.+)", error_text)
        if match:
            fields_str = match.group(1)
            # Extract field names (they're in quotes)
            fields = re.findall(r"'([^']+)'", fields_str)
            for field in fields:
                details.append(
                    {
                        "field": field,
                        "message": "Field required",
                        "type": "missing",
                        "input": None,
                    }
                )

    # Handle enum validation failures
    elif "validation failed: enum" in error_text:
        # Example: "Field 'package_type' validation failed: enum"
        match = re.search(r"Field '([^']+)' validation failed: enum", error_text)
        if match:
            field = match.group(1)
            details.append(
                {
                    "field": field,
                    "message": "Input should be 'simple' or 'detailed'",
                    "type": "enum",
                    "input": None,
                }
            )

    # If we couldn't parse specific details, return a generic error
    if not details:
        details.append(
            {
                "field": "unknown",
                "message": error_text,
                "type": "validation_error",
                "input": None,
            }
        )

    return details
