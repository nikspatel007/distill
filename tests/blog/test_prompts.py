"""Tests for blog prompt template generation."""

from distill.blog.config import BlogPostType
from distill.blog.prompts import (
    BLOG_SYSTEM_PROMPTS,
    MEMORY_EXTRACTION_PROMPT,
    SOCIAL_PROMPTS,
    get_blog_prompt,
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


class TestMemoryExtractionPrompt:
    def test_memory_extraction_prompt_exists(self):
        assert len(MEMORY_EXTRACTION_PROMPT) > 0
        assert "JSON" in MEMORY_EXTRACTION_PROMPT
