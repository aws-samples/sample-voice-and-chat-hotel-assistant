# Requirements Document

## Introduction

This feature upgrades the LiveKit voice agent from Amazon Nova Sonic 1 to Amazon
Nova Sonic 2 (`amazon.nova-2-sonic-v1:0`). Nova Sonic 2 introduces significant
improvements including native support for the agent speaking first (eliminating
workarounds), text message input capabilities, expanded multilingual voice
support with 16 voices across 8 languages, and configurable turn-taking
behavior. The upgrade will leverage the new LiveKit agents 1.3.9+ release which
includes full Nova Sonic 2 support.

## Glossary

- **Nova Sonic**: Amazon Bedrock's real-time conversational AI model for
  speech-to-speech interactions
- **LiveKit**: Real-time communication platform used for voice agent
  infrastructure
- **RealtimeModel**: LiveKit's interface to Nova Sonic for bidirectional audio
  streaming
- **Turn-taking**: The conversational flow control mechanism that determines
  when the agent responds
- **Endpointing sensitivity**: Configuration parameter controlling how quickly
  the agent detects user pauses
- **VoiceId**: Type-safe enum for selecting voices across different languages
- **MCP Server**: Model Context Protocol server providing tool integration for
  domain-specific operations
- **AgentSession**: LiveKit session managing the conversation lifecycle

## Requirements

### Requirement 1

**User Story:** As a developer, I want to upgrade to Nova Sonic 2 using the new
LiveKit factory method, so that I can access the latest model capabilities with
proper configuration.

#### Acceptance Criteria

1. WHEN the agent initializes THEN it SHALL use
   `RealtimeModel.with_nova_sonic_2()` instead of the default constructor
2. WHEN the model is configured THEN it SHALL specify the model ID as
   `amazon.nova-2-sonic-v1:0`
3. WHEN the agent starts THEN it SHALL verify Nova Sonic 2 is available in the
   AWS region
4. WHEN model initialization fails THEN it SHALL provide clear error messages
   indicating Nova Sonic 2 requirements
5. WHEN the agent runs THEN it SHALL log the model version being used for
   debugging purposes

### Requirement 2

**User Story:** As a user, I want the agent to greet me immediately when I
connect, so that I have a natural conversation start without awkward silence.

#### Acceptance Criteria

1. WHEN a guest connects to the voice agent THEN the agent SHALL speak the
   greeting without requiring audio input workarounds
2. WHEN the greeting is delivered THEN it SHALL use the native Nova Sonic 2
   "speak first" capability
3. WHEN the greeting completes THEN the agent SHALL be ready to listen for the
   guest's response
4. WHEN the greeting audio is played THEN it SHALL use the pre-recorded greeting
   asset for consistent quality
5. WHEN greeting delivery fails THEN the system SHALL log the error and attempt
   a text-based greeting fallback

### Requirement 3

**User Story:** As a developer, I want to configure the Tiffany polyglot voice
for multi-language support, so that the agent can automatically detect and
respond in the user's language.

#### Acceptance Criteria

1. WHEN configuring the voice THEN it SHALL use the string "tiffany" for the
   polyglot female voice
2. WHEN the voice is set THEN it SHALL support automatic language detection and
   response in Spanish, English, French, German, Italian, Portuguese, and Hindi
3. WHEN voice configuration is validated THEN it SHALL ensure the voice is
   compatible with Nova Sonic 2
4. WHEN voice initialization fails THEN it SHALL provide clear error messages
   about voice availability
5. WHEN the agent speaks THEN it SHALL use the Tiffany voice consistently and
   respond in the user's detected language

### Requirement 4

**User Story:** As a system administrator, I want configurable turn-taking
sensitivity, so that I can tune the agent's responsiveness based on user
feedback and conversation patterns.

#### Acceptance Criteria

1. WHEN the agent is configured THEN it SHALL read `ENDPOINTING_SENSITIVITY`
   from environment variables
2. WHEN no sensitivity is configured THEN it SHALL default to "MEDIUM" for
   balanced behavior
3. WHEN sensitivity is set to "HIGH" THEN the agent SHALL respond quickly to
   short pauses
4. WHEN sensitivity is set to "LOW" THEN the agent SHALL wait longer before
   responding to reduce interruptions
5. WHEN an invalid sensitivity value is provided THEN it SHALL log a warning and
   use the default "MEDIUM" setting

### Requirement 5

**User Story:** As a developer, I want to send text instructions to the agent
during conversations, so that I can dynamically adjust agent behavior without
interrupting the audio flow.

#### Acceptance Criteria

1. WHEN text input capability is needed THEN the system SHALL verify
   `session.supports_text_input` is True
2. WHEN sending instructions THEN it SHALL use
   `session.generate_reply(instructions="...")` for system-level commands
3. WHEN sending user text THEN it SHALL use
   `session.generate_reply(user_input="...")` for text-based user messages
4. WHEN text input is sent THEN it SHALL not interrupt ongoing audio
   conversations
5. WHEN text input is used with Nova Sonic 1 THEN it SHALL log a warning and
   skip the operation gracefully

### Requirement 6

**User Story:** As a developer, I want to remove the audio input workaround for
initial greeting, so that the codebase is cleaner and uses native Nova Sonic 2
capabilities.

#### Acceptance Criteria

1. WHEN reviewing the greeting implementation THEN it SHALL not include silent
   audio packet workarounds
2. WHEN the agent greets users THEN it SHALL use the native `session.say()`
   method without audio input tricks
3. WHEN the greeting is delivered THEN it SHALL rely on Nova Sonic 2's native
   "speak first" support
4. WHEN comparing to the old implementation THEN the new code SHALL be simpler
   and more maintainable
5. WHEN the greeting completes THEN the conversation flow SHALL be natural
   without artificial delays

### Requirement 7

**User Story:** As a developer, I want to use the latest LiveKit agents code
from the 1.3.9 release, so that I can test Nova Sonic 2 features immediately.

#### Acceptance Criteria

4. WHEN the agent starts THEN it SHALL log the LiveKit agents version for
   debugging
5. WHEN version 1.3.9+ is officially released THEN the dependencies SHALL be
   updated to use PyPI versions instead of Git URLs

### Requirement 8

**User Story:** As a developer, I want to maintain backward compatibility with
existing MCP integration, so that domain-specific tools continue to work
seamlessly with Nova Sonic 2.

#### Acceptance Criteria

1. WHEN the agent initializes THEN it SHALL continue to use the existing MCP
   server integration
2. WHEN tools are called THEN they SHALL work identically to the Nova Sonic 1
   implementation
3. WHEN tool results are returned THEN they SHALL be properly formatted for Nova
   Sonic 2
4. WHEN MCP servers are unavailable THEN the agent SHALL handle errors
   gracefully as before
5. WHEN tool execution completes THEN the agent SHALL incorporate results into
   Spanish responses naturally

### Requirement 9

**User Story:** As a system administrator, I want comprehensive logging for the
Nova Sonic 2 upgrade, so that I can troubleshoot issues and monitor the new
capabilities.

#### Acceptance Criteria

1. WHEN the agent starts THEN it SHALL log the Nova Sonic model version being
   used
2. WHEN text input is used THEN it SHALL log the instructions or user input
   being sent
3. WHEN voice configuration is applied THEN it SHALL log the VoiceId and
   language settings
4. WHEN endpointing sensitivity is configured THEN it SHALL log the selected
   sensitivity level
5. WHEN Nova Sonic 2 specific features are used THEN they SHALL be logged at
   DEBUG level for troubleshooting

### Requirement 10

**User Story:** As a developer, I want to update the CDK infrastructure to
support Nova Sonic 2, so that the deployment includes necessary permissions and
configurations.

#### Acceptance Criteria

1. WHEN deploying the infrastructure THEN it SHALL include permissions for the
   `amazon.nova-2-sonic-v1:0` model
2. WHEN environment variables are configured THEN they SHALL include
   `ENDPOINTING_SENSITIVITY` with a default value
3. WHEN the ECS task definition is created THEN it SHALL use the updated Docker
   image with LiveKit 1.3.9+
4. WHEN Bedrock permissions are granted THEN they SHALL include both Nova Sonic
   1 and 2 for gradual migration
5. WHEN the stack is deployed THEN it SHALL validate that Nova Sonic 2 is
   available in the target region

### Requirement 11

**User Story:** As a developer, I want to maintain a configurable persona with
multi-language support, so that users can interact in their preferred language
while maintaining consistent service quality.

#### Acceptance Criteria

1. WHEN the agent responds THEN it SHALL use a multi-language system prompt with
   language mirroring rules
2. WHEN a Spanish-speaking user connects THEN the greeting SHALL be delivered in
   Spanish with the same friendly, professional tone
3. WHEN an English-speaking guest connects THEN the greeting SHALL be delivered
   in English with the same friendly, professional tone
4. WHEN tools are used THEN the agent SHALL explain actions in the user's
   detected language
5. WHEN errors occur THEN the agent SHALL provide helpful messages in the user's
   detected language

### Requirement 12

**User Story:** As a developer, I want to test the Nova Sonic 2 upgrade in a
development environment, so that I can verify functionality before production
deployment.

#### Acceptance Criteria

1. WHEN testing locally THEN the system SHALL support running with Nova Sonic 2
   via environment configuration
2. WHEN testing the greeting THEN it SHALL verify the agent speaks first without
   workarounds
3. WHEN testing turn-taking THEN it SHALL verify different endpointing
   sensitivity settings work correctly
4. WHEN testing voice quality THEN it SHALL verify the Spanish female voice
   (Lupe) sounds natural
5. WHEN testing MCP integration THEN it SHALL verify MCP tools work correctly
   with Nova Sonic 2

### Requirement 13

**User Story:** As a system administrator, I want documentation for the Nova
Sonic 2 upgrade, so that I understand the new capabilities and configuration
options.

#### Acceptance Criteria

1. WHEN reviewing documentation THEN it SHALL explain the benefits of Nova Sonic
   2 over Nova Sonic 1
2. WHEN configuring the agent THEN documentation SHALL describe the new
   environment variables
3. WHEN troubleshooting THEN documentation SHALL include common issues and
   solutions for Nova Sonic 2
4. WHEN understanding features THEN documentation SHALL explain text input
   capabilities and use cases
5. WHEN deploying THEN documentation SHALL include migration steps from Nova
   Sonic 1 to Nova Sonic 2

### Requirement 14

**User Story:** As a developer, I want access to the LiveKit agents source code
for reference during development, so that I can understand the implementation
details and debug issues effectively.

#### Acceptance Criteria

1. WHEN developing the upgrade THEN the LiveKit agents repository SHALL be
   available as a reference in the workspace
2. WHEN reviewing implementation details THEN the developer SHALL be able to
   examine the RealtimeModel and RealtimeSession source code
3. WHEN debugging issues THEN the developer SHALL be able to trace through the
   LiveKit agents code to understand behavior
4. WHEN the upgrade is complete THEN the reference code SHALL be removed or
   documented as a development-only resource
5. WHEN questions arise about Nova Sonic 2 features THEN the developer SHALL be
   able to consult the LiveKit agents README and examples
