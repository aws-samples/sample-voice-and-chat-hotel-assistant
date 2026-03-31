# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
AgentCore Cognito wrapper construct for Gateway authentication.

This construct provides Cognito User Pool configuration specifically designed
for AgentCore Gateway authentication, maintaining compatibility with existing
Cognito integration patterns while providing JWT authorizer configuration.
"""

import re

from aws_cdk import Aws, Duration, Names, Stack
from aws_cdk import aws_cognito as cognito
from constructs import Construct


class JWTAuthorizerConfig:
    """JWT authorizer configuration for AgentCore Gateway."""

    def __init__(
        self,
        discovery_url: str,
        allowed_clients: list[str],
        allowed_audience: list[str] | None = None,
    ):
        """
        Initialize JWT authorizer configuration.

        Args:
            discovery_url: OpenID Connect discovery URL
            allowed_clients: List of allowed client IDs
            allowed_audience: Optional list of allowed audiences
        """
        self.discovery_url = discovery_url
        self.allowed_clients = allowed_clients
        self.allowed_audience = allowed_audience or []


class AgentCoreCognitoUserPoolProps:
    """Properties for AgentCore Cognito User Pool construct."""

    def __init__(
        self,
        enable_self_sign_up: bool = False,
        user_pool_name: str | None = None,
        password_policy: cognito.PasswordPolicy | None = None,
        token_validity: dict | None = None,
        oauth_scopes: list[str] | None = None,
        callback_urls: list[str] | None = None,
        logout_urls: list[str] | None = None,
    ):
        """
        Initialize AgentCore Cognito User Pool properties.

        Args:
            enable_self_sign_up: Whether to enable self sign-up
            user_pool_name: Optional name for the user pool
            password_policy: Optional password policy configuration
            token_validity: Optional token validity settings
            oauth_scopes: Optional OAuth scopes for the client
            callback_urls: Optional callback URLs for OAuth
            logout_urls: Optional logout URLs for OAuth
        """
        self.enable_self_sign_up = enable_self_sign_up
        self.user_pool_name = user_pool_name
        self.password_policy = password_policy
        self.token_validity = token_validity or {}
        self.oauth_scopes = oauth_scopes or []
        self.callback_urls = callback_urls or []
        self.logout_urls = logout_urls or []


class AgentCoreCognitoUserPool(Construct):
    """
    AgentCore Cognito User Pool construct for Gateway authentication.

    This construct creates a Cognito User Pool specifically configured for
    AgentCore Gateway authentication, providing JWT authorizer configuration
    and maintaining compatibility with existing integration patterns.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs):
        """
        Initialize AgentCore Cognito User Pool construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID
            **kwargs: Keyword arguments that can include AgentCoreCognitoUserPoolProps or individual properties
        """
        super().__init__(scope, construct_id)

        # Handle both props object and individual keyword arguments for backward compatibility
        if "props" in kwargs:
            props = kwargs["props"]
        else:
            # Create props from individual keyword arguments
            props = AgentCoreCognitoUserPoolProps(
                enable_self_sign_up=kwargs.get("enable_self_sign_up", False),
                user_pool_name=kwargs.get("user_pool_name"),
                password_policy=kwargs.get("password_policy"),
                token_validity=kwargs.get("token_validity"),
                oauth_scopes=kwargs.get("oauth_scopes"),
                callback_urls=kwargs.get("callback_urls"),
                logout_urls=kwargs.get("logout_urls"),
            )

        # Validate properties
        self._validate_properties(props)

        # Create User Pool
        self._create_user_pool(props)

        # Create User Pool Client
        self._create_user_pool_client(props)

        # Create User Pool Domain for OAuth token endpoint access
        # This is required even for client credentials flow
        self._create_user_pool_domain()

    def _validate_properties(self, props: AgentCoreCognitoUserPoolProps) -> None:
        """
        Validate Cognito User Pool properties.

        Args:
            props: User Pool properties to validate

        Raises:
            ValueError: If properties are invalid
        """
        # Validate user pool name format if provided
        if props.user_pool_name is not None:
            if not re.match(r"^[a-zA-Z0-9_-]+$", props.user_pool_name):
                raise ValueError("user_pool_name must contain only alphanumeric characters, hyphens, and underscores")

            if len(props.user_pool_name) > 128:
                raise ValueError("user_pool_name must be 128 characters or less")

        # Validate callback URLs format if provided
        for url in props.callback_urls:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"callback_url must be a valid HTTP/HTTPS URL: {url}")

        # Validate logout URLs format if provided
        for url in props.logout_urls:
            if not url.startswith(("http://", "https://")):
                raise ValueError(f"logout_url must be a valid HTTP/HTTPS URL: {url}")

        # Validate OAuth scopes
        valid_scopes = [
            "openid",
            "profile",
            "email",
            "phone",
            "aws.cognito.signin.user.admin",
        ]
        for scope in props.oauth_scopes:
            if scope not in valid_scopes and not scope.startswith("chatbot-messaging/"):
                # Allow custom scopes that start with known prefixes
                pass

    def _create_user_pool(self, props: AgentCoreCognitoUserPoolProps) -> None:
        """
        Create Cognito User Pool.

        Args:
            props: User Pool properties
        """
        # Use provided password policy or create a secure default
        password_policy = props.password_policy or cognito.PasswordPolicy(
            min_length=8,
            require_lowercase=True,
            require_uppercase=True,
            require_digits=True,
            require_symbols=True,
        )

        # Generate unique user pool name if not provided
        user_pool_name = props.user_pool_name or self._generate_unique_name("UserPool")

        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name=user_pool_name,
            self_sign_up_enabled=props.enable_self_sign_up,
            password_policy=password_policy,
            # Configure for machine-to-machine authentication
            sign_in_aliases=cognito.SignInAliases(
                username=True,
                email=False,  # Disable email sign-in for M2M
                phone=False,  # Disable phone sign-in for M2M
            ),
            # Enable PLUS feature plan for OAuth2 support and advanced security features
            feature_plan=cognito.FeaturePlan.PLUS,
            # Modern threat protection configuration:
            # Using StandardThreatProtectionMode.FULL_FUNCTION instead of deprecated AdvancedSecurityMode.ENFORCED
            # This provides equivalent security functionality with the modern CDK API
            standard_threat_protection_mode=cognito.StandardThreatProtectionMode.FULL_FUNCTION,
            # Configure account recovery
            account_recovery=cognito.AccountRecovery.NONE
            if not props.enable_self_sign_up
            else cognito.AccountRecovery.EMAIL_ONLY,
        )

    def _create_user_pool_client(self, props: AgentCoreCognitoUserPoolProps) -> None:
        """
        Create Cognito User Pool Client configured for machine-to-machine authentication.

        Args:
            props: User Pool properties
        """
        # Create resource server with read/write scopes for AgentCore Gateway
        read_scope = cognito.ResourceServerScope(scope_name="read", scope_description="Read access")
        write_scope = cognito.ResourceServerScope(scope_name="write", scope_description="Write access")

        self.resource_server = self.user_pool.add_resource_server(
            "GatewayResourceServer", identifier="gateway-resource-server", scopes=[read_scope, write_scope]
        )

        # Configure OAuth settings for machine-to-machine authentication only
        oauth_settings = cognito.OAuthSettings(
            flows=cognito.OAuthFlows(
                client_credentials=True,  # Only enable client credentials flow for M2M
                authorization_code_grant=False,  # Disable authorization code grant
                implicit_code_grant=False,  # Disable implicit grant
            ),
            scopes=[
                cognito.OAuthScope.resource_server(self.resource_server, read_scope),
                cognito.OAuthScope.resource_server(self.resource_server, write_scope),
            ],
            # No callback URLs needed for M2M authentication
        )

        # Configure token validity (using individual Duration properties)
        access_token_validity = (
            props.token_validity.get("access_token", Duration.hours(1)) if props.token_validity else Duration.hours(1)
        )
        id_token_validity = (
            props.token_validity.get("id_token", Duration.hours(1)) if props.token_validity else Duration.hours(1)
        )
        refresh_token_validity = (
            props.token_validity.get("refresh_token", Duration.days(30)) if props.token_validity else Duration.days(30)
        )

        self.user_pool_client = cognito.UserPoolClient(
            self,
            "UserPoolClient",
            user_pool=self.user_pool,
            # Configure for machine-to-machine authentication only
            auth_flows=cognito.AuthFlow(
                user_password=False,  # Disable user password auth
                user_srp=False,  # Disable SRP auth
                admin_user_password=False,  # Disable admin user password auth
                custom=False,  # Disable custom auth
            ),
            o_auth=oauth_settings,
            supported_identity_providers=[cognito.UserPoolClientIdentityProvider.COGNITO],
            generate_secret=True,  # Generate secret for M2M authentication
            prevent_user_existence_errors=True,
            access_token_validity=access_token_validity,
            id_token_validity=id_token_validity,
            refresh_token_validity=refresh_token_validity,
        )

    def _create_user_pool_domain(self) -> None:
        """
        Create Cognito User Pool Domain for OAuth flows.

        This is required for OAuth2 flows including client credentials flow
        as it provides the OAuth2 token endpoints.
        """
        # Generate hash-based domain prefix that's globally unique and persistent
        # (matching the TypeScript implementation)
        import hashlib

        stack_name = Stack.of(self).stack_name
        account = Stack.of(self).account
        region = Stack.of(self).region

        hash_input = f"{stack_name}-{account}-{region}"
        hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
        domain_prefix = f"agent-gateway-{hash_value}"

        self.user_pool_domain = cognito.UserPoolDomain(
            self,
            "UserPoolDomain",
            user_pool=self.user_pool,
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=domain_prefix,
            ),
        )

    def _generate_unique_name(self, resource_type: str) -> str:
        """
        Generate a unique name using CDK's Names.unique_resource_name().

        Args:
            resource_type: Type of resource for naming

        Returns:
            Unique resource name (stable across deployments)
        """
        # Generate name using CDK's Names utility with Cognito-specific constraints
        return Names.unique_resource_name(
            self,
            max_length=60,  # Cognito allows longer names
            separator="-",
            allowed_special_characters="",
        )

    def create_jwt_authorizer_config(self) -> JWTAuthorizerConfig:
        """
        Create JWT authorizer configuration for AgentCore Gateway.

        Returns:
            JWT authorizer configuration
        """
        # Build OpenID Connect discovery URL
        discovery_url = f"https://cognito-idp.{Aws.REGION}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/openid-configuration"

        # Get client ID for allowed clients
        allowed_clients = [self.user_pool_client.user_pool_client_id]

        # For client credentials flow, include resource server identifier as allowed audience
        # This allows the JWT authorizer to validate tokens that contain the resource server
        # identifier in the aud claim when requested with the resource server scope
        allowed_audience = [self.resource_server.user_pool_resource_server_id]

        return JWTAuthorizerConfig(
            discovery_url=discovery_url,
            allowed_clients=allowed_clients,
            allowed_audience=allowed_audience,
        )

    def add_resource_server(
        self,
        identifier: str,
        scopes: list[cognito.ResourceServerScope],
        user_pool_resource_server_name: str | None = None,
    ) -> cognito.UserPoolResourceServer:
        """
        Add a resource server to the User Pool.

        Args:
            identifier: Resource server identifier
            scopes: List of resource server scopes
            user_pool_resource_server_name: Optional name for the resource server

        Returns:
            Created resource server
        """
        return cognito.UserPoolResourceServer(
            self,
            f"ResourceServer{identifier}",
            user_pool=self.user_pool,
            identifier=identifier,
            scopes=scopes,
            user_pool_resource_server_name=user_pool_resource_server_name,
        )

    @property
    def discovery_url(self) -> str:
        """Get the OpenID Connect discovery URL."""
        return f"https://cognito-idp.{Aws.REGION}.amazonaws.com/{self.user_pool.user_pool_id}/.well-known/openid-configuration"

    @property
    def user_pool_id(self) -> str:
        """Get the User Pool ID."""
        return self.user_pool.user_pool_id

    @property
    def user_pool_client_id(self) -> str:
        """Get the User Pool Client ID."""
        return self.user_pool_client.user_pool_client_id

    @property
    def user_pool_arn(self) -> str:
        """Get the User Pool ARN."""
        return self.user_pool.user_pool_arn

    @property
    def gateway_resource_server(self) -> cognito.UserPoolResourceServer:
        """Get the gateway resource server."""
        return self.resource_server
