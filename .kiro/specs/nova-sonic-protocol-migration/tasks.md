# Implementation Plan

## Simple Fix: Map Frontend Messages to Existing Backend Protocol

The issue is not that we're missing Nova Sonic protocol implementation - the
backend already has it in `NovaSonicProtocolManager`. The problem is that the
simplified frontend messages aren't properly triggering the existing protocol
flow.

- [x] 1. Fix start_recording message handler
  - Implement proper `handle_simplified_start_recording` method in
    WebSocketHandler
  - Generate unique audio content name for the recording session
  - Send `contentStart(AUDIO)` event using existing S2sEvent.content_start_audio
  - Start audio processing using existing AudioProcessor
  - _Requirements: 1.1, 2.1_

- [x] 2. Fix audio_chunk message handler
  - Implement proper `handle_simplified_audio_chunk` method in WebSocketHandler
  - Route audio chunks to existing AudioProcessor.queue_audio method
  - Ensure audio chunks are sent to Nova Sonic with correct prompt and content
    names
  - _Requirements: 1.2, 2.2_

- [x] 3. Fix stop_recording message handler
  - Implement proper `handle_simplified_stop_recording` method in
    WebSocketHandler
  - Send `contentEnd` event using existing S2sEvent.content_end
  - Stop audio processing gracefully
  - _Requirements: 1.3, 2.3_

- [x] 4. Fix Nova Sonic response processing
  - Update `_process_responses` method to convert Nova Sonic events to
    simplified messages
  - Convert `textOutput` events to `transcript` messages for frontend
  - Convert `audioOutput` events to `audio_response` messages for frontend
  - Convert `transcript` events to `transcript` messages for frontend
  - Add proper `status_update` messages for conversation state changes
  - _Requirements: 3.1, 3.2, 3.3, 3.4_

- [x] 5. Fix session initialization and cleanup
  - Ensure Nova Sonic protocol is properly initialized when connection starts
  - Ensure proper cleanup when session ends
  - Handle connection errors and recovery
  - _Requirements: 1.4, 1.5, 6.1, 6.2_

- [x] 6. Test the complete speech-to-speech flow
  - Test that frontend `start_recording` triggers Nova Sonic audio content start
  - Test that audio chunks flow from frontend → AudioProcessor → Nova Sonic
  - Test that `stop_recording` triggers content end and Nova Sonic generates
    response
  - Test that Nova Sonic responses are converted to frontend messages
  - Test that transcripts and audio responses appear in frontend UI
  - _Requirements: 6.3, 6.4, 6.5_

The key insight is that we already have:

- ✅ `NovaSonicProtocolManager` with complete protocol implementation
- ✅ `AudioProcessor` for handling audio chunks
- ✅ `SystemPromptManager` for Spanish hotel receptionist prompt
- ✅ Tool configuration and MCP integration

We just need to:

- 🔧 Fix the message routing from simplified frontend to existing backend
  components
- 🔧 Fix the response processing to convert Nova Sonic events back to simplified
  frontend messages
- 🔧 Fix the audio content lifecycle management

This is much simpler than rebuilding the entire protocol!
