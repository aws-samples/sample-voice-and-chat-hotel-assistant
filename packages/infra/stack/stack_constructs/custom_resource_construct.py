# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#

from aws_cdk import (
    Aws,
)
from aws_cdk import (
    aws_s3_deployment as s3deploy,
)
from constructs import Construct

from .cognito_constructs import CognitoConstruct


class CustomResourceConstruct(Construct):
    """A CDK construct that generates and deploys runtime configuration to S3.

    This construct uses S3 BucketDeployment to generate and upload runtime-config.json
    to a private S3 bucket with necessary AWS resource information. It handles:
    - Generates runtime-config.json with Cognito and messaging backend configuration
    - Deploys the configuration file to S3 bucket using CDK's built-in deployment
    - No custom Lambda functions required - uses CDK's native S3 deployment capabilities

    Args:
        scope (Construct): The scope in which this construct is defined
        construct_id (str): The scoped construct ID
        cognito_construct (CognitoConstruct): The Cognito construct containing user pool and client information
        config_bucket (s3.IBucket): The private S3 bucket for storing runtime-config.json
        messaging_api_endpoint (str, optional): The messaging backend API endpoint URL
        virtual_assistant_client_id (str, optional): The virtual assistant client ID for messaging
        cognito_domain (str, optional): The Cognito domain for OAuth endpoints
        **kwargs: Additional keyword arguments to pass to the parent Construct class

    Dependencies:
        - Requires CognitoConstruct for user pool and client IDs
        - Requires config bucket for runtime-config.json storage
        - Optionally requires messaging backend properties for messaging integration
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        cognito_construct: CognitoConstruct,
        config_bucket,
        messaging_api_endpoint: str = None,
        virtual_assistant_client_id: str = None,
        cognito_domain: str = None,
        **kwargs,
    ) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Build runtime configuration object
        runtime_config = {
            "cognitoProps": {
                "userPoolId": cognito_construct.user_pool.user_pool_id,
                "userPoolWebClientId": cognito_construct.user_pool_client.user_pool_client_id,
                "region": Aws.REGION,
            },
            "applicationName": "Virtual Assistant",
            "logo": "",
        }

        # Add Cognito domain if provided
        if cognito_domain:
            runtime_config["cognitoProps"]["domain"] = cognito_domain

        # Add messaging API endpoint if provided
        if messaging_api_endpoint:
            runtime_config["messagingApiEndpoint"] = messaging_api_endpoint

        # Add virtual assistant client ID if provided
        if virtual_assistant_client_id:
            runtime_config["virtualAssistantClientId"] = virtual_assistant_client_id

        # Deploy runtime configuration to S3 bucket
        self.runtime_config_deployment = s3deploy.BucketDeployment(
            self,
            "RuntimeConfigDeployment",
            sources=[s3deploy.Source.json_data("runtime-config.json", runtime_config)],
            destination_bucket=config_bucket,
            retain_on_delete=False,  # Don't retain files on delete
            prune=True,  # Remove files that don't exist in the source
        )

        # Ensure deployment waits for Cognito construct to be ready
        self.runtime_config_deployment.node.add_dependency(cognito_construct)
