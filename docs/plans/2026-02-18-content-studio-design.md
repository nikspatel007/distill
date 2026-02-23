# Content Studio Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current Publish page with a Content Studio that lets the user review pipeline output, collaborate with Claude to refine per-platform content, and publish to Postiz — all in one page.

**Architecture:** Content list → Studio editor with inline Claude chat → per-platform previews → one-click publish to Postiz. Claude chat calls `claude -p` subprocess with blog content + platform prompt + user direction. No TroopX dependency.

**Tech Stack:** React + TanStack Router (frontend), Hono API routes (server), Claude subprocess (LLM), Postiz API (publishing)

---

## UX Flow

1. User opens `/studio` (replaces `/publish`)
2. Sees today's content list: blog posts, daily social, reading digests
3. Clicks a content item → enters studio editor view
4. Studio has three zones:
   - **Editor** (center): Full content with inline AI annotations
   - **Claude chat** (right, collapsible): Conversational refinement
   - **Platform bar** (bottom): Per-platform previews, toggle, schedule, publish
5. User works with Claude to refine content per platform
6. User approves → publishes to Ghost + Postiz

## Architecture

### Data Flow

```
Pipeline output (local files)
    ↓
GET /api/studio/items → reads blog state, journal, intake
    ↓
Content Studio list (React)
    ↓
GET /api/studio/items/:slug → full content + metadata
    ↓
Studio editor (React)
    ↓
POST /api/studio/chat → claude -p subprocess
    ├── input: content + platform prompt + user message + conversation history
    └── output: adapted content or suggestions
    ↓
POST /api/studio/publish/:slug → Postiz API + Ghost API
    ├── uploads image to Ghost CDN first
    ├── creates Ghost post
    └── creates Postiz posts with correct integration IDs
```

### Server Routes (Hono)

```
GET  /api/studio/items              → list today's publishable content
GET  /api/studio/items/:slug        → full content + metadata for one item
POST /api/studio/chat               → Claude conversation (subprocess)
POST /api/studio/publish/:slug      → publish to Ghost + Postiz
GET  /api/studio/platforms           → list connected Postiz integrations
```

### Claude Chat Implementation

The chat endpoint wraps `claude -p` subprocess:

```typescript
// POST /api/studio/chat
{
  content: string,        // the blog post text
  platform: string,       // "linkedin" | "x" | "ghost" | "slack"
  message: string,        // user's direction
  history: ChatMessage[], // conversation so far
}

// Server builds prompt:
// 1. System: platform-specific prompt from blog/prompts.py
// 2. Context: the full blog post
// 3. History: previous exchanges
// 4. User message: latest direction
// Calls: claude -p "..."
// Returns: { response: string, adapted_content: string }
```

### Review State

`.distill-review-queue.json` tracks content status:

```json
{
  "items": [
    {
      "slug": "agents-outnumber-decisions",
      "type": "thematic",
      "status": "draft",           // draft | ready | published
      "generated_at": "2026-02-18T07:40:00",
      "platforms": {
        "ghost": { "enabled": true, "content": null, "published": false },
        "linkedin": { "enabled": true, "content": "adapted...", "published": false },
        "x": { "enabled": true, "content": "thread...", "published": false },
        "slack": { "enabled": true, "content": "summary...", "published": false }
      },
      "chat_history": []
    }
  ]
}
```

### Frontend Components

```
src/routes/studio.tsx          → content list (entry point)
src/routes/studio.$slug.tsx    → studio editor + chat + platform bar
src/components/studio/
  Editor.tsx                   → markdown content display (read + edit)
  AgentChat.tsx                → Claude conversation panel
  PlatformBar.tsx              → platform tabs + preview + publish
  Annotation.tsx               → inline AI suggestion block
```

### Publishing Flow

When user clicks "Publish":

1. **Ghost**: Upload feature image via Ghost Admin API → get CDN URL. Create/update Ghost post with markdown + feature image URL.
2. **Postiz**: For each enabled social platform, create a Postiz post with:
   - The adapted content (from Claude chat refinement)
   - The correct integration ID (looked up from connected integrations)
   - The feature image URL (from Ghost CDN)
   - Schedule time (from platform bar picker)
3. **State**: Mark item as published in review queue JSON.

### Fixing Current Postiz Issues

As part of this work, fix:
- **Integration linking**: Posts must include `integration.id` from connected integrations
- **Image handling**: Upload to Ghost first, pass CDN URL to Postiz `image` field
- **Dedup**: Check review queue before creating duplicate posts
- **Scheduling**: Verify timezone math (America/Chicago → UTC conversion)

## Scope

### In scope
- Content list page
- Studio editor with editable markdown
- Claude chat panel (subprocess-based)
- Platform bar with per-platform preview, toggle, schedule
- Publish to Ghost + Postiz with correct integrations
- Review queue state tracking
- Image upload to Ghost CDN

### Out of scope (future)
- TroopX workflow integration
- Inline annotations from AI analysis (start with chat only)
- Version history / undo
- Calendar view
- Auto-scheduling optimization
