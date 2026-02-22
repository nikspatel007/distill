# Daily Briefing Home Page + Human Review Gate

## Problem

The Distill PWA has too many pages with no clear workflow. Two launchd plists run the same pipeline to different directories. Publishing happens automatically with no human review. On a phone, there's no way to see "what happened today" and act on it.

## Design

### Single Flow

```
launchd (7 AM)
  → distill run --dir ~ --output ./insights (no --publish)
  → generates drafts to insights/

Phone (PWA)
  → opens Daily Briefing (home page)
  → reviews journal, intake, blog/social drafts
  → approves/edits → publishes to Ghost, Postiz
```

One launchd plist. One output directory. One review surface. Nothing publishes without human approval.

### Home Page (`/` route)

Replaces the current Dashboard. Shows a scrollable card stack for the selected date (defaults to latest available).

```
┌─────────────────────────┐
│ What you built           │  journal brief (3-5 bullets)
│ • Shipped TLS + PWA     │  tap to expand full narrative
│ • Fixed agent routing    │
│ [Read more]              │
├─────────────────────────┤
│ What you read            │  intake highlights (3-5 items)
│ 12 items · 3 tagged      │  tap to expand full digest
├─────────────────────────┤
│ Ready to publish         │  pending drafts
│ ▸ Weekly W08 → Ghost     │  [Approve] [Edit in Studio]
│ ▸ Twitter thread         │  [Approve] [Edit]
│ ▸ LinkedIn post          │  [Approve] [Edit]
├─────────────────────────┤
│ Seeds                    │  idea fragments
│ "Agent fatigue patterns" │  [Develop] [Dismiss]
└─────────────────────────┘
```

Date picker at top to go back. Mobile: full-width cards, bottom tab bar (Journal, Blog, Studio, Reading). Desktop: same cards in main content area with existing sidebar.

### Pipeline Changes

**Journal frontmatter** — extend the LLM prompt to also produce `brief:` bullets:

```yaml
---
date: 2026-02-22
type: journal
brief:
  - "Shipped TLS + PWA for Distill mobile access"
  - "Fixed dual HTTP/HTTPS server binding"
  - "Redesigned mobile nav to 4 core tabs"
---
# Dev Journal: February 22, 2026
...full narrative...
```

**Intake frontmatter** — same pattern, add `highlights:`:

```yaml
---
date: 2026-02-22
type: intake-digest
highlights:
  - "John D. Cook on Fibonacci certificates and verification artifacts"
  - "Multi-agent roster-build workflow ran end-to-end"
  - "Chairman agent flagged draft as insufficiently unique"
---
# The Agent Team That Grew Its Own CMO
...full digest...
```

No new files. No extra LLM calls. Just extend existing prompts.

**Remove auto-publish** — the `--publish` flag gets removed from the launchd plist. Publishing moves entirely to the web server's approve flow.

### API

**`GET /api/home/:date`** — aggregates everything for the daily briefing.

Response follows canonical Zod schemas in `shared/schemas.ts`:

```typescript
const JournalBriefSchema = z.object({
  brief: z.array(z.string()),
  hasFullEntry: z.boolean(),
});

const IntakeBriefSchema = z.object({
  highlights: z.array(z.string()),
  itemCount: z.number(),
  hasFullDigest: z.boolean(),
});

const PublishQueueItemSchema = z.object({
  slug: z.string(),
  title: z.string(),
  type: z.enum(["blog", "twitter", "linkedin", "reddit"]),
  status: z.enum(["draft", "approved", "published"]),
});

const SeedItemSchema = z.object({
  id: z.string(),
  text: z.string(),
  createdAt: z.string(),
});

const DailyBriefingSchema = z.object({
  date: z.string(),
  journal: JournalBriefSchema,
  intake: IntakeBriefSchema,
  publishQueue: z.array(PublishQueueItemSchema),
  seeds: z.array(SeedItemSchema),
});
```

**`POST /api/publish/:slug/approve`** — marks a draft as approved, triggers publish to the appropriate platform (Ghost API for blog, Postiz API for social).

### Launchd Cleanup

**Kill duplicate:** unload and remove `com.distill.daily-intake.plist`.

**Update `com.distill.daily.plist`:**
- Remove `--publish` flags (no auto-publish)
- Output to `insights/` only
- Keep 7 AM schedule

**Obsidian:** symlink `insights/` into Obsidian Vault if still wanted.

**Web server:** already runs manually. No launchd plist needed for it.

### Mobile Nav

Bottom tab bar with 4 tabs: Journal, Blog, Studio, Reading. Home page (Daily Briefing) is the default — navigating to `/` shows the briefing, not a tab.

## Files to Change

| File | Action |
|------|--------|
| `web/shared/schemas.ts` | Add DailyBriefing schemas |
| `web/server/routes/home.ts` | Create — `/api/home/:date` endpoint |
| `web/server/index.ts` | Mount home route |
| `web/src/routes/index.tsx` | Rewrite — Daily Briefing card stack |
| `web/src/components/layout/Sidebar.tsx` | Already done — 4 mobile tabs |
| `src/journal/prompts.py` | Extend prompt to produce `brief:` in frontmatter |
| `src/intake/prompts.py` | Extend prompt to produce `highlights:` in frontmatter |
| `src/core.py` | Remove auto-publish from `run` command flow (gate it) |
| `com.distill.daily.plist` | Update — remove `--publish`, single output dir |
| `com.distill.daily-intake.plist` | Delete |

## Not Changing

- Python parsers (work fine, 500+ tests)
- Existing journal/intake/blog file formats (additive frontmatter only)
- Desktop sidebar navigation
- Studio functionality
- Existing API endpoints (journal, blog, reading, etc.)
