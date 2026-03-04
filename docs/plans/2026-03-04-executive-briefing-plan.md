# Executive Briefing Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add an LLM-synthesized executive briefing to the Knowledge Graph dashboard that surfaces momentum, risks, recommendations, and reading-to-building connections.

**Architecture:** New `BriefingGenerator` class in `src/graph/briefing.py` gathers graph context + daily insights + intake digest data, feeds them into an executive-tuned prompt, and saves structured JSON to `.distill-briefing.json`. The API serves it; the frontend renders a new default "Briefing" tab.

**Tech Stack:** Python (Pydantic, subprocess `claude -p`), TypeScript (Hono API, React, Zod)

---

## Context

The existing Knowledge Graph dashboard (`/graph`) has 3 tabs: Activity, Explorer, Insights — all developer-level telemetry. This plan adds an executive intelligence layer as a 4th "Briefing" tab that becomes the default landing.

### Key existing patterns to follow:
- **Synthesis**: `src/graph/synthesizer.py` — `claude -p` subprocess pattern (lines 65-82)
- **Prompts**: `src/graph/prompts.py` — `get_X_prompt(data) -> str` pattern
- **Insights**: `src/graph/insights.py` — `DailyInsights` dataclass (lines 100-111), `generate_daily_insights()` (lines 314-329)
- **Query**: `src/graph/query.py` — `gather_context_data()` (lines 240-394)
- **Intake digests**: `insights/intake/intake-YYYY-MM-DD.md` — frontmatter with themes, highlights, tags + prose
- **CLI graph commands**: `src/cli.py` lines 2355-2734
- **Pipeline graph step**: `src/cli.py` lines 1660-1679 (in `distill run`)
- **API routes**: `web/server/routes/graph.ts` — `loadGraph()` helper, `app.get()` pattern
- **Schemas**: `web/shared/schemas.ts` lines 121-249 (graph section)
- **Frontend tabs**: `web/src/routes/graph.tsx` — `Tab` type at line 31, tab rendering at lines 652-675

---

### Task 1: Briefing Pydantic Model

**Files:**
- Create: `src/graph/briefing.py`
- Test: `tests/graph/test_briefing.py`

Create the Pydantic models for the briefing data structure. No LLM integration yet — just the data model and a simple JSON store.

```python
# src/graph/briefing.py
"""Executive briefing — LLM-synthesized personal intelligence from the knowledge graph."""

from __future__ import annotations

import json
import logging
from datetime import datetime, UTC
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

BRIEFING_FILENAME = ".distill-briefing.json"


class BriefingArea(BaseModel):
    """A project or focus area with momentum tracking."""
    name: str
    status: str = "active"          # active | cooling | emerging
    momentum: str = "steady"        # accelerating | steady | decelerating
    headline: str = ""
    sessions: int = 0
    reading_count: int = 0
    open_threads: list[str] = Field(default_factory=list)


class BriefingLearning(BaseModel):
    """A reading/learning topic and its connection to active work."""
    topic: str
    reading_count: int = 0
    connection: str = ""
    status: str = "emerging"        # active | emerging | cooling


class BriefingRisk(BaseModel):
    """A risk with severity and plain-English description."""
    severity: str = "medium"        # high | medium | low
    headline: str
    detail: str = ""
    project: str = ""


class BriefingRecommendation(BaseModel):
    """A prioritized action recommendation."""
    priority: int = 1
    action: str
    rationale: str = ""


class Briefing(BaseModel):
    """Complete executive briefing for a given day."""
    date: str = Field(default_factory=lambda: datetime.now(tz=UTC).strftime("%Y-%m-%d"))
    generated_at: str = Field(default_factory=lambda: datetime.now(tz=UTC).isoformat())
    time_window_hours: int = 48
    summary: str = ""
    areas: list[BriefingArea] = Field(default_factory=list)
    learning: list[BriefingLearning] = Field(default_factory=list)
    risks: list[BriefingRisk] = Field(default_factory=list)
    recommendations: list[BriefingRecommendation] = Field(default_factory=list)


def load_briefing(output_dir: Path) -> Briefing | None:
    """Load the most recent briefing from disk."""
    path = output_dir / BRIEFING_FILENAME
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return Briefing.model_validate(data)
    except (json.JSONDecodeError, ValueError, KeyError):
        logger.warning("Corrupt briefing file at %s", path)
        return None


def save_briefing(briefing: Briefing, output_dir: Path) -> Path:
    """Save a briefing to disk. Returns the file path."""
    path = output_dir / BRIEFING_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(briefing.model_dump(mode="json"), indent=2, default=str),
        encoding="utf-8",
    )
    return path
```

**Tests** (`tests/graph/test_briefing.py`):

```python
"""Tests for executive briefing model and persistence."""

import json
from pathlib import Path

import pytest

from distill.graph.briefing import (
    Briefing,
    BriefingArea,
    BriefingLearning,
    BriefingRecommendation,
    BriefingRisk,
    load_briefing,
    save_briefing,
    BRIEFING_FILENAME,
)


def _sample_briefing() -> Briefing:
    return Briefing(
        date="2026-03-04",
        time_window_hours=48,
        summary="You made strong progress on TroopX workflows.",
        areas=[
            BriefingArea(
                name="TroopX",
                status="active",
                momentum="accelerating",
                headline="Workflow engine taking shape",
                sessions=8,
                reading_count=3,
                open_threads=["state machine edge cases"],
            )
        ],
        learning=[
            BriefingLearning(
                topic="Distributed state machines",
                reading_count=3,
                connection="Directly relevant to TroopX",
                status="emerging",
            )
        ],
        risks=[
            BriefingRisk(
                severity="high",
                headline="Registration module fragile",
                detail="Recurring problems growing",
                project="TroopX",
            )
        ],
        recommendations=[
            BriefingRecommendation(
                priority=1,
                action="Stabilize workflow registration",
                rationale="Unblocks safer iteration",
            )
        ],
    )


def test_briefing_model_defaults():
    b = Briefing()
    assert b.summary == ""
    assert b.areas == []
    assert b.time_window_hours == 48


def test_briefing_roundtrip(tmp_path: Path):
    original = _sample_briefing()
    save_briefing(original, tmp_path)

    loaded = load_briefing(tmp_path)
    assert loaded is not None
    assert loaded.summary == original.summary
    assert len(loaded.areas) == 1
    assert loaded.areas[0].name == "TroopX"
    assert loaded.areas[0].momentum == "accelerating"
    assert len(loaded.learning) == 1
    assert loaded.learning[0].topic == "Distributed state machines"
    assert len(loaded.risks) == 1
    assert loaded.risks[0].severity == "high"
    assert len(loaded.recommendations) == 1


def test_load_missing_file(tmp_path: Path):
    assert load_briefing(tmp_path) is None


def test_load_corrupt_file(tmp_path: Path):
    (tmp_path / BRIEFING_FILENAME).write_text("not json", encoding="utf-8")
    assert load_briefing(tmp_path) is None


def test_save_creates_directory(tmp_path: Path):
    nested = tmp_path / "deep" / "dir"
    save_briefing(_sample_briefing(), nested)
    assert (nested / BRIEFING_FILENAME).exists()


def test_briefing_area_status_values():
    for status in ("active", "cooling", "emerging"):
        a = BriefingArea(name="test", status=status)
        assert a.status == status


def test_briefing_area_momentum_values():
    for momentum in ("accelerating", "steady", "decelerating"):
        a = BriefingArea(name="test", momentum=momentum)
        assert a.momentum == momentum
```

**Verification:**
```bash
uv run pytest tests/graph/test_briefing.py -x -q
```

---

### Task 2: Executive Briefing Prompt

**Files:**
- Modify: `src/graph/prompts.py` (add after line 121)

Add the executive briefing prompt functions following the existing `get_context_prompt()` pattern.

```python
# Add after line 121 of src/graph/prompts.py

# ── Executive briefing prompt ───────────────────────────────────────────

_BRIEFING_SYSTEM_PROMPT = """\
You are a personal intelligence analyst. You synthesize a developer's recent \
coding sessions, reading habits, and structural insights into an executive briefing.

Rules:
- Write in second person ("You made progress on...", "Your reading on...")
- Use plain English — no file paths, no session IDs, no jargon
- A non-technical stakeholder should be able to read this
- Use momentum language: active/cooling/emerging for status, \
accelerating/steady/decelerating for momentum
- Never use completion language ("50% done", "on track to finish")
- Connect reading topics to active work when relevant
- Limit recommendations to top 3, ordered by impact
- Keep the summary to 2-3 sentences
- Headlines should be under 15 words
- Output valid JSON matching the schema exactly — no markdown, no code fences

Output schema:
{
  "summary": "2-3 sentence executive narrative",
  "areas": [{"name": "...", "status": "active|cooling|emerging", \
"momentum": "accelerating|steady|decelerating", "headline": "...", \
"sessions": N, "reading_count": N, "open_threads": ["..."]}],
  "learning": [{"topic": "...", "reading_count": N, \
"connection": "...", "status": "active|emerging|cooling"}],
  "risks": [{"severity": "high|medium|low", "headline": "...", \
"detail": "...", "project": "..."}],
  "recommendations": [{"priority": N, "action": "...", "rationale": "..."}]
}
"""


def get_briefing_prompt(
    context_data: dict[str, Any],
    insights_text: str,
    intake_text: str,
) -> str:
    """Build the executive briefing prompt from graph + insights + intake data."""
    system = _BRIEFING_SYSTEM_PROMPT
    user = _format_briefing_user_prompt(context_data, insights_text, intake_text)
    return f"{system}\n\n---\n\n{user}"


def _format_briefing_user_prompt(
    data: dict[str, Any],
    insights_text: str,
    intake_text: str,
) -> str:
    """Format the user portion of the briefing prompt."""
    parts: list[str] = []

    project = data.get("project", "(all)")
    hours = data.get("time_window_hours", 48)
    parts.append(f"Project: {project}")
    parts.append(f"Time window: last {hours} hours")

    # Sessions
    sessions = data.get("sessions", [])
    if sessions:
        parts.append(f"\n## Recent Sessions ({len(sessions)})")
        for s in sessions:
            proj = s.get("project", "unknown")
            goal = _sanitize_text(s.get("goal", "")) or "(no goal)"
            hours_ago = s.get("hours_ago", 0)
            files_mod = s.get("files_modified", [])
            problems = s.get("problems", [])
            entities = s.get("entities", [])
            parts.append(f"- [{proj}] {goal} ({hours_ago}h ago)")
            if files_mod:
                parts.append(f"  Files modified: {len(files_mod)}")
            if problems:
                parts.append(f"  Problems: {len(problems)}")
            if entities:
                parts.append(f"  Tech: {', '.join(entities[:8])}")

    # Entities / tech stack
    top_entities = data.get("top_entities", [])
    if top_entities:
        parts.append("\n## Tech Stack (by frequency)")
        for e in top_entities[:15]:
            parts.append(f"- {e['name']}: {e['count']}")

    # Structural insights
    if insights_text.strip():
        parts.append(f"\n## Structural Insights\n{insights_text}")

    # Intake / reading
    if intake_text.strip():
        parts.append(f"\n## Recent Reading\n{intake_text}")

    # Other projects
    other = data.get("other_projects", [])
    if other:
        parts.append("\n## Other Active Projects")
        for o in other:
            parts.append(f"- {o['project']}: {o.get('summary', '')} ({o.get('hours_ago', 0)}h ago)")

    return "\n".join(parts)
```

**Test** — add to `tests/graph/test_briefing.py`:

```python
from distill.graph.prompts import get_briefing_prompt


def test_get_briefing_prompt_contains_sections():
    data = {
        "project": "TroopX",
        "time_window_hours": 48,
        "sessions": [
            {"project": "TroopX", "goal": "Build workflow engine", "hours_ago": 2,
             "files_modified": ["a.py"], "problems": [{"error": "import error"}],
             "entities": ["python", "temporal"]},
        ],
        "top_entities": [{"name": "python", "count": 10}],
        "other_projects": [],
    }
    prompt = get_briefing_prompt(data, "2 error hotspots detected", "Read 3 articles on state machines")
    assert "TroopX" in prompt
    assert "Build workflow engine" in prompt
    assert "Structural Insights" in prompt
    assert "Recent Reading" in prompt
    assert "valid JSON" in prompt


def test_get_briefing_prompt_empty_data():
    prompt = get_briefing_prompt(
        {"project": "(all)", "time_window_hours": 48, "sessions": []},
        "",
        "",
    )
    assert "Project: (all)" in prompt
    assert "Structural Insights" not in prompt
    assert "Recent Reading" not in prompt
```

**Verification:**
```bash
uv run pytest tests/graph/test_briefing.py -x -q
```

---

### Task 3: BriefingGenerator — LLM Synthesis

**Files:**
- Modify: `src/graph/briefing.py` (add `generate_briefing()` function)
- Modify: `src/graph/__init__.py` (add exports)

Add the generator function that gathers all data and calls Claude. Follows the exact `synthesize_context()` pattern from `src/graph/synthesizer.py` lines 36-94.

```python
# Add to src/graph/briefing.py after save_briefing()

import os
import re as _re
import subprocess
from typing import Any

from distill.graph.insights import DailyInsights, GraphInsights, format_insights_for_prompt
from distill.graph.prompts import get_briefing_prompt
from distill.graph.query import GraphQuery
from distill.graph.store import GraphStore


_DEFAULT_TIMEOUT = 90
_JSON_FENCE_RE = _re.compile(r"```(?:json)?\s*\n?(.*?)\n?```", _re.DOTALL)


def _strip_json_fences(text: str) -> str:
    """Remove markdown code fences wrapping JSON (Claude sometimes adds them)."""
    m = _JSON_FENCE_RE.search(text)
    return m.group(1).strip() if m else text.strip()


def _load_recent_intake(output_dir: Path, days: int = 3) -> str:
    """Load recent intake digest summaries for reading context."""
    intake_dir = output_dir / "intake"
    if not intake_dir.exists():
        return ""

    parts: list[str] = []
    files = sorted(intake_dir.glob("intake-*.md"), reverse=True)[:days]
    for f in files:
        try:
            text = f.read_text(encoding="utf-8")
            # Extract frontmatter fields
            tags_match = _re.search(r"^tags:\s*\[(.+?)\]", text, _re.MULTILINE)
            highlights = _re.findall(r'^\s+-\s+"(.+?)"', text, _re.MULTILINE)
            # Extract first paragraph of prose (after frontmatter)
            prose_match = _re.search(r"^---\s*\n#\s+(.+?)$", text, _re.MULTILINE)
            title = prose_match.group(1) if prose_match else f.stem

            parts.append(f"### {f.stem}")
            parts.append(f"Title: {title}")
            if tags_match:
                parts.append(f"Topics: {tags_match.group(1)}")
            if highlights:
                parts.append("Key findings:")
                for h in highlights[:3]:
                    parts.append(f"  - {h[:200]}")
        except OSError:
            continue

    return "\n".join(parts)


def generate_briefing(
    output_dir: Path,
    *,
    hours: float = 48.0,
    model: str | None = None,
    timeout: int = _DEFAULT_TIMEOUT,
) -> Briefing:
    """Generate an executive briefing from the knowledge graph + intake data.

    Gathers graph context, structural insights, and recent reading,
    then synthesizes via Claude into a structured briefing.
    """
    # Load graph
    store = GraphStore(path=output_dir)
    query = GraphQuery(store)
    insights_engine = GraphInsights(store)

    # Gather data
    context_data = query.gather_context_data(max_hours=hours)
    daily_insights = insights_engine.generate_daily_insights(lookback_hours=hours)
    insights_text = format_insights_for_prompt(daily_insights)
    intake_text = _load_recent_intake(output_dir)

    # Build prompt
    prompt = get_briefing_prompt(context_data, insights_text, intake_text)

    # Call Claude
    cmd: list[str] = ["claude", "-p"]
    if model:
        cmd.extend(["--model", model])
    cmd.append(prompt)

    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout, env=env,
        )
    except FileNotFoundError as exc:
        raise BriefingSynthesisError("Claude CLI not found") from exc
    except subprocess.TimeoutExpired as exc:
        raise BriefingSynthesisError(f"Timed out after {timeout}s") from exc

    if result.returncode != 0:
        raise BriefingSynthesisError(f"Claude exited with code {result.returncode}: {result.stderr[:200]}")

    # Parse JSON response
    raw = _strip_json_fences(result.stdout)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise BriefingSynthesisError(f"Invalid JSON from Claude: {exc}") from exc

    briefing = Briefing(
        time_window_hours=int(hours),
        summary=data.get("summary", ""),
        areas=[BriefingArea.model_validate(a) for a in data.get("areas", [])],
        learning=[BriefingLearning.model_validate(l) for l in data.get("learning", [])],
        risks=[BriefingRisk.model_validate(r) for r in data.get("risks", [])],
        recommendations=[BriefingRecommendation.model_validate(r) for r in data.get("recommendations", [])],
    )

    save_briefing(briefing, output_dir)
    return briefing


class BriefingSynthesisError(Exception):
    """Raised when briefing synthesis fails."""
```

**Update `src/graph/__init__.py`** — add imports and exports:

```python
# Add to imports:
from distill.graph.briefing import (
    Briefing, BriefingArea, BriefingLearning, BriefingRecommendation,
    BriefingRisk, BriefingSynthesisError, BRIEFING_FILENAME,
    generate_briefing, load_briefing, save_briefing,
)
from distill.graph.prompts import get_briefing_prompt

# Add to __all__:
    # briefing
    "Briefing", "BriefingArea", "BriefingLearning", "BriefingRecommendation",
    "BriefingRisk", "BriefingSynthesisError", "BRIEFING_FILENAME",
    "generate_briefing", "load_briefing", "save_briefing",
    "get_briefing_prompt",
```

**Tests** — add to `tests/graph/test_briefing.py`:

```python
from unittest.mock import patch, MagicMock
from distill.graph.briefing import (
    generate_briefing,
    BriefingSynthesisError,
    _strip_json_fences,
    _load_recent_intake,
)


def test_strip_json_fences():
    assert _strip_json_fences('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _strip_json_fences('{"a": 1}') == '{"a": 1}'
    assert _strip_json_fences('```\n{"a": 1}\n```') == '{"a": 1}'


def test_load_recent_intake_missing_dir(tmp_path: Path):
    assert _load_recent_intake(tmp_path) == ""


def test_load_recent_intake_reads_files(tmp_path: Path):
    intake_dir = tmp_path / "intake"
    intake_dir.mkdir()
    (intake_dir / "intake-2026-03-04.md").write_text(
        '---\ntags: [python, testing]\nhighlights:\n  - "Found a great article"\n---\n# Test Title\nBody text',
        encoding="utf-8",
    )
    result = _load_recent_intake(tmp_path)
    assert "intake-2026-03-04" in result
    assert "Test Title" in result
    assert "python, testing" in result


@patch("distill.graph.briefing.subprocess.run")
@patch("distill.graph.briefing.GraphStore")
@patch("distill.graph.briefing.GraphQuery")
@patch("distill.graph.briefing.GraphInsights")
def test_generate_briefing_success(
    mock_insights_cls, mock_query_cls, mock_store_cls, mock_run, tmp_path: Path
):
    # Setup mocks
    mock_query = mock_query_cls.return_value
    mock_query.gather_context_data.return_value = {
        "project": "(all)", "time_window_hours": 48, "sessions": [],
        "top_entities": [], "active_files": [], "other_projects": [],
    }
    mock_insights = mock_insights_cls.return_value
    mock_insights.generate_daily_insights.return_value = MagicMock(
        coupling_clusters=[], error_hotspots=[], scope_warnings=[], recurring_problems=[],
    )

    mock_run.return_value = MagicMock(
        returncode=0,
        stdout=json.dumps({
            "summary": "Good progress on TroopX.",
            "areas": [{"name": "TroopX", "status": "active", "momentum": "accelerating",
                        "headline": "Workflow engine", "sessions": 5, "reading_count": 2,
                        "open_threads": []}],
            "learning": [],
            "risks": [],
            "recommendations": [{"priority": 1, "action": "Keep going", "rationale": "Momentum"}],
        }),
        stderr="",
    )

    briefing = generate_briefing(tmp_path)
    assert briefing.summary == "Good progress on TroopX."
    assert len(briefing.areas) == 1
    assert briefing.areas[0].name == "TroopX"
    assert len(briefing.recommendations) == 1


@patch("distill.graph.briefing.subprocess.run")
@patch("distill.graph.briefing.GraphStore")
@patch("distill.graph.briefing.GraphQuery")
@patch("distill.graph.briefing.GraphInsights")
def test_generate_briefing_claude_not_found(
    mock_insights_cls, mock_query_cls, mock_store_cls, mock_run, tmp_path: Path
):
    mock_query_cls.return_value.gather_context_data.return_value = {
        "project": "(all)", "time_window_hours": 48, "sessions": [],
        "top_entities": [], "active_files": [], "other_projects": [],
    }
    mock_insights_cls.return_value.generate_daily_insights.return_value = MagicMock(
        coupling_clusters=[], error_hotspots=[], scope_warnings=[], recurring_problems=[],
    )
    mock_run.side_effect = FileNotFoundError("claude not found")
    with pytest.raises(BriefingSynthesisError, match="CLI not found"):
        generate_briefing(tmp_path)
```

**Verification:**
```bash
uv run pytest tests/graph/test_briefing.py -x -q
```

---

### Task 4: CLI Command — `distill graph briefing`

**Files:**
- Modify: `src/cli.py` (add at line 2735, between `graph_inject` and `@app.command() def mcp`)

```python
@graph_app.command()
def briefing(
    output: Annotated[
        str,
        typer.Option("--output", "-o", help="Output directory"),
    ] = ".",
    hours: Annotated[
        float,
        typer.Option("--hours", help="Lookback window in hours"),
    ] = 48.0,
    model: Annotated[
        str | None,
        typer.Option("--model", help="LLM model to use"),
    ] = None,
    quiet: Annotated[
        bool,
        typer.Option("--quiet", "-q", help="Suppress output"),
    ] = False,
) -> None:
    """Generate an executive briefing from the knowledge graph."""
    from distill.graph.briefing import generate_briefing, BriefingSynthesisError

    output_path = Path(output)
    if not quiet:
        console.print(f"[dim]Generating executive briefing (last {hours}h)...[/dim]")

    try:
        result = generate_briefing(output_path, hours=hours, model=model)
    except BriefingSynthesisError as e:
        console.print(f"[red]Briefing synthesis failed:[/red] {e}")
        raise typer.Exit(1) from None

    if not quiet:
        console.print(f"[green]Briefing generated for {result.date}[/green]")
        console.print()
        console.print(f"[bold]{result.summary}[/bold]")
        if result.areas:
            console.print()
            for area in result.areas:
                status_color = {"active": "green", "cooling": "yellow", "emerging": "blue"}.get(area.status, "white")
                console.print(f"  [{status_color}]{area.name}[/{status_color}] — {area.headline}")
        if result.recommendations:
            console.print()
            console.print("[bold]Recommendations:[/bold]")
            for rec in result.recommendations:
                console.print(f"  {rec.priority}. {rec.action}")
```

**Pipeline integration** — add after graph build in `distill run` (after line 1679):

```python
                # Generate executive briefing (non-blocking, best-effort)
                try:
                    from distill.graph.briefing import generate_briefing as _gen_briefing
                    _gen_briefing(output, hours=48.0)
                    console.print("  [green]Executive briefing generated[/green]")
                except Exception as exc:
                    report.add_error("briefing", str(exc), error_type="stage_error", recoverable=True)
                    console.print(f"  [dim]Briefing skipped: {exc}[/dim]")
```

**Verification:**
```bash
# CLI smoke test (requires graph data + Claude CLI):
uv run python -m distill graph briefing --output ./insights --quiet

# Check file was created:
cat insights/.distill-briefing.json | python -m json.tool | head -20
```

---

### Task 5: Zod Schemas + API Endpoint

**Files:**
- Modify: `web/shared/schemas.ts` (add after line 249, before `// --- Editorial Notes ---`)
- Modify: `web/server/routes/graph.ts` (add before `export default app` at line 533)

**Zod schemas** — add to `web/shared/schemas.ts`:

```typescript
// --- Executive Briefing ---
export const BriefingAreaSchema = z.object({
	name: z.string(),
	status: z.enum(["active", "cooling", "emerging"]),
	momentum: z.enum(["accelerating", "steady", "decelerating"]),
	headline: z.string().default(""),
	sessions: z.number().default(0),
	reading_count: z.number().default(0),
	open_threads: z.array(z.string()).default([]),
});

export const BriefingLearningSchema = z.object({
	topic: z.string(),
	reading_count: z.number().default(0),
	connection: z.string().default(""),
	status: z.enum(["active", "emerging", "cooling"]),
});

export const BriefingRiskSchema = z.object({
	severity: z.enum(["high", "medium", "low"]),
	headline: z.string(),
	detail: z.string().default(""),
	project: z.string().default(""),
});

export const BriefingRecommendationSchema = z.object({
	priority: z.number(),
	action: z.string(),
	rationale: z.string().default(""),
});

export const BriefingResponseSchema = z.object({
	date: z.string(),
	generated_at: z.string(),
	time_window_hours: z.number(),
	summary: z.string(),
	areas: z.array(BriefingAreaSchema),
	learning: z.array(BriefingLearningSchema),
	risks: z.array(BriefingRiskSchema),
	recommendations: z.array(BriefingRecommendationSchema),
});
```

Add type exports alongside the other graph types (after line 721):

```typescript
export type BriefingArea = z.infer<typeof BriefingAreaSchema>;
export type BriefingLearning = z.infer<typeof BriefingLearningSchema>;
export type BriefingRisk = z.infer<typeof BriefingRiskSchema>;
export type BriefingRecommendation = z.infer<typeof BriefingRecommendationSchema>;
export type BriefingResponse = z.infer<typeof BriefingResponseSchema>;
```

**API endpoint** — add to `web/server/routes/graph.ts` before `export default app`:

```typescript
// GET /api/graph/briefing — executive briefing
app.get("/api/graph/briefing", async (c) => {
	const briefingPath = path.join(OUTPUT_DIR, ".distill-briefing.json");
	try {
		const raw = await Bun.file(briefingPath).text();
		const data = JSON.parse(raw);
		return c.json(data);
	} catch {
		return c.json(
			{
				date: "",
				generated_at: "",
				time_window_hours: 48,
				summary: "",
				areas: [],
				learning: [],
				risks: [],
				recommendations: [],
			},
			200,
		);
	}
});
```

**API test** — add to `web/server/__tests__/graph.test.ts`:

```typescript
test("GET /api/graph/briefing returns briefing data or empty default", async () => {
	const res = await app.request("/api/graph/briefing");
	expect(res.status).toBe(200);
	const data = await res.json();
	expect(data).toHaveProperty("summary");
	expect(data).toHaveProperty("areas");
	expect(data).toHaveProperty("learning");
	expect(data).toHaveProperty("risks");
	expect(data).toHaveProperty("recommendations");
});
```

**Verification:**
```bash
cd web && bun test server/__tests__/graph.test.ts
```

---

### Task 6: Frontend — Briefing Tab

**Files:**
- Modify: `web/src/routes/graph.tsx`

Update the tab type, add BriefingTab component, make it the default landing tab.

**Changes to existing code:**

1. Update `Tab` type (line 31):
```typescript
type Tab = "briefing" | "activity" | "explorer" | "insights";
```

2. Update default state (in `GraphPage`, line 628):
```typescript
const [activeTab, setActiveTab] = useState<Tab>("briefing");
```

3. Update tab array (line 655):
```typescript
{(["briefing", "activity", "explorer", "insights"] as const).map((tab) => (
```

4. Add BriefingTab render (before the activity conditional, line 672):
```typescript
{activeTab === "briefing" && <BriefingTab />}
```

**New BriefingTab component** — add before `ActivityTab` (before line 45):

```tsx
// ── Briefing Tab ──────────────────────────────────────────────────────
function BriefingTab() {
	const { data, isLoading } = useQuery({
		queryKey: ["graph", "briefing"],
		queryFn: async () => {
			const res = await fetch("/api/graph/briefing");
			return res.json();
		},
	});

	if (isLoading) return <div className="animate-pulse text-zinc-400">Loading briefing...</div>;

	if (!data?.summary) {
		return (
			<div className="text-center py-16 text-zinc-500">
				<p className="text-lg">No briefing generated yet</p>
				<p className="text-sm mt-2">
					Run <code className="bg-zinc-800 px-2 py-0.5 rounded">distill graph briefing --output ./insights</code> to generate one
				</p>
			</div>
		);
	}

	const statusColor = (s: string) =>
		({ active: "text-emerald-400 bg-emerald-400/10 border-emerald-400/30",
		   cooling: "text-amber-400 bg-amber-400/10 border-amber-400/30",
		   emerging: "text-blue-400 bg-blue-400/10 border-blue-400/30",
		}[s] ?? "text-zinc-400 bg-zinc-400/10 border-zinc-400/30");

	const momentumIcon = (m: string) =>
		({ accelerating: "\u2197", steady: "\u2192", decelerating: "\u2198" }[m] ?? "");

	const severityColor = (s: string) =>
		({ high: "border-red-400/40 bg-red-400/5",
		   medium: "border-amber-400/40 bg-amber-400/5",
		   low: "border-zinc-600 bg-zinc-800/50",
		}[s] ?? "border-zinc-600 bg-zinc-800/50");

	return (
		<div className="space-y-8">
			{/* Summary */}
			<div className="bg-zinc-900/50 border border-zinc-800 rounded-lg p-6">
				<p className="text-lg text-zinc-200 leading-relaxed">{data.summary}</p>
				{data.generated_at && (
					<p className="text-xs text-zinc-600 mt-3">
						Generated {new Date(data.generated_at).toLocaleString()}
					</p>
				)}
			</div>

			{/* Areas */}
			{data.areas?.length > 0 && (
				<section>
					<h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
						Focus Areas
					</h3>
					<div className="grid gap-3 md:grid-cols-2">
						{data.areas.map((area: any, i: number) => (
							<div key={i} className={`border rounded-lg p-4 ${statusColor(area.status)}`}>
								<div className="flex items-center justify-between mb-1">
									<span className="font-semibold">{area.name}</span>
									<span className="text-sm opacity-70">
										{momentumIcon(area.momentum)} {area.status}
									</span>
								</div>
								<p className="text-sm opacity-80">{area.headline}</p>
								<div className="flex gap-4 mt-2 text-xs opacity-60">
									{area.sessions > 0 && <span>{area.sessions} sessions</span>}
									{area.reading_count > 0 && <span>{area.reading_count} articles</span>}
								</div>
								{area.open_threads?.length > 0 && (
									<div className="mt-2 flex flex-wrap gap-1">
										{area.open_threads.map((t: string, j: number) => (
											<span key={j} className="text-xs bg-black/20 rounded px-2 py-0.5">
												{t}
											</span>
										))}
									</div>
								)}
							</div>
						))}
					</div>
				</section>
			)}

			{/* Learning */}
			{data.learning?.length > 0 && (
				<section>
					<h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
						Learning
					</h3>
					<div className="space-y-2">
						{data.learning.map((l: any, i: number) => (
							<div key={i} className="border border-zinc-800 rounded-lg p-4 bg-zinc-900/30">
								<div className="flex items-center justify-between">
									<span className="font-medium text-zinc-200">{l.topic}</span>
									<span className={`text-xs px-2 py-0.5 rounded border ${statusColor(l.status)}`}>
										{l.status}
									</span>
								</div>
								{l.connection && (
									<p className="text-sm text-zinc-400 mt-1">{l.connection}</p>
								)}
								{l.reading_count > 0 && (
									<p className="text-xs text-zinc-600 mt-1">{l.reading_count} articles</p>
								)}
							</div>
						))}
					</div>
				</section>
			)}

			{/* Risks & Recommendations */}
			<div className="grid gap-6 md:grid-cols-2">
				{/* Risks */}
				{data.risks?.length > 0 && (
					<section>
						<h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
							Risks
						</h3>
						<div className="space-y-2">
							{data.risks.map((r: any, i: number) => (
								<div key={i} className={`border rounded-lg p-3 ${severityColor(r.severity)}`}>
									<div className="flex items-center gap-2">
										<span className={`text-xs font-bold uppercase ${
											r.severity === "high" ? "text-red-400" :
											r.severity === "medium" ? "text-amber-400" : "text-zinc-400"
										}`}>
											{r.severity}
										</span>
										<span className="text-sm text-zinc-200">{r.headline}</span>
									</div>
									{r.detail && <p className="text-xs text-zinc-500 mt-1">{r.detail}</p>}
								</div>
							))}
						</div>
					</section>
				)}

				{/* Recommendations */}
				{data.recommendations?.length > 0 && (
					<section>
						<h3 className="text-sm font-medium text-zinc-400 uppercase tracking-wider mb-3">
							Recommendations
						</h3>
						<div className="space-y-2">
							{data.recommendations.map((rec: any, i: number) => (
								<div key={i} className="border border-zinc-800 rounded-lg p-3 bg-zinc-900/30">
									<div className="flex items-start gap-3">
										<span className="text-lg font-bold text-indigo-400 leading-none mt-0.5">
											{rec.priority}
										</span>
										<div>
											<p className="text-sm font-medium text-zinc-200">{rec.action}</p>
											{rec.rationale && (
												<p className="text-xs text-zinc-500 mt-1">{rec.rationale}</p>
											)}
										</div>
									</div>
								</div>
							))}
						</div>
					</section>
				)}
			</div>
		</div>
	);
}
```

**Verification:**
```bash
cd web && bun run build
```

---

### Task 7: Verification — Full Stack

**Verification steps:**

```bash
# 1. Python tests
uv run pytest tests/graph/test_briefing.py -x -q

# 2. TypeScript tests
cd web && bun test server/__tests__/graph.test.ts

# 3. Frontend build
cd web && bun run build

# 4. Generate a real briefing (requires Claude CLI + graph data)
uv run python -m distill graph briefing --output ./insights

# 5. Start server and check API
# (server should already be running, or start with: cd web && bun run server/index.ts)
curl http://localhost:6107/api/graph/briefing | python -m json.tool | head -30

# 6. Open browser to verify Briefing tab is default
# Navigate to http://localhost:6107/graph — should show Briefing tab first
```
