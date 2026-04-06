# Chat Response XML Tag Parsing - Design

## Overview

This design implements structured response formatting for the chat agent using
`<message>` and `<thinking>` XML tags. The solution uses simple regex-based
parsing to extract user-facing content while discarding internal reasoning,
ensuring clean responses are sent to users.

## Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Agent Stream Processing                  │
│                                                              │
│  ┌────────────┐      ┌──────────────┐      ┌─────────────┐ │
│  │   Strands  │─────▶│   Response   │─────▶│  Platform   │ │
│  │    Agent   │      │    Parser    │      │   Router    │ │
│  │            │      │              │      │             │ │
│  │ stream_    │      │ parse_       │      │ send_       │ │
│  │ async()    │      │ response()   │      │ response()  │ │
│  └────────────┘      └──────────────┘      └─────────────┘ │
│                             │                                │
│                             │                                │
│                      ┌──────▼──────┐                        │
│                      │   Logging   │                        │
│                      │  (warnings) │                        │
│                      └─────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Agent generates response** → Strands Agent produces text with optional tags
2. **Extract text content** → Pull text from message event structure
3. **Parse response** → Apply regex patterns to extract `<message>` content
4. **Send to user** → Forward parsed content to platform router
5. **Log warnings** → Record any malformed tag issues

## Implementation Details

### 1. Response Parser Utility

**Location**:
`packages/virtual-assistant/virtual-assistant-common/virtual_assistant_common/utils/response_parser.py`

**Function Signature**:

```python
def parse_response(text: str) -> str:
    """Parse response text to extract message content and discard thinking.

    Args:
        text: Raw response text from model

    Returns:
        Parsed message content (or original text if no tags found)
    """
```

**Parsing Logic**:

```python
import re
import logging

logger = logging.getLogger(__name__)

def parse_response(text: str) -> str:
    """Parse response text to extract message content and discard thinking.

    Extracts content from <message> tags and discards <thinking> tags.
    Falls back to original text if no tags are found (backward compatibility).

    Args:
        text: Raw response text from model

    Returns:
        Parsed message content (or original text if no tags found)

    Examples:
        >>> parse_response("<message>Hello</message>")
        'Hello'

        >>> parse_response("<message>Hello</message><thinking>reasoning</thinking>")
        'Hello'

        >>> parse_response("Plain text")
        'Plain text'
    """
    if not text or not isinstance(text, str):
        return text

    # Pattern to match <message>content</message> (non-greedy, dotall for multiline)
    message_pattern = r'<message>(.*?)</message>'

    # Find all message blocks
    message_matches = re.findall(message_pattern, text, re.DOTALL)

    if message_matches:
        # Concatenate all message blocks with double newlines between them
        parsed_content = '\n\n'.join(message_matches)

        # Check for unclosed message tags and append their content
        if '<message>' in text and text.count('<message>') != text.count('</message>'):
            logger.warning("Detected unclosed <message> tag in response")
            # Find the last unclosed message tag and extract its content
            last_message_idx = text.rfind('<message>')
            # Check if this message tag is actually unclosed (not in our matches)
            after_last_tag = text[last_message_idx:]
            if '</message>' not in after_last_tag:
                # Extract content after the unclosed tag
                unclosed_content = text[last_message_idx + len('<message>'):].strip()
                # Remove any thinking tags from unclosed content
                if '<thinking>' in unclosed_content:
                    thinking_idx = unclosed_content.find('<thinking>')
                    unclosed_content = unclosed_content[:thinking_idx].strip()
                if unclosed_content:
                    parsed_content = parsed_content + '\n\n' + unclosed_content

        # Check for thinking tags (just for logging)
        if '<thinking>' in text:
            logger.debug("Discarded <thinking> content from response")

        return parsed_content.strip()

    # Check for orphaned closing tags (closing tags without opening tags)
    if '</message>' in text and '<message>' not in text:
        logger.warning("Found orphaned </message> closing tag - extracting content before tag")
        # Extract everything before the first closing tag
        end_idx = text.find('</message>')
        return text[:end_idx].strip()

    # Check for mixed orphaned closing tags with proper message blocks
    if '</message>' in text and text.count('</message>') > text.count('<message>'):
        logger.warning("Found orphaned </message> closing tags")
        # Extract content before first closing tag as first message
        first_close_idx = text.find('</message>')
        orphaned_content = text[:first_close_idx].strip()

        # Find any properly formed messages after the orphaned closing tag
        remaining_text = text[first_close_idx + len('</message>'):]
        remaining_matches = re.findall(message_pattern, remaining_text, re.DOTALL)

        if remaining_matches:
            all_content = [orphaned_content] + remaining_matches
            return '\n\n'.join(all_content).strip()
        else:
            return orphaned_content

    # No message tags found - check if there's an unclosed message tag
    if '<message>' in text:
        logger.warning("Found unclosed <message> tag - extracting content after tag")
        # Extract everything after the opening tag
        start_idx = text.find('<message>') + len('<message>')
        return text[start_idx:].strip()

    # If only thinking tags present, discard them (return empty string)
    # This handles the case where model outputs thinking before a tool call
    if '<thinking>' in text:
        logger.debug("Response contains only <thinking> tags - discarding")
        return ""

    # Backward compatibility: return original text if no tags at all
    return text
```

**Key Design Decisions**:

1. **Non-greedy matching** (`.*?`): Handles multiple `<message>` blocks
   correctly
2. **DOTALL flag** (`re.DOTALL`): Allows content to span multiple lines
3. **Double newline concatenation**: Multiple `<message>` blocks are joined with
   `\n\n` for readability
4. **Whitespace preservation**: Content within tags keeps original formatting
5. **Strip final result**: Remove leading/trailing whitespace from concatenated
   messages
6. **Unclosed tag handling**: Extracts content after `<message>` tag even if not
   closed
7. **Thinking-only responses**: Returns empty string when only `<thinking>` tags
   present
8. **Backward compatibility**: Returns original text if no tags found
9. **Warning logs**: Alerts on malformed tags without breaking functionality

### 2. Integration with Agent

**Location**:
`packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`

**Modification Point**: In `process_user_message()` function, update the message
processing loop:

```python
# Current code (lines ~260-275):
async for event in agent.stream_async(user_message):
    if "message" in event:
        text = []
        message_content = event.get("message", {}).get("content", [])

        for content in message_content:
            if isinstance(content, dict) and "text" in content:
                text.append(content["text"])

        message = "".join(text)
        if message.strip():
            response_result = await platform_router.send_response(conversation_id, message)
            if not response_result.success:
                logger.error(f"Failed to send response for message group {message_ids}: {response_result.error}")
```

**Updated code**:

```python
from virtual_assistant_common.utils.response_parser import parse_response

async for event in agent.stream_async(user_message):
    if "message" in event:
        text = []
        message_content = event.get("message", {}).get("content", [])

        for content in message_content:
            if isinstance(content, dict) and "text" in content:
                text.append(content["text"])

        raw_message = "".join(text)
        if raw_message.strip():
            # Parse response to extract <message> content and discard <thinking>
            parsed_message = parse_response(raw_message)

            # Only send if there's actual content (handles thinking-only responses)
            if parsed_message.strip():
                response_result = await platform_router.send_response(conversation_id, parsed_message)
                if not response_result.success:
                    logger.error(f"Failed to send response for message group {message_ids}: {response_result.error}")
```

**Changes**:

1. Import `parse_response` utility
2. Rename `message` to `raw_message` for clarity
3. Call `parse_response()` to extract message content
4. Send `parsed_message` instead of `raw_message`
5. Check `parsed_message.strip()` before sending

### 3. Chat Prompt Updates

**Location**:
`packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/chat_prompt.txt`

**Add new section after hotel list and before "## Capacidades Principales"**:

```text
## Requisitos de Formato de Respuesta

DEBES formatear todas las respuestas con esta estructura:

<message>Tu respuesta al cliente va aquí. Este texto será hablado en voz alta, así que escribe de forma natural y conversacional.</message>

<thinking>Tu proceso de razonamiento puede ir aquí si es necesario para decisiones complejas.</thinking>

Reglas importantes:
- NUNCA pongas contenido de pensamiento dentro de las etiquetas message
- SIEMPRE comienza con etiquetas `<message>`, incluso cuando uses herramientas, para informar al cliente que estás trabajando en resolver su solicitud
- El contenido de `<thinking>` es solo para tu razonamiento interno y nunca será mostrado al cliente
- Mantén el contenido de `<message>` conversacional y apropiado para ser hablado en voz alta
```

**Update existing response examples** (in "## Requisitos de Formato de
Respuesta" section):

Replace the "Estilo Conversacional" subsection examples with:

```text
### Ejemplos de Respuestas

Ejemplo - Inicio de conversación:
Usuario: "Quiero hacer una reserva para dos personas del 15 al 17 de enero."
<message>Perfecto, dos personas del 15 al 17 de enero. ¿En cuál hotel le gustaría hospedarse?</message>

Ejemplo - Usando herramientas:
Usuario: "En el Paraíso Vallarta."
<message>Déjeme verificar la disponibilidad.</message>
<thinking>El cliente quiere hospedarse en el Paraíso Vallarta del 15 al 17 de enero para dos personas. Voy a usar check_availability para verificar qué habitaciones están disponibles.</thinking>

Ejemplo - Solo pensamiento antes de herramienta (no se envía al usuario):
<thinking>Necesito verificar disponibilidad. Llamaré a check_availability con hotel_id, fechas y número de huéspedes.</thinking>
[Nota: Este tipo de respuesta no envía nada al usuario - solo razonamiento interno antes de usar herramientas]

Ejemplo - Presentando opciones:
<message>Tenemos disponible una habitación doble estándar con dos camas matrimoniales por tres mil pesos por noche, y también una suite doble con vista al mar por cinco mil pesos por noche. ¿Cuál les interesa más?</message>

Ejemplo - Recolectando datos:
Usuario: "La estándar está bien."
<message>Excelente elección. Para proceder con la reserva, necesito algunos datos. ¿Me puede proporcionar su nombre completo?</message>
<thinking>El cliente eligió la habitación doble estándar. Necesito recolectar nombre, email y teléfono antes de crear la reserva.</thinking>

Ejemplo - Confirmación:
Usuario: "María González."
<message>Perfecto María. ¿Y su correo electrónico?</message>

Ejemplo - Manejando errores:
<message>Disculpe, estoy teniendo dificultades técnicas en este momento. ¿Le gustaría que lo transfiera con uno de nuestros agentes?</message>
<thinking>La herramienta check_availability falló. Debo ofrecer transferencia a agente humano.</thinking>
```

**Add to security section**:

```text
- NUNCA expongas tu razonamiento interno o el contenido de `<thinking>` al usuario
- Mantén toda la información técnica y de depuración dentro de las etiquetas `<thinking>`
```

## Testing Strategy

### Unit Tests

**Location**:
`packages/virtual-assistant/virtual-assistant-chat/tests/test_response_parser.py`

**Test Cases**:

```python
import pytest
from virtual_assistant_common.utils.response_parser import parse_response


class TestResponseParser:
    """Test suite for response parser utility."""

    def test_simple_message_tag(self):
        """Test basic message tag extraction."""
        text = "<message>Hello world</message>"
        assert parse_response(text) == "Hello world"

    def test_message_with_thinking(self):
        """Test that thinking content is discarded."""
        text = "<message>Hello</message><thinking>Internal reasoning</thinking>"
        assert parse_response(text) == "Hello"

    def test_thinking_before_message(self):
        """Test thinking tag before message tag."""
        text = "<thinking>Reasoning first</thinking><message>Response</message>"
        assert parse_response(text) == "Response"

    def test_multiple_message_blocks(self):
        """Test concatenation of multiple message blocks."""
        text = "<message>First part</message><message>Second part</message>"
        assert parse_response(text) == "First part\n\nSecond part"

    def test_multiple_message_blocks_three(self):
        """Test concatenation of three message blocks."""
        text = "<message>Part 1</message><message>Part 2</message><message>Part 3</message>"
        assert parse_response(text) == "Part 1\n\nPart 2\n\nPart 3"

    def test_multiline_message(self):
        """Test message content spanning multiple lines."""
        text = """<message>Line 1
Line 2
Line 3</message>"""
        result = parse_response(text)
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_no_tags_backward_compatibility(self):
        """Test backward compatibility with plain text."""
        text = "Plain text without tags"
        assert parse_response(text) == "Plain text without tags"

    def test_empty_message_tag(self):
        """Test empty message tag."""
        text = "<message></message>"
        assert parse_response(text) == ""

    def test_whitespace_preservation(self):
        """Test that whitespace within tags is preserved."""
        text = "<message>  Indented text  </message>"
        assert parse_response(text) == "Indented text"  # Stripped at end

    def test_unclosed_message_tag(self):
        """Test handling of unclosed message tag."""
        text = "<message>Unclosed tag"
        # Should extract content after opening tag
        assert parse_response(text) == "Unclosed tag"

    def test_closed_and_unclosed_message_tags(self):
        """Test response with both closed and unclosed message tags."""
        text = "<message>First</message><message>Second"
        result = parse_response(text)
        assert "First" in result
        assert "Second" in result
        assert result == "First\n\nSecond"

    def test_unclosed_message_with_thinking(self):
        """Test unclosed message tag followed by thinking tag."""
        text = "<message>First</message><message>Second<thinking>reasoning</thinking>"
        result = parse_response(text)
        assert "First" in result
        assert "Second" in result
        assert "reasoning" not in result
        assert result == "First\n\nSecond"

    def test_only_thinking_tag(self):
        """Test response with only thinking tag (before tool call)."""
        text = "<thinking>Reasoning before tool call</thinking>"
        # Should return empty string, not original text
        assert parse_response(text) == ""

    def test_only_thinking_tag_multiline(self):
        """Test multiline thinking-only response."""
        text = """<thinking>
Step 1: Analyze request
Step 2: Call tool
Step 3: Process result
</thinking>"""
        # Should return empty string
        assert parse_response(text) == ""

    def test_empty_string(self):
        """Test empty string input."""
        assert parse_response("") == ""

    def test_none_input(self):
        """Test None input."""
        assert parse_response(None) is None

    def test_special_characters_in_message(self):
        """Test message with special characters."""
        text = "<message>Price: $100 & taxes</message>"
        assert parse_response(text) == "Price: $100 & taxes"

    def test_nested_angle_brackets(self):
        """Test content with angle brackets inside."""
        text = "<message>Use <command> to proceed</message>"
        assert parse_response(text) == "Use <command> to proceed"

    def test_case_sensitivity(self):
        """Test that tags are case-sensitive."""
        text = "<MESSAGE>Should not match</MESSAGE>"
        # Should return original since tags are lowercase only
        assert parse_response(text) == "<MESSAGE>Should not match</MESSAGE>"

    def test_mixed_content(self):
        """Test realistic mixed content."""
        text = """<message>Déjeme verificar la disponibilidad.</message>
<thinking>Cliente quiere Paraíso Vallarta del 15-17 enero. Usar check_availability.</thinking>
<message>Tenemos habitaciones disponibles.</message>"""
        result = parse_response(text)
        assert "Déjeme verificar" in result
        assert "Tenemos habitaciones" in result
        assert "check_availability" not in result
        assert "thinking" not in result.lower()

    # Edge case tests

    def test_thinking_inside_closed_message(self):
        """Test thinking tag inside a properly closed message tag."""
        text = "<message>First</message><message>Second<thinking>reasoning</thinking> continuation</message>"
        result = parse_response(text)
        # Regex will match up to </message>, so thinking and continuation are included
        assert "First" in result
        assert "Second" in result
        assert "reasoning" in result  # Inside closed message, so it's captured
        assert "continuation" in result

    def test_thinking_inside_unclosed_message(self):
        """Test thinking tag inside an unclosed message tag."""
        text = "<message>First</message><message>Second<thinking>reasoning</thinking> continuation"
        result = parse_response(text)
        assert "First" in result
        assert "Second" in result
        assert "reasoning" not in result  # Thinking stripped from unclosed message
        assert "continuation" in result  # But continuation after thinking is kept

    def test_preamble_and_epilogue(self):
        """Test content before and after message tags."""
        text = "preamble<thinking>Reasoning first</thinking><message>Response</message>epilogue"
        result = parse_response(text)
        assert result == "Response"
        assert "preamble" not in result
        assert "epilogue" not in result
        assert "Reasoning" not in result

    def test_only_closing_tags(self):
        """Test response with only closing tags (no opening tags)."""
        text = "First</message><message>Second</message>"
        result = parse_response(text)
        # "First" before orphaned closing tag + "Second" with proper tags
        assert result == "First\n\nSecond"

    def test_single_closing_tag(self):
        """Test response with only a single closing tag."""
        text = "First</message>"
        result = parse_response(text)
        # Content before orphaned closing tag
        assert result == "First"
```

### Integration Tests

**Location**:
`packages/virtual-assistant/virtual-assistant-chat/tests/test_agent_response_parsing.py`

**Test Cases**:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from virtual_assistant_chat.agent import process_user_message


@pytest.mark.asyncio
async def test_agent_parses_message_tags(mock_agent, mock_platform_router):
    """Test that agent correctly parses message tags from model response."""

    # Mock agent stream to return response with tags
    mock_event = {
        "message": {
            "content": [
                {"text": "<message>Hello user</message><thinking>Internal reasoning</thinking>"}
            ]
        }
    }

    mock_agent.stream_async = AsyncMock(return_value=[mock_event])
    mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

    # Process message
    await process_user_message(
        user_message="Test",
        actor_id="test-actor",
        message_ids=["msg-1"],
        conversation_id="conv-1",
        model_id="test-model",
        temperature=0.2,
        session_id="session-1"
    )

    # Verify only message content was sent (no thinking)
    mock_platform_router.send_response.assert_called_once()
    call_args = mock_platform_router.send_response.call_args
    assert call_args[0][1] == "Hello user"
    assert "thinking" not in call_args[0][1].lower()


@pytest.mark.asyncio
async def test_agent_handles_plain_text_response(mock_agent, mock_platform_router):
    """Test backward compatibility with plain text responses."""

    mock_event = {
        "message": {
            "content": [
                {"text": "Plain text response without tags"}
            ]
        }
    }

    mock_agent.stream_async = AsyncMock(return_value=[mock_event])
    mock_platform_router.send_response = AsyncMock(return_value=MagicMock(success=True))

    await process_user_message(
        user_message="Test",
        actor_id="test-actor",
        message_ids=["msg-1"],
        conversation_id="conv-1",
        model_id="test-model",
        temperature=0.2,
        session_id="session-1"
    )

    # Verify plain text was sent as-is
    mock_platform_router.send_response.assert_called_once()
    call_args = mock_platform_router.send_response.call_args
    assert call_args[0][1] == "Plain text response without tags"
```

## Correctness Properties

### Property 1: Message Content Extraction

**Validates: Requirements 1.1, 1.2**

**Property**: For any response containing `<message>` tags, the parsed output
contains only the content within those tags.

**Test Strategy**:

```python
@given(st.text(min_size=1), st.text(min_size=1))
def test_message_extraction_property(message_content, thinking_content):
    """Property: Message tags extract only message content."""
    text = f"<message>{message_content}</message><thinking>{thinking_content}</thinking>"
    result = parse_response(text)

    # Property: Result contains message content
    assert message_content in result or message_content.strip() == result

    # Property: Result does not contain thinking content
    assert thinking_content not in result
```

### Property 2: Backward Compatibility

**Validates: Requirement 1.3**

**Property**: For any response without tags, the parsed output equals the
original input.

**Test Strategy**:

```python
@given(st.text().filter(lambda x: '<message>' not in x and '<thinking>' not in x))
def test_backward_compatibility_property(plain_text):
    """Property: Plain text passes through unchanged."""
    result = parse_response(plain_text)
    assert result == plain_text
```

### Property 3: Whitespace Preservation

**Validates: Requirement 3.6**

**Property**: Whitespace within message tags is preserved (except
leading/trailing).

**Test Strategy**:

```python
@given(st.text(min_size=1))
def test_whitespace_preservation_property(content):
    """Property: Internal whitespace is preserved."""
    text = f"<message>{content}</message>"
    result = parse_response(text)

    # Property: Internal whitespace preserved
    if content.strip():
        assert result == content.strip()
```

### Property 4: Multiple Message Concatenation

**Validates: Requirement 1.4**

**Property**: Multiple message blocks are concatenated with double newlines
between them.

**Test Strategy**:

```python
@given(st.lists(st.text(min_size=1), min_size=2, max_size=5))
def test_multiple_message_concatenation_property(messages):
    """Property: Multiple messages concatenate with double newlines."""
    text = "".join(f"<message>{msg}</message>" for msg in messages)
    result = parse_response(text)

    # Property: All messages appear in result joined by double newlines
    expected = "\n\n".join(messages).strip()
    assert result == expected
```

## Error Handling

### Malformed Tags

**Scenario 1: Unclosed message tag**

```python
Input:  "<message>Hello world"
Output: "Hello world"  # Content after opening tag
Log:    WARNING - "Found unclosed <message> tag - extracting content after tag"
```

**Scenario 2: Orphaned closing tag**

```python
Input:  "Hello world</message>"
Output: "Hello world"  # Content before orphaned closing tag
Log:    WARNING - "Found orphaned </message> closing tag - extracting content before tag"
```

**Scenario 3: Empty message tag**

```python
Input:  "<message></message>"
Output: ""  # Empty string
Log:    None (valid case)
```

**Scenario 4: Closed and unclosed message tags**

```python
Input:  "<message>First</message><message>Second"
Output: "First\n\nSecond"  # Both messages extracted
Log:    WARNING - "Detected unclosed <message> tag in response"
```

**Scenario 5: Unclosed message with thinking**

```python
Input:  "<message>First</message><message>Second<thinking>reasoning</thinking>"
Output: "First\n\nSecond"  # Thinking discarded from unclosed message
Log:    WARNING - "Detected unclosed <message> tag in response"
        DEBUG - "Discarded <thinking> content from response"
```

### Edge Cases

**Case 1: Only thinking tag (before tool call)**

```python
Input:  "<thinking>Internal reasoning before tool call</thinking>"
Output: ""  # Empty string - discard thinking
Log:    DEBUG - "Response contains only <thinking> tags - discarding"
```

**Case 2: Mixed valid and invalid tags**

```python
Input:  "<message>Valid</message><invalid>content</invalid>"
Output: "Valid"  # Extracts valid message
Log:    None
```

**Case 3: Thinking inside closed message**

```python
Input:  "<message>First</message><message>Second<thinking>reasoning</thinking> continuation</message>"
Output: "First\n\nSecond<thinking>reasoning</thinking> continuation"  # Thinking captured inside closed tag
Log:    DEBUG - "Discarded <thinking> content from response"
```

**Case 4: Thinking inside unclosed message**

```python
Input:  "<message>First</message><message>Second<thinking>reasoning</thinking> continuation"
Output: "First\n\nSecond continuation"  # Thinking stripped from unclosed content
Log:    WARNING - "Detected unclosed <message> tag in response"
        DEBUG - "Discarded <thinking> content from response"
```

**Case 5: Preamble and epilogue**

```python
Input:  "preamble<thinking>Reasoning</thinking><message>Response</message>epilogue"
Output: "Response"  # Only message content extracted
Log:    DEBUG - "Discarded <thinking> content from response"
```

**Case 6: Only closing tags**

```python
Input:  "First</message><message>Second</message>"
Output: "First\n\nSecond"  # Orphaned closing tag treated as end of implicit message
Log:    WARNING - "Found orphaned </message> closing tags"
```

**Case 7: Single closing tag**

```python
Input:  "First</message>"
Output: "First"  # Content before orphaned closing tag
Log:    WARNING - "Found orphaned </message> closing tag - extracting content before tag"
```

**Case 3: Multiline with mixed content**

```python
Input:  """Some text
<message>Message content</message>
More text
<thinking>Reasoning</thinking>"""
Output: "Message content"
Log:    DEBUG - "Discarded <thinking> content from response"
```

## Performance Considerations

### Regex Performance

- **Pattern complexity**: Simple non-greedy patterns are O(n) where n is text
  length
- **Expected text size**: Typically < 4KB per response
- **Regex compilation**: Patterns can be pre-compiled for repeated use
- **Memory usage**: Minimal - only stores matched groups

### Optimization Opportunities

1. **Pre-compile regex patterns** (if performance becomes an issue):

```python
MESSAGE_PATTERN = re.compile(r'<message>(.*?)</message>', re.DOTALL)

def parse_response(text: str) -> str:
    message_matches = MESSAGE_PATTERN.findall(text)
    # ... rest of logic
```

2. **Early return for common case** (no tags):

```python
def parse_response(text: str) -> str:
    # Fast path: no tags at all
    if '<' not in text:
        return text
    # ... rest of logic
```

3. **Avoid unnecessary string operations**:

- Use `''.join()` for concatenation (already doing this)
- Single `.strip()` call at the end (already doing this)

## Deployment Considerations

### Rollout Strategy

1. **Phase 1**: Deploy parser utility and agent changes
   - Parser handles both tagged and untagged responses
   - Backward compatible with existing behavior
   - Monitor logs for parsing warnings

2. **Phase 2**: Update chat prompt with tag instructions
   - Models start using tags in responses
   - Parser extracts message content
   - Monitor for any parsing issues

3. **Phase 3**: Validate and optimize
   - Review logs for malformed tags
   - Adjust prompt if needed
   - Optimize parser if performance issues arise

### Monitoring

**Metrics to track**:

- Frequency of parsing warnings (malformed tags)
- Response processing latency (should be negligible)
- Percentage of responses with vs without tags

**Log analysis**:

- Search for "unclosed <message> tag" warnings
- Search for "partial tags but no complete <message> blocks" warnings
- Track adoption of tag format over time

### Rollback Plan

If issues arise:

1. **Immediate**: Remove tag instructions from prompt (models stop using tags)
2. **Parser remains**: Backward compatible, handles plain text
3. **No code rollback needed**: Parser gracefully handles both formats

## Security Considerations

### Input Validation

- **No code execution risk**: Regex patterns don't execute content
- **No injection risk**: Content is not evaluated or executed
- **XSS protection**: Content is sent through existing platform router (already
  handles escaping)

### Information Disclosure

- **Thinking content**: Properly discarded, never sent to user
- **System prompts**: Remain in thinking tags, not exposed
- **Technical details**: Models instructed to keep in thinking tags

### Logging

- **Sanitization**: Existing log sanitization applies (actor_id, session_id)
- **Warning logs**: Don't include sensitive content, only tag structure issues
- **Debug logs**: Only log presence of thinking tags, not content

## Dependencies

### New Dependencies

- None (uses Python standard library `re` module)

### Modified Files

1. `packages/virtual-assistant/virtual-assistant-common/virtual_assistant_common/utils/response_parser.py`
   (new)
2. `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`
   (modified)
3. `packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/chat_prompt.txt`
   (modified)
4. `packages/virtual-assistant/virtual-assistant-chat/tests/test_response_parser.py`
   (new)
5. `packages/virtual-assistant/virtual-assistant-chat/tests/test_agent_response_parsing.py`
   (new)

### Version Compatibility

- Python 3.9+ (regex module is standard library)
- No breaking changes to existing APIs
- Backward compatible with current response format

## Future Enhancements

### Potential Improvements (Out of Scope)

1. **Streaming support**: Parse partial responses as they stream
2. **Additional tags**: Support for `<action>`, `<context>`, etc.
3. **Tag attributes**: Support `<message lang="es">` for language hints
4. **Performance optimization**: Pre-compiled patterns if needed
5. **Metrics dashboard**: Visualize tag adoption and parsing stats

### Extension Points

The parser is designed to be easily extended:

- Add new tag types by adding regex patterns
- Modify concatenation logic for different behaviors
- Add custom validation rules
- Integrate with monitoring systems

## Acceptance Criteria Mapping

| Requirement              | Design Element           | Validation                                       |
| ------------------------ | ------------------------ | ------------------------------------------------ |
| 1.1 Discard thinking     | `parse_response()` regex | Unit test: `test_message_with_thinking`          |
| 1.2 Extract message      | `parse_response()` regex | Unit test: `test_simple_message_tag`             |
| 1.3 Backward compat      | No-tag fallback          | Unit test: `test_no_tags_backward_compatibility` |
| 1.4 Multiple messages    | Concatenation logic      | Unit test: `test_multiple_message_blocks`        |
| 1.5 Tag order            | DOTALL regex flag        | Unit test: `test_thinking_before_message`        |
| 1.6 Case sensitive       | Lowercase patterns       | Unit test: `test_case_sensitivity`               |
| 2.1 Prompt instructions  | Chat prompt section      | Manual review                                    |
| 2.2 Voice-friendly note  | Chat prompt text         | Manual review                                    |
| 2.3 Thinking explanation | Chat prompt text         | Manual review                                    |
| 2.4 Examples             | Chat prompt examples     | Manual review                                    |
| 2.5 Spanish language     | Chat prompt language     | Manual review                                    |
| 3.1 Regex-based          | `re.findall()` usage     | Code review                                      |
| 3.2 Reusable function    | Utility module           | Code structure                                   |
| 3.3 Unit tests           | Test file                | Test coverage report                             |
| 3.4 Warning logs         | `logger.warning()`       | Unit tests with log capture                      |
| 3.5 Whitespace           | `.strip()` on result     | Unit test: `test_whitespace_preservation`        |
| 3.6 Simple/readable      | Code structure           | Code review                                      |

## Summary

This design provides a simple, robust solution for parsing structured responses
using regex-based pattern matching. The implementation is backward compatible,
well-tested, and easy to maintain. The chat prompt updates guide models to use
the tag format while the parser gracefully handles both tagged and untagged
responses.
