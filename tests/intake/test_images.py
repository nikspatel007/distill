"""Tests for image prompt extraction and insertion."""

from __future__ import annotations

import json
from unittest.mock import patch

from distill.intake.images import (
    ImagePrompt,
    _strip_json_fences,
    extract_image_prompts,
    insert_images_into_prose,
)
from distill.llm import LLMError

# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

_SAMPLE_PROMPTS_JSON = json.dumps(
    [
        {
            "role": "hero",
            "prompt": "A wide-angle photo of a workshop table covered in blueprints",
            "alt": "Workshop table with blueprints",
            "after_heading": None,
            "mood": "reflective",
        },
        {
            "role": "inline",
            "prompt": "A close-up of tangled cables being untangled by steady hands",
            "alt": "Hands untangling cables",
            "after_heading": "The Refactoring",
            "mood": "reflective",
        },
    ]
)

_SAMPLE_PROSE = """\
# My Great Essay

Some intro paragraph about the topic.

A second paragraph providing more context and detail about the overall
theme of the essay before we dive into the first section.

## The Refactoring

Details about refactoring the codebase.

## The Outcome

Final results and lessons learned."""


# ---------------------------------------------------------------------------
# _strip_json_fences
# ---------------------------------------------------------------------------


class TestStripJsonFences:
    def test_strips_json_fence(self):
        text = '```json\n[{"role": "hero"}]\n```'
        assert _strip_json_fences(text) == '[{"role": "hero"}]'

    def test_strips_bare_fence(self):
        text = '```\n[{"role": "hero"}]\n```'
        assert _strip_json_fences(text) == '[{"role": "hero"}]'

    def test_plain_json_unchanged(self):
        text = '[{"role": "hero"}]'
        assert _strip_json_fences(text) == '[{"role": "hero"}]'

    def test_preamble_text_finds_array(self):
        text = 'Here is the JSON:\n[{"role": "hero"}]'
        result = _strip_json_fences(text)
        assert result.startswith("[")


# ---------------------------------------------------------------------------
# extract_image_prompts — LLM mocked
# ---------------------------------------------------------------------------


class TestExtractImagePrompts:
    @patch("distill.llm.call_claude")
    def test_returns_prompts_on_success(self, mock_call):
        mock_call.return_value = _SAMPLE_PROMPTS_JSON

        prompts = extract_image_prompts("# Essay\n\nSome text.")

        assert len(prompts) == 2
        assert prompts[0].role == "hero"
        assert prompts[0].after_heading is None
        assert prompts[1].role == "inline"
        assert prompts[1].after_heading == "The Refactoring"

    @patch("distill.llm.call_claude")
    def test_returns_empty_on_llm_error(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI failed (exit 1)")

        prompts = extract_image_prompts("# Essay")
        assert prompts == []

    @patch("distill.llm.call_claude")
    def test_returns_empty_on_invalid_json(self, mock_call):
        mock_call.return_value = "This is not valid JSON at all"

        prompts = extract_image_prompts("# Essay")
        assert prompts == []

    @patch("distill.llm.call_claude")
    def test_strips_code_fences(self, mock_call):
        fenced = f"```json\n{_SAMPLE_PROMPTS_JSON}\n```"
        mock_call.return_value = fenced

        prompts = extract_image_prompts("# Essay")
        assert len(prompts) == 2
        assert prompts[0].role == "hero"

    @patch("distill.llm.call_claude")
    def test_returns_empty_on_timeout(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI timed out after 60s")

        prompts = extract_image_prompts("# Essay")
        assert prompts == []

    @patch("distill.llm.call_claude")
    def test_returns_empty_on_file_not_found(self, mock_call):
        mock_call.side_effect = LLMError("Claude CLI not found")

        prompts = extract_image_prompts("# Essay")
        assert prompts == []

    @patch("distill.llm.call_claude")
    def test_returns_empty_on_empty_response(self, mock_call):
        mock_call.return_value = ""

        prompts = extract_image_prompts("# Essay")
        assert prompts == []

    @patch("distill.llm.call_claude")
    def test_skips_malformed_entries(self, mock_call):
        data = [
            {"role": "hero", "prompt": "A scene", "alt": "desc", "after_heading": None},
            {"role": "inline"},  # missing required fields
        ]
        mock_call.return_value = json.dumps(data)

        prompts = extract_image_prompts("# Essay")
        assert len(prompts) == 1
        assert prompts[0].role == "hero"


# ---------------------------------------------------------------------------
# insert_images_into_prose
# ---------------------------------------------------------------------------


class TestInsertImagesIntoProse:
    def _make_prompts(self) -> list[ImagePrompt]:
        return [
            ImagePrompt(
                role="hero",
                prompt="A wide-angle shot",
                alt="Workshop table",
                after_heading=None,
                mood="reflective",
            ),
            ImagePrompt(
                role="inline",
                prompt="A close-up shot",
                alt="Hands untangling cables",
                after_heading="The Refactoring",
                mood="reflective",
            ),
        ]

    def test_inserts_hero_after_h1(self):
        prompts = self._make_prompts()
        paths = {0: "images/hero.png"}

        result = insert_images_into_prose(_SAMPLE_PROSE, prompts, paths)
        lines = result.split("\n")

        # H1 should be first, hero image immediately after
        h1_idx = next(i for i, line in enumerate(lines) if line.startswith("# "))
        assert lines[h1_idx + 1] == "![Workshop table](images/hero.png)"

    def test_inserts_inline_before_matching_h2(self):
        prompts = self._make_prompts()
        paths = {1: "images/refactoring.png"}

        result = insert_images_into_prose(_SAMPLE_PROSE, prompts, paths)
        lines = result.split("\n")

        # Find the image line
        img_idx = next(
            i for i, line in enumerate(lines) if "refactoring.png" in line
        )
        # The next line should be the matching H2
        assert lines[img_idx + 1] == "## The Refactoring"

    def test_returns_unchanged_prose_if_paths_empty(self):
        prompts = self._make_prompts()
        result = insert_images_into_prose(_SAMPLE_PROSE, prompts, {})
        assert result == _SAMPLE_PROSE

    def test_handles_missing_heading_appends_at_end(self):
        prompts = [
            ImagePrompt(
                role="inline",
                prompt="A scene",
                alt="Some image",
                after_heading="Nonexistent Section",
                mood="reflective",
            ),
        ]
        paths = {0: "images/fallback.png"}

        result = insert_images_into_prose(_SAMPLE_PROSE, prompts, paths)
        lines = result.split("\n")

        assert lines[-1] == "![Some image](images/fallback.png)"

    def test_both_hero_and_inline_inserted(self):
        prompts = self._make_prompts()
        paths = {0: "images/hero.png", 1: "images/refactoring.png"}

        result = insert_images_into_prose(_SAMPLE_PROSE, prompts, paths)

        assert "![Workshop table](images/hero.png)" in result
        assert "![Hands untangling cables](images/refactoring.png)" in result

    def test_skips_prompts_without_paths(self):
        prompts = self._make_prompts()
        # Only provide path for index 0, not 1
        paths = {0: "images/hero.png"}

        result = insert_images_into_prose(_SAMPLE_PROSE, prompts, paths)

        assert "![Workshop table](images/hero.png)" in result
        assert "refactoring.png" not in result

    def test_invalid_index_in_paths_ignored(self):
        prompts = self._make_prompts()
        paths = {99: "images/invalid.png"}

        result = insert_images_into_prose(_SAMPLE_PROSE, prompts, paths)
        assert result == _SAMPLE_PROSE

    def test_prose_without_h1_hero_at_beginning(self):
        prose = "Some text without any heading.\n\nMore text."
        prompts = [
            ImagePrompt(
                role="hero",
                prompt="A scene",
                alt="Hero image",
                after_heading=None,
                mood="reflective",
            ),
        ]
        paths = {0: "images/hero.png"}

        result = insert_images_into_prose(prose, prompts, paths)
        lines = result.split("\n")
        assert lines[0] == "![Hero image](images/hero.png)"

    def test_back_to_back_images_prevented(self):
        """Inline image too close to hero should be dropped."""
        short_prose = (
            "# Title\n\nOne short paragraph.\n\n## Section\n\nMore text here."
        )
        prompts = [
            ImagePrompt(
                role="hero",
                prompt="Hero scene",
                alt="Hero",
                after_heading=None,
                mood="reflective",
            ),
            ImagePrompt(
                role="inline",
                prompt="Inline scene",
                alt="Inline",
                after_heading="Section",
                mood="technical",
            ),
        ]
        paths = {0: "images/hero.png", 1: "images/inline.png"}

        result = insert_images_into_prose(short_prose, prompts, paths)

        # Hero should be present
        assert "![Hero](images/hero.png)" in result
        # Inline should be dropped because it's too close to hero
        assert "![Inline](images/inline.png)" not in result
