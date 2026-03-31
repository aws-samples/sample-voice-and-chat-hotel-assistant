# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import (
    Duration,
    RemovalPolicy,
    Stack,
)
from aws_cdk import (
    aws_s3 as s3,
)
from constructs import Construct


class AccessLogsBucket(s3.Bucket):
    """Per-stack bucket for storing S3 access logs."""

    _instances = {}  # Store instances per stack

    @classmethod
    def get_instance(cls, scope: Construct, construct_id: str = "AccessLogsBucket"):
        stack = Stack.of(scope)
        stack_id = stack.stack_name

        if stack_id not in cls._instances:
            cls._instances[stack_id] = s3.Bucket(
                stack,
                construct_id,
                versioned=True,
                removal_policy=RemovalPolicy.RETAIN,  # Retain logs even if stack is destroyed
                object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
                block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
                encryption=s3.BucketEncryption.S3_MANAGED,
                enforce_ssl=True,
                lifecycle_rules=[
                    s3.LifecycleRule(
                        enabled=True,
                        expiration=Duration.days(365),  # Adjust retention period as needed
                    ),
                ],
            )
        return cls._instances[stack_id]


class PACEBucket(s3.Bucket):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
        **kwargs,
    ):
        access_logs_bucket = AccessLogsBucket.get_instance(scope)

        # Extract lifecycle_rules from kwargs or use default
        lifecycle_rules = kwargs.pop(
            "lifecycle_rules",
            [
                s3.LifecycleRule(enabled=True, expiration=Duration.days(90)),
            ],
        )

        super().__init__(
            scope,
            construct_id,
            versioned=True,
            auto_delete_objects=True,
            removal_policy=RemovalPolicy.DESTROY,
            object_ownership=s3.ObjectOwnership.BUCKET_OWNER_PREFERRED,
            block_public_access=s3.BlockPublicAccess(
                block_public_acls=True,
                block_public_policy=True,
                ignore_public_acls=True,
                restrict_public_buckets=True,
            ),
            encryption=s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True,
            lifecycle_rules=lifecycle_rules,
            server_access_logs_bucket=access_logs_bucket,
            server_access_logs_prefix=f"{construct_id}/",
            cors=[
                s3.CorsRule(
                    allowed_methods=[
                        s3.HttpMethods.GET,
                        s3.HttpMethods.HEAD,
                        s3.HttpMethods.PUT,
                        s3.HttpMethods.POST,
                    ],
                    allowed_origins=["*"],
                    allowed_headers=["*"],
                    exposed_headers=[
                        "x-amz-server-side-encryption",
                        "x-amz-request-id",
                        "x-amz-id-2",
                        "ETag",
                    ],
                    max_age=3000,
                )
            ],
            **kwargs,
        )
