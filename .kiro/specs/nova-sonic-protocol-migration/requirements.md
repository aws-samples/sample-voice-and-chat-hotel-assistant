# Nova Sonic Protocol Migration Requirements

## Introduction

The current speech-to-speech system is not working because the Nova Sonic
protocol implementation was not properly migrated from the frontend
`WebSocketEventManager.ts` to the backend. The frontend was simplified to only
handle audio I/O, but the backend is missing the complete Nova Sonic protocol
sequence that was previously handled by the frontend.

## Requirements

### Requirement 1: Complete Nova Sonic Protocol Implementation

**User Story:** As a user, I want the speech-to-speech system to work properly
so that I can have conversations with the hotel assistant.

#### Acceptance Criteria

1. WHEN the backend receives a `start_recording` message THEN it SHALL
   initialize the complete Nova Sonic protocol sequence
2. WHEN the Nova Sonic protocol is initialized THEN it SHALL send sessionStart,
   promptStart, and system prompt events
3. WHEN audio chunks are received THEN they SHALL be properly sent to Nova Sonic
   with contentStart(AUDIO) events
4. WHEN Nova Sonic generates responses THEN they SHALL be converted to
   simplified frontend messages
5. WHEN the session ends THEN it SHALL properly clean up Nova Sonic protocol
   state

### Requirement 2: Audio Content Lifecycle Management

**User Story:** As a user, I want my speech to be properly processed so that the
assistant can understand and respond to me.

#### Acceptance Criteria

1. WHEN `start_recording` is received THEN the backend SHALL send
   contentStart(AUDIO) with USER role
2. WHEN audio chunks are received THEN they SHALL be sent as audioInput events
   to Nova Sonic
3. WHEN `stop_recording` is received THEN the backend SHALL send contentEnd for
   the audio content
4. WHEN Nova Sonic processes audio THEN it SHALL generate transcript,
   textOutput, or audioOutput events
5. WHEN audio content ends THEN the backend SHALL be ready for the next user
   input

### Requirement 3: Response Processing and Conversion

**User Story:** As a user, I want to see transcriptions and hear audio responses
so that I can have a natural conversation.

#### Acceptance Criteria

1. WHEN Nova Sonic sends textOutput events THEN they SHALL be converted to
   transcript messages for the frontend
2. WHEN Nova Sonic sends audioOutput events THEN they SHALL be converted to
   audio_response messages for the frontend
3. WHEN Nova Sonic sends transcript events THEN they SHALL be forwarded as
   transcript messages to the frontend
4. WHEN Nova Sonic sends contentStart/contentEnd events THEN they SHALL update
   conversation status appropriately
5. WHEN errors occur THEN they SHALL be converted to user-friendly error
   messages

### Requirement 4: Tool Configuration Migration

**User Story:** As a hotel assistant, I want to have access to hotel tools so
that I can help guests with their requests.

#### Acceptance Criteria

1. WHEN the Nova Sonic protocol starts THEN it SHALL include the complete tool
   configuration from the existing tools registry
2. WHEN MCP tools are available THEN they SHALL be included in the tool
   configuration
3. WHEN tool schemas are generated THEN they SHALL match the format expected by
   Nova Sonic
4. WHEN tools are executed THEN the results SHALL be properly formatted and sent
   back to Nova Sonic
5. WHEN tool execution fails THEN appropriate error handling SHALL occur

### Requirement 5: System Prompt Integration

**User Story:** As a hotel guest, I want to interact with a Spanish-speaking
hotel receptionist so that I can get help in my preferred language.

#### Acceptance Criteria

1. WHEN the Nova Sonic protocol starts THEN it SHALL send the Spanish hotel
   receptionist system prompt
2. WHEN the system prompt is sent THEN it SHALL be properly formatted as a
   contentStart(TEXT) + textInput + contentEnd sequence
3. WHEN the system prompt is processed THEN Nova Sonic SHALL be ready to receive
   user audio input
4. WHEN responses are generated THEN they SHALL follow the Spanish hotel
   receptionist persona
5. WHEN the system prompt fails to load THEN a fallback prompt SHALL be used

### Requirement 6: Session State Management

**User Story:** As a user, I want the conversation to flow naturally so that I
can have multiple exchanges with the assistant.

#### Acceptance Criteria

1. WHEN a session starts THEN it SHALL maintain proper state throughout the
   conversation
2. WHEN multiple audio inputs occur THEN each SHALL be processed in the correct
   sequence
3. WHEN the assistant responds THEN the system SHALL be ready for the next user
   input
4. WHEN barge-in occurs THEN the system SHALL handle interruptions gracefully
5. WHEN the session ends THEN all resources SHALL be properly cleaned up

### Requirement 7: Error Handling and Recovery

**User Story:** As a user, I want the system to handle errors gracefully so that
I can continue using the service even when issues occur.

#### Acceptance Criteria

1. WHEN Nova Sonic protocol errors occur THEN they SHALL be logged and handled
   gracefully
2. WHEN authentication fails THEN appropriate error messages SHALL be sent to
   the frontend
3. WHEN audio processing fails THEN the system SHALL attempt recovery or provide
   clear error messages
4. WHEN tool execution fails THEN the conversation SHALL continue with
   appropriate error responses
5. WHEN connection issues occur THEN the system SHALL attempt reconnection or
   graceful degradation

### Requirement 8: Performance and Timing

**User Story:** As a user, I want the conversation to feel natural and
responsive so that I can have a smooth interaction experience.

#### Acceptance Criteria

1. WHEN audio is processed THEN responses SHALL be generated within reasonable
   time limits
2. WHEN silence is detected THEN the system SHALL wait appropriately before
   processing
3. WHEN responses are ready THEN they SHALL be sent to the frontend immediately
4. WHEN multiple events occur THEN they SHALL be processed in the correct order
5. WHEN the system is under load THEN it SHALL maintain acceptable response
   times
