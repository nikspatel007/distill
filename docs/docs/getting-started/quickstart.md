# Quickstart

Get Distill running in 5 minutes. All you need is Python and an Anthropic API key.

## Prerequisites

| Requirement | Version | Install |
|------------|---------|---------|
| Python | 3.11+ | [python.org](https://www.python.org/downloads/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Bun | latest | `curl -fsSL https://bun.sh/install \| bash` (for web dashboard) |

## Step 1: Clone and install

```bash
git clone https://github.com/nikspatel007/distill.git
cd distill
uv sync
```

This installs all Python dependencies including `trafilatura` (article extraction), `feedparser` (RSS), and the `anthropic` SDK.

## Step 2: Set your API key

=== "Environment variable"

    ```bash
    export ANTHROPIC_API_KEY=sk-ant-api03-...
    ```

=== ".env file"

    Create a `.env` file in the project root:

    ```
    ANTHROPIC_API_KEY=sk-ant-api03-...
    ```

Distill uses the Anthropic Python SDK directly. The default model is `claude-sonnet-4-6`.

## Step 3: Run your first digest

```bash
uv run python -m distill intake --output ./insights --use-defaults
```

This will:

1. Fetch articles from 90+ built-in RSS feeds (tech, AI, engineering)
2. Extract full text from each article using trafilatura
3. Auto-tag and classify content
4. Send everything to Claude for synthesis
5. Write a markdown digest to `./insights/intake/YYYY-MM-DD.md`

!!! info "First run takes 2-3 minutes"
    Most time is spent fetching RSS feeds and extracting article text. The LLM synthesis itself takes ~30 seconds.

## Step 4: Read your digest

Open the generated file:

```bash
cat ./insights/intake/$(date +%Y-%m-%d).md
```

Or start the web dashboard:

```bash
uv run python -m distill serve --output ./insights
```

Then open [http://localhost:6107](http://localhost:6107) in your browser.

## Step 5: Add your own feeds

Create `.distill.toml` in the project root:

```toml
[user]
name = "Your Name"
role = "software engineer"

[intake]
use_defaults = true  # keep the built-in 90+ feeds
rss_feeds = [
    "https://your-favorite-blog.com/feed",
    "https://another-blog.com/rss.xml",
]
```

Run again:

```bash
uv run python -m distill intake --output ./insights
```

## What's next

- **Automate it**: [Set up a daily cron](automation.md) so digests appear every morning
- **Web dashboard**: [Start the dashboard](../dashboard/setup.md) to browse digests
- **Share from phone**: [Set up iOS Shortcut](../dashboard/sharing.md) to share articles
- **Customize**: [Full configuration reference](configuration.md)

## Full pipeline (optional)

If you also use Claude Code or Codex CLI, Distill can generate a dev journal from your coding sessions and synthesize blog posts:

```bash
# Everything: sessions + journal + intake + blog
uv run python -m distill run --output ./insights --use-defaults --global
```

The `--global` flag scans `~/.claude` and `~/.codex` for session data.
