"""Parser-specific models for session data."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Message(BaseModel):
    """Represents a message in a conversation."""

    role: str  # 'user' or 'assistant'
    content: str
    timestamp: datetime | None = None


class ToolUsage(BaseModel):
    """Represents a tool call made during a session."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str | None = None
    duration_ms: int | None = None


@dataclass
class ToolUsageSummary:
    """Simplified tool usage for compatibility with models.ToolUsage."""

    name: str
    count: int = 1


class BaseSession(BaseModel):
    """Abstract base model for AI coding assistant sessions.

    This serves as the common interface for sessions from different sources
    (Claude, Cursor, etc.).
    """

    session_id: str
    timestamp: datetime
    source: str = "unknown"
    messages: list[Message] = Field(default_factory=list)
    tool_calls: list[ToolUsage] = Field(default_factory=list)
    summary: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Compatibility properties for models/__init__.py:BaseSession interface
    @property
    def id(self) -> str:
        """Alias for session_id (compatibility with models.BaseSession)."""
        return self.session_id

    @property
    def start_time(self) -> datetime:
        """Alias for timestamp (compatibility with models.BaseSession).

        Note: Subclasses may override this with an actual field.
        """
        # Check if subclass has start_time as a field (not a property)
        cls = type(self)
        if "start_time" in cls.model_fields and not isinstance(
            cls.__dict__.get("start_time"), property
        ):
            val = self.__dict__.get("start_time")
            if val is not None:
                return val
        return self.timestamp

    @property
    def end_time(self) -> datetime | None:
        """End time derived from last message timestamp.

        Note: Subclasses may override this with an actual field.
        """
        # Check if subclass has end_time as a field (not a property)
        cls = type(self)
        if "end_time" in cls.model_fields and not isinstance(
            cls.__dict__.get("end_time"), property
        ):
            val = self.__dict__.get("end_time")
            if val is not None:
                return val
        # Fall back to deriving from message timestamps
        timestamps = [m.timestamp for m in self.messages if m.timestamp is not None]
        return max(timestamps) if timestamps else None

    @property
    def tools_used(self) -> list[ToolUsageSummary]:
        """Convert tool_calls to tools_used format (compatibility)."""
        tool_counts: Counter[str] = Counter(tc.tool_name for tc in self.tool_calls)
        return [ToolUsageSummary(name=name, count=count) for name, count in tool_counts.items()]

    @property
    def note_name(self) -> str:
        """Generate Obsidian-compatible note name."""
        date_str = self.timestamp.strftime("%Y-%m-%d")
        time_str = self.timestamp.strftime("%H%M")
        return f"session-{date_str}-{time_str}-{self.session_id[:8]}"

    @property
    def tags(self) -> list[str]:
        """Return empty tags list (compatibility with models.BaseSession)."""
        return []

    @property
    def turns(self) -> list[Any]:
        """Return messages as turns (compatibility with models.BaseSession)."""
        return [{"role": m.role, "content": m.content, "timestamp": m.timestamp} for m in self.messages]

    @property
    def outcomes(self) -> list[Any]:
        """Return empty outcomes (compatibility with models.BaseSession)."""
        return []

    @property
    def duration_minutes(self) -> float | None:
        """Calculate session duration based on first and last message timestamps."""
        timestamps = [m.timestamp for m in self.messages if m.timestamp is not None]
        if len(timestamps) < 2:
            return None
        delta = max(timestamps) - min(timestamps)
        return delta.total_seconds() / 60
