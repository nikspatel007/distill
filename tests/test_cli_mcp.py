"""Tests for the distill mcp CLI command."""

from unittest.mock import patch

from typer.testing import CliRunner

from distill.cli import app

runner = CliRunner()


def test_mcp_command_exists():
    """The mcp command is registered."""
    result = runner.invoke(app, ["mcp", "--help"])
    assert result.exit_code == 0
    assert "MCP server" in result.output


def test_mcp_command_missing_bun(tmp_path):
    """Shows error when bun is not installed."""
    with patch("subprocess.run", side_effect=FileNotFoundError):
        result = runner.invoke(app, ["mcp", "--output", str(tmp_path)])
        assert result.exit_code != 0
