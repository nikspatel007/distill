# Distill

Personal intelligence platform. Ingests everything you read and build, synthesizes highlights, generates draft posts, tracks your learning trajectory, and discovers what you should read next.

## Project Structure

```
src/
  analyzers/                  # Pattern detection from session data
  blog/                       # Blog synthesis pipeline
    config.py                 # BlogConfig, BlogPostType, Platform, GhostConfig
    context.py                # WeeklyBlogContext, ThematicBlogContext preparation
    diagrams.py               # Mermaid diagram generation for blog posts
    formatter.py              # Thin re-export: ObsidianPublisher as BlogFormatter
    prompts.py                # LLM prompts for blog synthesis
    reader.py                 # Journal entry reader + IntakeDigestEntry for blog input
    state.py                  # BlogState tracking (what's been generated)
    synthesizer.py            # BlogSynthesizer - LLM-based content generation
    themes.py                 # Theme detection and thematic post generation
    blog_memory.py            # BlogMemory/BlogPostSummary for cross-referencing
    publishers/               # Multi-platform output
      base.py                 # BlogPublisher ABC
      obsidian.py             # Obsidian wiki links
      ghost.py                # Ghost CMS markdown
      markdown.py             # Plain markdown
      postiz.py               # Postiz social media scheduler
      twitter.py, linkedin.py, reddit.py  # Social publishers
  brief/                      # Daily reading brief + intelligence layer
    models.py                 # ReadingBrief, ReadingHighlight, DraftPost
    services.py               # generate_reading_brief() — orchestrates the full brief
    store.py                  # JSON persistence (.distill-reading-brief.json)
    prompts.py                # LLM prompts for highlight extraction + draft generation
    connection.py             # ConnectionInsight — links today's reading to past threads/entities
    learning.py               # TopicTrend — topic attention tracking over 14-day window
    discovery.py              # DiscoveryItem — finds new content based on reading patterns
  formatters/                 # Output formatters
    obsidian.py               # Obsidian markdown (wiki links, frontmatter)
    project.py                # Per-project note formatter
    templates.py              # Formatting templates
    weekly.py                 # Weekly digest formatter
  intake/                     # Content ingestion pipeline
    parsers/                  # Source parsers (RSS, browser, substack, etc.)
    publishers/               # Intake output publishers
    config.py                 # Per-source config models
    models.py                 # ContentItem, ContentSource, ContentType
    seeds.py                  # SeedStore + SeedIdea
    intelligence.py           # LLM entity extraction + classification
    context.py                # Intake context partitioning
  integrations/               # External service integrations
    postiz.py                 # Postiz API client
    scheduling.py             # Postiz scheduling helpers
  journal/                    # Journal synthesis pipeline
    cache.py                  # Journal entry caching (skip regeneration)
    config.py                 # JournalConfig (style, word count, model)
    context.py                # DailyContext preparation for LLM synthesis
    formatter.py              # Journal markdown formatting
    memory.py                 # Working memory (cross-session context)
    prompts.py                # Journal generation prompts
    synthesizer.py            # JournalSynthesizer - LLM journal generation
  memory/                     # Unified cross-pipeline memory
    models.py                 # UnifiedMemory, DailyEntry, MemoryThread, EntityRecord
    services.py               # load/save unified memory
  pipeline/                   # Pipeline orchestration
    intake.py                 # Intake pipeline (includes brief + discovery generation)
    blog.py                   # Blog pipeline
    journal.py                # Journal pipeline
    social.py                 # Social publishing coordination
  voice/                      # Voice learning system
    models.py                 # VoiceProfile, VoiceRule — learned writing style
    services.py               # Voice extraction from editing history
    store.py                  # Voice profile persistence (.distill-voice.json)
    prompts.py                # Voice analysis prompts
  graph/                      # Knowledge graph + executive briefing
    briefing.py               # BriefingGenerator — executive-level summary
  measurers/                  # Quality KPI measurers
  models/                     # Core data models (Insight, etc.)
  parsers/                    # Session parsers (Claude, Codex)
  shared/                     # Shared utilities
    config.py                 # Unified config (.distill.toml + env vars)
    llm.py                    # LLM call utilities
  cli.py                      # CLI entry point (Typer app)
  core.py                     # Legacy pipeline orchestration
  editorial.py                # EditorialStore - user steering notes
  store.py                    # JsonStore / PgvectorStore
  embeddings.py               # Sentence-transformer embeddings (optional)
tests/                        # 1800+ tests (unit + integration)
```

## Essential Commands

```bash
# Run all tests
uv run pytest tests/ -x -q

# Run specific test file
uv run pytest tests/blog/test_formatter.py -x -q

# Type checking
uv run mypy src/ --no-error-summary

# Lint and format
uv run ruff check src/ && uv run ruff format src/

# Run the CLI
uv run python -m distill analyze --dir . --output ./insights
uv run python -m distill journal --dir . --output ./insights --global
uv run python -m distill blog --output ./insights --type all
uv run python -m distill intake --output ./insights --use-defaults
uv run python -m distill run --dir . --output ./insights --use-defaults
uv run python -m distill brief --output ./insights --date 2026-03-05
uv run python -m distill note "Emphasize X this week" --target "week:2026-W06"
```

## Key Architecture

### Pipeline Flow
```
Raw sessions (.claude/, .codex/)
    -> Parsers (claude.py, codex.py) -> BaseSession models
    -> Analyzers (pattern detection, statistics)
    -> Formatters (Obsidian notes, project notes, weekly digests)
    -> Journal synthesizer (LLM: sessions -> daily journal entries)
        + project context from .distill.toml
    -> Intake (RSS, browser, social -> ContentItem -> daily digest)
    -> Reading brief (filter reading-only items -> 3 highlights + LinkedIn/X drafts)
        + voice profile for style consistency
        + connection engine (link reading to past threads/entities)
        + learning pulse (topic attention trends over 14 days)
    -> Discovery engine (active topics -> Claude web search -> curated recommendations)
    -> Blog synthesizer (LLM: journal entries -> weekly/thematic blog posts)
        + project context + editorial notes
    -> Publishers (Obsidian, Ghost, Postiz, social)
```

### Configuration
- `.distill.toml` loaded by `config.py:load_config()` (CWD then ~/.config/distill/)
- `ProjectConfig` in `[[projects]]` — injected into all LLM prompts
- `EditorialStore` in `.distill-notes.json` — user steering notes
- Environment variables overlay TOML values
- CLI flags overlay everything

### LLM Integration
- Journal and blog synthesis call Claude via subprocess (`claude -p`)
- `BlogSynthesizer` and `JournalSynthesizer` both use `subprocess.run`
- Prompts are in `blog/prompts.py` and `journal/prompts.py`
- Project context and editorial notes injected into rendered prompts
- Configurable model and timeout via config objects

### Blog Pipeline
- `core.py:generate_blog_posts()` orchestrates blog generation
- Loads `DistillConfig` for project context, `EditorialStore` for notes
- Reads journal entries via `blog/reader.py`
- Builds context via `blog/context.py` (WeeklyBlogContext, ThematicBlogContext)
- Detects themes via `blog/themes.py`
- Synthesizes via `blog/synthesizer.py`
- Publishes via `blog/publishers/` (fan-out to multiple platforms)
- Tracks state via `blog/state.py` (avoids re-generating existing posts)

### Intake Pipeline
- Fan-in: 8 source parsers -> canonical ContentItem
- Enrichment: full-text extraction, auto-tagging, entity extraction
- Optional: sentence-transformer embeddings + pgvector store
- Synthesis: LLM daily digest
- Fan-out: publishers (obsidian, ghost, postiz)
- After intake: generates reading brief + runs discovery engine

### Reading Brief Pipeline (`src/brief/`)
- `services.py:generate_reading_brief()` — orchestrates the full brief
- Filters intake items to reading-only sources (RSS, browser, substack, reddit, gmail, manual, discovery, youtube)
- Step 1: LLM extracts 3 highlights with interestingness ranking
- Step 2: LLM generates LinkedIn + X draft posts from highlights (voice profile applied)
- Step 3: `connection.py:find_connection()` — algorithmic matching against UnifiedMemory (threads, entities, themes)
- Step 4: `learning.py:compute_learning_pulse()` — scans 14 days of intake archives, classifies topics as trending/cooling/emerging/stable
- Step 5: `discovery.py:discover_content()` — extracts active topics, asks Claude to find fresh content, deduplicates against already-read URLs
- Output: `.distill-reading-brief.json` (list of dated briefs) + `.distill-discoveries.json`
- All steps are wrapped in try/except — failures don't block the pipeline

### Voice System (`src/voice/`)
- `VoiceProfile` learns writing style from editing history
- `render_for_prompt(min_confidence=0.5)` injects voice rules into LLM prompts
- Applied to reading brief drafts and blog synthesis
- Persistence: `.distill-voice.json`

## Conventions

- **Python 3.11+**, managed with `uv`
- **Pydantic v2** for all models and validation
- **Typer** for CLI (app instance in `cli.py`)
- **Strict mypy** type checking
- **ruff** for linting and formatting (line length 100)
- Test files mirror source structure: `src/.../foo.py` -> `tests/.../test_foo.py`
- Optional deps: try/except with `_HAS_X` flag, define name in except block
- Coverage target: 90%+

## Web Dashboard

The web dashboard lives in `web/` — Bun + Hono (server) + React + Tailwind + TanStack Router (frontend).

### Port Convention (ENFORCED)

All services use the **6100 series** to stay consistent and avoid conflicts.

| Service | Port | Notes |
|---------|------|-------|
| Postiz app (HTTP) | **6100** | Internal, behind Caddy |
| PostgreSQL (Postiz) | **6101** | Docker |
| Redis | **6102** | Docker |
| OpenSearch | **6103** | Docker |
| Temporal gRPC | **6104** | Docker |
| PostgreSQL (Temporal) | **6105** | Docker |
| Postiz HTTPS (Caddy) | **6106** | Public endpoint |
| Distill API server | **6107** | Default in `web/server/lib/config.ts`, CLI `--port` flag |
| Vite dev server | **6108** | Only used during `bun run dev` (frontend HMR) |
| Server tests | **6109** | Used in `web/server/__tests__/` via `setConfig()` |

- The canonical API port is **6107**. All agents, scripts, and tools must use port 6107 for the API server.
- Vite's dev proxy forwards `/api` requests from 6108 → 6107 (see `web/vite.config.ts`).
- In production (`distill serve`), only port 6107 is exposed (Hono serves both API + static files).
- Tests use port 6109 to avoid conflicts with running dev servers.
- **Never** introduce new arbitrary ports. If you need a port, use one from the table above.

### Web Commands

```bash
cd web && bun test server    # Run server tests
cd web && bun test src       # Run frontend tests
cd web && bun run build      # Build frontend (tsc + vite)
cd web && bun run dev        # Dev mode (vite HMR on 6108 + API on 6107)
```

### Web Conventions

- Zod schemas in `web/shared/schemas.ts` are the single source of truth for types
- Biome v1.9 for formatting/linting (NOT v2)
- `noUncheckedIndexedAccess` is enabled — null-coalesce optional fields
- Tests must pass `NO_COLOR=1` env when invoking CLI (GitHub Actions sets `FORCE_COLOR`)

## Known Issues

- `test_verify_all_kpis.py` depends on local data files and may fail in clean clones
