# Virtual Assistant Chat

Professional virtual assistant chatbot built with Strands Agents SDK and Amazon
Bedrock AgentCore Runtime. Provides multilingual guest services through natural
conversation with real-time hotel PMS integration.

## Features

### Core Capabilities

- **Hotel PMS Integration**: Real-time data access through MCP server
  connections
- **Session Management**: Persistent conversation context with Amazon Bedrock
  Amazon Bedrock AgentCore Memory
- **Dynamic Prompts**: Context-aware prompts with current date and hotel
  information

### Technical Features

- **Multi-Model Support**: Optimized for Amazon Nova and Anthropic Claude models
  via Amazon Bedrock, including Claude 3.5 Haiku with configurable temperature
- **MCP Protocol**: Secure OAuth2 authentication with hotel PMS systems
- **Memory Persistence**: Conversation history with configurable turn limits
- **OpenTelemetry Tracing**: Built-in observability and performance monitoring
- **AgentCore Ready**: Native support for Bedrock AgentCore Runtime deployment

## Project Structure

```
virtual-assistant-chat/
├── hotel_assistant_chat/           # Package source code
│   ├── __init__.py
│   ├── agent.py                   # Main AgentCore Runtime entry point
│   ├── memory_hooks.py            # AgentCore Memory integration hooks
│   └── prompts.py                 # Dynamic prompt generation with fallback prompts
├── tests/                         # Test suite
│   ├── __init__.py
│   ├── test_agent.py             # Agent functionality tests
│   ├── test_integration.py       # Integration tests with AWS services
│   └── test_memory_hooks.py      # Memory integration tests
├── pyproject.toml                # Python dependencies and project configuration
├── .env.example                  # Environment configuration template
├── .dockerignore                 # Docker build exclusions
└── project.json                  # NX project configuration
```

**Note**: This package is part of the virtual-assistant workspace. The `uv.lock`
file is located at the workspace root (`packages/virtual-assistant/uv.lock`),
and AWS utilities are imported from the shared `virtual-assistant-common`
package.

## Key Components

### Agent Core (`agent.py`)

- **BedrockAgentCoreApp**: Main application entry point using Amazon Bedrock
  AgentCore
- **Strands Agent**: Conversational AI agent with tool integration via Strands
  framework
- **Memory Integration**: Session-based conversation persistence with
  MemoryClient
- **MCP Client**: Real-time hotel PMS data access through
  `hotel_assistant_common.hotel_pms_mcp_client`
- **OpenTelemetry**: Distributed tracing and observability with baggage context
- **AWS Integration**: Uses shared AWS utilities from
  `hotel_assistant_common.utils.aws`

### Memory Management (`memory_hooks.py`)

- **MemoryHookProvider**: AgentCore Memory integration hooks
- **Session Initialization**: Automatic greeting for new sessions
- **Conversation Loading**: Historical context retrieval
- **Event Storage**: Message persistence with timestamps

### Prompt Engineering (`prompts.py`)

- **Dynamic Prompts**: Context-aware system prompts with
  `generate_dynamic_hotel_instructions`
- **Hotel Data Integration**: Real-time hotel information from MCP client
- **Multilingual Support**: Spanish (es-mx) and English (en) prompt templates with fallback prompts in prompts.py
- **Base Prompt Loading**: `load_base_hotel_prompt` function with
  fallback prompts when template files are not available

## Configuration

### Environment Variables

The agent supports flexible configuration through environment variables or AWS
Secrets Manager. Copy `.env.example` to `.env` and configure:

#### Core Configuration

```bash
# AWS Configuration
AWS_REGION=us-east-1                    # AWS region for all services
BEDROCK_MODEL_ID=global.amazon.nova-2-lite-v1:0  # Bedrock model identifier
MODEL_TEMPERATURE=0.2                   # Response randomness (0.0-1.0)

# Logging and Monitoring
LOG_LEVEL=INFO                          # Logging level (DEBUG, INFO, WARN, ERROR)
```

#### Hotel PMS MCP Server Configuration

Choose **one** of the following configuration methods:

**Option 1: AWS Secrets Manager (Recommended for Production)**

```bash
# Single secret containing all MCP configuration
HOTEL_PMS_MCP_SECRET_ARN=arn:aws:secretsmanager:us-east-1:123456789012:secret:hotel-pms-mcp-config
```

**Option 2: Individual Environment Variables (Development)**

```bash
# MCP Server Connection
HOTEL_PMS_MCP_URL=https://your-agentcore-gateway.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp
HOTEL_PMS_MCP_CLIENT_ID=your-cognito-client-id
HOTEL_PMS_MCP_CLIENT_SECRET=your-cognito-client-secret
HOTEL_PMS_MCP_USER_POOL_ID=us-east-1_YourUserPool

# Connection Settings
HOTEL_PMS_MCP_TIMEOUT=30                # Request timeout in seconds
HOTEL_PMS_MCP_MAX_RETRIES=3             # Maximum retry attempts
```

#### Memory Configuration

Amazon Bedrock AgentCore Memory provides conversation persistence:

```bash
# Memory Settings
AGENTCORE_MEMORY_ID=mem-12345abcdef     # Memory resource ID (from infrastructure)
AGENTCORE_MEMORY_MAX_TURNS=30           # Maximum conversation turns to load
```

**Memory Behavior:**

- **With Memory**: Maintains conversation context across conversation turns
- **Without Memory**: Operates in stateless mode (each request is independent)
- **Greeting Initialization**: Automatically initializes new sessions with
  Spanish greeting

### AWS Secrets Manager Configuration

For production deployments, store sensitive MCP configuration in AWS Secrets
Manager:

#### Secret Structure

Create a secret with the following JSON structure:

```json
{
  "url": "https://your-agentcore-gateway.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp",
  "client_id": "your-cognito-client-id",
  "client_secret": "your-cognito-client-secret",
  "user_pool_id": "us-east-1_YourUserPool",
  "region": "us-east-1",
  "timeout": 30,
  "max_retries": 3
}
```

## API Endpoints

### POST /invocations

Main agent invocation endpoint compatible with Amazon Bedrock AgentCore Runtime.

**Request Format**:

```json
{
  "prompt": "Hola, necesito ayuda con mi reservación",
  "actorId": "guest-maria-123",
  "modelId": "us.amazon.nova-lite-v1:0",
  "temperature": 0.2
}
```

**Request Headers**:

```
Content-Type: application/json
X-Amzn-Bedrock-AgentCore-Runtime-Session-Id: hotel-session-456
```

**Response Format**:

```json
{
  "message": "¡Hola! Soy su asistente virtual de hoteles. Estoy aquí para ayudarle con cualquier consulta sobre su reservación. ¿En qué puedo asistirle hoy?"
}
```

**Parameters**:

- `prompt` (required): User's message or question
- `actorId` (optional): Unique identifier for the guest (required for memory)
- `modelId` (optional): Bedrock model ID (defaults to environment configuration)
- `temperature` (optional): Response randomness 0.0-1.0 (defaults to environment
  configuration)

### GET /ping

Health check endpoint for monitoring and load balancing.

**Response**:

```json
{
  "status": "healthy",
  "timestamp": "2024-08-29T22:04:07.777Z"
}
```

### Session Management

Sessions are managed through the `X-Amzn-Bedrock-AgentCore-Runtime-Session-Id`
header and `actorId` parameter:

- **New Session**: Generate a unique session ID (minimum 33 characters,
  recommend UUID) for each new conversation
- **Continue Session**: Use the same session ID for all related invocations to
  maintain context
- **Memory Loading**: Previous conversation turns automatically loaded when
  memory is configured

**Session ID Requirements:**

- Minimum 33 characters in length
- Unique per user/conversation
- Recommended format: UUID or `user-{userId}-conversation-{uuid}`
- Generated by the client application, not the AgentCore service

## Development

### Local Development Setup

```bash
# Install dependencies
uv sync

# Install development dependencies
uv sync --group dev

# Set up environment
cp .env.example .env
# Edit .env with your configuration
```

### Code Quality

This project uses ruff for formatting and linting with strict quality standards:

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Fix linting issues automatically
uv run ruff check --fix .

# Run all quality checks
uv run ruff check --fix . && uv run ruff format .
```

### Testing

Test suite with unit and integration tests:

```bash
# Run unit tests only
uv run pytest

# Run all tests including integration
uv run pytest -m integration

# Run with coverage report
uv run pytest --cov=hotel_assistant_chat --cov-report=html

# Run specific test file
uv run pytest tests/test_agent.py -v
```
