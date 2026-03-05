"""Tests for reading brief prompts."""
from distill.brief.prompts import get_draft_post_prompt, get_reading_brief_prompt


class TestReadingBriefPrompt:
    def test_returns_string(self):
        prompt = get_reading_brief_prompt()
        assert isinstance(prompt, str)
        assert "3 most interesting" in prompt

    def test_includes_voice_context(self):
        prompt = get_reading_brief_prompt(voice_context="Be direct.")
        assert "Be direct." in prompt
        assert "Voice Patterns" in prompt

    def test_no_voice_when_empty(self):
        prompt = get_reading_brief_prompt(voice_context="")
        assert "Voice Patterns" not in prompt


class TestDraftPostPrompt:
    def test_linkedin_prompt(self):
        prompt = get_draft_post_prompt("linkedin")
        assert "LinkedIn" in prompt
        assert "800-1200 characters" in prompt
        assert "Do NOT mention any personal projects" in prompt

    def test_x_prompt(self):
        prompt = get_draft_post_prompt("x")
        assert "280 characters" in prompt

    def test_voice_injection(self):
        prompt = get_draft_post_prompt("linkedin", voice_context="No hedging.")
        assert "No hedging." in prompt
