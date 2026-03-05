# Voice Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Learn the user's writing voice from Studio chat histories and inject it into all content generation prompts.

**Architecture:** A new `src/voice/` package with Pydantic models, a JSON-backed store, LLM extraction prompts, and CLI commands. Follows the exact patterns from `src/shared/editorial.py` (EditorialStore) and `src/content/store.py` (ContentStore). Voice rules are injected into prompts alongside editorial notes in `src/blog/services.py` and `src/journal/services.py`.

**Tech Stack:** Python 3.11+, Pydantic v2, Typer CLI, Claude LLM via `call_claude()` from `src/shared/llm.py`

---

### Task 1: VoiceRule and VoiceProfile models

**Files:**
- Create: `src/voice/__init__.py`
- Create: `src/voice/models.py`
- Test: `tests/voice/test_models.py`

**Step 1: Write the failing test**

Create `tests/voice/__init__.py` (empty) and `tests/voice/test_models.py`:

```python
"""Tests for voice memory models."""

from datetime import datetime, UTC

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_rule_defaults():
    rule = VoiceRule(rule="Use direct statements.", category=RuleCategory.TONE)
    assert rule.confidence == 0.3
    assert rule.source_count == 1
    assert rule.id  # auto-generated
    assert rule.examples is None


def test_voice_rule_with_examples():
    rule = VoiceRule(
        rule="Name specific tools.",
        category=RuleCategory.SPECIFICITY,
        examples={"before": "the framework", "after": "FastAPI"},
    )
    assert rule.examples["before"] == "the framework"


def test_voice_profile_empty():
    profile = VoiceProfile()
    assert profile.rules == []
    assert profile.processed_slugs == []
    assert profile.version == 1


def test_voice_profile_add_rule():
    profile = VoiceProfile()
    rule = VoiceRule(rule="Be direct.", category=RuleCategory.TONE)
    profile.rules.append(rule)
    assert len(profile.rules) == 1


def test_confidence_label():
    low = VoiceRule(rule="x", category=RuleCategory.TONE, confidence=0.2)
    med = VoiceRule(rule="x", category=RuleCategory.TONE, confidence=0.5)
    high = VoiceRule(rule="x", category=RuleCategory.TONE, confidence=0.8)
    assert low.confidence_label == "low"
    assert med.confidence_label == "medium"
    assert high.confidence_label == "high"


def test_render_for_prompt_empty():
    profile = VoiceProfile()
    assert profile.render_for_prompt() == ""


def test_render_for_prompt_filters_by_threshold():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="High rule", category=RuleCategory.TONE, confidence=0.8),
        VoiceRule(rule="Low rule", category=RuleCategory.TONE, confidence=0.2),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "High rule" in rendered
    assert "Low rule" not in rendered


def test_render_for_prompt_groups_by_category():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct", category=RuleCategory.TONE, confidence=0.7),
        VoiceRule(rule="Name tools", category=RuleCategory.SPECIFICITY, confidence=0.7),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "### Tone" in rendered
    assert "### Specificity" in rendered
    assert "Be direct" in rendered
    assert "Name tools" in rendered


def test_prune_removes_low_confidence():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="keep", category=RuleCategory.TONE, confidence=0.5),
        VoiceRule(rule="prune", category=RuleCategory.TONE, confidence=0.05),
    ])
    pruned = profile.prune()
    assert pruned == 1
    assert len(profile.rules) == 1
    assert profile.rules[0].rule == "keep"
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/voice/test_models.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'distill.voice'`

**Step 3: Write minimal implementation**

Create `src/voice/__init__.py`:
```python
"""Voice memory — learns writing style from Studio editing sessions."""
```

Create `src/voice/models.py`:
```python
"""Voice memory models — pure Pydantic v2 data types."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class RuleCategory(StrEnum):
    """Category of a voice rule."""

    TONE = "tone"
    SPECIFICITY = "specificity"
    STRUCTURE = "structure"
    VOCABULARY = "vocabulary"
    FRAMING = "framing"


class VoiceRule(BaseModel):
    """A single learned voice rule."""

    id: str = Field(default_factory=lambda: f"v-{uuid.uuid4().hex[:8]}")
    rule: str
    confidence: float = 0.3
    source_count: int = 1
    category: RuleCategory
    examples: dict[str, str] | None = None

    @property
    def confidence_label(self) -> str:
        if self.confidence >= 0.7:
            return "high"
        if self.confidence >= 0.4:
            return "medium"
        return "low"


class VoiceProfile(BaseModel):
    """Accumulated voice rules learned from editing history."""

    version: int = 1
    extracted_from: int = 0
    last_updated: datetime = Field(default_factory=lambda: datetime.now(tz=UTC))
    rules: list[VoiceRule] = Field(default_factory=list)
    processed_slugs: list[str] = Field(default_factory=list)

    def render_for_prompt(self, min_confidence: float = 0.5) -> str:
        """Render voice rules as markdown for LLM prompt injection."""
        filtered = [r for r in self.rules if r.confidence >= min_confidence]
        if not filtered:
            return ""

        lines = [
            "## Your Voice (learned from editing history)",
            "",
            "IMPORTANT: These rules reflect how the author actually writes, learned from",
            "their edits. Follow them precisely — they override generic style guidelines.",
            "",
        ]

        by_category: dict[RuleCategory, list[VoiceRule]] = {}
        for rule in filtered:
            by_category.setdefault(rule.category, []).append(rule)

        for cat in RuleCategory:
            cat_rules = by_category.get(cat, [])
            if not cat_rules:
                continue
            lines.append(f"### {cat.value.title()}")
            for r in sorted(cat_rules, key=lambda x: -x.confidence):
                lines.append(f"- {r.rule} (confidence: {r.confidence_label})")
            lines.append("")

        return "\n".join(lines)

    def prune(self, threshold: float = 0.1) -> int:
        """Remove rules below confidence threshold. Returns count pruned."""
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.confidence >= threshold]
        return before - len(self.rules)
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/voice/test_models.py -x -q`
Expected: All 9 tests PASS

**Step 5: Commit**

```bash
git add src/voice/__init__.py src/voice/models.py tests/voice/__init__.py tests/voice/test_models.py
git commit -m "feat(voice): add VoiceRule and VoiceProfile models"
```

---

### Task 2: Voice profile load/save (store)

**Files:**
- Create: `src/voice/store.py`
- Test: `tests/voice/test_store.py`

**Step 1: Write the failing test**

```python
"""Tests for voice profile persistence."""

import json
from pathlib import Path

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.store import VOICE_FILENAME, load_voice_profile, save_voice_profile


def test_load_missing_file(tmp_path: Path):
    profile = load_voice_profile(tmp_path)
    assert profile.rules == []
    assert profile.version == 1


def test_save_and_load_roundtrip(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(id="v-001", rule="Be direct.", category=RuleCategory.TONE, confidence=0.7),
    ])
    save_voice_profile(profile, tmp_path)

    loaded = load_voice_profile(tmp_path)
    assert len(loaded.rules) == 1
    assert loaded.rules[0].rule == "Be direct."
    assert loaded.rules[0].confidence == 0.7


def test_save_creates_json_file(tmp_path: Path):
    profile = VoiceProfile()
    save_voice_profile(profile, tmp_path)
    assert (tmp_path / VOICE_FILENAME).exists()
    data = json.loads((tmp_path / VOICE_FILENAME).read_text())
    assert data["version"] == 1


def test_load_corrupt_file(tmp_path: Path):
    (tmp_path / VOICE_FILENAME).write_text("not json {{{")
    profile = load_voice_profile(tmp_path)
    assert profile.rules == []


def test_processed_slugs_persist(tmp_path: Path):
    profile = VoiceProfile(processed_slugs=["slug-1", "slug-2"])
    save_voice_profile(profile, tmp_path)
    loaded = load_voice_profile(tmp_path)
    assert loaded.processed_slugs == ["slug-1", "slug-2"]
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/voice/test_store.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'distill.voice.store'`

**Step 3: Write minimal implementation**

Create `src/voice/store.py`:
```python
"""Voice profile persistence — JSON-backed load/save."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from distill.voice.models import VoiceProfile

logger = logging.getLogger(__name__)

VOICE_FILENAME = ".distill-voice.json"


def load_voice_profile(output_dir: Path) -> VoiceProfile:
    """Load voice profile from disk, or return empty profile."""
    path = output_dir / VOICE_FILENAME
    if not path.exists():
        return VoiceProfile()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return VoiceProfile.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt voice profile at %s, starting fresh", path)
        return VoiceProfile()


def save_voice_profile(profile: VoiceProfile, output_dir: Path) -> None:
    """Save voice profile to disk."""
    path = output_dir / VOICE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/voice/test_store.py -x -q`
Expected: All 5 tests PASS

**Step 5: Commit**

```bash
git add src/voice/store.py tests/voice/test_store.py
git commit -m "feat(voice): add voice profile load/save"
```

---

### Task 3: Extraction prompt and rule merging

**Files:**
- Create: `src/voice/prompts.py`
- Create: `src/voice/services.py`
- Test: `tests/voice/test_prompts.py`
- Test: `tests/voice/test_services.py`

**Step 1: Write the failing tests**

`tests/voice/test_prompts.py`:
```python
"""Tests for voice extraction prompts."""

from distill.voice.prompts import get_extraction_prompt


def test_extraction_prompt_is_nonempty():
    prompt = get_extraction_prompt()
    assert len(prompt) > 100


def test_extraction_prompt_mentions_categories():
    prompt = get_extraction_prompt()
    assert "tone" in prompt.lower()
    assert "specificity" in prompt.lower()
    assert "structure" in prompt.lower()
    assert "vocabulary" in prompt.lower()
    assert "framing" in prompt.lower()


def test_extraction_prompt_requests_json():
    prompt = get_extraction_prompt()
    assert "json" in prompt.lower()
```

`tests/voice/test_services.py`:
```python
"""Tests for voice extraction and merging services."""

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.services import (
    compute_confidence,
    merge_rule_into_profile,
)


def test_compute_confidence_low():
    assert compute_confidence(1) == 0.3
    assert compute_confidence(2) == 0.3


def test_compute_confidence_medium():
    assert compute_confidence(3) == 0.6
    assert compute_confidence(5) == 0.6


def test_compute_confidence_high():
    assert compute_confidence(6) == 0.9
    assert compute_confidence(10) == 0.9


def test_merge_new_rule():
    profile = VoiceProfile()
    new_rule = VoiceRule(rule="Be direct.", category=RuleCategory.TONE)
    merge_rule_into_profile(profile, new_rule)
    assert len(profile.rules) == 1
    assert profile.rules[0].confidence == 0.3
    assert profile.rules[0].source_count == 1


def test_merge_matching_rule_increases_confidence():
    profile = VoiceProfile(rules=[
        VoiceRule(
            id="v-001",
            rule="Be direct and concise.",
            category=RuleCategory.TONE,
            source_count=2,
            confidence=0.3,
        ),
    ])
    new_rule = VoiceRule(rule="Use direct language.", category=RuleCategory.TONE)
    merge_rule_into_profile(profile, new_rule, is_match_id="v-001")
    assert len(profile.rules) == 1
    assert profile.rules[0].source_count == 3
    assert profile.rules[0].confidence == 0.6


def test_merge_contradiction_halves_confidence():
    profile = VoiceProfile(rules=[
        VoiceRule(
            id="v-001",
            rule="Be formal.",
            category=RuleCategory.TONE,
            source_count=4,
            confidence=0.6,
        ),
    ])
    merge_rule_into_profile(profile, None, contradict_id="v-001")
    assert profile.rules[0].confidence == 0.3


def test_merge_preserves_examples_from_new_rule():
    profile = VoiceProfile(rules=[
        VoiceRule(
            id="v-001", rule="Be direct.", category=RuleCategory.TONE,
            source_count=1, confidence=0.3,
        ),
    ])
    new_rule = VoiceRule(
        rule="Be direct.",
        category=RuleCategory.TONE,
        examples={"before": "It might work", "after": "It works"},
    )
    merge_rule_into_profile(profile, new_rule, is_match_id="v-001")
    assert profile.rules[0].examples is not None
    assert profile.rules[0].examples["after"] == "It works"
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/voice/test_prompts.py tests/voice/test_services.py -x -q`
Expected: FAIL — `ModuleNotFoundError`

**Step 3: Write minimal implementation**

Create `src/voice/prompts.py`:
```python
"""LLM prompts for voice pattern extraction."""

from __future__ import annotations


def get_extraction_prompt() -> str:
    """Return the system prompt for extracting voice rules from chat history."""
    return """\
You are analyzing a conversation between a user and an AI writing assistant.
The user edited AI-generated content and gave feedback about style, tone, and word choice.

Extract voice rules from this conversation. Each rule should be:
- A specific, actionable instruction (not vague like "write better")
- Grounded in what the user actually said or changed
- Categorized as one of: tone, specificity, structure, vocabulary, framing

Categories:
- tone: Formality level, hedging, confidence, humor
- specificity: Concrete vs abstract, naming things, metrics
- structure: Sentence length, paragraph rhythm, transitions
- vocabulary: Preferred/avoided words, jargon policy
- framing: How setbacks are described, how wins are shared

Return ONLY valid JSON — no markdown fences, no commentary. Format:
[
  {
    "rule": "Imperative instruction (e.g., 'Use direct statements')",
    "category": "tone|specificity|structure|vocabulary|framing",
    "examples": {"before": "original text", "after": "edited text"}
  }
]

Rules:
- Only extract rules with clear evidence in the conversation.
- Do NOT extract content-specific preferences (topic choices, what to cover).
- ONLY extract style/voice patterns (HOW to write, not WHAT to write).
- If there are no clear style patterns, return an empty array: []
"""
```

Create `src/voice/services.py`:
```python
"""Voice extraction and merging logic."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from distill.content.models import ContentRecord
from distill.content.store import ContentStore
from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.prompts import get_extraction_prompt
from distill.voice.store import load_voice_profile, save_voice_profile

logger = logging.getLogger(__name__)


def compute_confidence(source_count: int) -> float:
    """Compute confidence from number of confirming sources."""
    if source_count >= 6:
        return 0.9
    if source_count >= 3:
        return 0.6
    return 0.3


def merge_rule_into_profile(
    profile: VoiceProfile,
    new_rule: VoiceRule | None = None,
    *,
    is_match_id: str | None = None,
    contradict_id: str | None = None,
) -> None:
    """Merge a new rule into the profile, or apply a contradiction.

    - is_match_id: ID of existing rule that matches new_rule (reinforce).
    - contradict_id: ID of existing rule that is contradicted (decay).
    - If neither, new_rule is appended as a new entry.
    """
    if contradict_id:
        for r in profile.rules:
            if r.id == contradict_id:
                r.confidence = round(r.confidence / 2, 2)
                return
        return

    if new_rule is None:
        return

    if is_match_id:
        for r in profile.rules:
            if r.id == is_match_id:
                r.source_count += 1
                r.confidence = compute_confidence(r.source_count)
                if new_rule.examples and not r.examples:
                    r.examples = new_rule.examples
                return
        return

    # New rule — append
    profile.rules.append(new_rule)


def _parse_extraction_response(raw: str) -> list[dict]:
    """Parse the LLM extraction response into a list of rule dicts."""
    from distill.shared.llm import strip_json_fences

    cleaned = strip_json_fences(raw)
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, ValueError):
        logger.warning("Failed to parse voice extraction response")
    return []


def _dict_to_rule(d: dict) -> VoiceRule | None:
    """Convert an extraction response dict to a VoiceRule."""
    rule_text = d.get("rule", "").strip()
    cat_str = d.get("category", "").strip().lower()
    if not rule_text or not cat_str:
        return None
    try:
        category = RuleCategory(cat_str)
    except ValueError:
        return None
    examples = d.get("examples")
    if isinstance(examples, dict) and "before" in examples and "after" in examples:
        examples = {"before": str(examples["before"]), "after": str(examples["after"])}
    else:
        examples = None
    return VoiceRule(rule=rule_text, category=category, examples=examples)


def extract_from_record(record: ContentRecord) -> list[VoiceRule]:
    """Extract voice rules from a single ContentRecord's chat history.

    Makes an LLM call to analyze the chat and extract style patterns.
    """
    from distill.shared.llm import LLMError, call_claude

    if len(record.chat_history) < 2:
        return []

    # Format chat history for the LLM
    chat_text = "\n".join(
        f"[{msg.role}]: {msg.content}" for msg in record.chat_history
    )

    system_prompt = get_extraction_prompt()
    user_prompt = f"Analyze this editing conversation and extract voice/style rules:\n\n{chat_text}"

    try:
        raw = call_claude(
            system_prompt,
            user_prompt,
            model="haiku",
            timeout=60,
            label=f"voice-extract:{record.slug}",
        )
    except LLMError as exc:
        logger.warning("Voice extraction failed for %s: %s", record.slug, exc)
        return []

    parsed = _parse_extraction_response(raw)
    rules = []
    for d in parsed:
        rule = _dict_to_rule(d)
        if rule:
            rules.append(rule)
    return rules


def extract_voice_rules(output_dir: Path) -> VoiceProfile:
    """Extract voice rules from all unprocessed ContentStore records.

    Loads the ContentStore and voice profile, finds records with chat history
    that haven't been processed yet, extracts rules from each, merges them
    into the profile, and saves.
    """
    store = ContentStore(output_dir)
    profile = load_voice_profile(output_dir)

    all_records = store.list()
    unprocessed = [
        r for r in all_records
        if r.slug not in profile.processed_slugs and len(r.chat_history) >= 2
    ]

    if not unprocessed:
        logger.info("No unprocessed records with chat history")
        return profile

    total_new = 0
    for record in unprocessed:
        new_rules = extract_from_record(record)
        for rule in new_rules:
            merge_rule_into_profile(profile, rule)
            total_new += 1
        profile.processed_slugs.append(record.slug)

    profile.extracted_from = len(profile.processed_slugs)
    profile.last_updated = datetime.now(tz=UTC)
    profile.prune()
    save_voice_profile(profile, output_dir)

    logger.info(
        "Extracted %d new rules from %d records (total: %d rules)",
        total_new, len(unprocessed), len(profile.rules),
    )
    return profile
```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/voice/test_prompts.py tests/voice/test_services.py -x -q`
Expected: All 11 tests PASS

**Step 5: Commit**

```bash
git add src/voice/prompts.py src/voice/services.py tests/voice/test_prompts.py tests/voice/test_services.py
git commit -m "feat(voice): add extraction prompt and rule merging services"
```

---

### Task 4: CLI commands (voice extract, voice show, voice add, voice reset)

**Files:**
- Modify: `src/cli.py`
- Test: `tests/voice/test_cli.py`

**Step 1: Write the failing test**

```python
"""Tests for voice CLI commands."""

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from distill.cli import app
from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule
from distill.voice.store import save_voice_profile

runner = CliRunner()


def test_voice_show_empty(tmp_path: Path):
    result = runner.invoke(app, ["voice", "show", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "No voice rules" in result.output


def test_voice_show_with_rules(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE, confidence=0.8),
    ])
    save_voice_profile(profile, tmp_path)
    result = runner.invoke(app, ["voice", "show", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "Be direct." in result.output


def test_voice_show_filter_category(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE, confidence=0.8),
        VoiceRule(rule="Name tools.", category=RuleCategory.SPECIFICITY, confidence=0.7),
    ])
    save_voice_profile(profile, tmp_path)
    result = runner.invoke(app, ["voice", "show", "--output", str(tmp_path), "--category", "tone"])
    assert result.exit_code == 0
    assert "Be direct." in result.output
    assert "Name tools." not in result.output


def test_voice_add(tmp_path: Path):
    result = runner.invoke(app, [
        "voice", "add", "Always use Oxford commas",
        "--category", "vocabulary",
        "--output", str(tmp_path),
    ])
    assert result.exit_code == 0
    assert "Rule added" in result.output


def test_voice_reset(tmp_path: Path):
    profile = VoiceProfile(rules=[
        VoiceRule(rule="old rule", category=RuleCategory.TONE),
    ])
    save_voice_profile(profile, tmp_path)
    result = runner.invoke(app, ["voice", "reset", "--output", str(tmp_path)])
    assert result.exit_code == 0
    assert "reset" in result.output.lower()


@patch("distill.voice.services.extract_voice_rules")
def test_voice_extract_calls_service(mock_extract, tmp_path: Path):
    mock_extract.return_value = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE),
    ])
    result = runner.invoke(app, ["voice", "extract", "--output", str(tmp_path)])
    assert result.exit_code == 0
    mock_extract.assert_called_once()
```

**Step 2: Run test to verify it fails**

Run: `uv run pytest tests/voice/test_cli.py -x -q`
Expected: FAIL — no `voice` command group registered

**Step 3: Write minimal implementation**

Add to `src/cli.py` — find the existing command registrations and add:

```python
# --- Voice Memory commands ---

voice_app = typer.Typer(help="Voice memory — learn and apply your writing style.")
app.add_typer(voice_app, name="voice")


@voice_app.command(name="show")
def voice_show(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory."),
    ] = Path("./insights"),
    category: Annotated[
        str | None,
        typer.Option("--category", "-c", help="Filter by category (tone, specificity, structure, vocabulary, framing)."),
    ] = None,
) -> None:
    """Display the current voice profile."""
    from distill.voice.models import RuleCategory
    from distill.voice.store import load_voice_profile

    profile = load_voice_profile(output)
    rules = profile.rules

    if category:
        try:
            cat = RuleCategory(category.lower())
            rules = [r for r in rules if r.category == cat]
        except ValueError:
            console.print(f"[red]Unknown category: {category}[/red]")
            raise typer.Exit(1)

    if not rules:
        console.print("[dim]No voice rules found.[/dim]")
        return

    console.print(f"[bold]{len(rules)} voice rule(s):[/bold]")
    for rule in sorted(rules, key=lambda r: (-r.confidence, r.category)):
        conf = rule.confidence_label
        console.print(f"  [{conf}] ({rule.category}) {rule.rule}")
        if rule.examples:
            console.print(f"    [dim]before:[/dim] {rule.examples.get('before', '')}")
            console.print(f"    [dim]after:[/dim]  {rule.examples.get('after', '')}")


@voice_app.command(name="extract")
def voice_extract(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory."),
    ] = Path("./insights"),
) -> None:
    """Extract voice patterns from Studio chat histories."""
    from distill.voice.services import extract_voice_rules

    profile = extract_voice_rules(output)
    console.print(f"[green]Voice profile updated:[/green] {len(profile.rules)} total rules")
    console.print(f"  Processed {profile.extracted_from} records")


@voice_app.command(name="add")
def voice_add(
    text: Annotated[str, typer.Argument(help="Voice rule to add.")],
    category: Annotated[
        str,
        typer.Option("--category", "-c", help="Rule category."),
    ] = "tone",
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory."),
    ] = Path("./insights"),
) -> None:
    """Manually add a voice rule."""
    from distill.voice.models import RuleCategory, VoiceRule
    from distill.voice.store import load_voice_profile, save_voice_profile

    try:
        cat = RuleCategory(category.lower())
    except ValueError:
        console.print(f"[red]Unknown category: {category}[/red]")
        raise typer.Exit(1)

    profile = load_voice_profile(output)
    rule = VoiceRule(rule=text, category=cat, confidence=0.6, source_count=1)
    profile.rules.append(rule)
    save_voice_profile(profile, output)
    console.print(f"[green]Rule added:[/green] {text}")


@voice_app.command(name="reset")
def voice_reset(
    output: Annotated[
        Path,
        typer.Option("--output", "-o", help="Output directory."),
    ] = Path("./insights"),
) -> None:
    """Reset the voice profile (start fresh)."""
    from distill.voice.models import VoiceProfile
    from distill.voice.store import save_voice_profile

    save_voice_profile(VoiceProfile(), output)
    console.print("[green]Voice profile reset.[/green]")
```

**Step 4: Run test to verify it passes**

Run: `uv run pytest tests/voice/test_cli.py -x -q`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add src/cli.py tests/voice/test_cli.py
git commit -m "feat(voice): add CLI commands (show, extract, add, reset)"
```

---

### Task 5: Inject voice into blog prompts

**Files:**
- Modify: `src/blog/services.py` — `_render_weekly_prompt()` and `_render_thematic_prompt()`
- Modify: `src/blog/context.py` (if context objects need a `voice_context` field)
- Test: `tests/blog/test_voice_injection.py`

**Step 1: Write the failing test**

```python
"""Tests for voice rule injection into blog prompts."""

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_profile_renders_for_blog():
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Be direct.", category=RuleCategory.TONE, confidence=0.8),
        VoiceRule(rule="Name tools.", category=RuleCategory.SPECIFICITY, confidence=0.6),
        VoiceRule(rule="Low conf.", category=RuleCategory.STRUCTURE, confidence=0.2),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "## Your Voice" in rendered
    assert "Be direct." in rendered
    assert "Name tools." in rendered
    assert "Low conf." not in rendered
    assert "override generic style guidelines" in rendered
```

**Step 2: Run test to verify it passes** (this should already pass from Task 1's model)

Run: `uv run pytest tests/blog/test_voice_injection.py -x -q`
Expected: PASS

**Step 3: Wire voice context into blog pipeline**

The injection into `_render_weekly_prompt()` and `_render_thematic_prompt()` in `src/blog/services.py` follows the editorial notes pattern. Find the lines:

```python
if context.editorial_notes:
    lines.append(context.editorial_notes)
    lines.append("")
```

Add immediately after:

```python
if context.voice_context:
    lines.append(context.voice_context)
    lines.append("")
```

In the context models (`src/blog/context.py` or wherever `WeeklyBlogContext` and `ThematicBlogContext` are defined), add:

```python
voice_context: str = ""
```

In the pipeline orchestration (`src/pipeline/blog.py` or `src/core.py`), where editorial notes are loaded, add:

```python
from distill.voice.store import load_voice_profile

voice_profile = load_voice_profile(output_dir)
context.voice_context = voice_profile.render_for_prompt(min_confidence=0.5)
```

**Step 4: Run existing blog tests to verify nothing broke**

Run: `uv run pytest tests/blog/ -x -q`
Expected: All existing tests PASS

**Step 5: Commit**

```bash
git add src/blog/services.py src/blog/context.py src/pipeline/blog.py
git commit -m "feat(voice): inject voice rules into blog prompts"
```

---

### Task 6: Inject voice into journal prompts

**Files:**
- Modify: `src/journal/services.py` — `JournalSynthesizer.synthesize()`
- Modify: `src/journal/context.py` (if context needs `voice_context` field)
- Test: `tests/journal/test_voice_injection.py`

**Step 1: Write the failing test**

```python
"""Tests for voice rule injection into journal prompts."""

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_renders_for_journal():
    """Voice profile renders for journal context with standard threshold."""
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Short sentences.", category=RuleCategory.STRUCTURE, confidence=0.7),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.5)
    assert "Short sentences." in rendered
```

**Step 2: Run test (should already pass from Task 1)**

Run: `uv run pytest tests/journal/test_voice_injection.py -x -q`
Expected: PASS

**Step 3: Wire voice context into journal pipeline**

In `src/journal/services.py`, find where `DailyContext.render_text()` is called or where the system prompt is assembled. Add voice context to the user prompt:

```python
from distill.voice.store import load_voice_profile

# In the synthesize method or wherever context is assembled:
voice_profile = load_voice_profile(output_dir)
voice_section = voice_profile.render_for_prompt(min_confidence=0.5)
if voice_section:
    user_prompt = voice_section + "\n\n" + user_prompt
```

The exact location depends on whether `output_dir` is available in the synthesizer. If not, add `voice_context: str = ""` to `DailyContext` and populate it in `src/pipeline/journal.py` (or equivalent orchestration file).

**Step 4: Run existing journal tests to verify nothing broke**

Run: `uv run pytest tests/journal/ -x -q`
Expected: All existing tests PASS

**Step 5: Commit**

```bash
git add src/journal/services.py src/journal/context.py
git commit -m "feat(voice): inject voice rules into journal prompts"
```

---

### Task 7: Inject voice into social adaptation and intake digest

**Files:**
- Modify: `src/blog/services.py` — `adapt_for_platform()`
- Modify: `src/intake/prompts.py` — `get_unified_intake_prompt()`
- Test: `tests/voice/test_social_injection.py`

**Step 1: Write the failing test**

```python
"""Tests for voice injection into social and intake prompts."""

from distill.voice.models import RuleCategory, VoiceProfile, VoiceRule


def test_voice_renders_with_low_threshold_for_social():
    """Social adaptation uses lower threshold (0.3) to include experimental rules."""
    profile = VoiceProfile(rules=[
        VoiceRule(rule="Tentative rule.", category=RuleCategory.TONE, confidence=0.35),
    ])
    rendered = profile.render_for_prompt(min_confidence=0.3)
    assert "Tentative rule." in rendered

    # Same rule excluded at standard threshold
    rendered_high = profile.render_for_prompt(min_confidence=0.5)
    assert "Tentative rule." not in rendered_high
```

**Step 2: Run test (should pass from existing model code)**

Run: `uv run pytest tests/voice/test_social_injection.py -x -q`
Expected: PASS

**Step 3: Wire into social adaptation**

In `src/blog/services.py`, `adapt_for_platform()`, find where editorial hint is prepended. Add voice context similarly:

```python
# After editorial hint prepend, before calling Claude:
if voice_context:
    prose = voice_context + "\n\n" + prose
```

The voice context for social uses `min_confidence=0.3` (lower threshold).

In `src/intake/prompts.py`, add voice context injection after memory context in `get_unified_intake_prompt()`.

**Step 4: Run existing tests**

Run: `uv run pytest tests/blog/ tests/intake/ -x -q`
Expected: All existing tests PASS

**Step 5: Commit**

```bash
git add src/blog/services.py src/intake/prompts.py tests/voice/test_social_injection.py
git commit -m "feat(voice): inject voice into social adaptation and intake digest"
```

---

### Task 8: Integration test — end-to-end extraction

**Files:**
- Test: `tests/voice/test_integration.py`

**Step 1: Write the integration test**

```python
"""Integration test — mock LLM extraction end-to-end."""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from distill.content.models import ChatMessage, ContentRecord, ContentStatus, ContentType
from distill.content.store import ContentStore
from distill.voice.services import extract_voice_rules
from distill.voice.store import load_voice_profile


def _make_record(slug: str, messages: list[dict]) -> ContentRecord:
    return ContentRecord(
        slug=slug,
        content_type=ContentType.WEEKLY,
        title=f"Test post {slug}",
        body="Some content",
        status=ContentStatus.DRAFT,
        created_at=datetime.now(tz=UTC),
        chat_history=[
            ChatMessage(role=m["role"], content=m["content"], timestamp="2026-03-04T10:00:00Z")
            for m in messages
        ],
    )


MOCK_LLM_RESPONSE = json.dumps([
    {
        "rule": "Use direct statements without hedging",
        "category": "tone",
        "examples": {"before": "This might work", "after": "This works"},
    },
    {
        "rule": "Name specific tools and versions",
        "category": "specificity",
        "examples": {"before": "the library", "after": "React 19"},
    },
])


@patch("distill.voice.services.call_claude", return_value=MOCK_LLM_RESPONSE)
def test_end_to_end_extraction(mock_claude, tmp_path: Path):
    # Set up ContentStore with a record that has chat history
    store = ContentStore(tmp_path)
    record = _make_record("test-post-1", [
        {"role": "user", "content": "This is too formal, make it more direct"},
        {"role": "assistant", "content": "I've updated the post to be more direct."},
    ])
    store.upsert(record)

    # Run extraction
    profile = extract_voice_rules(tmp_path)

    # Verify rules were extracted
    assert len(profile.rules) == 2
    assert profile.processed_slugs == ["test-post-1"]
    assert profile.extracted_from == 1

    # Verify rules are correct
    tone_rules = [r for r in profile.rules if r.category == "tone"]
    assert len(tone_rules) == 1
    assert "direct" in tone_rules[0].rule.lower()

    # Verify profile was saved
    loaded = load_voice_profile(tmp_path)
    assert len(loaded.rules) == 2

    # Run again — should skip already-processed records
    profile2 = extract_voice_rules(tmp_path)
    assert len(profile2.rules) == 2  # No new rules
    mock_claude.assert_called_once()  # Only 1 LLM call total


@patch("distill.voice.services.call_claude", return_value=MOCK_LLM_RESPONSE)
def test_extraction_skips_records_without_chat(mock_claude, tmp_path: Path):
    store = ContentStore(tmp_path)
    record = _make_record("no-chat", [])  # No chat history
    record.chat_history = []
    store.upsert(record)

    profile = extract_voice_rules(tmp_path)
    assert len(profile.rules) == 0
    mock_claude.assert_not_called()
```

**Step 2: Run test**

Run: `uv run pytest tests/voice/test_integration.py -x -q`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/voice/test_integration.py
git commit -m "test(voice): add end-to-end extraction integration test"
```

---

### Task 9: Run full test suite and final commit

**Step 1: Run all voice tests**

Run: `uv run pytest tests/voice/ -x -q`
Expected: All tests PASS

**Step 2: Run full test suite to verify no regressions**

Run: `uv run pytest tests/ -x -q --timeout=120`
Expected: No new failures (existing known failures like `test_verify_all_kpis.py` may still fail)

**Step 3: Type check**

Run: `uv run mypy src/voice/ --no-error-summary`
Expected: No errors

**Step 4: Lint and format**

Run: `uv run ruff check src/voice/ && uv run ruff format src/voice/`
Expected: Clean

**Step 5: Final commit**

```bash
git add -A
git commit -m "chore(voice): type check, lint, and format pass"
git push origin main
```

---

## Summary

| Task | What | Tests |
|------|------|-------|
| 1 | VoiceRule + VoiceProfile models | 9 |
| 2 | Load/save persistence | 5 |
| 3 | Extraction prompt + rule merging | 11 |
| 4 | CLI commands (show, extract, add, reset) | 6 |
| 5 | Blog prompt injection | 1 + existing |
| 6 | Journal prompt injection | 1 + existing |
| 7 | Social + intake injection | 1 + existing |
| 8 | End-to-end integration test | 2 |
| 9 | Full suite validation | — |
| **Total** | | **~36 new tests** |
