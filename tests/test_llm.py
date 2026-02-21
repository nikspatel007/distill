"""Tests for distill.llm — call_claude() and strip_json_fences()."""

from __future__ import annotations

import asyncio
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from distill.llm import LLMError, call_claude, strip_json_fences


# ---------------------------------------------------------------------------
# Helpers for Agent SDK mocks
# ---------------------------------------------------------------------------


def _make_assistant_message(text: str) -> MagicMock:
    """Create a mock AssistantMessage with a single TextBlock."""
    from claude_agent_sdk import AssistantMessage, TextBlock

    block = TextBlock(text=text)
    return AssistantMessage(content=[block], model="claude-sonnet-4-5-20250929")


def _make_result_message() -> MagicMock:
    """Create a mock ResultMessage."""
    from claude_agent_sdk import ResultMessage

    return ResultMessage(
        subtype="success",
        duration_ms=100,
        duration_api_ms=80,
        is_error=False,
        num_turns=1,
        session_id="test-session",
        total_cost_usd=0.01,
    )


async def _async_iter_messages(*messages):
    """Create an async iterator yielding the given messages."""
    for msg in messages:
        yield msg


# ---------------------------------------------------------------------------
# call_claude — Agent SDK path
# ---------------------------------------------------------------------------


class TestCallClaudeAgentSDK:
    """Tests for the Agent SDK path in call_claude()."""

    @patch("distill.llm._agent_query")
    def test_sdk_returns_text(self, mock_query: MagicMock) -> None:
        """Agent SDK path returns response text."""
        mock_query.return_value = _async_iter_messages(
            _make_assistant_message("  Hello from SDK  "),
            _make_result_message(),
        )

        result = call_claude("system prompt", "user prompt")
        assert result == "Hello from SDK"

    @patch("distill.llm._agent_query")
    def test_sdk_passes_model(self, mock_query: MagicMock) -> None:
        """Agent SDK path passes model to ClaudeAgentOptions."""
        mock_query.return_value = _async_iter_messages(
            _make_assistant_message("ok"),
            _make_result_message(),
        )

        call_claude("sys", "usr", model="haiku")

        # Verify the options passed to query()
        _args, kwargs = mock_query.call_args
        options = kwargs.get("options") or _args[0] if _args else kwargs.get("options")
        # query() is called as query(prompt=..., options=...)
        assert mock_query.call_count == 1
        call_kwargs = mock_query.call_args[1] if mock_query.call_args[1] else {}
        if "options" in call_kwargs:
            assert call_kwargs["options"].model == "haiku"

    @patch("distill.llm._agent_query")
    def test_sdk_passes_none_model(self, mock_query: MagicMock) -> None:
        """Agent SDK path passes None model when not specified."""
        mock_query.return_value = _async_iter_messages(
            _make_assistant_message("ok"),
            _make_result_message(),
        )

        call_claude("sys", "usr", model=None)
        call_kwargs = mock_query.call_args[1]
        if "options" in call_kwargs:
            assert call_kwargs["options"].model is None

    @patch("distill.llm._agent_query")
    def test_sdk_passes_system_prompt(self, mock_query: MagicMock) -> None:
        """Agent SDK path passes system_prompt to options."""
        mock_query.return_value = _async_iter_messages(
            _make_assistant_message("ok"),
            _make_result_message(),
        )

        call_claude("My system prompt", "usr")
        call_kwargs = mock_query.call_args[1]
        if "options" in call_kwargs:
            assert call_kwargs["options"].system_prompt == "My system prompt"

    @patch("distill.llm._agent_query")
    def test_sdk_passes_user_prompt(self, mock_query: MagicMock) -> None:
        """Agent SDK path passes user_prompt as prompt."""
        mock_query.return_value = _async_iter_messages(
            _make_assistant_message("ok"),
            _make_result_message(),
        )

        call_claude("sys", "My user prompt")
        call_kwargs = mock_query.call_args[1]
        assert call_kwargs["prompt"] == "My user prompt"

    @patch("distill.llm._agent_query")
    def test_sdk_concatenates_multiple_text_blocks(self, mock_query: MagicMock) -> None:
        """Agent SDK path concatenates text from multiple blocks."""
        from claude_agent_sdk import AssistantMessage, TextBlock

        msg = AssistantMessage(
            content=[TextBlock(text="Hello "), TextBlock(text="world")],
            model="claude-sonnet-4-5-20250929",
        )
        mock_query.return_value = _async_iter_messages(msg, _make_result_message())

        result = call_claude("sys", "usr")
        assert result == "Hello world"

    @patch("distill.llm._agent_query")
    def test_sdk_empty_response_raises_llm_error(self, mock_query: MagicMock) -> None:
        """Agent SDK path raises LLMError on empty response."""
        mock_query.return_value = _async_iter_messages(_make_result_message())

        with pytest.raises(LLMError, match="empty response"):
            call_claude("sys", "usr")

    @patch("distill.llm._agent_query")
    def test_sdk_exception_raises_llm_error(self, mock_query: MagicMock) -> None:
        """Agent SDK exceptions are wrapped in LLMError."""

        async def _failing_iter(**kwargs):
            raise RuntimeError("SDK boom")
            yield  # noqa: unreachable — makes this an async generator

        mock_query.return_value = _failing_iter()

        with pytest.raises(LLMError, match="Agent SDK failed"):
            call_claude("sys", "usr", label="test-label")

    @patch("distill.llm._agent_query")
    def test_sdk_exception_includes_label(self, mock_query: MagicMock) -> None:
        """LLMError from SDK includes the label."""

        async def _failing_iter(**kwargs):
            raise RuntimeError("boom")
            yield  # noqa

        mock_query.return_value = _failing_iter()

        with pytest.raises(LLMError, match="label=my-label"):
            call_claude("sys", "usr", label="my-label")

    @patch("distill.llm._HAS_AGENT_SDK", False)
    @patch("distill.llm.subprocess.run")
    def test_falls_back_to_subprocess_when_no_sdk(self, mock_run: MagicMock) -> None:
        """Falls back to subprocess when Agent SDK is not installed."""
        mock_run.return_value = MagicMock(returncode=0, stdout="from CLI", stderr="")

        result = call_claude("sys", "usr")
        assert result == "from CLI"
        mock_run.assert_called_once()

    @patch.dict("os.environ", {"DISTILL_USE_CLI": "1"})
    @patch("distill.llm.subprocess.run")
    def test_distill_use_cli_forces_subprocess(self, mock_run: MagicMock) -> None:
        """DISTILL_USE_CLI=1 forces subprocess path even with SDK available."""
        mock_run.return_value = MagicMock(returncode=0, stdout="from CLI", stderr="")

        result = call_claude("sys", "usr")
        assert result == "from CLI"
        mock_run.assert_called_once()

    @patch("distill.llm._agent_query")
    def test_sdk_uses_bypass_permissions(self, mock_query: MagicMock) -> None:
        """Agent SDK path uses bypassPermissions mode."""
        mock_query.return_value = _async_iter_messages(
            _make_assistant_message("ok"),
            _make_result_message(),
        )

        call_claude("sys", "usr")
        call_kwargs = mock_query.call_args[1]
        if "options" in call_kwargs:
            assert call_kwargs["options"].permission_mode == "bypassPermissions"

    @patch("distill.llm._agent_query")
    def test_sdk_uses_no_tools(self, mock_query: MagicMock) -> None:
        """Agent SDK path uses empty allowed_tools (text-only)."""
        mock_query.return_value = _async_iter_messages(
            _make_assistant_message("ok"),
            _make_result_message(),
        )

        call_claude("sys", "usr")
        call_kwargs = mock_query.call_args[1]
        if "options" in call_kwargs:
            assert call_kwargs["options"].allowed_tools == []


# ---------------------------------------------------------------------------
# call_claude — subprocess path (forced via _HAS_AGENT_SDK=False)
# ---------------------------------------------------------------------------


@patch("distill.llm._HAS_AGENT_SDK", False)
class TestCallClaudeSubprocess:
    """Tests for the subprocess fallback path in call_claude()."""

    @patch("distill.llm.subprocess.run")
    def test_successful_call(self, mock_run: MagicMock) -> None:
        """Successful subprocess returns stripped stdout."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="  Hello from Claude  \n",
            stderr="",
        )
        result = call_claude("system prompt", "user prompt")
        assert result == "Hello from Claude"

        # Verify the command line
        args, kwargs = mock_run.call_args
        assert args[0] == ["claude", "-p"]
        assert kwargs["input"] == "system prompt\n\nuser prompt"
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["timeout"] == 120

    @patch("distill.llm.subprocess.run")
    def test_model_parameter(self, mock_run: MagicMock) -> None:
        """When model is provided, --model flag is added."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ok", stderr=""
        )
        call_claude("sys", "usr", model="haiku")

        args, _kwargs = mock_run.call_args
        assert args[0] == ["claude", "-p", "--model", "haiku"]

    @patch("distill.llm.subprocess.run")
    def test_no_model_parameter(self, mock_run: MagicMock) -> None:
        """When model is None, no --model flag."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ok", stderr=""
        )
        call_claude("sys", "usr", model=None)

        args, _kwargs = mock_run.call_args
        assert args[0] == ["claude", "-p"]

    @patch("distill.llm.subprocess.run")
    def test_custom_timeout(self, mock_run: MagicMock) -> None:
        """Custom timeout is forwarded to subprocess.run."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ok", stderr=""
        )
        call_claude("sys", "usr", timeout=300)

        _args, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 300

    @patch("distill.llm.subprocess.run")
    def test_file_not_found_raises_llm_error(self, mock_run: MagicMock) -> None:
        """FileNotFoundError from subprocess is wrapped in LLMError."""
        mock_run.side_effect = FileNotFoundError("claude not found")

        with pytest.raises(LLMError, match="Claude CLI not found"):
            call_claude("sys", "usr", label="test-label")

    @patch("distill.llm.subprocess.run")
    def test_file_not_found_includes_label(self, mock_run: MagicMock) -> None:
        """LLMError from FileNotFoundError includes the label."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(LLMError, match="label=my-label"):
            call_claude("sys", "usr", label="my-label")

    @patch("distill.llm.subprocess.run")
    def test_file_not_found_chains_cause(self, mock_run: MagicMock) -> None:
        """LLMError from FileNotFoundError chains the original exception."""
        original = FileNotFoundError("original")
        mock_run.side_effect = original

        with pytest.raises(LLMError) as exc_info:
            call_claude("sys", "usr")
        assert exc_info.value.__cause__ is original

    @patch("distill.llm.subprocess.run")
    def test_timeout_raises_llm_error(self, mock_run: MagicMock) -> None:
        """TimeoutExpired from subprocess is wrapped in LLMError."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["claude", "-p"], timeout=120
        )

        with pytest.raises(LLMError, match="timed out after 120s"):
            call_claude("sys", "usr", timeout=120)

    @patch("distill.llm.subprocess.run")
    def test_timeout_includes_label(self, mock_run: MagicMock) -> None:
        """LLMError from TimeoutExpired includes the label."""
        mock_run.side_effect = subprocess.TimeoutExpired(
            cmd=["claude", "-p"], timeout=60
        )

        with pytest.raises(LLMError, match="label=generation"):
            call_claude("sys", "usr", timeout=60, label="generation")

    @patch("distill.llm.subprocess.run")
    def test_timeout_chains_cause(self, mock_run: MagicMock) -> None:
        """LLMError from TimeoutExpired chains the original exception."""
        original = subprocess.TimeoutExpired(cmd=["claude"], timeout=30)
        mock_run.side_effect = original

        with pytest.raises(LLMError) as exc_info:
            call_claude("sys", "usr", timeout=30)
        assert exc_info.value.__cause__ is original

    @patch("distill.llm.subprocess.run")
    def test_nonzero_exit_raises_llm_error(self, mock_run: MagicMock) -> None:
        """Non-zero exit code is wrapped in LLMError."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="something went wrong"
        )

        with pytest.raises(LLMError, match="exit 1"):
            call_claude("sys", "usr")

    @patch("distill.llm.subprocess.run")
    def test_nonzero_exit_includes_stderr(self, mock_run: MagicMock) -> None:
        """LLMError for non-zero exit includes stderr content."""
        mock_run.return_value = MagicMock(
            returncode=2, stdout="", stderr="detailed error message"
        )

        with pytest.raises(LLMError, match="detailed error message"):
            call_claude("sys", "usr")

    @patch("distill.llm.subprocess.run")
    def test_nonzero_exit_includes_label(self, mock_run: MagicMock) -> None:
        """LLMError for non-zero exit includes the label."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="err"
        )

        with pytest.raises(LLMError, match="label=blog"):
            call_claude("sys", "usr", label="blog")

    @patch("distill.llm.subprocess.run")
    def test_nonzero_exit_truncates_long_stderr(self, mock_run: MagicMock) -> None:
        """Stderr in LLMError is truncated to 500 chars."""
        long_stderr = "Z" * 1000
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr=long_stderr
        )

        with pytest.raises(LLMError) as exc_info:
            call_claude("sys", "usr")
        msg = str(exc_info.value)
        z_count = msg.count("Z")
        assert z_count == 500

    @patch("distill.llm.subprocess.run")
    def test_claudecode_env_filtered(self, mock_run: MagicMock) -> None:
        """CLAUDECODE is removed from the environment passed to subprocess."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ok", stderr=""
        )

        with patch.dict("os.environ", {"CLAUDECODE": "1", "HOME": "/home/test"}, clear=False):
            call_claude("sys", "usr")

        _args, kwargs = mock_run.call_args
        env = kwargs["env"]
        assert "CLAUDECODE" not in env
        assert "HOME" in env

    @patch("distill.llm.subprocess.run")
    def test_env_without_claudecode_unchanged(self, mock_run: MagicMock) -> None:
        """When CLAUDECODE is not set, env still passes through normally."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="ok", stderr=""
        )

        with patch.dict("os.environ", {"HOME": "/home/test"}, clear=True):
            call_claude("sys", "usr")

        _args, kwargs = mock_run.call_args
        env = kwargs["env"]
        assert "CLAUDECODE" not in env
        assert env.get("HOME") == "/home/test"

    @patch("distill.llm.subprocess.run")
    def test_prompt_concatenation(self, mock_run: MagicMock) -> None:
        """System and user prompts are concatenated with double newline."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="response", stderr=""
        )
        call_claude("SYSTEM", "USER")

        _args, kwargs = mock_run.call_args
        assert kwargs["input"] == "SYSTEM\n\nUSER"

    @patch("distill.llm.subprocess.run")
    def test_default_label(self, mock_run: MagicMock) -> None:
        """Default label is 'synthesis'."""
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(LLMError, match="label=synthesis"):
            call_claude("sys", "usr")


# ---------------------------------------------------------------------------
# strip_json_fences
# ---------------------------------------------------------------------------


class TestStripJsonFences:
    """Tests for the strip_json_fences() function."""

    def test_plain_json_object(self) -> None:
        """Plain JSON object is returned as-is."""
        text = '{"key": "value"}'
        assert strip_json_fences(text) == '{"key": "value"}'

    def test_plain_json_with_whitespace(self) -> None:
        """Leading/trailing whitespace is stripped."""
        text = '  {"key": "value"}  '
        assert strip_json_fences(text) == '{"key": "value"}'

    def test_json_fenced_block(self) -> None:
        """```json fenced block is unwrapped."""
        text = '```json\n{"key": "value"}\n```'
        assert strip_json_fences(text) == '{"key": "value"}'

    def test_generic_fenced_block(self) -> None:
        """``` fenced block (no language) is unwrapped."""
        text = '```\n{"key": "value"}\n```'
        assert strip_json_fences(text) == '{"key": "value"}'

    def test_fenced_block_with_surrounding_text(self) -> None:
        """Fenced block with text before/after still extracts JSON."""
        text = 'Here is the JSON:\n```json\n{"a": 1}\n```\nDone.'
        assert strip_json_fences(text) == '{"a": 1}'

    def test_array_json(self) -> None:
        """JSON array is returned correctly."""
        text = '[{"a": 1}, {"b": 2}]'
        assert strip_json_fences(text) == '[{"a": 1}, {"b": 2}]'

    def test_array_json_fenced(self) -> None:
        """Fenced JSON array is unwrapped."""
        text = '```json\n[1, 2, 3]\n```'
        assert strip_json_fences(text) == '[1, 2, 3]'

    def test_mixed_content_with_json_object(self) -> None:
        """Text before/after a raw JSON object — object is extracted."""
        text = 'Here is the result: {"title": "Test"} end'
        assert strip_json_fences(text) == '{"title": "Test"}'

    def test_mixed_content_with_json_array(self) -> None:
        """Text before/after a raw JSON array — array is extracted."""
        text = 'Output: [1, 2, 3] done'
        assert strip_json_fences(text) == '[1, 2, 3]'

    def test_no_json_returns_original(self) -> None:
        """Text with no JSON delimiters returns the (stripped) original."""
        text = "Just plain text"
        assert strip_json_fences(text) == "Just plain text"

    def test_brace_before_bracket(self) -> None:
        """When { appears before [, object is extracted."""
        text = 'prefix {"a": [1,2]} suffix'
        assert strip_json_fences(text) == '{"a": [1,2]}'

    def test_bracket_before_brace(self) -> None:
        """When [ appears before {, array is extracted."""
        text = 'prefix [{"a": 1}] suffix'
        assert strip_json_fences(text) == '[{"a": 1}]'

    def test_fenced_takes_priority_over_raw(self) -> None:
        """Fenced block is preferred even if raw JSON also exists outside."""
        text = '{"outside": true}\n```json\n{"inside": true}\n```'
        assert strip_json_fences(text) == '{"inside": true}'

    def test_multiline_fenced_json(self) -> None:
        """Multi-line fenced JSON is handled."""
        text = '```json\n{\n  "key": "value",\n  "num": 42\n}\n```'
        result = strip_json_fences(text)
        assert '"key": "value"' in result
        assert '"num": 42' in result

    def test_empty_string(self) -> None:
        """Empty string returns empty string."""
        assert strip_json_fences("") == ""

    def test_only_whitespace(self) -> None:
        """Whitespace-only string returns empty string."""
        assert strip_json_fences("   \n  ") == ""

    def test_lone_brace_no_close(self) -> None:
        """A lone { with no matching } returns the stripped text."""
        text = "prefix { but no close"
        assert strip_json_fences(text) == "prefix { but no close"

    def test_lone_bracket_no_close(self) -> None:
        """A lone [ with no matching ] returns the stripped text."""
        text = "prefix [ but no close"
        assert strip_json_fences(text) == "prefix [ but no close"

    def test_close_before_open_brace(self) -> None:
        """} before { — end < start so falls through."""
        text = "} some text {"
        assert strip_json_fences(text) == "} some text {"


# ---------------------------------------------------------------------------
# LLMError
# ---------------------------------------------------------------------------


class TestLLMError:
    """Tests for the LLMError exception class."""

    def test_is_exception(self) -> None:
        """LLMError is an Exception subclass."""
        assert issubclass(LLMError, Exception)

    def test_message(self) -> None:
        """LLMError preserves message."""
        err = LLMError("test message")
        assert str(err) == "test message"
