# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#


from aws_cdk import (
    CfnOutput,
    Stack,
)
from aws_cdk import (
    aws_cognito as cognito,
)
from cdk_nag import NagPackSuppression, NagSuppressions
from constructs import Construct


class CognitoConstruct(Construct):
    """
    A construct that sets up AWS Cognito resources including a User Pool,
    User Pool Client, and Identity Pool, along with associated roles and
    permissions for authenticated and unauthenticated users.
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        oauth_scopes: list[str] = None,
        callback_urls: list[str] = None,
        logout_urls: list[str] = None,
    ):
        super().__init__(scope, construct_id)

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=True,
            ),
            feature_plan=cognito.FeaturePlan.PLUS,
            standard_threat_protection_mode=cognito.StandardThreatProtectionMode.FULL_FUNCTION,
        )

        NagSuppressions.add_resource_suppressions(
            construct=self.user_pool,
            suppressions=[
                NagPackSuppression(
                    id="AwsSolutions-COG2",
                    reason="MFA is not required for prototype environment as this Cognito User Pool "
                    "is used for frontend user authentication with basic security requirements. "
                    "Production deployment should evaluate MFA requirements based on user access patterns "
                    "and implement appropriate multi-factor authentication for enhanced security.",
                ),
            ],
        )

        CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            export_name=f"{Stack.of(self).stack_name}{construct_id}UserPoolId",
        )

        # Configure OAuth settings if provided
        oauth_settings = None
        if oauth_scopes and callback_urls:
            # Convert scope strings to proper OAuthScope objects
            scopes = []
            for scope in oauth_scopes:
                if scope == "aws.cognito.signin.user.admin":
                    scopes.append(cognito.OAuthScope.COGNITO_ADMIN)
                elif scope == "openid":
                    scopes.append(cognito.OAuthScope.OPENID)
                elif scope == "profile":
                    scopes.append(cognito.OAuthScope.PROFILE)
                elif scope == "email":
                    scopes.append(cognito.OAuthScope.EMAIL)
                elif scope == "phone":
                    scopes.append(cognito.OAuthScope.PHONE)
                else:
                    # For custom scopes, they need to be defined as resource server scopes first
                    # This will be handled separately in the messaging backend construct
                    pass

            # Add default scopes
            scopes.extend([cognito.OAuthScope.OPENID, cognito.OAuthScope.PROFILE])

            oauth_settings = cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True,
                    implicit_code_grant=True,
                    client_credentials=False,  # Not needed for frontend client
                ),
                scopes=scopes,
                callback_urls=callback_urls,
                logout_urls=logout_urls or callback_urls,
            )

        self.user_pool_client = cognito.UserPoolClient(
            self,
            "UserPoolClient",
            user_pool=self.user_pool,
            auth_flows=cognito.AuthFlow(
                user_password=False,
                user_srp=False,
                admin_user_password=True,
                custom=False,
            ),
            o_auth=oauth_settings,
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO] if oauth_settings else None,
            # Ensure OAuth flows are enabled for this client
            generate_secret=False,  # Frontend clients should not have secrets
            prevent_user_existence_errors=True,  # Better security practice
        )
        CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            export_name=f"{Stack.of(self).stack_name}{construct_id}UserPoolClientId",
        )
