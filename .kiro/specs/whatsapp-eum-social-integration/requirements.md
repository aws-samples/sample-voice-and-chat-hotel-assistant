# Requirements Document

## Introduction

This feature implements real WhatsApp messaging through AWS End User Messaging
Social (EUM Social) for the hotel assistant. The system will integrate with EUM
Social when configured via CDK context variables, supports both same-account and
cross-account EUM Social deployments, implements security through phone number
allow lists, and handles WhatsApp-specific message flows for text-based
conversations.

## Requirements

### Requirement 1

**User Story:** As a system administrator, I want to optionally enable real
WhatsApp messaging through AWS EUM Social, so that the hotel assistant can
communicate with guests via their preferred messaging platform.

#### Acceptance Criteria

1. WHEN CDK context variables `eumSocialTopicArn` and `eumSocialPhoneNumberId`
   are provided THEN the system SHALL integrate with AWS End User Messaging
   Social
2. WHEN EUM Social context variables are not provided THEN the system SHALL use
   the existing simulation-based messaging backend
3. WHEN `eumSocialCrossAccountRole` is provided THEN the system SHALL assume the
   specified role in the target account
4. WHEN EUM Social configuration is invalid THEN the CDK deployment SHALL fail
   with clear error messages
5. WHEN EUM Social is configured THEN the messaging stack SHALL not be deployed

### Requirement 2

**User Story:** As a security administrator, I want to implement an allow list
of WhatsApp phone numbers, so that the system only responds to authorized users
and prevents abuse.

#### Acceptance Criteria

1. WHEN receiving WhatsApp messages THEN the system SHALL check the sender's
   phone number against an allow list stored in SSM Parameter Store
2. WHEN a phone number is not on the allow list THEN the system SHALL log the
   attempt at DEBUG level and not process the message
3. WHEN a phone number is on the allow list THEN the system SHALL process the
   message normally
4. WHEN the allow list contains '\*' THEN the system SHALL allow messages from
   any phone number
5. WHEN the allow list parameter is missing THEN the system SHALL reject all
   incoming messages for security
6. WHEN the allow list is stored in SSM THEN it SHALL support comma-separated
   phone number format

### Requirement 3

**User Story:** As a messaging platform integration, I want to receive WhatsApp
messages via SNS and SQS from EUM Social, so that the hotel assistant can
respond to guest inquiries.

#### Acceptance Criteria

1. WHEN EUM Social receives a WhatsApp message THEN it SHALL publish the message
   to the configured SNS topic
2. WHEN the SNS topic receives a message THEN it SHALL forward to an SQS queue
   for processing
3. WHEN the messaging Lambda receives an SQS event THEN it SHALL parse the
   WhatsApp message format
4. WHEN parsing WhatsApp messages THEN the system SHALL extract sender phone
   number and message content
5. WHEN the message is from an allowed phone number THEN the system SHALL
   forward it directly to the hotel assistant via AgentCore

### Requirement 4

**User Story:** As a hotel assistant, I want to send WhatsApp messages to
guests, so that I can provide personalized assistance and information.

#### Acceptance Criteria

1. WHEN sending a message to WhatsApp THEN the system SHALL use the EUM Social
   SendWhatsAppMessage API
2. WHEN responding within the 24-hour customer service window THEN the system
   SHALL send free-form text messages
3. WHEN message sending fails THEN the system SHALL log the error and update
   message status appropriately

### Requirement 5

**User Story:** As a hotel assistant, I want to mark received WhatsApp messages
with appropriate status, so that message handling is consistent with other
messaging channels.

#### Acceptance Criteria

1. WHEN receiving a WhatsApp message THEN the system SHALL mark it as
   "delivered" upon successful receipt
2. WHEN forwarding a message to AgentCore THEN the system SHALL mark it as
   "read" upon successful processing
3. WHEN message processing fails THEN the system SHALL mark it as "failed" and
   log error details

### Requirement 6

**User Story:** As a developer, I want the EUM Social integration to be
configurable via CDK context, so that different environments can use different
configurations without code changes.

#### Acceptance Criteria

1. WHEN `eumSocialTopicArn` is provided THEN the system SHALL create an SQS
   queue and subscribe it to that SNS topic
2. WHEN `eumSocialPhoneNumberId` is provided THEN the system SHALL use it for
   sending WhatsApp messages
3. WHEN `eumSocialCrossAccountRole` is provided THEN the system SHALL assume
   that role for cross-account access
4. WHEN `eumSocialRegion` is provided THEN the system SHALL use that region for
   EUM Social API calls (default: us-east-1)
5. WHEN `whatsappAllowListParameter` is provided THEN the system SHALL use that
   SSM parameter for the phone number allow list

### Requirement 7

**User Story:** As a system administrator, I want proper error handling and
logging for WhatsApp operations, so that I can monitor and troubleshoot the
integration.

#### Acceptance Criteria

1. WHEN WhatsApp API calls fail THEN the system SHALL log detailed error
   information including error codes and messages
2. WHEN phone numbers are blocked by allow list THEN the system SHALL log the
   blocked attempt at DEBUG level only
3. WHEN cross-account role assumption fails THEN the system SHALL log the error
   and fall back gracefully
4. WHEN SNS message parsing fails THEN the system SHALL log the raw message for
   debugging
5. WHEN EUM Social API calls fail THEN the system SHALL log the error and return
   appropriate error responses

### Requirement 8

**User Story:** As a compliance officer, I want WhatsApp message handling to
respect privacy and data protection requirements, so that the system complies
with relevant regulations.

#### Acceptance Criteria

1. WHEN logging phone numbers THEN the system SHALL only log them at DEBUG level
2. WHEN logging message content THEN the system SHALL only log it at DEBUG level
3. WHEN WhatsApp messages are processed THEN message content SHALL only be
   retained in AgentCore memory with its short-term retention policy
4. WHEN processing personal data THEN the system SHALL implement appropriate
   data protection measures

### Requirement 9

**User Story:** As a system architect, I want the EUM Social integration to
maintain existing functionality, so that deployments without EUM Social continue
working.

#### Acceptance Criteria

1. WHEN EUM Social is not configured THEN the system SHALL use the existing
   simulation-based messaging backend
2. WHEN EUM Social configuration is missing THEN no EUM Social-specific
   resources SHALL be created
3. WHEN EUM Social is configured THEN the messaging simulation stack SHALL be
   skipped in deployment
