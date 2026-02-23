# nik-patel.com Personal Site Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a personal portfolio + blog site at nik-patel.com powered by Astro (frontend) and Ghost (headless CMS), with RSS feed, image support, and Distill pipeline integration.

**Architecture:** Astro static site pulls blog posts from a dedicated Ghost instance via Content API. Portfolio pages (about, projects, talks) are local Astro content collections. Distill publishes thought-leadership posts to Ghost via Admin API, Astro rebuilds on webhook trigger. RSS feed auto-generated from Ghost posts.

**Tech Stack:** Astro 5, Tailwind CSS 4, `@tryghost/content-api`, `@astrojs/rss`, Vercel (hosting), Ghost 5 on DigitalOcean (CMS)

---

## Prerequisites (manual, before code tasks)

### P1: Provision Ghost instance on DigitalOcean

1. Go to DigitalOcean > App Platform > Create App
2. Choose Ghost from the marketplace (1-Click)
3. Set environment variables:
   - `url`: `https://cms.nik-patel.com` (or temporary DO URL until DNS ready)
   - Configure SMTP (Mailgun) so password reset works this time
4. Once running, go to Ghost Admin > Settings > Integrations > Add Custom Integration
5. Note the **Content API Key** and **Admin API Key**
6. Create a test post to verify the Content API works:
   ```
   curl "https://<ghost-url>/ghost/api/content/posts/?key=<content-api-key>"
   ```

### P2: DNS for nik-patel.com

1. Point `nik-patel.com` A record to Vercel (or CNAME to `cname.vercel-dns.com`)
2. Point `cms.nik-patel.com` CNAME to the Ghost DigitalOcean app URL (for CMS admin access)
3. Verify TLS certs provision correctly

---

## Task 1: Scaffold Astro project

**Files:**
- Create: `personal-site/package.json`
- Create: `personal-site/astro.config.mjs`
- Create: `personal-site/tsconfig.json`
- Create: `personal-site/tailwind.config.mjs`
- Create: `personal-site/src/pages/index.astro` (placeholder)
- Create: `personal-site/.env.example`

**Step 1: Initialize Astro project**

```bash
cd /Users/nikpatel/Documents/GitHub
npm create astro@latest personal-site -- --template minimal --typescript strict --install
cd personal-site
npx astro add tailwind
npm install @tryghost/content-api @astrojs/rss
npm install -D @types/tryghost__content-api
```

**Step 2: Configure astro.config.mjs**

```javascript
import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://nik-patel.com',
  integrations: [tailwind()],
  output: 'static',
});
```

**Step 3: Create .env.example and .env**

```
GHOST_URL=https://cms.nik-patel.com
GHOST_CONTENT_API_KEY=your_content_api_key_here
GHOST_ADMIN_API_KEY=your_admin_api_key_here
```

**Step 4: Create src/env.d.ts**

```typescript
interface ImportMetaEnv {
  readonly GHOST_URL: string;
  readonly GHOST_CONTENT_API_KEY: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
```

**Step 5: Verify it runs**

```bash
npm run dev
# Should open on localhost:4321 with a blank page
```

**Step 6: Commit**

```bash
git init
git add -A
git commit -m "feat: scaffold Astro project with Tailwind"
```

---

## Task 2: Ghost Content API client

**Files:**
- Create: `personal-site/src/lib/ghost.ts`
- Create: `personal-site/src/lib/types.ts`

**Step 1: Create Ghost client**

```typescript
// src/lib/ghost.ts
import GhostContentAPI from '@tryghost/content-api';

export const ghost = new GhostContentAPI({
  url: import.meta.env.GHOST_URL,
  key: import.meta.env.GHOST_CONTENT_API_KEY,
  version: 'v5.0',
});

export async function getAllPosts() {
  return ghost.posts.browse({
    limit: 'all',
    include: ['tags', 'authors'],
    fields: [
      'id', 'slug', 'title', 'html', 'feature_image',
      'excerpt', 'published_at', 'reading_time', 'meta_description',
    ].join(','),
  });
}

export async function getPost(slug: string) {
  return ghost.posts.read({ slug }, {
    include: ['tags', 'authors'],
  });
}

export async function getAllPages() {
  return ghost.pages.browse({ limit: 'all' });
}

export async function getPage(slug: string) {
  return ghost.pages.read({ slug });
}
```

**Step 2: Create types helper**

```typescript
// src/lib/types.ts
import type { PostOrPage, Tag, Author } from '@tryghost/content-api';

export type Post = PostOrPage;
export type { Tag, Author };

export interface Project {
  name: string;
  description: string;
  url: string;
  tags: string[];
  featured: boolean;
}

export interface Talk {
  title: string;
  event: string;
  date: string;
  url?: string;
  slides?: string;
  description: string;
}
```

**Step 3: Commit**

```bash
git add src/lib/
git commit -m "feat: add Ghost Content API client and types"
```

---

## Task 3: Design system and layout

**Files:**
- Create: `personal-site/src/styles/global.css`
- Create: `personal-site/src/layouts/BaseLayout.astro`
- Create: `personal-site/src/components/Header.astro`
- Create: `personal-site/src/components/Footer.astro`
- Create: `personal-site/src/components/ThemeToggle.astro`

**Step 1: Create global CSS with design tokens**

Adapt the TroopX visual direction for personal branding. Dark mode default. Inter for headings, system sans for body, JetBrains Mono for code.

```css
/* src/styles/global.css */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
  --bg: #0a0a0a;
  --bg-surface: #141414;
  --text: #e5e5e5;
  --text-muted: #737373;
  --accent: #3b82f6;
  --accent-hover: #60a5fa;
  --code-bg: #1a1a1a;
  --border: #262626;
}

[data-theme="light"] {
  --bg: #fafafa;
  --bg-surface: #ffffff;
  --text: #171717;
  --text-muted: #737373;
  --accent: #2563eb;
  --accent-hover: #1d4ed8;
  --code-bg: #f5f5f5;
  --border: #e5e5e5;
}

html {
  background-color: var(--bg);
  color: var(--text);
}

body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  line-height: 1.7;
  max-width: 720px;
  margin: 0 auto;
  padding: 0 1.5rem;
}

h1, h2, h3 {
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  line-height: 1.3;
}

a {
  color: var(--accent);
  text-decoration: none;
}
a:hover {
  color: var(--accent-hover);
  text-decoration: underline;
}

code {
  font-family: 'JetBrains Mono', 'Fira Code', 'SF Mono', Consolas, monospace;
  font-size: 0.9em;
  background: var(--code-bg);
  padding: 0.15em 0.4em;
  border-radius: 4px;
}

pre {
  background: var(--code-bg);
  padding: 1.25rem;
  border-radius: 8px;
  overflow-x: auto;
  line-height: 1.5;
}
pre code {
  background: none;
  padding: 0;
}

img {
  max-width: 100%;
  border-radius: 8px;
}

blockquote {
  border-left: 3px solid var(--accent);
  padding-left: 1rem;
  color: var(--text-muted);
  font-style: italic;
}

hr {
  border: none;
  border-top: 1px solid var(--border);
  margin: 2rem 0;
}
```

**Step 2: Create BaseLayout**

```astro
---
// src/layouts/BaseLayout.astro
import Header from '../components/Header.astro';
import Footer from '../components/Footer.astro';
import '../styles/global.css';

interface Props {
  title: string;
  description?: string;
  image?: string;
}

const { title, description = 'Software engineer building with AI agents.', image } = Astro.props;
const canonicalURL = new URL(Astro.url.pathname, Astro.site);
---

<!doctype html>
<html lang="en" data-theme="dark">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    <meta name="description" content={description} />
    <link rel="canonical" href={canonicalURL} />
    <link rel="alternate" type="application/rss+xml" title="Nik Patel" href="/rss.xml" />

    <!-- Open Graph -->
    <meta property="og:title" content={title} />
    <meta property="og:description" content={description} />
    <meta property="og:type" content="website" />
    <meta property="og:url" content={canonicalURL} />
    {image && <meta property="og:image" content={image} />}

    <!-- Twitter -->
    <meta name="twitter:card" content={image ? 'summary_large_image' : 'summary'} />
    <meta name="twitter:title" content={title} />
    <meta name="twitter:description" content={description} />
    {image && <meta name="twitter:image" content={image} />}
  </head>
  <body>
    <Header />
    <main>
      <slot />
    </main>
    <Footer />
  </body>
</html>
```

**Step 3: Create Header**

```astro
---
// src/components/Header.astro
import ThemeToggle from './ThemeToggle.astro';

const navItems = [
  { href: '/', label: 'Home' },
  { href: '/about', label: 'About' },
  { href: '/projects', label: 'Projects' },
  { href: '/blog', label: 'Blog' },
];
---

<header style="display: flex; align-items: center; justify-content: space-between; padding: 2rem 0; border-bottom: 1px solid var(--border);">
  <a href="/" style="text-decoration: none; color: var(--text);">
    <strong style="font-family: 'Inter', sans-serif; font-size: 1.1rem;">Nik Patel</strong>
  </a>
  <nav style="display: flex; align-items: center; gap: 1.5rem;">
    {navItems.map((item) => (
      <a href={item.href} style="color: var(--text-muted); font-size: 0.9rem;">{item.label}</a>
    ))}
    <ThemeToggle />
  </nav>
</header>
```

**Step 4: Create Footer**

```astro
---
// src/components/Footer.astro
---

<footer style="border-top: 1px solid var(--border); padding: 2rem 0; margin-top: 4rem; color: var(--text-muted); font-size: 0.85rem; display: flex; justify-content: space-between;">
  <span>Nik Patel</span>
  <span>
    <a href="/rss.xml">RSS</a>
  </span>
</footer>
```

**Step 5: Create ThemeToggle**

```astro
---
// src/components/ThemeToggle.astro
---

<button
  id="theme-toggle"
  aria-label="Toggle dark mode"
  style="background: none; border: 1px solid var(--border); border-radius: 6px; padding: 0.4rem 0.6rem; cursor: pointer; color: var(--text-muted); font-size: 0.85rem;"
>
  <span id="theme-icon">☀</span>
</button>

<script is:inline>
  const toggle = document.getElementById('theme-toggle');
  const icon = document.getElementById('theme-icon');
  const html = document.documentElement;

  function setTheme(theme) {
    html.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
    icon.textContent = theme === 'dark' ? '☀' : '☾';
  }

  const saved = localStorage.getItem('theme');
  if (saved) {
    setTheme(saved);
  } else if (window.matchMedia('(prefers-color-scheme: light)').matches) {
    setTheme('light');
  }

  toggle.addEventListener('click', () => {
    const current = html.getAttribute('data-theme') || 'dark';
    setTheme(current === 'dark' ? 'light' : 'dark');
  });
</script>
```

**Step 6: Verify layout renders**

Update `src/pages/index.astro`:

```astro
---
import BaseLayout from '../layouts/BaseLayout.astro';
---

<BaseLayout title="Nik Patel">
  <h1 style="margin-top: 3rem;">Nik Patel</h1>
  <p style="color: var(--text-muted);">Software engineer building with AI agents.</p>
</BaseLayout>
```

Run: `npm run dev` and verify header, footer, dark/light toggle work.

**Step 7: Commit**

```bash
git add src/
git commit -m "feat: add design system, layout, header, footer, dark mode"
```

---

## Task 4: Blog index and post pages

**Files:**
- Create: `personal-site/src/pages/blog/index.astro`
- Create: `personal-site/src/pages/blog/[slug].astro`
- Create: `personal-site/src/components/PostList.astro`
- Create: `personal-site/src/components/PostMeta.astro`

**Step 1: Create PostMeta component**

```astro
---
// src/components/PostMeta.astro
interface Props {
  date: string;
  readingTime?: number;
}

const { date, readingTime } = Astro.props;
const formatted = new Date(date).toLocaleDateString('en-US', {
  year: 'numeric', month: 'short', day: 'numeric',
});
---

<span style="font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: var(--text-muted);">
  {formatted}{readingTime ? ` · ${readingTime} min` : ''}
</span>
```

**Step 2: Create PostList component**

```astro
---
// src/components/PostList.astro
import PostMeta from './PostMeta.astro';
import type { Post } from '../lib/types';

interface Props {
  posts: Post[];
}

const { posts } = Astro.props;
---

<ul style="list-style: none; padding: 0; margin: 0;">
  {posts.map((post) => (
    <li style="padding: 1.25rem 0; border-bottom: 1px solid var(--border);">
      <PostMeta date={post.published_at || ''} readingTime={post.reading_time} />
      <h3 style="margin: 0.25rem 0 0.4rem;">
        <a href={`/blog/${post.slug}`} style="color: var(--text); text-decoration: none;">
          {post.title}
        </a>
      </h3>
      {post.excerpt && (
        <p style="margin: 0; color: var(--text-muted); font-size: 0.9rem;">
          {post.excerpt.slice(0, 160)}
        </p>
      )}
    </li>
  ))}
</ul>
```

**Step 3: Create blog index page**

```astro
---
// src/pages/blog/index.astro
import BaseLayout from '../../layouts/BaseLayout.astro';
import PostList from '../../components/PostList.astro';
import { getAllPosts } from '../../lib/ghost';

const posts = await getAllPosts();
---

<BaseLayout title="Blog | Nik Patel" description="Writing about AI agents, architecture patterns, and building in public.">
  <h1 style="margin-top: 3rem;">Blog</h1>
  <p style="color: var(--text-muted); margin-bottom: 2rem;">
    Thinking out loud about building with AI agents.
  </p>
  <PostList posts={posts} />
</BaseLayout>
```

**Step 4: Create dynamic post page**

```astro
---
// src/pages/blog/[slug].astro
import BaseLayout from '../../layouts/BaseLayout.astro';
import PostMeta from '../../components/PostMeta.astro';
import { getAllPosts, getPost } from '../../lib/ghost';

export async function getStaticPaths() {
  const posts = await getAllPosts();
  return posts.map((post) => ({
    params: { slug: post.slug },
  }));
}

const { slug } = Astro.params;
const post = await getPost(slug!);
---

<BaseLayout
  title={`${post.title} | Nik Patel`}
  description={post.meta_description || post.excerpt || ''}
  image={post.feature_image || undefined}
>
  <article style="margin-top: 3rem;">
    <header>
      <h1>{post.title}</h1>
      <PostMeta date={post.published_at || ''} readingTime={post.reading_time} />
    </header>

    {post.feature_image && (
      <img
        src={post.feature_image}
        alt={post.title}
        style="width: 100%; margin: 2rem 0; border-radius: 8px;"
      />
    )}

    <div class="post-content" set:html={post.html} />
  </article>
</BaseLayout>

<style>
  .post-content :global(h2) {
    margin-top: 2.5rem;
  }
  .post-content :global(p) {
    margin: 1.25rem 0;
  }
  .post-content :global(img) {
    margin: 2rem 0;
  }
</style>
```

**Step 5: Verify with dev server**

If Ghost is not provisioned yet, mock the ghost client temporarily:

```bash
npm run dev
# Navigate to /blog and /blog/agent-fatigue-system-design
```

**Step 6: Commit**

```bash
git add src/
git commit -m "feat: add blog index and dynamic post pages"
```

---

## Task 5: About page

**Files:**
- Create: `personal-site/src/pages/about.astro`

**Step 1: Create about page**

```astro
---
// src/pages/about.astro
import BaseLayout from '../layouts/BaseLayout.astro';
---

<BaseLayout title="About | Nik Patel">
  <article style="margin-top: 3rem;">
    <h1>About</h1>

    <p>
      I'm Nik Patel, a software engineer building autonomous systems where
      AI agents collaborate to ship real software.
    </p>

    <p>
      I run <a href="https://troopx.ai">TroopX</a>, a platform for
      multi-agent development workflows. I also build
      <a href="https://github.com/nicholasgpatel/distill">Distill</a>,
      a content pipeline that transforms raw coding sessions into
      publishable content across platforms.
    </p>

    <p>
      This site is where I write about what I'm learning: agent architecture
      patterns, coordination problems, evaluation strategies, and what it
      looks like to run a company where most of the work is done by AI.
    </p>

    <h2>Elsewhere</h2>
    <ul>
      <li><a href="https://github.com/nicholasgpatel">GitHub</a></li>
      <li><a href="https://linkedin.com/in/nikgpatel">LinkedIn</a></li>
      <li><a href="https://journal.troopx.ai">TroopX Journal</a></li>
    </ul>
  </article>
</BaseLayout>
```

Note: Update the bio text, links, and social URLs to match your actual profiles.

**Step 2: Commit**

```bash
git add src/pages/about.astro
git commit -m "feat: add about page"
```

---

## Task 6: Projects page

**Files:**
- Create: `personal-site/src/content/projects/troopx.md`
- Create: `personal-site/src/content/projects/distill.md`
- Create: `personal-site/src/content/config.ts`
- Create: `personal-site/src/pages/projects/index.astro`

**Step 1: Define content collection schema**

```typescript
// src/content/config.ts
import { defineCollection, z } from 'astro:content';

const projects = defineCollection({
  type: 'content',
  schema: z.object({
    name: z.string(),
    description: z.string(),
    url: z.string().url().optional(),
    github: z.string().url().optional(),
    tags: z.array(z.string()).default([]),
    featured: z.boolean().default(false),
    order: z.number().default(0),
  }),
});

export const collections = { projects };
```

**Step 2: Create project entries**

```markdown
---
# src/content/projects/troopx.md
name: TroopX
description: Multi-agent development platform. Orchestrates teams of AI agents through structured workflows with dev, QA, and reviewer roles.
url: https://troopx.ai
tags: [multi-agent, orchestration, workflows]
featured: true
order: 1
---

TroopX is a platform for running multi-agent software development workflows. It coordinates AI agents with different roles (developer, QA, reviewer) through structured state machines, enabling autonomous software delivery with built-in quality gates.

Key capabilities:
- **Agent roster**: Define reusable agent templates with specific capabilities
- **Squad workflows**: Compose agents into teams with structured coordination
- **Blackboard communication**: Shared state for inter-agent findings
- **Quality gates**: Mandatory review checkpoints before code ships
```

```markdown
---
# src/content/projects/distill.md
name: Distill
description: Content pipeline that transforms raw AI coding sessions into publishable blog posts, journal entries, and social content across platforms.
github: https://github.com/nicholasgpatel/distill
tags: [content-pipeline, AI, publishing]
featured: true
order: 2
---

Distill ingests coding sessions from Claude and Codex, analyzes patterns, synthesizes daily journal entries, generates blog posts, and publishes across Ghost, social media, and Obsidian. The entire pipeline is AI-powered, including a daily brainstorm system that surfaces content ideas from Hacker News, arXiv, and RSS feeds.

Key features:
- **Multi-source intake**: RSS, browser history, Substack, LinkedIn, arXiv, YouTube
- **LLM synthesis**: Daily journals, weekly essays, thematic deep-dives
- **Multi-platform publishing**: Ghost, Postiz (social), Obsidian, markdown
- **Content brainstorm**: Daily idea generation scored against content pillars
```

**Step 3: Create projects page**

```astro
---
// src/pages/projects/index.astro
import BaseLayout from '../../layouts/BaseLayout.astro';
import { getCollection } from 'astro:content';

const projects = (await getCollection('projects'))
  .sort((a, b) => a.data.order - b.data.order);
---

<BaseLayout title="Projects | Nik Patel" description="Things I'm building.">
  <h1 style="margin-top: 3rem;">Projects</h1>

  <div style="display: flex; flex-direction: column; gap: 2rem; margin-top: 2rem;">
    {projects.map(async (project) => {
      const { Content } = await project.render();
      return (
        <article style="padding: 1.5rem; background: var(--bg-surface); border: 1px solid var(--border); border-radius: 8px;">
          <h2 style="margin-top: 0;">
            {project.data.url ? (
              <a href={project.data.url}>{project.data.name}</a>
            ) : (
              project.data.name
            )}
          </h2>
          <p style="color: var(--text-muted); margin: 0.5rem 0 1rem;">{project.data.description}</p>
          <div style="display: flex; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 1rem;">
            {project.data.tags.map((tag: string) => (
              <span style="font-size: 0.75rem; padding: 0.2rem 0.6rem; background: var(--code-bg); border-radius: 4px; color: var(--text-muted);">
                {tag}
              </span>
            ))}
          </div>
          <div class="project-body">
            <Content />
          </div>
          <div style="display: flex; gap: 1rem; margin-top: 1rem;">
            {project.data.url && <a href={project.data.url}>Visit</a>}
            {project.data.github && <a href={project.data.github}>GitHub</a>}
          </div>
        </article>
      );
    })}
  </div>
</BaseLayout>
```

**Step 4: Commit**

```bash
git add src/content/ src/pages/projects/
git commit -m "feat: add projects page with content collection"
```

---

## Task 7: RSS feed

**Files:**
- Create: `personal-site/src/pages/rss.xml.ts`

**Step 1: Create RSS endpoint**

```typescript
// src/pages/rss.xml.ts
import rss from '@astrojs/rss';
import type { APIContext } from 'astro';
import { getAllPosts } from '../lib/ghost';

export async function GET(context: APIContext) {
  const posts = await getAllPosts();

  return rss({
    title: 'Nik Patel',
    description: 'Writing about AI agents, architecture patterns, and building in public.',
    site: context.site!.toString(),
    items: posts.map((post) => ({
      title: post.title || '',
      pubDate: new Date(post.published_at || ''),
      description: post.excerpt || post.meta_description || '',
      link: `/blog/${post.slug}/`,
      content: post.html || undefined,
    })),
    customData: '<language>en-us</language>',
    stylesheet: '/rss-styles.xsl',
  });
}
```

**Step 2: Create optional RSS stylesheet for browser display**

```xml
<!-- public/rss-styles.xsl -->
<?xml version="1.0" encoding="utf-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:atom="http://www.w3.org/2005/Atom">
  <xsl:output method="html" version="1.0" encoding="UTF-8" indent="yes"/>
  <xsl:template match="/">
    <html>
      <head>
        <title><xsl:value-of select="/rss/channel/title"/> — RSS Feed</title>
        <style>
          body { font-family: -apple-system, sans-serif; max-width: 720px; margin: 2rem auto; padding: 0 1.5rem; line-height: 1.6; }
          h1 { font-size: 1.5rem; }
          .item { border-bottom: 1px solid #e5e5e5; padding: 1rem 0; }
          .item h2 { font-size: 1.1rem; margin: 0; }
          .item p { color: #666; font-size: 0.9rem; }
          a { color: #2563eb; }
        </style>
      </head>
      <body>
        <h1>📡 <xsl:value-of select="/rss/channel/title"/></h1>
        <p><xsl:value-of select="/rss/channel/description"/></p>
        <p>This is an RSS feed. Copy the URL into your reader to subscribe.</p>
        <xsl:for-each select="/rss/channel/item">
          <div class="item">
            <h2><a href="{link}"><xsl:value-of select="title"/></a></h2>
            <p><xsl:value-of select="description"/></p>
          </div>
        </xsl:for-each>
      </body>
    </html>
  </xsl:template>
</xsl:stylesheet>
```

**Step 3: Verify RSS**

```bash
npm run dev
# Visit http://localhost:4321/rss.xml
```

**Step 4: Commit**

```bash
git add src/pages/rss.xml.ts public/rss-styles.xsl
git commit -m "feat: add RSS feed with browser stylesheet"
```

---

## Task 8: Homepage

**Files:**
- Modify: `personal-site/src/pages/index.astro`

**Step 1: Build homepage with intro + recent posts + projects**

```astro
---
// src/pages/index.astro
import BaseLayout from '../layouts/BaseLayout.astro';
import PostList from '../components/PostList.astro';
import { getAllPosts } from '../lib/ghost';
import { getCollection } from 'astro:content';

const posts = (await getAllPosts()).slice(0, 5);
const projects = (await getCollection('projects'))
  .filter((p) => p.data.featured)
  .sort((a, b) => a.data.order - b.data.order);
---

<BaseLayout title="Nik Patel">
  <section style="margin-top: 3rem;">
    <h1>Nik Patel</h1>
    <p style="font-size: 1.15rem; color: var(--text-muted);">
      Software engineer building autonomous systems where AI agents
      collaborate to ship real software.
    </p>
  </section>

  <section style="margin-top: 3rem;">
    <h2 style="font-size: 1.1rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">
      Recent Writing
    </h2>
    <PostList posts={posts} />
    <a href="/blog" style="display: inline-block; margin-top: 1rem; font-size: 0.9rem;">
      All posts →
    </a>
  </section>

  <section style="margin-top: 3rem;">
    <h2 style="font-size: 1.1rem; color: var(--text-muted); text-transform: uppercase; letter-spacing: 0.05em;">
      Projects
    </h2>
    {projects.map((p) => (
      <div style="padding: 1rem 0; border-bottom: 1px solid var(--border);">
        <h3 style="margin: 0;">
          <a href={p.data.url || `/projects`} style="color: var(--text);">{p.data.name}</a>
        </h3>
        <p style="margin: 0.25rem 0 0; color: var(--text-muted); font-size: 0.9rem;">
          {p.data.description}
        </p>
      </div>
    ))}
    <a href="/projects" style="display: inline-block; margin-top: 1rem; font-size: 0.9rem;">
      All projects →
    </a>
  </section>
</BaseLayout>
```

**Step 2: Commit**

```bash
git add src/pages/index.astro
git commit -m "feat: build homepage with intro, recent posts, projects"
```

---

## Task 9: Distill integration

**Files:**
- Modify: `distill/src/config.py` (add personal Ghost config)
- Modify: `distill/src/brainstorm/publisher.py` (add personal Ghost target)

**Step 1: Add personal Ghost config to .distill.toml**

```toml
[ghost_personal]
url = "https://cms.nik-patel.com"
admin_api_key = ""  # Set via GHOST_PERSONAL_ADMIN_API_KEY env var
```

**Step 2: Update brainstorm publisher to support dual Ghost targets**

When a brainstorm idea is marked for "blog" platform, publish to personal Ghost.
When marked for "social" or "both", publish to both.

This is a config-level change: the publisher already supports Ghost via `GhostAPIClient`.
Add a second client instance configured from `ghost_personal` config.

**Step 3: Commit**

```bash
git add src/config.py src/brainstorm/publisher.py .distill.toml
git commit -m "feat: add personal Ghost target for Distill publishing"
```

---

## Task 10: Vercel deployment

**Files:**
- Create: `personal-site/vercel.json`

**Step 1: Create Vercel config**

```json
{
  "buildCommand": "npm run build",
  "outputDirectory": "dist",
  "framework": "astro"
}
```

**Step 2: Deploy**

```bash
cd personal-site
npx vercel --prod
```

Set environment variables in Vercel dashboard:
- `GHOST_URL`
- `GHOST_CONTENT_API_KEY`

**Step 3: Configure custom domain**

In Vercel dashboard, add `nik-patel.com` as a custom domain and follow the DNS instructions.

**Step 4: Set up rebuild webhook**

In Ghost Admin > Settings > Integrations, add a webhook that triggers on "Post published":
- URL: Vercel Deploy Hook URL (create in Vercel > Settings > Git > Deploy Hooks)
- This ensures the static site rebuilds when new content is published via Distill or Ghost admin.

**Step 5: Commit**

```bash
git add vercel.json
git commit -m "feat: add Vercel deployment config"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Scaffold Astro + Tailwind | Project setup |
| 2 | Ghost Content API client | `src/lib/ghost.ts`, `src/lib/types.ts` |
| 3 | Design system + layout | CSS, BaseLayout, Header, Footer, ThemeToggle |
| 4 | Blog index + post pages | `src/pages/blog/` |
| 5 | About page | `src/pages/about.astro` |
| 6 | Projects page | Content collection + page |
| 7 | RSS feed | `src/pages/rss.xml.ts` |
| 8 | Homepage | `src/pages/index.astro` |
| 9 | Distill integration | Config + publisher update |
| 10 | Vercel deployment | `vercel.json` + deploy |

Total: ~15 files, 10 tasks. Ghost provisioning and DNS are manual prerequisites.
