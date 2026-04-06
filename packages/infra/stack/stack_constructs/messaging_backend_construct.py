# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
MessagingBackendConstruct - CDK construct for messaging backend infrastructure.

This construct encapsulates all messaging backend components including:
- DynamoDB table for message storage with GSI
- SNS topic for message publishing
- Lambda function with APIGatewayRestResolver
- API Gateway with Cognito authorization
- Cognito User Pool for authentication
- WAF Web ACL for API protection
- Secrets Manager for machine client credentials
"""

import hashlib
import os

from aws_cdk import (
    Aws,
    Duration,
    RemovalPolicy,
    SecretValue,
    Stack,
)
from aws_cdk import (
    aws_apigateway as apigw,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from aws_cdk import (
    aws_dynamodb as dynamodb,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_lambda as _lambda,
)
from aws_cdk import (
    aws_logs as logs,
)
from aws_cdk import (
    aws_secretsmanager as secretsmanager,
)
from aws_cdk import (
    aws_sns as sns,
)
from aws_cdk import (
    aws_wafv2 as wafv2,
)
from cdk_nag import NagSuppressions
from constructs import Construct

from .cognito_constructs import CognitoConstruct
from .custom_resource_construct import CustomResourceConstruct
from .s3_constructs import PACEBucket


class MessagingBackendConstruct(Construct):
    """
    CDK construct that encapsulates the entire messaging backend infrastructure.

    This construct creates a complete messaging backend that can be conditionally
    deployed when EUM Social is not available. It includes all necessary components
    for a simulated messaging platform integration.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        callback_urls: list[str] | None = None,
        oauth_scopes: list[str] | None = None,
        **kwargs,
    ) -> None:
        """
        Initialize the MessagingBackendConstruct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            callback_urls: OAuth callback URLs for Cognito
            oauth_scopes: OAuth scopes for Cognito
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        # Get stack name for resource naming
        stack_name = Stack.of(self).stack_name

        # Set default values
        if callback_urls is None:
            callback_urls = [
                "http://localhost:5173",  # Vite dev server
                "http://localhost:3000",  # Alternative dev server
                "http://localhost:4200",  # NX serve frontend
                "http://localhost:4173",  # Vite preview server
            ]

        if oauth_scopes is None:
            oauth_scopes = ["aws.cognito.signin.user.admin"]  # Use standard scope

        ########################
        ### DYNAMODB TABLE ###
        ########################

        # Create DynamoDB table for message storage
        self.messages_table = dynamodb.Table(
            self,
            "ChatbotMessagesTable",
            table_name=f"{stack_name}-Messages",
            # Partition key: conversationId (format: senderId#recipientId)
            partition_key=dynamodb.Attribute(
                name="conversationId",
                type=dynamodb.AttributeType.STRING,
            ),
            # Sort key: timestamp (ISO8601 format)
            sort_key=dynamodb.Attribute(
                name="timestamp",
                type=dynamodb.AttributeType.STRING,
            ),
            # On-demand billing mode for cost optimization and auto-scaling
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            # Point-in-time recovery for data protection
            point_in_time_recovery_specification=dynamodb.PointInTimeRecoverySpecification(
                point_in_time_recovery_enabled=True
            ),
            # Removal policy for development
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create Global Secondary Index for message ID lookups
        self.messages_table.add_global_secondary_index(
            index_name="MessageIdIndex",
            # Partition key: messageId (UUID)
            partition_key=dynamodb.Attribute(
                name="messageId",
                type=dynamodb.AttributeType.STRING,
            ),
            # Projection: Include all attributes for complete message retrieval
            projection_type=dynamodb.ProjectionType.ALL,
        )

        ##################
        ### SNS TOPIC ###
        ##################

        # Create SNS topic for message publishing
        self.messaging_topic = sns.Topic(
            self,
            "ChatbotMessagingTopic",
            topic_name=f"{stack_name}-Messages",
            display_name="Chatbot Messaging Topic",
            # Enable server-side encryption
            master_key=None,  # Use AWS managed key for cost optimization
        )

        # Add topic policy to require SSL
        self.messaging_topic.add_to_resource_policy(
            iam.PolicyStatement(
                sid="DenyInsecureConnections",
                effect=iam.Effect.DENY,
                principals=[iam.AnyPrincipal()],
                actions=["SNS:Publish"],
                resources=[self.messaging_topic.topic_arn],
                conditions={"Bool": {"aws:SecureTransport": "false"}},
            )
        )

        ######################
        ### LAMBDA FUNCTION ###
        ######################

        # Get the path to the Lambda package zip file
        lambda_package_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
            "chatbot-messaging-backend",
            "dist",
            "lambda",
            "chatbot-messaging-handler",
            "lambda.zip",
        )

        # Create Lambda function for messaging API
        self.messaging_lambda = _lambda.Function(
            self,
            "ChatbotMessagingLambda",
            function_name=f"{stack_name}-MessagingAPI",
            description="Chatbot messaging backend API with APIGatewayRestResolver",
            # Runtime configuration
            runtime=_lambda.Runtime.PYTHON_3_14,
            architecture=_lambda.Architecture.ARM_64,  # Use ARM64 for better performance and cost
            handler="chatbot_messaging_backend.handlers.lambda_handler.lambda_handler",
            # Code location - relative to infra package directory
            code=_lambda.Code.from_asset(lambda_package_path),
            # Performance configuration
            memory_size=256,  # Sufficient for API operations and DynamoDB/SNS calls
            timeout=Duration.seconds(29),  # Appropriate for API Gateway timeout
            # Environment variables
            environment={
                "DYNAMODB_TABLE_NAME": self.messages_table.table_name,
                "SNS_TOPIC_ARN": self.messaging_topic.topic_arn,
            },
            # Reserved concurrency for cost control
            reserved_concurrent_executions=10,
        )

        # Grant DynamoDB permissions to Lambda
        self.messages_table.grant_read_write_data(self.messaging_lambda)

        # Grant SNS publish permissions to Lambda
        self.messaging_topic.grant_publish(self.messaging_lambda)

        # CDK Nag suppressions for Lambda function
        NagSuppressions.add_resource_suppressions(
            self.messaging_lambda,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "Using Python 3.13 runtime which is the latest available version",
                }
            ],
        )

        # CDK Nag suppressions for Lambda service role
        NagSuppressions.add_resource_suppressions(
            self.messaging_lambda,
            [
                {
                    "id": "AwsSolutions-IAM4",
                    "reason": "AWS managed policy AWSLambdaBasicExecutionRole is required for Lambda execution",
                },
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "DynamoDB GSI access requires wildcard permissions for index operations",
                },
            ],
            apply_to_children=True,
        )

        ######################
        ### API GATEWAY ###
        ######################

        # Create CloudWatch Log Group for API Gateway access logs
        self.api_log_group = logs.LogGroup(
            self,
            "APILogGroup",
            retention=logs.RetentionDays.ONE_WEEK,  # Cost optimization for prototype
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create REST API Gateway
        self.api = apigw.RestApi(
            self,
            "ChatbotMessagingAPI",
            rest_api_name=f"{stack_name}-API",
            description="Chatbot messaging backend REST API with Cognito authorization",
            # API Gateway configuration
            deploy=True,
            deploy_options=apigw.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,  # Requests per second
                throttling_burst_limit=200,  # Burst capacity
                # Enable logging for monitoring
                access_log_destination=apigw.LogGroupLogDestination(self.api_log_group),
                access_log_format=apigw.AccessLogFormat.json_with_standard_fields(
                    caller=True,
                    http_method=True,
                    ip=True,
                    protocol=True,
                    request_time=True,
                    resource_path=True,
                    response_length=True,
                    status=True,
                    user=True,
                ),
                # Enable X-Ray tracing
                tracing_enabled=True,
                # Enable metrics
                metrics_enabled=True,
                # Enable CloudWatch logging for all methods
                logging_level=apigw.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
            ),
            # CORS configuration for web clients
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,  # Configure specific origins in production
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=[
                    "Content-Type",
                    "X-Amz-Date",
                    "Authorization",
                    "X-Api-Key",
                    "X-Amz-Security-Token",
                    "X-Amz-User-Agent",
                ],
                allow_credentials=True,
            ),
            # Binary media types (if needed for future file uploads)
            binary_media_types=["application/octet-stream"],
            # Endpoint configuration
            endpoint_configuration=apigw.EndpointConfiguration(types=[apigw.EndpointType.REGIONAL]),
            # Policy for secure access
            policy=iam.PolicyDocument(
                statements=[
                    iam.PolicyStatement(
                        sid="AllowSecureAccess",
                        effect=iam.Effect.ALLOW,
                        principals=[iam.AnyPrincipal()],
                        actions=["execute-api:Invoke"],
                        resources=["*"],
                        conditions={"Bool": {"aws:SecureTransport": "true"}},
                    )
                ]
            ),
        )

        ######################
        ### WAF WEB ACL ###
        ######################

        # Create CloudWatch Log Group for WAF logs
        self.waf_log_group = logs.LogGroup(
            self,
            "ChatbotMessagingWAFLogGroup",
            log_group_name=f"aws-waf-logs-{stack_name}-WAF",
            retention=logs.RetentionDays.ONE_WEEK,  # Cost optimization for prototype
            removal_policy=RemovalPolicy.DESTROY,
        )

        # Create WAF Web ACL with AWS managed rule groups
        self.web_acl = wafv2.CfnWebACL(
            self,
            "ChatbotMessagingWebACL",
            name=f"{stack_name}-WebACL",
            description="WAF Web ACL for Chatbot Messaging API with AWS managed rules",
            scope="REGIONAL",  # For API Gateway (CloudFront would use CLOUDFRONT)
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            # Configure managed rule groups
            rules=[
                # AWS Core Rule Set - protects against OWASP Top 10 vulnerabilities
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesCommonRuleSet",
                    priority=1,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesCommonRuleSet",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesCommonRuleSetMetric",
                        sampled_requests_enabled=True,
                    ),
                ),
                # Known Bad Inputs - protects against known malicious inputs
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesKnownBadInputsRuleSet",
                    priority=2,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesKnownBadInputsRuleSet",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesKnownBadInputsRuleSetMetric",
                        sampled_requests_enabled=True,
                    ),
                ),
                # Amazon IP Reputation List - blocks requests from known malicious IP addresses
                wafv2.CfnWebACL.RuleProperty(
                    name="AWSManagedRulesAmazonIpReputationList",
                    priority=3,
                    override_action=wafv2.CfnWebACL.OverrideActionProperty(none={}),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        managed_rule_group_statement=wafv2.CfnWebACL.ManagedRuleGroupStatementProperty(
                            vendor_name="AWS",
                            name="AWSManagedRulesAmazonIpReputationList",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="AWSManagedRulesAmazonIpReputationListMetric",
                        sampled_requests_enabled=True,
                    ),
                ),
                # Rate limiting rule - prevent abuse by limiting requests per IP
                wafv2.CfnWebACL.RuleProperty(
                    name="RateLimitRule",
                    priority=4,
                    action=wafv2.CfnWebACL.RuleActionProperty(
                        block=wafv2.CfnWebACL.BlockActionProperty(
                            custom_response=wafv2.CfnWebACL.CustomResponseProperty(
                                response_code=429,
                                custom_response_body_key="TooManyRequests",
                            )
                        )
                    ),
                    statement=wafv2.CfnWebACL.StatementProperty(
                        rate_based_statement=wafv2.CfnWebACL.RateBasedStatementProperty(
                            limit=2000,  # 2000 requests per 5-minute window per IP
                            aggregate_key_type="IP",
                        )
                    ),
                    visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                        cloud_watch_metrics_enabled=True,
                        metric_name="RateLimitRuleMetric",
                        sampled_requests_enabled=True,
                    ),
                ),
            ],
            # Custom response bodies
            custom_response_bodies={
                "TooManyRequests": wafv2.CfnWebACL.CustomResponseBodyProperty(
                    content_type="APPLICATION_JSON",
                    content='{"error": "Too many requests. Please try again later."}',
                )
            },
            # Enable logging
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                cloud_watch_metrics_enabled=True,
                metric_name=f"{stack_name}WebACLMetric",
                sampled_requests_enabled=True,
            ),
        )

        # Create WAF logging configuration
        self.waf_logging_config = wafv2.CfnLoggingConfiguration(
            self,
            "ChatbotMessagingWAFLoggingConfig",
            resource_arn=self.web_acl.attr_arn,
            log_destination_configs=[self.waf_log_group.log_group_arn],
        )

        # Associate WAF Web ACL with API Gateway
        self.web_acl_association = wafv2.CfnWebACLAssociation(
            self,
            "ChatbotMessagingWebACLAssociation",
            resource_arn=f"arn:aws:apigateway:{Stack.of(self).region}::/restapis/{self.api.rest_api_id}/stages/prod",
            web_acl_arn=self.web_acl.attr_arn,
        )

        # Ensure the association waits for the API Gateway deployment
        self.web_acl_association.node.add_dependency(self.api.deployment_stage)

        ######################
        ### CONFIGURATION STORAGE ###
        ######################

        # Create private S3 bucket for storing runtime-config.json
        self.config_bucket = PACEBucket(self, "ConfigBucket")

        #######################
        ### COGNITO USER POOL ###
        #######################

        # Create Cognito User Pool for authentication (without custom scopes initially)
        self.cognito = CognitoConstruct(
            self,
            "ChatbotMessagingUserPool",
            oauth_scopes=["aws.cognito.signin.user.admin"],  # Use standard scope initially
            callback_urls=callback_urls,
            logout_urls=callback_urls,
        )
        self.user_pool = self.cognito.user_pool

        # Add CDK Nag suppressions for Cognito User Pool
        NagSuppressions.add_resource_suppressions(
            self.user_pool,
            [
                {
                    "id": "AwsSolutions-COG1",
                    "reason": (
                        "Password policy is configured with 8+ characters, "
                        "uppercase, lowercase, digits, and symbols as required"
                    ),
                },
                {
                    "id": "AwsSolutions-COG2",
                    "reason": "MFA is set to optional for prototype messaging backend - can be enforced in production",
                },
                {
                    "id": "AwsSolutions-COG3",
                    "reason": (
                        "Advanced Security Mode requires Plus feature plan - not needed for prototype messaging backend"
                    ),
                },
            ],
        )

        # Create User Pool Domain for OAuth endpoints
        # Create a hash-based domain prefix that's globally unique and persistent
        hash_input = f"{stack_name}-{Stack.of(self).account}-{Stack.of(self).region}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        domain_prefix = f"chatbot-messaging-{hash_value}"

        self.user_pool_domain = cognito.UserPoolDomain(
            self,
            "ChatbotMessagingUserPoolDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(domain_prefix=domain_prefix),
        )

        # Create resource server and custom scope
        write_scope = cognito.ResourceServerScope(scope_name="write", scope_description="Write access")

        self.user_pool_resource_server = self.user_pool.add_resource_server(
            "ChatbotMessagingUserPoolResourceServer",
            identifier="chatbot-messaging",
            scopes=[write_scope],
        )

        # Create machine-to-machine client for server-to-server communication
        self.machine_client = self.user_pool.add_client(
            "ChatbotMessagingMachineClient",
            user_pool_client_name="chatbot-messaging-machine-client",
            generate_secret=True,
            auth_flows=cognito.AuthFlow(
                user_password=False,
                user_srp=False,
                admin_user_password=False,
                custom=False,
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    client_credentials=True,
                    authorization_code_grant=False,
                    implicit_code_grant=False,
                ),
                scopes=[
                    cognito.OAuthScope.resource_server(
                        self.user_pool_resource_server,
                        write_scope,
                    ),
                ],
            ),
            access_token_validity=Duration.minutes(60),
            refresh_token_validity=Duration.days(1),
            id_token_validity=Duration.minutes(60),
            prevent_user_existence_errors=True,
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO,
            ],
        )

        # Grant Cognito permissions to Lambda for JWT validation
        self.messaging_lambda.add_to_role_policy(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                actions=[
                    "cognito-idp:GetUser",
                    "cognito-idp:DescribeUserPool",
                    "cognito-idp:DescribeUserPoolClient",
                ],
                resources=[
                    self.user_pool.user_pool_arn,
                ],
            )
        )

        # Create Cognito User Pool Authorizer
        self.cognito_authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "ChatbotMessagingAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name=f"{stack_name}-Authorizer",
        )

        # Create Lambda integration
        lambda_integration = apigw.LambdaIntegration(
            self.messaging_lambda,
            proxy=True,  # Use Lambda proxy integration
            allow_test_invoke=True,
        )

        # Configure API Gateway routes

        # POST /messages - Send message (requires authentication)
        messages_resource = self.api.root.add_resource("messages")
        messages_resource.add_method(
            "POST",
            lambda_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorization_scopes=["chatbot-messaging/write", "aws.cognito.signin.user.admin"],
        )

        # PUT /messages/{messageId}/status - Update message status (requires authentication)
        message_resource = messages_resource.add_resource("{messageId}")
        status_resource = message_resource.add_resource("status")
        status_resource.add_method(
            "PUT",
            lambda_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorization_scopes=["chatbot-messaging/write", "aws.cognito.signin.user.admin"],
        )

        # GET /conversations/{conversationId}/messages - Get messages (requires authentication)
        conversations_resource = self.api.root.add_resource("conversations")
        conversation_resource = conversations_resource.add_resource("{conversationId}")
        conversation_messages_resource = conversation_resource.add_resource("messages")
        conversation_messages_resource.add_method(
            "GET",
            lambda_integration,
            authorizer=self.cognito_authorizer,
            authorization_type=apigw.AuthorizationType.COGNITO,
            authorization_scopes=["chatbot-messaging/write", "aws.cognito.signin.user.admin"],
        )

        # Grant API Gateway permission to invoke Lambda
        self.messaging_lambda.add_permission(
            "APIGatewayInvokePermission",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"{self.api.arn_for_execute_api()}/*/*/*",
        )

        # Create custom resource to generate and upload runtime-config.json
        CustomResourceConstruct(
            self,
            "CustomResource",
            cognito_construct=self.cognito,
            config_bucket=self.config_bucket,
            messaging_api_endpoint=self.api.url,
            virtual_assistant_client_id=self.machine_client.user_pool_client_id,
            cognito_domain=self.user_pool_domain.domain_name,
        )

        # CDK Nag suppressions for API Gateway
        NagSuppressions.add_resource_suppressions(
            self.api,
            [
                {
                    "id": "AwsSolutions-APIG2",
                    "reason": "Request validation is handled by Lambda function with Powertools validation",
                },
                {
                    "id": "AwsSolutions-APIG4",
                    "reason": "API Gateway authorization is configured with Cognito User Pool authorizer",
                },
                {
                    "id": "AwsSolutions-APIG6",
                    "reason": "CloudWatch logging is enabled for API Gateway access logs",
                },
                {
                    "id": "AwsSolutions-COG4",
                    "reason": "API Gateway uses Cognito User Pool authorizer for authentication",
                },
            ],
        )

        # Create Secrets Manager secret to store machine client credentials
        self.machine_client_secret = secretsmanager.Secret(
            self,
            "ChatMessagingClientSecret",
            description="Complete configuration for chatbot machine-to-machine authentication and API access",
            secret_object_value={
                # API Configuration
                "api_url": SecretValue.unsafe_plain_text(self.api.url),
                "api_stage": SecretValue.unsafe_plain_text("prod"),
                # OAuth2 Client Credentials
                "client_id": SecretValue.resource_attribute(self.machine_client.user_pool_client_id),
                "client_secret": self.machine_client.user_pool_client_secret,
                "scope": SecretValue.unsafe_plain_text("chatbot-messaging/write"),
                # OAuth2 Endpoints
                "oauth_domain": SecretValue.resource_attribute(self.user_pool_domain.domain_name),
                "oauth_token_url": SecretValue.unsafe_plain_text(
                    f"https://{self.user_pool_domain.domain_name}.auth.{Aws.REGION}.amazoncognito.com/oauth2/token"
                ),
                # Cognito Configuration (for reference)
                "user_pool_id": SecretValue.resource_attribute(self.user_pool.user_pool_id),
                "region": SecretValue.unsafe_plain_text(Aws.REGION),
                # Authentication Instructions
                "auth_flow": SecretValue.unsafe_plain_text("client_credentials"),
                "token_type": SecretValue.unsafe_plain_text("Bearer"),
            },
        )

        # CDK Nag suppressions for prototype environment
        NagSuppressions.add_resource_suppressions(
            self.machine_client_secret,
            [
                {
                    "id": "AwsSolutions-SMG4",
                    "reason": "Automatic rotation not required for prototype messaging backend client credentials",
                }
            ],
        )

        # Note: CDK Nag suppressions for BucketDeployment resources are handled
        # by the stack that uses this construct, as the resource paths depend on
        # the stack name and construct hierarchy.
