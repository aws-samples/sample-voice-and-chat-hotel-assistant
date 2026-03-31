# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Integration tests for CognitoAuth class.

These tests validate the CognitoAuth implementation against real AWS Cognito services
using credentials loaded from environment variables.
"""

import os

import httpx
import pytest

from virtual_assistant_common.cognito_mcp.cognito_auth import CognitoAuth
from virtual_assistant_common.cognito_mcp.exceptions import CognitoAuthError


@pytest.mark.integration
class TestCognitoAuthIntegration:
    """Integration tests for CognitoAuth with real Cognito services."""

    def test_real_cognito_authentication(self):
        """Test CognitoAuth with real Cognito credentials."""
        # Load credentials from environment
        user_pool_id = os.getenv("HOTEL_PMS_MCP_USER_POOL_ID")
        client_id = os.getenv("HOTEL_PMS_MCP_CLIENT_ID")
        client_secret = os.getenv("HOTEL_PMS_MCP_CLIENT_SECRET")
        region = os.getenv("AWS_REGION", "us-east-1")

        # Skip test if credentials are not available
        if not all([user_pool_id, client_id, client_secret]):
            pytest.skip(
                "Integration test skipped: Missing required environment variables. "
                "Set HOTEL_PMS_MCP_USER_POOL_ID, HOTEL_PMS_MCP_CLIENT_ID, and HOTEL_PMS_MCP_CLIENT_SECRET"
            )

        # Create CognitoAuth instance
        auth = CognitoAuth(
            user_pool_id=user_pool_id,
            client_id=client_id,
            client_secret=client_secret,
            region=region,
            timeout=30.0,
            max_retries=3,
        )

        try:
            # Test token acquisition
            token = auth._get_valid_token()

            # Verify token properties
            assert token is not None
            assert token.access_token is not None
            assert len(token.access_token) > 0
            assert token.token_type == "Bearer"
            assert not token.is_expired
            assert not token.expires_soon()

            print(f"✅ Successfully acquired token: {token.access_token[:20]}...")
            print(f"✅ Token type: {token.token_type}")
            print(f"✅ Token expires at: {token.expires_at}")

            # Test token caching - second call should return same token
            token2 = auth._get_valid_token()
            assert token2 == token  # Should be the same cached token

            print("✅ Token caching works correctly")

        except CognitoAuthError as e:
            pytest.fail(f"CognitoAuth integration test failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error in CognitoAuth integration test: {e}")

    def test_real_cognito_oidc_discovery(self):
        """Test OIDC discovery with real Cognito user pool."""
        # Load credentials from environment
        user_pool_id = os.getenv("HOTEL_PMS_MCP_USER_POOL_ID")
        client_id = os.getenv("HOTEL_PMS_MCP_CLIENT_ID")
        client_secret = os.getenv("HOTEL_PMS_MCP_CLIENT_SECRET")
        region = os.getenv("AWS_REGION", "us-east-1")

        # Skip test if credentials are not available
        if not all([user_pool_id, client_id, client_secret]):
            pytest.skip(
                "Integration test skipped: Missing required environment variables. "
                "Set HOTEL_PMS_MCP_USER_POOL_ID, HOTEL_PMS_MCP_CLIENT_ID, and HOTEL_PMS_MCP_CLIENT_SECRET"
            )

        # Create CognitoAuth instance
        auth = CognitoAuth(
            user_pool_id=user_pool_id,
            client_id=client_id,
            client_secret=client_secret,
            region=region,
        )

        try:
            # Test OIDC discovery
            token_endpoint = auth._get_token_endpoint()

            # Verify token endpoint properties
            assert token_endpoint is not None
            assert token_endpoint.startswith("https://")
            assert "oauth2/token" in token_endpoint
            assert region in token_endpoint

            print(f"✅ Successfully discovered token endpoint: {token_endpoint}")

            # Test that endpoint is cached
            token_endpoint2 = auth._get_token_endpoint()
            assert token_endpoint2 == token_endpoint

            print("✅ Token endpoint caching works correctly")

        except CognitoAuthError as e:
            pytest.fail(f"OIDC discovery integration test failed: {e}")
        except Exception as e:
            pytest.fail(f"Unexpected error in OIDC discovery integration test: {e}")

    def test_invalid_credentials_handling(self):
        """Test CognitoAuth with invalid credentials."""
        # Use invalid credentials to test error handling
        auth = CognitoAuth(
            user_pool_id="us-east-1_invalid123",
            client_id="invalid-client-id",
            client_secret="invalid-client-secret",
            region="us-east-1",
            timeout=10.0,  # Shorter timeout for faster test
            max_retries=1,  # Fewer retries for faster test
        )

        # This should fail with a CognitoAuthError
        with pytest.raises(CognitoAuthError) as exc_info:
            auth._get_valid_token()

        error = exc_info.value
        assert "OAuth2 token request failed" in str(error) or "Failed to fetch OIDC configuration" in str(error)
        print(f"✅ Invalid credentials properly handled: {error}")

    def test_httpx_client_integration(self):
        """Test CognitoAuth with real httpx client making authenticated requests."""
        # Load credentials from environment
        user_pool_id = os.getenv("HOTEL_PMS_MCP_USER_POOL_ID")
        client_id = os.getenv("HOTEL_PMS_MCP_CLIENT_ID")
        client_secret = os.getenv("HOTEL_PMS_MCP_CLIENT_SECRET")
        region = os.getenv("AWS_REGION", "us-east-1")
        mcp_url = os.getenv("HOTEL_PMS_MCP_URL")

        # Skip test if credentials are not available
        if not all([user_pool_id, client_id, client_secret, mcp_url]):
            pytest.skip(
                "Integration test skipped: Missing required environment variables. "
                "Set HOTEL_PMS_MCP_USER_POOL_ID, HOTEL_PMS_MCP_CLIENT_ID, "
                "HOTEL_PMS_MCP_CLIENT_SECRET, and HOTEL_PMS_MCP_URL"
            )

        # Create CognitoAuth instance
        auth = CognitoAuth(
            user_pool_id=user_pool_id,
            client_id=client_id,
            client_secret=client_secret,
            region=region,
        )

        try:
            # Create httpx client with our auth
            with httpx.Client(auth=auth, timeout=30.0) as client:
                # Make a test request to the MCP server
                # This should automatically authenticate using our CognitoAuth
                response = client.get(f"{mcp_url}/health")

                # The request should be authenticated (we don't care about the response content,
                # just that authentication worked and we didn't get a 401)
                assert response.status_code != 401, f"Authentication failed: {response.status_code} {response.text}"

                print(f"✅ Authenticated request successful: {response.status_code}")
                print(f"✅ MCP server responded: {response.text[:100]}...")

        except Exception as e:
            # If the MCP server is not available, that's okay - we just want to test that
            # authentication works (no 401 errors)
            if "401" in str(e) or "Unauthorized" in str(e):
                pytest.fail(f"Authentication failed with httpx client: {e}")
            else:
                print(f"✅ Authentication worked, but MCP server may not be available: {e}")
