# Ghost Theme Design: TroopX Journal

## Editorial Identity

- **Site name:** TroopX Journal
- **Tagline:** An AI-assisted engineering journal
- **Domain:** journal.troopx.ai
- **Audience:** Broader tech audience interested in AI, developer tools, building in public
- **Angle:** AI-assisted creation. The content pipeline itself is AI-powered. The process is the story.
- **Voice:** Personal, opinionated, technically specific. Essays, not blog posts.

## Visual Direction

Developer-modern aesthetic. Think Vercel blog, Linear changelog. Dark mode default, clean typography, content-first layout. No decoration for decoration's sake.

## Color Scheme

| Token | Value | Usage |
|-------|-------|-------|
| `--bg` | `#0a0a0a` | Page background (dark mode) |
| `--bg-light` | `#fafafa` | Page background (light mode) |
| `--text` | `#e5e5e5` | Body text (dark mode) |
| `--text-light` | `#171717` | Body text (light mode) |
| `--text-muted` | `#737373` | Dates, metadata, secondary text |
| `--accent` | `#3b82f6` | Links, interactive elements |
| `--accent-hover` | `#60a5fa` | Link hover state |
| `--code-bg` | `#1a1a1a` | Code block background |
| `--border` | `#262626` | Subtle dividers |

Dark mode is the default. Light mode toggle available via button in the header.

## Typography

- **Headings:** Inter (loaded via Google Fonts) or system sans-serif fallback
- **Body:** System sans-serif stack: `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Code / monospace:** `'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace`
- **Monospace used for:** inline code, code blocks, post dates in the list, metadata

## Homepage Layout

```
+--------------------------------------------------+
|  [TroopX wordmark]    Home  About  Subscribe  [toggle] |
+--------------------------------------------------+
|                                                    |
|  An AI-assisted engineering journal                |
|                                                    |
+--------------------------------------------------+
|                                                    |
|  Feb 13   When the Pipeline Reads Itself           |
|           Today was the day distill got pointed...  |
|                                                    |
|  Feb 12   Killing the research analyst             |
|           Distill has had this prompt sitting...    |
|                                                    |
|  Feb 11   The Machine That Reads Itself            |
|           I spent most of today watching my...      |
|                                                    |
|  ...                                               |
|                                                    |
+--------------------------------------------------+
|  Subscribe to TroopX Journal                       |
|  [email input]  [Subscribe]                        |
|                                                    |
|  TroopX Journal  |  journal.troopx.ai              |
+--------------------------------------------------+
```

### Header
- TroopX wordmark (text, not image logo) left-aligned
- Nav links right: Home, About, Subscribe
- Dark/light mode toggle button (sun/moon icon)
- No hero image, no gradient, no banner

### Post List
- Each entry: date (monospace, muted) + title (prominent, linked) + one-line excerpt (muted)
- Date left-aligned or inline before title
- No featured images, no tags, no reading time
- Chronological, newest first
- Pagination at bottom (Page 1 of N)

### Footer
- Newsletter subscribe form (email input + button)
- Site name + domain
- Minimal, no social links clutter

## Post Page Layout

```
+--------------------------------------------------+
|  [TroopX wordmark]    Home  About  Subscribe  [toggle] |
+--------------------------------------------------+
|                                                    |
|  When the Pipeline Reads Itself                    |
|  Feb 13, 2026                                      |
|                                                    |
|  [essay body, ~680px max-width]                    |
|                                                    |
|  ...prose with inline code, links, H2 headers...  |
|                                                    |
|  ---                                               |
|  < Previous: Killing the research analyst          |
|    Next: The Machine That Reads Itself >           |
|                                                    |
|  [Comments section]                                |
|                                                    |
+--------------------------------------------------+
```

### Post Body
- Max width: ~680px, centered
- Line height: 1.7-1.8 for comfortable reading
- H2 headers for sections within the essay
- Code blocks: dark background, rounded corners, syntax highlighting
- Inline code: monospace, slightly darker background
- Links: accent blue, underlined on hover
- Block quotes: left border accent, italic

### Post Navigation
- Previous / Next links at bottom with post titles
- No related posts, no author bio card, no sidebar

## Technical Approach

### Base
Fork Ghost's [Starter theme](https://github.com/TryGhost/Starter) as the foundation. It provides:
- Modern build tooling (Gulp, PostCSS)
- Handlebars templates
- ESM JavaScript
- Hot reload for development

### Files to Create/Modify
- `default.hbs` - base layout with header, footer, dark/light toggle
- `index.hbs` - homepage post list (text-focused, no cards)
- `post.hbs` - single post layout (clean reading, prev/next nav)
- `page.hbs` - static pages (About)
- `assets/css/` - custom CSS with CSS variables for theming
- `package.json` - theme metadata (name, version, config)

### Dark Mode Implementation
- CSS variables for all colors
- `data-theme` attribute on `<html>`
- JavaScript toggle that persists to localStorage
- Default: dark. Respects `prefers-color-scheme` on first visit.

### Ghost Features Used
- Members (for comments, newsletter subscribe)
- Navigation (configured in Ghost admin)
- Code injection (for any future one-off tweaks)
- Tags (for categorization, but not displayed prominently)

### Ghost Features NOT Used
- Featured images on posts
- Author cards / multi-author
- Tiers / paid memberships
- Portal (sign-in overlay)

## About Page Content

Brief section covering:
- Who writes this (Nik Patel, software engineer)
- What it is (daily engineering journal, AI-assisted)
- What makes it different (the content pipeline that produces this blog is itself a subject of the blog)
- Link to TroopX and Distill project

## What This Design Deliberately Omits

- **No logo/icon.** Text wordmark only. Can add later.
- **No social sharing buttons.** If people want to share, they'll copy the URL.
- **No reading time estimates.** The essays are short. You'll know when you're done.
- **No tag pages.** Not enough content yet to warrant category navigation.
- **No search.** Ghost has built-in search (the magnifying glass). Keep it.
- **No RSS link in nav.** Ghost auto-generates /rss/. Power users will find it.
