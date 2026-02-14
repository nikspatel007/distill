"""Tests for journal synthesizer (mocked subprocess)."""

import subprocess
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

from distill.journal.config import JournalConfig, JournalStyle
from distill.journal.context import DailyContext
from distill.journal.synthesizer import JournalSynthesizer, SynthesisError


def _make_context() -> DailyContext:
    return DailyContext(
        date=date(2026, 2, 5),
        total_sessions=2,
        total_duration_minutes=60.0,
        projects_worked=["distill"],
    )


class TestSynthesizer:
    """Tests for JournalSynthesizer."""

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_successful_synthesis(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="Today I worked on the Distill project...",
            stderr="",
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        result = synthesizer.synthesize(_make_context())

        assert "Distill" in result
        mock_run.assert_called_once()

        # Verify the command starts with claude -p
        call_args = mock_run.call_args
        cmd = call_args[0][0]
        assert cmd[0] == "claude"
        assert cmd[1] == "-p"

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_passes_model_flag(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Some prose", stderr=""
        )
        config = JournalConfig(model="claude-haiku-4-5-20251001")
        synthesizer = JournalSynthesizer(config)
        synthesizer.synthesize(_make_context())

        cmd = mock_run.call_args[0][0]
        assert "--model" in cmd
        assert "claude-haiku-4-5-20251001" in cmd

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_no_model_flag_by_default(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="Some prose", stderr=""
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        synthesizer.synthesize(_make_context())

        cmd = mock_run.call_args[0][0]
        assert "--model" not in cmd

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_cli_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="not found"):
            synthesizer.synthesize(_make_context())

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_cli_timeout(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="claude", timeout=120)
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="timed out"):
            synthesizer.synthesize(_make_context())

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_cli_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="API key invalid",
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="exited 1"):
            synthesizer.synthesize(_make_context())

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_os_error(self, mock_run):
        mock_run.side_effect = OSError("Permission denied")
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)

        with pytest.raises(SynthesisError, match="Failed to run"):
            synthesizer.synthesize(_make_context())

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_strips_output(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="\n  Some prose with whitespace  \n\n",
            stderr="",
        )
        config = JournalConfig()
        synthesizer = JournalSynthesizer(config)
        result = synthesizer.synthesize(_make_context())

        assert result == "Some prose with whitespace"

    @patch("distill.journal.synthesizer.subprocess.run")
    def test_uses_configured_timeout(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=0, stdout="prose", stderr=""
        )
        config = JournalConfig(claude_timeout=60)
        synthesizer = JournalSynthesizer(config)
        synthesizer.synthesize(_make_context())

        call_kwargs = mock_run.call_args[1]
        assert call_kwargs["timeout"] == 60
