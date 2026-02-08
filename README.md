# Distill

Distill raw AI coding sessions into journals, blogs, and multi-platform publications.

Distill reads session data from AI coding assistants (Claude, Codex, VerMAS), ingests content from RSS feeds, browser history, and social platforms, then synthesizes everything into publishable content using Claude LLM.

## What It Does

```
Raw sessions (.claude/, .codex/)     External content (RSS, browser, social)
              \                              /
               \                            /
            ┌──────────────────────────────────┐
            │         distill run              │
            │                                  │
            │  1. Parse sessions               │
            │  2. Generate journal entries      │
            │  3. Ingest external content       │
            │  4. Synthesize daily digest       │
            │  5. Generate blog posts           │
            │  6. Publish everywhere            │
            └──────────────────────────────────┘
                           |
              ┌────────────┼────────────┐
              ▼            ▼            ▼
          Obsidian       Ghost      Social
          (local)     (newsletter)  (drafts)
```

**Pipeline steps:**

1. **Analyze** -- Parse sessions, compute statistics, detect patterns
2. **Journal** -- Synthesize daily journal entries from raw sessions via LLM
3. **Intake** -- Ingest RSS feeds, browser history, social saves into a daily digest
4. **Blog** -- Generate weekly synthesis posts and thematic deep-dives
5. **Publish** -- Distribute to Obsidian, Ghost CMS, Twitter/X, LinkedIn, Reddit

## Quickstart

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- [Claude CLI](https://docs.anthropic.com/en/docs/claude-code) (`claude` command) for LLM synthesis

### Install

```bash
git clone https://github.com/nikpatel/distill.git
cd distill
uv sync
```

For optional sources (Reddit, YouTube, Gmail):
```bash
uv sync --extra reddit        # Reddit saved/upvoted
uv sync --extra google         # YouTube + Gmail
uv sync --all-extras           # Everything
```

### First Run

```bash
# Analyze your AI coding sessions (no LLM needed)
distill analyze --dir . --output ./insights --global

# Generate a journal entry for today
distill journal --dir . --output ./insights --global

# Ingest RSS feeds and generate a daily digest
distill intake --output ./insights --use-defaults

# Run the full pipeline (sessions + intake + blog)
distill run --dir . --output ./insights --use-defaults
```

### Daily Automation

Run the full pipeline automatically every morning:

**macOS (launchd):**
```bash
# Edit the plist with your paths
cp scripts/daily-intake.sh ~/distill-daily.sh
# Set environment variables or edit the script:
export DISTILL_PROJECT_DIR="$HOME/distill"
export DISTILL_OUTPUT_DIR="$HOME/Documents/Obsidian Vault"
```

See `scripts/daily-intake.sh` for a ready-to-use template.

**Linux (cron):**
```bash
# Run at 7am daily
0 7 * * * cd ~/distill && uv run python -m distill run --dir $HOME --output ~/insights --use-defaults
```

## Commands

| Command | Description |
|---------|-------------|
| `distill analyze` | Parse sessions, compute stats, generate Obsidian notes |
| `distill journal` | Synthesize daily journal entries via LLM |
| `distill blog` | Generate blog posts from journal entries |
| `distill intake` | Ingest external content (RSS, browser, social) |
| `distill run` | Full pipeline: sessions + journal + intake + blog |
| `distill seed` | Add a seed idea for future content |
| `distill seeds` | List pending seed ideas |
| `distill sessions` | List discovered sessions as JSON |

Run `distill <command> --help` for detailed options.

## Content Sources

### Session Sources

| Source | Location | What It Captures |
|--------|----------|------------------|
| Claude | `~/.claude/projects/*/` | Claude Code session JSONL files |
| Codex | `.codex/sessions/` | Codex CLI session rollouts |
| VerMAS | `.vermas/state/` | Multi-agent workflow executions |

### Intake Sources

| Source | Flag / Config | What It Captures |
|--------|---------------|------------------|
| RSS | `--use-defaults` or `--feeds-file` | 90+ curated tech blogs, or your own feeds |
| Browser | `--browser-history` | Chrome and Safari browsing history |
| Substack | `--substack-blogs URL,URL` | Substack newsletter feeds |
| Reddit | `--reddit-user NAME` | Saved and upvoted posts (requires API creds) |
| YouTube | `--youtube-api-key KEY` | Watch history + transcripts |
| Gmail | `--gmail-credentials FILE` | Newsletter emails (via Google OAuth) |
| LinkedIn | `--linkedin-export DIR` | GDPR data export (shares, articles, saved) |
| Twitter/X | `--twitter-export DIR` | Data export + nitter RSS feeds |

## Configuration

### Environment Variables

All optional. Copy `.env.example` to `.env` and fill in what you need.

| Variable | Purpose |
|----------|---------|
| `GHOST_URL` | Ghost CMS instance URL |
| `GHOST_ADMIN_API_KEY` | Ghost Admin API key (`id:secret` format) |
| `GHOST_NEWSLETTER_SLUG` | Ghost newsletter for auto-send |
| `REDDIT_CLIENT_ID` | Reddit API app client ID |
| `REDDIT_CLIENT_SECRET` | Reddit API app secret |
| `REDDIT_USERNAME` | Reddit username |
| `REDDIT_PASSWORD` | Reddit password |
| `YOUTUBE_API_KEY` | YouTube Data API key |

### Publishing Platforms

Use `--publish` to target platforms (comma-separated):

```bash
# Publish to Obsidian (default)
distill blog --output ./insights --publish obsidian

# Publish to multiple platforms
distill blog --output ./insights --publish obsidian,ghost,markdown

# Social media content generation
distill blog --output ./insights --publish twitter,linkedin,reddit
```

| Platform | Output |
|----------|--------|
| `obsidian` | Obsidian-compatible markdown with wiki links |
| `ghost` | Ghost CMS markdown (publishes via API if configured) |
| `markdown` | Plain markdown with relative links |
| `twitter` | Thread format (5-8 tweets) |
| `linkedin` | Professional post with engagement hooks |
| `reddit` | Discussion post with TL;DR |

### Seed Ideas

Drop raw thoughts that get woven into your daily digest and blog posts:

```bash
distill seed "AI agents are the new APIs"
distill seed "The cost of context switching in deep work" --tags "productivity,focus"
distill seeds              # List pending seeds
distill seeds --all        # Include used seeds
```

## Project Structure

```
src/
  analyzers/           # Pattern detection from session data
  blog/                # Blog synthesis pipeline
    publishers/        # Multi-platform output (obsidian, ghost, social)
  formatters/          # Output formatters (Obsidian, project notes, weekly)
  intake/              # Content ingestion pipeline
    parsers/           # Source parsers (RSS, browser, social platforms)
    publishers/        # Intake output publishers
  journal/             # Journal synthesis pipeline
  parsers/             # Session parsers (Claude, Codex, VerMAS)
  cli.py               # CLI entry point (Typer)
  core.py              # Pipeline orchestration
tests/                 # 1500+ tests
scripts/               # Automation templates
```

## Development

```bash
# Install with dev dependencies
uv sync --all-extras

# Run tests
uv run pytest tests/ -x -q

# Lint and format
uv run ruff check src/ && uv run ruff format src/

# Type checking
uv run mypy src/ --no-error-summary
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines.

## License

[MIT](LICENSE)
