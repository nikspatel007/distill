"""CLI entry point for session-insights."""

import click

from . import __version__


@click.group()
@click.version_option(version=__version__, prog_name="session-insights")
def main() -> None:
    """Session Insights - Analyze AI coding assistant sessions."""
    pass


@main.command()
@click.argument("session_path", type=click.Path(exists=True))
@click.option(
    "--output",
    "-o",
    type=click.Path(),
    help="Output path for the generated report.",
)
@click.option(
    "--format",
    "-f",
    "output_format",
    type=click.Choice(["obsidian", "json", "text"]),
    default="obsidian",
    help="Output format for the report.",
)
def analyze(session_path: str, output: str | None, output_format: str) -> None:
    """Analyze a session file and generate insights.

    SESSION_PATH: Path to the session file to analyze.
    """
    click.echo(f"Analyzing session: {session_path}")
    click.echo(f"Output format: {output_format}")
    if output:
        click.echo(f"Output path: {output}")
    # TODO: Implement actual analysis logic


if __name__ == "__main__":
    main()
