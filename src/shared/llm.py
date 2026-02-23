"""Shared LLM calling utilities.

Centralizes all Claude invocations with three backends:
1. Anthropic API (preferred — uses ANTHROPIC_API_KEY)
2. Agent SDK (fallback — if installed)
3. Subprocess ``claude -p`` (last resort)
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic API (preferred)
# ---------------------------------------------------------------------------

try:
    import anthropic

    _HAS_ANTHROPIC = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    _HAS_ANTHROPIC = False

# ---------------------------------------------------------------------------
# Agent SDK (fallback)
# ---------------------------------------------------------------------------

try:
    from claude_agent_sdk import (
        AssistantMessage as _AssistantMessage,
        ClaudeAgentOptions as _AgentOptions,
        ResultMessage as _ResultMessage,
        TextBlock as _TextBlock,
    )
    from claude_agent_sdk import query as _agent_query

    _HAS_AGENT_SDK = True
except ImportError:
    _HAS_AGENT_SDK = False


class LLMError(Exception):
    """Base error for LLM calls."""


# ---------------------------------------------------------------------------
# Model name mapping
# ---------------------------------------------------------------------------

_MODEL_MAP: dict[str, str] = {
    "sonnet": "claude-sonnet-4-6",
    "haiku": "claude-haiku-4-5-20251001",
    "opus": "claude-opus-4-6",
}

_DEFAULT_MODEL = "claude-sonnet-4-6"


def _resolve_model(model: str | None) -> str:
    """Resolve a short model name to an API model ID."""
    if model is None:
        return _DEFAULT_MODEL
    return _MODEL_MAP.get(model, model)


# ---------------------------------------------------------------------------
# Internal: Anthropic API
# ---------------------------------------------------------------------------


def _call_anthropic_api(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    timeout: int = 120,
    label: str = "synthesis",
) -> str:
    """Call Claude via the Anthropic API."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise LLMError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key, timeout=timeout)  # type: ignore[union-attr]
    resolved_model = _resolve_model(model)

    logger.debug("Calling Anthropic API model=%s (%s)", resolved_model, label)

    # When user_prompt is empty, use system_prompt as the user message
    # (backwards compat with callers that put everything in system_prompt)
    if user_prompt.strip():
        sys = system_prompt
        usr = user_prompt
    else:
        sys = ""
        usr = system_prompt

    kwargs: dict[str, object] = {
        "model": resolved_model,
        "max_tokens": 16384,
        "messages": [{"role": "user", "content": usr}],
    }
    if sys.strip():
        kwargs["system"] = sys

    response = client.messages.create(**kwargs)  # type: ignore[arg-type]

    text_parts: list[str] = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)

    result = "".join(text_parts).strip()
    if not result:
        raise LLMError(f"Anthropic API returned empty response (label={label})")
    return result


# ---------------------------------------------------------------------------
# Internal: Agent SDK async helper
# ---------------------------------------------------------------------------


async def _call_agent_sdk(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    label: str = "synthesis",
) -> str:
    """Call Claude via the Agent SDK and return the response text."""
    options = _AgentOptions(
        system_prompt=system_prompt,
        model=model,  # Agent SDK handles short names: "sonnet", "haiku", "opus"
        max_turns=1,
        allowed_tools=[],  # No tools — just text generation
        permission_mode="bypassPermissions",
    )

    text_parts: list[str] = []
    async for message in _agent_query(prompt=user_prompt, options=options):
        if isinstance(message, _AssistantMessage):
            for block in message.content:
                if isinstance(block, _TextBlock):
                    text_parts.append(block.text)

    result = "".join(text_parts).strip()
    if not result:
        raise LLMError(f"Agent SDK returned empty response (label={label})")
    return result


# ---------------------------------------------------------------------------
# Internal: subprocess fallback
# ---------------------------------------------------------------------------


def _call_subprocess(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    timeout: int = 120,
    label: str = "synthesis",
) -> str:
    """Call Claude via subprocess (``claude -p``) fallback."""
    cmd = ["claude", "-p"]
    if model:
        cmd.extend(["--model", model])

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    # Filter CLAUDECODE env var to prevent recursive Claude invocations
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    logger.debug("Calling Claude CLI subprocess (%s)", label)

    try:
        result = subprocess.run(
            cmd,
            input=full_prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise LLMError(
            f"Claude CLI not found — is 'claude' on the PATH? (label={label})"
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise LLMError(f"Claude CLI timed out after {timeout}s (label={label})") from exc

    if result.returncode != 0:
        raise LLMError(
            f"Claude CLI failed (exit {result.returncode}, label={label}): {result.stderr[:500]}"
        )

    return result.stdout.strip()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def call_claude(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    timeout: int = 120,
    label: str = "synthesis",
) -> str:
    """Call Claude and return the response text.

    Priority order:
    1. Anthropic API (if ANTHROPIC_API_KEY is set)
    2. Agent SDK (if installed, unless DISTILL_USE_CLI=1)
    3. Subprocess ``claude -p`` (last resort)

    Args:
        system_prompt: System prompt for the LLM.
        user_prompt: User/content prompt.
        model: Optional model override (e.g. "sonnet", "haiku", "opus").
        timeout: Timeout in seconds.
        label: Label for logging.

    Returns:
        The LLM response text (stripped).

    Raises:
        LLMError: On any failure.
    """
    use_cli = os.environ.get("DISTILL_USE_CLI", "").strip() == "1"

    # 1. Anthropic API (preferred)
    if _HAS_ANTHROPIC and not use_cli:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if api_key:
            try:
                return _call_anthropic_api(
                    system_prompt,
                    user_prompt,
                    model=model,
                    timeout=timeout,
                    label=label,
                )
            except LLMError:
                raise
            except Exception as exc:
                raise LLMError(f"Anthropic API failed (label={label}): {exc}") from exc

    # 2. Agent SDK (fallback)
    if _HAS_AGENT_SDK and not use_cli:
        logger.debug("Calling Agent SDK (%s)", label)
        try:
            return asyncio.run(
                _call_agent_sdk(
                    system_prompt,
                    user_prompt,
                    model=model,
                    label=label,
                )
            )
        except LLMError:
            raise
        except Exception as exc:
            raise LLMError(f"Agent SDK failed (label={label}): {exc}") from exc

    # 3. Subprocess (last resort)
    return _call_subprocess(
        system_prompt,
        user_prompt,
        model=model,
        timeout=timeout,
        label=label,
    )


# ---------------------------------------------------------------------------
# JSON output helpers
# ---------------------------------------------------------------------------

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", re.DOTALL)


def strip_json_fences(text: str) -> str:
    """Strip markdown code fences from LLM JSON output.

    Handles Claude's tendency to wrap JSON in ```json ... ``` blocks.
    """
    text = text.strip()
    match = _JSON_FENCE_RE.search(text)
    if match:
        return match.group(1).strip()
    # Try to find raw JSON — use whichever delimiter appears first
    brace_start = text.find("{")
    bracket_start = text.find("[")

    # Determine which JSON structure appears first
    candidates: list[tuple[int, str, str]] = []
    if brace_start != -1:
        candidates.append((brace_start, "{", "}"))
    if bracket_start != -1:
        candidates.append((bracket_start, "[", "]"))

    # Sort by position — earliest delimiter wins
    candidates.sort()

    for _pos, start_char, end_char in candidates:
        start = text.find(start_char)
        end = text.rfind(end_char)
        if start != -1 and end > start:
            return text[start : end + 1]

    return text
