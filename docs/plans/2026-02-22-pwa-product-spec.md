# Distill PWA Product Specification

**Author**: Product Manager
**Date**: 2026-02-22
**Status**: Draft

---

## Executive Summary

Distill is a personal content pipeline for a solo developer. The web dashboard (Bun + Hono + React) currently runs at `localhost:6107` and is designed for desktop use. The user wants to review and publish content from their phone during commutes and breaks, with push notifications when the pipeline produces new content.

This spec defines what the PWA should do, prioritizes features, and designs the mobile review workflow.

---

## 1. User Stories

### Core Review Workflow
- **US-1**: As a user, I want to install Distill on my phone's home screen so I can open it with one tap like a native app.
- **US-2**: As a user, I want to receive a push notification when my pipeline finishes so I know there is content to review.
- **US-3**: As a user, I want to see a count of items awaiting review on the Dashboard so I can quickly assess my queue.
- **US-4**: As a user, I want to review draft content on my phone and approve it for publishing with a single tap.
- **US-5**: As a user, I want to reject or skip content that needs more work, so I only publish things I am happy with.

### Quick Publishing
- **US-6**: As a user, I want to publish approved content to specific platforms (Ghost, X, LinkedIn, Slack) from my phone.
- **US-7**: As a user, I want to see which platforms each piece of content has already been published to, so I do not double-post.
- **US-8**: As a user, I want to batch-approve multiple items and publish them all at once.

### Dashboard & Monitoring
- **US-9**: As a user, I want to view my daily dashboard stats (journal count, blog count, pending publish) on my phone.
- **US-10**: As a user, I want to read my journal entries on my phone to review what happened during the day.
- **US-11**: As a user, I want to see active threads and project activity so I know what is progressing.

### Content Management
- **US-12**: As a user, I want to view the Content Studio list on my phone and see each item's status (draft, review, ready, published).
- **US-13**: As a user, I want to read the full rendered markdown of any studio item on my phone.
- **US-14**: As a user, I want to view platform-adapted previews (Ghost newsletter, X thread, LinkedIn post) on my phone.

### Pipeline Control
- **US-15**: As a user, I want to trigger a pipeline run from my phone and get notified when it completes.
- **US-16**: As a user, I want to see whether a pipeline is currently running or has recently failed.

### Notifications
- **US-17**: As a user, I want a daily reminder if I have unpublished drafts older than 24 hours.
- **US-18**: As a user, I want to control which notifications I receive (pipeline, reminders, confirmations).
- **US-19**: As a user, I want notification taps to deep-link me directly to the relevant page (Studio item, Publish queue).

### Seeds & Notes
- **US-20**: As a user, I want to quickly add a seed idea from my phone (a thought I want to turn into content later).
- **US-21**: As a user, I want to add an editorial note from my phone to steer the next blog generation.

---

## 2. Feature Prioritization (MoSCoW)

### Must Have (MVP) -- make it installable and usable on mobile

| Feature | User Stories | Rationale |
|---------|-------------|-----------|
| Web app manifest + service worker (installable PWA) | US-1 | Without this, it is just a website. Installability is the table stakes. |
| Responsive mobile layout (bottom tab nav, stacked panels) | US-1, US-9 | Current sidebar layout does not work on mobile. Need bottom nav + full-width pages. |
| Mobile Dashboard | US-9, US-3 | First screen the user sees. Stat cards already use `grid-cols-2` but need review. |
| Mobile Studio list (review queue) | US-12 | Core triage screen: see all items and their statuses. |
| Mobile Studio detail (read-only view + status actions) | US-4, US-5, US-13 | Review content and change status (draft -> review -> ready). The right-panel agent chat collapses to full-screen or is hidden on mobile. |
| Mobile Publish page | US-6, US-7 | Publish to platforms from phone. Already has the API. |
| Touch-friendly buttons and tap targets (min 44px) | All | Basic mobile usability. |
| Viewport meta tag and safe-area-inset handling | All | Prevent iOS zoom, handle notch. |

### Should Have (v1.1) -- make it genuinely useful daily

| Feature | User Stories | Rationale |
|---------|-------------|-----------|
| Push notifications (pipeline complete) | US-2, US-19 | The primary reason for the PWA. Without this, the user still has to manually check. Requires a service worker push subscription + server-side web-push. |
| Push notifications (review reminder) | US-17, US-18 | Daily 9am reminder: "You have N unpublished drafts." Nudges the user to clear the queue. |
| Notification preferences page | US-18 | Toggle pipeline, reminder, and confirmation notifications. Quiet hours setting. |
| Deep links from notifications | US-19 | Tap notification -> open specific Studio item or Publish queue. |
| Quick-add seed idea | US-20 | Text input on Dashboard or a floating action button. Hits `POST /api/seeds`. |
| Quick-add editorial note | US-21 | Similar to seeds. Quick capture for blog steering. |
| Offline dashboard (cached stats) | US-9 | Service worker caches last dashboard response so the app opens instantly even without network. |
| Pipeline trigger + status from mobile | US-15, US-16 | The RunPipelineButton already exists. Just needs to work on mobile layout. |

### Could Have (v1.2) -- nice-to-have extras

| Feature | User Stories | Rationale |
|---------|-------------|-----------|
| Agent chat on mobile | -- | The AI rewriting chat is powerful but complex on small screens. Full-screen chat overlay. |
| Batch operations (select multiple, publish all) | US-8 | Multi-select with checkboxes + "Publish selected" button. |
| Platform preview on mobile (X thread, LinkedIn post) | US-14 | Already implemented in StudioDetail but needs mobile layout. |
| Swipe gestures for triage (swipe right = approve, left = skip) | US-4, US-5 | Faster triage but requires gesture library. |
| Offline reading of journal entries | US-10 | Cache journal markdown in service worker for commute reading. |
| Calendar/content ideas on mobile | -- | ContentCalendar already exists. Just needs responsive layout. |
| Image generation on mobile | -- | The image generation form exists but may be awkward on mobile. |
| Pull-to-refresh | All | Native-feeling refresh on all list pages. |

### Won't Have (keep desktop-only)

| Feature | Rationale |
|---------|-----------|
| Settings: Source configuration (RSS, Substack, browser history) | Complex multi-section forms with textareas. Done once, not on-the-go. |
| Settings: Publishing configuration (Ghost URL, API keys) | Sensitive credentials should not be entered on mobile. One-time setup. |
| Settings: Pipeline configuration (model, word counts) | Rarely changed, complex form. |
| Full rich-text editing of source content | Mobile editing of long-form markdown is a poor experience. Focus on approve/reject. |
| Agent chat as primary workflow | The agent chat is best experienced on desktop with a wide panel. Mobile should be for quick actions. |
| Projects detail pages | Deep drill-down per project is a desktop research activity. |

---

## 3. Mobile Review Workflow

### 3.1 Entry Points

The user opens the PWA. They land on the **Dashboard** which shows:

```
+-----------------------------------+
|  Dashboard                        |
|                                   |
|  [5 to review]  [3 ready]        |
|  [12 journals]  [4 blog posts]   |
|                                   |
|  --- Recent Activity ---          |
|  Journal: 2026-02-22  (3 sess)   |
|  Journal: 2026-02-21  (5 sess)   |
|                                   |
|  [Run Pipeline]                   |
+-----------------------------------+
| Dashboard | Studio | Publish | .. |
+-----------------------------------+
```

The "5 to review" badge taps through to the **Studio** list, filtered to `status = draft | review`.

### 3.2 Studio List (Triage Screen)

```
+-----------------------------------+
|  Content Studio                   |
|  [All] [Draft] [Review] [Ready]  |
|                                   |
|  Agent Fatigue...      [draft]   |
|  Feb 22 - weekly - 2 platforms   |
|                                   |
|  MCP Patterns...       [review]  |
|  Feb 21 - thematic - 0 platforms |
|                                   |
|  Pipeline Orchestr...  [ready]   |
|  Feb 20 - weekly - 3 platforms   |
+-----------------------------------+
| Dashboard | Studio | Publish | .. |
+-----------------------------------+
```

- Status filter tabs at the top (All / Draft / Review / Ready) for quick triage.
- Each item shows: title, date, content type, platform count, status badge.
- Tap an item to open the detail view.

### 3.3 Studio Detail (Review Screen)

On mobile, the two-panel layout collapses to a single full-width view:

```
+-----------------------------------+
| < Back          [Approve] [Skip] |
|                                   |
| Agent Fatigue in Large Teams      |
| weekly - draft - Feb 22           |
|                                   |
| [Ghost] [X] [LinkedIn] [Slack]   |
|                                   |
| --- Content ---                   |
| (rendered markdown, scrollable)   |
|                                   |
|                                   |
|                                   |
|                                   |
+-----------------------------------+
| [Approve]  [Edit on Desktop]     |
+-----------------------------------+
```

**Quick actions** (sticky bottom bar):
- **Approve** -> moves status from `draft` -> `review`, or `review` -> `ready`
- **Skip** -> leaves status unchanged, returns to list
- **Delete** -> with confirmation modal

**Platform chips** at the top show adapted content. Tapping a chip opens a full-screen preview of that platform's content (X thread view, LinkedIn post view, etc.).

The **Agent Chat** is hidden by default on mobile. A small "Chat with AI" button at the bottom opens a full-screen chat overlay. This is a Could Have for v1.2.

### 3.4 Publish Flow

From the Publish tab (or from a Studio item marked "ready"):

```
+-----------------------------------+
| Publish Queue                     |
|                                   |
| Ready to Publish (3)              |
|                                   |
| [ ] Agent Fatigue                 |
|     [Ghost] [X] [LinkedIn]       |
|                                   |
| [ ] MCP Patterns                  |
|     [Ghost] [X]                  |
|                                   |
| [Publish Selected]                |
+-----------------------------------+
```

- Each item shows platform chips. Published platforms show a green checkmark.
- Tap a platform chip to publish just that one. Tap the item checkbox for batch.
- **Default platform selection**: all enabled platforms for that content type.
- Confirmation modal before publishing: "Publish 'Agent Fatigue' to X and LinkedIn?"

### 3.5 Quick Capture

A floating action button (FAB) on the Dashboard provides quick-add options:
- **Add Seed Idea**: opens a single text input + submit button
- **Add Editorial Note**: opens text input + optional target field + submit button

These hit existing API endpoints (`POST /api/seeds`, `POST /api/notes`).

---

## 4. Notification Strategy

### 4.1 Notification Types

| Type | Trigger | Message | Action | Priority |
|------|---------|---------|--------|----------|
| Pipeline Complete | Pipeline process exits with code 0 | "Pipeline finished -- 3 new items to review" | Open Studio list | High |
| Pipeline Failed | Pipeline process exits with non-zero code | "Pipeline failed -- check logs" | Open Dashboard (pipeline section) | High |
| Review Reminder | Scheduled daily at 9:00 AM local time | "You have 5 unpublished drafts" | Open Studio list filtered to draft/review | Medium |
| Publish Confirmation | After successful Postiz API call | "Published 'Agent Fatigue' to X and LinkedIn" | Open Studio item detail | Low |

### 4.2 Implementation Approach

- **Web Push API** via service worker (`PushManager.subscribe()`)
- Server stores the push subscription endpoint (JSON file alongside content store)
- On pipeline completion, server sends push via `web-push` npm package
- Review reminder requires a lightweight scheduled job (cron or `setInterval` on the server)
- Publish confirmations fire immediately after successful API call

### 4.3 Frequency & Batching

- **Pipeline Complete**: sent once per pipeline run. No batching needed (pipeline runs are infrequent, typically 1-2 per day).
- **Review Reminder**: sent once daily at 9:00 AM if unpublished drafts exist. Suppressed if queue is empty.
- **Publish Confirmation**: batched if multiple items are published within 30 seconds. "Published 3 items to X, LinkedIn" instead of 3 separate notifications.
- **Maximum**: no more than 5 notifications per day total to avoid fatigue.

### 4.4 User Controls (Settings Page)

New "Notifications" tab in Settings:
- Toggle: Pipeline notifications (on/off, default: on)
- Toggle: Review reminders (on/off, default: on)
- Toggle: Publish confirmations (on/off, default: off -- most users just want to know about new content)
- Quiet hours: start time + end time (default: 10pm - 8am)
- "Test notification" button to verify setup

### 4.5 Deep Linking

Each notification carries a URL path in its `data` payload:
- Pipeline complete -> `/studio?filter=draft`
- Review reminder -> `/studio?filter=draft,review`
- Publish confirmation -> `/studio/{slug}`

The service worker's `notificationclick` handler calls `clients.openWindow(url)` or focuses the existing window.

---

## 5. Success Metrics

### Primary Metrics (measure PWA value)

| Metric | Baseline | Target (30 days) | How to Measure |
|--------|----------|-------------------|----------------|
| Time from pipeline completion to first review | Unknown (currently manual check) | < 15 minutes | Timestamp delta: pipeline `completedAt` vs first status change in ContentStore |
| Average draft-to-publish turnaround time | Unknown | < 24 hours | Timestamp delta: ContentStore `created_at` vs first `published_at` across platforms |
| Notification tap-through rate | N/A | > 40% | Service worker analytics: notification shown vs notificationclick events |
| Daily active usage (app opens per day) | 0 (no PWA exists) | >= 1 open per day | Service worker fetch events for `/api/dashboard` |

### Secondary Metrics (track engagement patterns)

| Metric | How to Measure |
|--------|----------------|
| % of content reviewed on mobile vs desktop | User-Agent header on `/api/studio/items/{slug}` requests |
| Mobile publish rate | Platform publish API calls with mobile User-Agent |
| Seeds added from mobile | `POST /api/seeds` calls with mobile User-Agent |
| Notification opt-in rate | Push subscription count vs total app installs |
| Offline cache hit rate | Service worker cache-hit vs network-fetch ratio |

### Instrumentation Notes

- All metrics can be collected server-side (Hono middleware logging request metadata).
- No third-party analytics needed -- this is a single-user app.
- A simple JSON log file (`/api/analytics` endpoint writing to `.distill-analytics.json`) is sufficient.
- Dashboard page can display these metrics in a "PWA Health" section on the Settings page.

---

## 6. Risks & Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Mobile editing is clunky | Users try to edit on mobile, get frustrated, stop using the app | Medium | Focus the mobile experience on approve/reject/publish. Hide complex editing behind an explicit "Edit on Desktop" label. Do not surface the agent chat by default on mobile. |
| Too many notifications | User disables all notifications, losing the primary PWA benefit | Medium | Conservative defaults (confirmations off), quiet hours enabled by default, hard cap of 5 notifications/day, batch related events. |
| Push notifications require HTTPS | PWA cannot be installed or receive push on plain HTTP localhost | High | Require the user to access via HTTPS. Options: (a) Caddy reverse proxy with self-signed cert, (b) Tailscale/Cloudflare Tunnel for remote access, (c) `--https` flag on `distill serve` using `mkcert`. Document this clearly in setup. |
| Service worker caching causes stale data | User sees outdated dashboard or studio list | Medium | Use stale-while-revalidate strategy for API calls. Show a "refresh" indicator when new data is available. Version the service worker and force update on new deploys. |
| Network required for publishing | User tries to publish while offline | Low | Disable publish buttons when offline. Show clear "No network" indicator. Queue publish actions for retry when online (Could Have). |
| Bottom nav conflicts with iOS gesture bar | Navigation taps register as system gestures | Low | Use `env(safe-area-inset-bottom)` CSS padding. Test on iOS Safari specifically. |
| Large markdown content slow on mobile | Long blog posts cause janky scrolling | Low | Virtualize long content or lazy-render sections. Most blog posts are 600-1200 words which is fine. |
| Single-user app does not need auth, but PWA is on network | Someone on the same network could access the dashboard | Medium | Add a simple bearer token or PIN lock option for the PWA. Not a blocker for MVP but should be addressed in v1.1. |

---

## 7. Out-of-Scope Decisions

These items were considered and explicitly excluded:

1. **Native app (React Native, Capacitor)**: Unnecessary for a single-user tool. PWA provides installability, push notifications, and offline support without an app store.
2. **Background sync for offline publishing**: Complex and low-value. The user can wait for network. Could be revisited in v1.2.
3. **Camera/media integration**: No use case for Distill (it is a text-based content pipeline).
4. **Multi-user support**: Distill is explicitly a solo developer tool. No auth, no collaboration.
5. **App store distribution (TWA)**: Overkill for a self-hosted personal tool.

---

## 8. Technical Dependencies

For the engineering team to implement this spec, the following are needed:

1. **Web app manifest** (`manifest.json`) with icons, theme color, display: standalone
2. **Service worker** for: installability, push notifications, basic offline caching
3. **`web-push` npm package** on the server for sending push notifications
4. **Responsive CSS overhaul**: bottom navigation, stacked layouts, touch-friendly targets
5. **HTTPS strategy** for push notification support (Caddy, mkcert, or tunnel)
6. **Push subscription storage** (JSON file or extend ContentStore)
7. **Notification scheduling** (lightweight cron for daily review reminders)

---

## 9. Implementation Phases

### Phase 1: Installable + Mobile Layout (MVP)
- Add web manifest + service worker shell
- Responsive layout: bottom nav on mobile, sidebar on desktop
- Mobile-optimized Dashboard, Studio list, Studio detail, Publish
- Touch-friendly tap targets and spacing

### Phase 2: Push Notifications (v1.1)
- Service worker push handler
- Server-side web-push integration
- Pipeline completion notification
- Daily review reminder (scheduled)
- Notification preferences in Settings
- Deep linking from notifications

### Phase 3: Enhanced Mobile Experience (v1.2)
- Quick-add FAB (seeds + editorial notes)
- Agent chat overlay on mobile
- Batch publish operations
- Offline dashboard caching
- Pull-to-refresh
- Swipe gestures for triage
