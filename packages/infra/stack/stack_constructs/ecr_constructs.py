# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#


from aws_cdk import (
    Duration,
    RemovalPolicy,
)
from aws_cdk import (
    aws_ecr as ecr,
)
from constructs import Construct


class ECRRepositoryConstruct(Construct):
    """
    A construct that creates an ECR repository with lifecycle policies for image management.

    This construct creates an ECR repository optimized for container image storage
    with automatic lifecycle management to control costs and storage usage.

    Parameters:
    - scope (Construct): The scope in which this construct is defined.
    - construct_id (str): The unique identifier for this construct.
    - repository_name (str): The name of the ECR repository.
    - max_image_count (int): Maximum number of images to keep (default: 10).
    - untagged_image_expiry_days (int): Days after which untagged images expire (default: 1).
    """

    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        repository_name: str,
        max_image_count: int = 10,
        untagged_image_expiry_days: int = 1,
    ):
        super().__init__(scope, construct_id)

        # Create ECR repository
        self.repository = ecr.Repository(
            self,
            "Repository",
            repository_name=repository_name,
            image_scan_on_push=True,  # Enable vulnerability scanning
            encryption=ecr.RepositoryEncryption.AES_256,  # AWS managed encryption
            removal_policy=RemovalPolicy.DESTROY,  # Allow cleanup during development
        )

        # Add lifecycle policy for untagged images (higher priority)
        self.repository.add_lifecycle_rule(
            description=f"Delete untagged images after {untagged_image_expiry_days} day(s)",
            rule_priority=1,
            tag_status=ecr.TagStatus.UNTAGGED,
            max_image_age=Duration.days(untagged_image_expiry_days),
        )

        # Add lifecycle policy to manage image retention (lower priority)
        self.repository.add_lifecycle_rule(
            description=f"Keep only {max_image_count} most recent images",
            rule_priority=2,
            tag_status=ecr.TagStatus.ANY,
            max_image_count=max_image_count,
        )

    @property
    def repository_arn(self) -> str:
        """Return the ARN of the ECR repository."""
        return self.repository.repository_arn

    @property
    def repository_name(self) -> str:
        """Return the name of the ECR repository."""
        return self.repository.repository_name

    @property
    def repository_uri(self) -> str:
        """Return the URI of the ECR repository."""
        return self.repository.repository_uri
