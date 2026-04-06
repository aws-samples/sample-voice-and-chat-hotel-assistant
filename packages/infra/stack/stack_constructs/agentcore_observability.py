# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AgentCore Observability constructs using L1 constructs.

This module provides a generic observability construct for AgentCore resources:
- AgentCoreObservability: Works with Runtime, Gateway, and Memory resources
- Configures CloudWatch Logs delivery for application logs
- Configures X-Ray delivery for distributed tracing

IMPORTANT: Identity resources do NOT support direct log delivery configuration.
WorkloadIdentity logging is configured at the Runtime or Gateway resource level
that uses the identity resource. See AWS documentation:
https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/observability-configure.html

Usage:
    # For Runtime
    AgentCoreObservability(self, "RuntimeObs",
        resource_arn=runtime.agent_runtime_arn,
        resource_name="VirtualAssistantRuntime")

    # For Gateway
    AgentCoreObservability(self, "GatewayObs",
        resource_arn=gateway.gateway_arn,
        resource_name="HotelPMSGateway")

    # For Memory
    AgentCoreObservability(self, "MemoryObs",
        resource_arn=memory.memory_arn,
        resource_name="ConversationMemory")

    # For Identity - DO NOT USE
    # Identity observability is configured through Runtime/Gateway resources
"""

from aws_cdk import aws_logs as logs
from constructs import Construct


class AgentCoreObservability(Construct):
    """
    Generic AgentCore Observability construct.

    Creates CloudWatch Logs delivery sources and destinations for both
    application logs and traces (X-Ray) for any AgentCore resource
    (Runtime, Gateway, Memory, Identity).

    This construct follows the AWS SDK pattern for enabling observability:
    1. Create CloudWatch Log Group for vended log delivery
    2. Create delivery source for application logs
    3. Create delivery source for traces (X-Ray)
    4. Create delivery destination for logs (CloudWatch Logs)
    5. Create delivery destination for traces (X-Ray)
    6. Create deliveries to connect sources to destinations
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        resource_arn: str,
        resource_name: str,
        log_retention: logs.RetentionDays = logs.RetentionDays.TWO_WEEKS,
        **kwargs,
    ):
        """
        Initialize AgentCore Observability construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            resource_arn: ARN of the AgentCore resource (Runtime, Gateway, Memory, Identity)
            resource_name: Unique name for the resource (used in log group and delivery names)
            log_retention: CloudWatch Logs retention period (default: 2 weeks)
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        self._resource_arn = resource_arn
        self._resource_name = resource_name
        self._log_retention = log_retention

        # Step 0: Create CloudWatch Log Group for vended log delivery
        self._create_log_group()

        # Steps 1-2: Create Delivery Sources for Application Logs and Traces
        self._create_delivery_sources()

        # Steps 3-4: Create Delivery Destinations for Logs and Traces
        self._create_delivery_destinations()

        # Steps 5-6: Create Deliveries (connect sources to destinations)
        self._create_deliveries()

    def _create_log_group(self) -> None:
        """
        Step 0: Create CloudWatch Log Group for vended log delivery.

        Log group name follows AWS pattern: /aws/vendedlogs/bedrock-agentcore/{resource_name}
        """
        self._log_group = logs.LogGroup(
            self,
            "LogGroup",
            log_group_name=f"/aws/vendedlogs/bedrock-agentcore/{self._resource_name}",
            retention=self._log_retention,
        )

    def _create_delivery_sources(self) -> None:
        """
        Steps 1-2: Create Delivery Sources for Application Logs and Traces.

        Delivery sources define what logs/traces to collect from the AgentCore resource.
        """
        # Step 1: Create delivery source for application logs
        self._logs_delivery_source = logs.CfnDeliverySource(
            self,
            "LogsDeliverySource",
            name=f"{self._resource_name}-logs-source",
            log_type="APPLICATION_LOGS",
            resource_arn=self._resource_arn,
        )

        # Step 2: Create delivery source for traces (X-Ray)
        self._traces_delivery_source = logs.CfnDeliverySource(
            self,
            "TracesDeliverySource",
            name=f"{self._resource_name}-traces-source",
            log_type="TRACES",
            resource_arn=self._resource_arn,
        )

    def _create_delivery_destinations(self) -> None:
        """
        Steps 3-4: Create Delivery Destinations for Logs and Traces.

        Delivery destinations define where to send the collected logs/traces.
        """
        # Step 3: Create delivery destination for logs (CloudWatch Logs)
        self._logs_delivery_destination = logs.CfnDeliveryDestination(
            self,
            "LogsDeliveryDestination",
            name=f"{self._resource_name}-logs-destination",
            delivery_destination_type="CWL",
            destination_resource_arn=self._log_group.log_group_arn,
        )

        # Step 4: Create delivery destination for traces (X-Ray)
        self._traces_delivery_destination = logs.CfnDeliveryDestination(
            self,
            "TracesDeliveryDestination",
            name=f"{self._resource_name}-traces-destination",
            delivery_destination_type="XRAY",
        )

    def _create_deliveries(self) -> None:
        """
        Steps 5-6: Create Deliveries to connect sources to destinations.

        Deliveries are the connections that route logs/traces from sources to destinations.
        """
        # Step 5: Create delivery for logs (connect logs source to logs destination)
        self._logs_delivery = logs.CfnDelivery(
            self,
            "LogsDelivery",
            delivery_source_name=self._logs_delivery_source.name,
            delivery_destination_arn=self._logs_delivery_destination.attr_arn,
        )
        self._logs_delivery.add_dependency(self._logs_delivery_source)
        self._logs_delivery.add_dependency(self._logs_delivery_destination)

        # Step 6: Create delivery for traces (connect traces source to traces destination)
        self._traces_delivery = logs.CfnDelivery(
            self,
            "TracesDelivery",
            delivery_source_name=self._traces_delivery_source.name,
            delivery_destination_arn=self._traces_delivery_destination.attr_arn,
        )
        self._traces_delivery.add_dependency(self._traces_delivery_source)
        self._traces_delivery.add_dependency(self._traces_delivery_destination)

    @property
    def log_group(self) -> logs.ILogGroup:
        """Get the CloudWatch Log Group."""
        return self._log_group

    @property
    def log_group_name(self) -> str:
        """Get the CloudWatch Log Group name."""
        return self._log_group.log_group_name

    @property
    def log_group_arn(self) -> str:
        """Get the CloudWatch Log Group ARN."""
        return self._log_group.log_group_arn

    @property
    def logs_delivery_source(self) -> logs.CfnDeliverySource:
        """Get the logs delivery source."""
        return self._logs_delivery_source

    @property
    def logs_delivery_destination(self) -> logs.CfnDeliveryDestination:
        """Get the logs delivery destination."""
        return self._logs_delivery_destination

    @property
    def logs_delivery(self) -> logs.CfnDelivery:
        """Get the logs delivery."""
        return self._logs_delivery

    @property
    def logs_delivery_id(self) -> str:
        """Get the logs delivery ID."""
        return self._logs_delivery.ref

    @property
    def traces_delivery_source(self) -> logs.CfnDeliverySource:
        """Get the traces delivery source."""
        return self._traces_delivery_source

    @property
    def traces_delivery_destination(self) -> logs.CfnDeliveryDestination:
        """Get the traces delivery destination."""
        return self._traces_delivery_destination

    @property
    def traces_delivery(self) -> logs.CfnDelivery:
        """Get the traces delivery."""
        return self._traces_delivery

    @property
    def traces_delivery_id(self) -> str:
        """Get the traces delivery ID."""
        return self._traces_delivery.ref
