# Voice Memory — Design Document

**Date:** 2026-03-04
**Status:** Approved
**Goal:** Learn the user's writing voice from Studio editing sessions and apply it to all content generation.

## Problem

Distill generates content that reads like AI wrote it — generic, hedged, lacking personality. The user must heavily edit every post in Studio before publishing. Each editing session teaches the same lessons: "be more direct," "use specific names," "shorter sentences." But that knowledge is lost — the next post starts from zero.

## Solution

A closed-loop voice learning system:

1. User edits a post in Studio, giving feedback via chat ("too formal," "use the actual metric")
2. Chat history is already saved in ContentStore
3. An extraction pass mines chat histories for voice patterns (style rules + before/after examples)
4. Rules accumulate in a `VoiceProfile` with confidence scores
5. Profile is injected into all future synthesis prompts
6. Generated content progressively sounds more like the user
7. Less editing needed → fewer corrections → profile stabilizes

## Architecture

```
ContentStore (.distill-content-store.json)
  └── chat_history per record
        │
        ▼
  Voice Extraction (LLM pass)
        │
        ▼
  VoiceProfile (.distill-voice.json)
  ├── rules[] with confidence scores
  ├── categories: tone, specificity, structure, vocabulary, framing
  └── decay/reinforcement on each extraction
        │
        ▼
  render_for_prompt()
        │
        ├── Journal prompts (system prompt)
        ├── Blog prompts (after editorial notes)
        ├── Social adaptation (prepended to prose)
        └── Intake digest (after memory context)
```

## Data Model

### VoiceRule

| Field | Type | Description |
|-------|------|-------------|
| id | str | Unique identifier (v-001, v-002, ...) |
| rule | str | Imperative instruction ("Use direct statements") |
| confidence | float | 0.0–1.0, based on how many edits confirm this |
| source_count | int | Number of chat histories that produced this rule |
| category | enum | tone, specificity, structure, vocabulary, framing |
| examples | {before, after} | Concrete before/after from actual edits |

### VoiceProfile

| Field | Type | Description |
|-------|------|-------------|
| version | int | Schema version |
| extracted_from | int | Count of processed records |
| last_updated | datetime | Last extraction timestamp |
| rules | VoiceRule[] | Accumulated voice rules |
| processed_slugs | str[] | ContentStore slugs already mined |

### Confidence Scoring

- 1–2 edits: 0.3 (tentative)
- 3–5 edits: 0.6 (established)
- 6+ edits: 0.9 (core voice)
- Contradiction: confidence halved
- Below 0.1: pruned on next extraction

## Extraction Prompt

The LLM receives a chat history and extracts voice rules:

- Only style/voice patterns (how to write), not content preferences (what to write)
- Each rule is an actionable imperative instruction
- Grounded in what the user actually said or changed
- Categorized by type
- Includes before/after examples from the conversation

## Override Hierarchy

```
Editorial notes (per-post intent)  ← highest priority
  > Voice rules (learned patterns)
    > Hardcoded prompt guidelines (defaults)  ← lowest priority
```

Voice rules override the generic style instructions in `prompts.py`, but editorial notes from `distill note` always take precedence. Structural constraints (word count, format) are never overridden.

## Injection Points

| Pipeline | Where | Confidence threshold |
|----------|-------|---------------------|
| Journal synthesis | System prompt in DailyContext | >= 0.5 |
| Blog weekly | After editorial notes in WeeklyBlogContext | >= 0.5 |
| Blog thematic | After editorial notes in ThematicBlogContext | >= 0.5 |
| Social adaptation | Prepended to prose input | >= 0.3 |
| Intake digest | After memory context | >= 0.5 |

## File Structure

```
src/voice/
  __init__.py
  models.py       # VoiceRule, VoiceProfile
  services.py     # extract, merge, load, save, render_for_prompt
  prompts.py      # Extraction and merge prompts
```

## CLI

```bash
distill voice extract --output ./insights   # Extract from unprocessed edits
distill voice show                          # Display current profile
distill voice show --category tone          # Filter by category
distill voice reset --output ./insights     # Start fresh
distill voice add "rule text" --category X  # Manual rule
```

## Why Chat History, Not Text Diffs

The user's explicit feedback ("too formal," "use the actual bug name") is vastly higher signal than trying to reverse-engineer style from comparing two blocks of text. A text diff tells you *what* changed; the chat tells you *why*.

## Key Decision: No New Capture Infrastructure

The ContentStore already saves `chat_history` on every Studio edit. Voice Memory is purely a read-from-existing-data pipeline. Zero changes to Studio's edit flow.

## Testing

- Unit: rule merging math, confidence decay, dedup, render_for_prompt
- Integration: mock chat history → extract → verify rules
- Integration: inject into blog prompt → verify voice section present
- Mirror structure: `tests/voice/test_models.py`, `test_services.py`, `test_prompts.py`
