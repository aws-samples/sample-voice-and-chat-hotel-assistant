# Implementation Plan

- [x] 1. Move configuration constants to backend
  - Move system prompt from `WebSocketEventManager.ts` constructor to
    `s2s_events.py` as `HOTEL_SYSTEM_PROMPT`
  - Move voice configuration (voiceId, temperature, maxTokens, topP) from
    frontend to `DEFAULT_AUDIO_OUTPUT_CONFIG` and `DEFAULT_INFER_CONFIG` in
    backend
  - Move tool specifications from frontend `startPrompt()` method to
    `DEFAULT_TOOL_CONFIG` in backend
  - Update `S2sEvent` class methods to use these backend configuration constants
    instead of parameters
  - _Requirements: 1.2, 4.1, 4.2, 4.3_

- [x] 2. Implement automatic session initialization in WebSocketHandler
  - Modify `WebSocketHandler` to automatically call session initialization after
    successful authentication
  - Add method to send sessionStart, promptStart, and system prompt events using
    backend configuration
  - Ensure session initialization happens before frontend can send audio input
  - Use existing `S2sEvent` methods with backend configuration constants
  - _Requirements: 1.1, 1.3, 3.1, 3.3_

- [x] 3. Remove configuration from frontend WebSocketEventManager
  - Remove `startSession()` method from `WebSocketEventManager.ts`
  - Remove `startPrompt()` method from `WebSocketEventManager.ts`
  - Remove `sendSystemPrompt()` method from `WebSocketEventManager.ts`
  - Remove system prompt parameter from constructor
  - Keep all existing audio processing methods (`startAudioContent`,
    `sendAudioChunk`, etc.) unchanged
  - _Requirements: 2.1, 2.3, 2.4, 2.5_

- [x] 4. Update frontend to rely on backend session initialization
  - Modify `WebSocketEventManager` constructor to not accept system prompt
    parameter
  - Update connection flow to wait for backend session initialization instead of
    calling `startSession()`
  - Keep existing `setupSocketListeners()`, `handleMessage()`, and audio
    processing methods unchanged
  - Ensure `startAudioContent()` and transcript display continue to work exactly
    as before
  - _Requirements: 1.4, 4.5, 5.1, 5.2, 5.3, 5.4_

- [x] 5. Test complete speech-to-speech flow
  - Test that conversation starts automatically when WebSocket connects (backend
    initializes session)
  - Test that existing audio capture and processing continues to work unchanged
  - Test that transcripts and audio responses display correctly in frontend UI
  - Test that tool usage works transparently without frontend configuration
    knowledge
  - Verify that all session configuration (system prompt, voice, tools) is now
    backend-controlled
  - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_
