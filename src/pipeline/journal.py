"""Journal pipeline — sessions → daily journal entries."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from distill.shared.errors import PipelineReport

from distill.core import _atomic_write
from distill.parsers import BaseSession

logger = logging.getLogger(__name__)


def generate_journal_notes(
    sessions: list[BaseSession],
    output_dir: Path,
    *,
    target_dates: list[date] | None = None,
    style: str = "dev-journal",
    target_word_count: int = 600,
    force: bool = False,
    dry_run: bool = False,
    model: str | None = None,
    report: PipelineReport | None = None,
    project_context: str = "",
) -> list[Path]:
    """Generate journal entries from sessions using LLM synthesis.

    Args:
        sessions: All parsed sessions.
        output_dir: Root output directory. Notes go in output_dir/journal/.
        target_dates: Dates to generate for. If None, generates for all dates.
        style: Journal style name (dev-journal, tech-blog, etc.).
        target_word_count: Target word count for each entry.
        force: Bypass cache and regenerate.
        dry_run: Print context without calling LLM.
        model: Optional Claude model override.

    Returns:
        List of written journal file paths.
    """
    from distill.journal import (
        JournalCache,
        JournalConfig,
        JournalFormatter,
        JournalStyle,
        JournalSynthesizer,
        load_memory,
        prepare_daily_context,
        save_memory,
    )
    from distill.memory import DailyEntry, load_unified_memory, save_unified_memory
    from distill.trends import detect_trends, render_trends_for_prompt

    config = JournalConfig(
        style=JournalStyle(style),
        target_word_count=target_word_count,
        model=model,
    )
    cache = JournalCache(output_dir)
    synthesizer = JournalSynthesizer(config)
    formatter = JournalFormatter(config)

    # Determine target dates
    if target_dates is None:
        all_dates: set[date] = {s.start_time.date() for s in sessions}
        target_dates = sorted(all_dates)

    written: list[Path] = []
    # Load both legacy and unified memory
    memory = load_memory(output_dir)
    unified = load_unified_memory(output_dir)

    # Inject trends into unified memory prompt
    trends = detect_trends(unified)
    if trends:
        unified.inject_trends(render_trends_for_prompt(trends))

    for target_date in target_dates:
        day_sessions = [s for s in sessions if s.start_time.date() == target_date]
        if not day_sessions:
            continue

        # Check cache
        if not force and cache.is_generated(target_date, config.style, len(day_sessions)):
            continue

        context = prepare_daily_context(day_sessions, target_date, config)
        context.project_context = project_context
        # Use unified memory for prompt context, fall back to legacy
        unified_text = unified.render_for_prompt(focus="sessions")
        context.previous_context = unified_text if unified_text else memory.render_for_prompt()

        # Append knowledge graph context if available
        try:
            from distill.graph.query import GraphQuery
            from distill.graph.store import GraphStore

            graph_store = GraphStore(path=output_dir)
            if graph_store.node_count() > 0:
                gq = GraphQuery(graph_store)
                graph_data = gq.gather_context_data(max_hours=168.0, max_sessions=5)
                if graph_data.get("sessions"):
                    from distill.graph.prompts import _format_user_prompt

                    graph_section = (
                        "\n\n## Knowledge Graph Context\n"
                        + _format_user_prompt(graph_data)
                    )
                    context.previous_context += graph_section

                # Append structural insights (coupling, hotspots, scope warnings)
                from distill.graph.insights import (
                    GraphInsights,
                    format_insights_for_prompt,
                )

                gi = GraphInsights(graph_store)
                daily = gi.generate_daily_insights(lookback_hours=48.0)
                insights_section = format_insights_for_prompt(daily)
                if insights_section:
                    context.previous_context += "\n\n" + insights_section

                # Persist insights back into the graph (feedback loop)
                gi.persist_insights(daily)
                graph_store.save()
        except Exception:
            pass  # graph is optional

        if dry_run:
            # Dry run prints context and skips LLM
            print(context.render_text())
            print("---")
            continue

        try:
            prose = synthesizer.synthesize(context)
        except Exception as exc:
            logger.warning("Synthesis failed for %s: %s", target_date, exc)
            if report:
                report.add_error(
                    "journal",
                    str(exc),
                    source="synthesizer",
                    error_type="synthesis_error",
                )
            continue

        # Extract memory from prose (second LLM call)
        try:
            daily_entry, threads = synthesizer.extract_memory(prose, target_date)
            memory.add_entry(daily_entry)
            memory.update_threads(threads)
            memory.prune(config.memory_window_days)
            save_memory(memory, output_dir)

            # Update unified memory
            unified.add_entry(
                DailyEntry(
                    date=target_date,
                    sessions=[s.summary or "" for s in day_sessions[:5]],
                    themes=daily_entry.themes if hasattr(daily_entry, "themes") else [],
                    insights=daily_entry.key_insights
                    if hasattr(daily_entry, "key_insights")
                    else [],
                    decisions=(
                        daily_entry.decisions_made if hasattr(daily_entry, "decisions_made") else []
                    ),
                    open_questions=(
                        daily_entry.open_questions if hasattr(daily_entry, "open_questions") else []
                    ),
                )
            )
            from distill.memory import MemoryThread as UnifiedThread

            unified_threads = []
            for t in threads:
                unified_threads.append(
                    UnifiedThread(
                        name=t.name,
                        summary=t.summary if hasattr(t, "summary") else "",
                        first_seen=t.first_mentioned
                        if hasattr(t, "first_mentioned")
                        else target_date,
                        last_seen=t.last_mentioned if hasattr(t, "last_mentioned") else target_date,
                        status=t.status if hasattr(t, "status") else "active",
                    )
                )
            unified.update_threads(unified_threads)
            unified.prune(keep_days=30)
            save_unified_memory(unified, output_dir)
        except Exception:
            logger.warning(
                "Memory extraction failed for %s, continuing without update",
                target_date,
                exc_info=True,
            )

        markdown = formatter.format_entry(context, prose)

        out_path = formatter.output_path(output_dir, context)
        _atomic_write(out_path, markdown)

        cache.mark_generated(target_date, config.style, len(day_sessions))
        written.append(out_path)

    return written
