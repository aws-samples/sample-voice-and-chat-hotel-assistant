# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Tests for CloudWatch metrics publishing functionality."""

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from virtual_assistant_livekit.metrics import (
    CloudWatchMetricsPublisher,
    decrement_active_calls,
    get_active_calls,
    get_metrics_publisher,
    increment_active_calls,
    start_metrics_publishing,
    stop_metrics_publishing,
)


class TestCloudWatchMetricsPublisher:
    """Test CloudWatch metrics publisher functionality."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        import tempfile

        with patch.dict(os.environ, {}, clear=True), tempfile.NamedTemporaryFile(delete=False) as tmp:
            publisher = CloudWatchMetricsPublisher(counter_file=tmp.name)

            assert publisher.namespace == "HotelAssistant"
            assert publisher.metric_name == "ActiveCalls"
            assert publisher.service_name == "virtual-assistant-livekit"
            assert publisher.publish_interval == 60
            assert publisher.get_active_calls() == 0

    def test_init_with_environment_variables(self):
        """Test initialization with environment variables."""
        env_vars = {"ECS_SERVICE_NAME": "test-service", "CLOUDWATCH_NAMESPACE": "TestNamespace"}

        with patch.dict(os.environ, env_vars, clear=True):
            publisher = CloudWatchMetricsPublisher()
            assert publisher.service_name == "virtual-assistant-livekit"  # Constructor param takes precedence
            assert publisher.namespace == "HotelAssistant"  # Constructor param takes precedence

    def test_init_with_custom_parameters(self):
        """Test initialization with custom parameters."""
        publisher = CloudWatchMetricsPublisher(
            namespace="CustomNamespace", metric_name="CustomMetric", service_name="custom-service", publish_interval=30
        )

        assert publisher.namespace == "CustomNamespace"
        assert publisher.metric_name == "CustomMetric"
        assert publisher.service_name == "custom-service"
        assert publisher.publish_interval == 30

    @patch("boto3.client")
    def test_init_cloudwatch_client_success(self, mock_boto_client):
        """Test successful CloudWatch client initialization."""
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        publisher = CloudWatchMetricsPublisher()

        mock_boto_client.assert_called_once_with("cloudwatch")
        assert publisher.cloudwatch == mock_client

    @patch("boto3.client")
    def test_init_cloudwatch_client_failure(self, mock_boto_client):
        """Test CloudWatch client initialization failure."""
        mock_boto_client.side_effect = Exception("AWS credentials not found")

        publisher = CloudWatchMetricsPublisher()

        assert publisher.cloudwatch is None

    def test_increment_active_calls(self):
        """Test incrementing active calls counter."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            publisher = CloudWatchMetricsPublisher(counter_file=tmp.name)

            with patch("asyncio.create_task"):  # Mock asyncio.create_task to avoid event loop issues
                assert publisher.get_active_calls() == 0
                publisher.increment_active_calls()
                assert publisher.get_active_calls() == 1
                publisher.increment_active_calls()
                assert publisher.get_active_calls() == 2

    def test_decrement_active_calls(self):
        """Test decrementing active calls counter."""
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            publisher = CloudWatchMetricsPublisher(counter_file=tmp.name)

            with patch("asyncio.create_task"):  # Mock asyncio.create_task to avoid event loop issues
                # Increment first
                publisher.increment_active_calls()
                publisher.increment_active_calls()
                assert publisher.get_active_calls() == 2

                # Decrement
                publisher.decrement_active_calls()
                assert publisher.get_active_calls() == 1

                publisher.decrement_active_calls()
                assert publisher.get_active_calls() == 0

                # Should not go below 0
                publisher.decrement_active_calls()
                assert publisher.get_active_calls() == 0

    @pytest.mark.asyncio
    async def test_publish_metric_no_client(self):
        """Test publishing metric when CloudWatch client is not available."""
        publisher = CloudWatchMetricsPublisher()
        publisher.cloudwatch = None

        result = await publisher.publish_metric()
        assert result is False

    @pytest.mark.asyncio
    async def test_publish_metric_success(self):
        """Test successful metric publication."""
        import tempfile

        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            publisher = CloudWatchMetricsPublisher(counter_file=tmp.name)
            publisher.cloudwatch = mock_client

            with patch("asyncio.create_task"):  # Mock asyncio.create_task to avoid event loop issues
                publisher.increment_active_calls()
                publisher.increment_active_calls()  # Set to 2 active calls

            result = await publisher.publish_metric()

            assert result is True
            mock_client.put_metric_data.assert_called_once()

            # Check the call arguments
            call_args = mock_client.put_metric_data.call_args
            assert call_args[1]["Namespace"] == "HotelAssistant"

            metric_data = call_args[1]["MetricData"][0]
            assert metric_data["MetricName"] == "ActiveCalls"
            assert metric_data["Value"] == 2
            assert metric_data["Unit"] == "Count"

            # Check dimensions
            dimensions = metric_data["Dimensions"]
        assert len(dimensions) == 1
        assert {"Name": "ServiceName", "Value": "virtual-assistant-livekit"} in dimensions

    @pytest.mark.asyncio
    async def test_publish_metric_with_custom_value(self):
        """Test publishing metric with custom value."""
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        publisher = CloudWatchMetricsPublisher()
        publisher.cloudwatch = mock_client

        result = await publisher.publish_metric(value=5)

        assert result is True
        call_args = mock_client.put_metric_data.call_args
        metric_data = call_args[1]["MetricData"][0]
        assert metric_data["Value"] == 5

    @pytest.mark.asyncio
    async def test_publish_metric_client_error(self):
        """Test metric publication with client error."""
        from botocore.exceptions import ClientError

        mock_client = MagicMock()
        mock_client.put_metric_data.side_effect = ClientError(
            {"Error": {"Code": "AccessDenied", "Message": "Access denied"}}, "PutMetricData"
        )

        publisher = CloudWatchMetricsPublisher()
        publisher.cloudwatch = mock_client

        result = await publisher.publish_metric()
        assert result is False

    @pytest.mark.asyncio
    async def test_start_stop_publishing(self):
        """Test starting and stopping metric publishing."""
        mock_client = MagicMock()
        mock_client.put_metric_data.return_value = {"ResponseMetadata": {"HTTPStatusCode": 200}}

        publisher = CloudWatchMetricsPublisher(publish_interval=0.1)  # Fast interval for testing
        publisher.cloudwatch = mock_client

        # Start publishing
        await publisher.start_publishing()
        assert publisher._publishing_task is not None
        assert not publisher._publishing_task.done()

        # Let it run for a short time
        await asyncio.sleep(0.2)

        # Stop publishing
        await publisher.stop_publishing()
        assert publisher._stop_publishing is True

        # Verify metrics were published
        assert mock_client.put_metric_data.call_count >= 1

    @pytest.mark.asyncio
    async def test_publishing_loop_exception_handling(self):
        """Test that publishing loop continues after exceptions."""
        mock_client = MagicMock()
        # First call fails, second succeeds
        mock_client.put_metric_data.side_effect = [
            Exception("Network error"),
            {"ResponseMetadata": {"HTTPStatusCode": 200}},
        ]

        publisher = CloudWatchMetricsPublisher(publish_interval=0.1)
        publisher.cloudwatch = mock_client

        await publisher.start_publishing()
        await asyncio.sleep(0.25)  # Let it run through both calls
        await publisher.stop_publishing()

        # Should have attempted both calls despite the first failure
        assert mock_client.put_metric_data.call_count >= 2


class TestGlobalMetricsFunctions:
    """Test global metrics functions."""

    def setup_method(self):
        """Reset global state before each test."""
        # Reset the singleton publisher
        import virtual_assistant_livekit.metrics

        virtual_assistant_livekit.metrics._singleton.reset()

    def test_get_metrics_publisher_singleton(self):
        """Test that get_metrics_publisher returns the same instance."""
        publisher1 = get_metrics_publisher()
        publisher2 = get_metrics_publisher()

        assert publisher1 is publisher2

    def test_get_metrics_publisher_with_env_vars(self):
        """Test get_metrics_publisher with environment variable overrides."""
        env_vars = {
            "CLOUDWATCH_NAMESPACE": "TestNamespace",
            "CLOUDWATCH_METRIC_NAME": "TestMetric",
            "ECS_SERVICE_NAME": "test-service",
            "METRICS_PUBLISH_INTERVAL": "30",
        }

        with patch.dict(os.environ, env_vars, clear=True):
            # Reset global state
            import virtual_assistant_livekit.metrics

            virtual_assistant_livekit.metrics._singleton.reset()

            publisher = get_metrics_publisher()

            assert publisher.namespace == "TestNamespace"
            assert publisher.metric_name == "TestMetric"
            assert publisher.service_name == "test-service"
            assert publisher.publish_interval == 30

    def test_increment_decrement_active_calls(self):
        """Test global increment/decrement functions."""
        # Reset global state
        import tempfile

        import virtual_assistant_livekit.metrics

        virtual_assistant_livekit.metrics._singleton.reset()

        # Create a temporary counter file for this test
        # Create a temporary counter file for this test
        with (
            tempfile.NamedTemporaryFile(delete=False),
            patch("hotel_assistant_livekit.metrics.CloudWatchMetricsPublisher") as mock_publisher_class,
        ):
            mock_publisher = MagicMock()
            mock_publisher.get_active_calls.return_value = 0
            mock_publisher_class.return_value = mock_publisher

            with patch("asyncio.create_task"):  # Mock asyncio.create_task to avoid event loop issues
                assert get_active_calls() == 0

                increment_active_calls()
                mock_publisher.increment_active_calls.assert_called_once()

                decrement_active_calls()
                mock_publisher.decrement_active_calls.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_stop_metrics_publishing(self):
        """Test global start/stop metrics publishing functions."""
        # Reset global state
        import virtual_assistant_livekit.metrics

        virtual_assistant_livekit.metrics._singleton.reset()

        with patch("virtual_assistant_livekit.metrics.CloudWatchMetricsPublisher") as mock_publisher_class:
            mock_publisher = AsyncMock()
            mock_publisher_class.return_value = mock_publisher

            await start_metrics_publishing()
            mock_publisher.start_publishing.assert_called_once()

            await stop_metrics_publishing()
            mock_publisher.stop_publishing.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_metrics_publishing_no_publisher(self):
        """Test stopping metrics publishing when no publisher exists."""
        # Reset global state
        import virtual_assistant_livekit.metrics

        virtual_assistant_livekit.metrics._singleton.reset()

        # Should not raise an exception
        await stop_metrics_publishing()
