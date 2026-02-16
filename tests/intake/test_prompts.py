"""Tests for intake prompt parameterization."""

from distill.intake.prompts import get_daily_intake_prompt, get_unified_intake_prompt


class TestDailyIntakePrompt:
    def test_default_no_user_name(self):
        prompt = get_daily_intake_prompt()
        assert "You are a software engineer" in prompt
        # Should not contain a specific name
        assert "You are Nik" not in prompt

    def test_with_user_name(self):
        prompt = get_daily_intake_prompt(user_name="Alice", user_role="indie hacker")
        assert "You are Alice, a indie hacker" in prompt

    def test_custom_role_no_name(self):
        prompt = get_daily_intake_prompt(user_role="data scientist")
        assert "You are a data scientist" in prompt

    def test_target_word_count(self):
        prompt = get_daily_intake_prompt(target_word_count=500)
        assert "500" in prompt

    def test_memory_context_included(self):
        prompt = get_daily_intake_prompt(memory_context="Previous day context")
        assert "Previous day context" in prompt

    def test_memory_context_omitted_when_empty(self):
        prompt = get_daily_intake_prompt(memory_context="")
        assert "Previous Context" not in prompt


class TestUnifiedIntakePrompt:
    def test_default_no_user_name(self):
        prompt = get_unified_intake_prompt()
        assert "You are a software engineer" in prompt
        assert "You are Nik" not in prompt

    def test_with_user_name(self):
        prompt = get_unified_intake_prompt(user_name="Bob", user_role="founder")
        assert "You are Bob, a founder" in prompt

    def test_custom_role_no_name(self):
        prompt = get_unified_intake_prompt(user_role="CTO")
        assert "You are a CTO" in prompt

    def test_sessions_guidance(self):
        prompt = get_unified_intake_prompt(has_sessions=True)
        assert "coding sessions" in prompt

    def test_seeds_guidance(self):
        prompt = get_unified_intake_prompt(has_seeds=True)
        assert "seed ideas" in prompt

    def test_target_word_count(self):
        prompt = get_unified_intake_prompt(target_word_count=1200)
        assert "1200" in prompt
