"""LLM synthesis for intake content."""

from __future__ import annotations

import logging

from distill.intake.config import IntakeConfig
from distill.intake.context import DailyIntakeContext
from distill.intake.prompts import get_daily_intake_prompt, get_unified_intake_prompt
from distill.llm import LLMError, call_claude

logger = logging.getLogger(__name__)


class IntakeSynthesisError(Exception):
    """Raised when intake LLM synthesis fails."""


class IntakeSynthesizer:
    """Synthesizes intake content via Claude CLI."""

    def __init__(self, config: IntakeConfig) -> None:
        self._config = config

    def synthesize_daily(self, context: DailyIntakeContext, memory_context: str = "") -> str:
        """Transform daily intake context into a research digest.

        Uses the unified prompt when sessions or seeds are present,
        falling back to the standard reading-only prompt otherwise.

        Args:
            context: The assembled daily intake context.
            memory_context: Rendered working memory for continuity.

        Returns:
            Synthesized prose as markdown.
        """
        if context.has_sessions or context.has_seeds:
            system_prompt = get_unified_intake_prompt(
                target_word_count=self._config.target_word_count,
                memory_context=memory_context,
                has_sessions=context.has_sessions,
                has_seeds=context.has_seeds,
                user_name=self._config.user_name,
                user_role=self._config.user_role,
            )
        else:
            system_prompt = get_daily_intake_prompt(
                target_word_count=self._config.target_word_count,
                memory_context=memory_context,
                user_name=self._config.user_name,
                user_role=self._config.user_role,
            )
        user_prompt = context.combined_text
        return self._call_claude(system_prompt, user_prompt, f"intake {context.date.isoformat()}")

    def _call_claude(self, system_prompt: str, user_prompt: str, label: str) -> str:
        """Call Claude CLI with prompt piped via stdin.

        Delegates to the shared call_claude() and translates LLMError
        to IntakeSynthesisError.
        """
        try:
            return call_claude(
                system_prompt,
                user_prompt,
                model=self._config.model,
                timeout=self._config.claude_timeout,
                label=label,
            )
        except LLMError as exc:
            raise IntakeSynthesisError(str(exc)) from exc
