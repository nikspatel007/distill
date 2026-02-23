# Distill PWA Mobile Design Proposal

**Date:** 2026-02-22
**Author:** UI Designer
**Status:** Draft

---

## 1. Current State Analysis

### Layout Structure
- Root: `flex h-screen` with `<Sidebar />` (fixed `w-56` / 224px) + `<main>` (flex-1, overflow-y-auto)
- No responsive breakpoints anywhere in the current layout
- All pages use `mx-auto max-w-5xl p-6` as their content wrapper
- Studio detail is the most complex: full `h-screen` flex column with a 50/50 split (left content, right chat)
- Tailwind v4 with `@tailwindcss/vite` plugin, no `tailwind.config.ts` file (theme in CSS `@theme` block)
- Custom theme tokens: `--color-primary: #6366f1`, `--color-primary-light: #818cf8`, `--color-surface`, `--color-surface-dark`

### Navigation (8 items)
1. Dashboard (`/`)
2. Projects (`/projects`)
3. Journal (`/journal`)
4. Blog (`/blog`)
5. Reading (`/reading`)
6. Calendar (`/calendar`)
7. Studio (`/studio`)
8. Settings (`/settings`)

### Key Problem Areas for Mobile
- Sidebar consumes 224px -- leaves almost nothing on a 375px screen
- Studio detail's 50/50 split is completely unusable below 768px
- Publish queue table layout breaks on narrow screens
- Chat input in AgentChat uses textarea + button side-by-side -- needs safe area handling
- No viewport meta for PWA standalone, no manifest, no service worker

---

## 2. Mobile Navigation Design

### Approach: Bottom Tab Bar + Overflow Menu

**Primary tabs (always visible in bottom bar, 5 items max for thumb reach):**

| Position | Item | Icon | Route |
|----------|------|------|-------|
| 1 | Dashboard | `LayoutDashboard` | `/` |
| 2 | Studio | `Wand2` | `/studio` |
| 3 | Publish | `Send` (new) | `/publish` |
| 4 | Journal | `BookOpen` | `/journal` |
| 5 | More | `Menu` | sheet/drawer |

**Secondary items (inside "More" drawer):**
- Projects (`/projects`)
- Blog (`/blog`)
- Reading (`/reading`)
- Calendar (`/calendar`)
- Settings (`/settings`)

**Rationale:**
- Studio and Publish are the primary action screens (create + ship)
- Dashboard is the home/overview
- Journal is the most-used read screen
- "More" drawer slides up as a bottom sheet (not a full sidebar) to keep spatial context

### Component Structure

```
<MobileBottomBar />        -- visible only below md (768px)
  <TabItem />              -- 5 tab buttons, active state = indigo-600 icon + label
  <MoreSheet />            -- bottom sheet overlay for secondary nav

<Sidebar />                -- visible only at md and above (unchanged)
```

### Breakpoint Behavior

| Breakpoint | Navigation | Content Layout |
|------------|-----------|----------------|
| < 640px (mobile) | Bottom tab bar | Single column, full width |
| 640-767px (sm, large phone / small tablet) | Bottom tab bar | Single column, wider cards |
| 768px+ (md, tablet+) | Fixed sidebar 224px | Current desktop layout |

### Implementation Detail

Root layout changes from:
```tsx
<div className="flex h-screen">
  <Sidebar />
  <main className="flex-1 overflow-y-auto">...</main>
</div>
```

To:
```tsx
<div className="flex h-screen flex-col md:flex-row">
  <Sidebar className="hidden md:flex" />
  <main className="flex-1 overflow-y-auto pb-16 md:pb-0">...</main>
  <MobileBottomBar className="fixed bottom-0 inset-x-0 md:hidden" />
</div>
```

The `pb-16` on main prevents content from being hidden behind the bottom bar.

---

## 3. Key Mobile Screens

### 3.1 Dashboard (Mobile)

**Current:** `grid-cols-2 sm:grid-cols-5` stat cards, then sections stacked.

**Mobile treatment:**
- Stat cards: `grid-cols-2` stays (works well on mobile, 2 per row)
- Fifth stat card wraps to second row alone, which is acceptable
- Sections (Active Projects, Recent Journals, Active Threads) stack naturally
- Project pills become horizontally scrollable: `flex overflow-x-auto gap-2 -mx-6 px-6` (edge-to-edge scroll with padding trick)
- Journal entries become full-width cards
- "Run Pipeline" button becomes a floating action button (FAB) on mobile: fixed bottom-20 right-4 (above tab bar), circular, indigo-600

**Breakpoint changes:**
- `sm:grid-cols-5` stays -- on sm screens (640px+) all 5 fit
- Below sm: 2 columns is fine
- No other structural changes needed -- the dashboard is already fairly mobile-friendly

### 3.2 Studio List (Mobile)

**Current:** `max-w-5xl p-6`, list of items as bordered cards with Link wrappers.

**Mobile treatment:**
- Remove horizontal padding on mobile: `p-4 sm:p-6`
- Cards become full-bleed with thinner borders: `mx-0 rounded-none border-x-0 sm:mx-0 sm:rounded-lg sm:border`
- Each card shows: title (bold, truncated to 1 line), type badge, status badge
- Metadata line below: date + platform counts
- "New Post" button moves from top-right to a FAB (plus icon) on mobile, stays inline on md+
- Journal picker modal: already has `mx-4`, works on mobile

**Key classes:**
```
Card: "border-b border-zinc-200 px-4 py-3.5 sm:rounded-lg sm:border sm:p-4"
Title: "text-sm font-medium truncate"
```

### 3.3 Publish Queue (Mobile)

**Current:** Two views (CardView without Postiz, PostizQueueView table with Postiz).

**Mobile treatment for CardView (no Postiz):**
- Cards are already single-column, just need tighter padding
- Platform badges wrap naturally with `flex-wrap`

**Mobile treatment for PostizQueueView (table):**
- Tables do not work on mobile. Replace with card list below md:
  - Each card: title, type badge, platform badge, "Draft" button
  - Use `md:table` / `md:table-row` to show table on desktop, cards on mobile
  - Or simpler: render a card list component on mobile, table on md+

```tsx
{/* Mobile card list */}
<div className="space-y-2 md:hidden">
  {unpublished.map(item => (
    <div className="border rounded-lg p-3">
      <div className="font-medium text-sm">{item.title}</div>
      <div className="flex items-center justify-between mt-2">
        <span className="badge">{item.platform}</span>
        <button className="btn-sm">Draft</button>
      </div>
    </div>
  ))}
</div>

{/* Desktop table */}
<div className="hidden md:block overflow-x-auto">
  <table>...</table>
</div>
```

### 3.4 Settings (Mobile)

**Current:** Tabs as horizontal text buttons + sectioned forms.

**Mobile treatment:**
- Tab bar becomes horizontally scrollable: `flex overflow-x-auto -mx-6 px-6 gap-0`
- Form sections stack naturally (already single-column in most places)
- `sm:grid-cols-3` word count inputs already collapse to `grid-cols-1` on mobile
- Save buttons become sticky at bottom: `sticky bottom-16 bg-white/80 backdrop-blur py-3 md:static md:bg-transparent`

### 3.5 Journal Detail / Blog Detail / Reading Detail

These are content-reading screens. Mobile treatment is straightforward:
- Reduce padding: `p-4 sm:p-6`
- Markdown content has `max-w-none` already via prose classes
- Date and metadata badges wrap naturally

---

## 4. Studio Detail Mobile Layout (Critical Screen)

This is the hardest screen. Current structure:

```
<div className="flex h-screen flex-col">
  {/* Header: back arrow, title, badges, action buttons, panel toggle */}
  {/* Main area: flex min-h-0 flex-1 */}
    {/* Left (w-1/2 or w-full): hero image, image thumbnails, platform chips, platform preview, source markdown */}
    {/* Right (w-1/2, min-w-360): AgentChat */}
</div>
```

### Mobile Solution: Tab-Based Layout with Swipeable Panels

On mobile (< md), replace the side-by-side layout with a tab switcher at the top:

**Two tabs:**
1. **Content** -- source markdown + hero image + platform chips + platform preview
2. **Chat** -- full-height AgentChat

```
[< Back]  Post Title                    [Content | Chat]
```

**Header simplification on mobile:**
- Back arrow + title (truncated) on left
- Tab toggle (Content / Chat) on right (replacing panel toggle)
- Status badge moves below title as a second line
- Action buttons (Mark for Review, Approve, Delete) move into a bottom action bar or a "..." overflow menu

**Layout structure (mobile):**
```tsx
{/* Mobile: tab-based */}
<div className="flex h-screen flex-col md:hidden">
  {/* Compact header */}
  <div className="flex items-center justify-between border-b px-3 py-2">
    <div className="flex items-center gap-2 min-w-0">
      <Link to="/studio"><ArrowLeft /></Link>
      <span className="truncate text-sm font-bold">{title}</span>
    </div>
    <div className="flex gap-1">
      <TabButton active={tab === 'content'} onClick={() => setTab('content')}>Content</TabButton>
      <TabButton active={tab === 'chat'} onClick={() => setTab('chat')}>Chat</TabButton>
    </div>
  </div>

  {/* Badges + actions row */}
  <div className="flex items-center justify-between border-b px-3 py-1.5">
    <div className="flex gap-1.5">
      <TypeBadge /><StatusBadge />
    </div>
    <ActionMenu /> {/* three-dot overflow for status changes + delete */}
  </div>

  {/* Tab content */}
  {tab === 'content' ? (
    <div className="flex-1 overflow-y-auto">
      {/* Hero image, image bar, platform chips, preview, markdown -- same as left panel */}
    </div>
  ) : (
    <div className="flex-1 flex flex-col min-h-0">
      <AgentChat ... />
    </div>
  )}
</div>

{/* Desktop: side-by-side (unchanged) */}
<div className="hidden md:flex h-screen flex-col">
  {/* existing layout */}
</div>
```

### Platform Chips on Mobile

The platform chips (Ghost, X, LinkedIn, Slack) become horizontally scrollable:
```
<div className="flex overflow-x-auto gap-1.5 px-4 py-2 border-b">
```

### Image Generation Form on Mobile

The image generation form is already single-column. Just ensure:
- Input takes full width (already does)
- Mood select + Generate button wrap to second line if needed: `flex flex-wrap gap-2`

### Chat Tab Specifics

When the Chat tab is active on mobile:
- Chat messages take full width
- Chat input sticks to bottom with safe area padding: `pb-safe` (env(safe-area-inset-bottom))
- The keyboard pushes the input up naturally in standalone mode via `interactive-widget=resizes-content` in the manifest
- Textarea auto-grows (already implemented)

---

## 5. Touch Interactions

### Swipe Gestures

**Studio list -- swipe actions on content cards:**
- Swipe right: quick status change (draft -> review -> ready) -- green slide
- Swipe left: delete -- red slide with confirmation
- Implemented via CSS transforms + touch event handlers (no library needed for simple gestures)
- Desktop: these actions stay as explicit buttons

**Publish queue cards (mobile):**
- Swipe right: publish as draft to Postiz
- Visual: card slides to reveal green "Draft" action behind it

**Journal / Blog lists:**
- No swipe needed -- these are read-only navigation lists

### Pull to Refresh

- All list screens (Dashboard, Studio list, Publish, Journal, Blog, Reading) support pull-to-refresh
- Implemented via a `<PullToRefresh>` wrapper component that triggers `queryClient.invalidateQueries()`
- Visual: small indigo spinner pulls down from top
- Only enabled on mobile (< md)

### Long Press

- Studio list cards: long press opens a context menu (change status, delete, duplicate)
- Not used elsewhere -- keep interactions simple

### Chat Input

- Textarea with auto-grow (already implemented)
- Send button is 40x40 (h-10 w-10) -- adequate touch target (44px recommended, close enough with padding)
- Consider bumping to `h-11 w-11` (44px) on mobile
- Enter sends (already implemented), Shift+Enter for newline
- On mobile, the return key should show "Send" label via `enterkeyhint="send"` attribute

---

## 6. PWA Chrome & Manifest

### Web App Manifest (`/manifest.json`)

```json
{
  "name": "Distill",
  "short_name": "Distill",
  "description": "Knowledge cockpit — transform coding sessions into publishable content",
  "start_url": "/",
  "display": "standalone",
  "orientation": "any",
  "background_color": "#fafafa",
  "theme_color": "#6366f1",
  "icons": [
    { "src": "/icons/icon-192.png", "sizes": "192x192", "type": "image/png" },
    { "src": "/icons/icon-512.png", "sizes": "512x512", "type": "image/png" },
    { "src": "/icons/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable" }
  ]
}
```

### Status Bar & Theme Color

```html
<meta name="theme-color" content="#6366f1" media="(prefers-color-scheme: light)" />
<meta name="theme-color" content="#18181b" media="(prefers-color-scheme: dark)" />
<meta name="apple-mobile-web-app-capable" content="yes" />
<meta name="apple-mobile-web-app-status-bar-style" content="default" />
```

- Light mode: indigo-500 (`#6366f1`) status bar blending with the header
- Dark mode: zinc-900 (`#18181b`) status bar blending with the dark background

### Safe Area Insets (iPhone Notch / Dynamic Island)

Add to `index.html`:
```html
<meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
```

Add to `index.css`:
```css
@theme {
  --spacing-safe-top: env(safe-area-inset-top);
  --spacing-safe-bottom: env(safe-area-inset-bottom);
  --spacing-safe-left: env(safe-area-inset-left);
  --spacing-safe-right: env(safe-area-inset-right);
}
```

Apply safe area padding:
- Root layout top: `pt-safe` (for notch/dynamic island)
- Bottom tab bar: `pb-safe` (for home indicator on iPhone X+)
- Chat input: `pb-safe` when chat is the active tab
- Content with `pb-16` for bottom bar becomes `pb-[calc(4rem+env(safe-area-inset-bottom))]`

### Orientation

Allow both portrait and landscape. The layout works in both:
- Portrait: primary use case, single-column on mobile
- Landscape: on phones this gives more horizontal space, useful for Studio detail chat
- On tablets (768px+ in landscape): full desktop sidebar layout activates

### Standalone Mode Considerations

- No browser chrome (URL bar, back/forward) in standalone mode
- Back navigation via in-app back arrows (already present on detail screens)
- Add a subtle left-edge swipe-back gesture handler for iOS parity
- Splash screens via `apple-touch-startup-image` meta tags (generate from icon)

---

## 7. Notification UI

### In-App Notification Badge

**Location:** On the bottom tab bar's "More" tab, or on a dedicated bell icon in the header.

**Proposed approach:** Add a notification indicator to the Dashboard tab:
- Small red dot (absolute positioned) on the Dashboard icon when there are items needing attention
- "Items needing attention" = content in review status + unpublished items ready to go

```tsx
<div className="relative">
  <LayoutDashboard className="h-5 w-5" />
  {hasNotifications && (
    <span className="absolute -top-0.5 -right-0.5 h-2 w-2 rounded-full bg-red-500" />
  )}
</div>
```

### Push Notifications (Future)

When implemented:
- Service worker handles push events
- Notification types:
  - "New content ready for review" (studio item moved to review)
  - "Pipeline completed" (daily run finished)
  - "Publishing failed" (Postiz API error)
- Notification appearance: standard OS notification with Distill icon
- Action buttons on notification:
  - "Review" -> opens studio detail
  - "Dismiss" -> clears notification

### Notification Center (In-App)

A simple notification list accessible from a bell icon in the mobile header:
- Slide-down panel or dedicated route `/notifications`
- Each notification: icon + message + timestamp + "Go to" link
- Mark all read button
- Limit: last 50 notifications, persisted in localStorage

---

## 8. Responsive Breakpoint Summary

| Breakpoint | Width | Key Layout Changes |
|------------|-------|--------------------|
| Default (mobile) | 0-639px | Bottom tab bar, single column, compact padding (p-4), full-bleed cards, tab-based Studio detail, card-based publish queue |
| `sm` | 640-767px | Wider stat card grid (cols-3), slightly more breathing room, still bottom tab bar |
| `md` | 768px+ | **Switch to sidebar navigation**, two-column Studio detail, table-based publish queue, desktop padding (p-6) |
| `lg` | 1024px+ | Max-width containers feel more spacious, no structural changes |

---

## 9. Component Inventory (New/Modified)

### New Components

| Component | Location | Description |
|-----------|----------|-------------|
| `MobileBottomBar` | `src/components/layout/MobileBottomBar.tsx` | 5-tab bottom navigation, visible < md |
| `MoreSheet` | `src/components/layout/MoreSheet.tsx` | Bottom sheet for secondary nav items |
| `PullToRefresh` | `src/components/shared/PullToRefresh.tsx` | Pull-to-refresh wrapper for list screens |
| `SwipeAction` | `src/components/shared/SwipeAction.tsx` | Swipeable card wrapper for list items |
| `ActionMenu` | `src/components/shared/ActionMenu.tsx` | Three-dot overflow menu for mobile headers |

### Modified Components

| Component | Changes |
|-----------|---------|
| `Sidebar` | Add `hidden md:flex` |
| `__root.tsx` (RootLayout) | Add `MobileBottomBar`, adjust flex direction, add safe area padding |
| `studio.$slug.tsx` | Add mobile tab-based layout (< md), responsive header, action overflow menu |
| `publish.tsx` | Add mobile card view for PostizQueueView (< md), hide table |
| `index.tsx` (Dashboard) | Add notification badge logic, scrollable project pills |
| `studio.tsx` (list) | Add FAB for "New Post" on mobile, swipeable cards |
| `settings.tsx` | Scrollable tab bar, sticky save button on mobile |
| `AgentChat.tsx` | Add `enterkeyhint="send"`, safe area bottom padding, larger touch targets |
| `index.html` | Add manifest link, theme-color meta, viewport-fit=cover, apple-mobile-web-app tags |
| `index.css` | Add safe area CSS custom properties |

---

## 10. Visual Design Tokens (Mobile Additions)

```css
/* Add to @theme in index.css */
@theme {
  /* Existing */
  --color-primary: #6366f1;
  --color-primary-light: #818cf8;
  --color-surface: #fafafa;
  --color-surface-dark: #18181b;

  /* Mobile additions */
  --spacing-safe-top: env(safe-area-inset-top);
  --spacing-safe-bottom: env(safe-area-inset-bottom);
  --spacing-tab-bar-height: 4rem;   /* 64px bottom tab bar */
}
```

### Bottom Tab Bar Spec

- Height: 64px (4rem) + safe area bottom inset
- Background: white (dark: zinc-900), with 1px top border (zinc-200 / zinc-800)
- Backdrop blur: `backdrop-blur-lg bg-white/80 dark:bg-zinc-900/80`
- Icons: 20px (h-5 w-5), labels: 10px (text-[10px])
- Active state: indigo-600 icon + label, inactive: zinc-400
- Active indicator: 2px top bar on active tab (indigo-600)

### Touch Targets

All interactive elements on mobile must be at least 44x44px effective touch area:
- Tab bar buttons: 64px tall, ~75px wide (well above minimum)
- Card links: full-width, min 48px tall
- Action buttons: min 44px touch target (use padding to expand if visual size is smaller)
- Chat send button: bump from h-10 w-10 to `h-11 w-11 sm:h-10 sm:w-10`

---

## 11. Implementation Priority

### Phase 1: Core Mobile Layout (Day 1)
1. Add `hidden md:flex` to Sidebar
2. Create `MobileBottomBar` component
3. Update RootLayout with responsive flex direction
4. Add safe area + viewport meta to index.html
5. Add `pb-16 md:pb-0` to main content area

### Phase 2: Screen-by-Screen Polish (Day 2)
1. Studio detail mobile tab layout (Content/Chat tabs)
2. Publish queue mobile card view
3. Settings scrollable tabs + sticky save
4. Responsive padding across all screens (p-4 sm:p-6)

### Phase 3: PWA Infrastructure (Day 2-3)
1. Web app manifest
2. Service worker (basic caching)
3. App icons (192, 512, maskable)
4. Apple-specific meta tags

### Phase 4: Touch Enhancements (Day 3+)
1. Pull-to-refresh on list screens
2. Swipe actions on studio list
3. Bottom sheet for "More" nav
4. Chat input polish (enterkeyhint, safe area)

---

## 12. Open Questions

1. **Offline support scope:** Should the PWA cache journal/blog content for offline reading, or just the app shell? Offline reading is useful for reviewing content on the go.

2. **Tablet layout:** At exactly 768px (iPad mini portrait), should we show the sidebar or bottom tabs? Current proposal: sidebar at 768px+. Could also use 1024px as the sidebar breakpoint for a better tablet experience with bottom tabs.

3. **Studio detail on tablet:** On an iPad in portrait (810px), the 50/50 split gives each panel ~405px. This is tight for the chat panel (current min-width is 360px). Consider 40/60 split on md, 50/50 on lg.

4. **Notification persistence:** localStorage vs server-side? Server-side allows cross-device sync but adds API complexity.

5. **Dark mode in PWA:** The theme-color meta tag supports media queries for light/dark. Should the PWA icon also have a dark variant?
