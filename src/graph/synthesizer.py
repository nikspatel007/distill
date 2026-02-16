"""Context synthesis for knowledge graph — generates narrative context via LLM.

Follows the same ``claude -p`` subprocess pattern as
``JournalSynthesizer`` and ``BlogSynthesizer``.
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
from pathlib import Path
from typing import Any

from distill.graph.prompts import get_context_prompt

logger = logging.getLogger(__name__)

# Default timeout for claude CLI call (seconds)
_DEFAULT_TIMEOUT = 60

# Markers for the injected context block in CLAUDE.md
_CONTEXT_START = "<!-- DISTILL-CONTEXT-START -->"
_CONTEXT_END = "<!-- DISTILL-CONTEXT-END -->"
_MARKER_RE = re.compile(
    re.escape(_CONTEXT_START) + r".*?" + re.escape(_CONTEXT_END),
    re.DOTALL,
)


class ContextSynthesisError(Exception):
    """Raised when context synthesis fails."""


def synthesize_context(
    context_data: dict[str, Any],
    *,
    model: str | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> str:
    """Synthesize narrative context from gathered graph data.

    Parameters
    ----------
    context_data:
        Structured data from ``GraphQuery.gather_context_data()``.
    model:
        Optional model override for the Claude CLI call.
    timeout:
        Timeout in seconds for the subprocess call.

    Returns
    -------
    str
        Markdown context block ready for injection.

    Raises
    ------
    ContextSynthesisError
        If the CLI call fails or times out.
    """
    prompt = get_context_prompt(context_data)

    cmd: list[str] = ["claude", "-p"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)

    # Clear CLAUDECODE env var so claude CLI can run inside a Claude Code session
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    logger.debug("Calling Claude CLI for context synthesis")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as e:
        raise ContextSynthesisError(
            "Claude CLI not found — is 'claude' on the PATH?"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise ContextSynthesisError(
            f"Claude CLI timed out after {timeout}s"
        ) from e
    except OSError as e:
        raise ContextSynthesisError(f"Failed to run Claude CLI: {e}") from e

    if result.returncode != 0:
        err_text = result.stderr.strip() if result.stderr else ""
        raise ContextSynthesisError(
            f"Claude CLI exited {result.returncode}: {err_text}"
        )

    return result.stdout.strip()


def inject_context(context_md: str, claude_md_path: Path) -> None:
    """Write synthesized context into a CLAUDE.md file between markers.

    If the file already contains a ``<!-- DISTILL-CONTEXT-START -->`` block,
    it is replaced.  Otherwise the block is appended.

    Parameters
    ----------
    context_md:
        The markdown context block (output of ``synthesize_context``).
    claude_md_path:
        Path to the CLAUDE.md file to update.
    """
    block = f"{_CONTEXT_START}\n{context_md}\n{_CONTEXT_END}"

    if claude_md_path.exists():
        existing = claude_md_path.read_text()
        if _CONTEXT_START in existing:
            updated = _MARKER_RE.sub(block, existing)
        else:
            updated = existing.rstrip() + "\n\n" + block + "\n"
    else:
        updated = block + "\n"

    claude_md_path.write_text(updated)
