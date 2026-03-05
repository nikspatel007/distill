"""Models for the daily reading brief."""
from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from distill.brief.connection import ConnectionInsight
    from distill.brief.learning import TopicTrend


class ReadingHighlight(BaseModel):
    """A single highlight from today's reading."""
    title: str
    source: str  # site name or author
    url: str = ""
    summary: str  # 2-3 sentence summary of why this matters
    tags: list[str] = Field(default_factory=list)


class DraftPost(BaseModel):
    """An auto-generated social media draft."""
    platform: str  # "linkedin" or "x"
    content: str
    char_count: int = 0
    source_highlights: list[str] = Field(default_factory=list)  # highlight titles used


class ReadingBrief(BaseModel):
    """The daily reading brief - top highlights + draft posts."""
    date: str
    generated_at: str = ""
    highlights: list[ReadingHighlight] = Field(default_factory=list)
    drafts: list[DraftPost] = Field(default_factory=list)
    connection: ConnectionInsight | None = None
    learning_pulse: list[TopicTrend] = Field(default_factory=list)


# Rebuild model to resolve forward references from TYPE_CHECKING imports.
# Import into module globals so Pydantic can find the types during rebuild.
from distill.brief.connection import ConnectionInsight as ConnectionInsight  # noqa: E402
from distill.brief.learning import TopicTrend as TopicTrend  # noqa: E402

ReadingBrief.model_rebuild()
