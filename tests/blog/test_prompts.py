"""Tests for blog prompt template generation."""

from session_insights.blog.config import BlogPostType
from session_insights.blog.prompts import BLOG_SYSTEM_PROMPTS, get_blog_prompt


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
