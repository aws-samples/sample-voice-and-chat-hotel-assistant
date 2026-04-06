# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""WhatsApp grant utilities following CDK grant patterns."""

from aws_cdk import aws_iam as iam
from constructs import Construct


def grant_whatsapp_permissions(
    grantee: iam.IGrantable,
    cross_account_role: str = None,
    scope: Construct = None,
) -> iam.Grant:
    """Grant WhatsApp permissions following CDK grant patterns.

    Args:
        grantee: The principal to grant permissions to
        cross_account_role: Optional cross-account role ARN for EUM Social access
        scope: Optional construct scope for region/account context

    Returns:
        iam.Grant: Grant object for chaining
    """
    # Get region and account from scope if provided, otherwise use defaults
    region = scope.region if scope else "*"
    account = scope.account if scope else "*"

    # Create policy statements for WhatsApp permissions
    statements = []

    # SSM parameter access for allow list
    statements.append(
        iam.PolicyStatement(
            sid="SSMParameterAccess",
            effect=iam.Effect.ALLOW,
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{region}:{account}:parameter/virtual-assistant/whatsapp/*"],
        )
    )

    # EUM Social API access
    statements.append(
        iam.PolicyStatement(
            sid="EUMSocialAPIAccess",
            effect=iam.Effect.ALLOW,
            actions=["socialmessaging:SendWhatsAppMessage"],
            resources=["*"],  # EUM Social API doesn't support resource-level permissions
        )
    )

    # Cross-account role assumption (if configured)
    if cross_account_role:
        statements.append(
            iam.PolicyStatement(
                sid="CrossAccountRoleAssumption",
                effect=iam.Effect.ALLOW,
                actions=["sts:AssumeRole"],
                resources=[cross_account_role],
            )
        )

    # Apply all policy statements to the grantee
    for statement in statements:
        grantee.grant_principal.add_to_principal_policy(statement)

    # Return a Grant object following CDK patterns
    # Use Grant.add_to_principal to create a proper Grant object
    all_actions = ["ssm:GetParameter", "socialmessaging:SendWhatsAppMessage"]
    if cross_account_role:
        all_actions.append("sts:AssumeRole")

    return iam.Grant.add_to_principal(
        grantee=grantee,
        actions=all_actions,
        resource_arns=[
            f"arn:aws:ssm:{region}:{account}:parameter/virtual-assistant/whatsapp/*",
            "*",  # EUM Social requires wildcard
        ]
        + ([cross_account_role] if cross_account_role else []),
    )
