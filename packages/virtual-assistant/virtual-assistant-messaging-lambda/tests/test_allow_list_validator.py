# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for phone number allow list validation service."""

import os
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from virtual_assistant_messaging_lambda.services.allow_list_validator import (
    clear_allow_list_cache,
    get_allow_list,
    is_phone_allowed,
)


class TestGetAllowList:
    """Test cases for get_allow_list function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_allow_list_cache()

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_get_allow_list_success(self, mock_boto3):
        """Test successful retrieval of allow list from SSM."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "+1234567890,+0987654321"}}

        # Test
        result = get_allow_list()

        # Verify
        assert result == "+1234567890,+0987654321"
        mock_boto3.client.assert_called_once_with("ssm")
        mock_ssm.get_parameter.assert_called_once_with(Name="/virtual-assistant/whatsapp/allow-list")

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_get_allow_list_custom_parameter_name(self, mock_boto3):
        """Test retrieval with custom parameter name from environment."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "*"}}

        # Set custom parameter name
        with patch.dict(os.environ, {"WHATSAPP_ALLOW_LIST_PARAMETER": "/custom/allow-list"}):
            result = get_allow_list()

        # Verify
        assert result == "*"
        mock_ssm.get_parameter.assert_called_once_with(Name="/custom/allow-list")

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_get_allow_list_parameter_not_found(self, mock_boto3):
        """Test handling when SSM parameter is not found."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.side_effect = ClientError({"Error": {"Code": "ParameterNotFound"}}, "GetParameter")

        # Test
        result = get_allow_list()

        # Verify
        assert result == ""

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_get_allow_list_access_denied(self, mock_boto3):
        """Test handling when access is denied to SSM parameter."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.side_effect = ClientError({"Error": {"Code": "AccessDenied"}}, "GetParameter")

        # Test
        result = get_allow_list()

        # Verify
        assert result == ""

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_get_allow_list_caching(self, mock_boto3):
        """Test that allow list is cached for 5 minutes."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "+1234567890"}}

        # First call
        result1 = get_allow_list()
        assert result1 == "+1234567890"
        assert mock_ssm.get_parameter.call_count == 1

        # Second call within cache TTL
        result2 = get_allow_list()
        assert result2 == "+1234567890"
        assert mock_ssm.get_parameter.call_count == 1  # Should not call SSM again

        # Verify both results are the same
        assert result1 == result2

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.time")
    def test_get_allow_list_cache_expiry(self, mock_time, mock_boto3):
        """Test that cache expires after 5 minutes."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "+1234567890"}}

        # Mock time progression - first call at time 0, second call at time 301
        mock_time.time.side_effect = [0, 301]

        # First call
        result1 = get_allow_list()
        assert result1 == "+1234567890"
        assert mock_ssm.get_parameter.call_count == 1

        # Second call after cache expiry (301 seconds > 300 TTL)
        result2 = get_allow_list()
        assert result2 == "+1234567890"
        assert mock_ssm.get_parameter.call_count == 2  # Should call SSM again

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_get_allow_list_empty_parameter(self, mock_boto3):
        """Test handling of empty parameter value."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": ""}}

        # Test
        result = get_allow_list()

        # Verify
        assert result == ""


class TestIsPhoneAllowed:
    """Test cases for is_phone_allowed function."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_allow_list_cache()

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_wildcard(self, mock_get_allow_list):
        """Test that wildcard allows any phone number."""
        mock_get_allow_list.return_value = "*"

        # Test various phone number formats
        assert is_phone_allowed("+1234567890") is True
        assert is_phone_allowed("+0987654321") is True
        assert is_phone_allowed("1234567890") is True
        assert is_phone_allowed("+44123456789") is True

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_specific_numbers(self, mock_get_allow_list):
        """Test validation against specific phone numbers."""
        mock_get_allow_list.return_value = "+1234567890,+0987654321"

        # Test allowed numbers
        assert is_phone_allowed("+1234567890") is True
        assert is_phone_allowed("+0987654321") is True

        # Test disallowed numbers
        assert is_phone_allowed("+1111111111") is False
        assert is_phone_allowed("+2222222222") is False

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_whitespace_handling(self, mock_get_allow_list):
        """Test that whitespace in allow list is handled correctly."""
        mock_get_allow_list.return_value = " +1234567890 , +0987654321 , +1111111111 "

        # Test allowed numbers (should work despite whitespace)
        assert is_phone_allowed("+1234567890") is True
        assert is_phone_allowed("+0987654321") is True
        assert is_phone_allowed("+1111111111") is True

        # Test disallowed number
        assert is_phone_allowed("+2222222222") is False

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_empty_allow_list(self, mock_get_allow_list):
        """Test that empty allow list rejects all numbers for security."""
        mock_get_allow_list.return_value = ""

        # All numbers should be rejected
        assert is_phone_allowed("+1234567890") is False
        assert is_phone_allowed("+0987654321") is False
        assert is_phone_allowed("*") is False

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_empty_phone_number(self, mock_get_allow_list):
        """Test handling of empty phone number."""
        mock_get_allow_list.return_value = "*"

        # Empty phone number should be rejected
        assert is_phone_allowed("") is False
        assert is_phone_allowed(None) is False

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_wildcard_with_other_numbers(self, mock_get_allow_list):
        """Test that wildcard works even when mixed with specific numbers."""
        mock_get_allow_list.return_value = "+1234567890,*,+0987654321"

        # Any number should be allowed due to wildcard
        assert is_phone_allowed("+1234567890") is True
        assert is_phone_allowed("+0987654321") is True
        assert is_phone_allowed("+9999999999") is True

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_single_number(self, mock_get_allow_list):
        """Test validation with single phone number in allow list."""
        mock_get_allow_list.return_value = "+1234567890"

        # Only the specific number should be allowed
        assert is_phone_allowed("+1234567890") is True
        assert is_phone_allowed("+0987654321") is False

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.get_allow_list")
    def test_is_phone_allowed_empty_entries_in_list(self, mock_get_allow_list):
        """Test handling of empty entries in comma-separated list."""
        mock_get_allow_list.return_value = "+1234567890,,+0987654321,"

        # Should work correctly despite empty entries
        assert is_phone_allowed("+1234567890") is True
        assert is_phone_allowed("+0987654321") is True
        assert is_phone_allowed("") is False
        assert is_phone_allowed("+1111111111") is False


class TestClearAllowListCache:
    """Test cases for clear_allow_list_cache function."""

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_clear_allow_list_cache(self, mock_boto3):
        """Test that cache is properly cleared."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "+1234567890"}}

        # First call to populate cache
        result1 = get_allow_list()
        assert result1 == "+1234567890"
        assert mock_ssm.get_parameter.call_count == 1

        # Clear cache
        clear_allow_list_cache()

        # Second call should hit SSM again
        result2 = get_allow_list()
        assert result2 == "+1234567890"
        assert mock_ssm.get_parameter.call_count == 2


class TestIntegrationScenarios:
    """Integration test scenarios combining multiple functions."""

    def setup_method(self):
        """Clear cache before each test."""
        clear_allow_list_cache()

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_full_workflow_with_allowed_number(self, mock_boto3):
        """Test complete workflow with allowed phone number."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "+1234567890,+0987654321"}}

        # Test allowed number
        assert is_phone_allowed("+1234567890") is True

        # Verify SSM was called
        mock_ssm.get_parameter.assert_called_once()

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_full_workflow_with_blocked_number(self, mock_boto3):
        """Test complete workflow with blocked phone number."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.return_value = {"Parameter": {"Value": "+1234567890,+0987654321"}}

        # Test blocked number
        assert is_phone_allowed("+9999999999") is False

        # Verify SSM was called
        mock_ssm.get_parameter.assert_called_once()

    @patch("virtual_assistant_messaging_lambda.services.allow_list_validator.boto3")
    def test_full_workflow_with_ssm_error(self, mock_boto3):
        """Test complete workflow when SSM fails."""
        # Setup mock
        mock_ssm = MagicMock()
        mock_boto3.client.return_value = mock_ssm
        mock_ssm.get_parameter.side_effect = ClientError({"Error": {"Code": "ParameterNotFound"}}, "GetParameter")

        # Test - should reject all numbers when SSM fails
        assert is_phone_allowed("+1234567890") is False

        # Verify SSM was called
        mock_ssm.get_parameter.assert_called_once()
