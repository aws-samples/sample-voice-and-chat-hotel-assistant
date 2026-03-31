# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
CDK construct for Hotel Assistant MCP Server deployment.

This construct deploys the Hotel Assistant MCP Server on AgentCore Runtime,
providing tools for querying hotel documentation and prompts for AI agents.
"""

from aws_cdk import Names, Stack
from aws_cdk import aws_bedrock_agentcore_alpha as agentcore
from aws_cdk import aws_ecr_assets as ecr_assets
from aws_cdk import aws_iam as iam
from cdk_nag import NagSuppressions
from constructs import Construct


class HotelAssistantMCPConstruct(Construct):
    """Construct for Hotel Assistant MCP Server on AgentCore Runtime."""

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        knowledge_base_id: str,
        knowledge_base_arn: str,
        hotels_table_name: str,
        hotels_table_arn: str,
        cognito_discovery_url: str,
        cognito_allowed_clients: list,
        **kwargs,
    ):
        """
        Initialize Hotel Assistant MCP Server construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            knowledge_base_id: Bedrock Knowledge Base ID
            knowledge_base_arn: Bedrock Knowledge Base ARN
            hotels_table_name: DynamoDB hotels table name
            hotels_table_arn: DynamoDB hotels table ARN
            cognito_discovery_url: OpenID Connect discovery URL for JWT validation
            cognito_allowed_clients: List of allowed Cognito client IDs
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Build Docker image
        docker_image = ecr_assets.DockerImageAsset(
            self,
            "MCPServerImage",
            directory="../hotel-pms-simulation",
            file="Dockerfile-mcp",
        )
        runtime_name = Names.unique_resource_name(self, separator="_", max_length=47)

        # Deploy MCP server on AgentCore Runtime
        # Uses same Cognito User Pool for inbound auth as AgentCore Gateway
        # Runtime construct creates its own IAM role with correct service principal
        self.runtime = agentcore.Runtime(
            self,
            "MCPRuntime",
            runtime_name=runtime_name,
            agent_runtime_artifact=agentcore.AgentRuntimeArtifact.from_ecr_repository(
                repository=docker_image.repository,
                tag=docker_image.image_tag,
            ),
            environment_variables={
                "KNOWLEDGE_BASE_ID": knowledge_base_id,
                "AWS_DEFAULT_REGION": Stack.of(self).region,
                "HOTELS_TABLE_NAME": hotels_table_name,
                "LOG_LEVEL": "INFO",
            },
            authorizer_configuration=agentcore.RuntimeAuthorizerConfiguration.using_jwt(
                discovery_url=cognito_discovery_url,
                allowed_clients=cognito_allowed_clients,
            ),
            protocol_configuration=agentcore.ProtocolType.MCP,
        )

        # Grant knowledge base access to runtime role
        self.runtime.add_to_role_policy(
            iam.PolicyStatement(
                sid="KnowledgeBaseAccess",
                actions=[
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate",
                ],
                resources=[knowledge_base_arn],
            )
        )

        # Grant DynamoDB read access for hotels table
        self.runtime.add_to_role_policy(
            iam.PolicyStatement(
                sid="DynamoDBReadAccess",
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Scan",
                    "dynamodb:Query",
                ],
                resources=[hotels_table_arn],
            )
        )

        # Suppress CDK Nag warnings for runtime role
        NagSuppressions.add_resource_suppressions(
            self.runtime.role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "MCP server requires read access to DynamoDB table and knowledge base. "
                    "Scoped to specific resources.",
                }
            ],
            apply_to_children=True,
        )

    @property
    def runtime_arn(self) -> str:
        """Get the AgentCore Runtime ARN."""
        return self.runtime.agent_runtime_arn

    @property
    def runtime_id(self) -> str:
        """Get the AgentCore Runtime ID."""
        return self.runtime.agent_runtime_id

    @property
    def runtime_name(self) -> str:
        """Get the AgentCore Runtime name."""
        return self.runtime.agent_runtime_name
