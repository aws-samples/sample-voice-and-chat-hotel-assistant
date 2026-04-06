# Chat Response XML Tag Parsing - Tasks

## Task List

- [x] 1. Create response parser utility with unit tests
  - [x] 1.1 Create `response_parser.py` module in
        `virtual-assistant-common/utils`
  - [x] 1.2 Implement `parse_response()` function with regex-based parsing
  - [x] 1.3 Add logging for malformed tags and edge cases
  - [x] 1.4 Handle orphaned closing tags gracefully
  - [x] 1.5 Create `test_response_parser.py` in `virtual-assistant-chat/tests`
  - [x] 1.6 Write unit tests for all tag combinations and edge cases
  - [x] 1.7 Run tests and verify >90% coverage

- [x] 2. Integrate parser with chat agent
  - [x] 2.1 Import `parse_response` in `agent.py`
  - [x] 2.2 Update message processing loop to use parser
  - [x] 2.3 Verify empty responses are not sent to platform router

- [x] 3. Write integration tests for agent
  - [x] 3.1 Test agent parses message tags from model response
  - [x] 3.2 Test agent handles plain text responses (backward compatibility)
  - [x] 3.3 Test agent doesn't send empty responses (thinking-only)
  - [x] 3.4 Run integration tests and verify all pass

- [x] 4. Update chat prompt with tag instructions
  - [x] 4.1 Add "Requisitos de Formato de Respuesta" section to chat prompt
  - [x] 4.2 Add tag usage examples to prompt
  - [x] 4.3 Update existing examples to use tags
  - [x] 4.4 Add security note about keeping reasoning in thinking tags

- [x] 5. Verify and validate
  - [x] 5.1 Run all unit tests and ensure >90% coverage
  - [x] 5.2 Run integration tests
  - [x] 5.3 Manual testing with sample responses
  - [x] 5.4 Review logs for proper warning messages

## Task Details

### 1. Create response parser utility with unit tests

**Files**:

- `packages/virtual-assistant/virtual-assistant-common/virtual_assistant_common/utils/response_parser.py`
- `packages/virtual-assistant/virtual-assistant-chat/tests/test_response_parser.py`

**Implementation**:

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

**Test Coverage** (see design.md for complete test implementations):

- Basic message extraction
- Thinking tag removal
- Multiple message concatenation with `\n\n`
- Unclosed message tags
- Orphaned closing tags
- Thinking-only responses (return empty string)
- Edge cases (thinking inside messages, preamble/epilogue)
- Backward compatibility

**Run Command**:

```bash
cd packages/virtual-assistant/virtual-assistant-chat
uv run pytest tests/test_response_parser.py -v --cov=virtual_assistant_common.utils.response_parser
```

**Acceptance Criteria**:

- Function handles all tag combinations correctly
- Proper logging for malformed tags
- Backward compatible with plain text
- Returns empty string for thinking-only responses
- All tests pass with >90% coverage
- Edge cases properly handled

### 2. Integrate parser with chat agent

**File**:
`packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`

**Changes Required**:

1. Add import at top of file:

```python
from virtual_assistant_common.utils.response_parser import parse_response
```

2. Update message processing loop (around line 260):

```python
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

**Acceptance Criteria**:

- Parser is called for all message events
- Empty responses (thinking-only) are not sent
- Existing functionality remains intact

### 3. Write integration tests for agent

**File**:
`packages/virtual-assistant/virtual-assistant-chat/tests/test_agent_response_parsing.py`

**Test Scenarios**:

- Agent correctly parses message tags from model response
- Agent handles plain text responses (backward compatibility)
- Agent doesn't send empty responses when only thinking tags present
- Agent sends parsed content to platform router

**Run Command**:

```bash
cd packages/virtual-assistant/virtual-assistant-chat
uv run pytest tests/test_agent_response_parsing.py -v
```

**Acceptance Criteria**:

- All integration tests pass
- Mocked platform router receives only parsed message content
- No thinking content is sent to users

### 4. Update chat prompt with tag instructions

**File**:
`packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/chat_prompt.txt`

**Changes Required**:

1. Add new section after hotel list and before "## Capacidades Principales":

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

2. Update "Estilo Conversacional" section with examples using tags:

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

3. Add to security section:

```text
- NUNCA expongas tu razonamiento interno o el contenido de `<thinking>` al usuario
- Mantén toda la información técnica y de depuración dentro de las etiquetas `<thinking>`
```

**Acceptance Criteria**:

- Prompt includes clear tag usage instructions in Spanish
- Examples demonstrate proper tag usage
- Security considerations updated
- Prompt remains conversational and natural

### 5. Verify and validate

**Verification Steps**:

1. **Run all unit tests**:

```bash
cd packages/virtual-assistant/virtual-assistant-chat
uv run pytest tests/test_response_parser.py -v --cov=virtual_assistant_common.utils.response_parser
```

2. **Run integration tests**:

```bash
uv run pytest tests/test_agent_response_parsing.py -v
```

3. **Manual testing**:
   - Test with sample responses containing tags
   - Test with plain text responses
   - Test with malformed tags
   - Verify logs show appropriate warnings

4. **Code review**:
   - Review parser implementation for edge cases
   - Review agent integration for correctness
   - Review prompt updates for clarity

**Acceptance Criteria**:

- All tests pass
- Coverage >90% for parser
- Manual testing confirms expected behavior
- Logs show appropriate warnings for malformed tags
- No regressions in existing functionality

## Dependencies

- Python 3.9+ (standard library `re` module)
- pytest for testing
- Existing agent and platform router code

## Estimated Effort

- Task 1: 3-5 hours (parser implementation + comprehensive unit tests)
- Task 2: 30 minutes (agent integration)
- Task 3: 1-2 hours (integration tests)
- Task 4: 1 hour (prompt updates)
- Task 5: 1 hour (verification and validation)

**Total**: 6-9 hours

## Success Criteria

- [ ] All unit tests pass with >90% coverage
- [ ] All integration tests pass
- [ ] Parser handles all documented edge cases
- [ ] Agent correctly integrates parser
- [ ] Prompt includes clear tag instructions
- [ ] No regressions in existing functionality
- [ ] Logs show appropriate warnings for malformed tags
- [ ] Manual testing confirms expected behavior

## Notes

- The parser is backward compatible - existing responses without tags will work
  unchanged
- Empty responses (thinking-only) are intentionally not sent to users
- Multiple message blocks are joined with double newlines for readability
- Orphaned closing tags are handled gracefully by extracting content before them
- All changes are isolated to response processing - no changes to model
  invocation or tool handling
