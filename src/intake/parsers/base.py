"""Base class for content source parsers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from distill.intake.config import IntakeConfig
from distill.intake.models import ContentItem, ContentSource


class ContentParser(ABC):
    """Base class for source-specific content parsers.

    Each source implements ``parse()`` and ``is_configured``. The
    pipeline skips unconfigured parsers silently.
    """

    def __init__(self, *, config: IntakeConfig) -> None:
        self._config = config

    @property
    @abstractmethod
    def source(self) -> ContentSource:
        """The content source this parser handles."""

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this parser has valid credentials/config to run."""

    @abstractmethod
    def parse(self, since: datetime | None = None) -> list[ContentItem]:
        """Fetch and parse content items from this source.

        Args:
            since: Only return items published/saved after this time.
                   If None, return recent items (source-defined default).

        Returns:
            List of canonical ContentItem objects.
        """
