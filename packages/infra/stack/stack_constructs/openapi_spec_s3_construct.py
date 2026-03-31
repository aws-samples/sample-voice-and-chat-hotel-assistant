# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""
Construct to deploy filled OpenAPI spec to S3 for Gateway Target.

This construct uses CDK's DeployTimeSubstitutedFile to upload the OpenAPI spec with
deploy-time substitution of the API Gateway URL, then references it in Gateway Target.
"""

from aws_cdk import aws_s3 as s3
from aws_cdk import aws_s3_deployment as s3deploy
from cdk_nag import NagSuppressions
from constructs import Construct


class OpenApiSpecS3Construct(Construct):
    """
    Deploy OpenAPI spec to S3 with deploy-time URL substitution for Gateway Target.

    This construct:
    1. Accepts a shared S3 bucket for OpenAPI specs
    2. Uses DeployTimeSubstitutedFile to upload spec with URL substitution
    3. Uses construct_id in the S3 key path for uniqueness
    4. Provides bucket and key for Gateway Target S3 reference
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        bucket: s3.IBucket,
        api_gateway_url: str,
        openapi_spec_path: str,
        **kwargs,
    ):
        """
        Initialize OpenApiSpecS3 construct.

        Args:
            scope: The scope in which to define this construct
            construct_id: The scoped construct ID (used in S3 key path)
            bucket: Shared S3 bucket for OpenAPI specs
            api_gateway_url: Actual API Gateway URL (can contain CloudFormation tokens)
            openapi_spec_path: Path to OpenAPI spec file
            placeholder_url: URL pattern to replace at deploy time
            **kwargs: Additional keyword arguments
        """
        super().__init__(scope, construct_id, **kwargs)

        self.bucket = bucket

        # Deploy OpenAPI spec with deploy-time substitution
        # DeployTimeSubstitutedFile handles CloudFormation token resolution
        self.deployment = s3deploy.DeployTimeSubstitutedFile(
            self,
            "DeployOpenApiSpec",
            source=openapi_spec_path,
            destination_bucket=self.bucket,
            substitutions={
                "base_url": api_gateway_url,
            },
        )

        # Apply CDK Nag suppressions for DeployTimeSubstitutedFile
        self._apply_nag_suppressions()

    def _apply_nag_suppressions(self):
        """Apply CDK Nag suppressions for DeployTimeSubstitutedFile custom resource."""
        NagSuppressions.add_resource_suppressions(
            self.deployment,
            [
                {
                    "id": "AwsSolutions-L1",
                    "reason": "DeployTimeSubstitutedFile Lambda is managed by CDK s3-deployment module. "
                    "Runtime version is determined by CDK and cannot be directly controlled.",
                }
            ],
            apply_to_children=True,
        )

    @property
    def bucket_name(self) -> str:
        """Get the S3 bucket name."""
        return self.bucket.bucket_name

    @property
    def object_key(self) -> str:
        """Get the S3 object key for the OpenAPI spec."""
        return self.deployment.object_key

    @property
    def s3_uri(self) -> str:
        """Get the S3 URI for the OpenAPI spec."""
        return f"s3://{self.bucket_name}/{self.object_key}"

    def get_deployment_resource(self):
        """
        Get the underlying deployment resource for dependency management.

        Returns:
            The DeployTimeSubstitutedFile resource that can be used in node.add_dependency()
        """
        return self.deployment
