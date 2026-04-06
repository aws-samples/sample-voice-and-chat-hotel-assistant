# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared pytest fixtures for integration tests."""

import os

import boto3
import pytest


@pytest.fixture(scope="session")
def stack_name():
    """CloudFormation stack name."""
    return os.environ.get("STACK_NAME", "HotelPmsStack")


@pytest.fixture(scope="session")
def knowledge_base_info(stack_name):
    """Get Knowledge Base ID from deployed CloudFormation stack."""
    cf_client = boto3.client("cloudformation")

    try:
        # Get stack outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0]["Outputs"]

        kb_info = {}
        for output in outputs:
            key = output["OutputKey"]
            value = output["OutputValue"]

            if "KnowledgeBase" in key and "Id" in key:
                kb_info["knowledge_base_id"] = value
            elif "KnowledgeBase" in key and "Arn" in key:
                kb_info["knowledge_base_arn"] = value

        if "knowledge_base_id" not in kb_info:
            print("⚠️ Knowledge Base ID not found in stack outputs")
            return None

        print(f"✅ Found Knowledge Base ID: {kb_info['knowledge_base_id']}")
        return kb_info

    except Exception as e:
        print(f"⚠️ Could not get Knowledge Base info from stack {stack_name}: {e}")
        return None


@pytest.fixture(scope="session")
def dynamodb_table_names(stack_name):
    """Get DynamoDB table names from deployed CloudFormation stack."""
    cf_client = boto3.client("cloudformation")

    try:
        # Get stack outputs
        response = cf_client.describe_stacks(StackName=stack_name)
        outputs = response["Stacks"][0]["Outputs"]

        table_names = {}
        for output in outputs:
            key = output["OutputKey"]
            value = output["OutputValue"]

            # Look for table name outputs (e.g., HotelsTableName, ReservationsTableName)
            if key.endswith("TableName"):
                table_type = key.replace("TableName", "").lower()
                table_names[table_type] = value

        if not table_names:
            print("⚠️ No DynamoDB table names found in stack outputs")
            return None

        print(f"✅ Found DynamoDB tables: {list(table_names.keys())}")
        return table_names

    except Exception as e:
        print(f"⚠️ Could not get DynamoDB table names from stack {stack_name}: {e}")
        return None


@pytest.fixture(scope="session")
def setup_knowledge_base_env(knowledge_base_info):
    """Automatically set up KNOWLEDGE_BASE_ID environment variable for integration tests."""
    original_value = os.environ.get("KNOWLEDGE_BASE_ID")

    # Only set if we found a Knowledge Base and it's not already set
    if knowledge_base_info and "knowledge_base_id" in knowledge_base_info:
        if not original_value:
            os.environ["KNOWLEDGE_BASE_ID"] = knowledge_base_info["knowledge_base_id"]
            print(
                f"🔧 Set KNOWLEDGE_BASE_ID environment variable: {knowledge_base_info['knowledge_base_id']}"
            )

            # Force re-initialization of the Knowledge Base handler in agentcore_handler
            try:
                from hotel_pms_simulation.handlers import agentcore_handler
                from hotel_pms_simulation.handlers.kb_query_handler import (
                    KnowledgeBaseQueryHandler,
                )

                # Re-initialize the Knowledge Base handler with the new environment variable
                agentcore_handler.kb_query_handler = KnowledgeBaseQueryHandler(
                    knowledge_base_info["knowledge_base_id"]
                )
                print("🔄 Re-initialized Knowledge Base handler")
            except Exception as e:
                print(f"⚠️ Could not re-initialize Knowledge Base handler: {e}")
        else:
            print(f"ℹ️ KNOWLEDGE_BASE_ID already set: {original_value}")
    else:
        print("⚠️ No Knowledge Base found, KNOWLEDGE_BASE_ID not set")

    yield knowledge_base_info

    # Restore original value only if we set it
    if (
        knowledge_base_info
        and "knowledge_base_id" in knowledge_base_info
        and not original_value
    ):
        os.environ.pop("KNOWLEDGE_BASE_ID", None)

        # Reset the Knowledge Base handler to None
        try:
            from hotel_pms_simulation.handlers import agentcore_handler

            agentcore_handler.kb_query_handler = None
            print("🔄 Reset Knowledge Base handler to None")
        except Exception as e:
            print(f"⚠️ Could not reset Knowledge Base handler: {e}")

        print("🧹 Cleaned up KNOWLEDGE_BASE_ID environment variable")


@pytest.fixture(scope="session")
def setup_dynamodb_env(dynamodb_table_names):
    """Automatically set up DynamoDB table environment variables for integration tests."""
    original_values = {}

    # Map CloudFormation output names to environment variable names
    # CloudFormation outputs use format like "RoomtypesTableName" (lowercase after first word)
    # But services expect "ROOM_TYPES_TABLE_NAME" (with underscores)
    table_name_mapping = {
        "roomtypes": "ROOM_TYPES_TABLE_NAME",
        "ratemodifiers": "RATE_MODIFIERS_TABLE_NAME",
        "hotels": "HOTELS_TABLE_NAME",
        "reservations": "RESERVATIONS_TABLE_NAME",
        "requests": "REQUESTS_TABLE_NAME",
        "quotes": "QUOTES_TABLE_NAME",
    }

    if dynamodb_table_names:
        for table_type, table_name in dynamodb_table_names.items():
            # Use mapping if available, otherwise default to uppercase with _TABLE_NAME
            env_var = table_name_mapping.get(
                table_type, f"{table_type.upper()}_TABLE_NAME"
            )
            original_values[env_var] = os.environ.get(env_var)

            if not original_values[env_var]:
                os.environ[env_var] = table_name
                print(f"🔧 Set {env_var} environment variable: {table_name}")
            else:
                print(f"ℹ️ {env_var} already set: {original_values[env_var]}")

        # Force re-initialization of the MCP server module to pick up new environment variables
        try:
            import importlib

            import hotel_pms_simulation.mcp.server as server_module

            importlib.reload(server_module)
            print("🔄 Re-initialized MCP server with DynamoDB environment variables")
        except Exception as e:
            print(f"⚠️ Could not re-initialize MCP server: {e}")
    else:
        print("⚠️ No DynamoDB tables found, environment variables not set")

    yield dynamodb_table_names

    # Restore original values
    if dynamodb_table_names:
        for table_type in dynamodb_table_names.keys():
            env_var = table_name_mapping.get(
                table_type, f"{table_type.upper()}_TABLE_NAME"
            )
            if original_values.get(env_var) is None:
                os.environ.pop(env_var, None)
                print(f"🧹 Cleaned up {env_var} environment variable")

        # Reload again to restore original state
        try:
            import importlib

            import hotel_pms_simulation.mcp.server as server_module

            importlib.reload(server_module)
            print("🔄 Reset MCP server to original state")
        except Exception as e:
            print(f"⚠️ Could not reset MCP server: {e}")
