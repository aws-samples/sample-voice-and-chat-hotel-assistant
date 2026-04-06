# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AgentCore Memory wrapper construct using L1 constructs.

This construct wraps the aws_cdk.aws_bedrockagentcore.CfnMemory L1 construct
with the same interface as the TypeScript custom constructs, providing
native CloudFormation support with better reliability and performance.
"""

import re

from aws_cdk import Names
from aws_cdk import aws_bedrockagentcore as bedrockagentcore
from aws_cdk import aws_iam as iam
from constructs import Construct


class MemoryStrategyConfig:
    """Configuration for memory strategy."""

    def __init__(
        self,
        strategy_type: str,  # 'SEMANTIC_MEMORY' | 'SUMMARY_MEMORY' | 'USER_PREFERENCE_MEMORY'
        description: str | None = None,
        namespaces: list[str] | None = None,
    ):
        """
        Initialize memory strategy configuration.

        Args:
            strategy_type: Type of memory strategy
            description: Optional description of the strategy
            namespaces: Optional list of namespaces for the strategy
        """
        self.strategy_type = strategy_type
        self.description = description
        self.namespaces = namespaces or []


class AgentCoreMemoryProps:
    """Properties for AgentCore Memory construct."""

    def __init__(
        self,
        event_expiry_duration: int,
        memory_name: str | None = None,
        description: str | None = None,
        memory_strategies: list[MemoryStrategyConfig] | None = None,
        memory_execution_role_arn: str | None = None,
        encryption_key_arn: str | None = None,
    ):
        """
        Initialize AgentCore Memory properties.

        Args:
            event_expiry_duration: Duration in days for event expiry (7-365 days)
            memory_name: Optional name for the memory resource
            description: Optional description of the memory resource
            memory_strategies: Optional list of memory strategy configurations
            memory_execution_role_arn: Optional ARN of execution role for memory
            encryption_key_arn: Optional ARN of KMS key for encryption
        """
        self.memory_name = memory_name
        self.description = description
        self.event_expiry_duration = event_expiry_duration
        self.memory_strategies = memory_strategies or []
        self.memory_execution_role_arn = memory_execution_role_arn
        self.encryption_key_arn = encryption_key_arn


class AgentCoreMemory(Construct):
    """
    AgentCore Memory wrapper construct using L1 constructs.

    This construct provides the same interface as the TypeScript custom constructs
    but uses the native CloudFormation L1 construct for better reliability and performance.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        """
        Initialize AgentCore Memory construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            **kwargs: Keyword arguments that can include AgentCoreMemoryProps or individual properties
        """
        super().__init__(scope, construct_id)

        # Handle both props object and individual keyword arguments for backward compatibility
        if "props" in kwargs:
            props = kwargs["props"]
        else:
            # Create props from individual keyword arguments
            props = AgentCoreMemoryProps(
                event_expiry_duration=kwargs.get("event_expiry_duration"),
                memory_name=kwargs.get("memory_name"),
                description=kwargs.get("description"),
                memory_strategies=kwargs.get("memory_strategies"),
                memory_execution_role_arn=kwargs.get("memory_execution_role_arn"),
                encryption_key_arn=kwargs.get("encryption_key_arn"),
            )

        # Validate properties
        self._validate_properties(props)

        # Generate unique memory name if not provided
        memory_name = props.memory_name or self._generate_unique_name()

        # Map memory strategies to L1 construct format
        memory_strategies_config = self._map_memory_strategies(props.memory_strategies)

        # Create CfnMemory L1 construct
        self._cfn_memory = bedrockagentcore.CfnMemory(
            self,
            "Memory",
            name=memory_name,
            event_expiry_duration=props.event_expiry_duration,
            description=props.description,
            memory_execution_role_arn=props.memory_execution_role_arn,
            encryption_key_arn=props.encryption_key_arn,
            memory_strategies=memory_strategies_config if memory_strategies_config else None,
        )

    def _validate_properties(self, props: AgentCoreMemoryProps) -> None:
        """
        Validate memory properties.

        Args:
            props: Memory properties to validate

        Raises:
            ValueError: If properties are invalid
        """
        # Validate event expiry duration
        if props.event_expiry_duration is None:
            raise ValueError("event_expiry_duration is required")

        if not (7 <= props.event_expiry_duration <= 365):
            raise ValueError("event_expiry_duration must be between 7 and 365 days")

        # Validate memory name format if provided (AWS pattern: ^[a-zA-Z][a-zA-Z0-9_]{0,47}$)
        if props.memory_name is not None:
            if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]{0,47}$", props.memory_name):
                raise ValueError(
                    "memory_name must start with a letter and contain only alphanumeric characters and underscores, "
                    "with a maximum length of 48 characters"
                )

            if len(props.memory_name) > 48:
                raise ValueError("memory_name must be 48 characters or less")

        # Validate ARN formats if provided
        if props.memory_execution_role_arn is not None and not self._is_valid_arn(
            props.memory_execution_role_arn, "iam", "role"
        ):
            raise ValueError("memory_execution_role_arn must be a valid IAM role ARN")

        if props.encryption_key_arn is not None and not self._is_valid_arn(props.encryption_key_arn, "kms", "key"):
            raise ValueError("encryption_key_arn must be a valid KMS key ARN")

        # Validate memory strategies
        for strategy in props.memory_strategies:
            if strategy.strategy_type not in ["SEMANTIC_MEMORY", "SUMMARY_MEMORY", "USER_PREFERENCE_MEMORY"]:
                raise ValueError(
                    f"Invalid strategy_type: {strategy.strategy_type}. "
                    "Must be one of: SEMANTIC_MEMORY, SUMMARY_MEMORY, USER_PREFERENCE_MEMORY"
                )

    def _is_valid_arn(self, arn: str, service: str, resource_type: str) -> bool:
        """
        Validate ARN format.

        Args:
            arn: ARN to validate
            service: Expected AWS service
            resource_type: Expected resource type

        Returns:
            True if ARN is valid, False otherwise
        """
        arn_pattern = rf"^arn:aws:{service}:[^:]*:[^:]*:{resource_type}/.*$"
        return bool(re.match(arn_pattern, arn))

    def _generate_unique_name(self) -> str:
        """
        Generate a unique memory name that complies with AWS pattern ^[a-zA-Z][a-zA-Z0-9_]{0,47}$.

        Uses CDK's Names.unique_resource_name() for stable, deterministic naming.

        Returns:
            Unique memory name (max 48 characters, alphanumeric + underscore only)
        """
        # Generate memory name using CDK's Names utility with memory-specific constraints
        return Names.unique_resource_name(
            self,
            max_length=48,
            separator="_",
            allowed_special_characters="",
        )

    def _map_memory_strategies(self, strategies: list[MemoryStrategyConfig]) -> list[dict] | None:
        """
        Map memory strategy configurations to L1 construct format.

        Args:
            strategies: List of memory strategy configurations

        Returns:
            List of strategy configurations in L1 format, or None if empty
        """
        if not strategies:
            return None

        mapped_strategies = []
        for strategy in strategies:
            # Map strategy type to L1 construct property name
            strategy_config = {}

            if strategy.strategy_type == "SEMANTIC_MEMORY":
                strategy_config["semanticMemoryStrategy"] = {
                    "description": strategy.description,
                    "namespaces": strategy.namespaces if strategy.namespaces else None,
                }
            elif strategy.strategy_type == "SUMMARY_MEMORY":
                strategy_config["summaryMemoryStrategy"] = {
                    "description": strategy.description,
                    "namespaces": strategy.namespaces if strategy.namespaces else None,
                }
            elif strategy.strategy_type == "USER_PREFERENCE_MEMORY":
                strategy_config["userPreferenceMemoryStrategy"] = {
                    "description": strategy.description,
                    "namespaces": strategy.namespaces if strategy.namespaces else None,
                }

            # Remove None values from nested dictionaries
            for key, value in strategy_config.items():
                if isinstance(value, dict):
                    strategy_config[key] = {k: v for k, v in value.items() if v is not None}

            mapped_strategies.append(strategy_config)

        return mapped_strategies

    def grant(self, grantee: iam.IGrantable, *actions: str) -> iam.Grant:
        """
        Grant permissions to the memory resource.

        Args:
            grantee: The principal to grant permissions to
            *actions: Actions to grant (defaults to memory access actions)

        Returns:
            The Grant object
        """
        # Default actions for memory access if none specified
        if not actions:
            actions = [
                "bedrock-agentcore:CreateEvent",
                "bedrock-agentcore:UpdateMemory",
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:RetrieveMemoryRecords",
                "bedrock-agentcore:ListMemoryRecords",
            ]

        return iam.Grant.add_to_principal(
            grantee=grantee,
            actions=list(actions),
            resource_arns=[self.memory_arn],
            scope=self,
        )

    @property
    def memory_id(self) -> str:
        """Get the memory ID."""
        return self._cfn_memory.attr_memory_id

    @property
    def memory_arn(self) -> str:
        """Get the memory ARN."""
        return self._cfn_memory.attr_memory_arn

    @property
    def memory_name(self) -> str:
        """Get the memory name."""
        return self._cfn_memory.name

    @property
    def cfn_memory(self) -> bedrockagentcore.CfnMemory:
        """Get the underlying CfnMemory construct for advanced usage."""
        return self._cfn_memory
