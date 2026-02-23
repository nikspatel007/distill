# Image Generation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add AI-generated photorealistic images to daily intake digests using Nano Banana Pro (Gemini 3 Pro Image), with graceful degradation when not configured.

**Architecture:** After prose synthesis, Claude extracts 2-3 image prompts from the essay. Nano Banana Pro generates images via the `google-genai` SDK. Images are saved locally and inserted into markdown. The Ghost publisher uploads images and sets the hero as `feature_image`. The entire feature is a no-op when `GOOGLE_AI_API_KEY` is absent.

**Tech Stack:** `google-genai` (Gemini SDK), `Pillow` (image handling), Ghost Admin API `/images/upload/`

---

### Task 1: Image generator client (`src/images.py`)

**Files:**
- Create: `src/images.py`
- Create: `tests/test_images.py`

**Step 1: Write the failing tests**

```python
"""Tests for src/images.py — image generation client."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestIsConfigured:
    """ImageGenerator.is_configured() checks."""

    def test_not_configured_without_package(self):
        with patch("distill.images._HAS_GENAI", False):
            from distill.images import ImageGenerator

            gen = ImageGenerator()
            assert gen.is_configured() is False

    def test_not_configured_without_api_key(self):
        with patch("distill.images._HAS_GENAI", True):
            with patch.dict(os.environ, {}, clear=True):
                from distill.images import ImageGenerator

                gen = ImageGenerator()
                assert gen.is_configured() is False

    def test_configured_with_package_and_key(self):
        with patch("distill.images._HAS_GENAI", True):
            with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}):
                from distill.images import ImageGenerator

                gen = ImageGenerator()
                assert gen.is_configured() is True


class TestGenerate:
    """ImageGenerator.generate() calls."""

    def test_returns_none_when_not_configured(self, tmp_path: Path):
        with patch("distill.images._HAS_GENAI", False):
            from distill.images import ImageGenerator

            gen = ImageGenerator()
            result = gen.generate("a cat", output_path=tmp_path / "cat.png")
            assert result is None

    def test_generate_saves_image(self, tmp_path: Path):
        """Mock the genai client and verify image is saved."""
        mock_image = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data = True
        mock_part.as_image.return_value = mock_image

        mock_response = MagicMock()
        mock_response.parts = [mock_part]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("distill.images._HAS_GENAI", True):
            with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}):
                from distill.images import ImageGenerator

                gen = ImageGenerator()
                gen._client = mock_client

                out = tmp_path / "test.png"
                result = gen.generate("a pipeline", output_path=out)

                assert result == out
                mock_image.save.assert_called_once_with(str(out))

    def test_generate_returns_none_on_error(self, tmp_path: Path):
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = Exception("API error")

        with patch("distill.images._HAS_GENAI", True):
            with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}):
                from distill.images import ImageGenerator

                gen = ImageGenerator()
                gen._client = mock_client

                result = gen.generate("fail", output_path=tmp_path / "fail.png")
                assert result is None

    def test_generate_prepends_style_prefix(self, tmp_path: Path):
        mock_image = MagicMock()
        mock_part = MagicMock()
        mock_part.inline_data = True
        mock_part.as_image.return_value = mock_image

        mock_response = MagicMock()
        mock_response.parts = [mock_part]

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        with patch("distill.images._HAS_GENAI", True):
            with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}):
                from distill.images import ImageGenerator

                gen = ImageGenerator()
                gen._client = mock_client

                gen.generate("a cat on a roof", output_path=tmp_path / "cat.png")

                call_args = mock_client.models.generate_content.call_args
                prompt = call_args.kwargs.get("contents", call_args.args[0] if call_args.args else "")
                # The actual prompt should contain our style prefix
                assert "Cinematic" in str(prompt) or "cinematic" in str(prompt)


class TestStylePrefix:
    """Style prefix configuration."""

    def test_default_style_prefix(self):
        with patch("distill.images._HAS_GENAI", True):
            with patch.dict(os.environ, {"GOOGLE_AI_API_KEY": "test-key"}):
                from distill.images import DEFAULT_STYLE_PREFIX

                assert "Cinematic" in DEFAULT_STYLE_PREFIX

    def test_custom_style_prefix_from_env(self):
        with patch("distill.images._HAS_GENAI", True):
            with patch.dict(
                os.environ,
                {"GOOGLE_AI_API_KEY": "key", "IMAGE_STYLE_PREFIX": "Watercolor painting"},
            ):
                from distill.images import ImageGenerator

                gen = ImageGenerator()
                assert "Watercolor" in gen.style_prefix
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_images.py -x -v`
Expected: FAIL (module `distill.images` not found)

**Step 3: Write the implementation**

```python
"""AI image generation for TroopX Journal.

Uses Nano Banana Pro (Gemini 3 Pro Image) via the google-genai SDK.
Gracefully degrades when the SDK is not installed or API key is missing.
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

DEFAULT_STYLE_PREFIX = (
    "Cinematic photorealistic photograph, high contrast lighting, "
    "cool blue-tinted shadows, clean minimalist composition, "
    "shallow depth of field, technical subject matter. "
    "No text, no logos, no UI elements. — "
)


class ImageGenerator:
    """Generate images using Nano Banana Pro (Gemini Image)."""

    def __init__(self) -> None:
        self._client: object | None = None
        self.model = os.environ.get("IMAGE_MODEL", DEFAULT_MODEL)
        self.style_prefix = os.environ.get("IMAGE_STYLE_PREFIX", DEFAULT_STYLE_PREFIX)

    def is_configured(self) -> bool:
        """Check if image generation is available and configured."""
        return _HAS_GENAI and bool(os.environ.get("GOOGLE_AI_API_KEY"))

    def _get_client(self) -> object:
        """Get or create the genai client."""
        if self._client is None:
            self._client = genai.Client(api_key=os.environ["GOOGLE_AI_API_KEY"])
        return self._client

    def generate(
        self,
        prompt: str,
        *,
        output_path: Path,
        aspect_ratio: str = "16:9",
    ) -> Path | None:
        """Generate an image from a prompt and save it.

        Returns the output path on success, None on failure.
        """
        if not self.is_configured():
            return None

        full_prompt = self.style_prefix + prompt

        try:
            client = self._get_client()
            config = types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
                image_config=types.ImageConfig(
                    aspect_ratio=aspect_ratio,
                    image_size="2K",
                ),
            )
            response = client.models.generate_content(
                model=self.model,
                contents=full_prompt,
                config=config,
            )

            for part in response.parts:
                if part.inline_data is not None:
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    image = part.as_image()
                    image.save(str(output_path))
                    logger.info("Generated image: %s", output_path)
                    return output_path

            logger.warning("No image in response for prompt: %s", prompt[:80])
            return None

        except Exception:
            logger.warning("Image generation failed for: %s", prompt[:80], exc_info=True)
            return None
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_images.py -x -v`
Expected: PASS (all tests)

**Step 5: Commit**

```bash
git add src/images.py tests/test_images.py
git commit -m "feat: add ImageGenerator client for Nano Banana Pro"
```

---

### Task 2: Image prompt extraction from prose (`src/intake/images.py`)

**Files:**
- Create: `src/intake/images.py`
- Create: `tests/intake/test_images.py`

**Step 1: Write the failing tests**

```python
"""Tests for src/intake/images.py — image prompt extraction."""

from __future__ import annotations

import json
from unittest.mock import patch, MagicMock

import pytest

from distill.intake.images import ImagePrompt, extract_image_prompts, insert_images_into_prose


SAMPLE_PROSE = """\
# The Machine That Reads Itself

Today was the day the pipeline turned inward. Thirty sessions, all under two minutes.

## The Assembly Line

Entity extraction, classification, key-point extraction. Each one fires off a claude -p subprocess.

## The Recursive Mirror

The registration essay was analyzing the ceremony overhead of agent registration in TroopX.
"""

SAMPLE_LLM_RESPONSE = json.dumps([
    {
        "role": "hero",
        "prompt": "A sleek industrial machine examining its own reflection in a polished steel mirror, factory setting with blue ambient lighting",
        "alt": "A machine examining its own reflection",
        "after_heading": None,
    },
    {
        "role": "inline",
        "prompt": "An assembly line of glowing data packets being sorted and classified by robotic arms, cool blue factory lighting",
        "alt": "Data packets on an assembly line",
        "after_heading": "The Assembly Line",
    },
])


class TestExtractImagePrompts:
    """extract_image_prompts() calls Claude to get image descriptions."""

    def test_returns_image_prompts_from_llm(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = SAMPLE_LLM_RESPONSE

        with patch("subprocess.run", return_value=mock_result):
            prompts = extract_image_prompts(SAMPLE_PROSE)

        assert len(prompts) == 2
        assert prompts[0].role == "hero"
        assert "reflection" in prompts[0].prompt
        assert prompts[1].role == "inline"
        assert prompts[1].after_heading == "The Assembly Line"

    def test_returns_empty_on_subprocess_failure(self):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "error"

        with patch("subprocess.run", return_value=mock_result):
            prompts = extract_image_prompts(SAMPLE_PROSE)

        assert prompts == []

    def test_returns_empty_on_invalid_json(self):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "not json at all"

        with patch("subprocess.run", return_value=mock_result):
            prompts = extract_image_prompts(SAMPLE_PROSE)

        assert prompts == []

    def test_strips_json_fences(self):
        """Claude sometimes wraps JSON in code fences."""
        fenced = "```json\n" + SAMPLE_LLM_RESPONSE + "\n```"
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = fenced

        with patch("subprocess.run", return_value=mock_result):
            prompts = extract_image_prompts(SAMPLE_PROSE)

        assert len(prompts) == 2


class TestInsertImagesIntoProse:
    """insert_images_into_prose() places image markdown at the right spots."""

    def test_inserts_hero_after_h1(self):
        prompts = [ImagePrompt(role="hero", prompt="x", alt="Hero image", after_heading=None)]
        paths = {0: "images/hero.png"}

        result = insert_images_into_prose(SAMPLE_PROSE, prompts, paths)

        lines = result.split("\n")
        h1_idx = next(i for i, l in enumerate(lines) if l.startswith("# "))
        assert "![Hero image](images/hero.png)" in lines[h1_idx + 1]

    def test_inserts_inline_before_heading(self):
        prompts = [
            ImagePrompt(role="inline", prompt="x", alt="Assembly line", after_heading="The Assembly Line"),
        ]
        paths = {0: "images/inline-1.png"}

        result = insert_images_into_prose(SAMPLE_PROSE, prompts, paths)

        lines = result.split("\n")
        img_idx = next(i for i, l in enumerate(lines) if "Assembly line" in l and l.startswith("!["))
        heading_idx = next(i for i, l in enumerate(lines) if "## The Assembly Line" in l)
        assert img_idx < heading_idx

    def test_skips_prompts_without_paths(self):
        prompts = [ImagePrompt(role="hero", prompt="x", alt="Hero", after_heading=None)]
        paths: dict[int, str] = {}  # no images generated

        result = insert_images_into_prose(SAMPLE_PROSE, prompts, paths)

        assert result == SAMPLE_PROSE  # unchanged

    def test_handles_missing_heading_gracefully(self):
        prompts = [
            ImagePrompt(role="inline", prompt="x", alt="Missing", after_heading="Nonexistent Heading"),
        ]
        paths = {0: "images/orphan.png"}

        result = insert_images_into_prose(SAMPLE_PROSE, prompts, paths)

        # Image should be appended after the last H2 or at the end
        assert "![Missing](images/orphan.png)" in result
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/intake/test_images.py -x -v`
Expected: FAIL (module not found)

**Step 3: Write the implementation**

```python
"""Image prompt extraction from synthesized prose.

Calls Claude to analyze an essay and produce image generation prompts
for hero and inline illustrations.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ImagePrompt:
    """A single image generation prompt extracted from prose."""

    role: str  # "hero" or "inline"
    prompt: str  # description for the image generator
    alt: str  # alt text for the markdown image
    after_heading: str | None  # H2 heading this image relates to (None for hero)


_EXTRACTION_PROMPT = """\
You are an art director for a technical journal. Given an essay, produce image prompts \
for photorealistic illustrations.

Rules:
- Output ONLY a JSON array, no other text
- First item must have role "hero" — the central visual metaphor of the essay
- 1-2 more items with role "inline" — visual moments from specific sections
- Each prompt should describe a SCENE, not just keywords
- Include specific details: lighting, composition, materials, setting
- Never mention text, logos, UI, or code in the scene
- The "after_heading" field must match an exact H2 heading from the essay (or null for hero)
- The "alt" field is a short accessible description (under 12 words)

Output format:
[
  {"role": "hero", "prompt": "scene description...", "alt": "short alt text", "after_heading": null},
  {"role": "inline", "prompt": "scene description...", "alt": "short alt text", "after_heading": "Exact H2 Text"}
]

Essay:
"""


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```json) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)
    return text.strip()


def extract_image_prompts(prose: str) -> list[ImagePrompt]:
    """Extract image prompts from synthesized prose via Claude.

    Returns an empty list on any failure (graceful degradation).
    """
    try:
        env = {**os.environ, "CLAUDECODE": ""}
        result = subprocess.run(
            ["claude", "-p", "--model", "sonnet", "--max-tokens", "1024"],
            input=_EXTRACTION_PROMPT + prose,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

        if result.returncode != 0:
            logger.warning("Image prompt extraction failed: %s", result.stderr[:200])
            return []

        raw = _strip_json_fences(result.stdout)
        items = json.loads(raw)

        return [
            ImagePrompt(
                role=item["role"],
                prompt=item["prompt"],
                alt=item.get("alt", ""),
                after_heading=item.get("after_heading"),
            )
            for item in items
        ]

    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        logger.warning("Failed to parse image prompts: %s", exc)
        return []
    except Exception:
        logger.warning("Image prompt extraction error", exc_info=True)
        return []


def insert_images_into_prose(
    prose: str,
    prompts: list[ImagePrompt],
    paths: dict[int, str],
) -> str:
    """Insert image markdown into prose at the right positions.

    Args:
        prose: The original essay markdown.
        prompts: Image prompts with placement info.
        paths: Map of prompt index -> relative image path. Missing indices are skipped.

    Returns:
        Updated prose with image markdown inserted.
    """
    if not paths:
        return prose

    lines = prose.split("\n")
    insertions: list[tuple[int, str]] = []  # (line_index, markdown)

    for idx, prompt in enumerate(prompts):
        if idx not in paths:
            continue

        img_md = f"![{prompt.alt}]({paths[idx]})"

        if prompt.role == "hero":
            # Insert after H1
            for i, line in enumerate(lines):
                if line.startswith("# ") and not line.startswith("## "):
                    insertions.append((i + 1, img_md))
                    break
        else:
            # Insert before the matching H2
            target = prompt.after_heading or ""
            found = False
            for i, line in enumerate(lines):
                if line.strip() == f"## {target}":
                    insertions.append((i, img_md))
                    found = True
                    break
            if not found and target:
                # Fallback: append after last content
                insertions.append((len(lines), img_md))

    # Apply insertions in reverse order to preserve line indices
    for line_idx, img_md in sorted(insertions, key=lambda x: x[0], reverse=True):
        lines.insert(line_idx, "")
        lines.insert(line_idx + 1, img_md)

    return "\n".join(lines)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/intake/test_images.py -x -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/intake/images.py tests/intake/test_images.py
git commit -m "feat: add image prompt extraction from prose"
```

---

### Task 3: Ghost image upload (`src/blog/publishers/ghost.py`)

**Files:**
- Modify: `src/blog/publishers/ghost.py:20-126` (GhostAPIClient)
- Modify: `tests/blog/test_publishers.py`

**Step 1: Write the failing test**

Add to the existing `tests/blog/test_publishers.py` (or a new test class):

```python
class TestGhostAPIClientImageUpload:
    """GhostAPIClient.upload_image() tests."""

    def test_upload_image_returns_url(self, tmp_path: Path):
        img_path = tmp_path / "hero.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        mock_response = {
            "images": [{"url": "https://ghost.example.com/content/images/hero.png"}]
        }

        with patch.object(GhostAPIClient, "_request_multipart", return_value=mock_response):
            client = GhostAPIClient("https://ghost.example.com", "fakeid:fakesecret")
            url = client.upload_image(img_path)

        assert url == "https://ghost.example.com/content/images/hero.png"

    def test_upload_image_returns_none_on_error(self, tmp_path: Path):
        img_path = tmp_path / "hero.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n")

        with patch.object(GhostAPIClient, "_request_multipart", side_effect=Exception("fail")):
            client = GhostAPIClient("https://ghost.example.com", "fakeid:fakesecret")
            url = client.upload_image(img_path)

        assert url is None
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/blog/test_publishers.py -x -v -k "image_upload"`
Expected: FAIL (no `upload_image` method, no `_request_multipart` method)

**Step 3: Write the implementation**

Add two methods to `GhostAPIClient` in `src/blog/publishers/ghost.py`:

```python
def _request_multipart(self, path: str, file_path: Path, field: str = "file") -> dict:
    """Send a multipart form upload to the Ghost API."""
    token = self._generate_token()
    url = f"{self.api_url}{path}"
    boundary = "----GhostUploadBoundary"

    file_data = file_path.read_bytes()
    content_type = "image/png" if file_path.suffix == ".png" else "image/jpeg"

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{field}"; filename="{file_path.name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode() + file_data + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Ghost {token}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )

    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode("utf-8"))

def upload_image(self, file_path: Path) -> str | None:
    """Upload an image to Ghost and return the CDN URL.

    Returns None on failure (graceful degradation).
    """
    try:
        result = self._request_multipart("/images/upload/", file_path)
        url = result["images"][0]["url"]
        logger.info("Uploaded image to Ghost: %s", url)
        return url
    except Exception:
        logger.warning("Failed to upload image to Ghost: %s", file_path, exc_info=True)
        return None
```

Also update `create_post` to accept an optional `feature_image` parameter:

```python
def create_post(
    self,
    title: str,
    markdown: str,
    tags: list[str] | None = None,
    status: str = "draft",
    feature_image: str | None = None,
) -> dict:
    post_data: dict = {
        "title": title,
        "mobiledoc": self._markdown_to_mobiledoc(markdown),
        "status": status,
    }
    if tags:
        post_data["tags"] = [{"name": t} for t in tags]
    if feature_image:
        post_data["feature_image"] = feature_image

    result = self._request("POST", "/posts/", {"posts": [post_data]})
    return result["posts"][0]
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/blog/test_publishers.py -x -v`
Expected: PASS

**Step 5: Commit**

```bash
git add src/blog/publishers/ghost.py tests/blog/test_publishers.py
git commit -m "feat: add image upload and feature_image to GhostAPIClient"
```

---

### Task 4: Wire image generation into intake synthesis (`src/core.py`)

**Files:**
- Modify: `src/core.py:1232-1251` (after synthesis, before fan-out)
- Create: `tests/test_image_pipeline.py`

**Step 1: Write the failing test**

```python
"""Tests for image generation integration in the intake pipeline."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from distill.intake.images import ImagePrompt


class TestGenerateImages:
    """generate_images() orchestrates prompt extraction + image generation."""

    def test_generates_hero_and_inline(self, tmp_path: Path):
        from distill.core import generate_images

        prompts = [
            ImagePrompt(role="hero", prompt="a machine", alt="Machine", after_heading=None),
            ImagePrompt(role="inline", prompt="assembly line", alt="Assembly", after_heading="Section"),
        ]

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = True
        mock_gen.generate.side_effect = lambda prompt, output_path, aspect_ratio: output_path

        with patch("distill.core.extract_image_prompts", return_value=prompts):
            result_prompts, result_paths = generate_images(
                prose="# Title\n\nContent",
                output_dir=tmp_path,
                date="2026-02-14",
                generator=mock_gen,
            )

        assert len(result_prompts) == 2
        assert 0 in result_paths
        assert 1 in result_paths
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
            ImagePrompt(role="hero", prompt="good", alt="Good", after_heading=None),
            ImagePrompt(role="inline", prompt="fail", alt="Fail", after_heading="S"),
        ]

        mock_gen = MagicMock()
        mock_gen.is_configured.return_value = True
        # First succeeds, second fails
        mock_gen.generate.side_effect = [tmp_path / "hero.png", None]

        with patch("distill.core.extract_image_prompts", return_value=prompts):
            result_prompts, result_paths = generate_images(
                prose="# Title\n\nContent",
                output_dir=tmp_path,
                date="2026-02-14",
                generator=mock_gen,
            )

        assert 0 in result_paths
        assert 1 not in result_paths
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_image_pipeline.py -x -v`
Expected: FAIL (no `generate_images` function)

**Step 3: Write the implementation**

Add to `src/core.py` (new function + wire into `generate_intake`):

```python
def generate_images(
    prose: str,
    output_dir: Path,
    date: str,
    generator: ImageGenerator | None = None,
) -> tuple[list[ImagePrompt], dict[int, str]]:
    """Generate images for an intake digest.

    Returns (prompts, paths) where paths maps prompt index to relative image path.
    Returns ([], {}) if not configured or on failure.
    """
    if generator is None:
        from distill.images import ImageGenerator
        generator = ImageGenerator()

    if not generator.is_configured():
        return [], {}

    from distill.intake.images import extract_image_prompts

    prompts = extract_image_prompts(prose)
    if not prompts:
        return [], {}

    images_dir = output_dir / "intake" / "images"
    paths: dict[int, str] = {}

    for idx, prompt in enumerate(prompts):
        suffix = "hero" if prompt.role == "hero" else str(idx)
        filename = f"{date}-{suffix}.png"
        aspect = "16:9" if prompt.role == "hero" else "3:2"

        result = generator.generate(
            prompt.prompt,
            output_path=images_dir / filename,
            aspect_ratio=aspect,
        )
        if result:
            paths[idx] = f"images/{filename}"

    return prompts, paths
```

Then in `generate_intake()`, after line 1232 (`prose = synthesizer.synthesize_daily(...)`) and before line 1234 (the fan-out loop), add:

```python
    # Generate images (optional — no-op if GOOGLE_AI_API_KEY not set)
    from distill.intake.images import insert_images_into_prose
    image_prompts, image_paths = generate_images(prose, output_dir, context.date)
    if image_paths:
        prose = insert_images_into_prose(prose, image_prompts, image_paths)
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_image_pipeline.py -x -v`
Expected: PASS

Also run the full test suite:
Run: `uv run pytest tests/ -x -q --ignore=tests/test_verify_all_kpis.py`
Expected: PASS (no regressions)

**Step 5: Commit**

```bash
git add src/core.py tests/test_image_pipeline.py
git commit -m "feat: wire image generation into intake pipeline"
```

---

### Task 5: Ghost intake publisher — upload images + set feature_image

**Files:**
- Modify: `src/intake/publishers/ghost.py:88-123` (`_publish_to_api`)
- Modify: `tests/intake/test_publishers.py` (or existing Ghost publisher tests)

**Step 1: Write the failing test**

```python
class TestGhostIntakePublisherImages:
    """Ghost intake publisher handles images in prose."""

    def test_uploads_images_and_sets_feature_image(self, tmp_path: Path):
        """When prose contains image references, upload them and set feature_image."""
        prose = '<!-- ghost-meta: {"title": "Test", "tags": ["intake"]} -->\n\n# Test\n\n![Hero](images/2026-02-14-hero.png)\n\nContent here.'

        # Create a fake image file
        images_dir = tmp_path / "intake" / "images"
        images_dir.mkdir(parents=True)
        (images_dir / "2026-02-14-hero.png").write_bytes(b"\x89PNG" + b"\x00" * 100)

        mock_api = MagicMock()
        mock_api.upload_image.return_value = "https://ghost.example.com/content/images/hero.png"
        mock_api.create_post.return_value = {"id": "abc123"}

        publisher = GhostIntakePublisher(ghost_config=mock_config)
        publisher._api = mock_api
        publisher._output_dir = tmp_path

        publisher._publish_to_api(prose)

        # Should have uploaded the image
        mock_api.upload_image.assert_called_once()
        # Should have set feature_image on create_post
        call_kwargs = mock_api.create_post.call_args
        assert "feature_image" in str(call_kwargs)
```

**Step 2: Run tests, implement, verify**

In `_publish_to_api()`, after extracting the prose and before calling `create_post`:

1. Scan prose for `![alt](images/filename)` patterns
2. For each match, resolve to local file path (`self._output_dir / "intake" / path`)
3. Call `self._api.upload_image(local_path)` → get Ghost CDN URL
4. Replace local path in prose with CDN URL
5. First image (hero) also goes into `feature_image` parameter of `create_post()`

**Step 3: Commit**

```bash
git add src/intake/publishers/ghost.py tests/intake/test_publishers.py
git commit -m "feat: upload images to Ghost and set feature_image on intake posts"
```

---

### Task 6: Add optional dependency to pyproject.toml

**Files:**
- Modify: `pyproject.toml:35-56`

**Step 1: Add the dependency group**

```toml
images = [
    "google-genai>=1.0",
    "Pillow>=10.0",
]
```

Add to the `all-sources` list as well.

**Step 2: Test install**

Run: `uv pip install -e ".[images]"`
Expected: `google-genai` and `Pillow` installed

**Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add images optional dependency group (google-genai, Pillow)"
```

---

### Task 7: Run full test suite + verify existing pipeline is unaffected

**Step 1: Run all tests without GOOGLE_AI_API_KEY set**

```bash
unset GOOGLE_AI_API_KEY
uv run pytest tests/ -x -q --ignore=tests/test_verify_all_kpis.py
```

Expected: ALL PASS — the image feature should be completely invisible when not configured.

**Step 2: Run type checking**

```bash
uv run mypy src/images.py src/intake/images.py --no-error-summary
```

Expected: No errors

**Step 3: Run linting**

```bash
uv run ruff check src/images.py src/intake/images.py
```

Expected: No errors

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore: fix any linting/type issues from image generation feature"
```
