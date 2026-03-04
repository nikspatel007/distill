# Configuration

Distill is configured via `.distill.toml`. The file is searched in order:

1. `.distill.toml` in the current working directory
2. `~/.config/distill/.distill.toml`

Environment variables and CLI flags override TOML values.

## Minimal config

```toml
[user]
name = "Your Name"
role = "software engineer"

[intake]
use_defaults = true
```

This uses the built-in 90+ RSS feeds and default settings. Everything else is optional.

## Full reference

### `[user]` — Identity

Injected into LLM prompts so Claude tailors the digest to you.

```toml
[user]
name = "Jane Doe"
role = "ML engineer"
bio = "Building recommendation systems at Acme Corp"
```

### `[output]`

```toml
[output]
directory = "./insights"  # where all output goes
```

### `[intake]` — Reading digest

```toml
[intake]
use_defaults = true          # include built-in 90+ feeds
target_word_count = 800      # digest length
model = "claude-sonnet-4-6"  # LLM model
publishers = ["obsidian"]    # output format

# Custom RSS feeds (added on top of defaults)
rss_feeds = [
    "https://blog.example.com/feed",
    "https://newsletter.example.com/rss",
]

# Or point to a file with one URL per line
feeds_file = "my-feeds.txt"

# Or import from your RSS reader
opml_file = "subscriptions.opml"

# Optional sources
browser_history = false
substack_blogs = []
```

### `[journal]` — Dev journal

Generated from Claude Code / Codex CLI sessions.

```toml
[journal]
style = "dev-journal"         # dev-journal | tech-blog | team-update | building-in-public
target_word_count = 600
model = "claude-sonnet-4-6"
memory_window_days = 7
```

### `[blog]` — Blog posts

Synthesized from journal entries.

```toml
[blog]
target_word_count = 1200
include_diagrams = true       # Mermaid diagrams
model = "claude-sonnet-4-6"
platforms = ["obsidian"]      # obsidian | ghost | markdown | postiz
```

### `[sessions]`

```toml
[sessions]
sources = ["claude", "codex"]
include_global = false        # scan ~/.claude, ~/.codex
since_days = 2
```

### `[[projects]]` — Project context

Tell Claude about your projects so it can reference them intelligently.

```toml
[[projects]]
name = "MyApp"
description = "A React Native mobile app for habit tracking"
url = "https://github.com/you/myapp"
tags = ["react-native", "mobile"]

[[projects]]
name = "DataPipe"
description = "ETL pipeline processing 10M events/day on AWS"
tags = ["python", "aws", "data"]
```

### `[discovery]` — Active web search

Searches the web for recent content about your topics. Requires `ANTHROPIC_API_KEY`.

```toml
[discovery]
topics = ["AI agents", "LLM evaluation", "Claude MCP"]
people = ["Simon Willison", "Hamel Husain"]
max_results_per_query = 5
max_age_days = 3
```

### `[social]` — Brand hashtags

```toml
[social]
brand_hashtags = ["#BuildInPublic"]
secondary_hashtags = ["#AI", "#LLM"]
```

### `[server]`

```toml
[server]
hostname = "your-machine.ts.net"  # for iOS Shortcut sharing URL
```

### `[notifications]`

```toml
[notifications]
enabled = true
slack_webhook = "https://hooks.slack.com/services/..."
ntfy_url = "https://ntfy.sh"
ntfy_topic = "distill"
```

### `[intelligence]`

```toml
[intelligence]
model = "claude-haiku-4-5-20251001"  # cheap model for entity extraction
```

## Environment variables

Any config value can be overridden via environment variable. See the [full environment variable reference](../reference/env-vars.md).

The most important one:

```bash
export ANTHROPIC_API_KEY=sk-ant-api03-...
```
