"""Shared LLM calling utilities.

Centralizes all subprocess-based Claude CLI invocations and common
LLM output parsing helpers.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Base error for LLM calls."""


def call_claude(
    system_prompt: str,
    user_prompt: str,
    *,
    model: str | None = None,
    timeout: int = 120,
    label: str = "synthesis",
) -> str:
    """Call Claude CLI and return the response text.

    Args:
        system_prompt: System prompt for the LLM.
        user_prompt: User/content prompt.
        model: Optional model override (e.g. "sonnet", "haiku").
        timeout: Subprocess timeout in seconds.
        label: Label for logging.

    Returns:
        The LLM response text (stripped).

    Raises:
        LLMError: On any failure (not found, timeout, non-zero exit).
    """
    cmd = ["claude", "-p"]
    if model:
        cmd.extend(["--model", model])

    full_prompt = f"{system_prompt}\n\n{user_prompt}"

    # Filter CLAUDECODE env var to prevent recursive Claude invocations
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    logger.debug("Calling Claude CLI (%s)", label)

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
            f"Claude CLI failed (exit {result.returncode}, label={label}): "
            f"{result.stderr[:500]}"
        )

    return result.stdout.strip()


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
