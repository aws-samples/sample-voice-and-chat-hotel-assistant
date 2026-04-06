# Backend Session Control Design

## Overview

This design moves Nova Sonic session configuration from the frontend to the
backend while preserving the existing working audio and transcript
functionality. The goal is to remove the ability for the frontend to control
system prompts, tools, voice settings, and other sensitive configuration while
maintaining the current user experience.

## Architecture

### Current vs Target Architecture

**Current (Insecure)**:

```
Frontend WebSocketEventManager → sessionStart/promptStart/systemPrompt → Backend → Nova Sonic
Frontend WebSocketEventManager → audioInput/audioOutput → Backend → Nova Sonic
```

**Target (Secure)**:

```
Backend WebSocketHandler → sessionStart/promptStart/systemPrompt → Nova Sonic
Frontend WebSocketEventManager → audioInput/audioOutput → Backend → Nova Sonic (unchanged)
```

### Component Changes

#### Frontend Changes (Minimal)

- Keep existing `WebSocketEventManager.ts` audio and transcript functionality
- Remove `startSession()`, `startPrompt()`, and `sendSystemPrompt()` methods
- Remove system prompt, voice, and tool configuration from constructor
- Keep all existing audio processing, transcript display, and response handling

#### Backend Changes (Focused)

- Add automatic session initialization to `WebSocketHandler`
- Move configuration constants to `s2s_events.py`
- Preserve existing audio processing and response handling
- Add backend-controlled session startup

## Configuration Migration

### Move to Backend Constants

**System Configuration** (in `s2s_events.py`):

```python
# Hotel receptionist system prompt (moved from frontend)
HOTEL_SYSTEM_PROMPT = """
You are a friend. The user and you will engage in a spoken dialog
exchanging the transcripts of a natural real-time conversation.
Keep your responses short, generally two or three sentences for chatty scenarios.
"""

# Voice and model configuration (moved from frontend)
DEFAULT_AUDIO_OUTPUT_CONFIG = {
    "mediaType": "audio/lpcm",
    "sampleRateHertz": 24000,
    "sampleSizeBits": 16,
    "channelCount": 1,
    "voiceId": "matthew",  # Or "lupe" for Spanish
    "encoding": "base64",
    "audioType": "SPEECH",
}

DEFAULT_INFER_CONFIG = {
    "maxTokens": 1024,
    "topP": 0.9,
    "temperature": 0.7
}

# Tool configuration (moved from frontend)
DEFAULT_TOOL_CONFIG = {
    "tools": [
        {
            "toolSpec": {
                "name": "getDateAndTimeTool",
                "description": "get information about the current date and current time",
                "inputSchema": {"json": "..."}
            }
        },
        {
            "toolSpec": {
                "name": "getWeatherTool",
                "description": "Get the current weather for a given location",
                "inputSchema": {"json": "..."}
            }
        }
    ]
}
```

## Implementation Strategy

### Phase 1: Backend Configuration

1. Move all configuration constants from frontend to `s2s_events.py`
2. Update `S2sEvent` methods to use backend constants
3. Add automatic session initialization to `WebSocketHandler`

### Phase 2: Frontend Cleanup

1. Remove session initialization methods from `WebSocketEventManager`
2. Remove configuration parameters from constructor
3. Keep all existing audio and transcript functionality intact

### Phase 3: Integration Testing

1. Test that backend automatically initializes sessions
2. Verify existing audio/transcript functionality works unchanged
3. Confirm configuration is now backend-controlled

## Preserved Functionality

### Frontend Keeps (Unchanged)

- Audio capture and processing
- Audio playback and response handling
- Transcript display and conversation UI
- WebSocket connection management
- Error handling and status updates
- All existing user interaction patterns

### Backend Adds

- Automatic session initialization after authentication
- Server-side system prompt management
- Server-side voice and model configuration
- Server-side tool specification management

## Security Benefits

1. **Configuration Control**: System prompts, tools, and model parameters
   controlled server-side
2. **Reduced Frontend Complexity**: Frontend cannot manipulate session
   configuration
3. **Centralized Management**: All configuration changes require backend
   deployment
4. **Maintained Functionality**: All existing features continue to work
   identically

## Backward Compatibility

- User experience remains completely unchanged
- All speech-to-speech features continue to work
- Audio quality and responsiveness preserved
- Transcript display and conversation flow identical
- No changes to UI components or user interactions
