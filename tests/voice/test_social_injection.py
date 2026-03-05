"""Tests for voice injection into social and intake prompts."""

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_renders_with_low_threshold_for_social():
    """Social adaptation uses lower threshold (0.3) to include experimental rules."""
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Tentative rule.", category=RuleCategory.TONE, confidence=0.35),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.3)
    assert "Tentative rule." in rendered

    # Same rule excluded at standard threshold
    rendered_high = profile.render_for_prompt(min_confidence=0.5)
    assert "Tentative rule." not in rendered_high


def test_voice_renders_empty_when_no_rules_pass_threshold():
    """Profile with no rules above threshold renders empty string."""
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Very low confidence.", category=RuleCategory.TONE, confidence=0.1),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.3)
    assert rendered == ""


def test_voice_renders_multiple_categories_for_social():
    """Social voice context includes rules from multiple categories."""
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE, confidence=0.4),
        VoiceRule(rule="Use short sentences.", category=RuleCategory.STRUCTURE, confidence=0.35),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.3)
    assert "Be direct." in rendered
    assert "Use short sentences." in rendered
