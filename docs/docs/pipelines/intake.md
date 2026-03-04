# Intake (Reading Digest)

The intake pipeline ingests content from RSS feeds and other sources, then uses Claude to synthesize a daily reading digest.

## Basic usage

```bash
uv run python -m distill intake --output ./insights --use-defaults
```

## How it works

```
RSS feeds, shared URLs, browser history, etc.
    ↓
Content parsers (source-specific)
    ↓
Canonical ContentItem list
    ↓
Enrichment: full-text extraction, auto-tagging, entity extraction
    ↓
Clustering by topic
    ↓
Claude synthesis → daily digest markdown
    ↓
Publishers: Obsidian, Ghost, Postiz
```

## Sources

### Built-in RSS feeds (default)

Distill ships with 90+ curated feeds covering AI, engineering, and tech. Enable with `--use-defaults` or:

```toml
[intake]
use_defaults = true
```

### Custom RSS feeds

```toml
[intake]
rss_feeds = [
    "https://blog.example.com/feed",
    "https://newsletter.example.com/rss.xml",
]
```

Or use OPML export from your RSS reader:

```bash
uv run python -m distill intake --output ./insights --opml subscriptions.opml
```

### Shared URLs

URLs shared from your phone or CLI get priority treatment in the digest. See [Sharing from Phone](../dashboard/sharing.md).

### Browser history

```bash
uv run python -m distill intake --output ./insights --browser-history
```

Reads Chrome and Safari history. Filters out common domains (Google, GitHub, localhost).

### Discovery (active search)

Searches the web for topics you care about:

```toml
[discovery]
topics = ["AI agents", "LLM evaluation"]
people = ["Simon Willison"]
max_results_per_query = 5
max_age_days = 3
```

### Other sources

| Source | Flag / Config | Extra deps |
|--------|--------------|------------|
| Substack | `--substack-blogs URL1,URL2` | None |
| Reddit | `--reddit-user NAME` | `praw` |
| YouTube | `--youtube-api-key KEY` | `google-api-python-client` |
| Gmail | `--gmail-credentials path/to/creds.json` | `google-api-python-client` |
| LinkedIn | `--linkedin-export path/to/export/` | None |
| Twitter/X | `--twitter-export path/to/export/` | None |
| Claude sessions | `--include-sessions --global-sessions` | None |

## Enrichment

Every content item goes through:

1. **Full-text extraction** — trafilatura fetches and parses the full article
2. **Auto-tagging** — keyword-based topic detection
3. **Entity extraction** — LLM identifies people, companies, technologies
4. **Classification** — LLM categorizes content type and relevance

Shared URLs are enriched first with a dedicated budget to guarantee coverage.

## Deduplication

The intake pipeline tracks processed items in `.intake-state.json`. Running twice on the same day won't re-process articles. Use `--force` to bypass:

```bash
uv run python -m distill intake --output ./insights --force
```

## Dry run

Preview what would be processed without calling the LLM:

```bash
uv run python -m distill intake --output ./insights --dry-run
```

## Output

The digest is written to `./insights/intake/YYYY-MM-DD.md` in Obsidian-compatible markdown with YAML frontmatter.

## Seed ideas

Inject your own topics into the digest:

```bash
uv run python -m distill seed "The intersection of AI and climate modeling"
```

Seeds are consumed by the next intake run and marked as used.
