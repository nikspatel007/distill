"""Models for the daily reading brief."""
from __future__ import annotations

from pydantic import BaseModel, Field


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
