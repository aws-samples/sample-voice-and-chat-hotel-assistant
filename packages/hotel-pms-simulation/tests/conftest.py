# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Shared pytest fixtures for integration tests."""

import os

import pytest


# Unit test fixtures
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment variables for unit tests."""
    # Only set these if they're not already set (to avoid interfering with integration tests)
    test_env_vars = {
        "AWS_DEFAULT_REGION": "us-east-1",
        "DB_SECRET_ARN": "arn:aws:secretsmanager:us-east-1:123456789012:secret:test-secret",
        "LOG_LEVEL": "DEBUG",
        "_LAMBDA_SERVER_PORT": "3001",
        "AWS_LAMBDA_FUNCTION_NAME": "test-function",
    }

    original_values = {}
    for key, value in test_env_vars.items():
        if key not in os.environ:
            original_values[key] = None
            os.environ[key] = value
        else:
            original_values[key] = os.environ[key]

    yield

    # Restore original values (but only for unit tests, not integration tests)
    for key, original_value in original_values.items():
        if original_value is None and key in test_env_vars:
            # Only remove if we set it and it's still our test value
            if os.environ.get(key) == test_env_vars[key]:
                os.environ.pop(key, None)


@pytest.fixture
def mock_db_connection():
    """Mock database connection for unit tests."""
    from unittest.mock import MagicMock, patch

    with patch(
        "hotel_pms_simulation.database.connection.get_connection"
    ) as mock_get_conn:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_get_conn.return_value = mock_conn
        yield mock_cursor


@pytest.fixture
def mock_execute_query():
    """Mock execute_query function for unit tests."""
    from unittest.mock import patch

    with patch("hotel_pms_simulation.database.connection.execute_query") as mock_query:
        yield mock_query
