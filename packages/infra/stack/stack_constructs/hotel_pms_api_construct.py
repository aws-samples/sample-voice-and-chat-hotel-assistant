# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""CDK construct for Hotel PMS API Gateway with Cognito authentication."""

from aws_cdk import RemovalPolicy
from aws_cdk import aws_apigateway as apigateway
from aws_cdk import aws_iam as iam
from aws_cdk import aws_lambda as _lambda
from aws_cdk import aws_logs as logs
from aws_cdk import aws_wafv2 as wafv2
from cdk_nag import NagSuppressions
from constructs import Construct

from .agentcore_cognito import AgentCoreCognitoUserPool


class HotelPmsApiConstruct(Construct):
    """CDK construct for Hotel PMS API Gateway with Cognito auth."""

    def __init__(self, scope: Construct, construct_id: str, lambda_function: _lambda.Function, **kwargs):
        super().__init__(scope, construct_id, **kwargs)

        # Create Cognito User Pool using AgentCoreCognitoUserPool construct
        self.cognito_construct = AgentCoreCognitoUserPool(
            self,
            "HotelPmsCognito",
            enable_self_sign_up=False,  # Machine-to-machine only
            user_pool_name="hotel-pms-api-pool",
            # Uses secure password policy and PLUS feature plan by default
        )

        # Get references to the created resources
        self.user_pool = self.cognito_construct.user_pool
        self.user_pool_client = self.cognito_construct.user_pool_client

        # Get JWT authorizer configuration for AgentCore Gateway integration
        self.jwt_config = self.cognito_construct.create_jwt_authorizer_config()

        # Create Cognito Authorizer using the construct's configuration
        # For client credentials flow (OAuth2 M2M), access tokens do NOT contain 'aud' claim
        # API Gateway validates the token signature and issuer against the user pool
        # The token contains 'client_id' and 'scope' claims which are validated
        self.authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self,
            "HotelPmsAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name="hotel-pms-authorizer",
            # No identity_source or results_cache_ttl configuration needed
            # API Gateway will validate the token against the user pool automatically
        )

        # Create API Gateway REST API with proper logging and WAF
        self.api = apigateway.RestApi(
            self,
            "HotelPmsApi",
            rest_api_name="hotel-pms-api",
            description="Hotel PMS API for AgentCore Gateway integration",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=apigateway.Cors.ALL_ORIGINS,
                allow_methods=apigateway.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
            deploy_options=apigateway.StageOptions(
                stage_name="v1",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                # Enable access logging (APIG1)
                access_log_destination=apigateway.LogGroupLogDestination(
                    logs.LogGroup(
                        self,
                        "ApiAccessLogs",
                        retention=logs.RetentionDays.ONE_WEEK,
                        removal_policy=RemovalPolicy.DESTROY,
                    )
                ),
                access_log_format=apigateway.AccessLogFormat.clf(),
                # Enable CloudWatch logging (APIG6)
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True,
            ),
        )

        # Create WAF Web ACL for API Gateway (APIG3)
        web_acl = wafv2.CfnWebACL(
            self,
            "HotelPmsApiWebACL",
            scope="REGIONAL",
            default_action=wafv2.CfnWebACL.DefaultActionProperty(allow={}),
            rules=[
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
                        sampled_requests_enabled=True,
                        cloud_watch_metrics_enabled=True,
                        metric_name="CommonRuleSetMetric",
                    ),
                ),
            ],
            visibility_config=wafv2.CfnWebACL.VisibilityConfigProperty(
                sampled_requests_enabled=True,
                cloud_watch_metrics_enabled=True,
                metric_name="HotelPmsApiWebACL",
            ),
        )

        # Associate WAF with API Gateway
        wafv2.CfnWebACLAssociation(
            self,
            "HotelPmsApiWebACLAssociation",
            resource_arn=self.api.deployment_stage.stage_arn,
            web_acl_arn=web_acl.attr_arn,
        )

        # Create request validator for API Gateway (APIG2)
        self.request_validator = apigateway.RequestValidator(
            self,
            "HotelPmsRequestValidator",
            rest_api=self.api,
            validate_request_body=True,
            validate_request_parameters=True,
        )

        # Create Lambda integration (proxy mode handles responses automatically)
        lambda_integration = apigateway.LambdaIntegration(
            lambda_function,
            proxy=True,
        )

        # Add API resources and methods
        self._create_api_resources(lambda_integration)

        # Grant API Gateway permission to invoke Lambda
        lambda_function.add_permission(
            "ApiGatewayInvoke",
            principal=iam.ServicePrincipal("apigateway.amazonaws.com"),
            source_arn=f"{self.api.arn_for_execute_api()}/*/*",
        )

        # Add CDK-NAG suppressions for Cognito (COG2)
        NagSuppressions.add_resource_suppressions(
            self.user_pool,
            [
                {
                    "id": "AwsSolutions-COG2",
                    "reason": "MFA not required for machine-to-machine authentication using client credentials flow. "
                    "This is a service-to-service API that uses OAuth2 client credentials, not user authentication.",
                }
            ],
        )

    @property
    def api_endpoint_url(self) -> str:
        """Get the API Gateway endpoint URL."""
        return self.api.url

    @property
    def cognito_user_pool_id(self) -> str:
        """Get the Cognito User Pool ID."""
        return self.cognito_construct.user_pool_id

    @property
    def cognito_client_id(self) -> str:
        """Get the Cognito User Pool Client ID."""
        return self.cognito_construct.user_pool_client_id

    @property
    def cognito_discovery_url(self) -> str:
        """Get the OpenID Connect discovery URL."""
        return self.cognito_construct.discovery_url

    @property
    def jwt_authorizer_config(self) -> dict:
        """Get JWT authorizer configuration for AgentCore Gateway."""
        return {
            "discovery_url": self.jwt_config.discovery_url,
            "allowed_clients": self.jwt_config.allowed_clients,
            "allowed_audience": self.jwt_config.allowed_audience,
        }

    def _create_api_resources(self, integration: apigateway.LambdaIntegration):
        """Create API Gateway resources and methods."""

        # Get resource server scopes for access token validation
        # For client credentials flow, access tokens contain 'scope' claim with these values
        resource_server = self.cognito_construct.gateway_resource_server
        authorization_scopes = [
            f"{resource_server.user_pool_resource_server_id}/read",
            f"{resource_server.user_pool_resource_server_id}/write",
        ]

        # Common method responses for CORS
        method_responses = [
            apigateway.MethodResponse(
                status_code="200",
                response_parameters={
                    "method.response.header.Access-Control-Allow-Origin": True,
                    "method.response.header.Access-Control-Allow-Headers": True,
                    "method.response.header.Access-Control-Allow-Methods": True,
                },
            ),
            apigateway.MethodResponse(
                status_code="400",
                response_parameters={
                    "method.response.header.Access-Control-Allow-Origin": True,
                },
            ),
            apigateway.MethodResponse(
                status_code="401",
                response_parameters={
                    "method.response.header.Access-Control-Allow-Origin": True,
                },
            ),
            apigateway.MethodResponse(
                status_code="404",
                response_parameters={
                    "method.response.header.Access-Control-Allow-Origin": True,
                },
            ),
            apigateway.MethodResponse(
                status_code="500",
                response_parameters={
                    "method.response.header.Access-Control-Allow-Origin": True,
                },
            ),
        ]

        # Availability endpoints
        availability = self.api.root.add_resource("availability")
        check = availability.add_resource("check")
        check.add_method(
            "POST",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )

        # Quote endpoints
        quotes = self.api.root.add_resource("quotes")
        generate = quotes.add_resource("generate")
        generate.add_method(
            "POST",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )

        # Reservation endpoints
        reservations = self.api.root.add_resource("reservations")
        reservations.add_method(
            "POST",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )
        reservations.add_method(
            "GET",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )

        reservation_id = reservations.add_resource("{id}")
        reservation_id.add_method(
            "GET",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )
        reservation_id.add_method(
            "PUT",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )

        checkout = reservation_id.add_resource("checkout")
        checkout.add_method(
            "POST",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )

        # Hotel endpoints
        hotels = self.api.root.add_resource("hotels")
        hotels.add_method(
            "GET",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )

        # Request endpoints
        requests = self.api.root.add_resource("requests")
        housekeeping = requests.add_resource("housekeeping")
        housekeeping.add_method(
            "POST",
            integration,
            authorizer=self.authorizer,
            authorization_scopes=authorization_scopes,
            request_validator=self.request_validator,
            method_responses=method_responses,
        )
