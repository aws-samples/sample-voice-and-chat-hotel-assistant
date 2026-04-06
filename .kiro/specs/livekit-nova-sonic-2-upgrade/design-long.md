# Design Document: LiveKit Nova Sonic 2 Upgrade

## Overview

This design document outlines the technical approach for upgrading the LiveKit
voice agent from Amazon Nova Sonic 1 to Amazon Nova Sonic 2
(`amazon.nova-2-sonic-v1:0`). The upgrade leverages LiveKit agents 1.3.9+ which
includes native support for Nova Sonic 2's enhanced capabilities including text
input, expanded multilingual voice support, and configurable turn-taking
behavior.

### Key Benefits of Nova Sonic 2

- **Native "speak first" capability**: Eliminates the need for audio input
  workarounds
- **Text message input**: Enables programmatic control via
  `generate_reply(instructions="...")`
- **Expanded voice support**: 16 voices across 8 languages (vs 11 voices in
  Nova 1)
- **Polyglot voices**: Matthew and Tiffany can seamlessly switch between
  languages
- **Configurable turn-taking**: HIGH/MEDIUM/LOW sensitivity for different use
  cases
- **Improved credential management**: Singleton pattern prevents credential
  loading spam
- **Session recycling**: Automatic restart before 8-minute AWS limit

## Architecture

### Current Architecture (Nova Sonic 1)

```
┌─────────────────────────────────────────────────────────────┐
│                    LiveKit Agent Worker                      │
│                                                              │
│  ┌────────────┐    ┌──────────────────────────────────┐   │
│  │  Prewarm   │───▶│  MCP Client Manager              │   │
│  │  Function  │    │  - Load system prompt            │   │
│  └────────────┘    │  - Initialize MCP connections    │   │
│                    └──────────────────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────────────────┐   │
│  │              Entrypoint Function                    │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐ │   │
│  │  │  AgentSession                                 │ │   │
│  │  │  - llm: RealtimeModel(voice="lupe")          │ │   │
│  │  │  - tts: aws.TTS (fallback, not used)         │ │   │
│  │  │  - mcp_servers: [HotelPmsMCPServer]          │ │   │
│  │  └──────────────────────────────────────────────┘ │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐ │   │
│  │  │  Greeting via session.say()                   │ │   │
│  │  │  - Uses pre-recorded greeting_audio()        │ │   │
│  │  │  - Workaround for "speak first" limitation   │ │   │
│  │  └──────────────────────────────────────────────┘ │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Target Architecture (Nova Sonic 2)

```
┌─────────────────────────────────────────────────────────────┐
│                    LiveKit Agent Worker                      │
│                                                              │
│  ┌────────────┐    ┌──────────────────────────────────┐   │
│  │  Prewarm   │───▶│  MCP Client Manager              │   │
│  │  Function  │    │  - Load system prompt            │   │
│  └────────────┘    │  - Initialize MCP connections    │   │
│                    └──────────────────────────────────┘   │
│                                                              │
│  ┌────────────────────────────────────────────────────┐   │
│  │              Entrypoint Function                    │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐ │   │
│  │  │  Agent with on_enter() hook                   │ │   │
│  │  │  - Implements greeting via generate_reply()  │ │   │
│  │  └──────────────────────────────────────────────┘ │   │
│  │                                                      │   │
│  │  ┌──────────────────────────────────────────────┐ │   │
│  │  │  AgentSession                                 │ │   │
│  │  │  - llm: RealtimeModel.with_nova_sonic_2()    │ │   │
│  │  │    * voice="tiffany" (polyglot)              │ │   │
│  │  │    * turn_detection=ENDPOINTING_SENSITIVITY   │ │   │
│  │  │    * tool_choice="auto"                       │ │   │
│  │  │  - mcp_servers: [HotelPmsMCPServer]          │ │   │
│  │  └──────────────────────────────────────────────┘ │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Changes

1. **Model Initialization**: Switch from `RealtimeModel()` to
   `RealtimeModel.with_nova_sonic_2()`
2. **Greeting Pattern**: Move from `session.say()` to `Agent.on_enter()` with
   `generate_reply()`
3. **TTS Removal**: Remove unused `aws.TTS` fallback (Nova Sonic 2 handles all
   TTS)
4. **Configuration**: Add `ENDPOINTING_SENSITIVITY` environment variable support
5. **Dependencies**: Use official PyPI release (livekit-agents >= 1.3.9)

## Components and Interfaces

### 1. Agent Class with on_enter Hook

**Purpose**: Implement the greeting using Nova Sonic 2's native "speak first"
capability

**Implementation**:

```python
class HotelAssistant(Agent):
    """Hotel assistant agent with Spanish greeting."""

    def __init__(self, instructions: str):
        super().__init__(instructions=instructions)

    async def on_enter(self):
        """Called when agent enters the room - greet the user."""
        await self.session.generate_reply(
            instructions=(
                "¡Hola! Soy su asistente virtual de hoteles. "
                "Estoy aquí para ayudarle con cualquier consulta. "
                "¿En qué puedo asistirle hoy?"
            )
        )
```

**Key Points**:

- `on_enter()` is called automatically when the agent joins the room
- `generate_reply(instructions="...")` triggers Nova Sonic 2 to speak first
- No audio workarounds needed - native Nova Sonic 2 capability
- Greeting text matches the current Spanish receptionist persona

### 2. RealtimeModel Configuration

**Purpose**: Configure Nova Sonic 2 with appropriate settings for hotel
assistant use case

**Implementation**:

```python
from livekit.plugins.aws.experimental.realtime import RealtimeModel

# Get configuration from environment
endpointing_sensitivity = os.getenv("ENDPOINTING_SENSITIVITY", "MEDIUM")
model_temperature = float(os.getenv("MODEL_TEMPERATURE", "0.0"))

# Create Nova Sonic 2 model with polyglot voice
llm = RealtimeModel.with_nova_sonic_2(
    voice="tiffany",                           # Polyglot female voice (multi-language)
    temperature=model_temperature,              # Deterministic responses
    turn_detection=endpointing_sensitivity,     # Configurable turn-taking
    tool_choice="auto",                        # Enable MCP tool calling
)
```

**Configuration Parameters**:

- `voice`: String identifier for voice selection ("tiffany" for polyglot female
  voice supporting Spanish, English, French, German, Italian, Portuguese, and
  Hindi)
- `temperature`: 0.0 for deterministic, 1.0 for creative (default: 0.0)
- `turn_detection`: "HIGH", "MEDIUM", or "LOW" (default: "MEDIUM")
- `tool_choice`: "auto" enables automatic tool calling for MCP integration

### 3. Dependency Management (Requirement 7)

**Purpose**: Use official PyPI release with Nova Sonic 2 support

#### Official PyPI Release (1.3.9+)

Nova Sonic 2 support is available in the official PyPI release of LiveKit agents
starting from version 1.3.9. This provides a stable, production-ready
implementation with full Nova Sonic 2 capabilities.

**pyproject.toml Configuration**:

```toml
[project]
name = "virtual-assistant-livekit"
version = "1.0.0"
description = "LiveKit integration for Virtual Assistant with Amazon Nova Sonic"
requires-python = ">=3.13,<4"
readme = "README.md"
dependencies = [
    # Official PyPI release with Nova Sonic 2 support
    "livekit-agents[mcp]>=1.3.9",
    "livekit-plugins-aws[realtime]>=1.3.9",

    # Other dependencies remain unchanged
    "aws_sdk_bedrock_runtime",
    "httpx>=0.25.0",
    "boto3>=1.34.0",
    "virtual-assistant-common",
]
```

**Rationale for PyPI Release**:

- **Stability**: Official releases undergo thorough testing and validation
- **Maintenance**: Easier to track versions and apply security patches
- **Documentation**: Official documentation aligns with release versions
- **CI/CD**: Simpler dependency resolution in automated pipelines
- **Production-Ready**: Vetted for production use by LiveKit team

#### What's Included in 1.3.9+

The official release includes:

- Complete Nova Sonic 2 implementation with `with_nova_sonic_2()` factory method
- Text input support via `generate_reply(instructions="...")`
- 16-voice support including all Spanish voices
- Configurable turn-taking with `turn_detection` parameter
- Credential management improvements (singleton pattern)
- Session recycling for 8-minute AWS limit
- Bug fixes for credential expiry handling

#### Installation Process

**Using uv (recommended)**:

```bash
cd packages/virtual-assistant/virtual-assistant-livekit
uv sync
```

**What happens during installation**:

1. uv downloads packages from PyPI
2. Installs `livekit-agents` version 1.3.9 or higher
3. Installs `livekit-plugins-aws` version 1.3.9 or higher
4. Installs all transitive dependencies
5. Creates a virtual environment with all packages

**Verification**:

```bash
# Verify livekit-agents version
uv run python -c "import livekit.agents; print(livekit.agents.__version__)"
# Expected output: "1.3.9" or higher

# Verify with_nova_sonic_2 factory method exists (Nova Sonic 2 specific)
uv run python -c "from livekit.plugins.aws.experimental.realtime import RealtimeModel; model = RealtimeModel.with_nova_sonic_2(); print(f'Model: {model.model}')"
# Expected output: "Model: amazon.nova-2-sonic-v1:0"

# Verify text input support (Nova Sonic 2 specific feature)
uv run python -c "from livekit.plugins.aws.experimental.realtime import RealtimeModel; print(hasattr(RealtimeModel, 'with_nova_sonic_2'))"
# Expected output: "True"
```

#### Handling Dependency Updates

**Updating to Latest Version**:

```bash
# Update to latest patch version
uv sync --upgrade-package livekit-agents
uv sync --upgrade-package livekit-plugins-aws

# Or update to specific version
# Edit pyproject.toml with version constraint
uv sync
```

#### Docker Build Considerations

**Dockerfile Configuration**:

```dockerfile
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock ./
COPY README.md ./

# Install dependencies from PyPI
RUN uv sync --frozen --no-cache

# Copy application code
COPY virtual_assistant_livekit/ ./virtual_assistant_livekit/

ENV PATH="/app/.venv/bin:$PATH"
CMD ["python", "-m", "virtual_assistant_livekit"]
```

**Build Process**:

```bash
# Build Docker image
docker build -t virtual-assistant-livekit:nova-sonic-2 .

# Verify build includes correct dependencies
docker run --rm virtual-assistant-livekit:nova-sonic-2 \
  python -c "import livekit.agents; print(livekit.agents.__version__)"
```

#### Version Logging

**Implementation**:

```python
import livekit.agents
import livekit.plugins.aws

logger.info(f"LiveKit agents version: {livekit.agents.__version__}")
logger.info(f"LiveKit AWS plugin version: {livekit.plugins.aws.__version__}")
```

This logging helps identify which version is running in production and aids
troubleshooting.

### 4. Environment Configuration

**Purpose**: Support configurable turn-taking and maintain existing
configuration

**New Environment Variables**:

```bash
# Nova Sonic 2 specific
ENDPOINTING_SENSITIVITY=MEDIUM  # HIGH, MEDIUM, or LOW

# Existing variables (unchanged)
MODEL_TEMPERATURE=0.0
LOG_LEVEL=WARN
```

**CDK Infrastructure Updates**:

```python
# In ECS task definition
environment={
    "ENDPOINTING_SENSITIVITY": "MEDIUM",
    "MODEL_TEMPERATURE": "0.0",
    "LOG_LEVEL": "WARN",
    # ... other existing variables
}
```

### 5. Multi-Language Support

**Purpose**: Leverage Nova Sonic 2's polyglot capabilities for automatic
language detection and response

#### Nova Sonic 2 Language Capabilities

Nova Sonic 2 includes built-in language mirroring that automatically detects the
user's language and responds in the same language. This is enabled by default in
the model's system prompt.

**Supported Languages**:

- Spanish (primary for hotel assistant)
- English (US and GB)
- French
- German
- Italian
- Portuguese
- Hindi

**Polyglot Voices** (Nova 2.0 only):

- **Matthew**: Can seamlessly switch between all supported languages
- **Tiffany**: Can seamlessly switch between all supported languages

#### Implementation (Multi-Language with Tiffany)

The upgraded hotel assistant uses Tiffany's polyglot voice for automatic
multi-language support:

```python
# Use Tiffany for automatic language switching
llm = RealtimeModel.with_nova_sonic_2(
    voice="tiffany",  # Polyglot female voice
    turn_detection=endpointing_sensitivity,
    tool_choice="auto",
)

# Multi-language system prompt with language mirroring
instructions = """
You are a friendly and professional hotel receptionist.
You can communicate in multiple languages including Spanish, English, French, German, Italian, Portuguese, and Hindi.

CRITICAL LANGUAGE MIRRORING RULES:
- Always reply in the language the user speaks
- If the user speaks Spanish, reply in Spanish
- If the user speaks English, reply in English
- If the user switches languages, switch with them seamlessly
- Never mix languages unless the user does
- Maintain the same warm, professional tone in all languages

Your primary role is to help guests with:
- Room reservations and availability
- Check-in and check-out procedures
- Hotel services and amenities
- Housekeeping and service requests
- General hotel information

When using tools to help guests, explain what you're doing in their language.
"""
```

**Why Tiffany?**

- **Polyglot capability**: Seamlessly switches between 7 languages
- **Female voice**: Maintains consistency with previous "lupe" voice
- **Natural transitions**: Handles language switches mid-conversation
- **No configuration needed**: Language detection is automatic

#### Language Detection Logging

```python
# Log detected language from user input
@session.on("user_transcription")
def on_transcription(event):
    text = event.text
    # Simple language detection (can be enhanced)
    if any(word in text.lower() for word in ["hola", "gracias", "por favor"]):
        logger.info("Detected Spanish input")
    elif any(word in text.lower() for word in ["hello", "thank you", "please"]):
        logger.info("Detected English input")
```

#### Configuration

**Environment Variables**:

```bash
# Current (Spanish-only)
VOICE_ID=lupe
LANGUAGE=es-US

# Future (Multi-language)
VOICE_ID=matthew  # or tiffany
LANGUAGE=auto     # Auto-detect
```

**CDK Configuration**:

```python
environment={
    "VOICE_ID": os.getenv("VOICE_ID", "lupe"),
    "LANGUAGE": os.getenv("LANGUAGE", "es-US"),
    # ... other variables
}
```

#### Benefits of Multi-Language Support

1. **Broader Guest Coverage**: Serve international guests in their native
   language
2. **Improved User Experience**: Guests feel more comfortable in their own
   language
3. **Competitive Advantage**: Few hotel assistants offer true multi-language
   support
4. **No Additional Cost**: Nova Sonic 2 includes multi-language at no extra
   charge
5. **Seamless Switching**: Polyglot voices handle language transitions naturally

#### Testing Multi-Language

**Test Scenarios**:

1. **Spanish Guest**: "Hola, necesito hacer una reserva" → Response in Spanish
2. **English Guest**: "Hello, I need to make a reservation" → Response in
   English
3. **Language Switch**: Start in Spanish, switch to English mid-conversation
4. **Mixed Language**: "Hola, do you have rooms available?" → Handle gracefully

**Test Commands**:

```bash
# Test with Spanish
echo "Hola, ¿tienen habitaciones disponibles?" | python -m virtual_assistant_livekit console

# Test with English
echo "Hello, do you have rooms available?" | python -m virtual_assistant_livekit console
```

#### Implementation Notes

**Voice Selection**: Tiffany was chosen over Matthew because:

- Maintains female voice consistency with previous "lupe" voice
- Provides the same polyglot capabilities as Matthew
- Natural, professional tone suitable for hotel reception

**System Prompt**: The multi-language prompt includes:

- Explicit language mirroring rules for Nova Sonic 2
- Clear role definition as hotel receptionist
- Guidance for tool usage explanations
- Emphasis on maintaining professional tone across languages

**No Additional Configuration**: Language detection and switching is handled
automatically by Nova Sonic 2's built-in capabilities. No additional code or
configuration is needed beyond using the Tiffany voice and appropriate system
prompt.

### 6. Logging Enhancements

**Purpose**: Provide visibility into Nova Sonic 2 features and configuration

**Implementation**:

```python
# Log model version and configuration
logger.info(f"Using Nova Sonic 2 with voice={voice}, turn_detection={turn_detection}")
logger.debug(f"Model configuration: temperature={temperature}, tool_choice={tool_choice}")

# Log text input usage
logger.debug(f"Sending text instruction: {instructions[:50]}...")

# Log session lifecycle
logger.info("Agent session started with Nova Sonic 2")
logger.debug(f"Session capabilities: text_input={session.supports_text_input}")
```

## Data Models

### Agent Configuration

```python
@dataclass
class AgentConfig:
    """Configuration for Nova Sonic 2 agent."""

    voice: str = "lupe"                    # Voice identifier
    temperature: float = 0.0                # Sampling temperature
    turn_detection: str = "MEDIUM"          # Turn-taking sensitivity
    tool_choice: str = "auto"              # Tool calling strategy
    model_temperature: float = 0.0          # Model temperature (legacy)
    log_level: str = "WARN"                # Logging level

    @classmethod
    def from_environment(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            voice=os.getenv("VOICE_ID", "lupe"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.0")),
            turn_detection=os.getenv("ENDPOINTING_SENSITIVITY", "MEDIUM"),
            tool_choice=os.getenv("TOOL_CHOICE", "auto"),
            log_level=os.getenv("LOG_LEVEL", "WARN"),
        )
```

### Session State

No changes to session state management - LiveKit agents framework handles this
internally.

## Correctness Properties

_A property is a characteristic or behavior that should hold true across all
valid executions of a system—essentially, a formal statement about what the
system should do. Properties serve as the bridge between human-readable
specifications and machine-verifiable correctness guarantees._

### Property 1: Nova Sonic 2 Model Selection

_For any_ agent initialization, when using the `with_nova_sonic_2()` factory
method, the resulting model SHALL use `amazon.nova-2-sonic-v1:0` and support
mixed modalities (audio + text input).

**Validates: Requirements 1.1, 1.2**

### Property 2: Native Greeting Capability

_For any_ agent session, when the agent enters the room, it SHALL greet the user
using `generate_reply(instructions="...")` without requiring audio input
workarounds.

**Validates: Requirements 2.1, 2.2, 6.1, 6.2, 6.3**

### Property 3: Turn-Taking Configuration

_For any_ valid turn-taking sensitivity value ("HIGH", "MEDIUM", "LOW"), the
agent SHALL configure Nova Sonic 2 with that sensitivity and respond to user
pauses accordingly.

**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

### Property 4: Text Input Support

_For any_ text instruction sent via `generate_reply(instructions="...")`, Nova
Sonic 2 SHALL process the instruction and generate an appropriate audio
response.

**Validates: Requirements 5.1, 5.2, 5.3**

### Property 5: Voice Configuration Consistency

_For any_ agent session, when configured with voice="tiffany", all agent
responses SHALL use the Tiffany polyglot voice consistently throughout the
conversation and automatically respond in the user's detected language.

**Validates: Requirements 3.1, 3.5, 11.1, 11.2, 11.3**

### Property 6: MCP Integration Preservation

_For any_ MCP tool call, the Nova Sonic 2 agent SHALL execute the tool and
incorporate results into Spanish responses identically to the Nova Sonic 1
implementation.

**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5**

### Property 7: Dependency Version Verification

_For any_ agent deployment, the system SHALL verify that livekit-agents and
livekit-plugins-aws are at version 1.3.9 or higher and log the versions at
startup.

**Validates: Requirements 7.4**

### Property 8: Configuration Validation

_For any_ invalid turn-taking sensitivity value, the agent SHALL log a warning
and default to "MEDIUM" without failing to start.

**Validates: Requirements 4.5**

### Property 9: Logging Completeness

_For any_ Nova Sonic 2 specific feature usage (text input, turn-taking, voice
selection), the system SHALL log the feature usage at the appropriate level
(INFO for configuration, DEBUG for operations).

**Validates: Requirements 9.1, 9.2, 9.3, 9.4, 9.5**

### Property 10: Multi-Language Persona Consistency

_For any_ agent response, the content SHALL maintain the hotel receptionist
persona with friendly, professional tone in the user's detected language as
defined in the system prompt.

**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

## Error Handling

### 1. Model Initialization Errors

**Scenario**: Nova Sonic 2 model not available in region

**Handling**:

```python
try:
    llm = RealtimeModel.with_nova_sonic_2(voice="lupe", ...)
except Exception as e:
    logger.error(f"Failed to initialize Nova Sonic 2: {e}")
    logger.error("Ensure amazon.nova-2-sonic-v1:0 is available in your AWS region")
    raise
```

### 2. Invalid Configuration

**Scenario**: Invalid turn-taking sensitivity value

**Handling**:

```python
valid_sensitivities = ["HIGH", "MEDIUM", "LOW"]
sensitivity = os.getenv("ENDPOINTING_SENSITIVITY", "MEDIUM").upper()

if sensitivity not in valid_sensitivities:
    logger.warning(
        f"Invalid ENDPOINTING_SENSITIVITY '{sensitivity}', "
        f"using default 'MEDIUM'. Valid values: {valid_sensitivities}"
    )
    sensitivity = "MEDIUM"
```

### 3. Text Input Not Supported

**Scenario**: Attempting to use text input with Nova Sonic 1

**Handling**:

```python
# This is handled automatically by LiveKit agents framework
# Nova Sonic 1 will log a warning and skip the operation
# No code changes needed - framework handles gracefully
```

### 4. Greeting Failure

**Scenario**: `generate_reply()` fails during greeting

**Handling**:

```python
async def on_enter(self):
    try:
        await self.session.generate_reply(
            instructions="¡Hola! Soy su asistente virtual de hoteles..."
        )
    except Exception as e:
        logger.error(f"Failed to deliver greeting: {e}")
        # Session continues - user can still initiate conversation
```

### 5. Dependency Version Mismatch

**Scenario**: Incorrect LiveKit agents version installed

**Handling**:

```python
import livekit.agents

# Log version at startup
logger.info(f"LiveKit agents version: {livekit.agents.__version__}")

# Framework will raise appropriate errors if features not available
# No explicit version checking needed - rely on import errors
```

## Testing Strategy

### Unit Tests

**Focus**: Core functionality and configuration

**Test Cases**:

1. **test_agent_config_from_environment**: Verify configuration loading from
   environment variables
2. **test_model_initialization**: Verify `with_nova_sonic_2()` creates correct
   model
3. **test_invalid_sensitivity_defaults_to_medium**: Verify invalid sensitivity
   handling
4. **test_voice_configuration**: Verify voice="lupe" is properly configured
5. **test_greeting_text_matches_persona**: Verify greeting maintains Spanish
   persona

**Example**:

```python
def test_agent_config_from_environment(monkeypatch):
    monkeypatch.setenv("ENDPOINTING_SENSITIVITY", "HIGH")
    monkeypatch.setenv("MODEL_TEMPERATURE", "0.5")

    config = AgentConfig.from_environment()

    assert config.turn_detection == "HIGH"
    assert config.temperature == 0.5
```

### Integration Tests

**Focus**: End-to-end agent behavior with Nova Sonic 2

**Test Cases**:

1. **test_agent_greets_on_enter**: Verify agent speaks first using
   `generate_reply()`
2. **test_mcp_tool_calling_works**: Verify MCP tools work with Nova Sonic 2
3. **test_turn_taking_sensitivity**: Verify different sensitivity settings
   affect behavior
4. **test_spanish_responses**: Verify all responses maintain Spanish language
5. **test_session_lifecycle**: Verify session starts, runs, and closes properly

**Example**:

```python
@pytest.mark.integration
async def test_agent_greets_on_enter(mock_livekit_room):
    agent = HotelAssistant(instructions="Test instructions")
    session = AgentSession(llm=RealtimeModel.with_nova_sonic_2(voice="lupe"))

    await session.start(room=mock_livekit_room, agent=agent)

    # Verify generate_reply was called with greeting
    assert session.generate_reply.called
    assert "¡Hola!" in session.generate_reply.call_args[1]["instructions"]
```

### Manual Testing

**Focus**: Voice quality and conversation flow

**Test Scenarios**:

1. **Greeting Quality**: Connect to agent and verify greeting sounds natural
2. **Turn-Taking**: Test with HIGH/MEDIUM/LOW sensitivity settings
3. **MCP Tools**: Request hotel information and verify tool execution
4. **Interruption**: Interrupt agent mid-speech and verify graceful handling
5. **Multi-Turn**: Have extended conversation and verify context maintenance

**Test Environment**:

```bash
# Local testing with console mode
python -m virtual_assistant_livekit console

# Test with different sensitivity settings
ENDPOINTING_SENSITIVITY=HIGH python -m virtual_assistant_livekit console
ENDPOINTING_SENSITIVITY=LOW python -m virtual_assistant_livekit console
```

## Deployment Considerations

### 1. Dependency Installation

**uv Installation**:

```bash
cd packages/virtual-assistant/virtual-assistant-livekit
uv sync
```

**Verification**:

```bash
# Verify version is 1.3.9 or higher
uv run python -c "import livekit.agents; print(livekit.agents.__version__)"

# Verify with_nova_sonic_2 factory method exists (Nova Sonic 2 specific)
uv run python -c "from livekit.plugins.aws.experimental.realtime import RealtimeModel; model = RealtimeModel.with_nova_sonic_2(); print(f'Model: {model.model}')"
# Expected: "Model: amazon.nova-2-sonic-v1:0"

# Verify text input support (Nova Sonic 2 specific feature)
uv run python -c "from livekit.plugins.aws.experimental.realtime import RealtimeModel; print(hasattr(RealtimeModel, 'with_nova_sonic_2'))"
# Expected: "True"
```

### 2. Docker Image Updates

**Build Configuration**:

The Docker image uses the standard uv workflow to install dependencies from
PyPI. The official release (1.3.9+) ensures consistent, production-ready builds
across all environments.

### 3. CDK Infrastructure Updates

**ECS Task Definition**:

```python
# Add new environment variable
environment={
    "ENDPOINTING_SENSITIVITY": "MEDIUM",
    # ... existing variables
}

# Update Bedrock permissions to include Nova Sonic 2
bedrock_policy.add_statements(
    iam.PolicyStatement(
        actions=["bedrock:InvokeModel", "bedrock:InvokeModelWithResponseStream"],
        resources=[
            f"arn:aws:bedrock:{region}::foundation-model/amazon.nova-sonic-v1:0",
            f"arn:aws:bedrock:{region}::foundation-model/amazon.nova-2-sonic-v1:0",
        ],
    )
)
```

### 4. Rollback Strategy

**If Issues Occur**:

1. Revert to Nova Sonic 1 by changing one line:
   ```python
   llm = RealtimeModel.with_nova_sonic_1(voice="lupe", ...)
   ```
2. Remove `ENDPOINTING_SENSITIVITY` environment variable
3. Redeploy with previous Docker image

**Gradual Rollout**:

- Deploy to development environment first
- Test thoroughly with real conversations
- Deploy to staging for user acceptance testing
- Deploy to production with monitoring

### 5. Monitoring

**Key Metrics**:

- Agent session start success rate
- Greeting delivery success rate
- Average time to first response
- MCP tool call success rate
- Session duration and completion rate

**CloudWatch Logs**:

```python
# Log filters to create
- "Nova Sonic 2" - Track Nova Sonic 2 usage
- "generate_reply" - Track text input usage
- "turn_detection" - Track turn-taking configuration
- "ERROR" - Track any errors
```

## Migration Path

### Phase 1: Development Setup (Day 1)

1. Update `pyproject.toml` with official PyPI dependencies (>=1.3.9)
2. Run `uv sync` to install dependencies from PyPI
3. Verify Nova Sonic 2 support is available with verification commands
4. Create feature branch for changes

**Key Decision**: Using official PyPI release (1.3.9+) instead of Git-based
dependencies provides better stability, easier maintenance, and production-ready
code.

### Phase 2: Code Changes (Day 1-2)

1. Create `HotelAssistant` class with `on_enter()` hook
2. Update `entrypoint()` to use `with_nova_sonic_2()`
3. Remove `aws.TTS` fallback (no longer needed)
4. Add `ENDPOINTING_SENSITIVITY` configuration
5. Update logging to include Nova Sonic 2 details
6. Remove `session.say()` greeting workaround

### Phase 3: Testing (Day 2-3)

1. Run unit tests and verify all pass
2. Run integration tests with mock LiveKit room
3. Manual testing with console mode
4. Test different turn-taking sensitivities
5. Verify MCP tools work correctly
6. Test greeting quality and naturalness

### Phase 4: Infrastructure Updates (Day 3)

1. Update CDK stack with new environment variable
2. Update Bedrock permissions for Nova Sonic 2
3. Build and test Docker image locally
4. Deploy to development environment
5. Verify deployment and run smoke tests

### Phase 5: Validation (Day 4)

1. Extended testing in development environment
2. User acceptance testing with Spanish speakers
3. Performance testing and monitoring
4. Documentation updates
5. Prepare rollback plan

### Phase 6: Production Deployment (Day 5)

1. Deploy to staging environment
2. Final validation and sign-off
3. Deploy to production during low-traffic window
4. Monitor metrics and logs closely
5. Verify greeting and conversation quality

## Performance Considerations

### 1. Session Initialization

**Nova Sonic 2 Benefits**:

- Faster greeting delivery (no audio workaround needed)
- Native text input reduces latency for programmatic control
- Improved credential caching reduces initialization overhead

**Expected Improvements**:

- Greeting latency: ~500ms faster (no audio file loading)
- Session start: ~200ms faster (improved credential management)

### 2. Turn-Taking Optimization

**Sensitivity Tuning**:

- **HIGH**: ~300ms pause detection (fast but may interrupt)
- **MEDIUM**: ~500ms pause detection (balanced, recommended)
- **LOW**: ~800ms pause detection (patient, fewer interruptions)

**Recommendation**: Start with MEDIUM, adjust based on user feedback

### 3. Memory and CPU

**No Significant Changes**:

- Nova Sonic 2 uses same underlying infrastructure
- Text input adds minimal overhead
- Session recycling improves long-term stability

## Security Considerations

### 1. Credential Management

**No Changes Required**:

- Existing ECS task role provides Bedrock access
- Nova Sonic 2 uses same authentication as Nova Sonic 1
- Improved credential caching reduces API calls

### 2. Model Permissions

**CDK Updates**:

```python
# Grant access to both models during transition
resources=[
    "arn:aws:bedrock:*::foundation-model/amazon.nova-sonic-v1:0",
    "arn:aws:bedrock:*::foundation-model/amazon.nova-2-sonic-v1:0",
]
```

### 3. Text Input Security

**Considerations**:

- Text input via `generate_reply()` is internal only
- No user-provided text input in current design
- System prompts are controlled by application code

## LiveKit Agents Source Code Reference (Requirement 14)

### Purpose

Having the LiveKit agents source code available during development provides
critical benefits:

- **Understanding implementation details**: See exactly how Nova Sonic 2
  features work
- **Debugging issues**: Trace through code to understand unexpected behavior
- **API discovery**: Find undocumented features and parameters
- **Best practices**: Learn from official examples and patterns
- **Troubleshooting**: Identify root causes of errors quickly

### Approach: Using repomix for Code Reference

Rather than cloning the entire LiveKit agents repository as a Git submodule
(which would add unnecessary files to the workspace), we'll use the existing
`repomix-output-livekit-agents.xml` file that contains the relevant LiveKit
agents code.

#### What's in repomix-output-livekit-agents.xml

The file contains a curated subset of the LiveKit agents repository focused on
AWS/Nova Sonic integration:

```
livekit-plugins/livekit-plugins-aws/
├── livekit/plugins/aws/
│   ├── experimental/realtime/
│   │   ├── __init__.py              # Exports RealtimeModel, RealtimeSession
│   │   ├── events.py                # Nova Sonic event builders
│   │   ├── pretty_printer.py        # Debug logging utilities
│   │   ├── realtime_model.py        # Core implementation (2800+ lines)
│   │   ├── turn_tracker.py          # Turn-taking state machine
│   │   └── types.py                 # Type definitions and constants
│   ├── __init__.py                  # Main AWS plugin exports
│   ├── llm.py                       # Nova Lite LLM implementation
│   ├── stt.py                       # AWS Transcribe STT
│   ├── tts.py                       # Amazon Polly TTS
│   └── utils.py                     # Utility functions
├── pyproject.toml                   # Package configuration
└── README.md                        # Complete documentation
```

#### Key Files for Nova Sonic 2 Development

**1. realtime_model.py** (Most Important)

Contains the complete implementation of:

- `RealtimeModel` class with factory methods
- `RealtimeSession` class with bidirectional streaming
- `with_nova_sonic_1()` and `with_nova_sonic_2()` factory methods
- `generate_reply()` implementation for text input
- Credential management with `Boto3CredentialsResolver`
- Session recycling logic
- Event handling for all Nova Sonic events
- Tool integration patterns

**Key sections to reference**:

```python
# Line ~400: RealtimeModel class definition
class RealtimeModel(llm.RealtimeModel):
    def __init__(self, model, modalities, voice, temperature, ...):
        # Configuration and initialization

# Line ~500: Factory methods
    @classmethod
    def with_nova_sonic_2(cls, voice, temperature, ...):
        return cls(
            model="amazon.nova-2-sonic-v1:0",
            modalities="mixed",  # Enables text input
            ...
        )

# Line ~1200: generate_reply implementation
    def generate_reply(self, *, instructions=NOT_GIVEN):
        # Text input handling for Nova Sonic 2

# Line ~1500: Session initialization
    async def initialize_streams(self, is_restart=False):
        # Bedrock client setup and stream initialization
```

**2. events.py**

Contains event builders for Nova Sonic protocol:

- `SonicEventBuilder` class for creating protocol events
- Event types: sessionStart, promptStart, contentStart, etc.
- Tool configuration builders
- Audio/text input event creation

**Key sections**:

```python
# Line ~200: Event builder class
class SonicEventBuilder:
    def create_prompt_start_block(self, voice_id, sample_rate, system_content, ...):
        # Creates initialization event sequence

# Line ~400: Text input events
    def create_text_content_start_event_interactive(self, content_name, role):
        # Creates interactive text input (Nova 2.0 only)
```

**3. types.py**

Contains type definitions and constants:

- `SONIC1_VOICES` and `SONIC2_VOICES` - Available voice IDs
- `TURN_DETECTION` - Turn-taking sensitivity values
- `MODALITIES` - Audio vs mixed mode
- `REALTIME_MODELS` - Supported model IDs

**4. README.md** Lines 4128 - 4486

Complete documentation including:

- Nova Sonic 2 capabilities and differences from 1.0
- Voice selection guide with all 16 voices
- Text prompting examples with `generate_reply()`
- Turn-taking sensitivity guide
- Complete code examples
- Troubleshooting guide

### How to Use the Reference Code

#### During Development

**1. Understanding a Feature**:

```bash
# Search for specific functionality
grep -n "generate_reply" repomix-output-livekit-agents.xml
grep -n "with_nova_sonic_2" repomix-output-livekit-agents.xml
grep -n "turn_detection" repomix-output-livekit-agents.xml
```

**2. Debugging an Issue**:

```bash
# Find error handling patterns
grep -n "try:" repomix-output-livekit-agents.xml | head -20
grep -n "except" repomix-output-livekit-agents.xml | head -20

# Find logging patterns
grep -n "logger\." repomix-output-livekit-agents.xml | head -20
```

**3. API Discovery**:

```bash
# Find all public methods
grep -n "def " repomix-output-livekit-agents.xml | grep -v "    def _"

# Find configuration options
grep -n "def __init__" repomix-output-livekit-agents.xml
```

#### Reading the Code

**Open in IDE**:

The `repomix-output-livekit-agents.xml` file is already in the workspace and can
be opened in any text editor or IDE. It's formatted as XML with clear file
boundaries:

```xml
<file path="livekit-plugins/livekit-plugins-aws/livekit/plugins/aws/experimental/realtime/realtime_model.py">
# Python code here
</file>
```

**Navigate by File Path**:

Use your IDE's search functionality to jump to specific files:

- Search for: `<file path="...realtime_model.py">`
- Search for: `<file path="...events.py">`
- Search for: `<file path="...README.md">`

**Extract Individual Files** (if needed):

```bash
# Extract a specific file for easier reading
# This is optional - the XML file is already readable
python -c "
import xml.etree.ElementTree as ET
tree = ET.parse('repomix-output-livekit-agents.xml')
for file_elem in tree.findall('.//file'):
    if 'realtime_model.py' in file_elem.get('path'):
        print(file_elem.text)
" > realtime_model_reference.py
```

### Reference Patterns for Common Tasks

#### 1. Implementing Agent Greeting

**Reference**: README.md, line ~4300

```python
# From LiveKit agents README
class Assistant(Agent):
    async def on_enter(self):
        await self.session.generate_reply(
            instructions="Greet the user and offer assistance"
        )
```

**Our Implementation**:

```python
class HotelAssistant(Agent):
    async def on_enter(self):
        await self.session.generate_reply(
            instructions=(
                "¡Hola! Soy su asistente virtual de hoteles. "
                "Estoy aquí para ayudarle con cualquier consulta. "
                "¿En qué puedo asistirle hoy?"
            )
        )
```

#### 2. Configuring Turn-Taking

**Reference**: README.md, line ~4250

```python
# From LiveKit agents README
model = aws.realtime.RealtimeModel.with_nova_sonic_2(
    turn_detection="MEDIUM"  # HIGH, MEDIUM (default), LOW
)
```

**Our Implementation**:

```python
endpointing_sensitivity = os.getenv("ENDPOINTING_SENSITIVITY", "MEDIUM")
llm = RealtimeModel.with_nova_sonic_2(
    voice="lupe",
    turn_detection=endpointing_sensitivity,
    tool_choice="auto",
)
```

#### 3. Voice Selection

**Reference**: README.md, line ~4200

```python
# From LiveKit agents README - Nova 2.0 voices
model = aws.realtime.RealtimeModel.with_nova_sonic_2(
    voice="lupe"  # Spanish, feminine
)
```

**Our Implementation**: Same pattern, already using "lupe"

#### 4. Understanding Session Lifecycle

**Reference**: realtime_model.py, line ~1500-1700

Key insights from the code:

- Sessions auto-recycle before 8-minute AWS limit
- Credential expiry is monitored and handled
- Tool results are queued and sent asynchronously
- Barge-in is detected automatically by Nova Sonic

### Cleanup After Development

Once the Nova Sonic 2 upgrade is complete and stable:

**Option 1: Keep for Future Reference**

- Keep `repomix-output-livekit-agents.xml` in the repository
- Add to `.gitignore` if it's too large
- Document its purpose in README

**Option 2: Remove and Document**

- Delete `repomix-output-livekit-agents.xml`
- Add link to LiveKit agents repository in README
- Document which commit was used for reference

**Recommended**: Keep the file with a note in README:

```markdown
## Development References

### LiveKit Agents Source Code

The `repomix-output-livekit-agents.xml` file contains a snapshot of the LiveKit
agents source code (commit 9fb59dd2d676069fb8e24d641dd374e5793f42b6) used during
the Nova Sonic 2 upgrade. This file is kept for reference and troubleshooting.

For the latest code, see: https://github.com/livekit/agents
```

### Alternative: Git Submodule (Not Recommended)

If you prefer to have the full LiveKit agents repository available:

```bash
# Add as submodule (not recommended - adds many unnecessary files)
git submodule add https://github.com/livekit/agents.git .livekit-agents-reference
cd .livekit-agents-reference
git checkout 9fb59dd2d676069fb8e24d641dd374e5793f42b6

# Add to .gitignore to prevent committing
echo ".livekit-agents-reference/" >> .gitignore
```

**Why not recommended**:

- Adds 100+ MB of files to workspace
- Includes many unrelated packages (OpenAI, Anthropic, etc.)
- Slower workspace operations
- The repomix file contains everything needed

## Documentation Updates

### 1. README Updates

**Add Section**: "Nova Sonic 2 Upgrade"

- Benefits of Nova Sonic 2
- New configuration options
- Migration guide from Nova Sonic 1

### 2. Environment Variables

**Update Documentation**:

```markdown
## Environment Variables

### Nova Sonic 2 Configuration

- `ENDPOINTING_SENSITIVITY`: Turn-taking sensitivity (HIGH, MEDIUM, LOW)
  - Default: MEDIUM
  - HIGH: Fast responses, may interrupt slower speakers
  - MEDIUM: Balanced, works for most use cases
  - LOW: Patient, better for thoughtful speakers

### Existing Variables

- `MODEL_TEMPERATURE`: Sampling temperature (0.0-1.0, default: 0.0)
- `LOG_LEVEL`: Logging level (DEBUG, INFO, WARN, ERROR, default: WARN)
```

### 3. Troubleshooting Guide

**Add Common Issues**:

- "Nova Sonic 2 not available in region" → Check AWS region and model access
- "Text input not working" → Verify using `with_nova_sonic_2()` not
  `with_nova_sonic_1()`
- "Greeting not playing" → Check `on_enter()` implementation and logs

## Conclusion

The upgrade to Nova Sonic 2 provides significant improvements in agent
capabilities while maintaining backward compatibility with existing MCP
integration and Spanish hotel receptionist persona. The migration is
straightforward, requiring minimal code changes and no changes to the overall
architecture. The use of the official PyPI release (version 1.3.9) ensures
stability and production-readiness, and the design includes a clear rollback
strategy if issues arise.

Key success factors:

- Native "speak first" capability simplifies greeting implementation
- Configurable turn-taking improves conversation quality
- Text input enables future programmatic control features
- Improved credential management reduces initialization overhead
- Clear migration path with comprehensive testing strategy
