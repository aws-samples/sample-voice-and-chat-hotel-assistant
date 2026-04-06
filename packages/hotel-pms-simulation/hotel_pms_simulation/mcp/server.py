# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Hotel Assistant MCP Server

Provides tools for querying hotel documentation and prompts for AI agents.
Location: packages/hotel-pms-simulation/hotel_pms_simulation/mcp/server.py
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Any

import boto3
from aws_lambda_powertools import Logger
from mcp.server import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# Import hotel service for DynamoDB access
from ..services.hotel_service import HotelService

logger = Logger()

# Initialize FastMCP server for AgentCore Runtime
# - host="0.0.0.0" allows external connections
# - stateless_http=True required for AgentCore Runtime session isolation
mcp = FastMCP("Hotel Assistant", host="0.0.0.0", stateless_http=True)

# Global configuration
# boto3 uses AWS_DEFAULT_REGION environment variable
AWS_REGION = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
PROMPT_DIR = Path(__file__).parent / "assets"

# Initialize services
hotel_service = HotelService()
bedrock_agent = boto3.client("bedrock-agent-runtime", region_name=AWS_REGION)


@mcp.tool(description="Query hotel documentation from knowledge base")
async def query_hotel_knowledge(
    query: str, hotel_ids: list[str] | None = None, max_results: int = 5
) -> str:
    """
    Query hotel documentation from knowledge base.

    Args:
        query: Search query string
        hotel_ids: Optional list of hotel IDs to filter by
        max_results: Maximum number of results (default: 5)

    Returns:
        Formatted string with relevant document excerpts
    """
    try:
        # Get knowledge base ID from environment (read dynamically for testing)
        knowledge_base_id = os.environ.get("KNOWLEDGE_BASE_ID")

        # Build retrieval configuration
        retrieval_config: dict[str, Any] = {
            "vectorSearchConfiguration": {"numberOfResults": max_results}
        }

        # Add hotel_id filter if provided
        if hotel_ids:
            retrieval_config["vectorSearchConfiguration"]["filter"] = {
                "in": {"key": "hotel_id", "value": hotel_ids}
            }

        # Query knowledge base
        response = bedrock_agent.retrieve(
            knowledgeBaseId=knowledge_base_id,
            retrievalQuery={"text": query},
            retrievalConfiguration=retrieval_config,
        )

        # Format results as a readable string for voice interaction
        results = []
        for idx, item in enumerate(response.get("retrievalResults", []), 1):
            hotel_name = item.get("metadata", {}).get("hotel_name", "Unknown Hotel")
            content = item["content"]["text"]
            score = item["score"]

            results.append(
                f"Result {idx} - {hotel_name} (relevance: {score:.2f}):\n{content}\n"
            )

        formatted_output = (
            "\n---\n".join(results) if results else "No relevant information found."
        )

        logger.info(
            "Knowledge base query completed",
            extra={
                "query": query,
                "hotel_ids": hotel_ids,
                "results_count": len(results),
            },
        )

        return formatted_output

    except Exception as e:
        logger.error(
            "Knowledge base query failed", extra={"error": str(e), "query": query}
        )
        raise


@mcp.prompt(name="chat_system_prompt")
async def chat_system_prompt() -> str:
    """System prompt optimized for text-based chat interactions."""
    return load_prompt_with_context("chat", prompt_dir=PROMPT_DIR)


@mcp.prompt(name="voice_system_prompt")
async def voice_system_prompt() -> str:
    """System prompt optimized for speech-to-speech voice interactions."""
    return load_prompt_with_context("voice", prompt_dir=PROMPT_DIR)


@mcp.prompt(name="default_system_prompt")
async def default_system_prompt() -> str:
    """General-purpose system prompt for any interaction type (returns chat prompt)."""
    return load_prompt_with_context("chat", prompt_dir=PROMPT_DIR)


def load_prompt_with_context(prompt_type: str, prompt_dir: Path) -> str:
    """
    Load prompt template and inject dynamic hotel context.

    Args:
        prompt_type: Type of prompt (chat, voice, default)
        prompt_dir: Directory containing prompt templates

    Returns:
        Prompt with injected context
    """
    # Load template
    template_path = prompt_dir / f"{prompt_type}_prompt.txt"
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    template = template_path.read_text()

    # Generate dynamic context
    context = generate_hotel_context()

    # Inject context
    prompt = template.replace("{current_date}", context["current_date"])
    prompt = prompt.replace("{hotel_list}", context["hotel_list"])

    logger.info("Generated prompt with context", extra={"prompt_type": prompt_type})

    return prompt


def generate_hotel_context() -> dict[str, str]:
    """
    Generate dynamic hotel context for prompt injection.

    Returns:
        Dictionary with current_date and hotel_list
    """
    # Get current date
    current_date = datetime.now().strftime("%B %d, %Y")

    # Get hotels from DynamoDB
    try:
        hotels_response = hotel_service.get_hotels()
        hotels = hotels_response.get("hotels", [])

        # Format hotel list
        hotel_list_lines = ["Available hotels:"]
        for hotel in hotels:
            hotel_list_lines.append(
                f"- {hotel.get('name', 'Unknown')} (ID: {hotel.get('hotel_id', 'unknown')})"
            )

        hotel_list = "\n".join(hotel_list_lines)

    except Exception as e:
        logger.error("Failed to get hotel list", extra={"error": str(e)})
        hotel_list = "Hotel list temporarily unavailable"

    return {"current_date": current_date, "hotel_list": hotel_list}


# Custom health check endpoint for Docker healthcheck
@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> JSONResponse:
    """
    Health check endpoint for container orchestration.

    Returns:
        JSON response with status and server information
    """
    return JSONResponse(
        {
            "status": "healthy",
            "server": "Hotel Assistant MCP Server",
            "timestamp": datetime.now().isoformat(),
        }
    )


# Alternative ping endpoint for simple health checks
@mcp.custom_route("/ping", methods=["GET"])
async def ping(request: Request) -> JSONResponse:
    """Simple ping endpoint for basic health checks."""
    return JSONResponse({"status": "ok"})


# Entry point for AgentCore Runtime
def handler(event: dict[str, Any], context: Any) -> Any:
    """
    Lambda handler for AgentCore Runtime.

    Note: With stateless_http=True, FastMCP automatically handles
    the streamable HTTP transport. No need to specify transport parameter.
    """
    return mcp.run()


# Main entry point for running the server
if __name__ == "__main__":
    logger.info("Starting Hotel Assistant MCP Server")
    logger.info("MCP endpoint available at: http://0.0.0.0:8000/mcp")
    logger.info("Health check available at: http://0.0.0.0:8000/health")
    logger.info("Ping endpoint available at: http://0.0.0.0:8000/ping")
    # With stateless_http=True, FastMCP uses streamable HTTP by default
    mcp.run(transport="streamable-http")
