"""Tests for voice profile persistence."""

import json
from pathlib import Path

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.store import VOICE_FILENAME, load_voice_profile, save_voice_profile


def test_load_missing_file(tmp_path: Path):
    profile = load_voice_profile(tmp_path)
    assert profile.rules == []
    assert profile.version == 1


def test_save_and_load_roundtrip(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(id="v-001", rule="Be direct.", category=RuleCategory.TONE, confidence=0.7),
    ])
    save_voice_profile(profile, tmp_path)

    loaded = load_voice_profile(tmp_path)
    assert len(loaded.rules) == 1
    assert loaded.rules[0].rule == "Be direct."
    assert loaded.rules[0].confidence == 0.7


def test_save_creates_json_file(tmp_path: Path):
    profile = VoiceProfile()
    save_voice_profile(profile, tmp_path)
    assert (tmp_path / VOICE_FILENAME).exists()
    data = json.loads((tmp_path / VOICE_FILENAME).read_text())
    assert data["version"] == 1


def test_load_corrupt_file(tmp_path: Path):
    (tmp_path / VOICE_FILENAME).write_text("not json {{{")
    profile = load_voice_profile(tmp_path)
    assert profile.rules == []


def test_processed_slugs_persist(tmp_path: Path):
    profile = VoiceProfile(processed_slugs=["slug-1", "slug-2"])
    save_voice_profile(profile, tmp_path)
    loaded = load_voice_profile(tmp_path)
    assert loaded.processed_slugs == ["slug-1", "slug-2"]
