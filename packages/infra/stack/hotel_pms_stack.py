# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CDK stack for simplified Hotel PMS with DynamoDB and API Gateway."""

import json
import os

from aws_cdk import (
    CfnOutput,
    Duration,
    Fn,
    SecretValue,
    Stack,
)
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_secretsmanager as secretsmanager
from aws_cdk import aws_ssm as ssm
from aws_cdk.aws_bedrock_agentcore_alpha import (
    ApiSchema,
    CustomJwtAuthorizer,
    GatewayCredentialProvider,
    McpProtocolConfiguration,
    MCPProtocolVersion,
)
from cdk_nag import NagSuppressions
from constructs import Construct

from .stack_constructs.agentcore_gateway import AgentCoreGateway
from .stack_constructs.agentcore_identity import AgentCoreIdentity
from .stack_constructs.agentcore_observability import AgentCoreObservability
from .stack_constructs.agentcore_runtime_url import AgentCoreRuntimeUrl
from .stack_constructs.hotel_assistant_mcp_construct import HotelAssistantMCPConstruct
from .stack_constructs.hotel_pms_api_construct import HotelPmsApiConstruct
from .stack_constructs.hotel_pms_dynamodb_construct import HotelPMSDynamoDBConstruct
from .stack_constructs.knowledge_base_s3_vectors_construct import KnowledgeBase
from .stack_constructs.openapi_spec_s3_construct import OpenApiSpecS3Construct
from .stack_constructs.s3_constructs import PACEBucket


class HotelPMSStack(Stack):
    """Stack for simplified Hotel PMS system using DynamoDB and API Gateway."""

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create DynamoDB tables with native data loading
        self.dynamodb_construct = HotelPMSDynamoDBConstruct(self, "HotelPMSDynamoDB")

        # Create Lambda function for API Gateway
        self.lambda_function = _lambda.Function(
            self,
            "HotelPmsApiHandler",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="hotel_pms_simulation.handlers.api_gateway_handler.lambda_handler",
            code=_lambda.Code.from_asset("../hotel-pms-simulation/dist/lambda/hotel-pms-handler/lambda.zip"),
            timeout=Duration.minutes(15),
            memory_size=512,
            architecture=_lambda.Architecture.ARM_64,
            environment=self.dynamodb_construct.environment_variables,
        )

        # Grant Lambda permissions to access DynamoDB tables
        self.dynamodb_construct.grant_read(self.lambda_function)
        self.dynamodb_construct.grant_write(self.lambda_function)

        # Suppress CDK-NAG warnings for Lambda function role
        NagSuppressions.add_resource_suppressions(
            self.lambda_function.role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Lambda function uses AWS managed policy AWSLambdaBasicExecutionRole "
                    "for CloudWatch logging, which is the recommended approach.",
                }
            ],
        )

        # Suppress CDK-NAG warnings for Lambda IAM role's default policy
        NagSuppressions.add_resource_suppressions(
            self.lambda_function.role.node.find_child("DefaultPolicy"),
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Lambda function requires wildcard permissions for DynamoDB GSI access "
                    "(/index/*) which is necessary for querying secondary indexes. "
                    "This is scoped to specific tables and is required for the application functionality.",
                }
            ],
        )

        # Create API Gateway with Cognito authentication
        self.api_construct = HotelPmsApiConstruct(
            self,
            "HotelPmsApi",
            lambda_function=self.lambda_function,
        )

        # Create shared bucket for Gateway Target OpenAPI specs

        self.gateway_specs_bucket = PACEBucket(
            self,
            "GatewaySpecsBucket",
        )

        # Deploy OpenAPI spec to S3 with deploy-time URL substitution
        # DeployTimeSubstitutedFile handles CloudFormation token resolution

        # Path relative to app.py location (packages/infra/)
        # Go up to workspace root, then into hotel-pms-simulation package
        infra_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        workspace_root = os.path.dirname(os.path.dirname(infra_dir))
        openapi_spec_path = os.path.join(workspace_root, "packages", "hotel-pms-simulation", "openapi.json")

        self.openapi_spec_s3 = OpenApiSpecS3Construct(
            self,
            "HotelPMSOpenApiSpec",
            bucket=self.gateway_specs_bucket,
            api_gateway_url=self.api_construct.api_endpoint_url,
            openapi_spec_path=openapi_spec_path,
        )

        #######################
        ### AGENTCORE IDENTITY #
        #######################

        # Create AgentCore Identity (OAuth2 Credential Provider)
        # Same for both Cognito and Connect - provides outbound auth to targets
        # Note: Identity observability is configured at the Runtime/Gateway level, not directly

        self.identity = AgentCoreIdentity(
            self,
            "Identity",
            cognito_construct=self.api_construct.cognito_construct,
        )

        #######################
        ### AGENTCORE GATEWAY #
        #######################

        # Get Cognito JWT configuration
        cognito_jwt_config = self.api_construct.cognito_construct.create_jwt_authorizer_config()

        # Create JWT authorizer with Cognito configuration
        jwt_authorizer = CustomJwtAuthorizer(
            discovery_url=cognito_jwt_config.discovery_url,
            allowed_clients=cognito_jwt_config.allowed_clients,
        )

        # Create MCP protocol configuration
        mcp_protocol = McpProtocolConfiguration(
            instructions="Use these tools to interact with the hotel backend to assist customers.",
            supported_versions=[
                MCPProtocolVersion.MCP_2025_03_26,
                MCPProtocolVersion.MCP_2025_06_18,
            ],
        )

        # Create AgentCore Gateway with L2 construct
        self.agentcore_gateway = AgentCoreGateway(
            self,
            "HotelPMS",
            authorizer_config=jwt_authorizer,
            protocol_config=mcp_protocol,
            identity_grant_fn=self.identity.grant,
            description="Hotel Assistant tools",
        )

        # Ensure Gateway waits for OpenAPI spec to be deployed to S3
        self.agentcore_gateway.gateway.node.add_dependency(self.openapi_spec_s3)

        #######################
        ### GATEWAY TARGETS ###
        #######################

        # Get OAuth scopes from Cognito resource server
        resource_server = self.api_construct.cognito_construct.gateway_resource_server
        oauth_scopes = [
            f"{resource_server.user_pool_resource_server_id}/read",
            f"{resource_server.user_pool_resource_server_id}/write",
        ]

        # Add Hotel PMS OpenAPI Target
        self.hotel_pms_target = self.agentcore_gateway.gateway.add_open_api_target(
            "HotelPMSTarget",
            gateway_target_name="HotelPMS",
            api_schema=ApiSchema.from_s3_file(
                bucket=self.gateway_specs_bucket,
                object_key=self.openapi_spec_s3.object_key,
            ),
            credential_provider_configurations=[
                GatewayCredentialProvider.from_oauth_identity_arn(
                    provider_arn=self.identity.credential_provider_arn,
                    scopes=oauth_scopes,
                    secret_arn=self.identity.secret_arn,
                )
            ],
            description="Hotel PMS API target for property management operations",
        )

        # Configure observability for AgentCore Gateway
        AgentCoreObservability(
            self,
            "HotelPMSGatewayObservability",
            resource_arn=self.agentcore_gateway.gateway_arn,
            resource_name="HotelPMSGateway",
        )

        # Create Knowledge Base with S3 Vectors
        # Only hotel_id needs to be filterable for hotel-specific queries
        # AMAZON_BEDROCK_TEXT and AMAZON_BEDROCK_METADATA must be non-filterable (Bedrock-managed fields)
        # All other custom metadata fields are also non-filterable to stay under S3 Vectors 2048 byte limit
        self.knowledge_base = KnowledgeBase(
            self,
            "KnowledgeBase",
            non_filterable_metadata_keys=[
                "AMAZON_BEDROCK_TEXT",  # Bedrock-managed: document text content
                "AMAZON_BEDROCK_METADATA",  # Bedrock-managed: system metadata
                "hotel_name",
                "document_type",
                "language",
                "category",
                "last_updated",
            ],
            s3_prefix="knowledge-base/",
            description="Hotel knowledge base using S3 Vectors for cost-effective document storage and retrieval",
        )

        # Create Hotel Assistant MCP Server
        # Uses same Cognito JWT configuration as AgentCore Gateway
        jwt_config = self.api_construct.jwt_authorizer_config
        self.mcp_server = HotelAssistantMCPConstruct(
            self,
            "HotelAssistantMCP",
            knowledge_base_id=self.knowledge_base.knowledge_base_id,
            knowledge_base_arn=self.knowledge_base.knowledge_base_arn,
            hotels_table_name=self.dynamodb_construct.table_names["hotels"],
            hotels_table_arn=self.dynamodb_construct.table_arns["hotels"],
            cognito_discovery_url=jwt_config["discovery_url"],
            cognito_allowed_clients=jwt_config["allowed_clients"],
        )

        # Configure observability for Hotel Assistant MCP Runtime
        AgentCoreObservability(
            self,
            "HotelAssistantMCPObservability",
            resource_arn=self.mcp_server.runtime_arn,
            resource_name=self.mcp_server.runtime_name,
        )

        # Create single shared Secrets Manager secret for MCP credentials
        # Both Hotel Assistant MCP and Hotel PMS MCP use the same Cognito configuration
        self._mcp_credentials_secret = self._create_mcp_secret(
            "MCPCredentialsSecret",
            self.api_construct.cognito_construct,
        )

        # Suppress CDK Nag warnings for MCP secret
        NagSuppressions.add_resource_suppressions(
            self._mcp_credentials_secret,
            [
                {
                    "id": "AwsSolutions-SMG4",
                    "reason": "MCP credentials secret does not require automatic rotation. "
                    "Cognito client secrets are managed by Cognito and rotated through Cognito APIs.",
                }
            ],
        )

        # Generate MCP configuration JSON and store in SSM Parameter Store
        # Use custom resource to URL-encode the runtime ARN

        # Get URL-encoded runtime URL
        runtime_url_construct = AgentCoreRuntimeUrl(
            self, "HotelAssistantMCPRuntimeUrl", runtime_arn=self.mcp_server.runtime_arn
        )

        # Construct MCP configuration JSON using Fn.sub
        mcp_config_json = Fn.sub(
            json.dumps(
                {
                    "mcpServers": {
                        "hotel-assistant-mcp": {
                            "type": "streamable-http",
                            "url": "${RuntimeUrl}",
                            "authentication": {"type": "cognito", "secretArn": "${SecretArn}"},
                            "systemPrompts": {"chat": "chat_system_prompt", "voice": "voice_system_prompt"},
                        },
                        "hotel-pms-mcp": {
                            "type": "streamable-http",
                            "url": f"https://${{GatewayId}}.gateway.bedrock-agentcore.{self.region}.amazonaws.com/mcp",
                            "authentication": {"type": "cognito", "secretArn": "${SecretArn}"},
                        },
                    }
                },
                indent=2,
            ),
            {
                "RuntimeUrl": runtime_url_construct.runtime_url,
                "GatewayId": self.agentcore_gateway.gateway_id,
                "SecretArn": self._mcp_credentials_secret.secret_arn,
            },
        )

        # Store in SSM Parameter Store
        self._mcp_config_parameter = ssm.StringParameter(
            self,
            "MCPConfigParameter",
            parameter_name="/hotel-assistant/mcp-config",
            string_value=mcp_config_json,
            description="MCP server configuration for virtual assistants",
            tier=ssm.ParameterTier.STANDARD,
        )

        # Suppress CDK Nag warnings for custom resource singleton
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            f"/{self.stack_name}/AWS679f53fac002430cb0da5b7982bd2287/ServiceRole/Resource",
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Custom resource singleton uses AWS managed policy AWSLambdaBasicExecutionRole "
                    "for CloudWatch logging, which is the recommended approach for Lambda functions.",
                }
            ],
        )

        # Suppress CDK Nag warnings for DeployTimeSubstitutedFile
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            f"/{self.stack_name}/HotelPMSOpenApiSpec/DeployOpenApiSpec/CustomResource/Default",
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "DeployTimeSubstitutedFile uses CDK-managed Lambda with latest runtime "
                    "available at CDK version.",
                }
            ],
        )

        # Suppress CDK Nag warnings for DeployTimeSubstitutedFile service role
        stack_name = Stack.of(self).stack_name
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            f"/{stack_name}/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole/Resource",
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "CDK BucketDeployment custom resource uses AWS managed policy "
                    "AWSLambdaBasicExecutionRole for CloudWatch logging.",
                }
            ],
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            f"/{stack_name}/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/ServiceRole/DefaultPolicy/Resource",
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "CDK BucketDeployment requires wildcard permissions for S3 operations "
                    "(GetBucket*, GetObject*, List*, Abort*, DeleteObject*) to deploy files to S3. "
                    "This is a CDK-managed custom resource with scoped permissions to specific buckets.",
                }
            ],
        )

        # Suppress Lambda runtime warnings for CDK-managed custom resources
        # These are upstream Lambda functions we cannot control
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            f"/{stack_name}/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C/Resource",
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "CDK BucketDeployment custom resource Lambda is managed by CDK framework. "
                    "Runtime version is determined by CDK version and cannot be directly controlled.",
                }
            ],
        )

        NagSuppressions.add_resource_suppressions_by_path(
            self,
            f"/{stack_name}/AWS679f53fac002430cb0da5b7982bd2287/Resource",
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Custom resource singleton Lambda is managed by CDK framework. "
                    "Runtime version is determined by CDK version and cannot be directly controlled.",
                }
            ],
        )

        # Stack outputs

        # Output table names
        for table_type, table_name in self.dynamodb_construct.table_names.items():
            CfnOutput(
                self,
                f"{table_type.title()}TableName",
                value=table_name,
                description=f"DynamoDB table name for {table_type}",
            )

        # Output S3 asset information
        CfnOutput(
            self,
            "HotelsAssetBucket",
            value=self.dynamodb_construct.hotels_asset.s3_bucket_name,
            description="S3 bucket containing hotels CSV data",
        )

        CfnOutput(
            self,
            "HotelsAssetKey",
            value=self.dynamodb_construct.hotels_asset.s3_object_key,
            description="S3 key for hotels CSV data",
        )

        # Output API Gateway information
        CfnOutput(
            self,
            "ApiEndpointUrl",
            value=self.api_construct.api_endpoint_url,
            description="API Gateway endpoint URL",
        )

        # Output Cognito information for AgentCore Gateway integration
        CfnOutput(
            self,
            "CognitoUserPoolId",
            value=self.api_construct.cognito_user_pool_id,
            description="Cognito User Pool ID",
        )

        CfnOutput(
            self,
            "CognitoClientId",
            value=self.api_construct.cognito_client_id,
            description="Cognito User Pool Client ID",
        )

        CfnOutput(
            self,
            "CognitoDiscoveryUrl",
            value=self.api_construct.cognito_discovery_url,
            description="OpenID Connect discovery URL for JWT validation",
        )

        # Output JWT authorizer configuration for AgentCore Gateway
        jwt_config = self.api_construct.jwt_authorizer_config
        clients_str = ",".join(jwt_config["allowed_clients"])
        CfnOutput(
            self,
            "JwtAuthorizerConfig",
            value=f"Discovery URL: {jwt_config['discovery_url']}, Allowed Clients: {clients_str}",
            description="JWT authorizer configuration for AgentCore Gateway",
        )

        # Output AgentCore Gateway information
        CfnOutput(
            self,
            "GatewayArn",
            value=self.agentcore_gateway.gateway_arn,
            description="AgentCore Gateway ARN",
        )

        CfnOutput(
            self,
            "GatewayId",
            value=self.agentcore_gateway.gateway_id,
            description="AgentCore Gateway ID",
        )

        CfnOutput(
            self,
            "GatewaySpecsBucketName",
            value=self.gateway_specs_bucket.bucket_name,
            description="Shared S3 bucket for Gateway Target OpenAPI specs",
        )

        CfnOutput(
            self,
            "HotelPMSOpenApiSpecKey",
            value=self.openapi_spec_s3.object_key,
            description="S3 key for Hotel PMS OpenAPI spec",
        )

        CfnOutput(
            self,
            "IdentityProviderArn",
            value=self.identity.credential_provider_arn,
            description="Identity Provider ARN",
        )

        # Output Knowledge Base information
        CfnOutput(
            self,
            "DocumentsBucketName",
            value=self.knowledge_base.bucket_name,
            description="S3 bucket name for knowledge base documents",
            export_name=f"{self.stack_name}-DocumentsBucketName",
        )

        CfnOutput(
            self,
            "KnowledgeBaseId",
            value=self.knowledge_base.knowledge_base_id,
            description="Bedrock Knowledge Base ID",
            export_name=f"{self.stack_name}-KnowledgeBaseId",
        )

        CfnOutput(
            self,
            "DataSourceId",
            value=self.knowledge_base.data_source_id,
            description="Knowledge Base Data Source ID",
            export_name=f"{self.stack_name}-DataSourceId",
        )

        CfnOutput(
            self,
            "KnowledgeBaseArn",
            value=self.knowledge_base.knowledge_base_arn,
            description="Bedrock Knowledge Base ARN",
            export_name=f"{self.stack_name}-KnowledgeBaseArn",
        )

        # Output MCP Server information
        CfnOutput(
            self,
            "MCPServerRuntimeArn",
            value=self.mcp_server.runtime_arn,
            description="Hotel Assistant MCP Server Runtime ARN",
        )

        CfnOutput(
            self,
            "MCPServerRuntimeId",
            value=self.mcp_server.runtime_id,
            description="Hotel Assistant MCP Server Runtime ID",
        )

        CfnOutput(
            self,
            "MCPServerRuntimeName",
            value=self.mcp_server.runtime_name,
            description="Hotel Assistant MCP Server Runtime Name",
        )

        # Output MCP Configuration resources for cross-stack references
        CfnOutput(
            self,
            "MCPConfigParameterName",
            value=self._mcp_config_parameter.parameter_name,
            description="SSM Parameter name containing MCP configuration",
            export_name=f"{self.stack_name}-MCPConfigParameter",
        )

        CfnOutput(
            self,
            "MCPCredentialsSecretArn",
            value=self._mcp_credentials_secret.secret_arn,
            description="Secrets Manager ARN for MCP credentials (shared by all MCP servers)",
            export_name=f"{self.stack_name}-MCPCredentialsSecret",
        )

    def _create_mcp_secret(self, id: str, cognito_construct) -> secretsmanager.Secret:
        """
        Create Secrets Manager secret for MCP credentials.

        Args:
            id: Construct ID for the secret
            cognito_construct: Cognito construct containing user pool and client

        Returns:
            Secrets Manager Secret containing MCP credentials
        """
        return secretsmanager.Secret(
            self,
            id,
            secret_object_value={
                "userPoolId": SecretValue.unsafe_plain_text(cognito_construct.user_pool.user_pool_id),
                "clientId": SecretValue.unsafe_plain_text(cognito_construct.user_pool_client.user_pool_client_id),
                "clientSecret": cognito_construct.user_pool_client.user_pool_client_secret,
                "region": SecretValue.unsafe_plain_text(self.region),
            },
            description="Cognito credentials for MCP server authentication",
        )

    @property
    def table_names(self) -> dict:
        """Get all table names."""
        return self.dynamodb_construct.table_names

    @property
    def table_arns(self) -> dict:
        """Get all table ARNs."""
        return self.dynamodb_construct.table_arns

    @property
    def api_endpoint_url(self) -> str:
        """Get the API Gateway endpoint URL."""
        return self.api_construct.api_endpoint_url

    @property
    def cognito_user_pool_id(self) -> str:
        """Get the Cognito User Pool ID."""
        return self.api_construct.cognito_user_pool_id

    @property
    def cognito_client_id(self) -> str:
        """Get the Cognito User Pool Client ID."""
        return self.api_construct.cognito_client_id

    @property
    def jwt_authorizer_config(self) -> dict:
        """Get JWT authorizer configuration for AgentCore Gateway."""
        return self.api_construct.jwt_authorizer_config

    @property
    def gateway_arn(self) -> str:
        """Get the AgentCore Gateway ARN."""
        return self.agentcore_gateway.gateway_arn

    @property
    def gateway_id(self) -> str:
        """Get the AgentCore Gateway ID."""
        return self.agentcore_gateway.gateway_id

    @property
    def gateway_url(self) -> str:
        """Get the AgentCore Gateway URL endpoint."""
        return self.agentcore_gateway.gateway_url

    @property
    def identity_provider_arn(self) -> str:
        """Get the Identity Provider ARN."""
        return self.identity.credential_provider_arn

    @property
    def knowledge_base_bucket_name(self) -> str:
        """Get the Knowledge Base S3 bucket name."""
        return self.knowledge_base.bucket_name

    @property
    def knowledge_base_id(self) -> str:
        """Get the Knowledge Base ID."""
        return self.knowledge_base.knowledge_base_id

    @property
    def knowledge_base_arn(self) -> str:
        """Get the Knowledge Base ARN."""
        return self.knowledge_base.knowledge_base_arn

    @property
    def knowledge_base_data_source_id(self) -> str:
        """Get the Knowledge Base Data Source ID."""
        return self.knowledge_base.data_source_id

    @property
    def mcp_server_runtime_arn(self) -> str:
        """Get the MCP Server Runtime ARN."""
        return self.mcp_server.runtime_arn

    @property
    def mcp_server_runtime_id(self) -> str:
        """Get the MCP Server Runtime ID."""
        return self.mcp_server.runtime_id

    @property
    def mcp_server_runtime_name(self) -> str:
        """Get the MCP Server Runtime Name."""
        return self.mcp_server.runtime_name

    @property
    def mcp_config_parameter(self) -> ssm.IStringParameter:
        """Get the MCP configuration SSM parameter."""
        return self._mcp_config_parameter

    @property
    def mcp_credentials_secret(self) -> secretsmanager.ISecret:
        """Get the MCP credentials secret (shared by all MCP servers)."""
        return self._mcp_credentials_secret
