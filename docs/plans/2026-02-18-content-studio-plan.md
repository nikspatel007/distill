# Content Studio Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the current Publish page with a Content Studio that lets the user review pipeline output, collaborate with Claude to refine per-platform content, and publish to Postiz — all in one page.

**Architecture:** Content list → Studio editor with inline Claude chat → per-platform previews → one-click publish to Postiz. Claude chat calls `claude -p` subprocess with blog content + platform prompt + user direction. No TroopX dependency.

**Tech Stack:** React + TanStack Router (frontend), Hono API routes (server), Claude subprocess (LLM), Postiz API (publishing)

---

### Task 1: Review Queue Data Model + Zod Schemas

**Files:**
- Modify: `web/shared/schemas.ts` (append new schemas)
- Create: `web/server/lib/review-queue.ts`
- Create: `web/server/__tests__/review-queue.test.ts`

The review queue is a JSON file (`.distill-review-queue.json`) stored in `OUTPUT_DIR`. It tracks per-item, per-platform content status so the studio knows what's draft, adapted, or published.

**Step 1: Add Zod schemas to `web/shared/schemas.ts`**

Append these schemas after the existing `ContentCalendarSchema` block (around line 435):

```typescript
// --- Studio / Review Queue ---

export const ChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  timestamp: z.string(),
});

export const PlatformContentSchema = z.object({
  enabled: z.boolean().default(true),
  content: z.string().nullable().default(null),
  published: z.boolean().default(false),
  postiz_id: z.string().nullable().default(null),
});

export const ReviewItemSchema = z.object({
  slug: z.string(),
  title: z.string(),
  type: z.enum(["weekly", "thematic", "daily-social", "intake"]),
  status: z.enum(["draft", "ready", "published"]).default("draft"),
  generated_at: z.string(),
  source_content: z.string().default(""),
  platforms: z.record(z.string(), PlatformContentSchema).default({}),
  chat_history: z.array(ChatMessageSchema).default([]),
});

export const ReviewQueueSchema = z.object({
  items: z.array(ReviewItemSchema).default([]),
});

export const StudioChatRequestSchema = z.object({
  content: z.string(),
  platform: z.string(),
  message: z.string(),
  history: z.array(ChatMessageSchema).default([]),
});

export const StudioChatResponseSchema = z.object({
  response: z.string(),
  adapted_content: z.string(),
});

export const StudioPublishRequestSchema = z.object({
  platforms: z.array(z.string()).min(1),
  mode: z.enum(["draft", "schedule", "now"]).default("draft"),
  scheduled_at: z.string().optional(),
});
```

Also add the corresponding type exports:

```typescript
export type ChatMessage = z.infer<typeof ChatMessageSchema>;
export type PlatformContent = z.infer<typeof PlatformContentSchema>;
export type ReviewItem = z.infer<typeof ReviewItemSchema>;
export type ReviewQueue = z.infer<typeof ReviewQueueSchema>;
export type StudioChatRequest = z.infer<typeof StudioChatRequestSchema>;
export type StudioChatResponse = z.infer<typeof StudioChatResponseSchema>;
export type StudioPublishRequest = z.infer<typeof StudioPublishRequestSchema>;
```

**Step 2: Create `web/server/lib/review-queue.ts`**

This module reads/writes the review queue JSON file:

```typescript
import { join } from "node:path";
import { readFile, writeFile } from "node:fs/promises";
import { ReviewQueueSchema, type ReviewItem, type ReviewQueue } from "../../shared/schemas.js";
import { getConfig } from "./config.js";

function queuePath(): string {
  return join(getConfig().OUTPUT_DIR, ".distill-review-queue.json");
}

export async function loadReviewQueue(): Promise<ReviewQueue> {
  try {
    const raw = await readFile(queuePath(), "utf-8");
    return ReviewQueueSchema.parse(JSON.parse(raw));
  } catch {
    return { items: [] };
  }
}

export async function saveReviewQueue(queue: ReviewQueue): Promise<void> {
  await writeFile(queuePath(), JSON.stringify(queue, null, 2), "utf-8");
}

export async function getReviewItem(slug: string): Promise<ReviewItem | null> {
  const queue = await loadReviewQueue();
  return queue.items.find((i) => i.slug === slug) ?? null;
}

export async function upsertReviewItem(item: ReviewItem): Promise<void> {
  const queue = await loadReviewQueue();
  const idx = queue.items.findIndex((i) => i.slug === item.slug);
  if (idx >= 0) {
    queue.items[idx] = item;
  } else {
    queue.items.push(item);
  }
  await saveReviewQueue(queue);
}
```

**Step 3: Write tests for review queue**

Create `web/server/__tests__/review-queue.test.ts`:

```typescript
import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtemp, rm, readFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { setConfig, resetConfig, type ServerConfig } from "../lib/config.js";
import { loadReviewQueue, saveReviewQueue, getReviewItem, upsertReviewItem } from "../lib/review-queue.js";

let tempDir: string;

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), "review-queue-"));
  setConfig({ OUTPUT_DIR: tempDir, PORT: 3001, PROJECT_DIR: "", POSTIZ_URL: "", POSTIZ_API_KEY: "" });
});

afterEach(async () => {
  resetConfig();
  await rm(tempDir, { recursive: true, force: true });
});

describe("loadReviewQueue", () => {
  test("returns empty queue when file missing", async () => {
    const queue = await loadReviewQueue();
    expect(queue.items).toEqual([]);
  });

  test("parses existing queue file", async () => {
    const data = { items: [{ slug: "test-post", title: "Test", type: "thematic", status: "draft", generated_at: "2026-02-18T10:00:00", platforms: {}, chat_history: [] }] };
    const { writeFile: wf } = await import("node:fs/promises");
    await wf(join(tempDir, ".distill-review-queue.json"), JSON.stringify(data));
    const queue = await loadReviewQueue();
    expect(queue.items).toHaveLength(1);
    expect(queue.items[0]?.slug).toBe("test-post");
  });
});

describe("saveReviewQueue", () => {
  test("writes queue to disk", async () => {
    await saveReviewQueue({ items: [{ slug: "a", title: "A", type: "weekly", status: "draft", generated_at: "2026-02-18T10:00:00", source_content: "", platforms: {}, chat_history: [] }] });
    const raw = await readFile(join(tempDir, ".distill-review-queue.json"), "utf-8");
    const parsed = JSON.parse(raw);
    expect(parsed.items).toHaveLength(1);
  });
});

describe("getReviewItem", () => {
  test("returns null for missing slug", async () => {
    expect(await getReviewItem("nonexistent")).toBeNull();
  });
});

describe("upsertReviewItem", () => {
  test("inserts new item", async () => {
    await upsertReviewItem({ slug: "new", title: "New", type: "thematic", status: "draft", generated_at: "2026-02-18T10:00:00", source_content: "", platforms: {}, chat_history: [] });
    const item = await getReviewItem("new");
    expect(item?.slug).toBe("new");
  });

  test("updates existing item", async () => {
    await upsertReviewItem({ slug: "up", title: "Up", type: "weekly", status: "draft", generated_at: "2026-02-18T10:00:00", source_content: "", platforms: {}, chat_history: [] });
    await upsertReviewItem({ slug: "up", title: "Updated", type: "weekly", status: "ready", generated_at: "2026-02-18T10:00:00", source_content: "", platforms: {}, chat_history: [] });
    const item = await getReviewItem("up");
    expect(item?.title).toBe("Updated");
    expect(item?.status).toBe("ready");
  });
});
```

**Step 4: Run tests**

```bash
cd web && bun test server/__tests__/review-queue.test.ts
```

Expected: All 6 tests pass.

**Step 5: Commit**

```bash
git add web/shared/schemas.ts web/server/lib/review-queue.ts web/server/__tests__/review-queue.test.ts
git commit -m "feat(studio): add review queue data model and Zod schemas"
```

---

### Task 2: Studio Server Routes — Items + Platforms

**Files:**
- Create: `web/server/routes/studio.ts`
- Modify: `web/server/index.ts` (mount new route)
- Create: `web/server/__tests__/studio.test.ts`

**Step 1: Create `web/server/routes/studio.ts`**

This route file handles listing studio items and fetching individual items. It reads from blog state, blog memory, journal, and intake files to build the content list.

```typescript
import { basename, join } from "node:path";
import { Hono } from "hono";
import {
  BlogFrontmatterSchema,
  BlogMemorySchema,
  BlogStateSchema,
  type ReviewItem,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readJson, readMarkdown } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { isPostizConfigured, listIntegrations } from "../lib/postiz.js";
import { loadReviewQueue, upsertReviewItem } from "../lib/review-queue.js";

const app = new Hono();

// List all publishable content items
app.get("/api/studio/items", async (c) => {
  const { OUTPUT_DIR } = getConfig();
  const queue = await loadReviewQueue();

  // Also discover blog posts not yet in queue
  const [weeklyFiles, thematicFiles] = await Promise.all([
    listFiles(join(OUTPUT_DIR, "blog", "weekly"), /\.md$/),
    listFiles(join(OUTPUT_DIR, "blog", "themes"), /\.md$/),
  ]);

  const allFiles = [...weeklyFiles, ...thematicFiles];
  const blogMemory = await readJson(
    join(OUTPUT_DIR, "blog", ".blog-memory.json"),
    BlogMemorySchema,
  );

  const items: Array<{
    slug: string;
    title: string;
    type: string;
    status: string;
    generated_at: string;
    platforms_ready: number;
    platforms_published: number;
  }> = [];

  // Build items from blog files
  for (const file of allFiles) {
    const slug = basename(file, ".md");
    const raw = await readMarkdown(file);
    if (!raw) continue;

    const parsed = parseFrontmatter(raw, BlogFrontmatterSchema);
    const title = parsed?.frontmatter.title ?? slug;
    const postType = parsed?.frontmatter.post_type ?? "unknown";
    const date = parsed?.frontmatter.date ?? "";

    // Check if in review queue
    const existing = queue.items.find((i) => i.slug === slug);

    const platformEntries = existing?.platforms
      ? Object.values(existing.platforms)
      : [];

    items.push({
      slug,
      title,
      type: postType,
      status: existing?.status ?? "draft",
      generated_at: existing?.generated_at ?? date,
      platforms_ready: platformEntries.filter((p) => p.content !== null).length,
      platforms_published: platformEntries.filter((p) => p.published).length,
    });
  }

  // Sort: drafts first, then by date descending
  items.sort((a, b) => {
    if (a.status !== b.status) {
      const order = { draft: 0, ready: 1, published: 2 };
      return (order[a.status as keyof typeof order] ?? 0) - (order[b.status as keyof typeof order] ?? 0);
    }
    return b.generated_at.localeCompare(a.generated_at);
  });

  return c.json({ items });
});

// Get a single content item with full content
app.get("/api/studio/items/:slug", async (c) => {
  const slug = c.req.param("slug");
  const { OUTPUT_DIR } = getConfig();

  // Find the blog file
  const [weeklyFiles, thematicFiles] = await Promise.all([
    listFiles(join(OUTPUT_DIR, "blog", "weekly"), /\.md$/),
    listFiles(join(OUTPUT_DIR, "blog", "themes"), /\.md$/),
  ]);
  const allFiles = [...weeklyFiles, ...thematicFiles];
  const match = allFiles.find(
    (f) => basename(f, ".md") === slug || f.includes(slug),
  );

  if (!match) return c.json({ error: "Content not found" }, 404);

  const raw = await readMarkdown(match);
  if (!raw) return c.json({ error: "Could not read file" }, 500);

  const parsed = parseFrontmatter(raw, BlogFrontmatterSchema);
  const title = parsed?.frontmatter.title ?? slug;
  const postType = parsed?.frontmatter.post_type ?? "unknown";

  // Load or create review item
  const queue = await loadReviewQueue();
  let reviewItem = queue.items.find((i) => i.slug === slug);

  if (!reviewItem) {
    reviewItem = {
      slug,
      title,
      type: postType as ReviewItem["type"],
      status: "draft",
      generated_at: parsed?.frontmatter.date ?? new Date().toISOString(),
      source_content: parsed?.content ?? "",
      platforms: {},
      chat_history: [],
    };
    await upsertReviewItem(reviewItem);
  }

  return c.json({
    slug,
    title,
    type: postType,
    content: parsed?.content ?? "",
    frontmatter: parsed?.frontmatter ?? {},
    review: reviewItem,
  });
});

// List connected Postiz integrations
app.get("/api/studio/platforms", async (c) => {
  if (!isPostizConfigured()) {
    return c.json({ integrations: [], configured: false });
  }
  try {
    const integrations = await listIntegrations();
    return c.json({ integrations, configured: true });
  } catch {
    return c.json({
      integrations: [],
      configured: true,
      error: "Failed to fetch integrations",
    });
  }
});

export default app;
```

**Step 2: Mount route in `web/server/index.ts`**

Add import after the existing publish import (line 18):

```typescript
import studio from "./routes/studio.js";
```

Add route mount after the publish mount (around line 38):

```typescript
app.route("/", studio);
```

**Step 3: Write tests**

Create `web/server/__tests__/studio.test.ts`:

```typescript
import { describe, expect, test, beforeEach, afterEach } from "bun:test";
import { mkdtemp, mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { app } from "../index.js";
import { setConfig, resetConfig, type ServerConfig } from "../lib/config.js";

let tempDir: string;

const mkTestConfig = (dir: string): ServerConfig => ({
  OUTPUT_DIR: dir,
  PORT: 3001,
  PROJECT_DIR: "",
  POSTIZ_URL: "",
  POSTIZ_API_KEY: "",
});

async function setupBlogFiles(dir: string) {
  await mkdir(join(dir, "blog", "weekly"), { recursive: true });
  await mkdir(join(dir, "blog", "themes"), { recursive: true });

  await writeFile(
    join(dir, "blog", "weekly", "weekly-2026-W07.md"),
    `---
title: Week 7 Synthesis
date: 2026-02-16
post_type: weekly
tags:
  - blog
---

The week's content here.`,
  );

  await writeFile(
    join(dir, "blog", "themes", "agents-outnumber-decisions.md"),
    `---
title: When Agents Outnumber Decisions
date: 2026-02-15
post_type: thematic
tags:
  - agents
---

Thematic deep dive content.`,
  );
}

beforeEach(async () => {
  tempDir = await mkdtemp(join(tmpdir(), "studio-test-"));
  setConfig(mkTestConfig(tempDir));
});

afterEach(async () => {
  resetConfig();
  await rm(tempDir, { recursive: true, force: true });
});

describe("GET /api/studio/items", () => {
  test("returns empty when no blog files", async () => {
    await mkdir(join(tempDir, "blog", "weekly"), { recursive: true });
    await mkdir(join(tempDir, "blog", "themes"), { recursive: true });
    const res = await app.request("/api/studio/items");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.items).toEqual([]);
  });

  test("returns blog posts as studio items", async () => {
    await setupBlogFiles(tempDir);
    const res = await app.request("/api/studio/items");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.items).toHaveLength(2);
    expect(data.items.map((i: { slug: string }) => i.slug).sort()).toEqual([
      "agents-outnumber-decisions",
      "weekly-2026-W07",
    ]);
  });
});

describe("GET /api/studio/items/:slug", () => {
  test("returns 404 for unknown slug", async () => {
    await mkdir(join(tempDir, "blog", "weekly"), { recursive: true });
    await mkdir(join(tempDir, "blog", "themes"), { recursive: true });
    const res = await app.request("/api/studio/items/nonexistent");
    expect(res.status).toBe(404);
  });

  test("returns full content for valid slug", async () => {
    await setupBlogFiles(tempDir);
    const res = await app.request("/api/studio/items/weekly-2026-W07");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.slug).toBe("weekly-2026-W07");
    expect(data.title).toBe("Week 7 Synthesis");
    expect(data.content).toContain("week's content");
    expect(data.review).toBeDefined();
    expect(data.review.status).toBe("draft");
  });
});

describe("GET /api/studio/platforms", () => {
  test("returns not configured when no postiz env", async () => {
    const res = await app.request("/api/studio/platforms");
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data.configured).toBe(false);
    expect(data.integrations).toEqual([]);
  });
});
```

**Step 4: Run tests**

```bash
cd web && bun test server/__tests__/studio.test.ts
```

Expected: All 5 tests pass.

**Step 5: Commit**

```bash
git add web/server/routes/studio.ts web/server/index.ts web/server/__tests__/studio.test.ts
git commit -m "feat(studio): add studio server routes for items and platforms"
```

---

### Task 3: Claude Chat API Endpoint

**Files:**
- Modify: `web/server/routes/studio.ts` (add chat endpoint)
- Modify: `web/server/__tests__/studio.test.ts` (add chat tests)

The chat endpoint receives the blog content + platform + user message + history, builds a prompt, and calls `claude -p` subprocess. It returns the assistant's response and any adapted content.

**Step 1: Add chat endpoint to `web/server/routes/studio.ts`**

Add these imports at top:

```typescript
import { StudioChatRequestSchema } from "../../shared/schemas.js";
import { zValidator } from "@hono/zod-validator";
```

Add this route after the `/api/studio/platforms` handler:

```typescript
// Platform-specific prompts (mirrors src/blog/prompts.py)
const PLATFORM_PROMPTS: Record<string, string> = {
  x: `You are adapting a blog post for X/Twitter. Create a thread of 6-10 tweets.
Rules:
- Each tweet MUST be under 280 characters
- Separate tweets with "---" on its own line
- First tweet hooks the reader
- Last tweet links back or has a call to action
- Use conversational, punchy tone
- No hashtags in tweets (they go in metadata)`,

  linkedin: `You are adapting a blog post for LinkedIn. Write a single post of 1200-1800 characters.
Rules:
- Open with a hook (question, bold claim, or surprising stat)
- Write in first person, conversational but professional
- Use short paragraphs (1-2 sentences)
- Add line breaks between paragraphs for readability
- End with a question or call to action
- No emojis in the first line`,

  slack: `You are adapting a blog post for a Slack channel. Write a concise summary of 800-1400 characters.
Rules:
- Use Slack mrkdwn (not standard markdown): *bold*, _italic_, \`code\`, > quote
- Start with a one-line summary
- Break into bullet points for key insights
- Keep it scannable — people skim Slack
- End with a discussion question`,

  ghost: `You are helping refine a blog post for Ghost (newsletter/website).
Rules:
- Maintain the essay structure
- Suggest improvements to clarity, flow, and engagement
- The content should work as a standalone newsletter
- Keep the author's voice intact`,
};

app.post(
  "/api/studio/chat",
  zValidator("json", StudioChatRequestSchema),
  async (c) => {
    const body = c.req.valid("json");

    const platformPrompt =
      PLATFORM_PROMPTS[body.platform] ??
      `You are helping adapt a blog post for the "${body.platform}" platform.`;

    // Build conversation for claude -p
    const historyText = body.history
      .map((m) => `${m.role === "user" ? "Human" : "Assistant"}: ${m.content}`)
      .join("\n\n");

    const fullPrompt = `${platformPrompt}

Here is the blog post to work with:

---
${body.content}
---

${historyText ? `Previous conversation:\n${historyText}\n\n` : ""}User's direction: ${body.message}

Respond with two sections:
1. RESPONSE: Your conversational response to the user (advice, explanation, what you changed)
2. ADAPTED_CONTENT: The full adapted content for this platform (ready to post)

Format:
RESPONSE:
<your response>

ADAPTED_CONTENT:
<the adapted content>`;

    try {
      const { spawn } = await import("node:child_process");

      const result = await new Promise<string>((resolve, reject) => {
        const proc = spawn("claude", ["-p", fullPrompt], {
          stdio: ["pipe", "pipe", "pipe"],
          timeout: 120_000,
        });

        let stdout = "";
        let stderr = "";

        proc.stdout.on("data", (data: Buffer) => {
          stdout += data.toString();
        });
        proc.stderr.on("data", (data: Buffer) => {
          stderr += data.toString();
        });
        proc.on("close", (code: number | null) => {
          if (code === 0) resolve(stdout);
          else reject(new Error(`claude exited with code ${code}: ${stderr}`));
        });
        proc.on("error", reject);
      });

      // Parse response sections
      const responseMatch = result.match(
        /RESPONSE:\s*([\s\S]*?)(?=ADAPTED_CONTENT:|$)/,
      );
      const contentMatch = result.match(/ADAPTED_CONTENT:\s*([\s\S]*?)$/);

      const response = responseMatch?.[1]?.trim() ?? result.trim();
      const adaptedContent = contentMatch?.[1]?.trim() ?? "";

      return c.json({ response, adapted_content: adaptedContent });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Chat failed";
      return c.json({ error: message }, 500);
    }
  },
);
```

**Step 2: Add chat tests**

Append to `web/server/__tests__/studio.test.ts`:

```typescript
describe("POST /api/studio/chat", () => {
  test("rejects invalid request body", async () => {
    const res = await app.request("/api/studio/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ invalid: true }),
    });
    // zValidator returns 400 for invalid body
    expect(res.status).toBe(400);
  });

  test("accepts valid chat request shape", async () => {
    // This test verifies the endpoint exists and validates input.
    // The actual claude subprocess will fail in test env, which is expected.
    const res = await app.request("/api/studio/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        content: "Blog post text",
        platform: "linkedin",
        message: "Make it punchier",
        history: [],
      }),
    });
    // Will return 500 because claude binary isn't available in test,
    // but importantly NOT 400 (validation passed)
    expect([200, 500]).toContain(res.status);
  });
});
```

**Step 3: Run tests**

```bash
cd web && bun test server/__tests__/studio.test.ts
```

Expected: All tests pass (chat test expects either 200 or 500).

**Step 4: Commit**

```bash
git add web/server/routes/studio.ts web/server/__tests__/studio.test.ts
git commit -m "feat(studio): add Claude chat API endpoint with platform prompts"
```

---

### Task 4: Publish Endpoint with Postiz Integration Fix

**Files:**
- Modify: `web/server/routes/studio.ts` (add publish endpoint)
- Modify: `web/server/lib/postiz.ts` (fix image support in createPost)
- Modify: `web/server/__tests__/studio.test.ts` (add publish tests)

This fixes the known Postiz issue: posts must include `integration.id` from connected integrations, and images must be passed as URLs.

**Step 1: Update `web/server/lib/postiz.ts` to support image URLs**

Replace the `createPost` function with:

```typescript
export async function createPost(
  content: string,
  integrationIds: string[],
  options: { postType?: string; scheduledAt?: string; imageUrl?: string } = {},
): Promise<unknown> {
  const imageArray = options.imageUrl ? [{ url: options.imageUrl }] : [];

  const posts = integrationIds.map((id) => ({
    integration: { id },
    value: [{ content, image: imageArray }],
    settings: { __type: "" },
  }));

  return postizRequest({
    method: "POST",
    path: "/posts",
    body: {
      type: options.postType ?? "draft",
      shortLink: false,
      tags: [],
      date: options.scheduledAt ?? new Date().toISOString(),
      posts,
    },
  });
}
```

**Step 2: Add publish endpoint to `web/server/routes/studio.ts`**

Add import for `StudioPublishRequestSchema` to the existing schema import line. Then add this route:

```typescript
app.post(
  "/api/studio/publish/:slug",
  zValidator("json", StudioPublishRequestSchema),
  async (c) => {
    const slug = c.req.param("slug");
    const body = c.req.valid("json");

    if (!isPostizConfigured()) {
      return c.json({ error: "Postiz not configured" }, 503);
    }

    // Load review item
    const queue = await loadReviewQueue();
    const item = queue.items.find((i) => i.slug === slug);
    if (!item) {
      return c.json({ error: "Item not found in review queue" }, 404);
    }

    try {
      // Get integrations to map platform names to IDs
      const integrations = await listIntegrations();
      const results: Array<{ platform: string; success: boolean; error?: string }> = [];

      for (const platform of body.platforms) {
        const platformContent = item.platforms[platform];
        if (!platformContent?.content) {
          results.push({ platform, success: false, error: "No adapted content" });
          continue;
        }

        if (platformContent.published) {
          results.push({ platform, success: false, error: "Already published" });
          continue;
        }

        // Map platform name to Postiz provider
        const providerMap: Record<string, string> = {
          x: "x",
          linkedin: "linkedin",
          slack: "slack",
        };
        const provider = providerMap[platform] ?? platform;

        const integration = integrations.find(
          (i) => i.provider.toLowerCase().includes(provider),
        );

        if (!integration) {
          results.push({ platform, success: false, error: `No integration for ${platform}` });
          continue;
        }

        try {
          const result = await createPost(
            platformContent.content,
            [integration.id],
            {
              postType: body.mode,
              scheduledAt: body.scheduled_at,
            },
          );

          // Mark as published in review queue
          platformContent.published = true;
          results.push({ platform, success: true });
        } catch (err) {
          const msg = err instanceof Error ? err.message : "Unknown error";
          results.push({ platform, success: false, error: msg });
        }
      }

      // Save updated queue
      await upsertReviewItem(item);

      // Check if all platforms published → mark item as published
      const allPlatforms = Object.values(item.platforms);
      if (allPlatforms.length > 0 && allPlatforms.every((p) => p.published)) {
        item.status = "published";
        await upsertReviewItem(item);
      }

      return c.json({ results });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Publish failed";
      return c.json({ error: message }, 500);
    }
  },
);
```

**Step 3: Add a save-adapted-content endpoint**

This lets the frontend save adapted content from Claude chat back to the review queue:

```typescript
app.put("/api/studio/items/:slug/platform/:platform", async (c) => {
  const slug = c.req.param("slug");
  const platform = c.req.param("platform");

  const body = await c.req.json();
  const content = typeof body.content === "string" ? body.content : null;

  const queue = await loadReviewQueue();
  const item = queue.items.find((i) => i.slug === slug);
  if (!item) return c.json({ error: "Item not found" }, 404);

  if (!item.platforms[platform]) {
    item.platforms[platform] = { enabled: true, content: null, published: false, postiz_id: null };
  }
  item.platforms[platform]!.content = content;

  await upsertReviewItem(item);
  return c.json({ success: true });
});

// Save chat history
app.put("/api/studio/items/:slug/chat", async (c) => {
  const slug = c.req.param("slug");
  const body = await c.req.json();

  const queue = await loadReviewQueue();
  const item = queue.items.find((i) => i.slug === slug);
  if (!item) return c.json({ error: "Item not found" }, 404);

  if (Array.isArray(body.chat_history)) {
    item.chat_history = body.chat_history;
  }

  await upsertReviewItem(item);
  return c.json({ success: true });
});
```

**Step 4: Add publish tests**

Append to `web/server/__tests__/studio.test.ts`:

```typescript
describe("POST /api/studio/publish/:slug", () => {
  test("returns 503 when postiz not configured", async () => {
    await setupBlogFiles(tempDir);
    const res = await app.request("/api/studio/publish/weekly-2026-W07", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ platforms: ["x"], mode: "draft" }),
    });
    expect(res.status).toBe(503);
  });
});

describe("PUT /api/studio/items/:slug/platform/:platform", () => {
  test("saves adapted content", async () => {
    await setupBlogFiles(tempDir);
    // First, create the review item by visiting the item
    await app.request("/api/studio/items/weekly-2026-W07");

    const res = await app.request(
      "/api/studio/items/weekly-2026-W07/platform/linkedin",
      {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: "Adapted for LinkedIn!" }),
      },
    );
    expect(res.status).toBe(200);

    // Verify it was saved
    const itemRes = await app.request("/api/studio/items/weekly-2026-W07");
    const data = await itemRes.json();
    expect(data.review.platforms.linkedin.content).toBe("Adapted for LinkedIn!");
  });
});
```

**Step 5: Run tests**

```bash
cd web && bun test server/__tests__/studio.test.ts
```

Expected: All tests pass.

**Step 6: Commit**

```bash
git add web/server/routes/studio.ts web/server/lib/postiz.ts web/server/__tests__/studio.test.ts
git commit -m "feat(studio): add publish endpoint with Postiz integration fix"
```

---

### Task 5: Content List Page (Frontend)

**Files:**
- Create: `web/src/routes/studio.tsx`
- Modify: `web/src/components/layout/Sidebar.tsx` (rename Publish → Studio)

**Step 1: Create `web/src/routes/studio.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { DateBadge } from "../components/shared/DateBadge.js";

interface StudioItem {
  slug: string;
  title: string;
  type: string;
  status: string;
  generated_at: string;
  platforms_ready: number;
  platforms_published: number;
}

export default function Studio() {
  const { data, isLoading } = useQuery<{ items: StudioItem[] }>({
    queryKey: ["studio-items"],
    queryFn: async () => {
      const res = await fetch("/api/studio/items");
      if (!res.ok) throw new Error("Failed to load studio items");
      return res.json();
    },
  });

  if (isLoading) {
    return <div className="animate-pulse text-zinc-400">Loading content...</div>;
  }

  const items = data?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-bold">Content Studio</h2>
        <p className="mt-1 text-sm text-zinc-500">
          Review, refine with Claude, and publish your content.
        </p>
      </div>

      {items.length === 0 ? (
        <div className="rounded-lg border border-zinc-200 p-8 text-center dark:border-zinc-800">
          <p className="text-zinc-500">
            No content yet. Run{" "}
            <code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">
              distill blog
            </code>{" "}
            to generate content.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {items.map((item) => (
            <Link
              key={item.slug}
              to="/studio/$slug"
              params={{ slug: item.slug }}
              className="flex items-center justify-between rounded-lg border border-zinc-200 p-4 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-zinc-800 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/30"
            >
              <div className="flex items-center gap-3">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{item.title}</span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        item.type === "weekly"
                          ? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
                          : "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
                      }`}
                    >
                      {item.type}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center gap-3 text-xs text-zinc-500">
                    <DateBadge date={item.generated_at} />
                    {item.platforms_ready > 0 && (
                      <span>{item.platforms_ready} platform{item.platforms_ready !== 1 ? "s" : ""} ready</span>
                    )}
                    {item.platforms_published > 0 && (
                      <span className="text-green-600">
                        {item.platforms_published} published
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <StatusBadge status={item.status} />
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
    ready: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
    published: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
  };
  return (
    <span className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${styles[status] ?? styles.draft}`}>
      {status}
    </span>
  );
}
```

**Step 2: Update Sidebar**

In `web/src/components/layout/Sidebar.tsx`, change the Publish nav item. Replace:

```typescript
import {
	BookMarked,
	BookOpen,
	CalendarDays,
	FolderKanban,
	LayoutDashboard,
	PenLine,
	Send,
	Settings,
} from "lucide-react";
```

With:

```typescript
import {
	BookMarked,
	BookOpen,
	CalendarDays,
	FolderKanban,
	LayoutDashboard,
	PenLine,
	Wand2,
	Settings,
} from "lucide-react";
```

And replace the `{ to: "/publish", label: "Publish", icon: Send }` entry with:

```typescript
{ to: "/studio", label: "Studio", icon: Wand2 },
```

**Step 3: Run TypeScript check and build**

```bash
cd web && npx tsc --noEmit
```

Expected: 0 errors. (If the route isn't registered in TanStack Router yet, we'll wire it in the next task.)

**Step 4: Commit**

```bash
git add web/src/routes/studio.tsx web/src/components/layout/Sidebar.tsx
git commit -m "feat(studio): add content list page and update sidebar nav"
```

---

### Task 6: Studio Editor Page — Editor + Chat + Platform Bar

**Files:**
- Create: `web/src/routes/studio.$slug.tsx`
- Create: `web/src/components/studio/AgentChat.tsx`
- Create: `web/src/components/studio/PlatformBar.tsx`

This is the main studio editor page. Layout: full-width markdown content on the left, collapsible Claude chat panel on the right, platform bar at the bottom.

**Step 1: Create `web/src/components/studio/AgentChat.tsx`**

```tsx
import { useState, useRef, useEffect } from "react";
import { useMutation } from "@tanstack/react-query";
import type { ChatMessage } from "../../../shared/schemas.js";

interface AgentChatProps {
  content: string;
  platform: string;
  chatHistory: ChatMessage[];
  onResponse: (response: string, adaptedContent: string, newHistory: ChatMessage[]) => void;
}

export function AgentChat({ content, platform, chatHistory, onResponse }: AgentChatProps) {
  const [message, setMessage] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const chatMutation = useMutation({
    mutationFn: async (userMessage: string) => {
      const res = await fetch("/api/studio/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          platform,
          message: userMessage,
          history: chatHistory,
        }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Chat failed" }));
        throw new Error(err.error || "Chat failed");
      }
      return res.json() as Promise<{ response: string; adapted_content: string }>;
    },
    onSuccess: (data, userMessage) => {
      const newHistory: ChatMessage[] = [
        ...chatHistory,
        { role: "user", content: userMessage, timestamp: new Date().toISOString() },
        { role: "assistant", content: data.response, timestamp: new Date().toISOString() },
      ];
      onResponse(data.response, data.adapted_content, newHistory);
    },
  });

  const handleSend = () => {
    const trimmed = message.trim();
    if (!trimmed || chatMutation.isPending) return;
    setMessage("");
    chatMutation.mutate(trimmed);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatHistory]);

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-200 px-4 py-3 dark:border-zinc-800">
        <h3 className="text-sm font-semibold">Claude</h3>
        <p className="text-xs text-zinc-500">Adapting for {platform}</p>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {chatHistory.length === 0 && (
          <p className="text-sm text-zinc-400 italic">
            Ask Claude to adapt this content for {platform}. Try: "Make it punchier" or "Add a hook"
          </p>
        )}
        {chatHistory.map((msg, i) => (
          <div
            key={`${msg.timestamp}-${i}`}
            className={`rounded-lg px-3 py-2 text-sm ${
              msg.role === "user"
                ? "ml-8 bg-indigo-50 text-indigo-900 dark:bg-indigo-950 dark:text-indigo-100"
                : "mr-8 bg-zinc-100 text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200"
            }`}
          >
            <div className="whitespace-pre-wrap">{msg.content}</div>
          </div>
        ))}
        {chatMutation.isPending && (
          <div className="mr-8 animate-pulse rounded-lg bg-zinc-100 px-3 py-2 text-sm text-zinc-400 dark:bg-zinc-800">
            Claude is thinking...
          </div>
        )}
        {chatMutation.isError && (
          <div className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 dark:bg-red-950 dark:text-red-300">
            {chatMutation.error.message}
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-zinc-200 p-3 dark:border-zinc-800">
        <div className="flex gap-2">
          <input
            type="text"
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && handleSend()}
            placeholder={`Refine for ${platform}...`}
            disabled={chatMutation.isPending}
            className="flex-1 rounded-lg border border-zinc-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 dark:border-zinc-700 dark:bg-zinc-900"
          />
          <button
            type="button"
            onClick={handleSend}
            disabled={chatMutation.isPending || !message.trim()}
            className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
```

**Step 2: Create `web/src/components/studio/PlatformBar.tsx`**

```tsx
import { useMutation, useQuery } from "@tanstack/react-query";
import type { PostizIntegration, PlatformContent } from "../../../shared/schemas.js";

interface PlatformBarProps {
  slug: string;
  selectedPlatform: string;
  onSelectPlatform: (platform: string) => void;
  platforms: Record<string, PlatformContent>;
}

const PLATFORMS = [
  { key: "ghost", label: "Ghost", color: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300" },
  { key: "x", label: "X", color: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300" },
  { key: "linkedin", label: "LinkedIn", color: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300" },
  { key: "slack", label: "Slack", color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300" },
];

export function PlatformBar({ slug, selectedPlatform, onSelectPlatform, platforms }: PlatformBarProps) {
  const { data: integrationData } = useQuery<{
    integrations: PostizIntegration[];
    configured: boolean;
  }>({
    queryKey: ["studio-platforms"],
    queryFn: async () => {
      const res = await fetch("/api/studio/platforms");
      if (!res.ok) throw new Error("Failed to load platforms");
      return res.json();
    },
  });

  const publishMutation = useMutation({
    mutationFn: async (platformKeys: string[]) => {
      const res = await fetch(`/api/studio/publish/${slug}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platforms: platformKeys, mode: "draft" }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: "Publish failed" }));
        throw new Error(err.error || "Publish failed");
      }
      return res.json();
    },
  });

  const configured = integrationData?.configured ?? false;

  return (
    <div className="border-t border-zinc-200 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/50">
      <div className="flex items-center gap-2 px-4 py-3">
        <span className="text-xs font-medium text-zinc-500 uppercase">Platforms:</span>
        {PLATFORMS.map((p) => {
          const platformState = platforms[p.key];
          const hasContent = Boolean(platformState?.content);
          const isPublished = platformState?.published ?? false;
          const isSelected = selectedPlatform === p.key;

          return (
            <button
              key={p.key}
              type="button"
              onClick={() => onSelectPlatform(p.key)}
              className={`relative rounded-full px-3 py-1 text-xs font-medium transition-all ${
                isSelected
                  ? `${p.color} ring-2 ring-indigo-400 ring-offset-1`
                  : hasContent
                    ? p.color
                    : "bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500"
              }`}
            >
              {p.label}
              {isPublished && <span className="ml-1 text-green-600">&#10003;</span>}
            </button>
          );
        })}

        <div className="ml-auto flex items-center gap-2">
          {!configured && (
            <span className="text-xs text-zinc-400">Postiz not connected</span>
          )}
          {configured && (
            <button
              type="button"
              onClick={() => {
                const readyPlatforms = Object.entries(platforms)
                  .filter(([_, v]) => v.content && !v.published)
                  .map(([k]) => k);
                if (readyPlatforms.length > 0) {
                  publishMutation.mutate(readyPlatforms);
                }
              }}
              disabled={publishMutation.isPending}
              className="rounded-lg bg-indigo-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {publishMutation.isPending ? "Publishing..." : "Publish All Ready"}
            </button>
          )}
        </div>
      </div>

      {/* Preview area for selected platform */}
      {platforms[selectedPlatform]?.content && (
        <div className="border-t border-zinc-200 px-4 py-3 dark:border-zinc-800">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-medium text-zinc-500">
              Preview: {PLATFORMS.find((p) => p.key === selectedPlatform)?.label}
            </span>
            {platforms[selectedPlatform]?.published && (
              <span className="text-xs text-green-600 font-medium">Published</span>
            )}
          </div>
          <div className="max-h-32 overflow-y-auto rounded-lg bg-white p-3 text-sm dark:bg-zinc-800">
            <pre className="whitespace-pre-wrap font-sans">{platforms[selectedPlatform]?.content}</pre>
          </div>
        </div>
      )}
    </div>
  );
}
```

**Step 3: Create `web/src/routes/studio.$slug.tsx`**

```tsx
import { useQuery, useMutation } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowLeft, PanelRightClose, PanelRightOpen } from "lucide-react";
import type { ChatMessage, PlatformContent, ReviewItem } from "../../shared/schemas.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { AgentChat } from "../components/studio/AgentChat.js";
import { PlatformBar } from "../components/studio/PlatformBar.js";

interface StudioItemData {
  slug: string;
  title: string;
  type: string;
  content: string;
  frontmatter: Record<string, unknown>;
  review: ReviewItem;
}

export default function StudioEditor() {
  const { slug } = useParams({ strict: false });
  const [chatOpen, setChatOpen] = useState(true);
  const [selectedPlatform, setSelectedPlatform] = useState("x");
  const [chatHistory, setChatHistory] = useState<ChatMessage[]>([]);
  const [platforms, setPlatforms] = useState<Record<string, PlatformContent>>({});

  const { data, isLoading } = useQuery<StudioItemData>({
    queryKey: ["studio-item", slug],
    queryFn: async () => {
      const res = await fetch(`/api/studio/items/${slug}`);
      if (!res.ok) throw new Error("Failed to load content");
      return res.json();
    },
    enabled: Boolean(slug),
  });

  // Sync review state from server on first load
  const reviewLoaded = useQuery({
    queryKey: ["studio-item-review-sync", slug],
    queryFn: async () => {
      if (data?.review) {
        setChatHistory(data.review.chat_history);
        setPlatforms(data.review.platforms);
      }
      return true;
    },
    enabled: Boolean(data),
  });

  // Save adapted content to server
  const savePlatformMutation = useMutation({
    mutationFn: async ({ platform, content }: { platform: string; content: string }) => {
      const res = await fetch(`/api/studio/items/${slug}/platform/${platform}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) throw new Error("Failed to save");
      return res.json();
    },
  });

  // Save chat history to server
  const saveChatMutation = useMutation({
    mutationFn: async (history: ChatMessage[]) => {
      const res = await fetch(`/api/studio/items/${slug}/chat`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_history: history }),
      });
      if (!res.ok) throw new Error("Failed to save chat");
      return res.json();
    },
  });

  const handleChatResponse = (response: string, adaptedContent: string, newHistory: ChatMessage[]) => {
    setChatHistory(newHistory);
    saveChatMutation.mutate(newHistory);

    if (adaptedContent) {
      setPlatforms((prev) => ({
        ...prev,
        [selectedPlatform]: {
          enabled: true,
          content: adaptedContent,
          published: false,
          postiz_id: null,
        },
      }));
      savePlatformMutation.mutate({ platform: selectedPlatform, content: adaptedContent });
    }
  };

  if (isLoading || !data) {
    return <div className="animate-pulse text-zinc-400">Loading studio...</div>;
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col -mx-6 -mt-6">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 px-4 py-2 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <Link
            to="/studio"
            className="rounded-md p-1 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <h1 className="text-lg font-semibold">{data.title}</h1>
            <span className="text-xs text-zinc-500">{data.type}</span>
          </div>
        </div>
        <button
          type="button"
          onClick={() => setChatOpen(!chatOpen)}
          className="rounded-md p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800"
          title={chatOpen ? "Close chat" : "Open chat"}
        >
          {chatOpen ? <PanelRightClose className="h-4 w-4" /> : <PanelRightOpen className="h-4 w-4" />}
        </button>
      </div>

      {/* Main content area */}
      <div className="flex flex-1 overflow-hidden">
        {/* Editor */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="prose prose-zinc max-w-none dark:prose-invert">
            <MarkdownRenderer content={data.content} />
          </div>
        </div>

        {/* Chat panel */}
        {chatOpen && (
          <div className="w-96 border-l border-zinc-200 dark:border-zinc-800">
            <AgentChat
              content={data.content}
              platform={selectedPlatform}
              chatHistory={chatHistory}
              onResponse={handleChatResponse}
            />
          </div>
        )}
      </div>

      {/* Platform bar */}
      <PlatformBar
        slug={slug ?? ""}
        selectedPlatform={selectedPlatform}
        onSelectPlatform={setSelectedPlatform}
        platforms={platforms}
      />
    </div>
  );
}
```

**Step 4: Run TypeScript check**

```bash
cd web && npx tsc --noEmit
```

Expected: 0 errors or minor fixable issues. Fix any type issues before continuing.

**Step 5: Commit**

```bash
git add web/src/routes/studio.tsx web/src/routes/studio.\$slug.tsx web/src/components/studio/AgentChat.tsx web/src/components/studio/PlatformBar.tsx
git commit -m "feat(studio): add studio editor page with Claude chat and platform bar"
```

---

### Task 7: Wire Up TanStack Router + Remove Old Publish Route

**Files:**
- Modify: `web/src/routes/__root.tsx` (if needed for layout changes)
- Remove old `/publish` references from route config if auto-generated
- Verify TanStack Router picks up `studio.tsx` and `studio.$slug.tsx`

TanStack Router uses file-based routing. The files `studio.tsx` and `studio.$slug.tsx` should be auto-discovered. Verify:

**Step 1: Check TanStack Router config**

```bash
cd web && ls src/routes/
```

If TanStack Router generates a `routeTree.gen.ts` file, regenerate it:

```bash
cd web && npx tsr generate
```

Or if there's a manual route tree, update it to include the studio routes.

**Step 2: Delete old publish route (optional)**

Keep `web/src/routes/publish.tsx` for now as a redirect or remove it. If removing:

```bash
rm web/src/routes/publish.tsx
```

Update `web/server/routes/publish.ts` — keep it for backward compatibility or remove if no longer needed.

**Step 3: Verify build**

```bash
cd web && bun run build
```

Expected: Build succeeds, no errors.

**Step 4: Run all web tests**

```bash
cd web && bun test
```

Expected: All existing tests + new studio tests pass.

**Step 5: Commit**

```bash
git add -A web/
git commit -m "feat(studio): wire up TanStack Router and finalize studio integration"
```

---

### Task 8: Manual Integration Test

Verify the full flow works end-to-end.

**Step 1: Start the dev server**

```bash
cd web && OUTPUT_DIR=/Users/nikpatel/Documents/GitHub/insights POSTIZ_URL=https://localhost:6106/api/public/v1 POSTIZ_API_KEY=ee5acefdfc8d1d0b75aa2b52ff3b85a15ef29f40ea776f382d532a27d82db51e bun run dev
```

**Step 2: Open the UI**

Navigate to `http://localhost:5173/studio`. Verify:
- [ ] Content list shows today's blog posts
- [ ] Clicking a post opens the studio editor
- [ ] Blog content renders in the editor panel
- [ ] Chat panel appears on the right
- [ ] Platform bar appears at the bottom with X, LinkedIn, Slack, Ghost tabs

**Step 3: Test Claude chat**

- Select "linkedin" in the platform bar
- Type "Adapt this for LinkedIn, make it conversational" in the chat
- Verify Claude responds with adapted content
- Verify the adapted content appears in the LinkedIn preview in the platform bar

**Step 4: Test publish**

- Click "Publish All Ready" with adapted content
- Verify the Postiz API receives the post with correct integration ID

**Step 5: Commit final state**

```bash
git add -A
git commit -m "feat(studio): content studio complete with Claude chat and Postiz publishing"
```

---

## Summary

| Task | What | Files |
|------|------|-------|
| 1 | Review queue data model + Zod schemas | `schemas.ts`, `review-queue.ts`, tests |
| 2 | Studio server routes (items + platforms) | `studio.ts` route, `index.ts` mount, tests |
| 3 | Claude chat API endpoint | `studio.ts` chat handler, tests |
| 4 | Publish endpoint + Postiz fix | `studio.ts` publish, `postiz.ts` fix, tests |
| 5 | Content list page (frontend) | `studio.tsx`, `Sidebar.tsx` |
| 6 | Studio editor + chat + platform bar | `studio.$slug.tsx`, `AgentChat.tsx`, `PlatformBar.tsx` |
| 7 | Router wiring + cleanup | Route tree, build verification |
| 8 | Manual integration test | End-to-end verification |
