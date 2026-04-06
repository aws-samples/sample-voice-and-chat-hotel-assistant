# Chat Response XML Tag Parsing - Requirements

## Overview

Update the chat agent to support structured response formatting using
`<message>` and `<thinking>` XML tags. This allows models to separate
user-facing content from internal reasoning, improving response quality and
preventing internal reasoning from being sent to users.

## User Stories

### 1. As a chat agent, I need to parse responses with XML tags

**Acceptance Criteria:**

- 1.1 When a model response contains `<thinking>` tags, the content between
  `<thinking>` and `</thinking>` MUST be discarded
- 1.2 When a model response contains `<message>` tags, only the content between
  `<message>` and `</message>` MUST be sent to the user
- 1.3 When a model response contains neither tag, the entire response MUST be
  sent to the user (backward compatibility)
- 1.4 The parsing MUST handle multiple `<message>` blocks in a single response
- 1.5 The parsing MUST handle responses where `<thinking>` appears before or
  after `<message>` blocks
- 1.6 The parsing MUST be case-sensitive (only lowercase tags are valid)

### 2. As a system administrator, I need the chat prompt to instruct models to use XML tags

**Acceptance Criteria:**

- 2.1 The chat prompt MUST include explicit instructions for using `<message>`
  and `<thinking>` tags
- 2.2 The instructions MUST specify that `<message>` content will be spoken
  aloud (voice-friendly)
- 2.3 The instructions MUST specify that `<thinking>` content is for internal
  reasoning only
- 2.4 The instructions MUST include examples showing proper tag usage
- 2.5 The instructions MUST be in Spanish (matching the existing prompt
  language)

### 3. As a developer, I need the parsing logic to be robust and maintainable

**Acceptance Criteria:**

- 3.1 The parsing logic MUST use regex-based pattern matching (no XML parser
  required)
- 3.2 The parsing logic MUST handle malformed tags gracefully (missing closing
  tags)
- 3.3 The parsing logic MUST be implemented as a reusable utility function
- 3.4 The parsing logic MUST include comprehensive unit tests
- 3.5 The parsing logic MUST log warnings when malformed tags are detected
- 3.6 The parsing logic MUST preserve whitespace within `<message>` content
- 3.7 The parsing logic MUST be simple and readable (prefer clarity over
  complexity)

## Technical Requirements

### Response Processing Flow

1. Agent receives model response from Strands SDK
2. Extract text content from response
3. Parse text for `<message>` and `<thinking>` tags
4. If `<message>` tags present: extract only message content
5. If no tags present: use entire response (backward compatibility)
6. Send processed content to platform router

### Tag Format Specification

- Opening tags: `<message>`, `<thinking>`
- Closing tags: `</message>`, `</thinking>`
- Tags are case-sensitive (lowercase only)
- Tags can appear in any order
- Multiple `<message>` blocks are concatenated
- All `<thinking>` blocks are discarded

### Error Handling

- Unclosed tags: Log warning, treat as plain text
- Empty tags: Treat as empty string
- Malformed tags: Fall back to entire response
- Use simple regex patterns for robustness and clarity

## Prompt Updates

The chat prompt at
`packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/chat_prompt.txt`
must be updated to include:

1. **Formatting Requirements Section** (new section after date and hotel list):

```
## Requisitos de Formato de Respuesta

DEBES formatear todas las respuestas con esta estructura:

<message>Tu respuesta al cliente va aquí. Este texto será hablado en voz alta, así que escribe de forma natural y conversacional.</message>

<thinking>Tu proceso de razonamiento puede ir aquí si es necesario para decisiones complejas.</thinking>

NUNCA pongas contenido de pensamiento dentro de las etiquetas message.
SIEMPRE comienza con etiquetas `<message>`, incluso cuando uses herramientas, para informar al cliente que estás trabajando en resolver su solicitud.
```

2. **Response Examples** (update existing examples to use tags):

- All example responses should demonstrate proper tag usage
- Show examples with and without `<thinking>` blocks
- Demonstrate tool usage with tags

3. **Security Section** (add to existing security requirements):

- Reinforce that system instructions and reasoning should stay in `<thinking>`
- Never expose internal reasoning to users

## Dependencies

- Strands SDK: Response format from `agent.stream_async()`
- Platform Router: `send_response()` method signature
- Chat Prompt: MCP server asset file

## Out of Scope

- Using an XML parser library (regex-based approach is sufficient)
- Parsing other XML tags beyond `<message>` and `<thinking>`
- HTML entity decoding (e.g., `&lt;`, `&gt;`)
- Complex XML validation beyond basic tag matching
- Support for tag attributes (e.g., `<message lang="es">`)
- Streaming partial tag content (wait for complete tags)
- Nested tag handling (not expected in model output)

## Success Metrics

- All responses with `<thinking>` tags have thinking content removed
- All responses with `<message>` tags send only message content
- Backward compatibility maintained for responses without tags
- Zero errors from malformed tags (graceful degradation)
- Unit test coverage > 90% for parsing logic

## References

- Commit d6545a1920f69ffc2e50326c103b21b83036a957: Connect prompt with tag
  examples
- `packages/virtual-assistant/virtual-assistant-chat/virtual_assistant_chat/agent.py`:
  Current response processing
- `packages/hotel-pms-simulation/hotel_pms_simulation/mcp/assets/chat_prompt.txt`:
  Chat prompt to update
