"""Tests for image generation pipeline integration in core.py."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from distill.intake.images import ImagePrompt


class TestGenerateImages:
    """generate_images() orchestrates prompt extraction + generation."""

    def test_generates_hero_and_inline(self, tmp_path: Path):
        from distill.core import generate_images

        prompts = [
            ImagePrompt(
                role="hero", prompt="a machine", alt="Machine", after_heading=None, mood="technical"
            ),
            ImagePrompt(
                role="inline",
                prompt="assembly line",
                alt="Assembly",
                after_heading="Section",
                mood="technical",
            ),
        ]

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = True
        # generate returns the output_path on success
        def side_effect(prompt, output_path, aspect_ratio, mood=None):
            return output_path
        mock_gen.generate.side_effect = side_effect

        with patch("distill.intake.images.extract_image_prompts", return_value=prompts):
            result_prompts, result_paths = generate_images(
                prose="# Title\n\nContent",
                output_dir=tmp_path,
                date="2026-02-14",
                generator=mock_gen,
            )

        assert len(result_prompts) == 2
        assert 0 in result_paths
        assert 1 in result_paths
        assert "hero" in result_paths[0]
        assert mock_gen.generate.call_count == 2

    def test_skips_when_not_configured(self, tmp_path: Path):
        from distill.core import generate_images

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = False

        result_prompts, result_paths = generate_images(
            prose="# Title\n\nContent",
            output_dir=tmp_path,
            date="2026-02-14",
            generator=mock_gen,
        )

        assert result_prompts == []
        assert result_paths == {}

    def test_partial_failure_continues(self, tmp_path: Path):
        from distill.core import generate_images

        prompts = [
            ImagePrompt(
                role="hero", prompt="good", alt="Good", after_heading=None, mood="energetic"
            ),
            ImagePrompt(
                role="inline", prompt="fail", alt="Fail", after_heading="S", mood="energetic"
            ),
        ]

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = True
        # First call succeeds (returns a path), second fails (returns None)
        mock_gen.generate.side_effect = [tmp_path / "intake" / "images" / "hero.png", None]

        with patch("distill.intake.images.extract_image_prompts", return_value=prompts):
            result_prompts, result_paths = generate_images(
                prose="# Title\n\nContent",
                output_dir=tmp_path,
                date="2026-02-14",
                generator=mock_gen,
            )

        assert 0 in result_paths
        assert 1 not in result_paths

    def test_empty_prompts_returns_empty(self, tmp_path: Path):
        from distill.core import generate_images

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = True

        with patch("distill.intake.images.extract_image_prompts", return_value=[]):
            result_prompts, result_paths = generate_images(
                prose="# Title\n\nContent",
                output_dir=tmp_path,
                date="2026-02-14",
                generator=mock_gen,
            )

        assert result_prompts == []
        assert result_paths == {}
        mock_gen.generate.assert_not_called()
