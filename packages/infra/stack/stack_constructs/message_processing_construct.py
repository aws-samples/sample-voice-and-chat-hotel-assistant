# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import os

from aws_cdk import Duration, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_lambda_event_sources as lambda_event_sources
from aws_cdk import aws_sqs as sqs
from cdk_nag import NagPackSuppression, NagSuppressions
from constructs import Construct


class MessageProcessingConstruct(Construct):
    """
    CDK construct that encapsulates SQS queue, DLQ, and Lambda function for message processing.

    This construct creates a complete message processing infrastructure including:
    - SQS queue for incoming messages
    - Dead letter queue for failed message processing
    - Lambda function to process messages and invoke AgentCore Runtime
    - Proper IAM permissions and CDK Nag suppressions
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        agentcore_runtime_arn: str,
        environment_variables: dict[str, str] | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the MessageProcessingConstruct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            agentcore_runtime_arn: ARN of the AgentCore runtime to invoke
            environment_variables: Optional environment variables for the Lambda function
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Get stack name for resource naming
        stack_name = Stack.of(self).stack_name

        # Merge default environment variables with provided ones
        default_env_vars = {
            "AGENTCORE_RUNTIME_ARN": agentcore_runtime_arn,
            "LOG_LEVEL": "INFO",
            "POWERTOOLS_LOG_LEVEL": "INFO",
        }

        if environment_variables:
            default_env_vars.update(environment_variables)

        # Create dead letter queue for failed message processing
        self.dead_letter_queue = sqs.Queue(
            self,
            "MessageProcessingDLQ",
            queue_name=f"{stack_name}-message-processing-dlq",
            retention_period=Duration.days(14),
            enforce_ssl=True,
        )

        # Create SQS queue for message processing
        self.processing_queue = sqs.Queue(
            self,
            "MessageProcessingQueue",
            queue_name=f"{stack_name}-message-processing",
            visibility_timeout=Duration.seconds(90),
            dead_letter_queue=sqs.DeadLetterQueue(
                max_receive_count=3,
                queue=self.dead_letter_queue,
            ),
            enforce_ssl=True,
        )

        # Get Lambda package path
        lambda_package_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "virtual-assistant",
            "virtual-assistant-messaging-lambda",
            "dist",
            "lambda",
            "message-processor",
            "lambda.zip",
        )

        # Create message processor Lambda function
        self.lambda_function = _lambda.Function(
            self,
            "MessageProcessorLambda",
            function_name=f"{stack_name}-message-processor",
            description="Process messages from SQS queue and invoke AgentCore Runtime",
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,
            handler="virtual_assistant_messaging_lambda.handlers.message_processor.lambda_handler",
            code=_lambda.Code.from_asset(lambda_package_path),
            memory_size=128,
            timeout=Duration.seconds(30),
            environment=default_env_vars,
        )

        # Grant SQS permissions to Lambda
        self.processing_queue.grant_consume_messages(self.lambda_function)

        # Grant AgentCore Runtime invocation permissions
        # Both actions are required when using X-Amzn-Bedrock-AgentCore-Runtime-User-Id header
        self.lambda_function.add_to_role_policy(
            iam.PolicyStatement(
                sid="AgentCoreRuntimeInvoke",
                effect=iam.Effect.ALLOW,
                actions=[
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock-agentcore:InvokeAgentRuntimeForUser",
                ],
                resources=[f"{agentcore_runtime_arn}*"],
            )
        )

        # Add SQS event source to Lambda
        self.lambda_function.add_event_source(
            lambda_event_sources.SqsEventSource(
                self.processing_queue,
                batch_size=100,
                max_batching_window=Duration.seconds(3),
                report_batch_item_failures=True,
            )
        )

        # Add CDK Nag suppressions with specific justifications
        NagSuppressions.add_resource_suppressions(
            self.lambda_function,
            [
                NagPackSuppression(
                    id="AwsSolutions-L1",
                    reason="Using Python 3.13 runtime which is the latest available version for Lambda",
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM4",
                    reason="AWS managed policy AWSLambdaBasicExecutionRole is required for Lambda execution "
                    "and follows AWS best practices for basic Lambda logging permissions",
                ),
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="Lambda function requires wildcard permissions for: 1) CloudWatch Logs access "
                    "(arn:aws:logs:*:*:log-group:* and log-stream:*) for runtime logging, 2) AgentCore "
                    "Runtime invocation (bedrock-agentcore:*) for AI agent operations, 3) AgentCore Runtime "
                    "ARN wildcard (*) for runtime resource access. These permissions are scoped to appropriate "
                    "service namespaces and required for message processing functionality.",
                    applies_to=[
                        "Action::bedrock-agentcore:*",
                        "Resource::arn:aws:logs:*:*:*",
                        "Resource::*",
                    ],
                ),
            ],
            apply_to_children=True,
        )
