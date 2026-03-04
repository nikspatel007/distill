# CLI Commands

All commands are run with `uv run python -m distill <command>` or the `distill` script if installed.

## `distill` (bare)

Run the full pipeline and start the web server.

```bash
uv run python -m distill --output ./insights
```

| Flag | Default | Description |
|------|---------|-------------|
| `--dir, -d` | `.` | Session directory |
| `--output, -o` | `./insights` | Output directory |
| `--port, -p` | `6107` | Web server port |
| `--no-run` | | Skip pipeline, just start server |
| `--no-serve` | | Skip server, just run pipeline |
| `--verbose, -v` | | Verbose logging |
| `--version, -V` | | Show version |

## `distill run`

Full pipeline: sessions + journal + intake + blog.

```bash
uv run python -m distill run --output ./insights --use-defaults
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output, -o` | `./insights` | Output directory |
| `--dir, -d` | `.` | Session directory |
| `--global` | `false` | Scan `~/.claude`, `~/.codex` |
| `--use-defaults` | `true` | Use built-in 90+ RSS feeds |
| `--publish` | `obsidian` | Comma-separated publishers |
| `--skip-sessions` | | Skip session parsing |
| `--skip-intake` | | Skip intake pipeline |
| `--skip-blog` | | Skip blog generation |
| `--model` | | Override LLM model |
| `--force` | | Bypass deduplication |
| `--dry-run` | | Preview without LLM calls |
| `--since` | 2 days ago | Date to look back from |

## `distill intake`

Ingest feeds and generate a reading digest.

```bash
uv run python -m distill intake --output ./insights --use-defaults
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output, -o` | required | Output directory |
| `--sources, -s` | auto-detect | Comma-separated: `rss,reddit,youtube,...` |
| `--use-defaults` | | Use built-in feeds |
| `--feeds-file` | | Path to feeds list file |
| `--opml` | | Path to OPML file |
| `--model` | | Override LLM model |
| `--words` | `800` | Target word count |
| `--publish` | `obsidian` | Output publishers |
| `--force` | | Reprocess all items |
| `--dry-run` | | Preview context |
| `--browser-history` | | Include browser history |
| `--substack-blogs` | | Comma-separated Substack URLs |
| `--reddit-user` | | Reddit username |
| `--youtube-api-key` | | YouTube API key |
| `--gmail-credentials` | | Path to Gmail credentials.json |
| `--include-sessions` | | Include coding sessions |
| `--global-sessions` | | Scan global session dirs |

## `distill journal`

Generate journal entries from coding sessions.

```bash
uv run python -m distill journal --output ./insights --global
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output, -o` | `./insights` | Output directory |
| `--dir, -d` | `.` | Session directory |
| `--style, -s` | `dev-journal` | Style preset |
| `--date` | today | Specific date |
| `--since` | | Generate since date |
| `--global` | `false` | Scan global sessions |
| `--words` | `600` | Target word count |
| `--model` | | Override model |
| `--force` | | Regenerate cached |
| `--dry-run` | | Preview context |

## `distill blog`

Generate blog posts from journal entries.

```bash
uv run python -m distill blog --output ./insights
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output, -o` | required | Output directory |
| `--type, -t` | `all` | `weekly`, `thematic`, or `all` |
| `--week` | | Specific week: `2026-W09` |
| `--publish` | | Publishers: `obsidian,ghost,postiz` |
| `--model` | | Override model |
| `--words` | `1200` | Target word count |
| `--force` | | Regenerate existing |
| `--dry-run` | | Preview context |

## `distill serve`

Start the web dashboard.

```bash
uv run python -m distill serve --output ./insights
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output, -o` | `./insights` | Output directory |
| `--port, -p` | `6107` | HTTP port |
| `--dev` | | Dev mode (API only, no static) |
| `--tls-cert` | | TLS certificate path |
| `--tls-key` | | TLS private key path |

## `distill share`

Share a URL for the next intake digest.

```bash
uv run python -m distill share "https://example.com" --note "interesting"
```

## `distill shares`

List shared URLs.

```bash
uv run python -m distill shares --all
```

## `distill seed`

Add a topic idea for the next digest.

```bash
uv run python -m distill seed "AI agents for code review" --tags "ai,agents"
```

## `distill seeds`

List seed ideas.

```bash
uv run python -m distill seeds --all
```

## `distill note`

Add an editorial note to guide content.

```bash
uv run python -m distill note "Focus on MCP servers" --target "week:2026-W09"
```

## `distill status`

Show pipeline state and statistics.

```bash
uv run python -m distill status --output ./insights
```
