"""Voice memory models — pure Pydantic v2 data types."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RuleCategory(StrEnum):
    """Category of a voice rule."""

    TONE = "tone"
    SPECIFICITY = "specificity"
    STRUCTURE = "structure"
    VOCABULARY = "vocabulary"
    FRAMING = "framing"


class VoiceRule(BaseModel):
    """A single learned voice rule."""

    id: str = Field(default_factory=lambda: f"v-{uuid.uuid4().hex[:8]}")
    rule: str
    confidence: float = 0.3
    source_count: int = 1
    category: RuleCategory
    examples: dict[str, str] | None = None

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.7:
            return "high"
        if self.confidence >= 0.4:
            return "medium"
        return "low"


class VoiceProfile(BaseModel):
    """Accumulated voice rules learned from editing history."""

    version: int = 1
    extracted_from: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    rules: list[VoiceRule] = Field(default_factory=list)
    processed_slugs: list[str] = Field(default_factory=list)

    def render_for_prompt(self, min_confidence: float = 0.5) -> str:
        """Render voice rules as markdown for LLM prompt injection."""
        filtered = [r for r in self.rules if r.confidence >= min_confidence]
        if not filtered:
            return ""

        lines = [
            "## Your Voice (learned from editing history)",
            "",
            "IMPORTANT: These rules reflect how the author actually writes, learned from",
            "their edits. Follow them precisely — they override generic style guidelines.",
            "",
        ]

        by_category: dict[RuleCategory, list[VoiceRule]] = {}
        for rule in filtered:
            by_category.setdefault(rule.category, []).append(rule)

        for cat in RuleCategory:
            cat_rules = by_category.get(cat, [])
            if not cat_rules:
                continue
            lines.append(f"### {cat.value.title()}")
            for r in sorted(cat_rules, key=lambda x: -x.confidence):
                lines.append(f"- {r.rule} (confidence: {r.confidence_label})")
            lines.append("")

        return "\n".join(lines)

    def prune(self, threshold: float = 0.1) -> int:
        """Remove rules below confidence threshold. Returns count pruned."""
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.confidence >= threshold]
        return before - len(self.rules)
