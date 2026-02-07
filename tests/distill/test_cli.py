"""Tests for distill CLI."""

import pytest

from distill.cli import main


def test_cli_exists():
    """Verify main function is importable."""
    assert main is not None
