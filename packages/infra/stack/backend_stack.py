# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

import hashlib
import os

from aws_cdk import (
    Aws,
    CfnOutput,
    Stack,
)
from aws_cdk import (
    aws_ecr_assets as ecr_assets,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_sns as sns,
)
from aws_cdk.aws_bedrock_agentcore_alpha import (
    AgentRuntimeArtifact,
    ProtocolType,
    Runtime,
    RuntimeNetworkConfiguration,
)
from cdk_nag import NagPackSuppression, NagSuppressions
from constructs import Construct

from .stack_constructs.agentcore_memory import AgentCoreMemory
from .stack_constructs.agentcore_observability import AgentCoreObservability
from .stack_constructs.ecr_constructs import ECRRepositoryConstruct
from .stack_constructs.livekit_ecs_construct import LiveKitECSConstruct
from .stack_constructs.message_buffering_construct import MessageBufferingConstruct
from .stack_constructs.messaging_backend_construct import MessagingBackendConstruct
from .stack_constructs.vpc_construct import VPCConstruct
from .stack_constructs.whatsapp_grant_utils import grant_whatsapp_permissions


class BackendStack(Stack):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        mcp_config_parameter: str = None,  # SSM parameter name for MCP configuration
        mcp_secrets: list = None,  # List of Secrets Manager secrets for MCP credentials
        messaging_topic: sns.ITopic = None,
        messaging_api_endpoint: str = None,
        messaging_client_secret: secretsmanager.ISecret = None,
        virtual_assistant_client_id: str = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        stack_name = Stack.of(self).stack_name

        #######################
        ### ECR REPOSITORY ####
        #######################

        # Create ECR repository for virtual-assistant-chat container
        virtual_assistant_ecr = ECRRepositoryConstruct(
            self,
            "VirtualAssistantECR",
            repository_name="virtual-assistant-chat",
            max_image_count=10,
            untagged_image_expiry_days=1,
        )

        #######################
        ### DOCKER RESOURCES ##
        #######################

        # Get directory path for virtual-assistant-chat package
        virtual_assistant_directory = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "virtual-assistant"
        )

        #######################
        ### AGENTCORE MEMORY ##
        #######################

        # Create AgentCore Memory resource for virtual assistant conversations
        agentcore_memory = AgentCoreMemory(
            self,
            "VirtualAssistantMemory",
            event_expiry_duration=7,  # 7 days for short-term memory usage
            description="Short-term memory for virtual assistant conversations",
        )

        # Configure observability for AgentCore Memory
        AgentCoreObservability(
            self,
            "VirtualAssistantMemoryObservability",
            resource_arn=agentcore_memory.memory_arn,
            resource_name="VirtualAssistantMemory",
        )

        #######################
        ### AGENTCORE RUNTIME #
        #######################

        # Create environment variables for the runtime
        environment_variables = {
            "AWS_REGION": Aws.REGION,
            "AWS_DEFAULT_REGION": Aws.REGION,  # boto3 looks for this environment variable
            "BEDROCK_MODEL_ID": "global.amazon.nova-2-lite-v1:0",
            "MODEL_TEMPERATURE": "0.2",
            "LOG_LEVEL": "INFO",
            "AGENTCORE_MEMORY_ID": agentcore_memory.memory_id,
        }

        # Add messaging API endpoint if provided
        if messaging_api_endpoint:
            environment_variables["MESSAGING_API_ENDPOINT"] = messaging_api_endpoint

        # Add messaging client secret ARN if provided
        if messaging_client_secret:
            environment_variables["MESSAGING_CLIENT_SECRET_ARN"] = messaging_client_secret.secret_arn
        # Add cross-account Bedrock role if provided in context
        bedrock_xacct_role = self.node.try_get_context("bedrock_xacct_role")
        bedrock_xacct_region = self.node.try_get_context("bedrock_xacct_region")

        if bedrock_xacct_role:
            environment_variables["BEDROCK_XACCT_ROLE"] = bedrock_xacct_role

            if bedrock_xacct_region:
                environment_variables["BEDROCK_XACCT_REGION"] = bedrock_xacct_region

        # Add MCP configuration parameter if provided
        if mcp_config_parameter:
            environment_variables["MCP_CONFIG_PARAMETER"] = mcp_config_parameter

        # Add EUM Social configuration if provided (for platform router detection)
        eum_social_phone_id = self.node.try_get_context("eumSocialPhoneNumberId")
        eum_social_cross_account_role = self.node.try_get_context("eumSocialCrossAccountRole")

        if eum_social_phone_id:
            environment_variables["EUM_SOCIAL_PHONE_NUMBER_ID"] = eum_social_phone_id

        if eum_social_cross_account_role:
            environment_variables["EUM_SOCIAL_CROSS_ACCOUNT_ROLE"] = eum_social_cross_account_role

        # Create AgentCore Runtime with L2 construct
        agentcore_runtime = Runtime(
            self,
            "VirtualAssistantRuntime",
            agent_runtime_artifact=AgentRuntimeArtifact.from_asset(
                directory=virtual_assistant_directory,
                file="Dockerfile-chat",
                platform=ecr_assets.Platform.LINUX_ARM64,
            ),
            runtime_name="VirtualAssistantRuntime",
            protocol_configuration=ProtocolType.HTTP,
            network_configuration=RuntimeNetworkConfiguration.using_public_network(),
            environment_variables=environment_variables,
            description="Virtual Assistant AgentCore Runtime",
        )

        # Configure observability for Virtual Assistant Runtime
        AgentCoreObservability(
            self,
            "VirtualAssistantObservability",
            resource_arn=agentcore_runtime.agent_runtime_arn,
            resource_name="VirtualAssistantRuntime",
        )

        if bedrock_xacct_role:
            agentcore_runtime.add_to_role_policy(
                iam.PolicyStatement(
                    sid="BedrockXacctRoleAccess",
                    effect=iam.Effect.ALLOW,
                    actions=["sts:AssumeRole"],
                    resources=[bedrock_xacct_role],
                )
            )

        # Grant AgentCore Memory access to the runtime role
        agentcore_memory.grant(agentcore_runtime.role)

        # Grant Step Functions callback permissions to AgentCore Runtime
        # Required for async task to send success/failure callbacks
        agentcore_runtime.add_to_role_policy(
            iam.PolicyStatement(
                sid="StepFunctionsCallback",
                effect=iam.Effect.ALLOW,
                actions=[
                    "states:SendTaskSuccess",
                    "states:SendTaskFailure",
                ],
                resources=["*"],  # Task tokens are opaque, cannot scope by ARN
            )
        )

        # Add MCP configuration access if provided
        if mcp_config_parameter:
            # Grant SSM parameter read access
            agentcore_runtime.add_to_role_policy(
                iam.PolicyStatement(
                    sid="MCPConfigParameterAccess",
                    effect=iam.Effect.ALLOW,
                    actions=["ssm:GetParameter"],
                    resources=[
                        f"arn:aws:ssm:{self.region}:{self.account}:parameter{mcp_config_parameter}",
                    ],
                )
            )

            # Grant Secrets Manager access for all MCP secrets
            if mcp_secrets:
                secret_arns = [secret.secret_arn for secret in mcp_secrets]
                agentcore_runtime.add_to_role_policy(
                    iam.PolicyStatement(
                        sid="MCPSecretsAccess",
                        effect=iam.Effect.ALLOW,
                        actions=["secretsmanager:GetSecretValue"],
                        resources=secret_arns,
                    )
                )

        # Add messaging client secret access if provided
        if messaging_client_secret:
            agentcore_runtime.add_to_role_policy(
                iam.PolicyStatement(
                    sid="MessagingClientSecretAccess",
                    effect=iam.Effect.ALLOW,
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[messaging_client_secret.secret_arn],
                )
            )

            # Grant messaging API access to AgentCore Runtime
            agentcore_runtime.add_to_role_policy(
                iam.PolicyStatement(
                    sid="MessagingAPIAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "execute-api:Invoke",
                    ],
                    resources=[
                        f"arn:aws:execute-api:{self.region}:{self.account}:*/*/POST/messages",
                        f"arn:aws:execute-api:{self.region}:{self.account}:*/*/PUT/messages/*/status",
                    ],
                )
            )

        # Add EUM Social permissions if configured
        if eum_social_phone_id:
            # Grant EUM Social permissions to AgentCore Runtime
            agentcore_runtime.add_to_role_policy(
                iam.PolicyStatement(
                    sid="EUMSocialAccess",
                    effect=iam.Effect.ALLOW,
                    actions=[
                        "socialmessaging:SendWhatsAppMessage",
                        "socialmessaging:GetWhatsAppMessage",
                    ],
                    resources=[
                        f"arn:aws:socialmessaging:{self.region}:{self.account}:phone-number-id/{eum_social_phone_id}",
                    ],
                )
            )

            # Grant cross-account role assumption if configured
            if eum_social_cross_account_role:
                agentcore_runtime.add_to_role_policy(
                    iam.PolicyStatement(
                        sid="EUMSocialCrossAccountAccess",
                        effect=iam.Effect.ALLOW,
                        actions=["sts:AssumeRole"],
                        resources=[eum_social_cross_account_role],
                    )
                )

        # Add suppressions for AgentCore Runtime execution role
        # The L2 construct creates its own execution role with necessary permissions
        NagSuppressions.add_resource_suppressions(
            agentcore_runtime.role,
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="AgentCore Runtime L2 construct execution role requires wildcard permissions for: "
                    "1) CloudWatch Logs access for runtime logging to AgentCore-specific log groups, "
                    "2) Bedrock AgentCore workload identity operations for service authentication, "
                    "3) Step Functions task token callbacks (task tokens are opaque and cannot be scoped by ARN). "
                    "These permissions are automatically configured by the L2 construct and are scoped to "
                    "appropriate service namespaces for AgentCore functionality.",
                )
            ],
            apply_to_children=True,
        )

        ####################################
        ### ASYNC MESSAGING INTEGRATION ###
        ####################################

        # Check for EUM Social configuration
        eum_social_topic_arn = self.node.try_get_context("eumSocialTopicArn")
        eum_social_phone_id = self.node.try_get_context("eumSocialPhoneNumberId")
        eum_social_cross_account_role = self.node.try_get_context("eumSocialCrossAccountRole")
        whatsapp_allow_list_parameter = self.node.try_get_context("whatsappAllowListParameter")

        # Create messaging integration based on configuration
        if eum_social_topic_arn and eum_social_phone_id:
            # EUM Social WhatsApp integration
            self._create_messaging_integration(
                agentcore_runtime,
                eum_social_topic_arn=eum_social_topic_arn,
                eum_social_phone_id=eum_social_phone_id,
                eum_social_cross_account_role=eum_social_cross_account_role,
                whatsapp_allow_list_parameter=whatsapp_allow_list_parameter,
            )
        elif messaging_topic is None and messaging_client_secret is None:
            # Deploy MessagingBackendConstruct when EUM Social is not available
            messaging_backend = MessagingBackendConstruct(
                self,
                "MessagingBackend",
                callback_urls=[
                    "http://localhost:5173",  # Vite dev server
                    "http://localhost:3000",  # Alternative dev server
                    "http://localhost:4200",  # NX serve frontend
                    "http://localhost:4173",  # Vite preview server
                ],
                oauth_scopes=["chatbot-messaging/write"],
            )

            # Use messaging backend construct outputs for integration
            self._create_messaging_integration(
                agentcore_runtime,
                messaging_topic=messaging_backend.messaging_topic,
                messaging_client_secret=messaging_backend.machine_client_secret,
                virtual_assistant_client_id=messaging_backend.machine_client.user_pool_client_id,
                messaging_api_endpoint=messaging_backend.api.url,
            )
        else:
            # Use provided messaging backend (external messaging stack)
            self._create_messaging_integration(
                agentcore_runtime,
                messaging_topic=messaging_topic,
                messaging_client_secret=messaging_client_secret,
                virtual_assistant_client_id=virtual_assistant_client_id,
                messaging_api_endpoint=messaging_api_endpoint,
            )

        livekit_secret_name = self.node.try_get_context("livekit_secret_name")
        if mcp_config_parameter and mcp_secrets and livekit_secret_name:
            #######################
            ### FARGATE SERVICE ###
            #######################

            # Create VPC
            vpc = VPCConstruct(self, "VPC")

            #######################
            ### LIVEKIT ECS SERVICE
            #######################

            # Create LiveKit ECS service with MCP configuration
            livekit_ecs = LiveKitECSConstruct(
                self,
                "LiveKitECS",
                vpc=vpc.vpc,
                mcp_config_secret=mcp_secrets[0] if mcp_secrets else None,
                mcp_config_parameter=mcp_config_parameter,
                livekit_secret_name=livekit_secret_name,
            )

            CfnOutput(
                self,
                "LiveKitECSClusterName",
                value=livekit_ecs.cluster.cluster_name,
                description="ECS cluster name for LiveKit agents",
            )

            CfnOutput(
                self,
                "LiveKitECSServiceName",
                value=livekit_ecs.service.service_name,
                description="ECS service name for LiveKit agents",
            )

            CfnOutput(
                self,
                "LiveKitTaskRoleArn",
                value=livekit_ecs.task_role.role_arn,
                description="IAM task role ARN for LiveKit agents",
            )

            CfnOutput(
                self,
                "LiveKitLogGroupName",
                value=livekit_ecs.log_group.log_group_name,
                description="CloudWatch log group for LiveKit agents",
            )

        #####################
        ### STACK OUTPUTS ###
        #####################

        CfnOutput(
            self,
            "RegionName",
            value=self.region,
            export_name=f"{Stack.of(self).stack_name}RegionName",
        )

        CfnOutput(
            self,
            "VirtualAssistantECRRepositoryName",
            value=virtual_assistant_ecr.repository_name,
            description="ECR repository name for virtual-assistant-chat",
        )

        CfnOutput(
            self,
            "VirtualAssistantECRRepositoryURI",
            value=virtual_assistant_ecr.repository_uri,
            description="ECR repository URI for virtual-assistant-chat",
        )

        CfnOutput(
            self,
            "AgentCoreMemoryId",
            value=agentcore_memory.memory_id,
            description="AgentCore Memory resource ID for virtual assistant",
            export_name=f"{Stack.of(self).stack_name}AgentCoreMemoryId",
        )

        CfnOutput(
            self,
            "AgentCoreMemoryArn",
            value=agentcore_memory.memory_arn,
            description="AgentCore Memory resource ARN for virtual assistant",
            export_name=f"{Stack.of(self).stack_name}AgentCoreMemoryArn",
        )

        CfnOutput(
            self,
            "AgentCoreRuntimeArn",
            value=agentcore_runtime.agent_runtime_arn,
            description="AgentCore Runtime ARN for virtual assistant chat",
        )

        CfnOutput(
            self,
            "AgentCoreRoleArn",
            value=agentcore_runtime.role.role_arn,
            description="AgentCore Runtime IAM Role ARN",
        )

        # Messaging integration outputs (if any messaging integration is configured)
        if hasattr(self, "message_buffer_table"):
            CfnOutput(
                self,
                "MessageBufferTableName",
                value=self.message_buffer_table.table_name,
                description="DynamoDB table name for message buffering",
            )

            CfnOutput(
                self,
                "MessageBufferTableArn",
                value=self.message_buffer_table.table_arn,
                description="DynamoDB table ARN for message buffering",
            )

            CfnOutput(
                self,
                "BatcherStateMachineArn",
                value=self.state_machine.state_machine_arn,
                description="Step Functions state machine ARN for message batching",
            )

            CfnOutput(
                self,
                "MessageHandlerLambdaArn",
                value=self.message_handler_lambda.function_arn,
                description="Lambda function ARN for message handling",
            )

        # CDK Nag suppressions for BucketDeployment resources (only when MessagingBackendConstruct is deployed)
        if (
            messaging_topic is None
            and messaging_client_secret is None
            and not (eum_social_topic_arn and eum_social_phone_id)
        ):
            # CDK BucketDeployment for runtime config (singleton with auto-generated ID)
            NagSuppressions.add_resource_suppressions_by_path(
                self,
                f"/{stack_name}/Custom::CDKBucketDeployment8693BB64968944B69AAFB0CC9EB8756C",
                [
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": "CDK BucketDeployment helper uses AWS managed policy "
                        "(AWSLambdaBasicExecutionRole) for Lambda execution. This is managed by the "
                        "CDK framework.",
                    },
                    {
                        "id": "AwsSolutions-L1",
                        "reason": "CDK BucketDeployment Lambda uses the latest runtime version available in "
                        "CDK framework.",
                    },
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "CDK BucketDeployment requires wildcard permissions for S3 operations "
                        "(s3:GetBucket*, s3:GetObject*, s3:List*, s3:Abort*, s3:DeleteObject*) to manage "
                        "deployment assets and runtime configuration. These permissions are scoped to "
                        "appropriate S3 operations and required for configuration deployment functionality.",
                    },
                ],
                apply_to_children=True,
            )
            NagSuppressions.add_resource_suppressions_by_path(
                self,
                f"/{stack_name}/AWS679f53fac002430cb0da5b7982bd2287",
                [
                    {
                        "id": "AwsSolutions-IAM4",
                        "reason": "Custom resource singleton Lambda uses AWS managed policy "
                        "(AWSLambdaBasicExecutionRole). Managed by CDK framework.",
                        "appliesTo": [
                            "Policy::arn:<AWS::Partition>:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
                        ],
                    },
                    {
                        "id": "AwsSolutions-L1",
                        "reason": "Custom resource singleton Lambda runtime is managed by CDK framework "
                        "and cannot be directly controlled.",
                    },
                ],
                apply_to_children=True,
            )

    def _create_messaging_integration(
        self,
        agentcore_runtime,
        # EUM Social parameters (optional)
        eum_social_topic_arn: str = None,
        eum_social_phone_id: str = None,
        eum_social_cross_account_role: str = None,
        whatsapp_allow_list_parameter: str = None,
        # Simulated messaging parameters (optional)
        messaging_topic: sns.ITopic = None,
        messaging_client_secret: secretsmanager.ISecret = None,
        virtual_assistant_client_id: str = None,
        messaging_api_endpoint: str = None,
    ) -> None:
        """Create unified messaging integration using MessageBufferingConstruct."""

        # Build environment variables based on integration type
        environment_vars = {
            "AGENTCORE_RUNTIME_ARN": agentcore_runtime.agent_runtime_arn,
            "LOG_LEVEL": "INFO",
            "POWERTOOLS_LOG_LEVEL": "INFO",
        }

        # Add EUM Social environment variables
        if eum_social_phone_id:
            environment_vars.update(
                {
                    "EUM_SOCIAL_PHONE_NUMBER_ID": eum_social_phone_id,
                    "WHATSAPP_ALLOW_LIST_PARAMETER": whatsapp_allow_list_parameter
                    or "/virtual-assistant/whatsapp/allow-list",
                }
            )
            if eum_social_cross_account_role:
                environment_vars["EUM_SOCIAL_CROSS_ACCOUNT_ROLE"] = eum_social_cross_account_role

        # Add simulated messaging environment variables
        if messaging_api_endpoint and messaging_client_secret:
            environment_vars.update(
                {
                    "MESSAGING_API_ENDPOINT": messaging_api_endpoint,
                    "MESSAGING_CLIENT_SECRET_ARN": messaging_client_secret.secret_arn,
                }
            )

        # Create message buffering construct (replaces MessageProcessingConstruct)
        message_buffering = MessageBufferingConstruct(
            self,
            "MessageBuffering",
            agentcore_runtime_arn=agentcore_runtime.agent_runtime_arn,
            environment_variables=environment_vars,
        )

        # Configure EUM Social integration
        if eum_social_topic_arn and eum_social_phone_id:
            # Subscribe to external SNS topic
            external_topic = sns.Topic.from_topic_arn(self, "EUMSocialTopic", eum_social_topic_arn)
            message_buffering.subscribe_to_sns_topic(external_topic)

            # Grant WhatsApp permissions using new grant pattern
            grant_whatsapp_permissions(
                grantee=message_buffering.message_handler_lambda,
                cross_account_role=eum_social_cross_account_role,
                scope=self,
            )

            # Add CDK Nag suppressions for EUM Social permissions
            NagSuppressions.add_resource_suppressions(
                message_buffering.message_handler_lambda,
                [
                    NagPackSuppression(
                        id="AwsSolutions-IAM5",
                        reason="Lambda function requires wildcard permissions for: 1) SSM parameter access "
                        f"(arn:aws:ssm:{self.region}:{self.account}:parameter/virtual-assistant/whatsapp/*) "
                        "for WhatsApp allow list configuration, 2) EUM Social API access (*) as the service "
                        "doesn't support resource-level permissions. These permissions are required for "
                        "WhatsApp messaging functionality and are scoped to appropriate service namespaces.",
                        applies_to=[
                            f"Resource::arn:aws:ssm:{self.region}:{self.account}:parameter/virtual-assistant/whatsapp/*",
                            "Resource::*",
                        ],
                    ),
                ],
                apply_to_children=True,
            )

            # Add CDK outputs for EUM Social
            CfnOutput(
                self,
                "EUMSocialTopicArn",
                value=eum_social_topic_arn,
                description="EUM Social SNS topic ARN used for WhatsApp message integration",
                export_name=f"{Stack.of(self).stack_name}EUMSocialTopicArn",
            )
            CfnOutput(
                self,
                "EUMSocialPhoneNumberId",
                value=eum_social_phone_id,
                description="EUM Social phone number ID for sending WhatsApp messages",
                export_name=f"{Stack.of(self).stack_name}EUMSocialPhoneNumberId",
            )

        # Configure simulated messaging integration
        elif messaging_topic and messaging_client_secret:
            # Subscribe with filtering
            recipient_id_filter = self.node.try_get_context("recipient_id_filter")
            if recipient_id_filter is None and virtual_assistant_client_id is not None:
                recipient_id_filter = virtual_assistant_client_id

            if recipient_id_filter:
                message_buffering.subscribe_to_sns_topic(
                    messaging_topic,
                    filter_policy={
                        "recipientId": sns.SubscriptionFilter.string_filter(allowlist=[recipient_id_filter])
                    },
                )
            else:
                message_buffering.subscribe_to_sns_topic(messaging_topic)

            # Grant messaging API permissions
            message_buffering.message_handler_lambda.add_to_role_policy(
                iam.PolicyStatement(
                    sid="MessagingAPIAccess",
                    effect=iam.Effect.ALLOW,
                    actions=["execute-api:Invoke"],
                    resources=[f"arn:aws:execute-api:{self.region}:{self.account}:*/*/PUT/messages/*/status"],
                )
            )
            NagSuppressions.add_resource_suppressions(
                message_buffering.message_handler_lambda,
                [
                    {
                        "id": "AwsSolutions-IAM5",
                        "reason": "Lambda requires wildcard in execute-api resource ARN to invoke "
                        "PUT /messages/*/status across all API Gateway stages and API IDs. "
                        "The permission is scoped to a specific route pattern.",
                    },
                ],
                apply_to_children=True,
            )
            message_buffering.message_handler_lambda.add_to_role_policy(
                iam.PolicyStatement(
                    sid="MessagingClientSecretAccess",
                    effect=iam.Effect.ALLOW,
                    actions=["secretsmanager:GetSecretValue"],
                    resources=[messaging_client_secret.secret_arn],
                )
            )

            # Add CDK output for simulated messaging
            CfnOutput(
                self,
                "MessageFilteringRecipientId",
                value=recipient_id_filter if recipient_id_filter else "No filtering (all messages processed)",
                description="Recipient ID used for SNS message filtering. "
                "Only messages with this recipientId will be processed.",
                export_name=f"{Stack.of(self).stack_name}MessageFilteringRecipientId",
            )

        # Add CDK Nag suppression for AgentCore Runtime ARN wildcard permission
        # This suppression is needed because the AgentCore Runtime ARN requires a wildcard suffix
        NagSuppressions.add_resource_suppressions_by_path(
            self,
            f"/{self.stack_name}/MessageBuffering/InvokeAgentCoreLambda/ServiceRole/DefaultPolicy/Resource",
            [
                NagPackSuppression(
                    id="AwsSolutions-IAM5",
                    reason="Lambda function requires wildcard permissions for AgentCore Runtime ARN "
                    "access (*) as the runtime ARN is dynamically generated and requires wildcard "
                    "suffix for proper invocation. This permission is scoped to the specific "
                    "AgentCore Runtime resource and required for message processing functionality.",
                ),
            ],
        )

        # Store references for outputs (updated to use message buffering construct)
        self.message_buffer_table = message_buffering.message_buffer_table
        self.state_machine = message_buffering.state_machine
        self.message_handler_lambda = message_buffering.message_handler_lambda

    def _generate_unique_suffix(self) -> str:
        """Generate a unique suffix based on account, stack name, and region."""
        # Combine account, stack name, and region
        unique_string = f"{self.account}-{self.stack_name}-{self.region}"

        # Create SHA256 hash and take first 8 characters
        hash_object = hashlib.sha256(unique_string.encode())
        hash_hex = hash_object.hexdigest()

        # Return first 8 characters as suffix
        return hash_hex[:8]
