"""CLI interface for session-insights."""

import json
from datetime import date, datetime
from pathlib import Path
from typing import Annotated, Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from session_insights.core import (
    AnalysisResult,
    analyze,
    discover_sessions,
    parse_session_file,
)
from session_insights.formatters.obsidian import ObsidianFormatter
from session_insights.models import BaseSession
from session_insights.parsers.claude import ClaudeParser
from session_insights.parsers.codex import CodexParser

app = typer.Typer(
    name="session-insights",
    help="Analyze AI coding assistant sessions and generate Obsidian notes.",
)

console = Console()


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        from session_insights import __version__

        console.print(f"session-insights {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-v",
            help="Show version and exit.",
            callback=version_callback,
            is_eager=True,
        ),
    ] = False,
) -> None:
    """Session Insights - Analyze AI coding assistant sessions."""
    pass


def _generate_index(
    sessions: list[BaseSession],
    daily_sessions: dict[date, list[BaseSession]],
    result: AnalysisResult,
) -> str:
    """Generate an index.md file linking all sessions.

    Args:
        sessions: All analyzed sessions.
        daily_sessions: Sessions grouped by date.
        result: Analysis result with patterns and stats.

    Returns:
        Markdown content for the index file.
    """
    lines = [
        "---",
        "type: index",
        f"created: {datetime.now().strftime('%Y-%m-%dT%H:%M:%S')}",
        f"total_sessions: {len(sessions)}",
        "---",
        "",
        "# Session Insights Index",
        "",
        "## Overview",
        "",
        f"- **Total Sessions**: {len(sessions)}",
        f"- **Total Days**: {len(daily_sessions)}",
    ]

    # Add date range if available
    if result.stats.date_range:
        start, end = result.stats.date_range
        lines.append(f"- **Date Range**: {start.date()} to {end.date()}")

    lines.extend(["", "## Sessions by Date", ""])

    # List sessions grouped by date
    for summary_date in sorted(daily_sessions.keys(), reverse=True):
        date_sessions = daily_sessions[summary_date]
        daily_link = f"[[daily/daily-{summary_date.isoformat()}|{summary_date.isoformat()}]]"
        lines.append(f"### {daily_link}")
        lines.append("")

        for session in sorted(date_sessions, key=lambda s: s.start_time):
            time_str = session.start_time.strftime("%H:%M")
            session_link = f"[[sessions/{session.note_name}]]"
            summary = session.summary[:60] + "..." if session.summary and len(session.summary) > 60 else (session.summary or "No summary")
            lines.append(f"- {time_str} - {session_link}: {summary}")

        lines.append("")

    # Add patterns section if available
    if result.patterns:
        lines.extend(["## Detected Patterns", ""])
        for pattern in result.patterns:
            lines.append(f"- {pattern.description}")
        lines.append("")

    return "\n".join(lines)


@app.command()
def analyze_cmd(
    directory: Annotated[
        Path,
        typer.Option(
            "--dir",
            "-d",
            help="Directory to scan for session history.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = Path("."),
    output: Annotated[
        Optional[Path],
        typer.Option(
            "--output",
            "-o",
            help="Output directory for Obsidian notes. Defaults to ./insights/",
        ),
    ] = None,
    output_format: Annotated[
        str,
        typer.Option(
            "--format",
            "-f",
            help="Output format. Currently only 'obsidian' is supported.",
        ),
    ] = "obsidian",
    source: Annotated[
        list[str] | None,
        typer.Option(
            "--source",
            "-s",
            help="Filter to specific sources (claude, codex, vermas).",
        ),
    ] = None,
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help="Only analyze sessions after this date (YYYY-MM-DD).",
        ),
    ] = None,
    include_conversation: Annotated[
        bool,
        typer.Option(
            "--include-conversation/--no-conversation",
            help="Include full conversation in notes.",
        ),
    ] = False,
    include_global: Annotated[
        bool,
        typer.Option(
            "--global/--no-global",
            help="Also scan home directory (~/.claude, ~/.codex) for sessions.",
        ),
    ] = False,
) -> None:
    """Analyze session history and generate Obsidian notes.

    Scans the specified directory for AI assistant session files and generates
    Obsidian-compatible markdown notes. Use --global to also include sessions
    from your home directory.
    """
    # Validate format option
    if output_format != "obsidian":
        console.print(f"[red]Error:[/red] Unsupported format: {output_format}")
        console.print("Currently only 'obsidian' format is supported.")
        raise typer.Exit(1)

    # Set default output directory if not provided
    if output is None:
        output = Path("./insights/")

    # Parse since date if provided
    since_date: date | None = None
    if since:
        try:
            since_date = datetime.strptime(since, "%Y-%m-%d").date()
        except ValueError:
            console.print(f"[red]Error:[/red] Invalid date format: {since}")
            console.print("Use YYYY-MM-DD format (e.g., 2024-01-15)")
            raise typer.Exit(1)

    # Create output directory if it doesn't exist and confirm
    output.mkdir(parents=True, exist_ok=True)
    console.print(f"Output will be written to: {output}")

    # Discover sessions
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Discovering session files...", total=None)
        discovered = discover_sessions(directory, source, include_home=include_global)

    if not discovered:
        console.print("[yellow]No session files found.[/yellow]")
        console.print(f"Searched in: {directory}")
        if source:
            console.print(f"Filtered to sources: {', '.join(source)}")
        raise typer.Exit(0)

    # Report discovery
    total_files = sum(len(files) for files in discovered.values())
    console.print(f"[green]Found {total_files} session file(s):[/green]")
    for src, files in discovered.items():
        console.print(f"  - {src}: {len(files)} file(s)")

    # Parse sessions
    all_sessions: list[BaseSession] = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Parsing sessions...", total=total_files)

        for src, files in discovered.items():
            for file_path in files:
                sessions = parse_session_file(file_path, src)
                # Filter by date if specified
                if since_date:
                    sessions = [
                        s for s in sessions if s.start_time.date() >= since_date
                    ]
                all_sessions.extend(sessions)
                progress.advance(task)

    if not all_sessions:
        console.print("[yellow]No sessions found after parsing.[/yellow]")
        if since_date:
            console.print(f"Date filter: sessions after {since_date}")
        raise typer.Exit(0)

    console.print(f"[green]Parsed {len(all_sessions)} session(s)[/green]")

    # Analyze sessions
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Analyzing patterns...", total=None)
        result = analyze(all_sessions)

    # Create subdirectories
    sessions_dir = output / "sessions"
    sessions_dir.mkdir(exist_ok=True)

    # Format and write notes
    formatter = ObsidianFormatter(include_conversation=include_conversation)
    written_count = 0
    daily_sessions: dict[date, list[BaseSession]] = {}

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Writing Obsidian notes...", total=len(all_sessions))

        for session in all_sessions:
            # Write session note
            note_content = formatter.format_session(session)
            note_path = sessions_dir / f"{session.note_name}.md"
            note_path.write_text(note_content, encoding="utf-8")
            written_count += 1

            # Collect for daily summary
            session_date = session.start_time.date()
            if session_date not in daily_sessions:
                daily_sessions[session_date] = []
            daily_sessions[session_date].append(session)

            progress.advance(task)

    # Write daily summaries
    daily_dir = output / "daily"
    daily_dir.mkdir(exist_ok=True)

    for summary_date, sessions in daily_sessions.items():
        daily_content = formatter.format_daily_summary(sessions, summary_date)
        daily_path = daily_dir / f"daily-{summary_date.isoformat()}.md"
        daily_path.write_text(daily_content, encoding="utf-8")

    # Write index.md linking all sessions
    index_content = _generate_index(all_sessions, daily_sessions, result)
    index_path = output / "index.md"
    index_path.write_text(index_content, encoding="utf-8")

    # Report results
    console.print()
    console.print("[bold green]Analysis complete![/bold green]")
    console.print(f"  Sessions: {written_count}")
    console.print(f"  Daily summaries: {len(daily_sessions)}")
    console.print(f"  Output: {output}")

    # Show statistics
    if result.stats.date_range:
        start, end = result.stats.date_range
        console.print(f"  Date range: {start.date()} to {end.date()}")

    if result.patterns:
        console.print()
        console.print("[bold]Detected patterns:[/bold]")
        for pattern in result.patterns:
            console.print(f"  - {pattern.description}")


# Register the analyze command with a cleaner name
app.command(name="analyze")(analyze_cmd)


@app.command(name="sessions")
def sessions_cmd(
    directory: Annotated[
        Path,
        typer.Option(
            "--dir",
            "-d",
            help="Directory to scan for .claude/ and .codex/ session directories.",
            exists=True,
            file_okay=False,
            dir_okay=True,
            resolve_path=True,
        ),
    ] = Path("."),
    include_global: Annotated[
        bool,
        typer.Option(
            "--global/--no-global",
            help="Also scan home directory (~/.claude, ~/.codex) for sessions.",
        ),
    ] = False,
) -> None:
    """Discover sessions and print a JSON summary.

    Scans the specified directory for .claude/ and .codex/ directories,
    uses the existing parsers to extract sessions, and prints a simple
    JSON summary with session count, total messages, and date range.
    Use --global to also include sessions from your home directory.
    """
    claude_parser = ClaudeParser()
    codex_parser = CodexParser()

    claude_sessions: list[BaseSession] = []
    codex_sessions: list[BaseSession] = []

    # Collect directories to scan
    dirs_to_scan = [directory]
    if include_global:
        home = Path.home()
        if home != directory:
            dirs_to_scan.append(home)

    for scan_dir in dirs_to_scan:
        # Find .claude/ directory
        claude_dir = scan_dir / ".claude"
        if claude_dir.exists() and claude_dir.is_dir():
            claude_sessions.extend(claude_parser.parse_directory(claude_dir))

        # Find .codex/ directory
        codex_dir = scan_dir / ".codex"
        if codex_dir.exists() and codex_dir.is_dir():
            codex_sessions.extend(codex_parser.parse_directory(codex_dir))

    # Combine all sessions
    all_sessions = claude_sessions + codex_sessions

    # Calculate summary statistics
    total_sessions = len(all_sessions)
    total_messages = sum(len(s.messages) for s in all_sessions)

    # Calculate date range
    date_range_start: str | None = None
    date_range_end: str | None = None
    if all_sessions:
        timestamps = [s.timestamp for s in all_sessions]
        earliest = min(timestamps)
        latest = max(timestamps)
        date_range_start = earliest.isoformat()
        date_range_end = latest.isoformat()

    # Build summary
    summary = {
        "session_count": total_sessions,
        "total_messages": total_messages,
        "date_range": {
            "start": date_range_start,
            "end": date_range_end,
        },
        "sources": {
            "claude": len(claude_sessions),
            "codex": len(codex_sessions),
        },
    }

    # Output JSON
    console.print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    app()
