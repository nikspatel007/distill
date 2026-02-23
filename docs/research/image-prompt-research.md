# Image Prompt Engineering Research

Research into improving the extraction and generation prompts used in the Distill blog image pipeline. Current system: Claude (Sonnet) extracts scene descriptions from essays, Gemini (Nano Banana Pro / gemini-3-pro-image-preview) generates images from those descriptions with a style prefix prepended.

---

## 1. What Is Wrong With the Current Prompts

### 1.1 Extraction Prompt (src/intake/images.py)

**Problem: JSON output compliance is unreliable.**

The prompt says "Output ONLY a JSON array" but Claude frequently produces preamble text before the JSON. The codebase already has a `_strip_json_fences()` fallback that hunts for `[` in the response, proving this is a known, recurring failure. The root cause is that a single instruction line ("Output ONLY a JSON array") is too weak to override Claude's default conversational behavior. Claude's instinct is to acknowledge, explain, then produce the output. Without structural reinforcement of the JSON-only constraint, the instruction gets overwhelmed by the model's tendency to be helpful.

**Problem: Scene descriptions are generic and literal.**

The prompt asks for "photorealistic illustrations" and provides two example starters: "A wide-angle photograph of ..." and "A close-up photograph of ...". This constrains the extraction model into two composition modes and one visual register (photorealism). Every essay gets the same treatment: a wide-angle establishing shot and a close-up detail shot. There is no guidance on visual metaphor, no vocabulary of photographic styles, no mood-matching, and no anti-repetition mechanism.

For example, an essay about "healthy friction between agents catching real bugs" could inspire imagery of tectonic plates grinding against each other to reveal crystals, or two chess clocks facing each other, or sandpaper revealing woodgrain. Instead, the current prompt would likely produce "robotic arms on an assembly line inspecting parts" -- a literal translation with no conceptual depth.

**Problem: No mood or tone signal is extracted from the essay.**

The prompt treats all essays identically. A reflective essay about measurement paralysis gets the same visual treatment as an energetic essay about compounding pipelines. There is no instruction to analyze the essay's emotional register and translate it into visual parameters (warm/cool palette, tight/expansive framing, high/low contrast, dynamic/static composition).

**Problem: The "after_heading" field is fragile.**

Requiring exact H2 heading text match is brittle. A minor formatting difference (em-dash vs hyphen, trailing whitespace) breaks placement. The extraction prompt provides no fallback guidance for when headings do not match cleanly.

### 1.2 Style Prefix (src/images.py)

**Problem: Every image looks the same.**

The current prefix is:

```
Cinematic photorealistic photograph, high contrast lighting,
cool blue-tinted shadows, clean minimalist composition,
shallow depth of field, technical subject matter.
No text, no logos, no UI elements. --
```

This locks every generated image into an identical visual signature: cool blue tones, shallow DOF, high contrast, cinematic framing. Across a blog with a dozen posts, the images become indistinguishable wallpaper. The reader's eye stops registering them because they all carry the same visual energy.

**Problem: "Technical subject matter" is vague and pushes toward cliche.**

Nano Banana Pro has a documented bias toward realism and "median behavior" -- it corrects prompts toward the most common interpretation. Saying "technical subject matter" reinforces the model's tendency to generate generic workshop/lab/server-room imagery. It does not differentiate between essays about coordination overhead, content pipelines, or branch-merge failures.

**Problem: The style prefix fights against the scene description.**

When you prepend a rigid style prefix to a scene description, you get a collision. The prefix says "cool blue-tinted shadows" but the scene might describe warm morning light in a workshop. Nano Banana Pro will try to satisfy both, producing incoherent images where cool and warm light sources fight. The prefix should complement the scene, not contradict it.

**Problem: No variety mechanism exists.**

There is no system to vary style per essay, per image role (hero vs inline), or per mood. The architecture concatenates a single static string to every prompt. Variety must be designed into the system.

---

## 2. Best Practices Discovered From Research

### 2.1 Gemini / Nano Banana Pro Prompting (2025-2026)

Key findings from Google's official documentation and community guides:

**Describe scenes narratively, not as keyword lists.** Nano Banana Pro excels with descriptive paragraphs, not comma-separated modifier spam. "A weathered brass astrolabe sits on a dark walnut desk, backlit by late afternoon sun streaming through a single tall window" outperforms "brass astrolabe, dark desk, afternoon light, window, warm tones, 4K, masterpiece."

**Drop the quality-modifier spam.** "4K, trending on artstation, masterpiece, highly detailed" is no longer necessary and actively harmful. Nano Banana Pro understands natural language. These tokens waste context and can push the model toward over-rendered, generic output.

**Use photographic and cinematic language for precise control.** Specific terms produce specific results:
- Lens: "85mm portrait lens", "24mm wide-angle", "macro lens at f/2.8"
- Lighting: "Rembrandt lighting", "rim light from camera-left", "diffused overcast daylight"
- Film: "Kodachrome warm saturation", "bleach bypass desaturation", "cross-processed greens"
- Composition: "rule-of-thirds placement", "Dutch angle", "bird's-eye view", "negative space on left for text overlay"

**Use positive framing, not negation.** Instead of "no people, no text, no clutter," describe what IS there: "an empty, still workspace with a single object centered on the surface." Nano Banana Pro handles inclusion better than exclusion.

**Specify materials and textures explicitly.** "Brushed aluminum with visible machining marks" is dramatically more effective than "metal surface." The model renders materials it can name.

**The model's realism bias is a feature for editorial photography.** Nano Banana Pro pushes prompts toward photorealism, which is ideal for editorial illustration. Lean into this rather than fighting it with surreal prompts. The editorial register -- a scene that could plausibly be photographed but was carefully staged -- is the sweet spot.

### 2.2 Enforcing JSON Output From Claude CLI

The current codebase calls Claude via `subprocess.run(["claude", "-p", "--model", "sonnet"])`. This is the Claude Code CLI in "print" mode, which does not support the API's structured output features (json_schema, tool_use). JSON enforcement must happen through prompt engineering alone.

**Effective prompt-only techniques for JSON enforcement:**

1. **Sandwich the constraint.** State the JSON-only rule at the beginning AND repeat it at the end, immediately before the input. Models weight instructions at the boundaries of prompts more heavily than buried mid-text.

2. **Use an explicit "start your response with" instruction.** Tell Claude: "Begin your response with the opening bracket `[` -- do not write any text before it." This is the prompt-engineering equivalent of the deprecated prefilling technique.

3. **Provide a complete, parseable example.** Not a schema -- an actual JSON array that could be parsed by `json.loads()`. This primes the model's pattern-completion toward valid JSON.

4. **Use the Claude Code CLI `--output-format json` flag.** While this wraps the response in a metadata envelope, the actual content field will be the model's raw output. This does not directly enforce JSON content, but it signals to the model that the output will be machine-parsed.

5. **Add a validation threat.** "Your output will be passed directly to `json.loads()`. If it is not valid JSON, the pipeline will fail silently and no images will be generated." Models respond to stated consequences.

### 2.3 Editorial Illustration and Visual Metaphor

Research from journalism and editorial design communities:

**The Axios method for editorial illustration:** (1) Identify the key abstract concept in the story. (2) Brainstorm physical-world metaphors for that concept. (3) Design a scene that makes the metaphor visually immediate. This is a three-step conceptual process, not a "describe what the article is about" process.

**Visual metaphor is harder for AI than literal illustration.** Current diffusion models (including Nano Banana Pro) struggle with genuine abstraction. The workaround is to use CONCRETE objects arranged in METAPHORICAL relationships. Do not ask for "an abstract representation of coordination overhead." Ask for "two hourglasses connected by a narrow brass tube, sand flowing slowly between them while a pocket watch lies face-down on the table between them."

**Professional editorial illustrations vary their visual register per piece.** The Atlantic, Wired, and similar publications do not use one visual style across all articles. A piece about burnout gets warm, desaturated, intimate framing. A piece about scaling infrastructure gets cool, expansive, architectural framing. A piece about technical debt gets weathered textures and signs of wear. The style IS part of the editorial message.

**The metaphor should be extractable from the essay's thesis, not its topic.** An essay about multi-agent coordination is not "about" robots -- it is about the tension between speed and thoroughness, or the value of friction, or the cost of communication. The image should visualize the THESIS (friction produces quality) not the TOPIC (multi-agent systems).

### 2.4 Color and Mood Vocabulary

Mapping essay moods to visual palettes (synthesized from color theory research):

| Essay Mood | Palette | Lighting | Composition |
|---|---|---|---|
| Reflective / Analytical | Cool blue-grey, desaturated | Diffused overcast, even | Symmetrical, centered, still |
| Energetic / Building | Warm amber, golden | Golden hour, directional | Dynamic diagonals, leading lines |
| Cautionary / Tension | Teal and orange contrast | Hard directional, deep shadows | Off-center, negative space, tight crop |
| Triumphant / Breakthrough | High saturation, vivid | Bright, high-key | Expansive, wide-angle, depth |
| Intimate / Personal | Warm muted earth tones | Soft window light | Close framing, shallow DOF |
| Technical / Systematic | Cool neutral, high clarity | Clean studio lighting | Geometric, orderly, overhead |

---

## 3. Proposed New Extraction Prompt

This replaces `_EXTRACTION_PROMPT` in `src/intake/images.py`. Key changes: stronger JSON enforcement, mood analysis, metaphorical depth, varied photographic vocabulary, and anti-repetition.

```python
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
```

### What Changed and Why

1. **"Visual editor" not "art director."** Reframes the role from aesthetic control to editorial judgment about meaning.

2. **Explicit 4-step process (THESIS, MOOD, METAPHOR, STYLE).** Forces Claude to think about the essay's argument before describing any image. This prevents the "illustrate the topic" failure mode.

3. **Concrete bad/good examples.** Demonstrates the difference between literal illustration and visual metaphor using scenarios that match the actual blog content.

4. **Photographic vocabulary lists.** Provides a menu of lens, lighting, and palette options so Claude can vary these per image instead of defaulting to the same "cinematic blue" look.

5. **"mood" field added to output.** This feeds forward into the style prefix system so the generator can match visual treatment to essay tone.

6. **40-80 word scene descriptions.** Forces narrative depth rather than keyword lists. Nano Banana Pro works better with descriptive paragraphs.

7. **Explicit blacklist of cliches.** "Server rooms, circuit boards, glowing nodes, abstract data streams, robots on assembly lines" -- the specific failure modes observed in practice.

8. **Triple JSON enforcement.** The constraint appears at the top ("Your entire response must be a single valid JSON array"), has a consequences statement ("pipeline will fail silently"), and is restated at the bottom ("Start your response with `[` immediately"). Boundary placement maximizes compliance.

---

## 4. Proposed New Style Prefix System

Replace the single `DEFAULT_STYLE_PREFIX` constant in `src/images.py` with a mood-indexed dictionary. The `mood` field from the extraction prompt selects the appropriate style treatment.

```python
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
        "at f/2, tight crop with the subject off-center. Unsettled atmosphere, "
        "something slightly wrong. "
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

# Fallback for unrecognized moods
DEFAULT_STYLE_PREFIX = STYLE_PREFIXES["reflective"]
```

### Integration with ImageGenerator

The `generate()` method would accept an optional `mood` parameter:

```python
def generate(
    self,
    prompt: str,
    *,
    output_path: Path,
    aspect_ratio: str = "16:9",
    mood: str | None = None,
) -> Path | None:
    style = STYLE_PREFIXES.get(mood or "", self.style_prefix)
    full_prompt = style + prompt
    # ... rest of generation logic unchanged
```

### What Changed and Why

1. **Eight distinct visual registers.** Instead of one blue-tinted look, each mood gets its own lighting, palette, lens choice, and composition guidance. Two blog posts with different moods will produce visibly different imagery.

2. **Specific photographic parameters.** Each prefix names a lens focal length, aperture, lighting setup, and palette. Nano Banana Pro responds well to precise technical photography language.

3. **Narrative style descriptions.** Following the Gemini prompting research, each prefix reads as a short paragraph rather than a keyword list. This produces more coherent images.

4. **"No text, no logos, no UI elements" retained in every prefix.** This is the one constraint that must remain universal because Nano Banana Pro will otherwise add text.

5. **Mood-to-style mapping is deterministic.** The extraction prompt classifies the essay mood; the generator looks up the corresponding prefix. No LLM call is needed for style selection -- it is a dictionary lookup.

---

## 5. Updated ImagePrompt Dataclass

The `ImagePrompt` dataclass needs a `mood` field to carry the style signal:

```python
@dataclass
class ImagePrompt:
    """A single image generation prompt with placement metadata."""

    role: str         # "hero" or "inline"
    prompt: str       # description for the image generator
    alt: str          # alt text for markdown image
    after_heading: str | None  # H2 heading (None for hero)
    mood: str         # essay mood for style prefix selection
```

---

## 6. Before/After Examples

### Example 1: "How Healthy Friction Between Agents Catches Real Bugs"

**Before (current system would produce):**

Extraction:
```json
[
  {
    "role": "hero",
    "prompt": "A wide-angle photograph of two robotic arms inspecting a circuit board on an assembly line, blue LED lighting, industrial setting",
    "alt": "Robotic arms inspecting electronics",
    "after_heading": null
  }
]
```

Style prefix applied: `Cinematic photorealistic photograph, high contrast lighting, cool blue-tinted shadows...`

Result: Blue-tinted industrial robots. Generic. Could be the hero image for any tech article.

**After (proposed system would produce):**

Extraction:
```json
[
  {
    "role": "hero",
    "prompt": "Two rough-hewn granite millstones stacked vertically in a traditional stone mill, golden wheat kernels caught in the grinding surface where the stones meet. Fine white flour cascades from the edge into a weathered wooden trough below. Late afternoon sunlight streams through a dusty mill window, catching flour particles suspended in the air. Shot on a 50mm lens at f/2.8, the focus plane on the grinding surface where friction transforms grain into flour.",
    "alt": "Millstones grinding wheat into flour in afternoon light",
    "after_heading": null,
    "mood": "energetic"
  },
  {
    "role": "inline",
    "prompt": "A close-up of a hand-forged iron gate latch, the bolt mechanism visible through a cross-section cutaway. Three separate pins must align for the bolt to slide — each pin machined to a different depth. The latch sits on a weathered oak door frame. Overcast daylight provides even illumination across the mechanism. 100mm macro lens, f/5.6, revealing the precision of each component.",
    "alt": "Cross-section of a gate latch with three alignment pins",
    "after_heading": "The Architecture That Produces Useful Friction",
    "mood": "technical"
  }
]
```

Style prefix applied (for hero, mood="energetic"): `Dynamic editorial photograph. Warm golden-hour directional light casting long shadows. 35mm lens at f/2.8...`

Result: Warm, tactile, metaphorical. The millstones embody the thesis: friction is the mechanism that transforms raw material into something useful. Visually distinct from any other post.

### Example 2: "Building a Content Pipeline That Compounds"

**Before:**
```json
[
  {
    "role": "hero",
    "prompt": "A wide-angle photograph of data flowing through translucent tubes in a futuristic laboratory, blue neon lighting",
    "alt": "Data flowing through tubes",
    "after_heading": null
  }
]
```

Result: Another blue-tinted tech scene. Indistinguishable from the friction essay's hero.

**After:**
```json
[
  {
    "role": "hero",
    "prompt": "A weathered leather-bound notebook lies open on a dark walnut desk, its current page filled with dense handwriting. Beneath it, a stack of three older notebooks of the same kind, each progressively more worn. The open page has an arrow drawn in the margin pointing to a dog-eared page visible in the notebook below. A brass fountain pen rests in the spine. Warm window light from the right illuminates dust motes and the amber tones of old paper. 85mm lens at f/2, focus on the margin annotation.",
    "alt": "Open notebook referencing annotations in older journals beneath it",
    "after_heading": null,
    "mood": "intimate"
  },
  {
    "role": "inline",
    "prompt": "An overhead bird's-eye photograph of a jeweler's workbench. A magnifying loupe sits beside a finished ring, but the compelling detail is the workbench surface itself: concentric rings of metal filings, each ring a slightly different alloy color — copper, silver, gold — layered over months of work. The accumulated residue has become beautiful. Clean studio lighting, 50mm lens, f/8 for full sharpness across the flat plane.",
    "alt": "Jeweler workbench with layered metal filings forming rings",
    "after_heading": "The Core Loop: Generate, Extract, Inject",
    "mood": "technical"
  }
]
```

Style prefix applied (for hero, mood="intimate"): `Quiet editorial photograph. Soft window light from camera-left, warm muted earth tones...`

Result: The compounding thesis is embodied in notebooks that reference each other -- knowledge that literally stacks and cross-references. The inline image shows accumulation as beauty (filings becoming pattern). Neither image contains a computer, a server, or a glowing node.

### Example 3: "When Coordination Overhead Exceeds Task Value"

**Before:**
```json
[
  {
    "role": "hero",
    "prompt": "A close-up photograph of tangled network cables in a server room, blue and red lights blinking",
    "alt": "Tangled network cables in server room",
    "after_heading": null
  }
]
```

**After:**
```json
[
  {
    "role": "hero",
    "prompt": "A heavy brass balance scale on a dark marble surface. On one pan, a single small brass key. On the other pan, an elaborate stack of official-looking wax seals, ribbons, and stamped documents -- the bureaucratic apparatus required to authorize the use of the key. The documents pan weighs far more, tilting the scale dramatically. Hard directional light from camera-left creates deep shadows. Teal shadows against warm brass highlights. 85mm lens, f/2.8, focus on the tipping point of the beam.",
    "alt": "Balance scale weighed down by paperwork opposite a small key",
    "after_heading": null,
    "mood": "cautionary"
  },
  {
    "role": "inline",
    "prompt": "A pocket watch disassembled on a white cotton cloth. The main spring, escapement, and gears are laid out in an orderly exploded view. Beside them, a second pocket watch of identical make sits intact and ticking. The disassembled watch cannot tell time because it is being measured. Clean overcast daylight, slight cool cast. 100mm macro, f/4, shallow enough to soften the background while keeping the components sharp.",
    "alt": "Disassembled pocket watch beside an identical working one",
    "after_heading": "The Measurement Trap",
    "mood": "reflective"
  }
]
```

Style prefix applied (for hero, mood="cautionary"): `Tense editorial photograph. Hard directional lighting from a single source, deep shadows with teal-and-orange color contrast...`

Result: The balance scale immediately communicates "overhead exceeds value" without any tech imagery. The disassembled watch embodies the measurement trap: you cannot measure and use the thing simultaneously. Both are visually and tonally distinct from the other essays' images.

---

## 7. Implementation Notes

### Changes Required (summary, not implementation)

1. **`src/intake/images.py`**: Replace `_EXTRACTION_PROMPT`. Add `mood` field to `ImagePrompt` dataclass. Update `extract_image_prompts()` to parse the `mood` field.

2. **`src/images.py`**: Replace `DEFAULT_STYLE_PREFIX` with `STYLE_PREFIXES` dictionary. Add `mood` parameter to `ImageGenerator.generate()`. Look up prefix by mood with fallback.

3. **Caller code** (wherever `extract_image_prompts` and `generate` are chained): Pass `prompt.mood` through to the generator.

4. **Tests**: Update test fixtures for the new `mood` field. Add tests for style prefix selection. Add tests for JSON-only output compliance (mock Claude responses with preamble and verify `_strip_json_fences` still works as fallback).

### Risk: Nano Banana Pro Realism Bias

Nano Banana Pro has a documented tendency to "correct" prompts toward median photorealistic behavior. Highly abstract or surreal metaphors may be flattened. The proposed prompts work with this bias by using concrete physical objects in metaphorical arrangements rather than requesting abstract concepts directly. A balance scale with documents is a real physical scene that happens to be a metaphor -- the model will render it faithfully.

### Risk: Claude CLI JSON Compliance

Even with triple enforcement, some fraction of Claude responses may include preamble text. The existing `_strip_json_fences()` function should be retained as a safety net. The proposed prompt dramatically reduces the failure rate but cannot eliminate it entirely without API-level structured outputs (not available via CLI subprocess).

### Future Enhancement: Structured Outputs via API

If the pipeline migrates from `claude -p` subprocess calls to the Anthropic Python SDK, the `output_config.format` parameter with `type: "json_schema"` would guarantee valid JSON output with zero parsing failures. This would eliminate the need for `_strip_json_fences()` entirely. The extraction prompt's JSON enforcement language could then be simplified since the constraint would be enforced at the decoding level.

---

## Sources

- [How to prompt Gemini 2.5 Flash Image Generation for the best results](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/) -- Google Developers Blog
- [Nano Banana Pro image generation in Gemini: Prompt tips](https://blog.google/products-and-platforms/products/gemini/prompting-tips-nano-banana-pro/) -- Google Blog
- [Ultimate Nano Banana Pro Prompting Guide](https://www.atlabs.ai/blog/the-ultimate-nano-banana-pro-prompting-guide-mastering-gemini-3-pro-image) -- Atlabs AI
- [Nano Banana Pro is the best AI image generator, with caveats](https://minimaxir.com/2025/12/nano-banana-pro/) -- Max Woolf
- [Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) -- Claude API Docs
- [Prefill Claude's response for greater output control](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prefill-claudes-response) -- Claude API Docs
- [How to Use AI Image Tools to Make Blog Hero Images](https://www.chrisemery.com/ai-blog-art/) -- Chris Emery
- [Simple Composition Tricks: Color and Mood Edition](https://civitai.com/articles/18284/simple-composition-tricks-to-instantly-improve-ai-images-with-prompts-color-and-mood-edition) -- Civitai
- [Prompt Design for Image Generation](https://aiprompttheory.com/prompt-design-for-image-generation/) -- AI Prompt Theory
- [Nano Banana Pro Prompting Guide](https://www.imagine.art/blogs/nano-banana-pro-prompt-guide) -- ImagineArt
- [Gemini 3 prompting guide](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/start/gemini-3-prompting-guide) -- Google Cloud Documentation
