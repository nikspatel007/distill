"""Narrative generation for session insights.

Generates human-readable narrative summaries from session data,
transforming raw tool/outcome data into coherent stories about
what was accomplished.
"""

from __future__ import annotations

from session_insights.parsers.models import BaseSession


def generate_narrative(session: BaseSession) -> str:
    """Generate a human-readable narrative for a session.

    Combines summary, outcomes, tools used, tags, and task context
    into a coherent paragraph describing what happened in the session.

    Args:
        session: The session to narrate.

    Returns:
        A human-readable narrative string.
    """
    parts: list[str] = []

    # Opening: what the session was about
    if session.task_description:
        parts.append(f"Worked on: {session.task_description.strip()[:200]}.")
    elif session.summary:
        summary = session.summary.strip()
        if len(summary) > 200:
            summary = summary[:197] + "..."
        parts.append(summary)

    # Duration context
    duration = session.duration_minutes
    if duration is not None:
        if duration < 1:
            parts.append("This was a brief interaction.")
        elif duration < 10:
            parts.append(f"The session lasted about {int(duration)} minutes.")
        elif duration < 60:
            parts.append(f"The session ran for {int(duration)} minutes.")
        else:
            hours = int(duration // 60)
            mins = int(duration % 60)
            if mins:
                parts.append(f"The session spanned {hours}h {mins}m.")
            else:
                parts.append(f"The session spanned {hours} hour{'s' if hours > 1 else ''}.")

    # Tools narrative
    if session.tools_used:
        top_tools = sorted(session.tools_used, key=lambda t: t.count, reverse=True)[:3]
        tool_parts = [f"{t.name} ({t.count}x)" for t in top_tools]
        parts.append(f"Primary tools: {', '.join(tool_parts)}.")

    # Outcomes narrative
    if session.outcomes:
        successes = [o for o in session.outcomes if o.success]
        failures = [o for o in session.outcomes if not o.success]
        if successes:
            outcome_descriptions = [o.description for o in successes[:3]]
            parts.append("Accomplished: " + "; ".join(outcome_descriptions) + ".")
        if failures:
            fail_descriptions = [o.description for o in failures[:2]]
            parts.append("Incomplete: " + "; ".join(fail_descriptions) + ".")

        # Files modified
        all_files = []
        for o in session.outcomes:
            all_files.extend(o.files_modified)
        if all_files:
            parts.append(f"Touched {len(all_files)} file(s).")

    # Tags as activity context
    if session.tags:
        parts.append(f"Activity type: {', '.join(session.tags)}.")

    # VerMAS workflow context
    if session.cycle_info:
        ci = session.cycle_info
        if ci.outcome and ci.outcome != "unknown":
            parts.append(f"Workflow outcome: {ci.outcome}.")

    return " ".join(parts)


def enrich_narrative(session: BaseSession) -> None:
    """Populate the session's narrative field if empty.

    Modifies the session in-place.

    Args:
        session: The session to enrich.
    """
    if not session.narrative:
        session.narrative = generate_narrative(session)
