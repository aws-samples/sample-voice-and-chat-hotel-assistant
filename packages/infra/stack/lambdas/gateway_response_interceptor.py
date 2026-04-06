# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AgentCore Gateway response interceptor Lambda function.

This Lambda function transforms all HTTP status codes to 200 while preserving
the original response body. This allows AI agents to access error details in
the response body rather than being blocked by non-2xx status codes.

Additionally, it unwraps OpenAPIClientException errors, extracting embedded
JSON when available or wrapping the error text in a simple message object.
"""

import json
import logging
import os
import re

logger = logging.getLogger()
logger.setLevel(os.getenv("LOG_LEVEL", logging.INFO))


def extract_error_json(text: str) -> dict | None:
    """
    Extract JSON error payload from OpenAPIClientException message.

    The Gateway wraps 400 errors in text like:
    "OpenAPIClientException - Error executing HTTP request for <id>:
     Client error: API request failed with status: 400 - {json_payload}"

    Args:
        text: Error message text that may contain embedded JSON

    Returns:
        Extracted JSON dict if found, None otherwise
    """
    # Look for JSON after "status: 400 -" or similar patterns
    match = re.search(r"status: \d+ - (\{.+\})$", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse embedded JSON: {e}")
            return None
    return None


def lambda_handler(event, context):
    """
    Transform all gateway responses to status code 200.

    This interceptor ensures AI agents can access response bodies
    regardless of the original HTTP status code.
    """

    logger.debug(f"Received event: {event}")

    mcp_data = event.get("mcp", {})

    # Check if this is a RESPONSE interceptor
    if "gatewayResponse" not in mcp_data or mcp_data["gatewayResponse"] is None:
        # REQUEST interceptor
        logger.warning("Not a RESPONSE interceptor event, passing through")
        gateway_request = mcp_data.get("gatewayRequest", {})
        return {
            "interceptorOutputVersion": "1.0",
            "mcp": {
                "transformedGatewayRequest": {
                    "body": gateway_request.get("body") or {},
                },
            },
        }

    # RESPONSE interceptor
    gateway_response = mcp_data.get("gatewayResponse", {})

    try:
        # Only wrap the body extraction in try-except since it could be malformed
        body = gateway_response.get("body") or {}
    except Exception as e:
        logger.error(f"Error extracting body: {str(e)}", exc_info=True)
        body = {}

    original_status = gateway_response.get("statusCode", 200)

    # Check if this is an MCP error response with OpenAPIClientException
    if isinstance(body, dict) and body.get("result", {}).get("isError"):
        result = body.get("result", {})
        content = result.get("content", [])

        # Look for OpenAPIClientException
        if content and isinstance(content, list) and len(content) > 0:
            first_content = content[0]
            if isinstance(first_content, dict) and first_content.get("type") == "text":
                text = first_content.get("text", "")

                # Check if this is an OpenAPIClientException
                if "OpenAPIClientException" in text:
                    error_json = None

                    # Try to extract embedded JSON (from backend 400 responses)
                    if "API request failed with status:" in text:
                        logger.info("Detected OpenAPIClientException with embedded JSON error from backend")
                        error_json = extract_error_json(text)

                    # If no embedded JSON found, wrap the error text in a simple message object
                    if not error_json:
                        logger.info("No embedded JSON found, wrapping error text in message object")
                        error_json = {"message": text}

                    logger.info(f"Transformed error: {error_json}")

                    # Replace the MCP error response with the error payload
                    body = {
                        "jsonrpc": body.get("jsonrpc", "2.0"),
                        "id": body.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": json.dumps(error_json)}],
                            "isError": False,  # Mark as not an error since we extracted/wrapped the payload
                        },
                    }
                    logger.info("Transformed MCP error response")

    # Transform 4xx errors to 200
    if 400 <= original_status < 500:
        logger.info(f"Transforming status code {original_status} to 200")
        new_status = 200
    else:
        new_status = original_status

    response = {
        "interceptorOutputVersion": "1.0",
        "mcp": {
            "transformedGatewayResponse": {
                "body": body,
                "statusCode": new_status,
            }
        },
    }

    logger.debug(f"Transformed gateway response: {response}")
    return response
