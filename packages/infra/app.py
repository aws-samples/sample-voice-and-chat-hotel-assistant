#!/usr/bin/env python3
# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

#


import os

import aws_cdk as cdk
from cdk_nag import AwsSolutionsChecks

from stack.backend_stack import BackendStack
from stack.hotel_pms_stack import HotelPMSStack

app = cdk.App()

# Hotel PMS Stack - must be created first to provide MCP configuration
hotel_pms_stack = HotelPMSStack(
    app,
    "HotelPmsStack",
    description="Simulated Hotel PMS (uksb-feodn73lrd)(tag:demomcp)",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=os.environ.get("CDK_DEFAULT_REGION")),
)

# Virtual Assistant Backend Stack
backend_stack = BackendStack(
    app,
    "VirtualAssistantStack",
    description="Speech and chat Virtual Assistant (uksb-feodn73lrd)(tag:app)",
    env=cdk.Environment(account=os.environ.get("CDK_DEFAULT_ACCOUNT"), region=os.environ.get("CDK_DEFAULT_REGION")),
    # Pass MCP configuration from HotelPmsStack
    mcp_config_parameter=hotel_pms_stack.mcp_config_parameter.parameter_name,
    mcp_secrets=[hotel_pms_stack.mcp_credentials_secret],
)

# Ensure proper stack dependencies
backend_stack.add_dependency(hotel_pms_stack)

cdk.Aspects.of(app).add(AwsSolutionsChecks())

app.synth()
