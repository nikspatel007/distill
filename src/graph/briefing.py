"""Executive briefing — LLM-synthesized personal intelligence from the knowledge graph."""

from __future__ import annotations

import json
import logging
import os
import re as _re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from distill.graph.insights import GraphInsights, format_insights_for_prompt
from distill.graph.prompts import get_briefing_prompt
from distill.graph.query import GraphQuery
from distill.graph.store import GraphStore

logger = logging.getLogger(__name__)

BRIEFING_FILENAME = ".distill-briefing.json"


class BriefingArea(BaseModel):
    """A project or focus area with momentum tracking."""

    name: str
    status: str = "active"
    momentum: str = "steady"
    headline: str = ""
    sessions: int = 0
    reading_count: int = 0
    open_threads: list[str] = Field(default_factory=list)


class BriefingLearning(BaseModel):
    """A reading/learning topic and its connection to active work."""

    topic: str
    reading_count: int = 0
    connection: str = ""
    status: str = "emerging"


class BriefingRisk(BaseModel):
    """A risk with severity and plain-English description."""

    severity: str = "medium"
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
            # Extract title from first heading after frontmatter
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
        raise BriefingSynthesisError(
            f"Claude exited with code {result.returncode}: {result.stderr[:200]}"
        )

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
        recommendations=[
            BriefingRecommendation.model_validate(r)
            for r in data.get("recommendations", [])
        ],
    )

    save_briefing(briefing, output_dir)
    return briefing


class BriefingSynthesisError(Exception):
    """Raised when briefing synthesis fails."""
