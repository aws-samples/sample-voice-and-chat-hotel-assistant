# Implementation Plan

- [x] 1. Set up OpenTelemetry dependencies and core infrastructure
  - Add OpenTelemetry packages to pyproject.toml dependencies
  - Create TracingClient class with environment-based initialization
  - Implement payload sanitization for sensitive data removal
  - Add error handling and graceful degradation patterns
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

- [x] 2. Implement core tracing functionality
  - [x] 2.1 Create TracingClient class with initialization logic
    - Implement environment variable detection for tracing enablement
    - Add OpenTelemetry SDK initialization with OTLP exporter
    - Create service configuration with default attributes
    - Add safe initialization with fallback to disabled state
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5_

  - [x] 2.2 Implement span creation methods
    - Create session-level root span creation method
    - Implement outbound event span creation with attributes
    - Implement inbound event span creation with attributes
    - Add span attribute extraction from Nova Sonic events
    - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.2, 3.3_

  - [x] 2.3 Add payload sanitization functionality
    - Implement audio content filtering while preserving metadata
    - Add sensitive data removal from event payloads
    - Create size-based content replacement for debugging
    - Add safe JSON serialization for span attributes
    - _Requirements: 2.3_

- [x] 3. Integrate tracing into WebSocketHandler
  - [x] 3.1 Add TracingClient to WebSocketHandler initialization
    - Import and initialize TracingClient in WebSocketHandler constructor
    - Add session span creation in handle_connection method
    - Implement conditional tracing execution throughout handler
    - Add proper span lifecycle management
    - _Requirements: 3.1, 3.2_

  - [x] 3.2 Instrument message handling methods
    - Add tracing to \_handle_message method for outbound events
    - Instrument \_process_responses method for inbound events
    - Add event type detection and span attribute setting
    - Implement correlation between related events using session/prompt IDs
    - _Requirements: 2.1, 2.2, 2.4, 3.2, 3.3_

  - [x] 3.3 Add tool execution tracing
    - Instrument \_handle_tool_use method with tool-specific spans
    - Add tool name and type attributes to spans
    - Trace both builtin and MCP tool execution
    - Add execution status and timing to tool spans
    - _Requirements: 3.4_

- [x] 4. Integrate tracing into BedrockClient
  - [x] 4.1 Add tracing to send_event method
    - Instrument BedrockInteractClient.send_event with span creation
    - Add event type detection from event payload
    - Implement timing measurement for send operations
    - Add error handling for failed send operations
    - _Requirements: 2.1, 3.2_

  - [x] 4.2 Add response processing tracing
    - Instrument response processing in \_process_responses method
    - Add inbound event tracing with response timing
    - Implement event correlation between send and receive
    - Add response payload tracing with sanitization
    - _Requirements: 2.2, 3.3_

- [ ] 5. Create comprehensive test suite
  - [x] 5.1 Create unit tests for TracingClient
    - Test environment variable-based initialization
    - Test tracing disabled behavior with no performance impact
    - Test span creation for different event types
    - Test payload sanitization functionality
    - Test error handling and graceful degradation
    - _Requirements: 1.1, 1.2, 1.5, 2.3, 2.5_

  - [x] 5.2 Create integration tests for WebSocket tracing (no mocking)
    - Test end-to-end conversation flow with real Bedrock and Jaeger
    - Test session span creation and lifecycle with actual trace export
    - Test event correlation across conversation turns in real traces
    - Test tool execution tracing integration with real MCP calls
    - Integration tests MUST fail if Jaeger or AWS credentials unavailable
    - _Requirements: 2.1, 2.2, 2.4, 3.1, 3.2, 3.3, 3.4_

  - [ ] 5.3 Create performance and reliability tests (real resources)
    - Test performance impact when tracing is disabled (should be zero)
    - Test minimal performance impact when tracing is enabled with real export
    - Test application continues functioning when Jaeger becomes unavailable
    - Test trace export to local Jaeger instance with real OTLP endpoint
    - Performance tests MUST use real Bedrock API calls for accurate measurement
    - _Requirements: 1.5, 2.5_

- [ ] 6. Add documentation and configuration examples
  - [ ] 6.1 Create configuration documentation
    - Document required environment variables for tracing enablement
    - Provide examples for local Jaeger setup with OTLP
    - Add authentication header configuration examples
    - Document troubleshooting steps for common issues
    - _Requirements: 1.2, 1.3_

  - [ ] 6.2 Add development setup instructions
    - Create local development setup guide with Jaeger
    - Add example docker-compose for local tracing stack
    - Document trace analysis workflow for debugging conversations
    - Add performance testing instructions
    - _Requirements: 1.2, 1.3_

- [ ] 7. Final integration and validation
  - [ ] 7.1 End-to-end testing with local Jaeger (real resources only)
    - Verify local Jaeger instance is running and accessible
    - Test complete conversation flow tracing with real Bedrock API
    - Validate trace visualization and debugging workflow in Jaeger UI
    - Test authentication header configuration with real OTLP export
    - Tests MUST fail if Jaeger is not running or AWS credentials invalid
    - _Requirements: 1.2, 1.3, 2.1, 2.2_

  - [ ] 7.2 Performance validation and optimization (real resources)
    - Measure baseline performance without tracing using real Bedrock calls
    - Measure performance impact with tracing enabled and real trace export
    - Optimize any performance bottlenecks found in actual usage scenarios
    - Validate graceful degradation when Jaeger becomes unavailable during
      operation
    - Performance tests MUST use real AWS Bedrock API for accurate measurements
    - _Requirements: 1.5, 2.5_
