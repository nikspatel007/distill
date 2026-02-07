"""Intake output publishers — fan-out from canonical model."""

from __future__ import annotations

from distill.intake.publishers.base import IntakePublisher


def create_intake_publisher(platform: str) -> IntakePublisher:
    """Create a publisher for the given platform.

    Args:
        platform: Target platform name (``"obsidian"``, ``"markdown"``).

    Returns:
        An IntakePublisher instance.

    Raises:
        ValueError: If the platform is unknown.
    """
    from distill.intake.publishers.markdown import MarkdownIntakePublisher
    from distill.intake.publishers.obsidian import ObsidianIntakePublisher

    publishers: dict[str, type[IntakePublisher]] = {
        "obsidian": ObsidianIntakePublisher,
        "markdown": MarkdownIntakePublisher,
    }

    if platform in publishers:
        return publishers[platform]()

    raise ValueError(f"Unknown intake publisher: {platform!r}")
