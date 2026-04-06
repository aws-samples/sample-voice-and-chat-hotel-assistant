# Implementation Plan: LiveKit Nova Sonic 2 Upgrade

## Overview

This implementation plan upgrades the LiveKit voice agent from Amazon Nova Sonic
1 to Nova Sonic 2, implementing multi-language support with the Tiffany polyglot
voice, native "speak first" capability, and configurable turn-taking.

## Task List

- [x] 1. Update Dependencies to Git-Based LiveKit Agents
  - Update pyproject.toml with Git URLs for pre-release Nova Sonic 2 support
  - Install dependencies and verify Nova Sonic 2 availability
  - Log versions at startup for debugging
  - _Requirements: 7.1, 7.2, 7.3, 7.4_

- [x] 1.1 Update pyproject.toml with Git dependencies
  - Replace livekit-agents and livekit-plugins-aws with Git URLs
  - Use commit 9fb59dd2d676069fb8e24d641dd374e5793f42b6
  - Specify subdirectories for each package
  - _Requirements: 7.1, 7.2, 7.3_

- [x] 1.2 Install and verify dependencies
  - Run `uv sync` to install Git-based dependencies
  - Verify livekit-agents version includes Git commit info
  - Verify Nova Sonic 2 support with `with_nova_sonic_2()` import
  - Test that RealtimeModel.with_nova_sonic_2() creates correct model
  - _Requirements: 7.3, 7.4_

- [x] 1.3 Add version logging
  - Log livekit-agents version at startup
  - Log livekit-plugins-aws version at startup
  - Detect and log if using Git-based vs PyPI installation
  - _Requirements: 7.4, 9.1_

- [x] 2. Create VirtualAssistant Agent Class with Multi-Language Support
  - Implement Agent subclass with on_enter() hook for greeting
  - Use Tiffany polyglot voice for multi-language support
  - Implement multi-language system prompt with language mirroring rules
  - _Requirements: 2.1, 2.2, 3.1, 3.2, 11.1, 11.2, 11.3_

- [x] 2.1 Create VirtualAssistant class with on_enter() hook
  - Create new VirtualAssistant class inheriting from Agent
  - Implement on_enter() method for native greeting
  - Use generate_reply(instructions="...") for greeting in multiple languages
  - Make greeting configurable via constructor parameter
  - _Requirements: 2.1, 2.2, 6.1, 6.2, 6.3_

- [x] 2.2 Implement multi-language system prompt
  - Create system prompt with language mirroring rules
  - Support Spanish, English, French, German, Italian, Portuguese, Hindi
  - Keep persona industry-agnostic (customization via environment config)
  - Add guidance for tool usage explanations in user's language
  - _Requirements: 3.2, 11.1, 11.2, 11.3, 11.4, 11.5_

- [x] 2.3 Write unit tests for VirtualAssistant class
  - Test on_enter() calls generate_reply with greeting
  - Test greeting includes multi-language instructions
  - Test system prompt includes language mirroring rules
  - Test configurable greeting parameter
  - _Requirements: 2.1, 2.2, 11.1_

- [x] 3. Update RealtimeModel Configuration for Nova Sonic 2
  - Switch from RealtimeModel() to RealtimeModel.with_nova_sonic_2()
  - Configure Tiffany polyglot voice
  - Add configurable turn-taking sensitivity
  - Remove unused TTS fallback
  - _Requirements: 1.1, 1.2, 3.1, 3.5, 4.1, 4.2, 4.3_

- [x] 3.1 Update model initialization to with_nova_sonic_2()
  - Replace RealtimeModel() with RealtimeModel.with_nova_sonic_2()
  - Configure voice="tiffany" for polyglot support
  - Add turn_detection parameter from environment variable
  - Keep tool_choice="auto" for MCP integration
  - Log model configuration at startup
  - _Requirements: 1.1, 1.2, 3.1, 4.1, 9.1, 9.3, 9.4_

- [x] 3.2 Add ENDPOINTING_SENSITIVITY configuration
  - Read ENDPOINTING_SENSITIVITY from environment (default: "MEDIUM")
  - Validate sensitivity value (HIGH, MEDIUM, LOW)
  - Log warning and default to MEDIUM if invalid
  - Pass to turn_detection parameter
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 9.4_

- [x] 3.3 Remove unused TTS fallback
  - Remove aws.TTS() from AgentSession configuration
  - Nova Sonic 2 handles all TTS natively
  - Clean up any TTS-related imports
  - _Requirements: 1.1_

- [x] 3.4 Write unit tests for model configuration
  - Test with_nova_sonic_2() creates correct model
  - Test voice="tiffany" is configured
  - Test turn_detection uses environment variable
  - Test invalid sensitivity defaults to MEDIUM
  - Test tool_choice="auto" is preserved
  - _Requirements: 1.1, 3.1, 4.1, 4.5_

- [x] 4. Update Entrypoint to Use VirtualAssistant Agent
  - Replace direct Agent() instantiation with VirtualAssistant()
  - Remove session.say() greeting workaround
  - Update AgentSession to use new model configuration
  - Maintain MCP server integration
  - _Requirements: 2.1, 2.2, 6.1, 6.2, 8.1, 8.2_

- [x] 4.1 Update entrypoint to use VirtualAssistant
  - Replace Agent(instructions=...) with VirtualAssistant(instructions=...)
  - Remove session.say() greeting call
  - Remove greeting_audio() import and usage
  - Let on_enter() handle greeting automatically
  - _Requirements: 2.1, 2.2, 6.1, 6.2, 6.3, 6.5_

- [x] 4.2 Update AgentSession configuration
  - Use new RealtimeModel.with_nova_sonic_2() configuration
  - Remove tts parameter (no longer needed)
  - Keep mcp_servers parameter for tool integration
  - Verify MCP integration still works
  - _Requirements: 1.1, 8.1, 8.2, 8.3_

- [ ]\* 4.3 Write integration tests for entrypoint
  - Test agent greets on enter without audio workaround
  - Test MCP servers are properly integrated
  - Test session starts and closes correctly
  - Test greeting uses generate_reply()
  - _Requirements: 2.1, 6.1, 8.1_

- [x] 5. Update CDK Infrastructure for Nova Sonic 2
  - Add ENDPOINTING_SENSITIVITY environment variable
  - Update Bedrock permissions for Nova Sonic 2 model
  - Update Docker image build process
  - Verify deployment configuration
  - _Requirements: 10.1, 10.2, 10.3, 10.4_

- [x] 5.1 Add environment variable to ECS task definition
  - Add ENDPOINTING_SENSITIVITY with default "MEDIUM"
  - Document new environment variable in CDK code
  - Ensure variable is passed to container
  - _Requirements: 10.2_

- [x] 5.2 Update Bedrock IAM permissions
  - Add amazon.nova-2-sonic-v1:0 to allowed models
  - Keep amazon.nova-sonic-v1:0 for gradual migration
  - Update IAM policy statement in CDK
  - _Requirements: 10.1, 10.4_

- [x] 5.3 Update Docker build for Git dependencies
  - Verify Dockerfile works with Git-based dependencies
  - Add verification step for Nova Sonic 2 support
  - Test Docker build locally
  - _Requirements: 10.3_
- [x] 5.4 Test CDK infrastructure with synth
  - Run `cdk synth` to validate template generation
  - Verify environment variable appears in task definition
  - Verify Bedrock permissions include Nova Sonic 2 model
  - Check for any CDK synthesis errors
  - _Requirements: 10.1, 10.2_

- [ ] 6. Add Comprehensive Logging for Nova Sonic 2
  - Log model version and configuration at startup
  - Log voice and turn-taking settings
  - Log text input usage (if used in future)
  - Add debug logging for Nova Sonic 2 features
  - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 6.1 Add startup logging
  - Log Nova Sonic model version (amazon.nova-2-sonic-v1:0)
  - Log voice configuration (tiffany)
  - Log turn_detection setting
  - Log tool_choice configuration
  - _Requirements: 9.1, 9.3, 9.4_

- [ ] 6.2 Add language detection logging
  - Log when Spanish input is detected
  - Log when English input is detected
  - Log when other languages are detected
  - Use DEBUG level for detailed language info
  - _Requirements: 9.5_

- [ ] 6.3 Write tests for logging
  - Test startup logs include model version
  - Test startup logs include voice configuration
  - Test startup logs include turn_detection setting
  - _Requirements: 9.1, 9.3, 9.4_

- [ ] 7. Update Documentation
  - Update README with Nova Sonic 2 capabilities
  - Document new environment variables
  - Document multi-language support with Tiffany voice
  - Add troubleshooting guide
  - Document migration from Nova Sonic 1
  - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5_

- [ ] 7.1 Update README with Nova Sonic 2 information
  - Add section on Nova Sonic 2 benefits
  - Document Tiffany polyglot voice capabilities
  - Explain automatic language detection
  - List supported languages (7 languages)
  - _Requirements: 13.1, 13.4_

- [ ] 7.2 Document environment variables
  - Document ENDPOINTING_SENSITIVITY (HIGH, MEDIUM, LOW)
  - Document default values
  - Explain when to use each sensitivity setting
  - Update existing MODEL_TEMPERATURE documentation
  - _Requirements: 13.2_

- [ ] 7.3 Add troubleshooting guide
  - "Nova Sonic 2 not available in region" solution
  - "Text input not working" solution
  - "Greeting not playing" solution
  - "Wrong language detected" solution
  - _Requirements: 13.3_

- [ ] 7.4 Document migration from Nova Sonic 1
  - List key changes (voice, greeting, dependencies)
  - Provide rollback instructions
  - Document testing checklist
  - _Requirements: 13.5_

- [ ] 8. Testing and Validation
  - Run unit tests and verify all pass
  - Test greeting with multiple languages
  - Test turn-taking with different sensitivities
  - Test MCP tool integration
  - Verify voice quality and naturalness
  - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5_

- [ ] 8.1 Run automated tests
  - Run all unit tests with pytest
  - Run integration tests
  - Verify test coverage for new code
  - Fix any failing tests
  - _Requirements: 12.1_

- [ ] 8.2 Manual testing with console mode
  - Test Spanish greeting: "¡Hola! Soy su asistente..."
  - Test English greeting by speaking English first
  - Test language switching mid-conversation
  - Test French, German, Italian greetings
  - _Requirements: 12.2, 12.4_

- [ ] 8.3 Test turn-taking sensitivity
  - Test with ENDPOINTING_SENSITIVITY=HIGH (fast responses)
  - Test with ENDPOINTING_SENSITIVITY=MEDIUM (balanced)
  - Test with ENDPOINTING_SENSITIVITY=LOW (patient)
  - Verify appropriate response timing for each
  - _Requirements: 12.3_

- [ ] 8.4 Test MCP tool integration
  - Request information in Spanish
  - Request information in English
  - Execute tool operations in Spanish
  - Execute tool operations in English
  - Verify tool results are explained in correct language
  - _Requirements: 12.5_

- [ ] 8.5 Verify voice quality
  - Listen to Tiffany voice in Spanish
  - Listen to Tiffany voice in English
  - Compare to previous Lupe voice quality
  - Verify natural language transitions
  - _Requirements: 12.4_

- [ ] 9. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Deployment Preparation
  - Build Docker image with new dependencies
  - Test Docker image locally
  - Prepare deployment plan
  - Document rollback procedure
  - _Requirements: 10.3_

- [ ] 10.1 Build and test Docker image
  - Build Docker image with Git dependencies
  - Verify Nova Sonic 2 support in container
  - Test container startup and shutdown
  - Verify environment variables are passed correctly
  - _Requirements: 10.3_

- [ ] 10.2 Prepare deployment documentation
  - Document deployment steps
  - Document verification steps
  - Document monitoring checklist
  - Document rollback procedure
  - _Requirements: 13.5_

- [ ] 11. Final Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

### Task Dependencies

- Task 2 depends on Task 1 (need dependencies installed)
- Task 3 depends on Task 1 (need Nova Sonic 2 support)
- Task 4 depends on Tasks 2 and 3 (need agent and model)
- Task 5 can be done in parallel with Tasks 2-4
- Task 6 can be done in parallel with Tasks 2-4
- Task 7 should be done after Tasks 2-4 are complete
- Task 8 depends on all previous tasks
- Task 10 depends on Task 8 passing

### Testing Strategy

Unit tests are colocated with implementation tasks as subtasks. Integration
tests are in Task 8. This ensures:

- Core functionality is validated immediately after implementation
- Tests serve as documentation for the implementation
- Bugs are caught early in the development process

### Migration Path

This implementation maintains backward compatibility:

- MCP integration unchanged
- Industry-agnostic persona maintained (now multi-language)
- Same infrastructure patterns
- Clear rollback path (change one line to use with_nova_sonic_1())

### Multi-Language Support

The Tiffany voice provides automatic language detection and response in:

- Spanish, English (US and GB)
- French
- German
- Italian
- Portuguese
- Hindi

No additional configuration needed - Nova Sonic 2 handles language detection
automatically.
