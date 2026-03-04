# Journal

The journal pipeline generates daily developer journal entries from your Claude Code and Codex CLI sessions.

## Basic usage

```bash
uv run python -m distill journal --output ./insights --global
```

The `--global` flag scans `~/.claude` and `~/.codex` for session data.

## What it produces

A markdown journal entry for each day you had coding sessions, written by Claude based on what you actually built. Example output in `./insights/journal/2026-03-04.md`.

## Styles

```bash
uv run python -m distill journal --output ./insights --style dev-journal
```

| Style | Description |
|-------|------------|
| `dev-journal` | Technical narrative of what you built (default) |
| `tech-blog` | Blog-ready writeup of your work |
| `team-update` | Standup-style summary for team |
| `building-in-public` | Public-facing progress update |

## Configuration

```toml
[journal]
style = "dev-journal"
target_word_count = 600
model = "claude-sonnet-4-6"
memory_window_days = 7
```

## Memory

The journal keeps a rolling memory (`.working-memory.json`) so entries can reference previous days. This avoids repetition and builds narrative continuity.

## Specific dates

```bash
# Generate for a specific date
uv run python -m distill journal --output ./insights --date 2026-03-01

# Generate for all days since a date
uv run python -m distill journal --output ./insights --since 2026-03-01
```

## Project-scoped

```bash
uv run python -m distill journal --output ./insights --project MyApp
```

Only includes sessions related to the specified project.
