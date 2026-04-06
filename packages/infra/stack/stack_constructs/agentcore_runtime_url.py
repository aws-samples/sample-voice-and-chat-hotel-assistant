# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Construct for generating AgentCore Runtime URL with URL-encoded ARN."""

from aws_cdk import CustomResource, Duration, Stack
from aws_cdk import aws_lambda as _lambda
from aws_cdk import custom_resources as cr
from cdk_nag import NagSuppressions
from constructs import Construct


class AgentCoreRuntimeUrl(Construct):
    """
    Construct that generates a properly formatted AgentCore Runtime URL.

    AgentCore Runtime requires the ARN to be URL-encoded in the invocation URL.
    This construct uses a custom resource Lambda to perform the URL encoding.
    """

    def __init__(self, scope: Construct, construct_id: str, runtime_arn: str, **kwargs):
        """
        Initialize AgentCore Runtime URL construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            runtime_arn: AgentCore Runtime ARN to URL-encode
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        stack = Stack.of(self)

        # Lambda to URL-encode runtime ARN
        url_fn = _lambda.SingletonFunction(
            self,
            "AgentCoreRuntimeUrlFn",
            uuid="agentcore-runtime-url",
            runtime=_lambda.Runtime.PYTHON_3_14,
            handler="agentcore_runtime_url.handler",
            code=_lambda.Code.from_asset("stack/lambdas"),
            timeout=Duration.seconds(30),
        )

        NagSuppressions.add_resource_suppressions(
            url_fn.role,
            [{"id": "AwsSolutions-IAM4", "reason": "Lambda uses AWS managed policy for CloudWatch logs"}],
        )

        # Custom resource to get URL-encoded runtime URL
        provider = cr.Provider(self, "Provider", on_event_handler=url_fn)
        self.resource = CustomResource(
            self,
            "AgentCoreRuntimeUrl",
            service_token=provider.service_token,
            properties={"RuntimeArn": runtime_arn, "Region": stack.region},
        )

        # Suppress CDK Nag warnings for provider framework
        NagSuppressions.add_resource_suppressions(
            provider.node.find_child("framework-onEvent").node.find_child("ServiceRole"),
            [{"id": "AwsSolutions-IAM4", "reason": "Provider framework uses AWS managed policy"}],
            apply_to_children=True,
        )
        NagSuppressions.add_resource_suppressions(
            provider.node.find_child("framework-onEvent")
            .node.find_child("ServiceRole")
            .node.find_child("DefaultPolicy"),
            [{"id": "AwsSolutions-IAM5", "reason": "Provider framework requires wildcard to invoke Lambda"}],
        )
        NagSuppressions.add_resource_suppressions(
            provider.node.find_child("framework-onEvent"),
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Provider framework Lambda is managed by CDK custom resource framework. "
                    "Runtime version is determined by CDK and cannot be directly controlled.",
                }
            ],
        )

    @property
    def runtime_url(self) -> str:
        """Get the URL-encoded AgentCore Runtime URL."""
        return self.resource.get_att_string("RuntimeUrl")
