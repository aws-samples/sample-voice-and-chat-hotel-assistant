# Virtual Assistant Workspace

This workspace contains the virtual assistant packages consolidated under a
unified uv workspace structure.

## Packages

- **virtual-assistant-livekit**: LiveKit voice agent with Amazon Nova Sonic
- **virtual-assistant-chat**: Text-based chat interface with Strands on
  AgentCore
- **virtual-assistant-common**: Shared utilities and common code

## Development

```bash
# Install all workspace dependencies
uv sync

# Install specific package dependencies
uv sync --package virtual-assistant-livekit
uv sync --package virtual-assistant-chat

# Run commands in workspace context
uv run --package virtual-assistant-livekit python -m virtual_assistant_livekit
uv run --package virtual-assistant-chat python -m virtual_assistant_chat

# Run tests for specific package
uv run --package virtual-assistant-livekit pytest
uv run --package virtual-assistant-chat pytest
```

## Docker

The workspace includes Dockerfiles at the root level:

- `Dockerfile-livekit`: For the LiveKit agent
- `Dockerfile-chat`: For the chat agent

Both Dockerfiles are designed to work with the workspace structure and shared
dependencies.
