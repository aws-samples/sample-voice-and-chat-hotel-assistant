# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""SQS event models for message processing."""

import json
from typing import Any

from pydantic import BaseModel, Field, field_validator


class SQSMessageAttributes(BaseModel):
    """SQS message attributes."""

    string_value: str = Field(alias="stringValue")
    data_type: str = Field(alias="dataType")


class SQSRecord(BaseModel):
    """Individual SQS record from batch event."""

    message_id: str = Field(alias="messageId")
    receipt_handle: str = Field(alias="receiptHandle")
    body: str
    attributes: dict[str, Any]
    message_attributes: dict[str, SQSMessageAttributes] = Field(alias="messageAttributes")
    md5_of_body: str = Field(alias="md5OfBody")
    event_source: str = Field(alias="eventSource")
    event_source_arn: str = Field(alias="eventSourceARN")
    aws_region: str = Field(alias="awsRegion")


class SQSEvent(BaseModel):
    """SQS batch event containing multiple records."""

    records: list[SQSRecord] = Field(alias="Records")


class SNSMessage(BaseModel):
    """SNS message contained within SQS record body."""

    type: str = Field(alias="Type")
    message_id: str = Field(alias="MessageId")
    topic_arn: str = Field(alias="TopicArn")
    subject: str = Field(alias="Subject", default="")
    message: str = Field(alias="Message")
    timestamp: str = Field(alias="Timestamp")
    signature_version: str = Field(alias="SignatureVersion", default="")
    signature: str = Field(alias="Signature", default="")
    signing_cert_url: str = Field(alias="SigningCertURL", default="")
    unsubscribe_url: str = Field(alias="UnsubscribeURL", default="")

    @field_validator("message")
    @classmethod
    def parse_message_json(cls, v):
        """Parse the message field as JSON if it's a string."""
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return v
        return v


class ProcessingResult(BaseModel):
    """Result of processing a single message."""

    message_id: str
    success: bool
    error: str = None
    agent_response: dict[str, Any] = None
