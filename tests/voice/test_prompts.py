"""Tests for voice extraction prompts."""

from distill.voice.prompts import get_extraction_prompt


def test_extraction_prompt_is_nonempty():
    prompt = get_extraction_prompt()
    assert len(prompt) > 100


def test_extraction_prompt_mentions_categories():
    prompt = get_extraction_prompt()
    assert "tone" in prompt.lower()
    assert "specificity" in prompt.lower()
    assert "structure" in prompt.lower()
    assert "vocabulary" in prompt.lower()
    assert "framing" in prompt.lower()


def test_extraction_prompt_requests_json():
    prompt = get_extraction_prompt()
    assert "json" in prompt.lower()
