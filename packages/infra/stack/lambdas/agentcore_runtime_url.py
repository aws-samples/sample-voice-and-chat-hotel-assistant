# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Custom resource Lambda to URL-encode AgentCore Runtime ARN."""

from urllib.parse import quote


def handler(event, context):
    """URL-encode the runtime ARN for use in AgentCore Runtime URL."""
    if event["RequestType"] == "Delete":
        return {"PhysicalResourceId": "url-encode-arn"}

    runtime_arn = event["ResourceProperties"]["RuntimeArn"]
    region = event["ResourceProperties"]["Region"]

    # URL-encode the ARN
    encoded_arn = quote(runtime_arn, safe="")

    # Construct the runtime URL
    runtime_url = (
        f"https://bedrock-agentcore.{region}.amazonaws.com/runtimes/{encoded_arn}/invocations?qualifier=DEFAULT"
    )

    return {"PhysicalResourceId": "url-encode-arn", "Data": {"RuntimeUrl": runtime_url}}
