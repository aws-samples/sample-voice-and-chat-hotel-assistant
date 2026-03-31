# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CloudWatch metrics publishing for LiveKit agent active calls tracking."""

import asyncio
import contextlib
import fcntl
import logging
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import boto3
import httpx
from botocore.exceptions import BotoCoreError, ClientError

logger = logging.getLogger(__name__)


class CloudWatchMetricsPublisher:
    """
    Publishes active calls metrics to CloudWatch for ECS auto-scaling.

    This class tracks active calls per task and publishes metrics to CloudWatch
    with appropriate dimensions for service name and task identification.
    Uses file-based counter to track calls across any process architecture.
    """

    def __init__(
        self,
        namespace: str = "HotelAssistant",
        metric_name: str = "ActiveCalls",
        service_name: str = "virtual-assistant-livekit",
        publish_interval: int = 60,
        counter_file: str | None = None,
    ):
        """
        Initialize the CloudWatch metrics publisher.

        Args:
            namespace: CloudWatch namespace for metrics
            metric_name: Name of the metric to publish
            service_name: ECS service name for dimensions
            publish_interval: Interval in seconds between metric publications
            counter_file: Path to counter file for cross-process tracking
        """
        self.namespace = namespace
        self.metric_name = metric_name
        self.service_name = service_name
        self.publish_interval = publish_interval

        # Initialize CloudWatch client
        try:
            self.cloudwatch = boto3.client("cloudwatch")
            logger.info(f"CloudWatch client initialized for namespace: {namespace}")
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch client: {e}")
            self.cloudwatch = None

        # Track active calls using file-based counter for cross-process communication
        self._counter_file = Path(counter_file or os.path.join(tempfile.gettempdir(), "livekit_active_calls.txt"))
        self._ensure_counter_file()
        self._publishing_task: asyncio.Task | None = None
        self._stop_publishing = False

        # ECS task protection settings
        self._ecs_agent_uri = os.environ.get("ECS_AGENT_URI")
        self._task_protection_enabled = False
        self._protection_duration_minutes = int(
            os.environ.get("TASK_PROTECTION_DURATION_MINUTES", "20")
        )  # 20 minutes default

    def _ensure_counter_file(self) -> None:
        """Ensure the counter file exists and is initialized."""
        try:
            if not self._counter_file.exists():
                self._counter_file.write_text("0")
                logger.info(f"Created counter file: {self._counter_file}")
        except Exception as e:
            logger.error(f"Failed to create counter file: {e}")

    def _read_counter(self) -> int:
        """Read the current counter value from file (thread-safe)."""
        try:
            with open(self._counter_file) as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_SH)  # Shared lock for reading
                try:
                    value = int(f.read().strip() or "0")
                    return max(0, value)  # Ensure non-negative
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except (FileNotFoundError, ValueError, OSError) as e:
            logger.warning(f"Failed to read counter file: {e}, returning 0")
            return 0

    def _write_counter(self, value: int) -> None:
        """Write the counter value to file (thread-safe)."""
        try:
            with open(self._counter_file, "w") as f:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Exclusive lock for writing
                try:
                    f.write(str(max(0, value)))  # Ensure non-negative
                    f.flush()
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        except OSError as e:
            logger.error(f"Failed to write counter file: {e}")

    def increment_active_calls(self) -> None:
        """Increment the active calls counter (thread-safe across processes)."""
        current = self._read_counter()
        new_value = current + 1
        self._write_counter(new_value)
        logger.debug(f"Active calls incremented to: {new_value}")

        # Ensure task protection is enabled when there are active calls
        if new_value > 0:
            asyncio.create_task(self._enable_task_protection())

    def decrement_active_calls(self) -> None:
        """Decrement the active calls counter (thread-safe across processes)."""
        current = self._read_counter()
        new_value = max(0, current - 1)  # Ensure non-negative
        self._write_counter(new_value)
        logger.debug(f"Active calls decremented to: {new_value}")

        # Ensure task protection is enabled when there are active calls
        if new_value > 0:
            asyncio.create_task(self._enable_task_protection())
        # Disable task protection when no calls are active
        else:
            asyncio.create_task(self._disable_task_protection())

    def get_active_calls(self) -> int:
        """Get the current active calls count."""
        return self._read_counter()

    async def publish_metric(self, value: int | None = None) -> bool:
        """
        Publish active calls metric to CloudWatch.

        Args:
            value: Optional value to publish. If None, uses current active calls count.

        Returns:
            True if metric was published successfully, False otherwise
        """
        if not self.cloudwatch:
            logger.warning("CloudWatch client not available, skipping metric publication")
            return False

        metric_value = value if value is not None else self.get_active_calls()

        try:
            # Prepare metric data with dimensions
            metric_data = [
                {
                    "MetricName": self.metric_name,
                    "Value": metric_value,
                    "Unit": "Count",
                    "Timestamp": datetime.now(UTC),
                    "Dimensions": [
                        {"Name": "ServiceName", "Value": self.service_name},
                    ],
                }
            ]

            # Publish to CloudWatch
            self.cloudwatch.put_metric_data(Namespace=self.namespace, MetricData=metric_data)

            logger.debug(f"Published metric {self.metric_name}={metric_value} for service={self.service_name}")
            return True

        except (ClientError, BotoCoreError) as e:
            logger.error(f"Failed to publish CloudWatch metric: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing metric: {e}")
            return False

    async def start_publishing(self) -> None:
        """Start the periodic metric publishing task."""
        if self._publishing_task and not self._publishing_task.done():
            logger.warning("Metric publishing already started")
            return

        self._stop_publishing = False
        self._publishing_task = asyncio.create_task(self._publishing_loop())
        logger.info(f"Started metric publishing every {self.publish_interval} seconds")

    async def stop_publishing(self) -> None:
        """Stop the periodic metric publishing task."""
        self._stop_publishing = True

        if self._publishing_task and not self._publishing_task.done():
            try:
                await asyncio.wait_for(self._publishing_task, timeout=5.0)
            except TimeoutError:
                logger.warning("Metric publishing task did not stop gracefully, cancelling")
                self._publishing_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._publishing_task

        logger.info("Stopped metric publishing")

    async def _publishing_loop(self) -> None:
        """Internal loop for periodic metric publishing."""
        while not self._stop_publishing:
            try:
                await self.publish_metric()
                await asyncio.sleep(self.publish_interval)
            except asyncio.CancelledError:
                logger.info("Metric publishing loop cancelled")
                break
            except Exception as e:
                logger.error(f"Error in metric publishing loop: {e}")
                # Continue the loop even if individual publications fail
                await asyncio.sleep(self.publish_interval)

    async def _enable_task_protection(self) -> None:
        """Enable ECS task scale-in protection when calls are active."""
        if not self._ecs_agent_uri:
            logger.debug("ECS_AGENT_URI not available, skipping task protection")
            return

        # Check current protection status to avoid unnecessary API calls
        try:
            from datetime import timedelta

            current_time = datetime.now(UTC)
            current_status = await self.get_task_protection_status()
            protection = current_status.get("protection", {})

            if protection.get("ProtectionEnabled"):
                expiration_date = protection.get("ExpirationDate")
                # Check if protection will expire within 10 minutes
                expires_soon = False
                if expiration_date:
                    try:
                        expiration_time = datetime.fromisoformat(expiration_date)
                        expires_soon = (expiration_time - current_time) <= timedelta(minutes=10)
                    except (ValueError, TypeError) as e:
                        logger.warning(f"Failed to parse expiration date {expiration_date}: {e}")

                if not expires_soon:
                    logger.debug("Task protection already enabled and won't expire soon")
                    self._task_protection_enabled = True
                    return
                else:
                    logger.info("Task protection expires soon, refreshing protection")
        except Exception as e:
            logger.debug(f"Could not check current protection status: {e}")

        try:
            protection_url = f"{self._ecs_agent_uri}/task-protection/v1/state"
            payload = {"ProtectionEnabled": True, "ExpiresInMinutes": self._protection_duration_minutes}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(protection_url, json=payload, headers={"Content-Type": "application/json"})

                if response.status_code == 200:
                    result = response.json()
                    if "protection" in result:
                        self._task_protection_enabled = True
                        expiration = result["protection"].get("ExpirationDate", "unknown")
                        logger.info(f"ECS task protection enabled until {expiration}")
                    else:
                        logger.warning(f"Unexpected task protection response: {result}")
                else:
                    logger.error(f"Failed to enable task protection: HTTP {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error enabling ECS task protection: {e}")

    async def _disable_task_protection(self) -> None:
        """Disable ECS task scale-in protection when no calls are active."""
        if not self._ecs_agent_uri:
            logger.debug("ECS_AGENT_URI not available, skipping task protection")
            return

        # Check current protection status to avoid unnecessary API calls
        try:
            current_status = await self.get_task_protection_status()
            if not current_status.get("protection", {}).get("ProtectionEnabled"):
                logger.debug("Task protection already disabled")
                self._task_protection_enabled = False
                return
        except Exception as e:
            logger.debug(f"Could not check current protection status: {e}")

        try:
            protection_url = f"{self._ecs_agent_uri}/task-protection/v1/state"
            payload = {"ProtectionEnabled": False}

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.put(protection_url, json=payload, headers={"Content-Type": "application/json"})

                if response.status_code == 200:
                    result = response.json()
                    if "protection" in result:
                        self._task_protection_enabled = False
                        logger.info("ECS task protection disabled")
                    else:
                        logger.warning(f"Unexpected task protection response: {result}")
                else:
                    logger.error(f"Failed to disable task protection: HTTP {response.status_code} - {response.text}")

        except Exception as e:
            logger.error(f"Error disabling ECS task protection: {e}")

    async def get_task_protection_status(self) -> dict:
        """Get current ECS task protection status."""
        if not self._ecs_agent_uri:
            return {"error": "ECS_AGENT_URI not available"}

        try:
            protection_url = f"{self._ecs_agent_uri}/task-protection/v1/state"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(protection_url)

                if response.status_code == 200:
                    return response.json()
                else:
                    return {"error": f"HTTP {response.status_code} - {response.text}"}

        except Exception as e:
            return {"error": str(e)}


class _MetricsPublisherSingleton:
    """Singleton container for the metrics publisher instance."""

    def __init__(self):
        self._publisher: CloudWatchMetricsPublisher | None = None

    def get_publisher(self) -> CloudWatchMetricsPublisher:
        """Get or create the metrics publisher instance."""
        if self._publisher is None:
            # Initialize with environment variable overrides if available
            namespace = os.environ.get("CLOUDWATCH_NAMESPACE", "HotelAssistant")
            metric_name = os.environ.get("CLOUDWATCH_METRIC_NAME", "ActiveCalls")
            service_name = os.environ.get("ECS_SERVICE_NAME", "virtual-assistant-livekit")
            publish_interval = int(os.environ.get("METRICS_PUBLISH_INTERVAL", "60"))
            counter_file = os.environ.get("METRICS_COUNTER_FILE")

            self._publisher = CloudWatchMetricsPublisher(
                namespace=namespace,
                metric_name=metric_name,
                service_name=service_name,
                publish_interval=publish_interval,
                counter_file=counter_file,
            )

        return self._publisher

    def reset(self) -> None:
        """Reset the publisher instance (useful for testing)."""
        self._publisher = None


# Module-level singleton instance
_singleton = _MetricsPublisherSingleton()


def get_metrics_publisher() -> CloudWatchMetricsPublisher:
    """
    Get the metrics publisher instance.

    Returns:
        CloudWatchMetricsPublisher instance
    """
    return _singleton.get_publisher()


async def start_metrics_publishing() -> None:
    """Start the global metrics publishing."""
    publisher = get_metrics_publisher()
    await publisher.start_publishing()


async def stop_metrics_publishing() -> None:
    """Stop the metrics publishing."""
    if _singleton._publisher:
        await _singleton._publisher.stop_publishing()


def increment_active_calls() -> None:
    """Increment the global active calls counter."""
    publisher = get_metrics_publisher()
    publisher.increment_active_calls()


def decrement_active_calls() -> None:
    """Decrement the global active calls counter."""
    publisher = get_metrics_publisher()
    publisher.decrement_active_calls()


def get_active_calls() -> int:
    """Get the current global active calls count."""
    publisher = get_metrics_publisher()
    return publisher.get_active_calls()


async def get_task_protection_status() -> dict:
    """Get current ECS task protection status."""
    publisher = get_metrics_publisher()
    return await publisher.get_task_protection_status()
