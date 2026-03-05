---
name: voice-memory
description: Use when generating any written content (journal, blog, social, digest) to apply the user's learned voice profile. Also use after the user edits content in Studio to extract new voice patterns from the chat history.
---

# Voice Memory

## Overview

Voice Memory is a closed-loop system that learns how you write from your Studio editing sessions. When you edit AI-generated content and give feedback like "too formal" or "use the actual bug name," those instructions accumulate into a voice profile that improves all future content generation.

**Two modes:**

1. **Extract** — Mine Studio chat histories for voice patterns, update the voice profile
2. **Apply** — Inject voice rules into synthesis prompts (journal, blog, social, digest)

## How It Works

```
Studio editing sessions (chat_history in ContentStore)
    → LLM extracts voice patterns (style rules + examples)
    → VoiceProfile stored in .distill-voice.json
    → Injected into all synthesis prompts via render_for_prompt()
    → Next generated content sounds more like you
    → You edit less → cycle reinforces
```

## Voice Profile Format

The voice profile lives at `{OUTPUT_DIR}/.distill-voice.json`:

```json
{
  "version": 1,
  "extracted_from": 12,
  "last_updated": "2026-03-04T10:00:00Z",
  "rules": [
    {
      "id": "v-001",
      "rule": "Use direct statements. Remove hedging words like 'seems', 'might', 'perhaps', 'arguably'.",
      "confidence": 0.9,
      "source_count": 8,
      "category": "tone",
      "examples": {
        "before": "This approach might be more efficient.",
        "after": "This approach is faster."
      }
    },
    {
      "id": "v-002",
      "rule": "Name specific tools, bugs, and metrics. Never say 'the framework' when you can say 'FastAPI'.",
      "confidence": 0.7,
      "source_count": 5,
      "category": "specificity",
      "examples": {
        "before": "We encountered a performance issue in the API layer.",
        "after": "The /api/graph/nodes endpoint was taking 3.2s due to N+1 queries in SQLAlchemy."
      }
    }
  ]
}
```

### Rule Categories

| Category | What it captures |
|----------|-----------------|
| **tone** | Formality level, hedging, confidence, humor |
| **specificity** | Concrete vs abstract, naming things, metrics |
| **structure** | Sentence length, paragraph rhythm, transitions |
| **vocabulary** | Preferred/avoided words, jargon policy |
| **framing** | How setbacks are described, how wins are shared |

### Confidence Scoring

- Each rule has a `confidence` score (0.0–1.0) and a `source_count`
- Rules seen in 1–2 edits start at 0.3 (tentative)
- Rules confirmed across 3–5 edits rise to 0.6 (established)
- Rules confirmed across 6+ edits rise to 0.9 (core voice)
- Contradicted rules decay: confidence halved per contradiction
- Rules below 0.1 confidence are pruned on next extraction

## Mode 1: Extract Voice Patterns

### When to Run

- After the user finishes editing a post in Studio
- On a batch schedule (e.g., weekly via `distill voice extract`)
- When the user explicitly asks to update their voice profile

### Extraction Process

1. **Load ContentStore** from `.distill-content-store.json`
2. **Filter records** that have `chat_history` with 2+ messages (evidence of editing)
3. **Skip already-processed** records (track `extracted_from` slugs in voice profile)
4. **For each unprocessed record**, send chat history to LLM with extraction prompt:

```
You are analyzing a conversation between a user and an AI writing assistant.
The user edited AI-generated content and gave feedback about style, tone, and word choice.

Extract voice rules from this conversation. Each rule should be:
- A specific, actionable instruction (not vague like "write better")
- Grounded in what the user actually said or changed
- Categorized as: tone, specificity, structure, vocabulary, or framing

For each rule, provide:
- The rule as an imperative instruction
- A before/after example from the conversation
- The category

Return JSON array of rules. Only extract rules with clear evidence.
Do NOT extract content-specific preferences (topic choices, what to cover).
ONLY extract style/voice patterns (how to write, not what to write).
```

5. **Merge new rules** with existing profile:
   - If a new rule matches an existing one (LLM similarity check), increase `source_count` and recalculate confidence
   - If new rule contradicts existing, decrease existing confidence
   - If genuinely new, add with starting confidence 0.3

6. **Save** updated `.distill-voice.json`

### Implementation Location

- **Model**: `src/voice/models.py` — `VoiceRule`, `VoiceProfile` (Pydantic)
- **Service**: `src/voice/services.py` — `extract_voice_rules()`, `merge_rules()`, `load_voice_profile()`, `save_voice_profile()`
- **Prompts**: `src/voice/prompts.py` — extraction prompt, merge/similarity prompt
- **CLI**: `distill voice extract --output ./insights` and `distill voice show`

## Mode 2: Apply Voice Rules

### Injection Points

Voice rules are injected into prompts via `voice_profile.render_for_prompt()`, following the same pattern as `EditorialStore.render_for_prompt()` and `UnifiedMemory.render_for_prompt()`.

The rendered output looks like:

```markdown
## Your Voice (learned from editing history)

IMPORTANT: These rules reflect how the author actually writes, learned from
their edits. Follow them precisely — they override generic style guidelines.

### Tone
- Use direct statements. Remove hedging words like 'seems', 'might', 'perhaps'. (confidence: high)
- Frame technical setbacks as discoveries, not failures. (confidence: medium)

### Specificity
- Name specific tools, bugs, and metrics. Say 'FastAPI' not 'the framework'. (confidence: high)

### Structure
- Vary sentence length. Mix 5-word punches with 25-word explanations. (confidence: medium)
```

### Where It Gets Injected

| Pipeline | File | Injection point |
|----------|------|----------------|
| **Journal** | `src/journal/services.py` | `DailyContext` — appended to system prompt |
| **Blog (weekly)** | `src/blog/services.py` | `_render_weekly_prompt()` — after editorial notes |
| **Blog (thematic)** | `src/blog/services.py` | `_render_thematic_prompt()` — after editorial notes |
| **Social adaptation** | `src/blog/services.py` | `adapt_for_platform()` — prepended to prose input |
| **Intake digest** | `src/intake/prompts.py` | `get_unified_intake_prompt()` — after memory context |

### Confidence Filtering

Only rules above a threshold are injected:
- **Journal/Blog system prompts**: confidence >= 0.5 (established rules only)
- **Social adaptation**: confidence >= 0.3 (more experimental, shorter content)

### Conflict Resolution

Voice rules take precedence over hardcoded prompt style guidelines when they conflict. The injection includes `"These rules override generic style guidelines"` to make this explicit to the LLM.

However, voice rules do NOT override:
- Editorial notes (user's per-post steering is intentional)
- Structural requirements (word count, format constraints)
- Banned patterns list (these exist for quality reasons)

## CLI Commands

```bash
# Extract voice patterns from all unprocessed Studio edits
distill voice extract --output ./insights

# Show current voice profile
distill voice show

# Show rules by category
distill voice show --category tone

# Reset voice profile (start fresh)
distill voice reset --output ./insights

# Manually add a voice rule
distill voice add "Always use Oxford commas" --category vocabulary
```

## File Structure

```
src/voice/
  __init__.py
  models.py       # VoiceRule, VoiceProfile (Pydantic)
  services.py     # extract, merge, load, save, render_for_prompt
  prompts.py      # LLM prompts for extraction and merging
```

## Testing Strategy

- Unit tests for rule merging (confidence math, dedup, contradiction decay)
- Unit tests for `render_for_prompt()` (category grouping, confidence filtering)
- Integration test: mock chat history → extract → verify rules
- Integration test: inject rules into blog prompt → verify presence in rendered prompt
- Tests mirror source: `tests/voice/test_models.py`, `test_services.py`, `test_prompts.py`

## Key Design Decisions

1. **Chat history, not text diffs** — The user's explicit feedback ("too formal") is higher signal than reverse-engineering style from before/after text.
2. **Confidence decay, not deletion** — Wrong rules fade naturally instead of being hard-deleted, allowing recovery if the user changes their mind.
3. **Category-based rendering** — Rules are grouped by category in prompts so the LLM can apply them systematically, not as a grab-bag.
4. **Override hierarchy** — Voice rules > hardcoded prompts, but editorial notes > voice rules. The user's per-post intent always wins.
5. **JSON storage** — Follows existing patterns (`.distill-notes.json`, `.distill-content-store.json`). No new storage dependencies.
