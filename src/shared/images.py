"""Image generation for blog post hero images.

Uses Google Gemini's image generation capability via the google-genai SDK.
Falls back gracefully when the optional dependency is not installed or
the API key is not configured.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Optional dependency
try:
    from google import genai
    from google.genai import types

    _HAS_GENAI = True
except ImportError:
    genai = None  # type: ignore[assignment]
    types = None  # type: ignore[assignment]
    _HAS_GENAI = False

DEFAULT_MODEL = "gemini-3-pro-image-preview"

# Mood-indexed style prefixes. Each provides a distinct visual register
# so images across different posts do not look identical.
STYLE_PREFIXES: dict[str, str] = {
    "reflective": (
        "Contemplative editorial photograph. Diffused overcast light, "
        "cool blue-grey palette with desaturated tones. 50mm lens at f/4, "
        "moderate depth of field. Symmetrical composition with deliberate "
        "negative space. Still, quiet atmosphere. "
        "No text, no logos, no UI elements. -- "
    ),
    "energetic": (
        "Dynamic editorial photograph. Warm golden-hour directional light "
        "casting long shadows. 35mm lens at f/2.8, shallow depth of field. "
        "Diagonal composition with strong leading lines and a sense of forward "
        "motion. Amber and warm-white palette. "
        "No text, no logos, no UI elements. -- "
    ),
    "cautionary": (
        "Tense editorial photograph. Hard directional lighting from a single "
        "source, deep shadows with teal-and-orange color contrast. 85mm lens "
        "at f/2, tight crop with the subject off-center. Unsettled atmosphere. "
        "No text, no logos, no UI elements. -- "
    ),
    "triumphant": (
        "Bold editorial photograph. Bright high-key lighting, vivid saturated "
        "colors. 24mm wide-angle lens at f/8 for deep focus. Expansive "
        "composition with a sense of scale and openness. The scene feels "
        "earned and resolved. "
        "No text, no logos, no UI elements. -- "
    ),
    "intimate": (
        "Quiet editorial photograph. Soft window light from camera-left, "
        "warm muted earth tones with cream and amber highlights. 85mm lens "
        "at f/1.8, very shallow depth of field isolating the subject. Close "
        "framing, personal scale. "
        "No text, no logos, no UI elements. -- "
    ),
    "technical": (
        "Precise editorial photograph. Clean even studio lighting, cool "
        "neutral palette with high clarity. 100mm macro lens or overhead "
        "bird's-eye view. Geometric composition with ordered elements. "
        "Clinical but elegant. "
        "No text, no logos, no UI elements. -- "
    ),
    "playful": (
        "Whimsical editorial photograph. Bright diffused daylight, "
        "slightly warm with pastel accent colors. 35mm lens at f/4, "
        "moderate depth. Off-kilter composition with an element of surprise "
        "or visual humor. Light and approachable atmosphere. "
        "No text, no logos, no UI elements. -- "
    ),
    "somber": (
        "Subdued editorial photograph. Low-key lighting with chiaroscuro "
        "contrast, desaturated palette leaning toward cool greys and muted "
        "blues. 135mm telephoto compression, f/2.8. Isolated subject with "
        "heavy negative space. Bleach-bypass tonal quality. "
        "No text, no logos, no UI elements. -- "
    ),
}

DEFAULT_STYLE_PREFIX = STYLE_PREFIXES["reflective"]


class ImageGenerator:
    """Generate hero images for blog posts via Google Gemini."""

    def __init__(self) -> None:
        self.model = os.environ.get("IMAGE_MODEL", DEFAULT_MODEL)
        self.style_prefix = os.environ.get("IMAGE_STYLE_PREFIX", DEFAULT_STYLE_PREFIX)
        self._client: object | None = None

    def is_configured(self) -> bool:
        """Check whether image generation is available and configured."""
        return _HAS_GENAI and bool(os.environ.get("GOOGLE_AI_API_KEY"))

    def _get_client(self) -> object:
        """Lazy-create and cache the genai Client."""
        if self._client is None:
            self._client = genai.Client(api_key=os.environ["GOOGLE_AI_API_KEY"])  # type: ignore[union-attr]
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        output_path: Path,
        aspect_ratio: str = "16:9",
        mood: str | None = None,
    ) -> Path | None:
        """Generate an image from a text prompt and save it to disk.

        Args:
            prompt: Description of the desired image.
            output_path: Where to write the generated image file.
            aspect_ratio: Image aspect ratio (default "16:9").
            mood: Essay mood for style prefix selection (e.g. "reflective").

        Returns:
            The output_path on success, or None if generation failed
            or the service is not configured.
        """
        if not self.is_configured():
            logger.warning("Image generation not configured — skipping")
            return None

        style = STYLE_PREFIXES.get(mood or "", self.style_prefix)
        full_prompt = style + prompt

        try:
            client = self._get_client()
            response = client.models.generate_content(  # type: ignore[union-attr]
                model=self.model,
                contents=full_prompt,
                config=types.GenerateContentConfig(  # type: ignore[union-attr]
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(  # type: ignore[union-attr]
                        aspect_ratio=aspect_ratio,
                        image_size="2K",
                    ),
                ),
            )

            for part in response.parts:
                if part.inline_data is not None:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    part.as_image().save(str(output_path))
                    logger.info("Saved generated image to %s", output_path)
                    return output_path

            logger.warning("No image data in response for prompt: %s", prompt[:80])
            return None

        except Exception:
            logger.warning("Image generation failed for prompt: %s", prompt[:80], exc_info=True)
            return None
