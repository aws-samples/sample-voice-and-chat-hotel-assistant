# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Response parser utility for extracting message content from XML-tagged responses.

This module provides functionality to parse model responses that use <message> and <thinking>
XML tags to separate user-facing content from internal reasoning.
"""

import logging
import re

logger = logging.getLogger(__name__)


def normalize_newlines(text: str) -> str:
    """Normalize literal newline strings to actual newlines.

    Some models output literal '\\n' strings instead of actual newlines.
    This function converts them to proper newlines and cleans up excessive whitespace.

    Args:
        text: Text that may contain literal \\n strings

    Returns:
        Text with normalized newlines

    Examples:
        >>> normalize_newlines("Line 1\\nLine 2")
        'Line 1\\nLine 2'

        >>> normalize_newlines("Line 1\\n\\nLine 2")
        'Line 1\\n\\nLine 2'
    """
    if not text or not isinstance(text, str):
        return text

    # Replace literal \n with actual newlines
    text = text.replace("\\n", "\n")

    # Clean up excessive newlines (more than 2 consecutive)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text


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
    message_pattern = r"<message>(.*?)</message>"

    # Find all message blocks
    message_matches = re.findall(message_pattern, text, re.DOTALL)

    # Check for orphaned closing tags (more closing than opening tags)
    has_orphaned_closing = "</message>" in text and text.count("</message>") > text.count("<message>")

    if message_matches or has_orphaned_closing:
        all_content = []

        # Handle orphaned closing tag at the beginning
        if has_orphaned_closing:
            first_close_idx = text.find("</message>")
            first_open_idx = text.find("<message>")

            # If closing tag comes before any opening tag, extract content before it
            if first_open_idx == -1 or first_close_idx < first_open_idx:
                logger.warning("Found orphaned </message> closing tags")
                orphaned_content = text[:first_close_idx].strip()
                if orphaned_content:
                    all_content.append(orphaned_content)

        # Add all properly matched message blocks
        if message_matches:
            all_content.extend(message_matches)

        # Concatenate all content blocks
        parsed_content = "\n\n".join(all_content) if all_content else ""

        # Check for unclosed message tags and append their content
        if "<message>" in text and text.count("<message>") != text.count("</message>"):
            logger.warning("Detected unclosed <message> tag in response")
            # Find the last unclosed message tag and extract its content
            last_message_idx = text.rfind("<message>")
            # Check if this message tag is actually unclosed (not in our matches)
            after_last_tag = text[last_message_idx:]
            if "</message>" not in after_last_tag:
                # Extract content after the unclosed tag
                unclosed_content = text[last_message_idx + len("<message>") :].strip()
                # Remove any thinking tags from unclosed content but keep content after them
                if "<thinking>" in unclosed_content:
                    thinking_start = unclosed_content.find("<thinking>")
                    thinking_end = unclosed_content.find("</thinking>")
                    if thinking_end != -1:
                        # Remove thinking block and keep content after
                        before_thinking = unclosed_content[:thinking_start]
                        after_thinking = unclosed_content[thinking_end + len("</thinking>") :]
                        unclosed_content = (before_thinking + " " + after_thinking).strip()
                    else:
                        # Unclosed thinking tag, just remove from start
                        unclosed_content = unclosed_content[:thinking_start].strip()
                if unclosed_content:
                    parsed_content = parsed_content + "\n\n" + unclosed_content if parsed_content else unclosed_content

        # Check for thinking tags (just for logging)
        if "<thinking>" in text:
            logger.debug("Discarded <thinking> content from response")

        # Normalize newlines before returning
        return normalize_newlines(parsed_content.strip())

    # Check for orphaned closing tags (closing tags without opening tags)
    if "</message>" in text and "<message>" not in text:
        logger.warning("Found orphaned </message> closing tag - extracting content before tag")
        # Extract everything before the first closing tag
        end_idx = text.find("</message>")
        return normalize_newlines(text[:end_idx].strip())

    # No message tags found - check if there's an unclosed message tag
    if "<message>" in text:
        logger.warning("Found unclosed <message> tag - extracting content after tag")
        # Extract everything after the opening tag
        start_idx = text.find("<message>") + len("<message>")
        return normalize_newlines(text[start_idx:].strip())

    # If only thinking tags present, discard them (return empty string)
    # This handles the case where model outputs thinking before a tool call
    if "<thinking>" in text:
        logger.debug("Response contains only <thinking> tags - discarding")
        return ""

    # Backward compatibility: return original text if no tags at all
    # Normalize newlines before returning
    return normalize_newlines(text)
