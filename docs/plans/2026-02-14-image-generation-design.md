# Image Generation for TroopX Journal — Design

## Goal

Add AI-generated photorealistic images to daily intake digests. Each post gets a hero image (top) and 1-2 inline illustrations. Images are generated during synthesis using Nano Banana Pro (Gemini 3 Pro Image) via the `google-genai` SDK. The entire feature is optional — no API key means no images, no errors.

## Architecture

```
Prose synthesis completes (existing)
    ↓
Claude extracts image prompts from prose (new: src/intake/images.py)
    ↓ JSON: [{role: "hero", prompt: "...", after_heading: "..."}, ...]
    ↓
Nano Banana Pro generates images (new: src/images.py)
    ↓ Saves to output_dir/intake/images/{date}-hero.png, {date}-1.png, ...
    ↓
Markdown updated with image references
    ↓
Ghost publisher uploads images via /images/upload API
    ↓ Replaces local paths with Ghost CDN URLs
```

## Components

### 1. `src/images.py` — Image generation client

- `ImageGenerator` class wrapping `google-genai` SDK
- Optional dep: `google-genai` + `Pillow` (try/except, `_HAS_GENAI` flag)
- Env vars:
  - `GOOGLE_AI_API_KEY` — required, no key = feature off
  - `IMAGE_MODEL` — optional, defaults to `gemini-3-pro-image-preview`
  - `IMAGE_STYLE_PREFIX` — optional, defaults to TroopX cinematic style
- `is_configured() -> bool` — checks `_HAS_GENAI` and API key
- `generate(prompt: str, aspect_ratio: str, output_path: Path) -> Path | None`
- Returns `None` on any failure (graceful)

### 2. `src/intake/images.py` — Prompt extraction from prose

- `extract_image_prompts(prose: str) -> list[ImagePrompt]`
- `ImagePrompt` dataclass: `role` ("hero"|"inline"), `prompt` (str), `after_heading` (str|None)
- Calls `claude -p` with essay text + extraction prompt
- Returns empty list on failure

### 3. Integration into intake synthesis

- After prose synthesis, call `extract_image_prompts(prose)`
- For each prompt, call `ImageGenerator.generate()`
- Insert `![alt](images/{filename})` into markdown:
  - Hero: right after H1 title
  - Inline: before the relevant H2 heading
- Images saved to `output_dir/intake/images/`

### 4. Ghost publisher enhancement

- `GhostAPIClient.upload_image(path: Path) -> str` — POST to `/images/upload/`, returns CDN URL
- Before publishing, replace local `images/` paths with Ghost CDN URLs
- If upload fails, publish without images

## TroopX Visual Identity

Default style prefix prepended to every image prompt:

> Cinematic photorealistic photograph, high contrast lighting, cool blue-tinted shadows (#3b82f6), clean minimalist composition, shallow depth of field, technical subject matter. No text, no logos, no UI elements. —

Overridable via `IMAGE_STYLE_PREFIX` env var.

## Graceful Degradation

1. No `google-genai` package → `_HAS_GENAI = False` → skip
2. No `GOOGLE_AI_API_KEY` → `is_configured()` returns False → skip
3. Image generation fails → log warning, continue without images
4. Ghost image upload fails → publish without images
5. Claude prompt extraction fails → skip image generation

Pipeline never breaks. Posts always publish. Images are enhancement only.

## Visual Spec

- Hero image: 16:9 aspect ratio, placed after H1
- Inline images: 3:2 aspect ratio, placed before relevant H2
- Max 2 inline images per post (3 total including hero)
- Style: photorealistic metaphors that visualize the essay's central ideas
