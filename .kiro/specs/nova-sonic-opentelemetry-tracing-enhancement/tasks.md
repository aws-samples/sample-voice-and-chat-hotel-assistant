# Implementation Plan

- [x] 1. Audit all code paths that send events to Nova Sonic/Bedrock
  - Identify all locations where events are sent to Bedrock stream
  - Find events that bypass the current bedrock_client.send_event() tracing
  - Locate audioInput events from AudioProcessor that go directly to stream
  - Find any other direct stream.input_stream.send() calls that bypass tracing
  - Document all Nova Sonic event flows to ensure complete coverage
  - **COMPLETED**: Audit documented in NOVA_SONIC_EVENT_FLOW_AUDIT.md
  - **FINDING**: Only AudioProcessor lacks proper tracing context (session_id,
    parent_span)
  - _Requirements: 1.1, 2.1, 2.2, 2.3_

- [x] 2. Fix AudioProcessor tracing context for audioInput events
  - [x] 2.1 Add session_id parameter to AudioProcessor
    - Modify AudioProcessor constructor to accept session_id parameter
    - Update WebSocketHandler to pass session_id when creating AudioProcessor
    - Store session_id in AudioProcessor for use in tracing calls
    - Update AudioProcessor.queue_audio method signature if needed
    - _Requirements: 1.1, 1.3_

  - [x] 2.2 Add TracingClient integration to AudioProcessor
    - Add TracingClient to AudioProcessor initialization
    - Import TracingClient in audio_processor.py
    - Initialize TracingClient instance in AudioProcessor constructor
    - Add audio-specific tracing methods for queue operations
    - _Requirements: 1.1, 1.3, 1.4_

  - [x] 2.3 Fix bedrock_client.send_event() call in AudioProcessor
    - Update the send_event call in audio_processor.py line 114
    - Add session_id parameter to the send_event call
    - Add parent_span parameter for proper trace hierarchy
    - Ensure audio events are properly correlated with session spans
    - _Requirements: 1.1, 1.3_

- [x] 3. Add audio-specific tracing attributes and metadata
  - [x] 3.1 Add audio metadata to tracing spans
    - Include audio content length without actual audio data
    - Add audio queue size and processing metrics
    - Include prompt name and content name correlation
    - Add audio processing timing information
    - _Requirements: 1.2, 1.3_

  - [x] 3.2 Add audio processing operation tracing
    - Trace audio queuing operations with timing
    - Add span for audio processing workflow
    - Include audio format and configuration metadata
    - Add correlation between audio chunks and conversation turns
    - _Requirements: 1.2, 1.3_

- [ ] 4. Create test suite for AudioProcessor tracing fix
  - [ ] 4.1 Create unit tests for AudioProcessor tracing
    - Test AudioProcessor initialization with session_id and TracingClient
    - Test audio queuing operations create proper tracing spans
    - Test bedrock_client.send_event() is called with correct tracing parameters
    - Test audio metadata is included in spans without audio content
    - Test tracing graceful degradation for AudioProcessor operations
    - _Requirements: 1.4, 1.5_

  - [ ] 4.2 Create integration tests for complete audioInput flow
    - Test complete audioInput event flow from frontend through AudioProcessor
      to Bedrock
    - Verify audioInput events appear in traces with proper session correlation
    - Test audio processing timing and metadata in real conversation scenarios
    - Validate that audioInput events are properly correlated with conversation
      flow
    - Test performance impact of AudioProcessor tracing enhancements
    - _Requirements: 1.1, 1.4, 1.5_

- [ ] 5. Validate complete audioInput tracing coverage
  - [ ] 5.1 Test audioInput events in real conversation flows
    - Execute speech input scenarios and verify audioInput events are traced
    - Validate session correlation works for audioInput events
    - Test audio processing metadata appears correctly in traces
    - Verify no performance impact on real-time audio processing
    - _Requirements: 1.1, 1.4, 1.5_

  - [ ] 5.2 Confirm no other tracing gaps exist
    - Re-run conversation flow scenarios to verify complete event coverage
    - Validate that all events to/from Nova Sonic appear in traces
    - Confirm the AudioProcessor fix resolves the identified tracing gap
    - Document that Nova Sonic event tracing is now complete
    - _Requirements: 2.1, 2.3, 2.5_
