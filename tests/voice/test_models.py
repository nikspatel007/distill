"""Tests for voice memory models."""

from datetime import datetime, UTC

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_rule_defaults():
    rule = VoiceRule(rule="Use direct statements.", category=RuleCategory.TONE)
    assert rule.confidence == 0.3
    assert rule.source_count == 1
    assert rule.id  # auto-generated
    assert rule.examples is None


def test_voice_rule_with_examples():
    rule = VoiceRule(
        rule="Name specific tools.",
        category=RuleCategory.SPECIFICITY,
        examples={"before": "the framework", "after": "FastAPI"},
    )
    assert rule.examples["before"] == "the framework"


def test_voice_profile_empty():
    profile = VoiceProfile()
    assert profile.rules == []
    assert profile.processed_slugs == []
    assert profile.version == 1


def test_voice_profile_add_rule():
    profile = VoiceProfile()
    rule = VoiceRule(rule="Be direct.", category=RuleCategory.TONE)
    profile.rules.append(rule)
    assert len(profile.rules) == 1


def test_confidence_label():
    low = VoiceRule(rule="x", category=RuleCategory.TONE, confidence=0.2)
    med = VoiceRule(rule="x", category=RuleCategory.TONE, confidence=0.5)
    high = VoiceRule(rule="x", category=RuleCategory.TONE, confidence=0.8)
    assert low.confidence_label == "low"
    assert med.confidence_label == "medium"
    assert high.confidence_label == "high"


def test_render_for_prompt_empty():
    profile = VoiceProfile()
    assert profile.render_for_prompt() == ""


def test_render_for_prompt_filters_by_threshold():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="High rule", category=RuleCategory.TONE, confidence=0.8),
        VoiceRule(rule="Low rule", category=RuleCategory.TONE, confidence=0.2),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "High rule" in rendered
    assert "Low rule" not in rendered


def test_render_for_prompt_groups_by_category():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct", category=RuleCategory.TONE, confidence=0.7),
        VoiceRule(rule="Name tools", category=RuleCategory.SPECIFICITY, confidence=0.7),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "### Tone" in rendered
    assert "### Specificity" in rendered
    assert "Be direct" in rendered
    assert "Name tools" in rendered


def test_prune_removes_low_confidence():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="keep", category=RuleCategory.TONE, confidence=0.5),
        VoiceRule(rule="prune", category=RuleCategory.TONE, confidence=0.05),
    ])
    pruned = profile.prune()
    assert pruned == 1
    assert len(profile.rules) == 1
    assert profile.rules[0].rule == "keep"
