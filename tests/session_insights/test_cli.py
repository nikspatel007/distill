"""Tests for session_insights CLI."""

import pytest

from session_insights.cli import main


def test_cli_exists():
    """Verify main function is importable."""
    assert main is not None
