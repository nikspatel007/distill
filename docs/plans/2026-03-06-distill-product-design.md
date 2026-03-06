# Distill Product — Multi-User Intelligence Platform Design

## Vision

Turn Distill from a personal CLI tool into a multi-user product. Anyone you invite can sign up, share URLs, get their own Daily View with highlights and drafts, and see what others in the community are reading.

TypeScript end-to-end. React Native app. You run the infra, absorb LLM costs.

## Decisions Made

| Question | Answer |
|----------|--------|
| Who uses it? | You + friends/community (~50 users). You run infra. |
| How do users add content? | Share URLs only. You curate default RSS feeds. Zero config for users. |
| Who pays for LLM? | You absorb it (~$5-15/day at community scale). |
| Cloud hosting? | Render (API server + cron jobs). |
| Self-host option? | Yes — Docker Compose for privacy-conscious users. |
| Session ingestion? | Lightweight CLI agent (`distill sync`) pushes to cloud API. |
| App delivery? | React Native (Expo) — not PWA. |
| MVP scope? | Daily View + social feed (see what others highlighted/shared). |
| Auth provider? | Supabase (auth + Postgres in one). |
| Backend language? | TypeScript end-to-end (rewrite pipeline from Python). |

## Tech Stack

| Layer | Technology | Why |
|-------|------------|-----|
| Runtime | Bun | Already using it, fast, good DX |
| API | Hono | Already built, lightweight, works with Bun |
| Database | Supabase Postgres + Drizzle ORM | Managed Postgres, RLS for multi-tenant, Drizzle for type-safe queries |
| Auth | Supabase Auth | Social login (Google, Apple, GitHub), JWTs, no passwords |
| Realtime | Supabase Realtime | WebSocket subscriptions for social feed updates |
| LLM | AI SDK (`@ai-sdk/anthropic`) | Already wired up, streaming, structured output, tool use |
| Mobile | Expo (React Native) | TypeScript, file-based routing, OTA updates |
| Web | React + TanStack Router | Already built, keeps working alongside mobile |
| Shared types | Zod schemas | Single source of truth across web, mobile, API |
| Embeddings | pgvector extension | Semantic search within Postgres, no separate service |
| Images | Google Gemini API (`@google/genai`) | Hero images for highlights, social cards for drafts, feed thumbnails |
| Storage | Supabase Storage | Image hosting with CDN, no separate S3 bucket needed |

## Architecture

```
┌─────────────┐  ┌─────────────┐
│  Expo App   │  │  Web App    │
│  (React     │  │  (React +   │
│   Native)   │  │   Tailwind) │
└──────┬──────┘  └──────┬──────┘
       │                │
       │    Shared Zod   │
       │    schemas +    │
       │    API client   │
       │                │
       └───────┬────────┘
               │
        ┌──────▼──────┐
        │  Hono API   │
        │  + Auth MW  │
        │  (Bun)      │
        └──────┬──────┘
               │
     ┌─────────┼─────────┐
     │         │         │
┌────▼───┐ ┌──▼───┐ ┌───▼────┐
│Supabase│ │AI SDK│ │Pipeline│
│Postgres│ │(LLM) │ │(cron)  │
│+ Auth  │ │      │ │        │
└────────┘ └──────┘ └────────┘
```

### Monorepo Structure

```
packages/
  shared/              # Zod schemas, API client, types, constants
    schemas/
      user.ts          # UserProfile, UserPreferences
      brief.ts         # ReadingBrief, Highlight, DraftPost (port from Python models)
      social.ts        # FeedItem, Reaction, Follow
      intake.ts        # ContentItem, ContentSource (port from Python models)
    api-client.ts      # Typed fetch wrapper for all endpoints
    constants.ts       # Shared constants

  server/              # Hono API + pipeline
    routes/
      auth.ts          # Supabase auth callbacks
      brief.ts         # Daily View data endpoints
      share.ts         # URL sharing endpoints
      feed.ts          # Social feed endpoints
      chat.ts          # AI chat streaming
      intake.ts        # Pipeline trigger/status
    pipeline/
      intake.ts        # RSS + shared URLs → ContentItems
      brief.ts         # ContentItems → highlights + drafts (LLM)
      discovery.ts     # Active topics → web search → recommendations
      connection.ts    # Today's reading × history → insight
      learning.ts      # Topic attention over 14 days
    lib/
      db.ts            # Drizzle client + schema
      auth.ts          # Supabase auth middleware
      llm.ts           # AI SDK helpers
      rss.ts           # RSS parser wrapper
    jobs/
      daily.ts         # Cron: run pipeline per user

  web/                 # React web app (existing, extended)
    src/routes/
    src/components/

  mobile/              # Expo React Native app
    app/               # File-based routing (Expo Router)
      (tabs)/
        index.tsx      # Daily View
        feed.tsx       # Social feed
        share.tsx      # Share URL
        settings.tsx   # Profile + preferences
    components/
      highlights/      # "3 Things Worth Knowing" cards
      drafts/          # Draft post editor cards
      feed/            # Social feed items
```

## Data Model (Drizzle + Postgres)

### Core Tables

```typescript
// users — managed by Supabase Auth, extended with profile
const users = pgTable("users", {
  id: uuid("id").primaryKey(),                    // Supabase auth.users.id
  displayName: text("display_name").notNull(),
  avatarUrl: text("avatar_url"),
  createdAt: timestamp("created_at").defaultNow(),
});

// shared_urls — URLs users share (replaces distill share)
const sharedUrls = pgTable("shared_urls", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id).notNull(),
  url: text("url").notNull(),
  title: text("title"),                           // Auto-extracted
  note: text("note"),                             // Optional user note
  createdAt: timestamp("created_at").defaultNow(),
  processedAt: timestamp("processed_at"),         // null = pending pipeline
});

// content_items — canonical ingested content (per user)
const contentItems = pgTable("content_items", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id).notNull(),
  source: text("source").notNull(),               // "rss", "manual", "discovery"
  url: text("url"),
  title: text("title").notNull(),
  summary: text("summary"),
  fullText: text("full_text"),
  tags: jsonb("tags").$type<string[]>(),
  entities: jsonb("entities").$type<string[]>(),
  publishedAt: timestamp("published_at"),
  ingestedAt: timestamp("ingested_at").defaultNow(),
  embedding: vector("embedding", { dimensions: 1536 }),  // pgvector
});

// reading_briefs — daily briefs (per user)
const readingBriefs = pgTable("reading_briefs", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id).notNull(),
  date: date("date").notNull(),
  highlights: jsonb("highlights").$type<Highlight[]>(),
  drafts: jsonb("drafts").$type<DraftPost[]>(),
  connection: jsonb("connection").$type<ConnectionInsight>(),
  learningPulse: jsonb("learning_pulse").$type<TopicTrend[]>(),
  discoveries: jsonb("discoveries").$type<DiscoveryItem[]>(),
  createdAt: timestamp("created_at").defaultNow(),
}, (t) => ({
  userDate: uniqueIndex().on(t.userId, t.date),
}));

// follows — social graph
const follows = pgTable("follows", {
  followerId: uuid("follower_id").references(() => users.id).notNull(),
  followingId: uuid("following_id").references(() => users.id).notNull(),
  createdAt: timestamp("created_at").defaultNow(),
}, (t) => ({
  pk: primaryKey(t.followerId, t.followingId),
}));

// feed_items — materialized social feed (denormalized for fast reads)
const feedItems = pgTable("feed_items", {
  id: serial("id").primaryKey(),
  userId: uuid("user_id").references(() => users.id).notNull(),  // who did it
  type: text("type").notNull(),          // "highlight", "share", "draft_published"
  title: text("title").notNull(),
  summary: text("summary"),
  url: text("url"),
  metadata: jsonb("metadata"),           // type-specific data
  createdAt: timestamp("created_at").defaultNow(),
});

// default_feeds — RSS feeds you curate for all users
const defaultFeeds = pgTable("default_feeds", {
  id: serial("id").primaryKey(),
  url: text("url").notNull().unique(),
  name: text("name"),
  category: text("category"),            // "ai", "engineering", "startups"
  active: boolean("active").default(true),
});
```

### Row Level Security

Supabase RLS policies ensure users only see their own data:

```sql
-- Users can only read/write their own briefs
CREATE POLICY "users_own_briefs" ON reading_briefs
  USING (user_id = auth.uid());

-- Users can see feed items from people they follow
CREATE POLICY "feed_from_following" ON feed_items
  USING (user_id IN (
    SELECT following_id FROM follows WHERE follower_id = auth.uid()
  ) OR user_id = auth.uid());

-- Shared URLs are visible to followers
CREATE POLICY "shared_urls_visible" ON shared_urls
  USING (user_id IN (
    SELECT following_id FROM follows WHERE follower_id = auth.uid()
  ) OR user_id = auth.uid());
```

## Auth Flow

1. User opens app → Supabase Auth sign-in screen (Google / Apple / GitHub)
2. Supabase returns JWT → stored in secure storage (mobile) or httpOnly cookie (web)
3. Every API request includes `Authorization: Bearer <jwt>`
4. Hono middleware validates JWT via Supabase, injects `userId` into request context
5. All DB queries scoped by `userId` + RLS as safety net

No passwords. No email verification flow. Social login only.

## Pipeline (Per-User)

The pipeline runs as a cron job (e.g., every morning at 6 AM per user's timezone):

```
1. Collect sources
   - Default RSS feeds (shared across all users)
   - User's shared URLs (pending items from shared_urls table)
   - Discovery items from yesterday

2. Ingest → content_items
   - Parse RSS via rss-parser
   - Fetch shared URL metadata (title, summary via readability)
   - Auto-tag via LLM (batch)
   - Generate embeddings (Anthropic embeddings API or pgvector)

3. Generate brief
   - Filter to reading-only sources
   - LLM: extract 3 highlights ranked by interestingness
   - LLM: generate LinkedIn + X drafts (apply voice rules if user has them)
   - Algorithmic: find connection to user's history
   - Algorithmic: compute learning pulse (14-day topic scan)

4. Run discovery
   - Extract active topics from recent content
   - Claude web search for fresh content
   - Deduplicate against already-read URLs
   - Store as discovery items for tomorrow's intake

5. Publish to feed
   - Insert highlight items into feed_items table
   - Supabase Realtime broadcasts to followers
```

### Cost Control

At community scale (~50 users):
- ~50 brief generations/day × ~$0.10 each = ~$5/day
- ~50 discovery runs/day × ~$0.05 each = ~$2.50/day
- RSS fetching is free (shared across users, cached)
- Supabase free tier: 500MB DB, 50K monthly active users, 5GB bandwidth

Total: **~$8-15/day** for 50 users. Scales linearly.

## Social Feed

The social feed is the community layer — see what your friends are reading and highlighting.

**Feed items are created when:**
- A user's daily brief is generated (their highlights become feed items)
- A user shares a URL (becomes a "shared" feed item)
- A user publishes a draft (becomes a "published" feed item)

**Feed UI:**
- Chronological list of cards from people you follow
- Each card: avatar, name, type badge, title, summary snippet, timestamp
- Tap to expand / read source
- No likes, no comments (MVP) — just visibility

**Follow system:**
- Invite-only initially (you add users, they auto-follow each other)
- Later: follow/unfollow from profile pages

## Mobile App (Expo)

### Screens

**Daily View (Home tab):**
- "3 Things Worth Knowing" — swipeable highlight cards
- "Connection" — single insight card
- "Ready to Post" — draft cards with edit + copy + push
- "Learning Pulse" — sparkline chart (react-native-svg-charts or victory-native)
- "Explore Next" — discovery cards with save/dismiss
- Pull-to-refresh triggers brief reload

**Social Feed tab:**
- Scrollable feed of friend activity
- Type badges: "highlighted", "shared", "published"
- Tap card → opens source URL in in-app browser

**Share tab:**
- URL input field + optional note
- Paste from clipboard button
- Recent shares list
- Share sheet integration (iOS/Android share target)

**Settings tab:**
- Profile (name, avatar from social login)
- Notification preferences
- Connected accounts (future: X, Reddit)
- About / feedback

### Push Notifications

- Expo Notifications + Supabase Edge Function (or Hono webhook)
- Daily brief ready → push notification with top highlight title
- Friend shared something → optional push

## Image Generation (Gemini API)

Every highlight and draft post gets a generated image via Google Gemini (`@google/genai` TypeScript SDK). Makes the Daily View and social feed visually rich, and drafts are publish-ready with images.

**Where images appear:**
- **Highlight cards** — hero image for each of the 3 daily highlights (visual metaphor of the topic)
- **Draft posts** — social card image attached to LinkedIn/X drafts (ready to publish with image)
- **Feed items** — thumbnails in the social feed (your highlights show up with images for followers)
- **Discovery cards** — generated thumbnail for recommended content

**Pipeline integration:**
```
Highlights extracted (3 items)
    ↓
LLM generates image prompt per highlight (part of brief generation step)
    ↓
Gemini API generates images (parallel, 16:9 for hero, 1:1 for social cards)
    ↓
Upload to Supabase Storage → CDN URLs
    ↓
Store URLs in reading_briefs.highlights[].imageUrl + feed_items.metadata.imageUrl
```

**Cost:** Gemini image generation is ~$0.02-0.04 per image. At 3 highlights × 50 users = 150 images/day = ~$3-6/day.

**Graceful degradation:** No API key → no images → cards render without them. Image generation failure doesn't block the brief.

**Data model addition:**

```typescript
// Add to content_items and reading_briefs
imageUrl: text("image_url"),              // Supabase Storage CDN URL
imagePrompt: text("image_prompt"),        // For regeneration / debugging
```

## Engagement Tracking (Future)

Track likes/comments across social platforms to feed back into Distill.

| Platform | Status | Approach |
|----------|--------|----------|
| X | Viable | Pay-per-use API. `GET /2/users/:id/liked_tweets`. Credits-based, cheap at personal volume. |
| Reddit | Needs application | Self-service credentials ended Nov 2025. Apply via Developer Support form (~7 day approval). If approved, praw-equivalent in TS via snoowrap or raw API. |
| LinkedIn | Hard | `r_member_social_feed` restricted to approved partners. No public "list my reactions" endpoint. OAuth only gives openid/profile/email. Possible: browser extension or manual export. |

Build as a plugin system: each platform is an `EngagementSource` with `fetchRecentEngagements()` method. Results become `content_items` with source="engagement".

## Deployment

### Cloud (Render)

```
Render Web Service          → Hono API (Bun runtime)
Render Cron Job             → Daily pipeline per user (6 AM per timezone)
Supabase (managed)          → Postgres + Auth + Storage + Realtime
```

- Render supports Bun natively via Docker or `bun run` start command
- Single web service handles API + serves static web assets
- Cron job triggers pipeline via internal API call with service token
- Supabase is external (managed SaaS) — not on Render

### Self-Host (Docker Compose)

For users who don't want session data leaving their machine:

```yaml
# docker-compose.yml
services:
  api:
    build: .
    ports: ["6107:6107"]
    environment:
      - DATABASE_URL=postgres://distill:pw@db:5432/distill
      - SUPABASE_URL=          # or local Postgres + custom auth
      - ANTHROPIC_API_KEY=     # user provides their own
      - GOOGLE_AI_API_KEY=     # user provides their own
    depends_on: [db]

  db:
    image: pgvector/pgvector:pg16
    volumes: ["pgdata:/var/lib/postgresql/data"]

  cron:
    build: .
    command: bun run jobs/daily.ts
    depends_on: [api, db]

volumes:
  pgdata:
```

Self-host differences:
- User provides their own `ANTHROPIC_API_KEY` and `GOOGLE_AI_API_KEY`
- No Supabase — direct Postgres + simple JWT auth (or Supabase self-hosted)
- Session data stays on their machine (CLI syncs to localhost)
- No social feed (single-user mode)

## Session Ingestion — `distill sync` CLI

Users install a lightweight CLI that watches `~/.claude/` (and `.codex/`) and pushes session data to the cloud API.

### How it works

```
~/.claude/projects/*/          ← Claude Code session JSONL files
    ↓
distill sync (runs as background daemon or cron)
    ↓
Detects new/changed session files since last sync
    ↓
Redacts secrets (API keys, tokens, passwords) locally before upload
    ↓
Pushes session data to cloud API (encrypted in transit)
    ↓
POST /api/sessions/sync { sessions: [...] }
    ↓
Cloud pipeline: parse → journal synthesis → "What You Built" highlights
    ↓
Server stores sessions + generated content in Postgres (encrypted at rest, RLS-isolated)
```

Cloud needs the session content because the LLM generates journal entries, extracts patterns, and produces "What You Built" highlights — summaries alone aren't enough.

### Security Model

Session data is sensitive — it contains code, errors, file paths, internal tool usage. Same trust model as GitHub (you push code to a cloud service with access controls).

| What | Where it lives | Who sees it |
|------|---------------|-------------|
| Raw session data | Cloud DB (encrypted at rest, RLS) | User only |
| Journal entries | Cloud DB (encrypted at rest, RLS) | User only |
| "What You Built" highlights | Social feed (if user opts in) | Followers |

**Security measures:**
1. **Local redaction before upload** — Sync CLI strips secrets patterns (`API_KEY=`, `password=`, tokens, `.env` contents) before sending. File paths are preserved (needed for journal context) but hostnames/IPs are stripped.
2. **Encryption in transit** — HTTPS everywhere. API requires valid JWT.
3. **Encryption at rest** — Supabase Postgres encrypts data at rest. Render encrypts at rest.
4. **RLS isolation** — Row Level Security ensures users can only query their own sessions. No cross-user data leakage.
5. **User controls what's shared** — Session data is private by default. Only curated highlights appear in the social feed, and only if the user explicitly opts in per-highlight or globally.
6. **Data retention** — Raw session data can be auto-deleted after processing (configurable). Only generated content (journal, highlights) is retained long-term.
7. **Self-host option** — Users who don't want any data in the cloud run Docker locally. Full pipeline, zero data leaves their machine.
8. **Account deletion** — Hard delete of all user data (sessions, briefs, content items) on account deletion. No soft-delete retention.

### CLI Distribution

```bash
# Install via npm (global)
npm install -g @distill/cli

# Or via Homebrew
brew install distill-cli

# Setup
distill login                    # Opens browser → Supabase auth → stores token
distill sync --watch             # Background daemon, watches ~/.claude/
distill sync --once              # One-shot sync (for cron)
distill sync --self-host http://localhost:6107  # Point to local Docker
```

## What Stays vs What Changes

### Stays (personal CLI)
- Python pipeline continues working for your personal use
- `.distill.toml` config, JSON file storage, `claude -p` LLM calls
- All existing CLI commands (`distill run`, `distill intake`, etc.)

### New (product)
- TypeScript pipeline (port of Python logic, not a wrapper)
- Supabase Postgres replaces JSON files
- AI SDK replaces `claude -p` subprocess
- Hono API gets auth middleware + per-user scoping
- React Native app alongside web dashboard
- Social feed + follow system

### Shared
- Zod schemas (already exist in `web/shared/schemas.ts`)
- Core algorithms: highlight extraction, connection matching, topic trending
- RSS feed list (default_feeds table, seeded from existing `default_feeds.txt`)

## MVP Scope (Phase 1)

Build the minimum to put in someone's hands:

1. **Supabase project** — auth + Postgres + RLS policies
2. **Auth flow** — Google social login in web + mobile
3. **Share URL** — authenticated endpoint + mobile share sheet
4. **Pipeline (simplified)** — RSS defaults + shared URLs → highlights via LLM
5. **Daily View API** — endpoints serving briefs from Postgres
6. **Daily View UI** — highlights + drafts (web first, then mobile)
7. **Social feed** — see what others highlighted
8. **Expo app** — basic shell with Daily View + Feed + Share tabs

Not in MVP: voice learning, discovery engine, engagement tracking, connection engine, inline editing, push notifications.

## Success Criteria

- A friend can sign up, share a URL, and see highlights the next morning
- Social feed shows activity from the community
- Daily View loads in < 2 seconds on mobile
- Pipeline runs reliably for 50 users without manual intervention
- LLM costs stay under $15/day at community scale
