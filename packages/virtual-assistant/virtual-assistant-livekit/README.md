# Virtual Assistant LiveKit

Real-time voice assistant for hotel guest services built with LiveKit and Amazon
Nova Sonic. Provides natural speech-to-speech conversations with hotel PMS
integration through MCP protocol.

## Features

### Core Capabilities

- **Real-Time Voice Processing**: Natural speech-to-speech interactions using
  Amazon Nova Sonic
- **Hotel PMS Integration**: Real-time data access through MCP server
  connections
- **Multi-Language Support**: Spanish (primary) with extensible language
  configuration
- **Professional Hotel Persona**: Contextual responses tailored for hospitality
  industry

### Technical Features

- **Amazon Nova Sonic Integration**: Bidirectional streaming for low-latency
  voice conversations
- **ECS Auto-Scaling**: CloudWatch metrics integration for production scaling
- **Task Protection**: Prevents ECS task termination during active calls
- **Prewarm Architecture**: Multi-process component initialization for
  performance
- **Secure Credentials**: AWS Secrets Manager integration with environment
  fallback
- **Health Monitoring**: Built-in health checks for container orchestration

## Project Structure

```
virtual-assistant-livekit/
├── hotel_assistant_livekit/           # Package source code
│   ├── __init__.py
│   ├── agent.py                      # Main LiveKit agent entry point
│   ├── credentials.py                # LiveKit credential management
│   ├── metrics.py                    # CloudWatch metrics publishing
│   ├── prompts.py                    # Dynamic prompt generation
│   ├── audio_utils.py                # Audio processing utilities
│   ├── hotel_pms_mcp_server.py       # MCP server integration
│   └── assets/                       # Audio files
│       ├── greeting.raw              # Pre-recorded greeting audio
│       └── un_momento.raw            # Thinking audio
├── tests/                            # Test suite
│   ├── test_agent_initialization.py  # Agent startup and prewarm tests
│   ├── test_metrics.py               # CloudWatch metrics tests
│   ├── test_prompts.py               # Dynamic prompt generation tests
│   ├── test_audio_utils.py           # Audio processing tests
│   └── integration/                  # Integration tests with AWS services
├── docs/                             # Documentation and images
├── pyproject.toml                    # Python dependencies and project configuration
├── .env.example                      # Environment configuration template
└── project.json                      # NX project configuration
```

**Note**: This package is part of the virtual-assistant workspace. The `uv.lock`
file is located at the workspace root (`packages/virtual-assistant/uv.lock`),
and shared utilities are imported from the `virtual-assistant-common` package.

## Key Components

### Agent Core (`agent.py`)

- **LiveKit Agent**: Main voice agent using Nova Sonic for speech-to-speech
- **Prewarm Architecture**: Multi-process component initialization for
  performance
- **Session Management**: Automatic greeting, conversation tracking, and cleanup
- **MCP Integration**: Real-time hotel PMS data access through
  `hotel_assistant_common.hotel_pms_mcp_client`
- **Metrics Publishing**: CloudWatch integration for ECS auto-scaling
- **Error Recovery**: Graceful degradation when optional services fail

### Credentials Management (`credentials.py`)

- **LiveKit Configuration**: Secure management of LiveKit server connection
  credentials
- **AWS Secrets Manager Integration**: Production credentials stored securely
  with automatic retrieval
- **Development Support**: Direct environment variable configuration for local
  development

### Metrics Publishing (`metrics.py`)

- **CloudWatch Integration**: Active calls metrics for ECS auto-scaling
- **Cross-Process Tracking**: File-based counters for multi-process environments
- **Task Protection**: ECS task protection during active calls
- **Performance Monitoring**: Configurable publishing intervals and dimensions

### Prompt Engineering (`prompts.py`)

- **Dynamic Instructions**: Context-aware system prompts with hotel information
- **Hotel Data Integration**: Real-time hotel information from MCP client

## Configuration

### Environment Variables

The agent supports flexible configuration through environment variables or AWS
Secrets Manager. Copy `.env.example` to `.env` and configure:

#### Core Configuration

```bash
# AWS Configuration
AWS_REGION=us-east-1                    # AWS region for all services
BEDROCK_REGION=us-east-1                # Bedrock region (defaults to AWS_REGION)
BEDROCK_MODEL_ID=amazon.nova-sonic-v1:0      # Nova Sonic model identifier
MODEL_TEMPERATURE=0.0                   # Response randomness (0.0-1.0)

# Logging and Monitoring
LOG_LEVEL=INFO                          # Logging level (DEBUG, INFO, WARN, ERROR)
```

#### LiveKit Configuration

Choose **one** of the following configuration methods:

**Option 1: AWS Secrets Manager (Recommended for Production)**

```bash
# Single secret containing all LiveKit configuration
LIVEKIT_SECRET_NAME=virtual-assistant-livekit
```

**Option 2: Individual Environment Variables (Development)**

```bash
# LiveKit Server Connection
LIVEKIT_URL=wss://your-livekit-server.com
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
```

#### CloudWatch Metrics Configuration

```bash
# Metrics Publishing
CLOUDWATCH_NAMESPACE=HotelAssistant     # CloudWatch namespace
CLOUDWATCH_METRIC_NAME=ActiveCalls     # Metric name for auto-scaling
ECS_SERVICE_NAME=virtual-assistant-livekit # ECS service name
METRICS_PUBLISH_INTERVAL=60             # Publishing interval in seconds

# ECS Task Protection
TASK_PROTECTION_DURATION_MINUTES=120    # Task protection duration (2 hours default)
```

### AWS Secrets Manager Configuration

For production deployments, store LiveKit credentials in AWS Secrets Manager:

#### Secret Structure

Create a secret with the following JSON structure:

```json
{
  "LIVEKIT_URL": "wss://your-livekit-server.com",
  "LIVEKIT_API_KEY": "your-api-key",
  "LIVEKIT_API_SECRET": "your-api-secret"
}
```

#### Creating the Secret

```bash
aws secretsmanager create-secret \
  --name "virtual-assistant-livekit" \
  --description "LiveKit credentials for Virtual Assistant" \
  --secret-string '{
    "LIVEKIT_URL": "wss://your-livekit-server.com",
    "LIVEKIT_API_KEY": "your-api-key",
    "LIVEKIT_API_SECRET": "your-api-secret"
  }'
```

## Quick Start

### Prerequisites

- **Python 3.13+**: Required for running the agent
- **AWS CLI**: Configured with credentials that have Amazon Bedrock access
- **Amazon Nova Sonic**: Model access enabled in Amazon Bedrock console
- **LiveKit Server**: Local development server or LiveKit Cloud account

### Local Development Setup

1. **Install LiveKit Server**:

   ```bash
   # macOS
   brew install livekit

   # Linux
   curl -sSL https://get.livekit.io | bash

   # Start development server
   livekit-server --dev
   ```

2. **Configure Environment**:

   ```bash
   # LiveKit credentials (for local development)
   export LIVEKIT_URL=ws://localhost:7880
   export LIVEKIT_API_KEY=devkey
   export LIVEKIT_API_SECRET=secret

   # AWS credentials for Bedrock
   export AWS_REGION=us-east-1
   export BEDROCK_MODEL_ID=amazon.nova-sonic-v1:0
   ```

3. **Install Dependencies**:

   ```bash
   cd packages/virtual-assistant-livekit
   uv sync
   ```

4. **Start the Agent**:

   ```bash
   uv run python -m hotel_assistant_livekit.agent start
   ```

5. **Test with LiveKit Playground**:
   - Open [LiveKit Agents Playground](https://agents-playground.livekit.io/)
   - Use Manual connection with `http://localhost:7880`
   - Generate token:
     `lk token create --api-key devkey --api-secret secret --join --room virtual-assistant --identity guest1 --valid-for 24h`

## Development

### Development Setup

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

This project uses ruff for formatting and linting:

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Fix linting issues automatically
uv run ruff check --fix .
```

### Testing

Test suite with unit and integration tests:

```bash
# Run unit tests only
uv run pytest

# Run all tests including integration
uv run pytest -m integration

# Run with coverage report
uv run pytest --cov=hotel_assistant_livekit --cov-report=html

# Run specific test categories
uv run pytest tests/test_metrics.py -v
uv run pytest tests/test_agent_initialization.py -v
```
