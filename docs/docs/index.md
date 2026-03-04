# Distill

**Turn your daily reading into a synthesized digest — powered by Claude.**

Distill is a personal content pipeline that ingests RSS feeds, shared links, browser history, and social media — then uses Claude to synthesize a daily reading digest. It runs locally on your Mac, serves a web dashboard, and optionally publishes to Ghost, social media, or Obsidian.

## What it does

1. **Intake** — Pulls content from 90+ RSS feeds (built-in), plus any sources you add
2. **Enrich** — Fetches full article text, auto-tags, extracts entities
3. **Synthesize** — Claude reads everything and writes a concise daily digest
4. **Publish** — Outputs to Obsidian markdown, Ghost CMS, or social platforms

## Minimum to get started

You need two things:

- **Python 3.11+** with [uv](https://docs.astral.sh/uv/)
- **An Anthropic API key** (`ANTHROPIC_API_KEY`)

```bash
# Clone and install
git clone https://github.com/nikspatel007/distill.git
cd distill
uv sync

# Set your API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run your first digest
uv run python -m distill intake --output ./insights --use-defaults
```

That's it. Distill ships with 90+ curated RSS feeds. Your first digest appears in `./insights/intake/`.

## What's included

| Feature | What you get |
|---------|-------------|
| Daily reading digest | LLM-synthesized summary of your feeds |
| Web dashboard | Browse digests, manage shares, read articles |
| Phone sharing | Share URLs from your phone via iOS Shortcut |
| Journal | Auto-generated dev journal from coding sessions |
| Blog | Weekly/thematic blog posts from journal entries |
| Social publishing | Push content to Twitter, LinkedIn, Reddit via Postiz |

## Next steps

- [Quickstart](getting-started/quickstart.md) — Full setup in 5 minutes
- [Configuration](getting-started/configuration.md) — Customize feeds, models, and outputs
- [Daily Automation](getting-started/automation.md) — Set up a daily cron
- [Web Dashboard](dashboard/setup.md) — Browse your digests in a browser
- [Share from Phone](dashboard/sharing.md) — iOS Shortcut + Tailscale setup
