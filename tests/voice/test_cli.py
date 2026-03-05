"""Tests for voice CLI commands."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from distill.cli import app
from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.store import save_voice_profile

runner = CliRunner()


def test_voice_show_empty(tmp_path: Path):
    result = runner.invoke(app, ["voice", "show", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "No voice rules" in result.output


def test_voice_show_with_rules(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE, confidence=0.8),
    ])
    save_voice_profile(profile, tmp_path)
    result = runner.invoke(app, ["voice", "show", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "Be direct." in result.output


def test_voice_show_filter_category(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE, confidence=0.8),
        VoiceRule(rule="Name tools.", category=RuleCategory.SPECIFICITY, confidence=0.7),
    ])
    save_voice_profile(profile, tmp_path)
    result = runner.invoke(app, ["voice", "show", "--output", str(tmp_path), "--category", "tone"])
    assert result.exit_code == 0
    assert "Be direct." in result.output
    assert "Name tools." not in result.output


def test_voice_add(tmp_path: Path):
    result = runner.invoke(app, [
        "voice", "add", "Always use Oxford commas",
        "--category", "vocabulary",
        "--output", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert "Rule added" in result.output


def test_voice_reset(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(rule="old rule", category=RuleCategory.TONE),
    ])
    save_voice_profile(profile, tmp_path)
    result = runner.invoke(app, ["voice", "reset", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "reset" in result.output.lower()


@patch("distill.voice.services.extract_voice_rules")
def test_voice_extract_calls_service(mock_extract, tmp_path: Path):
    mock_extract.return_value = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE),
    ])
    result = runner.invoke(app, ["voice", "extract", "--output", str(tmp_path)])
    assert result.exit_code == 0
    mock_extract.assert_called_once()
