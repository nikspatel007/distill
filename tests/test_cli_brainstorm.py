from unittest.mock import patch

from typer.testing import CliRunner

from distill.cli import app

runner = CliRunner()


def test_brainstorm_command_exists():
    result = runner.invoke(app, ["brainstorm", "--help"])
    assert result.exit_code == 0
    assert "brainstorm" in result.output.lower()


def test_brainstorm_command_runs_with_no_items(tmp_path):
    with (
        patch("distill.brainstorm.sources.fetch_hacker_news", return_value=[]),
        patch("distill.brainstorm.sources.fetch_arxiv", return_value=[]),
        patch("distill.brainstorm.sources.fetch_followed_feeds", return_value=[]),
        patch("distill.brainstorm.sources.fetch_manual_links", return_value=[]),
    ):
        result = runner.invoke(app, ["brainstorm", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "No research items found" in result.output
