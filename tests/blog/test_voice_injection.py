"""Tests for voice rule injection into blog prompts."""

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_profile_renders_for_blog():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE, confidence=0.8),
        VoiceRule(rule="Name tools.", category=RuleCategory.SPECIFICITY, confidence=0.6),
        VoiceRule(rule="Low conf.", category=RuleCategory.STRUCTURE, confidence=0.2),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "## Your Voice" in rendered
    assert "Be direct." in rendered
    assert "Name tools." in rendered
    assert "Low conf." not in rendered
    assert "override generic style guidelines" in rendered
