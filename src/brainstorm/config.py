"""BrainstormConfig model for idea-generation pipeline settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BrainstormConfig(BaseModel):
    """Configuration for the brainstorm pipeline.

    Controls which sources to scan and what topics to focus on.
    """

    pillars: list[str] = Field(default_factory=list)
    followed_people: list[str] = Field(default_factory=list)
    manual_links: list[str] = Field(default_factory=list)
    arxiv_categories: list[str] = Field(default_factory=lambda: ["cs.AI", "cs.SE", "cs.MA"])
    hacker_news: bool = True
    hn_min_points: int = 50

    @property
    def is_configured(self) -> bool:
        return bool(self.pillars)
