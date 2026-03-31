# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AgentCore Identity construct for outbound authentication from gateway to targets.

This module provides a CDK construct that creates an OAuth2 Credential Provider
for AgentCore Gateway to authenticate to targets (Hotel PMS API and Hotel Assistant MCP)
via Cognito. The construct includes a grant() method that encapsulates all necessary
permissions for outbound authentication.
"""

from aws_cdk import Aws, Names, Stack
from aws_cdk import aws_iam as iam
from aws_cdk import custom_resources as cr
from cdk_nag import NagSuppressions
from constructs import Construct


class AgentCoreIdentity(Construct):
    """
    AgentCore Identity for outbound authentication from gateway to targets.

    Creates an OAuth2 Credential Provider that the gateway uses to authenticate
    to targets (Hotel PMS API and Hotel Assistant MCP) via Cognito.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cognito_construct,
        **kwargs,
    ):
        """
        Initialize AgentCore Identity construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            cognito_construct: Cognito construct for OAuth2 configuration
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        if cognito_construct is None:
            raise ValueError("cognito_construct is required")

        # Generate unique provider name
        provider_name = Names.unique_resource_name(
            self,
            max_length=64,
            separator="-",
            allowed_special_characters="",
        )

        # Get Cognito configuration
        discovery_url = cognito_construct.discovery_url
        client_id = cognito_construct.user_pool_client_id
        client_secret = cognito_construct.user_pool_client.user_pool_client_secret.unsafe_unwrap()

        # Build OAuth2 endpoints from Cognito domain
        user_pool_domain = cognito_construct.user_pool_domain
        base_url = user_pool_domain.base_url()
        authorization_endpoint = f"{base_url}/oauth2/authorize"
        token_endpoint = f"{base_url}/oauth2/token"

        # Create IAM policy for custom resource
        identity_policy = cr.AwsCustomResourcePolicy.from_statements(
            [
                iam.PolicyStatement(
                    actions=[
                        "bedrock-agentcore:CreateOauth2CredentialProvider",
                        "bedrock-agentcore:UpdateOauth2CredentialProvider",
                        "bedrock-agentcore:DeleteOauth2CredentialProvider",
                        "bedrock-agentcore:GetOauth2CredentialProvider",
                        "bedrock-agentcore:CreateTokenVault",
                        "bedrock-agentcore:GetTokenVault",
                        "secretsmanager:CreateSecret",
                        "secretsmanager:DeleteSecret",
                        "secretsmanager:DescribeSecret",
                        "secretsmanager:PutSecretValue",
                    ],
                    resources=["*"],  # Provider ARN not known at synthesis time
                    conditions={
                        "StringEquals": {
                            "aws:RequestedRegion": Stack.of(self).region,
                        }
                    },
                )
            ]
        )

        # Create OAuth2 Credential Provider using custom resource
        self.identity = cr.AwsCustomResource(
            self,
            "Identity",
            on_create=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="createOauth2CredentialProvider",
                parameters={
                    "name": provider_name,
                    "credentialProviderVendor": "CognitoOauth2",
                    "oauth2ProviderConfigInput": {
                        "includedOauth2ProviderConfig": {
                            "clientId": client_id,
                            "clientSecret": client_secret,
                            "issuer": discovery_url,
                            "authorizationEndpoint": authorization_endpoint,
                            "tokenEndpoint": token_endpoint,
                        }
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("name"),
            ),
            on_update=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="updateOauth2CredentialProvider",
                parameters={
                    "name": cr.PhysicalResourceIdReference(),
                    "oauth2ProviderConfigInput": {
                        "includedOauth2ProviderConfig": {
                            "clientId": client_id,
                            "clientSecret": client_secret,
                            "issuer": discovery_url,
                            "authorizationEndpoint": authorization_endpoint,
                            "tokenEndpoint": token_endpoint,
                        }
                    },
                },
                physical_resource_id=cr.PhysicalResourceId.from_response("name"),
            ),
            on_delete=cr.AwsSdkCall(
                service="bedrock-agentcore-control",
                action="deleteOauth2CredentialProvider",
                parameters={
                    "name": cr.PhysicalResourceIdReference(),
                },
            ),
            policy=identity_policy,
        )

        # Get provider ARN and secret ARN from custom resource response
        self.credential_provider_arn = self.identity.get_response_field("credentialProviderArn")
        self.secret_arn = self.identity.get_response_field("clientSecretArn.secretArn")

        # Add CDK Nag suppressions
        NagSuppressions.add_resource_suppressions(
            self.identity,
            [
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Custom resource requires wildcard permissions for AgentCore Identity "
                    "operations because the provider ARN is not known at synthesis time. "
                    "Scoped to specific actions and region.",
                }
            ],
            apply_to_children=True,
        )

    def grant(self, grantee: iam.IGrantable) -> None:
        """
        Grant permissions to use this AgentCore Identity for outbound authentication.

        This grants all necessary permissions for a gateway to use this identity
        to authenticate to targets (Hotel PMS API and Hotel Assistant MCP).

        Permissions granted:
        - Get workload access tokens
        - Get OAuth2 tokens from provider
        - Get OAuth2 tokens from workload identity directory
        - Read OAuth2 client secret from Secrets Manager

        Args:
            grantee: The principal to grant permissions to (typically a gateway role)
        """
        # Get workload access tokens
        grantee.grant_principal.add_to_policy(
            iam.PolicyStatement(
                sid="GetWorkloadAccessToken",
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:GetWorkloadAccessToken"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{Aws.REGION}:{Aws.ACCOUNT_ID}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{Aws.REGION}:{Aws.ACCOUNT_ID}:workload-identity-directory/default/workload-identity/*",
                ],
            )
        )

        # Get OAuth2 tokens from provider
        grantee.grant_principal.add_to_policy(
            iam.PolicyStatement(
                sid="GetResourceOauth2TokenFromProvider",
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:GetResourceOauth2Token"],
                resources=[self.credential_provider_arn],
            )
        )

        # Get OAuth2 tokens from workload identity directory
        grantee.grant_principal.add_to_policy(
            iam.PolicyStatement(
                sid="GetResourceOauth2TokenFromWorkloadIdentity",
                effect=iam.Effect.ALLOW,
                actions=["bedrock-agentcore:GetResourceOauth2Token"],
                resources=[
                    f"arn:aws:bedrock-agentcore:{Aws.REGION}:{Aws.ACCOUNT_ID}:token-vault/default",
                    f"arn:aws:bedrock-agentcore:{Aws.REGION}:{Aws.ACCOUNT_ID}:workload-identity-directory/default",
                    f"arn:aws:bedrock-agentcore:{Aws.REGION}:{Aws.ACCOUNT_ID}:workload-identity-directory/default/workload-identity/*",
                ],
            )
        )

        # Read OAuth2 client secret
        grantee.grant_principal.add_to_policy(
            iam.PolicyStatement(
                sid="GetOAuth2ClientSecret",
                effect=iam.Effect.ALLOW,
                actions=["secretsmanager:GetSecretValue"],
                resources=[self.secret_arn],
            )
        )
