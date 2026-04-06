# Hotel Assistant Chat Design

## Overview

A basic chatbot implementation using Strands Agents SDK with Amazon Nova Lite
model for hotel guest services, deployed to Bedrock AgentCore Runtime. This
chatbot will copy and adapt the MCP server integration and dynamic prompt
creation patterns from the existing LiveKit implementation.

## Architecture

```
┌─────────────────┐    ┌──────────────────────┐    ┌─────────────────┐
│   HTTP Client   │───▶│  AgentCore Runtime   │───▶│  Nova Lite LLM  │
│                 │    │  (Strands Agent)     │    │                 │
└─────────────────┘    └──────────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌──────────────────┐
                       │   MCP Server     │
                       │  (Hotel PMS)     │
                       └──────────────────┘
```

## Key Components

### 1. Agent Entry Point (`agent.py`)

- Main Strands agent with BedrockAgentCoreApp wrapper
- Uses `us.amazon.nova-lite-v1:0` model
- Integrates with MCP server for hotel tools
- HTTP endpoint handler for AgentCore Runtime

### 2. MCP Integration (`mcp/`)

- Copy `hotel_pms_config.py` from LiveKit package
- Adapt for Strands agent usage (remove LiveKit dependencies)
- Hotel PMS tool access and authentication

### 3. Prompt Management (`prompts.py`)

- Copy prompt management from LiveKit package
- Dynamic prompt generation with current date
- Hotel information caching
- Multi-language support (Spanish/English)

## Model Configuration

- **Model ID**: `us.amazon.nova-lite-v1:0`
- **Temperature**: 0.2 (consistent with LiveKit implementation)
- **Tool Choice**: auto (enable MCP tools)

## AgentCore Runtime Deployment

The agent will be deployed using Bedrock AgentCore Runtime with the following
structure:

### BedrockAgentCoreApp Integration

```python
import os
os.environ["BYPASS_TOOL_CONSENT"] = "true"

from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Initialize agent with MCP tools and Nova Lite model
agent = Agent(
    model="us.amazon.nova-lite-v1:0",
    tools=[],  # MCP tools will be added here
    system_prompt="Generated dynamic hotel prompt"
)

app = BedrockAgentCoreApp()

@app.entrypoint
def agent_invocation(payload, context):
    """Handler for agent invocation"""
    user_message = payload.get("prompt", "Hello, how can I help you today?")
    result = agent(user_message)
    return {"result": result.message}

if __name__ == "__main__":
    app.run()
```

### Deployment Process

1. Build Docker container with uv
2. Push to ECR repository
3. Deploy using `CreateAgentRuntime` API
4. Invoke using `InvokeAgentRuntime` API

## Code Copying Strategy

We'll copy and adapt the following from the LiveKit package:

1. **MCP configuration** (`hotel_pms_config.py`) - remove LiveKit dependencies
2. **Prompt management** (`prompts.py`) - copy as-is
3. **Hotel assets** (system prompts) - copy prompt files
4. **Core logic patterns** - adapt for AgentCore Runtime

## File Structure

```
packages/hotel-assistant-chat/
├── design.md                    # This file
├── tasks.md                     # Implementation checklist
├── project.json                 # NX project configuration
├── pyproject.toml              # Python dependencies (uv)
├── Dockerfile                  # Container configuration (uv-based)
├── README.md                   # Package documentation
├── hotel_assistant_chat/
│   ├── __init__.py
│   ├── mcp/                    # MCP integration (copied from LiveKit)
│   │   ├── __init__.py
│   │   └── hotel_pms_config.py # Copied and adapted (no LiveKit deps)
│   ├── prompts.py              # Copied from LiveKit
│   └── assets/                 # Copied from LiveKit
│       ├── hotel_assistant_system_prompt_es.txt
│       └── hotel_assistant_system_prompt_en.txt
└── agent.py                    # Main AgentCore entry point
```

## Dependencies

### Core Dependencies (pyproject.toml)

- `strands-agents` - Strands Agents SDK
- `bedrock-agentcore` - AgentCore Runtime SDK
- `boto3` - AWS SDK for Nova Lite model
- `httpx` - HTTP client for MCP server communication

## Configuration

### Environment Variables

- `AWS_REGION` - AWS region for Nova Lite model
- `HOTEL_PMS_MCP_URL` - MCP server URL
- `HOTEL_PMS_CLIENT_ID` - MCP authentication client ID
- `HOTEL_PMS_CLIENT_SECRET` - MCP authentication secret
- `HOTEL_PMS_USER_POOL_ID` - Cognito user pool ID

## Implementation Approach

1. **Copy Core Logic**: Copy MCP and prompt management from LiveKit
2. **Adapt for AgentCore**: Wrap Strands agent with BedrockAgentCoreApp
3. **Minimal Implementation**: Focus only on core agent functionality
4. **Preserve Patterns**: Keep the same error handling and caching patterns

## Error Handling

- Graceful degradation when MCP server is unavailable
- Fallback to basic hotel assistant without tools
- Comprehensive logging for debugging
- Proper HTTP error responses for AgentCore Runtime

## Testing Strategy

- Local testing with `app.run()` on port 8080
- Unit tests for agent initialization
- Integration tests with MCP server
- Mock tests for Nova Lite model responses
