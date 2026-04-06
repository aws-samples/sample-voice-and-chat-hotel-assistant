# Design Document

## Overview

This design outlines the migration from custom memory hooks to the Bedrock
AgentCore Memory SessionManager for Strands Agents. The migration will simplify
the codebase, leverage built-in AgentCore capabilities, and improve session
persistence through proper global agent instantiation with lazy initialization
patterns.

## Architecture

### Current Architecture

The current implementation uses custom memory hooks (`MemoryHookProvider`) that:

- Initialize memory client and hooks in the async task function
- Create new agent instances per invocation
- Manage memory operations manually through custom hook implementations
- Handle greeting functionality through custom logic

### Target Architecture

The new implementation will use AgentCore Memory SessionManager that:

- Leverages built-in Strands Agent memory capabilities
- Uses global agent instantiation with lazy initialization
- Simplifies memory management through SessionManager
- Takes advantage of AgentCore Runtime session persistence

### Key Architectural Changes

1. **Global Agent Pattern**: Move from per-invocation agent creation to global
   agent with lazy initialization
2. **SessionManager Integration**: Replace custom memory hooks with AgentCore
   Memory SessionManager
3. **Simplified Memory Configuration**: Use built-in memory configuration
   instead of custom implementations
4. **Session Persistence**: Leverage AgentCore Runtime's ability to route
   same-session messages to same agent instance

## Components and Interfaces

### AgentCore Memory Configuration

```python
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.integrations.strands.config import AgentCoreMemoryConfig
from bedrock_agentcore.memory.integrations.strands.session_manager import AgentCoreMemorySessionManager

# Memory configuration
agentcore_memory_config = AgentCoreMemoryConfig(
    memory_id=MEMORY_ID,
    session_id=session_id,
    actor_id=actor_id
)

# Session manager
session_manager = AgentCoreMemorySessionManager(
    agentcore_memory_config=agentcore_memory_config,
    region_name=AWS_REGION
)
```

### Global Agent with Lazy Initialization

```python
# Global variables
global_agent = None
current_session_id = None
current_actor_id = None

def get_or_create_agent(session_id: str, actor_id: str) -> Agent:
    """Get existing agent or create new one with lazy initialization."""
    global global_agent, current_session_id, current_actor_id

    # Check if we need to create or recreate the agent
    if (global_agent is None or
        current_session_id != session_id or
        current_actor_id != actor_id):

        # Create new agent with session manager
        session_manager = create_session_manager(session_id, actor_id)
        global_agent = Agent(
            model=model,
            system_prompt=instructions,
            tools=tools,
            session_manager=session_manager,
        )

        current_session_id = session_id
        current_actor_id = actor_id

    return global_agent
```

### Memory Client Initialization

```python
def initialize_memory_client():
    """Initialize memory client with error handling."""
    memory_client = None
    memory_id = os.getenv("AGENTCORE_MEMORY_ID")

    if memory_id:
        try:
            memory_client = MemoryClient(region_name=os.getenv("AWS_REGION", "us-east-1"))
            logger.info("Memory client initialized successfully")
            return memory_client, memory_id
        except Exception as e:
            logger.warning(f"Memory client initialization failed: {e}")

    return None, None
```

### Session Manager Factory

```python
def create_session_manager(session_id: str, actor_id: str) -> Optional[AgentCoreMemorySessionManager]:
    """Create session manager if memory is configured."""
    memory_client, memory_id = initialize_memory_client()

    if memory_client and memory_id:
        try:
            config = AgentCoreMemoryConfig(
                memory_id=memory_id,
                session_id=session_id,
                actor_id=actor_id
            )

            return AgentCoreMemorySessionManager(
                agentcore_memory_config=config,
                region_name=os.getenv("AWS_REGION", "us-east-1")
            )
        except Exception as e:
            logger.warning(f"Session manager creation failed: {e}")

    return None
```

## Data Models

### Environment Variables

The system will use existing environment variables:

- `AGENTCORE_MEMORY_ID`: Memory resource identifier
- `AWS_REGION`: AWS region for memory client
- `BEDROCK_MODEL_ID`: Model configuration (existing)
- `MODEL_TEMPERATURE`: Temperature setting (existing)

### Session Parameters

Runtime parameters provided by AgentCore:

- `session_id`: From context.session_id (conversation_id)
- `actor_id`: From request payload
- `message_id`: From request payload
- `prompt`: User message content

## Error Handling

### Memory Initialization Failures

```python
def handle_memory_initialization_error(error: Exception):
    """Handle memory initialization failures gracefully."""
    logger.warning(f"Memory initialization failed: {error}")
    # Continue without memory - agent will work in stateless mode
    return None
```

### Session Manager Creation Failures

```python
def handle_session_manager_error(error: Exception):
    """Handle session manager creation failures."""
    logger.warning(f"Session manager creation failed: {error}")
    # Agent will be created without session manager
    return None
```

### Agent Creation Failures

```python
def handle_agent_creation_error(error: Exception):
    """Handle agent creation failures."""
    logger.error(f"Agent creation failed: {error}")
    # This is a critical error - should be propagated
    raise error
```

## Testing Strategy

### Unit Tests

1. **Memory Client Initialization**
   - Test successful initialization with valid environment variables
   - Test graceful failure with missing/invalid configuration
   - Test error handling and logging

2. **Session Manager Creation**
   - Test successful creation with valid parameters
   - Test failure handling with invalid memory configuration
   - Test configuration parameter validation

3. **Global Agent Management**
   - Test lazy initialization on first invocation
   - Test agent reuse for same session parameters
   - Test agent recreation when session parameters change
   - Test thread safety of global agent access

4. **Integration with AgentCore**
   - Test agent functionality with SessionManager
   - Test memory persistence within sessions
   - Test graceful degradation without memory

### Integration Tests

1. **End-to-End Memory Flow**
   - Test conversation persistence within a session
   - Test memory retrieval and storage
   - Test multiple message exchanges

2. **Session Transition Handling**
   - Test behavior when session_id changes
   - Test behavior when actor_id changes
   - Test proper cleanup and recreation

3. **Error Scenarios**
   - Test behavior with memory service unavailable
   - Test recovery from transient memory errors
   - Test agent functionality without memory

## Migration Plan

### Phase 1: Dependency Updates

1. Update `bedrock-agentcore` to `bedrock-agentcore[strands-agents]>=0.1.3` in
   pyproject.toml
2. Update imports to include AgentCore Memory components
3. Verify dependency compatibility

### Phase 2: Code Refactoring

1. Implement global agent pattern with lazy initialization
2. Replace custom memory hooks with SessionManager
3. Update agent creation logic
4. Remove greeting functionality (no longer needed)

### Phase 3: Cleanup

1. Remove custom memory hook files:
   - `memory_hooks.py`
   - Any related custom memory implementations
2. Remove tests that are no longer useful:
   - Tests for custom memory hook functionality
   - Tests for greeting functionality
   - Any tests specific to the old memory implementation
3. Update imports and remove unused dependencies
4. Clean up any remaining references to old memory system

### Phase 4: Testing and Validation

1. Run comprehensive test suite
2. Validate memory functionality in development environment
3. Verify session persistence behavior
4. Test error handling scenarios

## Performance Considerations

### Memory Usage

- Global agent reduces memory overhead from repeated instantiation
- SessionManager provides efficient memory operations
- Built-in caching in AgentCore Memory reduces redundant operations

### Response Time

- Global agent eliminates agent creation overhead per request
- SessionManager provides optimized memory retrieval
- Session persistence reduces context rebuilding time

### Scalability

- AgentCore Runtime handles session routing automatically
- Built-in memory strategies optimize storage and retrieval
- Reduced custom code maintenance overhead

## Security Considerations

### Memory Access Control

- Memory access controlled through IAM roles and policies
- Session isolation maintained through AgentCore Runtime
- Actor-based memory segregation through SessionManager

### Data Privacy

- Memory data encrypted at rest and in transit
- Session-specific memory isolation
- Proper cleanup of sensitive data in memory

### Error Information Exposure

- Error messages sanitized to prevent information leakage
- Detailed errors logged securely for debugging
- User-facing errors provide minimal technical details

## Monitoring and Observability

### Logging Strategy

```python
# Memory initialization
logger.info("Memory client initialized successfully")
logger.warning(f"Memory client initialization failed: {e}")

# Agent creation
logger.info(f"Created new agent for session {session_id}, actor {actor_id}")
logger.info(f"Reusing existing agent for session {session_id}")

# Memory operations
logger.debug(f"Session manager created for memory {memory_id}")
logger.warning(f"Session manager creation failed: {e}")
```

### Metrics to Monitor

- Agent creation frequency
- Memory operation success/failure rates
- Session persistence effectiveness
- Error rates by type

### Health Checks

- Memory client connectivity
- SessionManager functionality
- Agent creation success rates
- Overall system responsiveness
