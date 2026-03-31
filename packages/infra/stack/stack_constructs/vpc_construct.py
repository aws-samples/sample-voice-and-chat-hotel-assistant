# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

from aws_cdk import (
    RemovalPolicy,
)
from aws_cdk import (
    aws_ec2 as ec2,
)
from aws_cdk import (
    aws_iam as iam,
)
from aws_cdk import (
    aws_logs as logs,
)
from cdk_nag import NagSuppressions
from constructs import Construct


class VPCConstruct(Construct):
    def __init__(
        self,
        scope: Construct,
        construct_id: str,
    ):
        super().__init__(scope, construct_id)

        # Create VPC Flow Logs role with custom policy
        flow_log_role = iam.Role(self, "FlowLogRole", assumed_by=iam.ServicePrincipal("vpc-flow-logs.amazonaws.com"))

        # Add custom policy for VPC Flow Logs
        flow_log_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "logs:CreateLogGroup",
                    "logs:CreateLogStream",
                    "logs:PutLogEvents",
                    "logs:DescribeLogGroups",
                    "logs:DescribeLogStreams",
                ],
                resources=["*"],
            )
        )

        # Create Lambda role for security group management
        sg_manager_role = iam.Role(
            self, "SecurityGroupManagerRole", assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Add permissions for security group management
        sg_manager_role.add_to_policy(
            iam.PolicyStatement(
                actions=[
                    "ec2:AuthorizeSecurityGroupIngress",
                    "ec2:RevokeSecurityGroupIngress",
                    "ec2:DescribeSecurityGroups",
                ],
                resources=["*"],
            )
        )

        # Add CloudWatch Logs permissions for Lambda
        sg_manager_role.add_to_policy(
            iam.PolicyStatement(
                actions=["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], resources=["*"]
            )
        )

        # Add CDK Nag suppression for security group manager role default policy
        NagSuppressions.add_resource_suppressions(
            sg_manager_role.node.find_child("DefaultPolicy"),
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "Security group manager role requires wildcard permissions for EC2 security group "
                    "operations (ec2:AuthorizeSecurityGroupIngress, ec2:RevokeSecurityGroupIngress, "
                    "ec2:DescribeSecurityGroups) and CloudWatch Logs operations. These permissions are "
                    "required for dynamic security group management.",
                }
            ],
        )

        # Add CDK Nag suppression for Flow Logs role default policy
        NagSuppressions.add_resource_suppressions(
            flow_log_role.node.find_child("DefaultPolicy"),
            suppressions=[
                {
                    "id": "AwsSolutions-IAM5",
                    "reason": "VPC Flow Logs role requires wildcard permissions for CloudWatch Logs operations "
                    "(logs:CreateLogGroup, logs:CreateLogStream, logs:PutLogEvents, logs:DescribeLog*) to "
                    "manage VPC flow log streams. These permissions are required by the AWS VPC Flow Logs service.",
                }
            ],
        )

        # Create VPC with NAT Gateway and isolated subnets for Bedrock
        self.vpc = ec2.Vpc(
            self,
            "VPC",
            max_azs=2,
            nat_gateways=1,
            subnet_configuration=[
                ec2.SubnetConfiguration(name="Public", subnet_type=ec2.SubnetType.PUBLIC, cidr_mask=24),
                ec2.SubnetConfiguration(name="Private", subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS, cidr_mask=24),
                ec2.SubnetConfiguration(name="Isolated", subnet_type=ec2.SubnetType.PRIVATE_ISOLATED, cidr_mask=26),
            ],
        )

        # Add Flow Logs
        self.vpc.add_flow_log(
            "FlowLog",
            destination=ec2.FlowLogDestination.to_cloud_watch_logs(
                log_group=logs.LogGroup(
                    self,
                    "VPCFlowLogsGroup",
                    retention=logs.RetentionDays.ONE_WEEK,
                    removal_policy=RemovalPolicy.DESTROY,
                ),
                iam_role=flow_log_role,
            ),
            traffic_type=ec2.FlowLogTrafficType.ALL,
        )
