# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AgentCore Gateway construct for creating gateways with L2 constructs.

This module provides a CDK construct that creates an AgentCore Gateway using
the L2 construct from aws_cdk.aws_bedrock_agentcore_alpha. It focuses solely
on gateway creation, with identity and authentication configuration provided
as parameters.
"""

import os

from aws_cdk import Duration, Names, Stack
from aws_cdk import aws_bedrockagentcore as agentcore
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk.aws_bedrock_agentcore_alpha import (
    Gateway,
    GatewayExceptionLevel,
    IGatewayAuthorizerConfig,
    IGatewayProtocolConfig,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class AgentCoreGateway(Construct):
    """
    AgentCore Gateway construct using L2 constructs.

    Creates a Gateway with provided authentication and protocol configuration,
    response interceptor Lambda, and proper IAM permissions. Identity and
    target configuration are handled externally.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        authorizer_config: IGatewayAuthorizerConfig,
        protocol_config: IGatewayProtocolConfig,
        identity_grant_fn: callable,
        description: str = None,
        **kwargs,
    ):
        """
        Initialize AgentCore Gateway construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            authorizer_config: JWT authorizer configuration (Cognito or Connect)
            protocol_config: Protocol configuration (e.g., MCP)
            identity_grant_fn: Function to grant identity permissions to gateway role
            description: Optional gateway description
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Create IAM role for gateway
        gateway_role = iam.Role(
            self,
            "GatewayRole",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            description=description or "IAM role for AgentCore Gateway",
        )

        # Grant identity permissions to gateway role (provided by caller)
        identity_grant_fn(gateway_role)

        # Create response interceptor Lambda
        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "lambdas")

        interceptor_lambda = _lambda.Function(
            self,
            "GatewayResponseInterceptor",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="gateway_response_interceptor.lambda_handler",
            code=_lambda.Code.from_asset(lambda_code_path),
            memory_size=128,
            timeout=Duration.seconds(10),
            description="Response interceptor - transforms status codes to 200",
        )

        # Grant Lambda invoke permission
        interceptor_lambda.grant_invoke(gateway_role)

        # Generate unique gateway name
        gateway_name = Names.unique_resource_name(
            self,
            max_length=64,
            separator="-",
            allowed_special_characters="",
        )

        # Create Gateway using L2 construct
        self.gateway = Gateway(
            self,
            "Gateway",
            gateway_name=gateway_name,
            authorizer_configuration=authorizer_config,
            protocol_configuration=protocol_config,
            role=gateway_role,
            exception_level=GatewayExceptionLevel.DEBUG,
            description=description,
        )

        # Configure response interceptor via underlying CfnGateway
        # The L2 construct doesn't yet support interceptors, so we access the L1 resource
        cfn_gateway = self.gateway.node.find_child("Resource")
        cfn_gateway.interceptor_configurations = [
            agentcore.CfnGateway.GatewayInterceptorConfigurationProperty(
                interception_points=["RESPONSE"],
                interceptor=agentcore.CfnGateway.InterceptorConfigurationProperty(
                    lambda_=agentcore.CfnGateway.LambdaInterceptorConfigurationProperty(
                        arn=interceptor_lambda.function_arn
                    )
                ),
                input_configuration=agentcore.CfnGateway.InterceptorInputConfigurationProperty(
                    pass_request_headers=False  # Not needed for response transformation
                ),
            )
        ]

        # Add CDK Nag suppressions for gateway role
        # Use wildcard pattern since the exact Lambda resource name varies
        NagSuppressions.add_resource_suppressions(
            gateway_role,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Gateway role requires wildcard permissions for: "
                    "1) AgentCore workload identity operations, "
                    "2) Lambda invoke permission (includes version/alias wildcards). "
                    "These permissions are scoped to appropriate service namespaces.",
                    # "appliesTo": [
                    #     "Resource::arn:aws:bedrock-agentcore:<AWS::Region>:<AWS::AccountId>:"
                    #     "workload-identity-directory/default/workload-identity/*",
                    #     "Resource::<HotelPMSGatewayResponseInterceptor470C1274.Arn>:*",
                    # ],
                },
            ],
            apply_to_children=True,
        )

        # Add CDK Nag suppressions for interceptor Lambda role
        NagSuppressions.add_resource_suppressions(
            interceptor_lambda.role,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "Lambda uses AWS managed policy AWSLambdaBasicExecutionRole for CloudWatch logging.",
                }
            ],
        )

        # Add CDK Nag suppressions for interceptor Lambda
        NagSuppressions.add_resource_suppressions(
            interceptor_lambda,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Lambda uses Python 3.14 which is the latest available runtime.",
                }
            ],
        )

    @property
    def gateway_arn(self) -> str:
        """Get the AgentCore Gateway ARN."""
        return self.gateway.gateway_arn

    @property
    def gateway_id(self) -> str:
        """Get the AgentCore Gateway ID."""
        return self.gateway.gateway_id

    @property
    def gateway_url(self) -> str:
        """Get the AgentCore Gateway URL endpoint."""
        return f"https://{self.gateway.gateway_id}.gateway.bedrock-agentcore.{Stack.of(self).region}.amazonaws.com"

    @property
    def gateway_target_id(self) -> str:
        """Get the Gateway Target ID (placeholder for now, will be set when targets are added)."""
        return "placeholder-target-id"
