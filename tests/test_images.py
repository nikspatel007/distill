"""Tests for image generation module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from distill.images import DEFAULT_STYLE_PREFIX, STYLE_PREFIXES, ImageGenerator


class TestIsConfigured:
    def test_returns_false_without_package(self):
        with patch("distill.images._HAS_GENAI", False):
            gen = ImageGenerator()
            assert gen.is_configured() is False

    def test_returns_false_without_api_key(self):
        with patch("distill.images._HAS_GENAI", True), patch.dict("os.environ", {}, clear=True):
            gen = ImageGenerator()
            assert gen.is_configured() is False

    def test_returns_true_with_both(self):
        with (
            patch("distill.images._HAS_GENAI", True),
            patch.dict("os.environ", {"GOOGLE_AI_API_KEY": "test-key"}),
        ):
            gen = ImageGenerator()
            assert gen.is_configured() is True


class TestGenerate:
    def test_returns_none_when_not_configured(self, tmp_path: Path):
        with patch("distill.images._HAS_GENAI", False):
            gen = ImageGenerator()
            result = gen.generate("a test image", output_path=tmp_path / "img.png")
            assert result is None

    def test_saves_image_on_success(self, tmp_path: Path):
        # Build mock response with an image part
        mock_image = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data = b"fake-png-bytes"
        mock_part.as_image.return_value = mock_image

        mock_response = MagicMock()
        mock_response.parts = [mock_part]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        output = tmp_path / "subdir" / "hero.png"

        mock_types = MagicMock()

        with (
            patch("distill.images._HAS_GENAI", True),
            patch.dict("os.environ", {"GOOGLE_AI_API_KEY": "test-key"}),
            patch("distill.images.genai") as mock_genai,
            patch("distill.images.types", mock_types),
        ):
            mock_genai.Client.return_value = mock_client

            gen = ImageGenerator()
            result = gen.generate("a futuristic city", output_path=output)

        assert result == output
        # Verify parent dir was created
        assert output.parent.exists()
        # Verify image was saved with string path
        mock_image.save.assert_called_once_with(str(output))

    def test_returns_none_on_error(self, tmp_path: Path):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = RuntimeError("API error")

        mock_types = MagicMock()
        output = tmp_path / "hero.png"

        with (
            patch("distill.images._HAS_GENAI", True),
            patch.dict("os.environ", {"GOOGLE_AI_API_KEY": "test-key"}),
            patch("distill.images.genai") as mock_genai,
            patch("distill.images.types", mock_types),
        ):
            mock_genai.Client.return_value = mock_client

            gen = ImageGenerator()
            result = gen.generate("broken prompt", output_path=output)

        assert result is None

    def test_prepends_style_prefix_to_prompt(self, tmp_path: Path):
        mock_part = MagicMock()
        mock_part.inline_data = b"data"
        mock_part.as_image.return_value = MagicMock()

        mock_response = MagicMock()
        mock_response.parts = [mock_part]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_types = MagicMock()
        output = tmp_path / "hero.png"

        with (
            patch("distill.images._HAS_GENAI", True),
            patch.dict("os.environ", {"GOOGLE_AI_API_KEY": "test-key"}),
            patch("distill.images.genai") as mock_genai,
            patch("distill.images.types", mock_types),
        ):
            mock_genai.Client.return_value = mock_client

            gen = ImageGenerator()
            gen.generate("a robot painting", output_path=output)

        call_kwargs = mock_client.models.generate_content.call_args
        contents_arg = call_kwargs.kwargs.get("contents")
        if contents_arg is None:
            contents_arg = call_kwargs.args[0] if call_kwargs.args else None
        assert contents_arg.startswith(DEFAULT_STYLE_PREFIX)
        assert contents_arg.endswith("a robot painting")

    def test_returns_none_when_no_image_in_response(self, tmp_path: Path):
        # Response with a text-only part (no inline_data)
        mock_part = MagicMock()
        mock_part.inline_data = None

        mock_response = MagicMock()
        mock_response.parts = [mock_part]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        mock_types = MagicMock()
        output = tmp_path / "hero.png"

        with (
            patch("distill.images._HAS_GENAI", True),
            patch.dict("os.environ", {"GOOGLE_AI_API_KEY": "test-key"}),
            patch("distill.images.genai") as mock_genai,
            patch("distill.images.types", mock_types),
        ):
            mock_genai.Client.return_value = mock_client

            gen = ImageGenerator()
            result = gen.generate("text only response", output_path=output)

        assert result is None


class TestStylePrefix:
    def test_default_style_prefix_is_reflective(self):
        assert DEFAULT_STYLE_PREFIX == STYLE_PREFIXES["reflective"]
        assert "Contemplative" in DEFAULT_STYLE_PREFIX

    def test_custom_style_prefix_from_env(self):
        custom_prefix = "Watercolor painting, soft pastels. "
        with patch.dict("os.environ", {"IMAGE_STYLE_PREFIX": custom_prefix}):
            gen = ImageGenerator()
            assert gen.style_prefix == custom_prefix

    def test_default_style_prefix_used_when_no_env(self):
        with patch.dict("os.environ", {}, clear=True):
            gen = ImageGenerator()
            assert gen.style_prefix == DEFAULT_STYLE_PREFIX


class TestModelConfig:
    def test_default_model(self):
        with patch.dict("os.environ", {}, clear=True):
            gen = ImageGenerator()
            assert gen.model == "gemini-3-pro-image-preview"

    def test_custom_model_from_env(self):
        with patch.dict("os.environ", {"IMAGE_MODEL": "gemini-custom"}):
            gen = ImageGenerator()
            assert gen.model == "gemini-custom"
