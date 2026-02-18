"""Tests for blog prompt template generation."""

from distill.blog.config import BlogPostType
from distill.blog.prompts import (
    BLOG_SYSTEM_PROMPTS,
    DAILY_SOCIAL_PROMPTS,
    MEMORY_EXTRACTION_PROMPT,
    SOCIAL_PROMPTS,
    get_blog_prompt,
    get_daily_social_prompt,
    get_social_prompt,
)


class TestBlogPrompts:
    def test_weekly_prompt_interpolation(self):
        prompt = get_blog_prompt(BlogPostType.WEEKLY, 1200)
        assert "1200" in prompt
        assert "weekly" in prompt.lower() or "week" in prompt.lower()
        assert "mermaid" in prompt.lower()

    def test_thematic_prompt_interpolation(self):
        prompt = get_blog_prompt(
            BlogPostType.THEMATIC, 1500, theme_title="Test Theme"
        )
        assert "1500" in prompt
        assert "Test Theme" in prompt
        assert "mermaid" in prompt.lower()

    def test_all_types_have_prompts(self):
        for post_type in BlogPostType:
            assert post_type in BLOG_SYSTEM_PROMPTS

    def test_prompts_mention_first_person(self):
        for post_type in BlogPostType:
            prompt = get_blog_prompt(post_type, 1000, theme_title="placeholder")
            # All prompts should instruct first-person writing
            assert "first person" in prompt.lower() or '"I"' in prompt or '"we"' in prompt


class TestSocialPrompts:
    def test_social_prompts_keys_exist(self):
        assert "twitter" in SOCIAL_PROMPTS
        assert "linkedin" in SOCIAL_PROMPTS
        assert "reddit" in SOCIAL_PROMPTS

    def test_social_prompts_are_nonempty(self):
        for platform, prompt in SOCIAL_PROMPTS.items():
            assert len(prompt) > 0, f"{platform} prompt is empty"


class TestBlogMemoryInjection:
    def test_get_blog_prompt_with_memory_appends(self):
        memory_text = "## Previous Blog Posts\n\n- Some post"
        prompt = get_blog_prompt(BlogPostType.WEEKLY, 1200, blog_memory=memory_text)
        assert prompt.endswith(memory_text)
        assert "1200" in prompt

    def test_get_blog_prompt_without_memory_unchanged(self):
        with_empty = get_blog_prompt(BlogPostType.WEEKLY, 1200, blog_memory="")
        without = get_blog_prompt(BlogPostType.WEEKLY, 1200)
        assert with_empty == without


class TestGetSocialPrompt:
    def test_get_social_prompt_default_hashtags(self):
        prompt = get_social_prompt("twitter")
        assert "#AgenticAI" in prompt or "#DevTools" in prompt or "#BuildInPublic" in prompt

    def test_get_social_prompt_custom_hashtags(self):
        prompt = get_social_prompt("twitter", hashtags="#MyTag #OtherTag")
        assert "#MyTag #OtherTag" in prompt

    def test_get_social_prompt_linkedin(self):
        prompt = get_social_prompt("linkedin", hashtags="#Custom")
        assert "#Custom" in prompt

    def test_get_social_prompt_reddit_no_hashtags(self):
        prompt = get_social_prompt("reddit")
        assert len(prompt) > 0
        assert "Reddit" in prompt

    def test_get_social_prompt_unknown_raises(self):
        import pytest

        with pytest.raises(KeyError):
            get_social_prompt("nonexistent_platform")

    def test_backward_compat_social_prompts_dict(self):
        for key in ("twitter", "linkedin", "reddit", "slack", "newsletter"):
            assert key in SOCIAL_PROMPTS
            assert len(SOCIAL_PROMPTS[key]) > 0


class TestGetDailySocialPrompt:
    def test_default_no_project(self):
        prompt = get_daily_social_prompt("linkedin")
        assert "building software" in prompt

    def test_with_project_name(self):
        prompt = get_daily_social_prompt("linkedin", project_name="FooProject")
        assert "FooProject" in prompt

    def test_with_project_name_and_description(self):
        prompt = get_daily_social_prompt(
            "linkedin",
            project_name="FooProject",
            project_description="a widget framework",
        )
        assert "FooProject" in prompt
        assert "a widget framework" in prompt

    def test_custom_hashtags(self):
        prompt = get_daily_social_prompt(
            "linkedin", hashtags="#MyBrand #BuildInPublic"
        )
        assert "#MyBrand #BuildInPublic" in prompt

    def test_twitter_platform(self):
        prompt = get_daily_social_prompt(
            "twitter", project_name="MyApp", hashtags="#MyApp"
        )
        assert "MyApp" in prompt
        assert "#MyApp" in prompt

    def test_slack_platform_no_placeholders(self):
        prompt = get_daily_social_prompt("slack")
        assert "Slack" in prompt

    def test_unknown_platform_falls_back_to_linkedin(self):
        prompt = get_daily_social_prompt("nonexistent")
        # Should return a valid prompt (linkedin fallback)
        assert len(prompt) > 100

    def test_backward_compat_daily_social_prompts_dict(self):
        for key in ("linkedin", "twitter", "slack"):
            assert key in DAILY_SOCIAL_PROMPTS
            assert len(DAILY_SOCIAL_PROMPTS[key]) > 0
        # The compat dict should NOT contain template placeholders
        for key, prompt in DAILY_SOCIAL_PROMPTS.items():
            assert "{project_intro}" not in prompt
            assert "{hashtags}" not in prompt


class TestMemoryExtractionPrompt:
    def test_memory_extraction_prompt_exists(self):
        assert len(MEMORY_EXTRACTION_PROMPT) > 0
        assert "JSON" in MEMORY_EXTRACTION_PROMPT
