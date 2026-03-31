# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: MIT-0

"""Unit tests for response parser utility."""

import pytest
from hypothesis import given
from hypothesis import strategies as st
from virtual_assistant_common.utils.response_parser import normalize_newlines, parse_response


class TestNormalizeNewlines:
    """Test suite for normalize_newlines function."""

    def test_literal_newline_single(self):
        """Test conversion of single literal \\n to actual newline."""
        text = "Line 1\\nLine 2"
        assert normalize_newlines(text) == "Line 1\nLine 2"

    def test_literal_newline_double(self):
        """Test conversion of double literal \\n to actual newlines."""
        text = "Line 1\\n\\nLine 2"
        assert normalize_newlines(text) == "Line 1\n\nLine 2"

    def test_literal_newline_multiple(self):
        """Test conversion of multiple literal \\n strings."""
        text = "Line 1\\nLine 2\\nLine 3"
        assert normalize_newlines(text) == "Line 1\nLine 2\nLine 3"

    def test_excessive_newlines_cleanup(self):
        """Test cleanup of more than 2 consecutive newlines."""
        text = "Line 1\n\n\n\nLine 2"
        assert normalize_newlines(text) == "Line 1\n\nLine 2"

    def test_mixed_literal_and_actual_newlines(self):
        """Test handling of both literal \\n and actual newlines."""
        text = "Line 1\\nLine 2\nLine 3"
        assert normalize_newlines(text) == "Line 1\nLine 2\nLine 3"

    def test_no_newlines(self):
        """Test text without any newlines."""
        text = "Single line text"
        assert normalize_newlines(text) == "Single line text"

    def test_empty_string(self):
        """Test empty string input."""
        assert normalize_newlines("") == ""

    def test_none_input(self):
        """Test None input."""
        assert normalize_newlines(None) is None

    def test_real_world_example(self):
        """Test with real-world example from the issue."""
        text = (
            "¡El Paraíso Tulum tiene gastronomía increíble!\\n\\n"
            "1. *Itzamná* - Cocina maya\\n2. *Cenote Azul* - Vegetariana"
        )
        result = normalize_newlines(text)
        expected = (
            "¡El Paraíso Tulum tiene gastronomía increíble!\n\n"
            "1. *Itzamná* - Cocina maya\n2. *Cenote Azul* - Vegetariana"
        )
        assert result == expected


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

    def test_literal_newlines_in_message(self):
        """Test that literal \\n strings are converted to actual newlines."""
        text = "<message>Line 1\\nLine 2\\nLine 3</message>"
        result = parse_response(text)
        assert result == "Line 1\nLine 2\nLine 3"

    def test_literal_newlines_in_plain_text(self):
        """Test that literal \\n strings are converted in plain text (no tags)."""
        text = "Line 1\\nLine 2"
        result = parse_response(text)
        assert result == "Line 1\nLine 2"

    def test_real_world_spanish_response_with_literal_newlines(self):
        """Test real-world Spanish response with literal newlines."""
        text = (
            "<message>¡Hola! Trabajamos con cuatro hoteles:\\n\\n"
            "1. Grand Paraíso Resort\\n2. Paraíso Los Cabos\\n"
            "3. Paraíso Tulum\\n4. Paraíso Vallarta</message>"
        )
        result = parse_response(text)
        expected = (
            "¡Hola! Trabajamos con cuatro hoteles:\n\n"
            "1. Grand Paraíso Resort\n2. Paraíso Los Cabos\n"
            "3. Paraíso Tulum\n4. Paraíso Vallarta"
        )
        assert result == expected

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


class TestResponseParserProperties:
    """Property-based tests for response parser."""

    @given(st.text(min_size=1))
    def test_property_no_tags_returns_original(self, text):
        """Property: Text without tags should return unchanged (backward compatibility)."""
        # Filter out text that contains our special tags
        if (
            "<message>" not in text
            and "</message>" not in text
            and "<thinking>" not in text
            and "</thinking>" not in text
        ):
            result = parse_response(text)
            assert result == text

    @given(st.text(min_size=0, max_size=1000))
    def test_property_message_content_extracted(self, content):
        """Property: Content in message tags should be extracted."""
        text = f"<message>{content}</message>"
        result = parse_response(text)
        # Result should contain the content (stripped)
        assert result == content.strip()

    @given(st.text(min_size=0, max_size=1000), st.text(min_size=0, max_size=1000))
    def test_property_thinking_discarded(self, message_content, thinking_content):
        """Property: Message content should be extracted, thinking tags should be removed."""
        text = f"<message>{message_content}</message><thinking>{thinking_content}</thinking>"
        result = parse_response(text)

        # Result should equal the message content (stripped)
        assert result == message_content.strip()

        # Thinking tags themselves should not appear
        assert "<thinking>" not in result
        assert "</thinking>" not in result

    @given(st.lists(st.text(min_size=1, max_size=500), min_size=1, max_size=5))
    def test_property_multiple_messages_concatenated(self, messages):
        """Property: Multiple message blocks should be concatenated with double newlines."""
        text = "".join(f"<message>{msg}</message>" for msg in messages)
        result = parse_response(text)

        # All messages should appear in result
        for msg in messages:
            if msg.strip():
                assert msg.strip() in result

    @given(st.text(min_size=0, max_size=1000))
    def test_property_thinking_only_returns_empty(self, thinking_content):
        """Property: Text with only thinking tags should return empty string."""
        text = f"<thinking>{thinking_content}</thinking>"
        result = parse_response(text)
        assert result == ""

    @given(st.text(min_size=1, max_size=1000))
    def test_property_never_crashes(self, text):
        """Property: Parser should never crash regardless of input."""
        try:
            result = parse_response(text)
            # Should always return a string or None
            assert result is None or isinstance(result, str)
        except Exception as e:
            pytest.fail(f"Parser crashed with input: {text[:100]}... Error: {e}")

    @given(st.text(min_size=0, max_size=1000))
    def test_property_unclosed_message_extracts_content(self, content):
        """Property: Unclosed message tag should extract content after opening tag."""
        text = f"<message>{content}"
        result = parse_response(text)
        # Should extract the content (stripped)
        assert result == content.strip()

    @given(st.text(min_size=0, max_size=1000))
    def test_property_orphaned_closing_extracts_before(self, content):
        """Property: Orphaned closing tag should extract content before it."""
        text = f"{content}</message>"
        result = parse_response(text)
        # Should extract content before the closing tag
        assert result == content.strip()

    @given(st.text(min_size=0, max_size=500), st.text(min_size=0, max_size=500))
    def test_property_message_before_thinking_order(self, msg, think):
        """Property: Order of message and thinking shouldn't matter for extraction."""
        text1 = f"<message>{msg}</message><thinking>{think}</thinking>"
        text2 = f"<thinking>{think}</thinking><message>{msg}</message>"

        result1 = parse_response(text1)
        result2 = parse_response(text2)

        # Both should extract the same message content
        assert result1 == result2 == msg.strip()

    @given(st.text(min_size=0, max_size=1000))
    def test_property_whitespace_handling(self, content):
        """Property: Leading/trailing whitespace should be stripped from final result."""
        text = f"<message>{content}</message>"
        result = parse_response(text)

        # Result should not have leading/trailing whitespace
        if result:
            assert result == result.strip()

    @given(st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=0, max_size=1000))
    def test_property_unicode_handling(self, content):
        """Property: Parser should handle unicode content correctly."""
        text = f"<message>{content}</message>"
        result = parse_response(text)

        # Should extract unicode content
        assert result == content.strip()
