"""Tests for journal synthesizer (mocked LLM calls)."""

from datetime import date
from unittest.mock import patch

import pytest

from distill.journal.config import JournalConfig, JournalStyle
from distill.journal.context import DailyContext
from distill.journal.synthesizer import JournalSynthesizer, SynthesisError
from distill.llm import LLMError


def _make_context() -> DailyContext:
    return DailyContext(
        date=date(2026, 2, 5),
        total_sessions=2,
        total_duration_minutes=60.0,
        projects_worked=["distill"],
    )


class TestSynthesizer:
    """Tests for JournalSynthesizer."""

    @patch("distill.llm.call_claude")
    def test_successful_synthesis(self, mock_call):
        mock_call.return_value = "Today I worked on the Distill project..."
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        result = synthesizer.synthesize(_make_context())

        assert "Distill" in result
        mock_call.assert_called_once()

    @patch("distill.llm.call_claude")
    def test_passes_model_flag(self, mock_call):
        mock_call.return_value = "Some prose"
        config = JournalConfig(model="claude-haiku-4-5-20251001")
        synthesizer = JournalSynthesizer(config)
        synthesizer.synthesize(_make_context())

        _, kwargs = mock_call.call_args
        assert kwargs["model"] == "claude-haiku-4-5-20251001"

    @patch("distill.llm.call_claude")
    def test_no_model_flag_by_default(self, mock_call):
        mock_call.return_value = "Some prose"
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        synthesizer.synthesize(_make_context())

        _, kwargs = mock_call.call_args
        assert kwargs["model"] is None

    @patch("distill.llm.call_claude")
    def test_cli_not_found(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI not found — is 'claude' on the PATH?")
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="not found"):
            synthesizer.synthesize(_make_context())

    @patch("distill.llm.call_claude")
    def test_cli_timeout(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI timed out after 120s")
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="timed out"):
            synthesizer.synthesize(_make_context())

    @patch("distill.llm.call_claude")
    def test_cli_nonzero_exit(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI failed (exit 1): API key invalid")
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="exit 1"):
            synthesizer.synthesize(_make_context())

    @patch("distill.llm.call_claude")
    def test_llm_error_becomes_synthesis_error(self, mock_call):
        mock_call.side_effect = LLMError("Something went wrong")
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="Something went wrong"):
            synthesizer.synthesize(_make_context())

    @patch("distill.llm.call_claude")
    def test_returns_stripped_output(self, mock_call):
        mock_call.return_value = "Some prose with whitespace"
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        result = synthesizer.synthesize(_make_context())

        assert result == "Some prose with whitespace"

    @patch("distill.llm.call_claude")
    def test_uses_configured_timeout(self, mock_call):
        mock_call.return_value = "prose"
        config = JournalConfig(claude_timeout=60)
        synthesizer = JournalSynthesizer(config)
        synthesizer.synthesize(_make_context())

        _, kwargs = mock_call.call_args
        assert kwargs["timeout"] == 60
