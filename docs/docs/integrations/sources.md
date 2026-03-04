# Optional Sources

Beyond RSS feeds, Distill can ingest content from several additional sources. Each requires either an API key or a data export.

## Reddit

Ingest your saved and upvoted posts.

**Install:**
```bash
uv add 'distill[reddit]'
```

**Configure:**
```toml
[reddit]
client_id = "your-client-id"
client_secret = "your-client-secret"
username = "your-reddit-username"
```

Create a Reddit app at [reddit.com/prefs/apps](https://www.reddit.com/prefs/apps/) (choose "script" type).

**Run:**
```bash
uv run python -m distill intake --output ./insights --sources rss,reddit
```

## YouTube

Ingest video metadata and transcripts from your liked/saved videos.

**Install:**
```bash
uv add 'distill[google]'
```

**Configure:**
```bash
export YOUTUBE_API_KEY=your-youtube-api-key
```

Get a key from [Google Cloud Console](https://console.cloud.google.com/apis/credentials) with YouTube Data API v3 enabled.

**Run:**
```bash
uv run python -m distill intake --output ./insights --sources rss,youtube
```

## Gmail (newsletters)

Ingest newsletters from your Gmail using the `List-Unsubscribe` header to identify newsletters.

**Install:**
```bash
uv add 'distill[google]'
```

**Setup:**

1. Create OAuth credentials in [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Enable the Gmail API
3. Download `credentials.json`

**Run:**
```bash
uv run python -m distill intake --output ./insights --gmail-credentials path/to/credentials.json
```

The first run opens a browser for OAuth consent. A `token.json` is saved for subsequent runs.

## Browser history

Read recently visited URLs from Chrome or Safari.

**No extra installation needed.**

```bash
uv run python -m distill intake --output ./insights --browser-history
```

Common domains (Google, GitHub, localhost, StackOverflow) are filtered out by default. Customize the blocklist in `.distill.toml`:

```toml
[intake]
browser_history = true
```

## Substack

Ingest posts from specific Substack newsletters:

```bash
uv run python -m distill intake --output ./insights \
  --substack-blogs "https://newsletter.example.com,https://another.substack.com"
```

Or in config:

```toml
[intake]
substack_blogs = [
    "https://newsletter.example.com",
    "https://another.substack.com",
]
```

This fetches the Substack RSS feed and extracts full article text.

## LinkedIn (GDPR export)

Import from your LinkedIn data export:

1. Request your data at [linkedin.com/mypreferences/d/download-my-data](https://www.linkedin.com/mypreferences/d/download-my-data)
2. Download and extract the ZIP

```bash
uv run python -m distill intake --output ./insights \
  --linkedin-export path/to/linkedin-export/
```

Reads: shares, articles, saved items, and reactions.

## Twitter/X (data export)

Import from your X data export:

1. Request your data at [x.com/settings/download_your_data](https://x.com/settings/download_your_data)
2. Download and extract the ZIP

```bash
uv run python -m distill intake --output ./insights \
  --twitter-export path/to/twitter-export/
```

## Combining sources

Use `--sources` to run specific sources, or omit it to auto-detect all configured sources:

```bash
# Specific sources
uv run python -m distill intake --output ./insights --sources rss,reddit,youtube

# All configured sources (auto-detected from config + env)
uv run python -m distill intake --output ./insights
```
