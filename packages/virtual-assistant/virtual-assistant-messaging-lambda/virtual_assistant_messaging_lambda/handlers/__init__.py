# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Lambda handlers for message processing."""

from .delete_processed_messages import lambda_handler as delete_processed_messages_handler
from .invoke_agentcore import lambda_handler as invoke_agentcore_handler
from .mark_messages_processing import lambda_handler as mark_messages_processing_handler
from .message_buffer_handler import lambda_handler as message_buffer_handler
from .message_processor import lambda_handler as message_processor_handler

__all__ = [
    "delete_processed_messages_handler",
    "invoke_agentcore_handler",
    "mark_messages_processing_handler",
    "message_buffer_handler",
    "message_processor_handler",
]
