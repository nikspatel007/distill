"""Tests for voice rule injection into journal prompts."""

from datetime import date

from distill.journal.models import DailyContext
from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_renders_for_journal():
    """Voice profile renders for journal context with standard threshold."""
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Short sentences.", category=RuleCategory.STRUCTURE, confidence=0.7),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "Short sentences." in rendered


def test_daily_context_renders_voice_context():
    """DailyContext includes voice_context in rendered text."""
    ctx = DailyContext(
        date=date(2026, 3, 1),
        total_sessions=1,
        total_duration_minutes=30.0,
        voice_context="## Your Voice\n- Use active voice",
    )
    rendered = ctx.render_text()
    assert "## Your Voice" in rendered
    assert "Use active voice" in rendered


def test_daily_context_empty_voice_context_omitted():
    """Empty voice_context adds nothing to rendered text."""
    ctx = DailyContext(
        date=date(2026, 3, 1),
        total_sessions=1,
        total_duration_minutes=30.0,
        voice_context="",
    )
    rendered = ctx.render_text()
    assert "Voice" not in rendered
