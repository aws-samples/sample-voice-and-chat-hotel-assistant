# Design Document: LiveKit Nova Sonic 2 Upgrade

## Overview

This design upgrades the LiveKit voice agent from Amazon Nova Sonic 1 to Nova
Sonic 2 (`amazon.nova-2-sonic-v1:0`). The upgrade leverages LiveKit agents
1.3.9+ which includes native support for Nova Sonic 2's enhanced capabilities.

### Key Benefits

- **Native "speak first"**: Eliminates audio input workarounds for greetings
- **Text message input**: Enables programmatic control via
  `generate_reply(instructions="...")`
- **Expanded voice support**: 16 voices across 8 languages (vs 11 voices in
  Nova 1)
- **Polyglot voices**: Tiffany and Matthew can seamlessly switch between
  languages
- **Configurable turn-taking**: HIGH/MEDIUM/LOW sensitivity for different use
  cases
- **Improved credential management**: Singleton pattern prevents credential
  loading spam
- **Session recycling**: Automatic restart before 8-minute AWS limit

## Architecture

### Current vs Target Architecture

**Current (Nova Sonic 1)**:

```
Entrypoint → AgentSession(
  llm: RealtimeModel(voice="lupe"),
  tts: aws.TTS (fallback, unused)
) → session.say(greeting_audio()) [workaround]
```

**Target (Nova Sonic 2)**:

```
Entrypoint → VirtualAssistant(Agent) → on_enter() → generate_reply(instructions="...")
           → AgentSession(
               llm: RealtimeModel.with_nova_sonic_2(
                 voice="tiffany",
                 turn_detection=ENDPOINTING_SENSITIVITY
               )
             )
```

### Key Architectural Changes

1. **Model Initialization**: `RealtimeModel()` →
   `RealtimeModel.with_nova_sonic_2()`
2. **Greeting Pattern**: `session.say()` → `Agent.on_enter()` with
   `generate_reply()`
3. **TTS Removal**: Remove unused `aws.TTS` fallback
4. **Configuration**: Add `ENDPOINTING_SENSITIVITY` environment variable
5. **Dependencies**: Use official PyPI release (livekit-agents >= 1.3.9)

## Components and Interfaces

### 1. VirtualAssistant Agent Class

**Purpose**: Implement greeting using Nova Sonic 2's native "speak first"
capability

```python
class VirtualAssistant(Agent):
    """Industry-agnostic virtual assistant agent with configurable greeting."""

    def __init__(self, instructions: str, greeting: str | None = None):
        super().__init__(instructions=instructions)
        self._greeting = greeting

    async def on_enter(self):
        """Called when agent enters the room - greet the user."""
        if self._greeting:
            await self.session.generate_reply(
                instructions=self._greeting
            )
```

**Design Rationale**:

- `on_enter()` is called automatically when agent joins room
- `generate_reply(instructions="...")` triggers Nova Sonic 2 to speak first
- No audio workarounds needed - native Nova Sonic 2 capability
- Greeting text is configurable via constructor parameter
- Industry-specific customization comes from system instructions and MCP tools
- Agent remains generic and reusable across different domains

### 2. RealtimeModel Configuration

**Purpose**: Configure Nova Sonic 2 with appropriate settings for virtual
assistant

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

- `voice`: "tiffany" for polyglot female voice (Spanish, English, French,
  German, Italian, Portuguese, Hindi)
- `temperature`: 0.0 for deterministic, 1.0 for creative (default: 0.0)
- `turn_detection`: "HIGH", "MEDIUM", or "LOW" (default: "MEDIUM")
- `tool_choice`: "auto" enables automatic tool calling for MCP integration

**Design Rationale**:

- Tiffany voice maintains female voice consistency with previous "lupe" voice
- Polyglot capability enables automatic language detection and response
- Configurable turn-taking allows tuning based on user feedback
- Temperature 0.0 ensures consistent, professional responses

### 3. Dependency Management

**Purpose**: Use official PyPI release with Nova Sonic 2 support

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

**Design Rationale**:

- **Stability**: Official releases undergo thorough testing
- **Maintenance**: Easier to track versions and apply security patches
- **Documentation**: Official docs align with release versions
- **CI/CD**: Simpler dependency resolution in automated pipelines
- **Production-Ready**: Vetted for production use by LiveKit team

**Installation & Verification**:

```bash
# Install dependencies
cd packages/virtual-assistant/virtual-assistant-livekit
uv sync

# Verify version is 1.3.9 or higher
uv run python -c "import livekit.agents; print(livekit.agents.__version__)"

# Verify with_nova_sonic_2 factory method exists (Nova Sonic 2 specific)
uv run python -c "from livekit.plugins.aws.experimental.realtime import RealtimeModel; model = RealtimeModel.with_nova_sonic_2(); print(f'Model: {model.model}')"
# Expected: "Model: amazon.nova-2-sonic-v1:0"
```

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

**Turn-Taking Sensitivity Guide**:

- **HIGH**: ~300ms pause detection (fast but may interrupt)
- **MEDIUM**: ~500ms pause detection (balanced, recommended)
- **LOW**: ~800ms pause detection (patient, fewer interruptions)

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
language detection

#### Language Capabilities

Nova Sonic 2 includes built-in language mirroring that automatically detects the
user's language and responds in the same language.

**Supported Languages**:

- Spanish, English (US and GB)
- French, German, Italian, Portuguese, Hindi
- Language selection configured via system instructions

**Polyglot Voice**: Tiffany can seamlessly switch between all supported
languages

#### Implementation

```python
# Use Tiffany for automatic language switching
llm = RealtimeModel.with_nova_sonic_2(
    voice="tiffany",  # Polyglot female voice
    turn_detection=endpointing_sensitivity,
    tool_choice="auto",
)

# Multi-language system prompt with language mirroring
# Note: Industry-specific persona and capabilities should be provided via environment configuration
instructions = """
You are a friendly and professional virtual assistant.
You can communicate in multiple languages including Spanish, English, French, German, Italian, Portuguese, and Hindi.

CRITICAL LANGUAGE MIRRORING RULES:
- Always reply in the language the user speaks
- If the user speaks Spanish, reply in Spanish
- If the user speaks English, reply in English
- If the user switches languages, switch with them seamlessly
- Never mix languages unless the user does
- Maintain the same warm, professional tone in all languages

When using tools to help users, explain what you're doing in their language.
"""
```

**Design Rationale**:

- **Tiffany voice**: Maintains female voice consistency, provides polyglot
  capability
- **Automatic detection**: No configuration needed, Nova Sonic 2 handles it
- **Natural transitions**: Handles language switches mid-conversation
- **System prompt**: Explicit language mirroring rules ensure proper behavior

### 6. Logging Enhancements

**Purpose**: Provide visibility into Nova Sonic 2 features and configuration

```python
import livekit.agents
import livekit.plugins.aws

# Log model version and configuration at startup
logger.info(f"LiveKit agents version: {livekit.agents.__version__}")
logger.info(f"LiveKit AWS plugin version: {livekit.plugins.aws.__version__}")
logger.info(f"Using Nova Sonic 2 with voice={voice}, turn_detection={turn_detection}")
logger.debug(f"Model configuration: temperature={temperature}, tool_choice={tool_choice}")

# Log text input usage
logger.debug(f"Sending text instruction: {instructions[:50]}...")

# Log session lifecycle
logger.info("Agent session started with Nova Sonic 2")
```

## Data Models

### Agent Configuration

```python
@dataclass
class AgentConfig:
    """Configuration for Nova Sonic 2 agent."""

    voice: str = "tiffany"                 # Voice identifier
    temperature: float = 0.0                # Sampling temperature
    turn_detection: str = "MEDIUM"          # Turn-taking sensitivity
    tool_choice: str = "auto"              # Tool calling strategy
    log_level: str = "WARN"                # Logging level

    @classmethod
    def from_environment(cls) -> "AgentConfig":
        """Load configuration from environment variables."""
        return cls(
            voice=os.getenv("VOICE_ID", "tiffany"),
            temperature=float(os.getenv("MODEL_TEMPERATURE", "0.0")),
            turn_detection=os.getenv("ENDPOINTING_SENSITIVITY", "MEDIUM"),
            tool_choice=os.getenv("TOOL_CHOICE", "auto"),
            log_level=os.getenv("LOG_LEVEL", "WARN"),
        )
```

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
incorporate results into responses identically to the Nova Sonic 1
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

_For any_ agent response, the content SHALL maintain the configured persona with
friendly, professional tone in the user's detected language as defined in the
system prompt.

**Validates: Requirements 11.1, 11.2, 11.3, 11.4, 11.5**

## Error Handling

### 1. Model Initialization Errors

**Scenario**: Nova Sonic 2 model not available in region

```python
try:
    llm = RealtimeModel.with_nova_sonic_2(voice="tiffany", ...)
except Exception as e:
    logger.error(f"Failed to initialize Nova Sonic 2: {e}")
    logger.error("Ensure amazon.nova-2-sonic-v1:0 is available in your AWS region")
    raise
```

### 2. Invalid Configuration

**Scenario**: Invalid turn-taking sensitivity value

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

### 3. Greeting Failure

**Scenario**: `generate_reply()` fails during greeting

```python
async def on_enter(self):
    try:
        await self.session.generate_reply(
            instructions="Hello! I'm your virtual assistant..."
        )
    except Exception as e:
        logger.error(f"Failed to deliver greeting: {e}")
        # Session continues - user can still initiate conversation
```

## Testing Strategy

### Unit Tests

**Focus**: Core functionality and configuration

**Test Cases**:

1. `test_agent_config_from_environment`: Verify configuration loading
2. `test_model_initialization`: Verify `with_nova_sonic_2()` creates correct
   model
3. `test_invalid_sensitivity_defaults_to_medium`: Verify invalid sensitivity
   handling
4. `test_voice_configuration`: Verify voice="tiffany" is properly configured
5. `test_greeting_text_matches_persona`: Verify greeting maintains persona

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

1. `test_agent_greets_on_enter`: Verify agent speaks first using
   `generate_reply()`
2. `test_mcp_tool_calling_works`: Verify MCP tools work with Nova Sonic 2
3. `test_turn_taking_sensitivity`: Verify different sensitivity settings
4. `test_multi_language_responses`: Verify language detection and response
5. `test_session_lifecycle`: Verify session starts, runs, and closes properly

### Manual Testing

**Focus**: Voice quality and conversation flow

**Test Scenarios**:

1. **Greeting Quality**: Connect and verify greeting sounds natural
2. **Turn-Taking**: Test with HIGH/MEDIUM/LOW sensitivity settings
3. **MCP Tools**: Request information and verify tool execution
4. **Language Switching**: Test Spanish → English → Spanish transitions
5. **Multi-Turn**: Extended conversation to verify context maintenance

**Test Commands**:

```bash
# Local testing with console mode
python -m virtual_assistant_livekit console

# Test with different sensitivity settings
ENDPOINTING_SENSITIVITY=HIGH python -m virtual_assistant_livekit console
ENDPOINTING_SENSITIVITY=LOW python -m virtual_assistant_livekit console
```

## Deployment Considerations

### 1. Docker Image

**Dockerfile**:

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

### 2. CDK Infrastructure Updates

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

### 3. Rollback Strategy

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

### 4. Monitoring

**Key Metrics**:

- Agent session start success rate
- Greeting delivery success rate
- Average time to first response
- MCP tool call success rate
- Session duration and completion rate

**CloudWatch Logs Filters**:

- "Nova Sonic 2" - Track Nova Sonic 2 usage
- "generate_reply" - Track text input usage
- "turn_detection" - Track turn-taking configuration
- "ERROR" - Track any errors

## Migration Path

### Phase 1: Development Setup (Day 1)

1. Update `pyproject.toml` with official PyPI dependencies (>=1.3.9)
2. Run `uv sync` to install dependencies from PyPI
3. Verify Nova Sonic 2 support with verification commands
4. Create feature branch for changes

**Key Decision**: Using official PyPI release (1.3.9+) provides better
stability, easier maintenance, and production-ready code.

### Phase 2: Code Changes (Day 1-2)

1. Create `VirtualAssistant` class with `on_enter()` hook
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

### Session Initialization

**Nova Sonic 2 Benefits**:

- Greeting latency: ~500ms faster (no audio file loading)
- Session start: ~200ms faster (improved credential management)

### Turn-Taking Optimization

**Sensitivity Tuning**:

- **HIGH**: ~300ms pause detection (fast but may interrupt)
- **MEDIUM**: ~500ms pause detection (balanced, recommended)
- **LOW**: ~800ms pause detection (patient, fewer interruptions)

**Recommendation**: Start with MEDIUM, adjust based on user feedback

### Memory and CPU

**No Significant Changes**:

- Nova Sonic 2 uses same underlying infrastructure
- Text input adds minimal overhead
- Session recycling improves long-term stability

## Security Considerations

### Credential Management

**No Changes Required**:

- Existing ECS task role provides Bedrock access
- Nova Sonic 2 uses same authentication as Nova Sonic 1
- Improved credential caching reduces API calls

### Model Permissions

**CDK Updates**: Grant access to both models during transition

### Text Input Security

**Considerations**:

- Text input via `generate_reply()` is internal only
- No user-provided text input in current design
- System prompts are controlled by application code

## LiveKit Agents Source Code Reference

### Purpose

The `repomix-output-livekit-agents.xml` file in the workspace root contains the
LiveKit agents source code used during development. This reference is valuable
for:

- Understanding implementation details of Nova Sonic 2 features
- Debugging issues by tracing through actual code
- Discovering undocumented features and parameters
- Learning best practices from official examples

### File Index

The XML file contains the following source files with their line numbers:

| Line | File Path                                 | Description                                          |
| ---- | ----------------------------------------- | ---------------------------------------------------- |
| 74   | `experimental/realtime/__init__.py`       | Module exports for RealtimeModel and RealtimeSession |
| 88   | `experimental/realtime/events.py`         | Nova Sonic event builders (548 lines)                |
| 636  | `experimental/realtime/pretty_printer.py` | Debug logging utilities (52 lines)                   |
| 688  | `experimental/realtime/realtime_model.py` | **Core implementation** (2109 lines)                 |
| 2797 | `experimental/realtime/turn_tracker.py`   | Turn-taking state machine (174 lines)                |
| 2971 | `experimental/realtime/types.py`          | Type definitions and constants (41 lines)            |
| 3012 | `aws/__init__.py`                         | Main AWS plugin exports (73 lines)                   |
| 3085 | `aws/llm.py`                              | Nova Lite LLM implementation (322 lines)             |
| 3407 | `aws/log.py`                              | Logging configuration (10 lines)                     |
| 3417 | `aws/models.py`                           | Data models (52 lines)                               |
| 3469 | `aws/stt.py`                              | AWS Transcribe STT (349 lines)                       |
| 3818 | `aws/tts.py`                              | Amazon Polly TTS (188 lines)                         |
| 4006 | `aws/utils.py`                            | Utility functions (50 lines)                         |
| 4056 | `aws/version.py`                          | Version information (18 lines)                       |
| 4074 | `pyproject.toml`                          | Package configuration (54 lines)                     |
| 4128 | `README.md`                               | **Complete documentation** (358 lines)               |

### Key Files for Nova Sonic 2 Development

**1. realtime_model.py (Line 688)** - Most Important

- `RealtimeModel` class with factory methods
- `with_nova_sonic_1()` and `with_nova_sonic_2()` implementations
- `generate_reply()` for text input
- Credential management with `Boto3CredentialsResolver`
- Session recycling logic
- Event handling for all Nova Sonic events

**2. events.py (Line 88)**

- `SonicEventBuilder` class for creating protocol events
- Event types: sessionStart, promptStart, contentStart, etc.
- Tool configuration builders
- Audio/text input event creation

**3. types.py (Line 2971)**

- `SONIC1_VOICES` and `SONIC2_VOICES` - Available voice IDs
- `TURN_DETECTION` - Turn-taking sensitivity values
- `MODALITIES` - Audio vs mixed mode
- `REALTIME_MODELS` - Supported model IDs

**4. README.md (Line 4128)**

- Nova Sonic 2 capabilities and differences from 1.0
- Voice selection guide with all 16 voices
- Text prompting examples with `generate_reply()`
- Turn-taking sensitivity guide
- Complete code examples

### How to Use the Reference

**Read specific sections directly**:

Use the `readFile` tool with line ranges to examine specific parts of the
reference implementation:

- **realtime_model.py** (lines 688-2797): Core RealtimeModel implementation
- **session.py** (lines 2798-2970): Session management and event handling
- **models.py** (lines 2971-3012): Voice configuration and model definitions
- **README.md** (lines 4128-end): Complete documentation and usage examples

**Search for specific functionality**:

Use the `grepSearch` tool to find specific patterns:

```
# Find generate_reply implementation
grepSearch: query="generate_reply", includePattern="repomix-output-livekit-agents.xml"

# Find voice configuration
grepSearch: query="SONIC2_VOICES", includePattern="repomix-output-livekit-agents.xml"

# Find session event handling
grepSearch: query="session_update", includePattern="repomix-output-livekit-agents.xml"
```

## Documentation Updates

### README Updates

**Add Section**: "Nova Sonic 2 Upgrade"

- Benefits of Nova Sonic 2
- New configuration options (ENDPOINTING_SENSITIVITY)
- Multi-language support with Tiffany voice
- Migration guide from Nova Sonic 1

### Environment Variables Documentation

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

### Troubleshooting Guide

**Common Issues**:

- "Nova Sonic 2 not available in region" → Check AWS region and model access
- "Text input not working" → Verify using `with_nova_sonic_2()` not
  `with_nova_sonic_1()`
- "Greeting not playing" → Check `on_enter()` implementation and logs
- "Wrong language detected" → Review system prompt language mirroring rules

## Conclusion

The upgrade to Nova Sonic 2 provides significant improvements in agent
capabilities while maintaining backward compatibility with existing MCP
integration. The agent remains industry-agnostic, with customization provided
through system instructions and MCP tools. The migration is straightforward,
requiring minimal code changes and no changes to the overall architecture.

**Key Success Factors**:

- Native "speak first" capability simplifies greeting implementation
- Configurable turn-taking improves conversation quality
- Multi-language support with Tiffany polyglot voice
- Text input enables future programmatic control features
- Official PyPI release (1.3.9+) ensures stability and production-readiness
- Clear migration path with comprehensive testing strategy
- Simple rollback strategy if issues arise
