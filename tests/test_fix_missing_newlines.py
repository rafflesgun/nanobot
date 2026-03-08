"""Tests for AgentLoop._fix_missing_newlines()."""

from __future__ import annotations

import re


# ── Copy of the static method under test so we can run without heavy deps ──
def _fix_missing_newlines(text: str | None) -> str | None:
    """Heuristically insert missing newlines (copy from loop.py for testing)."""
    if not text:
        return text
    if text.count("\n") >= max(1, len(text) // 300):
        return text
    text = re.sub(r"(?<=[.!?:;])\s+(?=- )", "\n", text)
    text = re.sub(r" (?=- [A-Z\u0400-\u04FF\u4e00-\u9fff])", "\n", text)
    text = re.sub(r"(?<=[.!?:;])\s+(?=\d{1,3}[.)]\s)", "\n", text)
    text = re.sub(r"(?<=[.!?])\s+(?=\*\*)", "\n", text)
    text = re.sub(r"(?<=[.!?])\s+(?=#{1,6}\s)", "\n", text)
    return text


fix = _fix_missing_newlines


class TestPassthrough:
    """Already-formatted text should pass through unchanged."""

    def test_none(self):
        assert fix(None) is None

    def test_empty(self):
        assert fix("") == ""

    def test_already_has_newlines(self):
        text = "Line 1\nLine 2\nLine 3\n- bullet\n- bullet 2"
        assert fix(text) == text

    def test_short_text_no_patterns(self):
        text = "Hello, how are you today?"
        assert fix(text) == text


class TestBulletLists:
    """Bullet items preceded by sentence-ending punctuation should get newlines."""

    def test_bullets_after_colon(self):
        text = "Here are the results: - Item one - Item two - Item three"
        result = fix(text)
        assert "results:\n- Item one" in result

    def test_bullets_after_period(self):
        text = "I found three things. - First thing. - Second thing. - Third thing."
        result = fix(text)
        assert "things.\n- First" in result

    def test_no_false_positive_on_hyphenated_words(self):
        text = "This is a well-known fact about state-of-the-art systems."
        result = fix(text)
        assert result == text  # No changes


class TestNumberedLists:
    """Numbered items should get newlines."""

    def test_numbered_after_colon(self):
        text = "Steps to follow: 1. Do this 2. Do that 3. Done"
        result = fix(text)
        assert "follow:\n1. Do this" in result

    def test_numbered_with_parens(self):
        text = "Three options: 1) Option A. 2) Option B. 3) Option C."
        result = fix(text)
        assert "options:\n1) Option A" in result


class TestBoldHeaders:
    """**Bold header**: patterns should get newlines."""

    def test_bold_headers_after_period(self):
        text = "Overview complete. **Name**: Bot. **Status**: Online. **Version**: 1.0."
        result = fix(text)
        assert "complete.\n**Name**" in result
        assert "Bot.\n**Status**" in result

    def test_bold_headers_after_exclamation(self):
        text = "Great news! **Feature**: Now available."
        result = fix(text)
        assert "news!\n**Feature**" in result


class TestMarkdownHeaders:
    """# Markdown headers should get newlines."""

    def test_h2_after_period(self):
        text = "Introduction done. ## Next Section"
        result = fix(text)
        assert "done.\n## Next Section" in result


class TestDensityGuard:
    """Text with sufficient newlines should not be modified."""

    def test_dense_newlines_no_change(self):
        # ~60 chars with 2 newlines -> density is fine -> no changes
        text = "Line one here.\n- Bullet one.\n- Bullet two. - Bullet three."
        result = fix(text)
        assert result == text


class TestRealWorldExamples:
    """Patterns observed from the minimax-m2.5 model output."""

    def test_metadata_style_response(self):
        text = (
            "Here is the information you requested. "
            "**Name**: Nanobot. **Version**: 2.1. **Status**: Active. "
            "**Features**: - Multi-channel support - Tool calling - Memory"
        )
        result = fix(text)
        assert "\n**Name**" in result
        assert "\n**Version**" in result
        assert "\n- Multi-channel" in result

    def test_bullet_list_run_together(self):
        text = (
            "I can help with the following: "
            "- Answering questions - Searching the web "
            "- Writing code - Managing files"
        )
        result = fix(text)
        assert "following:\n- Answering" in result
        # Capital letters after " - " trigger newline insertion
        assert "\n- Searching" in result
        assert "\n- Writing" in result
        assert "\n- Managing" in result
