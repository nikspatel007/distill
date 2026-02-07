"""Base class for intake output publishers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date
from pathlib import Path

from distill.intake.context import DailyIntakeContext


class IntakePublisher(ABC):
    """Base class for intake output formatting."""

    @abstractmethod
    def format_daily(self, context: DailyIntakeContext, prose: str) -> str:
        """Format a daily intake digest for this target."""

    @abstractmethod
    def daily_output_path(self, output_dir: Path, target_date: date) -> Path:
        """Compute the output file path for a daily digest."""
