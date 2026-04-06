# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Messaging platform integrations.

This package provides platform-specific messaging implementations
for different channels (web, SMS, WhatsApp, etc.) with a unified
interface for consistent message handling.
"""

from .aws_eum import AWSEndUserMessaging
from .base import MessagingPlatform
from .router import PlatformRouter, platform_router
from .twilio import TwilioMessaging
from .web import WebMessaging

__all__ = [
    "MessagingPlatform",
    "WebMessaging",
    "TwilioMessaging",
    "AWSEndUserMessaging",
    "PlatformRouter",
    "platform_router",
]
