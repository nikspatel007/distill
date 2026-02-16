"""Image prompt extraction and insertion for blog posts.

Uses Claude CLI to extract visual scene descriptions from essay prose,
then inserts generated image references into the markdown.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ImagePrompt:
    """A single image generation prompt with placement metadata."""

    role: str  # "hero" or "inline"
    prompt: str  # description for the image generator
    alt: str  # alt text for markdown image
    after_heading: str | None  # H2 heading this image relates to (None for hero)
    mood: str  # essay mood for style prefix selection


_EXTRACTION_PROMPT = """\
You are a visual editor for a technical journal. Your job is to produce \
image generation prompts that work as VISUAL METAPHORS, not literal illustrations.

CRITICAL: Your entire response must be a single valid JSON array. \
Begin your response with `[` — no preamble, no explanation, no markdown fences. \
Your output will be passed directly to json.loads(). Any non-JSON text will \
cause a silent pipeline failure.

PROCESS — follow these steps in order:

1. THESIS: Identify the essay's central argument or tension (not its topic).
2. MOOD: Classify the essay's emotional register as one of:
   reflective, energetic, cautionary, triumphant, intimate, technical, playful, somber.
3. METAPHOR: For each image, find a concrete physical-world scene that embodies
   the thesis. Do NOT illustrate the topic literally.
   - BAD: An essay about multi-agent coordination → "robots on an assembly line"
   - GOOD: An essay about productive friction → "two millstones grinding wheat,
     golden flour cascading into a wooden bowl, late afternoon light"
   - BAD: An essay about content pipelines → "data flowing through tubes"
   - GOOD: An essay about compounding knowledge → "a handwritten notebook open
     beside a stack of older notebooks, the newest page referencing a margin
     note from a weathered volume beneath it"
4. STYLE: Choose photographic parameters that match the mood. VARY these across
   images. Do not default to the same lens, lighting, and palette for every image.

   Lens vocabulary: 24mm wide-angle, 35mm street, 50mm standard, 85mm portrait,
   100mm macro, 135mm telephoto, tilt-shift miniature.

   Lighting vocabulary: golden hour, blue hour, overcast diffusion, Rembrandt,
   rim light, split lighting, chiaroscuro, high-key studio, low-key dramatic,
   window light, candlelight, neon glow, dappled forest light.

   Palette vocabulary: warm amber, cool steel-blue, teal-and-orange contrast,
   desaturated earth tones, high-saturation vivid, monochrome sepia,
   muted pastels, bleach-bypass silver.

RULES:
- The first item MUST have role "hero" — the essay's central visual metaphor.
- Include 1-2 items with role "inline" — metaphors for specific sections.
- Each "prompt" must describe a SCENE as a narrative paragraph (40-80 words).
  Include: subject, materials/textures, spatial arrangement, lighting direction
  and quality, color temperature, lens/DOF choice, and atmosphere.
- NEVER mention: text, typography, logos, UI, code, screens, or keyboards.
- NEVER use generic tech imagery: server rooms, circuit boards, glowing nodes,
  abstract data streams, or robots on assembly lines.
- "after_heading" must match an exact ## heading from the essay (null for hero).
- "alt" is accessible alt-text, under 12 words, describing the physical scene.
- "mood" is the essay mood from step 2 (used for style prefix selection).

JSON format — your response must be EXACTLY this structure, starting with `[`:
[
  {
    "role": "hero",
    "prompt": "Narrative scene description, 40-80 words...",
    "alt": "Short accessible description",
    "after_heading": null,
    "mood": "reflective"
  },
  {
    "role": "inline",
    "prompt": "Narrative scene description, 40-80 words...",
    "alt": "Short accessible description",
    "after_heading": "Exact H2 Heading Text",
    "mood": "reflective"
  }
]

Remember: Start your response with `[` immediately. No other text.

---

"""


def _strip_json_fences(text: str) -> str:
    """Strip markdown code fences and preamble from LLM JSON output."""
    from distill.llm import strip_json_fences

    return strip_json_fences(text)


def extract_image_prompts(prose: str) -> list[ImagePrompt]:
    """Extract image prompts from essay prose via Claude CLI.

    Calls Claude with the extraction prompt and the essay text, then parses
    the JSON response into a list of :class:`ImagePrompt` objects.

    Args:
        prose: The essay markdown to extract image prompts from.

    Returns:
        List of ImagePrompt objects. Returns empty list on any failure.
    """
    from distill.llm import LLMError, call_claude

    try:
        raw = call_claude(
            _EXTRACTION_PROMPT,
            prose,
            model="sonnet",
            timeout=60,
            label="image-prompts",
        )
    except LLMError as exc:
        logger.warning("Image prompt extraction failed: %s", exc)
        return []
    if not raw:
        logger.warning("Empty response from Claude CLI for image extraction")
        return []

    raw = _strip_json_fences(raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse image prompts JSON: %s", exc)
        return []

    if not isinstance(data, list):
        logger.warning("Image prompts response is not a list")
        return []

    prompts: list[ImagePrompt] = []
    for item in data:
        try:
            prompts.append(
                ImagePrompt(
                    role=item["role"],
                    prompt=item["prompt"],
                    alt=item["alt"],
                    after_heading=item.get("after_heading"),
                    mood=item.get("mood", "reflective"),
                )
            )
        except (KeyError, TypeError) as exc:
            logger.warning("Skipping malformed image prompt entry: %s", exc)

    return prompts


def insert_images_into_prose(
    prose: str,
    prompts: list[ImagePrompt],
    paths: dict[int, str],
) -> str:
    """Insert image markdown references into essay prose.

    Args:
        prose: The essay markdown text.
        prompts: List of image prompts with placement info.
        paths: Map of prompt index to relative image path.

    Returns:
        Modified prose with image references inserted. Returns unchanged prose
        if paths is empty.
    """
    if not paths:
        return prose

    lines = prose.split("\n")

    # Collect insertions: list of (line_index, image_markdown)
    insertions: list[tuple[int, str]] = []

    for idx, path in paths.items():
        if idx < 0 or idx >= len(prompts):
            continue
        prompt = prompts[idx]
        img_md = f"![{prompt.alt}]({path})"

        if prompt.role == "hero":
            # Insert after the first H1 line
            h1_line = _find_h1_line(lines)
            if h1_line is not None:
                insertions.append((h1_line + 1, img_md))
            else:
                # No H1 found — insert at the beginning
                insertions.append((0, img_md))
        else:
            # Inline: insert BEFORE the matching H2
            heading = prompt.after_heading
            if heading:
                h2_line = _find_h2_line(lines, heading)
                if h2_line is not None:
                    insertions.append((h2_line, img_md))
                else:
                    # Heading not found — append at end
                    insertions.append((len(lines), img_md))
            else:
                # No heading specified — append at end
                insertions.append((len(lines), img_md))

    # Sort: hero first (priority), then by position
    insertions.sort(key=lambda x: (0 if x[0] <= 1 else 1, x[0]))

    # Enforce minimum content gap: at least MIN_CONTENT_LINES non-blank lines
    # must separate any two images. Hero always wins.
    MIN_CONTENT_LINES = 2
    kept: list[tuple[int, str]] = []
    for pos, img_md in insertions:
        too_close = False
        for kept_pos, _ in kept:
            lo, hi = min(pos, kept_pos), max(pos, kept_pos)
            content_between = sum(
                1 for i in range(lo, hi) if lines[i].strip()
            )
            if content_between < MIN_CONTENT_LINES:
                too_close = True
                break
        if not too_close:
            kept.append((pos, img_md))
        else:
            logger.info("Skipping image too close to another (line %d): %s", pos, img_md[:60])

    # Insert in reverse order so earlier insertions don't shift later ones
    kept.sort(key=lambda x: x[0], reverse=True)

    for line_idx, img_md in kept:
        lines.insert(line_idx, img_md)

    return "\n".join(lines)


def _find_h1_line(lines: list[str]) -> int | None:
    """Find the line index of the first H1 heading."""
    for i, line in enumerate(lines):
        if line.startswith("# ") and not line.startswith("## "):
            return i
    return None


def _find_h2_line(lines: list[str], heading: str) -> int | None:
    """Find the line index of an H2 heading matching the given text."""
    target = f"## {heading}"
    for i, line in enumerate(lines):
        if line.strip() == target:
            return i
    return None
