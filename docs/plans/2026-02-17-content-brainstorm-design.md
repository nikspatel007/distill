# Content Brainstorm Pipeline — Design

**Date:** 2026-02-17
**Status:** Approved

## Problem

We publish daily social posts and weekly blog posts, but content ideas are reactive — driven by whatever happened in coding sessions. We need a proactive pipeline that:

1. Reads new papers, articles, and posts from people we follow
2. Brainstorms daily on what content to publish
3. Outputs a content calendar with 2-3 focused ideas per day

## Content Pillars

All content ideas must connect to at least one pillar:

1. **Building multi-agent systems** — architecture, coordination, failure modes
2. **AI architecture patterns** — both human-organizational and technical
3. **Human-AI collaboration** — workflows, trust, delegation, oversight
4. **Evals and verification** — testing AI systems, quality gates, correctness
5. **Running an autonomous company** — building in public with AI agents

Configured in `.distill.toml` under `[brainstorm] pillars`.

## Architecture: TroopX 3-Agent Workflow

Three agents coordinate via agent-router MCP, communicating through the shared blackboard:

```
researcher → blackboard → analyst → blackboard → editor → seeds + Ghost + dashboard
```

### Agent 1: Researcher (gather)

**Job:** Fetch and summarize content from 3 source tiers.

**Tier 1 — Manual links + followed people (highest signal):**
- Reads `[brainstorm] followed_people` from `.distill.toml` (RSS/Atom feed URLs)
- Reads `[brainstorm] manual_links` for ad-hoc URLs
- Fetches each feed/URL, extracts title + summary + key points
- Reuses existing `RSSParser` logic for feed URLs; raw HTTP fetch + extraction for one-off links

**Tier 2 — Hacker News (community-curated):**
- Fetches HN front page via Algolia API (`hn.algolia.com/api/v1/search?tags=front_page`)
- Filters for stories with 50+ points
- Extracts title, URL, points, comment count

**Tier 3 — arXiv (research):**
- Queries arXiv API (`export.arxiv.org/api/query`) for configured categories
- Categories configured in `[brainstorm] arxiv_categories` (default: `cs.AI`, `cs.SE`, `cs.MA`)
- Fetches last 24h of new submissions
- Extracts title, authors, abstract, PDF link

**Output:** Writes to blackboard:
- `namespace=research`, `key=hn-findings` — JSON array of HN items
- `namespace=research`, `key=arxiv-findings` — JSON array of arXiv papers
- `namespace=research`, `key=followed-findings` — JSON array of feed items
- `namespace=research`, `key=manual-findings` — JSON array of manual link items

Each item: `{title, url, summary, source_tier, points?}`.

### Agent 2: Analyst (synthesize)

**Job:** Cross-reference research findings with user context, brainstorm content angles.

**Inputs:**
- Blackboard `namespace=research` (all researcher findings)
- Recent journal entries (last 3 days) from `insights/journal/`
- Unused seeds from `.distill-seeds.json`
- Active editorial notes from `.distill-notes.json`
- Project context from `.distill.toml` `[[projects]]`
- Content pillars from `.distill.toml` `[brainstorm] pillars`
- Published post history from `BlogMemory` (dedup + pillar gap detection)

**LLM prompt approach:**
1. Score each research finding against content pillars — drop anything that doesn't connect
2. Cross-reference with journal (what are we building right now?)
3. Cross-reference with BlogMemory (what have we already covered?)
4. Prioritize ideas that bridge multiple pillars
5. Weight toward underserved pillars (gap detection)
6. Produce 2-3 content ideas, each with title, angle, source, platform, rationale

**Output:** Writes to blackboard:
- `namespace=content-ideas`, `key=daily-calendar` — JSON array of content ideas

Each idea: `{title, angle, source_url, platform, rationale, pillars, tags}`.

- `platform` is one of: `blog`, `social`, `both`
- `pillars` lists which content pillars this idea serves

### Agent 3: Editor (output)

**Job:** Take content ideas and publish to 3 destinations.

**Destination 1 — Seeds** (`.distill-seeds.json`):
- Each content idea becomes a `SeedIdea` with `text=title + angle`, `tags=pillar tags`
- Seeds automatically flow into daily social + blog pipeline on next `distill run`

**Destination 2 — Ghost drafts:**
- For ideas with `platform=blog` or `platform=both`
- Creates Ghost draft post: title, 2-3 paragraph outline, tags from pillars
- Uses `GhostAPIClient.create_post(status="draft")`
- Stores Ghost post ID back in the content calendar JSON for reference

**Destination 3 — Dashboard data:**
- Writes `insights/content-calendar/YYYY-MM-DD.json` with all ideas + metadata
- Also writes human-readable `insights/content-calendar/YYYY-MM-DD.md`
- Dashboard page shows cards with approve/reject/edit actions
- Approving an idea marks it active in seeds; rejecting archives it

**Completion:** Signals `done` on workflow with summary message.

## Configuration

```toml
[brainstorm]
pillars = [
  "Building multi-agent systems",
  "AI architecture patterns",
  "Human-AI collaboration",
  "Evals and verification",
  "Running an autonomous company",
]
followed_people = [
  "https://simonwillison.net/atom/everything/",
  "https://martinfowler.com/feed.atom",
]
manual_links = []
arxiv_categories = ["cs.AI", "cs.SE", "cs.MA"]
hacker_news = true
hn_min_points = 50
```

## Interactive Mode

In addition to the automated TroopX workflow, users can run Claude Code interactively:

```
> brainstorm today's content

Claude reads the same sources + any existing blackboard results,
presents findings, and you iterate together in conversation.
```

This reuses the same source-fetching and analysis logic but in a conversational loop rather than agent pipeline.

## TroopX Workflow Definition

```yaml
workflow: content-brainstorm
agents:
  - name: researcher
    role: researcher
    description: "Fetch HN, arXiv, followed feeds, and manual links"
  - name: analyst
    role: analyst
    description: "Cross-reference findings with journal, seeds, pillars"
  - name: editor
    role: editor
    description: "Publish content ideas to seeds, Ghost drafts, dashboard"
states:
  - name: research
    agent: researcher
    next: analyze
    on_signal:
      done: analyze
      blocked: research
  - name: analyze
    agent: analyst
    next: publish
    on_signal:
      done: publish
      blocked: analyze
  - name: publish
    agent: editor
    next: complete
    on_signal:
      done: complete
```

## Data Flow

```
.distill.toml (config)
    ↓
[Researcher]
    → HN Algolia API → hn-findings
    → arXiv API → arxiv-findings
    → RSS feeds → followed-findings
    → manual URLs → manual-findings
    ↓ (blackboard)
[Analyst]
    ← journal entries (last 3 days)
    ← unused seeds
    ← editorial notes
    ← BlogMemory (published history)
    ← content pillars
    → daily-calendar (2-3 ideas)
    ↓ (blackboard)
[Editor]
    → .distill-seeds.json (SeedIdea per idea)
    → Ghost API (draft posts)
    → insights/content-calendar/YYYY-MM-DD.json
    → insights/content-calendar/YYYY-MM-DD.md
```

## New Files

| File | Purpose |
|------|---------|
| `src/brainstorm/config.py` | BrainstormConfig model, pillar definitions |
| `src/brainstorm/sources.py` | HN fetcher, arXiv fetcher, feed fetcher |
| `src/brainstorm/analyst.py` | Pillar scoring, gap detection, idea generation |
| `src/brainstorm/publisher.py` | Seeds + Ghost + calendar file output |
| `src/brainstorm/prompts.py` | LLM prompts for analysis and ideation |
| `web/server/routes/calendar.ts` | API route for content calendar |
| `web/src/routes/calendar.tsx` | Dashboard page for content calendar |

## Dashboard Page: Content Calendar

Shows daily content ideas as cards:

- **Date header** with navigation (prev/next day)
- **Card per idea**: title, angle, source link, pillars as colored tags, platform badge
- **Actions**: Approve (→ seed), Reject (→ archive), Edit (inline)
- **Sidebar**: pillar coverage chart (which pillars are underserved this week)

## Testing Strategy

- Unit tests for each source fetcher (mock HTTP responses)
- Unit tests for analyst scoring/filtering logic
- Unit tests for editor output (seeds, Ghost mock, file output)
- Integration test for full pipeline with mocked sources
- Dashboard tests (API + frontend)
