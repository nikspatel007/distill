# TroopX Journal Ghost Theme — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a custom Ghost theme for journal.troopx.ai with dark-mode-default, developer-modern aesthetic, and text-focused post list.

**Architecture:** Fork Ghost's Starter theme (Rollup + PostCSS + Handlebars). Rewrite all templates for a minimal journal layout. CSS variables for dark/light theming. Ship as a zip uploaded to Ghost admin.

**Tech Stack:** Handlebars templates, PostCSS, Rollup, Babel, gscan (Ghost theme validator)

**Design doc:** `docs/plans/2026-02-13-ghost-theme-design.md`

---

### Task 1: Scaffold Theme from Starter

**Files:**
- Create: `ghost-theme/` directory (at project root, sibling to `web/`)

**Step 1: Clone Starter theme**

```bash
cd /Users/nikpatel/Documents/GitHub/distill
git clone --depth 1 https://github.com/TryGhost/Starter.git ghost-theme
rm -rf ghost-theme/.git ghost-theme/.github
```

**Step 2: Update package.json identity**

Edit `ghost-theme/package.json`:
- `"name"` → `"troopx-journal"`
- `"description"` → `"A developer-modern journal theme for TroopX"`
- `"version"` → `"1.0.0"`
- `"author.name"` → `"Nik Patel"`
- `"config.posts_per_page"` → `25`
- Remove `"demo"` and `"repository"` fields (or update to own repo)

**Step 3: Install dependencies and verify build**

```bash
cd ghost-theme && npm install && npm run build
```

Expected: Clean build, `assets/built/` directory created.

**Step 4: Run theme validator**

```bash
npx gscan .
```

Expected: No fatal errors. Warnings about unused features are fine.

**Step 5: Commit**

```bash
git add ghost-theme/
git commit -m "feat: scaffold TroopX Journal Ghost theme from Starter"
```

---

### Task 2: CSS Variables and Dark Mode Foundation

**Files:**
- Modify: `ghost-theme/assets/css/global.css` (or create `ghost-theme/assets/css/vars.css`)
- Modify: `ghost-theme/assets/css/index.css` (main entry point)

**Step 1: Create CSS variables file**

Create `ghost-theme/assets/css/vars.css`:

```css
/* TroopX Journal — CSS Custom Properties */

:root,
[data-theme="dark"] {
    --bg: #0a0a0a;
    --bg-surface: #111111;
    --text: #e5e5e5;
    --text-muted: #737373;
    --accent: #3b82f6;
    --accent-hover: #60a5fa;
    --code-bg: #1a1a1a;
    --border: #262626;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
    --content-width: 680px;
    --page-width: 1080px;
}

[data-theme="light"] {
    --bg: #fafafa;
    --bg-surface: #ffffff;
    --text: #171717;
    --text-muted: #737373;
    --accent: #2563eb;
    --accent-hover: #1d4ed8;
    --code-bg: #f3f4f6;
    --border: #e5e7eb;
}

@media (prefers-color-scheme: light) {
    :root:not([data-theme="dark"]) {
        --bg: #fafafa;
        --bg-surface: #ffffff;
        --text: #171717;
        --text-muted: #737373;
        --accent: #2563eb;
        --accent-hover: #1d4ed8;
        --code-bg: #f3f4f6;
        --border: #e5e7eb;
    }
}
```

**Step 2: Create base global styles**

Replace `ghost-theme/assets/css/global.css`:

```css
@import "vars.css";

/* Reset & Base */
*,
*::before,
*::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html {
    font-size: 16px;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}

body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--font-sans);
    line-height: 1.6;
    min-height: 100vh;
}

a {
    color: var(--accent);
    text-decoration: none;
}

a:hover {
    color: var(--accent-hover);
    text-decoration: underline;
}

img {
    max-width: 100%;
    height: auto;
}

code {
    font-family: var(--font-mono);
    font-size: 0.9em;
    background: var(--code-bg);
    padding: 0.15em 0.4em;
    border-radius: 4px;
}

pre {
    background: var(--code-bg);
    border-radius: 8px;
    padding: 1.25em;
    overflow-x: auto;
    margin: 1.5em 0;
}

pre code {
    background: none;
    padding: 0;
    font-size: 0.875em;
    line-height: 1.6;
}

blockquote {
    border-left: 3px solid var(--accent);
    padding-left: 1.25em;
    margin: 1.5em 0;
    color: var(--text-muted);
    font-style: italic;
}
```

**Step 3: Build and verify**

```bash
cd ghost-theme && npm run build
```

Expected: Clean build.

**Step 4: Commit**

```bash
git add ghost-theme/assets/css/
git commit -m "feat: add CSS variables and dark mode foundation"
```

---

### Task 3: Base Layout (default.hbs)

**Files:**
- Modify: `ghost-theme/default.hbs`
- Create: `ghost-theme/partials/header.hbs`
- Create: `ghost-theme/partials/footer.hbs`
- Create: `ghost-theme/assets/css/layout.css`

**Step 1: Write header partial**

Create `ghost-theme/partials/header.hbs`:

```handlebars
<header class="site-header">
    <div class="site-header-inner">
        <a class="site-title" href="{{@site.url}}">{{@site.title}}</a>
        <nav class="site-nav">
            {{navigation}}
            <button class="theme-toggle" aria-label="Toggle dark mode" type="button">
                <svg class="icon-sun" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
                <svg class="icon-moon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
            </button>
        </nav>
    </div>
</header>
```

**Step 2: Write footer partial**

Create `ghost-theme/partials/footer.hbs`:

```handlebars
<footer class="site-footer">
    <div class="site-footer-inner">
        <section class="subscribe-form">
            <h3>Subscribe to {{@site.title}}</h3>
            <form data-members-form="subscribe" class="footer-subscribe">
                <input type="email" data-members-email placeholder="your@email.com" required />
                <button type="submit">Subscribe</button>
            </form>
        </section>
        <div class="site-footer-meta">
            <span>{{@site.title}}</span>
            <span class="separator">&middot;</span>
            <span>journal.troopx.ai</span>
        </div>
    </div>
</footer>
```

**Step 3: Rewrite default.hbs**

Replace `ghost-theme/default.hbs`:

```handlebars
<!DOCTYPE html>
<html lang="{{@site.locale}}" data-theme="dark">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet" />
    <title>{{meta_title}}</title>
    {{ghost_head}}
    <link rel="stylesheet" href="{{asset "built/index.css"}}" />
</head>
<body class="{{body_class}}">

    {{> header}}

    <main class="site-main">
        {{{body}}}
    </main>

    {{> footer}}

    {{ghost_foot}}
    <script src="{{asset "built/index.js"}}"></script>
</body>
</html>
```

**Step 4: Write layout CSS**

Create `ghost-theme/assets/css/layout.css`:

```css
/* Header */
.site-header {
    border-bottom: 1px solid var(--border);
    padding: 1rem 0;
}

.site-header-inner {
    max-width: var(--page-width);
    margin: 0 auto;
    padding: 0 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.site-title {
    font-family: var(--font-sans);
    font-size: 1rem;
    font-weight: 600;
    color: var(--text);
    text-decoration: none;
    letter-spacing: -0.02em;
}

.site-title:hover {
    color: var(--text);
    text-decoration: none;
}

.site-nav {
    display: flex;
    align-items: center;
    gap: 1.5rem;
}

.site-nav a {
    color: var(--text-muted);
    font-size: 0.875rem;
    font-weight: 500;
}

.site-nav a:hover {
    color: var(--text);
    text-decoration: none;
}

/* Ghost generates nav as <ul> inside {{navigation}} */
.site-nav ul {
    display: flex;
    list-style: none;
    gap: 1.5rem;
    margin: 0;
    padding: 0;
}

.theme-toggle {
    background: none;
    border: none;
    color: var(--text-muted);
    cursor: pointer;
    padding: 0.25rem;
    display: flex;
    align-items: center;
}

.theme-toggle:hover {
    color: var(--text);
}

/* Show/hide sun/moon based on theme */
[data-theme="dark"] .icon-sun { display: block; }
[data-theme="dark"] .icon-moon { display: none; }
[data-theme="light"] .icon-sun { display: none; }
[data-theme="light"] .icon-moon { display: block; }

/* Main */
.site-main {
    max-width: var(--page-width);
    margin: 0 auto;
    padding: 0 1.5rem;
}

/* Footer */
.site-footer {
    border-top: 1px solid var(--border);
    margin-top: 4rem;
    padding: 3rem 0;
}

.site-footer-inner {
    max-width: var(--page-width);
    margin: 0 auto;
    padding: 0 1.5rem;
    text-align: center;
}

.subscribe-form h3 {
    font-size: 1rem;
    font-weight: 500;
    margin-bottom: 0.75rem;
    color: var(--text);
}

.footer-subscribe {
    display: flex;
    gap: 0.5rem;
    max-width: 400px;
    margin: 0 auto 2rem;
}

.footer-subscribe input {
    flex: 1;
    padding: 0.5rem 0.75rem;
    background: var(--bg-surface);
    border: 1px solid var(--border);
    border-radius: 6px;
    color: var(--text);
    font-size: 0.875rem;
    font-family: var(--font-sans);
}

.footer-subscribe input::placeholder {
    color: var(--text-muted);
}

.footer-subscribe button {
    padding: 0.5rem 1rem;
    background: var(--accent);
    color: #fff;
    border: none;
    border-radius: 6px;
    font-size: 0.875rem;
    font-weight: 500;
    cursor: pointer;
    font-family: var(--font-sans);
}

.footer-subscribe button:hover {
    background: var(--accent-hover);
}

.site-footer-meta {
    color: var(--text-muted);
    font-size: 0.8rem;
}

.separator {
    margin: 0 0.5rem;
}

/* Responsive */
@media (max-width: 640px) {
    .site-header-inner {
        padding: 0 1rem;
    }
    .site-main {
        padding: 0 1rem;
    }
    .site-nav {
        gap: 1rem;
    }
    .site-nav ul {
        gap: 1rem;
    }
    .footer-subscribe {
        flex-direction: column;
    }
}
```

**Step 5: Import layout.css in index.css**

Update `ghost-theme/assets/css/index.css` to import all CSS files:

```css
@import "vars.css";
@import "global.css";
@import "layout.css";
```

Note: Depending on how Starter's PostCSS is configured, `global.css` may already be the entry point. Check `ghost-theme/assets/css/index.css` and adjust imports accordingly. The key is that vars.css loads first, then global, then layout.

**Step 6: Build and verify**

```bash
cd ghost-theme && npm run build
```

**Step 7: Commit**

```bash
git add ghost-theme/
git commit -m "feat: add base layout with header, footer, dark mode toggle"
```

---

### Task 4: Homepage Post List (index.hbs)

**Files:**
- Modify: `ghost-theme/index.hbs`
- Create: `ghost-theme/assets/css/home.css`

**Step 1: Rewrite index.hbs**

Replace `ghost-theme/index.hbs`:

```handlebars
{{!< default}}

{{#if @site.description}}
<section class="site-tagline">
    <p>{{@site.description}}</p>
</section>
{{/if}}

<section class="post-feed">
    {{#foreach posts}}
    <article class="post-item">
        <time class="post-date" datetime="{{date format="YYYY-MM-DD"}}">{{date format="MMM DD"}}</time>
        <div class="post-content">
            <h2 class="post-title">
                <a href="{{url}}">{{title}}</a>
            </h2>
            {{#if custom_excerpt}}
                <p class="post-excerpt">{{custom_excerpt}}</p>
            {{else if excerpt}}
                <p class="post-excerpt">{{excerpt words="25"}}</p>
            {{/if}}
        </div>
    </article>
    {{/foreach}}
</section>

{{#if pagination.pages}}
{{!-- only show pagination if more than 1 page --}}
{{#if (gt pagination.pages 1)}}
<nav class="pagination">
    {{#if pagination.prev}}
        <a class="pagination-prev" href="{{pagination.prev}}">Newer</a>
    {{/if}}
    <span class="pagination-info">Page {{pagination.page}} of {{pagination.pages}}</span>
    {{#if pagination.next}}
        <a class="pagination-next" href="{{pagination.next}}">Older</a>
    {{/if}}
</nav>
{{/if}}
{{/if}}
```

**Step 2: Write home.css**

Create `ghost-theme/assets/css/home.css`:

```css
/* Tagline */
.site-tagline {
    padding: 2rem 0 1rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.5rem;
}

.site-tagline p {
    color: var(--text-muted);
    font-size: 0.95rem;
    margin: 0;
}

/* Post Feed */
.post-feed {
    padding-top: 1rem;
}

.post-item {
    display: flex;
    gap: 1.5rem;
    padding: 1.25rem 0;
    border-bottom: 1px solid var(--border);
    align-items: baseline;
}

.post-date {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--text-muted);
    white-space: nowrap;
    min-width: 4.5rem;
    flex-shrink: 0;
}

.post-content {
    flex: 1;
    min-width: 0;
}

.post-title {
    font-size: 1.1rem;
    font-weight: 600;
    line-height: 1.4;
    margin: 0;
    letter-spacing: -0.01em;
}

.post-title a {
    color: var(--text);
}

.post-title a:hover {
    color: var(--accent);
    text-decoration: none;
}

.post-excerpt {
    color: var(--text-muted);
    font-size: 0.875rem;
    line-height: 1.5;
    margin-top: 0.25rem;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
}

/* Pagination */
.pagination {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 1.5rem;
    padding: 2rem 0;
    font-size: 0.875rem;
}

.pagination a {
    color: var(--accent);
    font-weight: 500;
}

.pagination-info {
    color: var(--text-muted);
    font-family: var(--font-mono);
    font-size: 0.8rem;
}

/* Responsive */
@media (max-width: 640px) {
    .post-item {
        flex-direction: column;
        gap: 0.25rem;
    }
    .post-date {
        min-width: auto;
    }
}
```

**Step 3: Add import to index.css**

Add `@import "home.css";` to the CSS entry point.

**Step 4: Build and verify**

```bash
cd ghost-theme && npm run build
```

**Step 5: Commit**

```bash
git add ghost-theme/
git commit -m "feat: add text-focused homepage post list"
```

---

### Task 5: Post Page (post.hbs)

**Files:**
- Modify: `ghost-theme/post.hbs`
- Create: `ghost-theme/assets/css/post.css`

**Step 1: Rewrite post.hbs**

Replace `ghost-theme/post.hbs`:

```handlebars
{{!< default}}

{{#post}}
<article class="post-full">
    <header class="post-header">
        <h1 class="post-full-title">{{title}}</h1>
        <time class="post-full-date" datetime="{{date format="YYYY-MM-DD"}}">{{date format="MMMM D, YYYY"}}</time>
    </header>

    <section class="post-body">
        {{content}}
    </section>

    <nav class="post-nav">
        {{#prev_post}}
        <a class="post-nav-prev" href="{{url}}">
            <span class="post-nav-label">&larr; Previous</span>
            <span class="post-nav-title">{{title}}</span>
        </a>
        {{/prev_post}}
        {{#next_post}}
        <a class="post-nav-next" href="{{url}}">
            <span class="post-nav-label">Next &rarr;</span>
            <span class="post-nav-title">{{title}}</span>
        </a>
        {{/next_post}}
    </nav>

    {{#if comments}}
    <section class="post-comments">
        {{comments}}
    </section>
    {{/if}}
</article>
{{/post}}
```

**Step 2: Write post.css**

Create `ghost-theme/assets/css/post.css`:

```css
/* Post Full */
.post-full {
    max-width: var(--content-width);
    margin: 0 auto;
    padding: 3rem 0;
}

.post-header {
    margin-bottom: 2.5rem;
}

.post-full-title {
    font-size: 2rem;
    font-weight: 700;
    line-height: 1.25;
    letter-spacing: -0.03em;
    margin: 0;
}

.post-full-date {
    display: block;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 0.75rem;
}

/* Post Body — Ghost content */
.post-body {
    font-size: 1.05rem;
    line-height: 1.75;
}

.post-body h2 {
    font-size: 1.4rem;
    font-weight: 600;
    margin-top: 2.5rem;
    margin-bottom: 0.75rem;
    letter-spacing: -0.02em;
}

.post-body h3 {
    font-size: 1.15rem;
    font-weight: 600;
    margin-top: 2rem;
    margin-bottom: 0.5rem;
}

.post-body p {
    margin-bottom: 1.25rem;
}

.post-body ul,
.post-body ol {
    margin-bottom: 1.25rem;
    padding-left: 1.5rem;
}

.post-body li {
    margin-bottom: 0.5rem;
}

.post-body a {
    text-decoration: underline;
    text-underline-offset: 2px;
}

.post-body a:hover {
    text-decoration-color: var(--accent-hover);
}

.post-body hr {
    border: none;
    border-top: 1px solid var(--border);
    margin: 2.5rem 0;
}

/* Post Navigation */
.post-nav {
    display: flex;
    justify-content: space-between;
    gap: 2rem;
    margin-top: 3rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border);
}

.post-nav-prev,
.post-nav-next {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    text-decoration: none;
    max-width: 45%;
}

.post-nav-next {
    text-align: right;
    margin-left: auto;
}

.post-nav-label {
    font-size: 0.75rem;
    font-family: var(--font-mono);
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.post-nav-title {
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--accent);
}

.post-nav-prev:hover .post-nav-title,
.post-nav-next:hover .post-nav-title {
    color: var(--accent-hover);
}

/* Comments */
.post-comments {
    margin-top: 3rem;
    padding-top: 2rem;
    border-top: 1px solid var(--border);
}

/* Responsive */
@media (max-width: 640px) {
    .post-full {
        padding: 2rem 0;
    }
    .post-full-title {
        font-size: 1.5rem;
    }
    .post-body {
        font-size: 1rem;
    }
    .post-nav {
        flex-direction: column;
        gap: 1rem;
    }
    .post-nav-next {
        text-align: left;
    }
}
```

**Step 3: Add import to index.css**

Add `@import "post.css";`

**Step 4: Build and verify**

```bash
cd ghost-theme && npm run build
```

**Step 5: Commit**

```bash
git add ghost-theme/
git commit -m "feat: add clean reading post page with prev/next navigation"
```

---

### Task 6: Static Page Template + Error Page

**Files:**
- Modify: `ghost-theme/page.hbs`
- Modify: `ghost-theme/error.hbs`

**Step 1: Write page.hbs**

Replace `ghost-theme/page.hbs`:

```handlebars
{{!< default}}

{{#post}}
<article class="page-full">
    <header class="page-header">
        <h1 class="page-title">{{title}}</h1>
    </header>
    <section class="post-body">
        {{content}}
    </section>
</article>
{{/post}}
```

**Step 2: Write error.hbs**

Replace `ghost-theme/error.hbs`:

```handlebars
{{!< default}}

<section class="error-page">
    <h1 class="error-code">{{statusCode}}</h1>
    <p class="error-message">{{message}}</p>
    <a class="error-link" href="{{@site.url}}">Back to home</a>
</section>
```

**Step 3: Add page/error CSS to post.css**

Append to `ghost-theme/assets/css/post.css`:

```css
/* Static Page */
.page-full {
    max-width: var(--content-width);
    margin: 0 auto;
    padding: 3rem 0;
}

.page-title {
    font-size: 2rem;
    font-weight: 700;
    letter-spacing: -0.03em;
    margin-bottom: 2rem;
}

/* Error Page */
.error-page {
    text-align: center;
    padding: 6rem 0;
}

.error-code {
    font-family: var(--font-mono);
    font-size: 4rem;
    font-weight: 700;
    color: var(--text-muted);
}

.error-message {
    color: var(--text-muted);
    margin: 1rem 0 2rem;
}

.error-link {
    color: var(--accent);
    font-weight: 500;
}
```

**Step 4: Build and verify**

```bash
cd ghost-theme && npm run build
```

**Step 5: Commit**

```bash
git add ghost-theme/
git commit -m "feat: add page and error templates"
```

---

### Task 7: Dark Mode Toggle JavaScript

**Files:**
- Modify: `ghost-theme/assets/js/index.js`

**Step 1: Write toggle script**

Replace `ghost-theme/assets/js/index.js`:

```js
// Dark mode toggle
(function () {
    const toggle = document.querySelector('.theme-toggle');
    if (!toggle) return;

    // Check saved preference, default to dark
    const saved = localStorage.getItem('theme');
    if (saved) {
        document.documentElement.setAttribute('data-theme', saved);
    }
    // If no saved preference, data-theme="dark" is set in HTML

    toggle.addEventListener('click', function () {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('theme', next);
    });
})();
```

**Step 2: Build and verify**

```bash
cd ghost-theme && npm run build
```

**Step 3: Commit**

```bash
git add ghost-theme/assets/js/
git commit -m "feat: add dark mode toggle with localStorage persistence"
```

---

### Task 8: Clean Up Starter Artifacts

**Files:**
- Delete: `ghost-theme/partials/card.hbs` (unused, Starter's card component)
- Delete: `ghost-theme/tag.hbs` (not using tag pages)
- Delete: `ghost-theme/author.hbs` (single author, no author pages)
- Delete: any other Starter-specific partials/templates not needed
- Modify: `ghost-theme/package.json` — remove unused config if any

**Step 1: Remove unused files**

```bash
cd ghost-theme
rm -f partials/card.hbs tag.hbs author.hbs
```

Only delete files that exist. Check with `ls` first.

**Step 2: Run gscan validation**

```bash
npx gscan .
```

Expected: No fatal errors. Warnings about missing optional templates (tag.hbs, author.hbs) are acceptable since Ghost falls back gracefully.

**Step 3: Final build**

```bash
npm run build && npm run zip
```

Expected: `troopx-journal.zip` (or similar) created in the theme directory.

**Step 4: Commit**

```bash
git add -A ghost-theme/
git commit -m "chore: clean up unused Starter artifacts"
```

---

### Task 9: Upload Theme and Configure Ghost

**Step 1: Upload theme to Ghost**

- Go to Ghost Admin → Settings → Design → Change theme → Upload theme
- Upload the zip from Task 8
- Activate the theme

**Step 2: Configure Ghost settings**

In Ghost Admin → Settings:
- **Site title:** TroopX Journal
- **Site description:** An AI-assisted engineering journal
- **Navigation (primary):** Home (`/`), About (`/about/`)
- **Navigation (secondary):** clear all entries
- Remove any old code injection CSS (the theme handles styling now)

**Step 3: Create About page**

In Ghost Admin → Pages → New page:
- Title: About
- URL: `/about/`
- Content: Brief description of who writes this, what it is, the AI-assisted pipeline angle

**Step 4: Verify**

- Homepage shows post list with dates, titles, excerpts
- Dark mode is default
- Toggle switches to light mode
- Post pages show clean reading layout
- Prev/Next navigation works
- Comments appear on posts
- Subscribe form in footer works
- Mobile responsive

**Step 5: Commit any Ghost admin changes if needed**

---

### Task 10: Fix Post Titles on Ghost (if still showing old ones)

The old "Daily Digest: February X, 2026" posts may still be cached or the new titled posts may need their slugs cleaned up.

**Step 1: Verify via API**

```bash
uv run python3 -c "
import json, time, urllib.request, jwt

key_id, secret = '698fe4c6e9c2dc0001eb7fdc:8acdea38ffcccfd77982658bc48c14c2a8620a2b2d2d53f22266b100bdd73081'.split(':')
iat = int(time.time())
token = jwt.encode({'iat': iat, 'exp': iat + 300, 'aud': '/admin/'}, bytes.fromhex(secret), algorithm='HS256', headers={'alg': 'HS256', 'typ': 'JWT', 'kid': key_id})
req = urllib.request.Request('https://ghost-blog-mmxjf.ondigitalocean.app/ghost/api/admin/posts/?limit=all&fields=id,title,slug', headers={'Authorization': f'Ghost {token}'})
data = json.loads(urllib.request.urlopen(req).read())
for p in data['posts']:
    print(f\"{p['title']} -> /{p['slug']}/\")
"
```

**Step 2: Delete any remaining old-titled posts** if duplicates exist.

**Step 3: Verify public site** loads new theme with correct posts.

---

## Verification Checklist

After all tasks are complete:

- [ ] `cd ghost-theme && npm run build` succeeds
- [ ] `cd ghost-theme && npx gscan .` has no fatal errors
- [ ] `cd ghost-theme && npm run zip` produces uploadable zip
- [ ] Theme uploaded and activated on Ghost
- [ ] Homepage: dark background, text post list, monospace dates
- [ ] Post page: clean 680px reading width, prev/next nav, comments
- [ ] Dark/light toggle works, persists across page loads
- [ ] Mobile responsive (test at 375px width)
- [ ] Subscribe form in footer submits successfully
- [ ] About page renders with static content
- [ ] No "Sign in" / "Sign up" / Portal buttons visible
