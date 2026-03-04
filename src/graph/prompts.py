"""Prompt templates for knowledge graph context synthesis."""

from __future__ import annotations

import re
from typing import Any

# XML tag pattern for sanitization
_XML_TAG_RE = re.compile(r"</?[a-zA-Z][\w-]*(?:\s[^>]*)?>")


def _sanitize_text(text: str) -> str:
    """Strip XML tags, collapse whitespace, and truncate for prompt use."""
    cleaned = _XML_TAG_RE.sub("", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned[:200] if len(cleaned) > 200 else cleaned


def _filter_project_files(paths: list[str]) -> list[str]:
    """Filter out absolute paths outside the project and temp files."""
    result: list[str] = []
    for p in paths:
        # Skip absolute paths (outside project), temp files, plugin cache
        if p.startswith("/") or p.startswith("~"):
            continue
        result.append(p)
    return result


def get_context_prompt(data: dict[str, Any]) -> str:
    """Build the full prompt for context synthesis.

    Takes the structured output from ``GraphQuery.gather_context_data()``
    and formats it into a prompt that asks Claude to produce a concise
    markdown context block.
    """
    system = _SYSTEM_PROMPT
    user = _format_user_prompt(data)
    return f"{system}\n\n---\n\n{user}"


_SYSTEM_PROMPT = """\
You are a context synthesizer for a developer's knowledge graph. Your job is to \
produce a concise markdown context block that will be injected into a Claude Code \
session to give the AI assistant awareness of recent work.

Rules:
- Write in second person ("You were working on...")
- Be concise — aim for 150-300 words total
- Group by recency: what happened in the last few hours vs. earlier
- Highlight unresolved problems — these are the most actionable
- Show file areas being actively modified (group by directory when possible)
- Mention the tech stack only if it's relevant context
- If there's work in other projects, mention it briefly
- Use markdown headers (##) to organize sections
- Do NOT include relevance scores, node keys, or graph internals
- Do NOT invent information — only use what's provided in the data
- Output ONLY the markdown context block, nothing else
"""


def _format_user_prompt(data: dict[str, Any]) -> str:
    """Format the gathered context data into the user portion of the prompt."""
    lines: list[str] = []
    lines.append(f"Project: {data.get('project', '(all)')}")
    if data.get("time_window_hours"):
        lines.append(f"Time window: last {data['time_window_hours']:.0f} hours")
    lines.append("")

    sessions = data.get("sessions", [])
    if sessions:
        lines.append("## Recent Sessions")
        for s in sessions:
            hours = s.get("hours_ago", "?")
            summary = _sanitize_text(s.get("summary", s.get("id", "?")))
            lines.append(f"\n### {summary} ({hours}h ago)")
            goal = s.get("goal", "")
            if goal:
                goal = _sanitize_text(goal)
                if len(goal) > 5:
                    lines.append(f"Goal: {goal}")
            if s.get("project"):
                lines.append(f"Project: {s['project']}")
            if s.get("files_modified"):
                files = _filter_project_files(s["files_modified"])
                if files:
                    lines.append(f"Files modified: {', '.join(files)}")
            if s.get("files_read"):
                files = _filter_project_files(s["files_read"])
                if files:
                    lines.append(f"Files read: {', '.join(files)}")
            if s.get("problems"):
                for p in s["problems"]:
                    status = "RESOLVED" if p["resolved"] else "UNRESOLVED"
                    error = str(p.get("error", ""))[:120]
                    cmd = str(p.get("command", ""))[:80]
                    lines.append(f"Problem [{status}]: {error} (cmd: {cmd})")
            if s.get("entities"):
                lines.append(f"Tools/tech: {', '.join(s['entities'])}")
    else:
        lines.append("No recent sessions found.")

    top_entities = data.get("top_entities", [])
    if top_entities:
        lines.append("\n## Tech Stack (by frequency)")
        for e in top_entities:
            lines.append(f"- {e['name']}: {e['count']} sessions")

    active_files = data.get("active_files", [])
    if active_files:
        lines.append("\n## Active Files (recently modified)")
        for f in active_files:
            lines.append(f"- {f['path']} ({f['hours_ago']}h ago)")

    other_projects = data.get("other_projects", [])
    if other_projects:
        lines.append("\n## Other Projects")
        for op in other_projects:
            lines.append(f"- {op['project']}: {op['summary']} ({op['hours_ago']}h ago)")

    return "\n".join(lines)


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
            parts.append(
                f"- {o['project']}: {o.get('summary', '')} ({o.get('hours_ago', 0)}h ago)"
            )

    return "\n".join(parts)
