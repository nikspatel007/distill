"""Tests for voice extraction and merging services."""

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.services import (
    compute_confidence,
    merge_rule_into_profile,
)


def test_compute_confidence_low():
    assert compute_confidence(1) == 0.3
    assert compute_confidence(2) == 0.3


def test_compute_confidence_medium():
    assert compute_confidence(3) == 0.6
    assert compute_confidence(5) == 0.6


def test_compute_confidence_high():
    assert compute_confidence(6) == 0.9
    assert compute_confidence(10) == 0.9


def test_merge_new_rule():
    profile = VoiceProfile()
    new_rule = VoiceRule(rule="Be direct.", category=RuleCategory.TONE)
    merge_rule_into_profile(profile, new_rule)
    assert len(profile.rules) == 1
    assert profile.rules[0].confidence == 0.3
    assert profile.rules[0].source_count == 1


def test_merge_matching_rule_increases_confidence():
    profile = VoiceProfile(rules=[
        VoiceRule(
            id="v-001",
            rule="Be direct and concise.",
            category=RuleCategory.TONE,
            source_count=2,
            confidence=0.3,
        ),
    ])
    new_rule = VoiceRule(rule="Use direct language.", category=RuleCategory.TONE)
    merge_rule_into_profile(profile, new_rule, is_match_id="v-001")
    assert len(profile.rules) == 1
    assert profile.rules[0].source_count == 3
    assert profile.rules[0].confidence == 0.6


def test_merge_contradiction_halves_confidence():
    profile = VoiceProfile(rules=[
        VoiceRule(
            id="v-001",
            rule="Be formal.",
            category=RuleCategory.TONE,
            source_count=4,
            confidence=0.6,
        ),
    ])
    merge_rule_into_profile(profile, None, contradict_id="v-001")
    assert profile.rules[0].confidence == 0.3


def test_merge_preserves_examples_from_new_rule():
    profile = VoiceProfile(rules=[
        VoiceRule(
            id="v-001", rule="Be direct.", category=RuleCategory.TONE,
            source_count=1, confidence=0.3,
        ),
    ])
    new_rule = VoiceRule(
        rule="Be direct.",
        category=RuleCategory.TONE,
        examples={"before": "It might work", "after": "It works"},
    )
    merge_rule_into_profile(profile, new_rule, is_match_id="v-001")
    assert profile.rules[0].examples is not None
    assert profile.rules[0].examples["after"] == "It works"
