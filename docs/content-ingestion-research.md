# Content Ingestion Research

**Date:** 2026-02-07
**Status:** Research Complete, Implementation Pending

## Goal

Ingest content from social media and reading sources into Distill's pipeline so we can synthesize daily research notes, track what we're consuming, and generate original thoughts alongside our coding journals and blog posts.

## Sources

### 1. RSS Feeds

**Priority: Highest** | **Effort: Low** | **Value: High**

RSS is the simplest and most reliable way to ingest content from blogs, news sites, and publications. Most content sources (including Substack) expose RSS feeds.

**Approach:**
- Use `feedparser` library to parse RSS/Atom feeds
- Maintain a list of feed URLs in config (OPML import support)
- Poll feeds on a schedule, deduplicate by URL/GUID
- Extract full article content with `trafilatura` when feeds only provide excerpts

**Key libraries:**
- `feedparser` — battle-tested RSS/Atom parser
- `trafilatura` — full article extraction from URLs
- `opml` — import/export feed lists from other readers

**Config example:**
```yaml
intake:
  rss:
    feeds:
      - https://simonwillison.net/atom/everything
      - https://blog.pragmaticengineer.com/rss/
      - https://newsletter.semianalysis.com/feed
    opml_file: ~/feeds.opml  # optional bulk import
    poll_interval_minutes: 60
```

**Advantages:**
- No authentication required for most feeds
- Standardized format, well-supported libraries
- Works with blogs, news sites, Substack, Medium, Ghost, WordPress
- Can replace Substack-specific parsing for most use cases
- OPML import means easy migration from any RSS reader

---

### 2. Substack

**Priority: High** | **Effort: Low** | **Value: High**

Substack newsletters are a primary reading source. Every Substack publication exposes an RSS feed at `https://{publication}.substack.com/feed`.

**Approach (primary):** RSS feed parsing via the RSS parser above — simplest path.

**Approach (alternative):** `substack-api` Python library for richer metadata.

**Key libraries:**
- `substack-api` — Python client for Substack's internal API
- RSS fallback at `https://{name}.substack.com/feed`

**Data available:**
- Post title, body (HTML), author, publication date
- Subtitle, preview text
- Comments (via API only)

**Notes:**
- RSS approach is preferred since it shares infrastructure with general RSS parsing
- `substack-api` is useful if we need comments or subscriber-only content
- Free posts are fully available via RSS; paid posts show previews only

---

### 3. Reddit

**Priority: High** | **Effort: Low-Medium** | **Value: High**

Reddit activity (upvotes, saves, comments) represents curated content — things we've already signaled interest in.

**Approach:** PRAW (Python Reddit API Wrapper) with OAuth2.

**Key libraries:**
- `praw` — official Python Reddit wrapper

**Setup:**
1. Create Reddit app at https://www.reddit.com/prefs/apps
2. Select "script" type for personal use
3. Get `client_id`, `client_secret`
4. Store in `.env`: `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET`, `REDDIT_USERNAME`, `REDDIT_PASSWORD`

**Data available:**
- Upvoted posts: `reddit.user.me().upvoted(limit=None)` (API cap: 1000 items)
- Saved posts/comments: `reddit.user.me().saved(limit=None)`
- Subscribed subreddits
- Comment history

**Limitations:**
- Reddit API returns max 1000 items per listing
- Rate limit: 100 requests/minute (generous for our use case)
- For complete history: GDPR data export (manual, one-time backfill)

**GDPR export for backfill:**
1. Request at https://www.reddit.com/settings/data-request
2. Arrives as ZIP with CSV files
3. Parse `upvoted_posts.csv`, `saved_posts.csv`, `comments.csv`

---

### 4. Gmail Newsletters

**Priority: High** | **Effort: Medium** | **Value: High**

Gmail contains newsletters, alerts, and digests that represent a significant portion of daily reading.

**Approach:** Gmail API with OAuth2.

**Key libraries:**
- `google-api-python-client` — Google API client
- `google-auth-oauthlib` — OAuth2 flow
- `html2text` — HTML to markdown conversion

**Setup:**
1. Create project in Google Cloud Console
2. Enable Gmail API
3. Create OAuth2 credentials (Desktop app type)
4. Download `credentials.json`
5. First run triggers browser OAuth flow, saves `token.json`

**Filtering strategy:**
```python
# Target newsletters specifically
query = "category:promotions OR label:newsletters"
# Or filter by known senders
query = "from:newsletter@substack.com OR from:digest@example.com"
```

**Data available:**
- Full email body (HTML → markdown via `html2text`)
- Subject, sender, date
- Labels for categorization
- Attachments (PDFs, etc.)

**Rate limits:** 250 quota units/user/second (generous — a single message read is 5 units)

**Notes:**
- OAuth2 setup is the main complexity; once done, it's reliable
- Consider filtering by label or sender list to avoid ingesting noise
- Token refresh is handled automatically by the library

---

### 5. Browser History

**Priority: Medium** | **Effort: Medium** | **Value: Medium**

Browser history captures what we're actually reading, but it's noisy (includes every page load).

**Approach:** Direct SQLite reads from browser profile databases + content extraction.

**Browser database locations (macOS):**

| Browser | Path |
|---------|------|
| Chrome | `~/Library/Application Support/Google/Chrome/Default/History` |
| Safari | `~/Library/Safari/History.db` |
| Firefox | `~/Library/Application Support/Firefox/Profiles/*.default-release/places.sqlite` |
| Arc | `~/Library/Application Support/Arc/User Data/Default/History` |

**Key libraries:**
- `browser-history` — cross-browser history access (convenience wrapper)
- `trafilatura` — article text extraction from URLs
- `sqlite3` — built-in, for direct DB access

**Filtering strategies (critical for noise reduction):**
- **Visit duration**: Chrome tracks `visit_duration` — filter for pages viewed > 30 seconds
- **Domain allowlist**: Only extract content from known article/blog domains
- **Domain blocklist**: Skip google.com, github.com, stackoverflow.com, localhost, etc.
- **URL patterns**: Skip URLs matching `/login`, `/settings`, `/search`, `/api/`
- **Frequency**: Pages visited multiple times may indicate reference material vs. articles

**Notes:**
- Browser must be closed OR copy the DB file before reading (SQLite lock)
- Content extraction via `trafilatura` needs rate limiting to avoid hammering sites
- This is the noisiest source — invest in good filtering before scaling up
- Consider only processing URLs from the last 24 hours for daily synthesis

---

### 6. LinkedIn

**Priority: Low** | **Effort: Low** | **Value: Low**

LinkedIn activity (likes, saves, shares) can surface professional content.

**Approach:** GDPR data export (only realistic option).

**Why not the API:**
- LinkedIn's API is locked down to approved partners
- < 10% approval rate for Marketing Developer Platform
- No public endpoint for likes, saves, or feed content
- Even "Sign in with LinkedIn" scope is extremely limited

**GDPR export process:**
1. Go to Settings > Data Privacy > Get a copy of your data
2. Select "Likes" and other relevant categories
3. Wait for email (usually 24-72 hours)
4. Download ZIP archive
5. Parse JSON/CSV files from the archive

**Data available from export:**
- Liked posts (URL, timestamp)
- Shares and comments
- Saved articles
- Connections (for context)

**Notes:**
- Manual trigger required — cannot be automated
- Best used for periodic backfill (monthly) rather than daily ingestion
- Parse the export files and cross-reference URLs with `trafilatura` for content

---

## Architecture

### Design Principles

The intake pipeline follows a **fan-in → canonical model → fan-out** pattern:

1. **Source adapters (fan-in)**: Each source has a parser that knows how to authenticate, fetch, and normalize data into `ContentItem` — the canonical model. A parser only runs if the user has configured credentials for it.
2. **Canonical model**: `ContentItem` is source-agnostic. The core pipeline (context building, deduplication, synthesis, memory) operates entirely on `ContentItem[]` and never knows which source produced an item.
3. **Output adapters (fan-out)**: Publishers format synthesized output for different targets (Obsidian, Ghost, markdown, journal injection). Each publisher only fires if enabled.
4. **Auth gating**: Everything is credential-aware. No credentials configured for Gmail? That parser is silently skipped. No Ghost config? That publisher doesn't fire. The system works with whatever the user has set up.

This mirrors the existing blog pipeline exactly:
- Blog: `JournalEntry[]` → `WeeklyBlogContext` → `BlogSynthesizer` → `BlogPublisher` (obsidian, ghost, markdown, twitter...)
- Intake: `ContentItem[]` → `DailyIntakeContext` → `IntakeSynthesizer` → `IntakePublisher` (obsidian, ghost, markdown, journal injection...)

```
  ┌─ RSS ──────────┐                                          ┌─ Obsidian Notes ─┐
  ├─ Gmail ────────┤   is_configured?                         ├─ Ghost CMS ──────┤
  ├─ Substack ─────┤──── skip if no ────► ContentItem[] ──►   ├─ Markdown ───────┤
  ├─ Reddit ───────┤     credentials      (canonical)         ├─ Journal ctx ────┤
  ├─ Browser ──────┤                          │               └─ Blog themes ────┘
  └─ LinkedIn ─────┘                          │                   is_enabled?
                                              ▼                   skip if not
                                   ┌───────────────────┐
                                   │  IntakeSynthesizer │
                                   │  (LLM: "what did  │
                                   │   I read today?")  │
                                   └───────────────────┘
```

### Source Adapter ABC

```python
class ContentParser(ABC):
    """Base class for source-specific content parsers.

    Mirrors the BlogPublisher pattern — each source implements
    parse() and is_configured. The pipeline skips unconfigured parsers.
    """

    @abstractmethod
    def parse(self, since: datetime | None = None) -> list[ContentItem]:
        """Fetch and parse content items from this source."""

    @abstractmethod
    @property
    def is_configured(self) -> bool:
        """Whether this parser has valid credentials/config to run."""

    @property
    def source(self) -> ContentSource:
        """The ContentSource enum value for this parser."""
        ...
```

Factory function (mirrors `create_publisher()`):

```python
def create_parser(
    source: ContentSource | str,
    *,
    config: IntakeConfig,
) -> ContentParser:
    """Create a parser for the given source.

    Returns a parser instance. Caller should check parser.is_configured
    before calling parse().
    """
```

### Output Adapter ABC

```python
class IntakePublisher(ABC):
    """Base class for intake output formatting.

    Same pattern as BlogPublisher — each target implements
    format_daily() and format_weekly().
    """

    @abstractmethod
    def format_daily(self, context: DailyIntakeContext, prose: str) -> str:
        """Format a daily intake digest for this target."""

    @abstractmethod
    def format_weekly(self, context: WeeklyIntakeContext, prose: str) -> str:
        """Format a weekly intake synthesis for this target."""

    @abstractmethod
    def daily_output_path(self, output_dir: Path, date: date) -> Path:
        """Compute the output file path for a daily digest."""

    @abstractmethod
    def weekly_output_path(self, output_dir: Path, year: int, week: int) -> Path:
        """Compute the output file path for a weekly synthesis."""
```

### Module Structure

```
src/intake/
    __init__.py
    models.py              # ContentItem, ContentSource, ContentType, Highlight
    config.py              # IntakeConfig (per-source credentials, filters, feed URLs)
    parsers/
        __init__.py        # create_parser() factory, get_configured_parsers()
        base.py            # ContentParser ABC
        rss.py             # RSSParser (feedparser + trafilatura)
        gmail.py           # GmailParser (Gmail API + html2text)
        substack.py        # SubstackParser (wraps RSS with Substack feed URLs)
        browser.py         # BrowserParser (SQLite + trafilatura)
        linkedin.py        # LinkedInExportParser (GDPR archive)
        reddit.py          # RedditParser (PRAW)
    publishers/
        __init__.py        # create_intake_publisher() factory
        base.py            # IntakePublisher ABC
        obsidian.py        # Obsidian-formatted intake notes
        ghost.py           # Ghost CMS intake posts
        markdown.py        # Plain markdown output
    context.py             # DailyIntakeContext, WeeklyIntakeContext
    memory.py              # IntakeMemory (tracks processed items, avoids dupes)
    prompts.py             # LLM prompts for daily/weekly synthesis
    synthesizer.py         # IntakeSynthesizer (claude -p subprocess)
```

### Canonical Data Model

```python
class ContentSource(str, Enum):
    RSS = "rss"
    GMAIL = "gmail"
    SUBSTACK = "substack"
    BROWSER = "browser"
    LINKEDIN = "linkedin"
    REDDIT = "reddit"
    MANUAL = "manual"

class ContentType(str, Enum):
    ARTICLE = "article"
    NEWSLETTER = "newsletter"
    POST = "post"
    COMMENT = "comment"
    VIDEO = "video"
    THREAD = "thread"
    WEBPAGE = "webpage"

class Highlight(BaseModel):
    text: str
    note: str = ""
    position: int = 0

class ContentItem(BaseModel):
    """Source-agnostic content item — the canonical model.

    Every source parser produces these. The core pipeline only
    operates on ContentItem[] and never knows which source
    produced an item. Analogous to BaseSession in the session
    parsing pipeline.
    """
    id: str                              # deduplication key (url hash or source-specific)
    url: str = ""
    title: str = ""
    body: str = ""                       # extracted text/markdown
    excerpt: str = ""
    word_count: int = 0
    author: str = ""
    site_name: str = ""
    source: ContentSource
    source_id: str = ""                  # source-specific ID (message ID, post ID, etc.)
    content_type: ContentType = ContentType.ARTICLE
    tags: list[str] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)  # LLM-extracted after ingestion
    published_at: datetime | None = None
    saved_at: datetime = Field(default_factory=datetime.now)
    consumed_at: datetime | None = None
    reading_progress: float = 0.0
    is_starred: bool = False
    highlights: list[Highlight] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)  # source-specific extras
```

### Auth-Gated Pipeline Flow

The orchestration function discovers which parsers are configured, runs them, merges into a single `ContentItem[]`, deduplicates, builds context, synthesizes, then fans out to enabled publishers:

```python
def generate_intake(
    config: IntakeConfig,
    output_dir: Path,
    sources: list[str] | None = None,    # None = all configured
    publish: list[str] | None = None,    # None = ["obsidian"]
) -> None:
    # Fan-in: collect from all configured sources
    items: list[ContentItem] = []
    for source in ContentSource:
        if sources and source.value not in sources:
            continue
        parser = create_parser(source, config=config)
        if not parser.is_configured:
            logger.info("Skipping %s (not configured)", source.value)
            continue
        items.extend(parser.parse(since=last_run))

    # Deduplicate by URL/id
    items = deduplicate(items)

    # Core pipeline: canonical model only
    context = DailyIntakeContext.from_items(items)
    prose = synthesizer.synthesize_daily(context)

    # Fan-out: publish to all enabled targets
    for platform in publish:
        publisher = create_intake_publisher(platform, config=config)
        content = publisher.format_daily(context, prose)
        path = publisher.daily_output_path(output_dir, date.today())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
```

### Cross-Pipeline Integration

The canonical model enables clean integration points with existing pipelines:

```
  ContentItem[]                        Existing Pipelines
  (canonical)                          ──────────────────
       │
       ├──► DailyIntakeContext ──────► IntakeSynthesizer ──► daily digest
       │
       ├──► inject into ─────────────► JournalSynthesizer
       │    journal prompts              ("What I read today while
       │    (context.py)                  working on X")
       │
       └──► weekly themes ───────────► BlogSynthesizer
            (ThemeDefinition)             (thematic posts sourced
                                          from reading + coding)
```

- **Intake → Journal**: `DailyIntakeContext` referenced in journal prompts
- **Intake → Blog**: Weekly intake themes feed `ThemeDefinition` detection
- **Journal → Intake**: Coding context informs intake synthesis

### Config Model

```python
class IntakeConfig(BaseModel):
    """All intake configuration — credentials, filters, feed URLs.

    Each source section is optional. Unconfigured sources are skipped.
    Supports env vars for secrets.
    """
    rss: RSSConfig = Field(default_factory=RSSConfig)
    gmail: GmailConfig = Field(default_factory=GmailConfig)
    reddit: RedditConfig = Field(default_factory=RedditConfig)
    browser: BrowserConfig = Field(default_factory=BrowserConfig)
    linkedin: LinkedInConfig = Field(default_factory=LinkedInConfig)

    # Global filters
    domain_blocklist: list[str] = ["google.com", "localhost", "github.com"]
    min_word_count: int = 100
    max_items_per_source: int = 50

class RSSConfig(BaseModel):
    feeds: list[str] = []          # feed URLs
    opml_file: str = ""            # path to OPML file
    @property
    def is_configured(self) -> bool:
        return bool(self.feeds or self.opml_file)

class GmailConfig(BaseModel):
    credentials_file: str = ""     # path to OAuth credentials.json
    token_file: str = ""           # path to saved token.json
    query: str = "category:promotions OR label:newsletters"
    @property
    def is_configured(self) -> bool:
        return bool(self.credentials_file)

class RedditConfig(BaseModel):
    client_id: str = ""            # from env: REDDIT_CLIENT_ID
    client_secret: str = ""        # from env: REDDIT_CLIENT_SECRET
    username: str = ""
    password: str = ""
    @property
    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)
    @classmethod
    def from_env(cls) -> "RedditConfig": ...

class BrowserConfig(BaseModel):
    browsers: list[str] = ["chrome"]  # which browsers to read
    min_visit_duration_seconds: int = 30
    domain_allowlist: list[str] = []   # if set, only these domains
    @property
    def is_configured(self) -> bool:
        return True  # always available (local SQLite)

class LinkedInConfig(BaseModel):
    export_path: str = ""          # path to GDPR export ZIP/dir
    @property
    def is_configured(self) -> bool:
        return bool(self.export_path)
```

### Output Layout

```
insights/intake/
    intake-2026-02-07.md          # daily digest
    intake-weekly-2026-W06.md     # weekly synthesis
    .intake-memory.json           # processed item tracking
    .intake-state.json            # generation state
```

### CLI

```bash
# Daily intake — runs all configured sources
uv run python -m distill intake --output ./insights

# Specific sources only
uv run python -m distill intake --output ./insights --sources rss,reddit

# With OPML import for RSS
uv run python -m distill intake --output ./insights --sources rss --opml ~/feeds.opml

# Publish to multiple targets
uv run python -m distill intake --output ./insights --publish obsidian,ghost

# All sources, all publishers
uv run python -m distill intake --output ./insights --sources all --publish all
```

---

## Dependencies

| Package | Purpose | Required For |
|---------|---------|-------------|
| `feedparser` | RSS/Atom feed parsing | RSS, Substack |
| `trafilatura` | Full article text extraction | RSS, Browser |
| `praw` | Reddit API wrapper | Reddit |
| `google-api-python-client` | Gmail API | Gmail |
| `google-auth-oauthlib` | Gmail OAuth2 | Gmail |
| `html2text` | HTML → markdown | Gmail |
| `substack-api` | Substack API (optional) | Substack |
| `browser-history` | Cross-browser history (optional) | Browser |

---

## Implementation Phases

### Phase 1: RSS + Substack (MVP)
- `models.py` — ContentItem, ContentSource, ContentType
- `parsers/base.py` — ContentParser ABC
- `parsers/rss.py` — RSS/Atom feed parser with feedparser
- `parsers/substack.py` — Thin wrapper pointing at Substack RSS feeds
- `config.py` — IntakeConfig with feed URLs
- `context.py` — DailyIntakeContext
- `synthesizer.py` — IntakeSynthesizer (claude -p)
- `prompts.py` — Daily synthesis prompts
- CLI wiring in `cli.py` and `core.py`

### Phase 2: Reddit
- `parsers/reddit.py` — PRAW integration
- GDPR export parser for backfill
- Config for Reddit credentials

### Phase 3: Gmail
- `parsers/gmail.py` — Gmail API + OAuth2
- `html2text` conversion
- Newsletter filtering logic

### Phase 4: Browser History
- `parsers/browser.py` — SQLite + trafilatura
- Visit duration filtering
- Domain allow/blocklists

### Phase 5: LinkedIn + Cross-Pipeline
- `parsers/linkedin.py` — GDPR export parser
- Journal ↔ Intake cross-referencing
- IntakeMemory for narrative continuity
- Weekly intake digest generation
