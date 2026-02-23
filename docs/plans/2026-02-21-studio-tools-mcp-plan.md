# Studio Tools & MCP Server Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Extract Studio chat tools into reusable modules and expose them via MCP server for external agents.

**Architecture:** Pure tool functions in `server/tools/`, imported directly by Studio chat endpoint. Thin MCP wrapper in `server/mcp/server.ts` exposes the same functions over stdio for Claude Code / TroopX. Pipeline tools shell out to `uv run python -m distill`.

**Tech Stack:** `@modelcontextprotocol/sdk`, `cheerio`, AI SDK `tool()`, Bun subprocess

---

### Task 1: Install Dependencies

**Files:**
- Modify: `web/package.json`

**Step 1: Install packages**

```bash
cd web && bun add @modelcontextprotocol/sdk cheerio
cd web && bun add -d @types/cheerio
```

**Step 2: Verify install**

```bash
cd web && bun run check
```

Expected: tsc clean, biome clean (new deps don't break anything)

**Step 3: Commit**

```bash
cd web && git add package.json bun.lock
git commit -m "chore: add @modelcontextprotocol/sdk and cheerio dependencies"
```

---

### Task 2: Content Tools Module

**Files:**
- Create: `web/server/tools/content.ts`
- Test: `web/server/__tests__/tools-content.test.ts`

These wrap the existing ContentStore functions as AI SDK `tool()` definitions.

**Step 1: Write tests**

Create `web/server/__tests__/tools-content.test.ts`:

```typescript
import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { writeFileSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";
import { setConfig, resetConfig } from "../lib/config.js";
import { saveContentStore } from "../lib/content-store.js";
import type { ContentStoreData } from "../lib/content-store.js";

const FIXTURES = join(import.meta.dir, "fixtures");

// Seed a test ContentStore
function seedStore(): void {
	const store: ContentStoreData = {
		"test-post": {
			slug: "test-post",
			content_type: "weekly",
			title: "Test Post",
			body: "# Original Content",
			status: "draft",
			created_at: "2026-02-21T00:00:00Z",
			source_dates: [],
			tags: ["test"],
			images: [],
			platforms: {
				ghost: {
					platform: "ghost",
					content: "Ghost version",
					published: false,
					published_at: null,
					external_id: "",
				},
			},
			chat_history: [],
			metadata: {},
			file_path: "",
		},
	};
	saveContentStore(store);
}

describe("Content tools", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
		mkdirSync(FIXTURES, { recursive: true });
		seedStore();
	});

	afterAll(() => {
		resetConfig();
	});

	test("listContent returns items", async () => {
		const { listContent } = await import("../tools/content.js");
		const result = await listContent({});
		expect(result.items.length).toBeGreaterThan(0);
		expect(result.items[0].slug).toBe("test-post");
	});

	test("listContent filters by status", async () => {
		const { listContent } = await import("../tools/content.js");
		const result = await listContent({ status: "published" });
		expect(result.items.length).toBe(0);
	});

	test("getContent returns full record", async () => {
		const { getContent } = await import("../tools/content.js");
		const result = await getContent({ slug: "test-post" });
		expect(result.title).toBe("Test Post");
		expect(result.body).toContain("# Original Content");
	});

	test("getContent returns error for missing slug", async () => {
		const { getContent } = await import("../tools/content.js");
		const result = await getContent({ slug: "nonexistent" });
		expect(result.error).toBeDefined();
	});

	test("updateSource updates body", async () => {
		const { updateSource, getContent } = await import("../tools/content.js");
		const result = await updateSource({ slug: "test-post", content: "# Updated" });
		expect(result.saved).toBe(true);
		const record = await getContent({ slug: "test-post" });
		expect(record.body).toBe("# Updated");
		// Reset
		await updateSource({ slug: "test-post", content: "# Original Content" });
	});

	test("savePlatform saves adapted content", async () => {
		const { savePlatform, getContent } = await import("../tools/content.js");
		const result = await savePlatform({
			slug: "test-post",
			platform: "x",
			content: "Thread content",
		});
		expect(result.saved).toBe(true);
		const record = await getContent({ slug: "test-post" });
		expect(record.platforms?.x?.content).toBe("Thread content");
	});

	test("updateStatus changes status", async () => {
		const { updateStatus, getContent } = await import("../tools/content.js");
		await updateStatus({ slug: "test-post", status: "review" });
		const record = await getContent({ slug: "test-post" });
		expect(record.status).toBe("review");
		// Reset
		await updateStatus({ slug: "test-post", status: "draft" });
	});

	test("createContent creates a new item", async () => {
		const { createContent, getContent } = await import("../tools/content.js");
		const result = await createContent({
			title: "New Post",
			body: "Some content",
			content_type: "thematic",
			tags: ["new"],
		});
		expect(result.slug).toBeDefined();
		expect(result.created).toBe(true);
		const record = await getContent({ slug: result.slug });
		expect(record.title).toBe("New Post");
	});
});
```

**Step 2: Run tests — verify they fail**

```bash
cd web && bun test server/__tests__/tools-content.test.ts
```

Expected: FAIL (module `../tools/content.js` not found)

**Step 3: Implement content tools**

Create `web/server/tools/content.ts`:

```typescript
/**
 * Content management tools — pure functions wrapping ContentStore.
 *
 * Used directly by Studio chat (imported as AI SDK tools) and
 * exposed via MCP server for external agents.
 */
import {
	getContentRecord,
	loadContentStore,
	saveContentStore,
	updateContentRecord,
} from "../lib/content-store.js";

export async function listContent(params: {
	type?: string;
	status?: string;
}): Promise<{ items: Array<{ slug: string; title: string; type: string; status: string }> }> {
	const store = loadContentStore();
	let items = Object.values(store).map((r) => ({
		slug: r.slug,
		title: r.title,
		type: r.content_type,
		status: r.status,
		created_at: r.created_at,
	}));

	if (params.type) {
		items = items.filter((i) => i.type === params.type);
	}
	if (params.status) {
		items = items.filter((i) => i.status === params.status);
	}

	return { items };
}

export async function getContent(params: {
	slug: string;
}): Promise<Record<string, unknown>> {
	const record = getContentRecord(params.slug);
	if (!record) return { error: `Content "${params.slug}" not found` };
	return { ...record };
}

export async function updateSource(params: {
	slug: string;
	content: string;
	title?: string;
}): Promise<{ saved: boolean; error?: string }> {
	const updates: { body: string; title?: string } = { body: params.content };
	if (params.title) updates.title = params.title;
	const updated = updateContentRecord(params.slug, updates);
	if (!updated) return { saved: false, error: `Content "${params.slug}" not found` };
	return { saved: true };
}

export async function savePlatform(params: {
	slug: string;
	platform: string;
	content: string;
}): Promise<{ saved: boolean; platform: string; error?: string }> {
	const store = loadContentStore();
	const record = store[params.slug];
	if (!record) return { saved: false, platform: params.platform, error: "Not found" };

	const existing = record.platforms[params.platform] ?? {
		platform: params.platform,
		content: "",
		published: false,
		published_at: null,
		external_id: "",
	};
	existing.content = params.content;
	record.platforms[params.platform] = existing;
	saveContentStore(store);
	return { saved: true, platform: params.platform };
}

export async function updateStatus(params: {
	slug: string;
	status: string;
}): Promise<{ saved: boolean; error?: string }> {
	const updated = updateContentRecord(params.slug, {
		status: params.status as "draft" | "review" | "ready" | "published" | "archived",
	});
	if (!updated) return { saved: false, error: `Content "${params.slug}" not found` };
	return { saved: true };
}

export async function createContent(params: {
	title: string;
	body: string;
	content_type: string;
	tags?: string[];
}): Promise<{ slug: string; created: boolean }> {
	const store = loadContentStore();
	const baseSlug = params.title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "")
		.slice(0, 60);

	let slug = baseSlug;
	let counter = 1;
	while (store[slug]) {
		slug = `${baseSlug}-${counter}`;
		counter++;
	}

	const now = new Date().toISOString();
	store[slug] = {
		slug,
		content_type: params.content_type as "weekly" | "thematic" | "reading_list" | "digest" | "daily_social" | "seed" | "journal",
		title: params.title,
		body: params.body,
		status: "draft",
		created_at: now,
		source_dates: [],
		tags: params.tags ?? [],
		images: [],
		platforms: {},
		chat_history: [],
		metadata: {},
		file_path: "",
	};

	saveContentStore(store);
	return { slug, created: true };
}
```

**Step 4: Run tests — verify they pass**

```bash
cd web && bun test server/__tests__/tools-content.test.ts
```

Expected: all pass

**Step 5: Commit**

```bash
cd web && git add server/tools/content.ts server/__tests__/tools-content.test.ts
git commit -m "feat: extract content tools to server/tools/content.ts"
```

---

### Task 3: Pipeline Tools Module

**Files:**
- Create: `web/server/tools/pipeline.ts`
- Test: `web/server/__tests__/tools-pipeline.test.ts`

Pipeline tools shell out to `uv run python -m distill <command>`. They read `PROJECT_DIR` and `OUTPUT_DIR` from server config and map optional `project` param to a project directory from `.distill.toml`.

**Step 1: Write tests**

Create `web/server/__tests__/tools-pipeline.test.ts`:

```typescript
import { afterAll, beforeAll, describe, expect, mock, test } from "bun:test";
import { setConfig, resetConfig } from "../lib/config.js";

describe("Pipeline tools", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: "/tmp/distill-test-output",
			PORT: 6109,
			PROJECT_DIR: "/tmp/distill-test-project",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("runPipeline builds correct command", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("run", {});
		expect(cmd).toContain("uv");
		expect(cmd).toContain("run");
		expect(cmd).toContain("--output");
		expect(cmd).toContain("/tmp/distill-test-output");
	});

	test("runPipeline includes project dir", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("run", {});
		expect(cmd).toContain("--dir");
		expect(cmd).toContain("/tmp/distill-test-project");
	});

	test("runJournal builds correct command with date", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("journal", { date: "2026-02-21" });
		expect(cmd).toContain("journal");
		expect(cmd).toContain("--date");
		expect(cmd).toContain("2026-02-21");
	});

	test("runBlog builds correct command with type", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("blog", { type: "weekly" });
		expect(cmd).toContain("blog");
		expect(cmd).toContain("--type");
		expect(cmd).toContain("weekly");
	});

	test("runIntake builds correct command", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("intake", { use_defaults: true });
		expect(cmd).toContain("intake");
		expect(cmd).toContain("--use-defaults");
	});

	test("addSeed builds correct command", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("seed", { text: "My idea", tags: "ai,tools" });
		expect(cmd).toContain("seed");
		expect(cmd).toContain("My idea");
		expect(cmd).toContain("--tags");
	});

	test("addNote builds correct command", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("note", {
			text: "Focus on X",
			target: "week:2026-W08",
		});
		expect(cmd).toContain("note");
		expect(cmd).toContain("Focus on X");
		expect(cmd).toContain("--target");
	});

	test("skip flags are applied", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("run", {
			skip_journal: true,
			skip_blog: true,
		});
		expect(cmd).toContain("--skip-journal");
		expect(cmd).toContain("--skip-blog");
		expect(cmd).not.toContain("--skip-intake");
	});
});
```

**Step 2: Run tests — verify they fail**

```bash
cd web && bun test server/__tests__/tools-pipeline.test.ts
```

Expected: FAIL (module not found)

**Step 3: Implement pipeline tools**

Create `web/server/tools/pipeline.ts`:

```typescript
/**
 * Pipeline tools — shell out to `uv run python -m distill <command>`.
 *
 * Each tool builds a CLI command, executes it via Bun subprocess,
 * and returns stdout/stderr to the agent.
 */
import { getConfig } from "../lib/config.js";

/**
 * Build the command array for a distill CLI invocation.
 * Exported for testing — the actual tools call execPipeline().
 */
export function buildPipelineCommand(
	command: string,
	params: Record<string, unknown>,
): string[] {
	const config = getConfig();
	const args = ["uv", "run", "python", "-m", "distill", command];

	// Common flags
	if (config.OUTPUT_DIR) {
		args.push("--output", config.OUTPUT_DIR);
	}
	if (config.PROJECT_DIR && ["run", "journal", "analyze"].includes(command)) {
		args.push("--dir", config.PROJECT_DIR);
	}

	// Command-specific flags
	switch (command) {
		case "run":
			if (params.skip_journal) args.push("--skip-journal");
			if (params.skip_intake) args.push("--skip-intake");
			if (params.skip_blog) args.push("--skip-blog");
			if (params.force) args.push("--force");
			break;

		case "journal":
			if (params.date) args.push("--date", String(params.date));
			if (params.since) args.push("--since", String(params.since));
			if (params.force) args.push("--force");
			args.push("--global");
			break;

		case "blog":
			if (params.type) args.push("--type", String(params.type));
			if (params.week) args.push("--week", String(params.week));
			if (params.force) args.push("--force");
			break;

		case "intake":
			if (params.use_defaults) args.push("--use-defaults");
			if (params.sources) args.push("--sources", String(params.sources));
			break;

		case "seed":
			if (params.text) args.push(String(params.text));
			if (params.tags) args.push("--tags", String(params.tags));
			break;

		case "note":
			if (params.text) args.push(String(params.text));
			if (params.target) args.push("--target", String(params.target));
			break;
	}

	return args;
}

/**
 * Execute a distill pipeline command and return stdout/stderr.
 */
async function execPipeline(
	command: string,
	params: Record<string, unknown>,
): Promise<{ success: boolean; output: string; error?: string }> {
	const args = buildPipelineCommand(command, params);

	try {
		const proc = Bun.spawn(args, {
			stdout: "pipe",
			stderr: "pipe",
			cwd: process.cwd(),
		});

		const stdout = await new Response(proc.stdout).text();
		const stderr = await new Response(proc.stderr).text();
		const exitCode = await proc.exited;

		if (exitCode !== 0) {
			return {
				success: false,
				output: stdout,
				error: stderr || `Process exited with code ${exitCode}`,
			};
		}
		return { success: true, output: stdout || "Command completed successfully." };
	} catch (err) {
		return {
			success: false,
			output: "",
			error: err instanceof Error ? err.message : "Unknown error",
		};
	}
}

export async function runPipeline(params: {
	project?: string;
	skip_journal?: boolean;
	skip_intake?: boolean;
	skip_blog?: boolean;
}): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("run", params);
}

export async function runJournal(params: {
	project?: string;
	date?: string;
	since?: string;
	force?: boolean;
}): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("journal", params);
}

export async function runBlog(params: {
	project?: string;
	type?: string;
	week?: string;
	force?: boolean;
}): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("blog", params);
}

export async function runIntake(params: {
	project?: string;
	sources?: string;
	use_defaults?: boolean;
}): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("intake", params);
}

export async function addSeed(params: {
	text: string;
	tags?: string;
}): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("seed", params);
}

export async function addNote(params: {
	text: string;
	target?: string;
}): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("note", params);
}
```

**Step 4: Run tests — verify they pass**

```bash
cd web && bun test server/__tests__/tools-pipeline.test.ts
```

Expected: all pass

**Step 5: Commit**

```bash
cd web && git add server/tools/pipeline.ts server/__tests__/tools-pipeline.test.ts
git commit -m "feat: add pipeline tools (shell out to distill CLI)"
```

---

### Task 4: Research Tools Module

**Files:**
- Create: `web/server/tools/research.ts`
- Test: `web/server/__tests__/tools-research.test.ts`

**Step 1: Write tests**

Create `web/server/__tests__/tools-research.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";

describe("Research tools", () => {
	test("extractReadableText strips HTML to text", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const html = `
			<html><body>
				<nav>Menu stuff</nav>
				<article>
					<h1>Article Title</h1>
					<p>First paragraph of content.</p>
					<p>Second paragraph.</p>
				</article>
				<footer>Footer stuff</footer>
			</body></html>
		`;
		const text = extractReadableText(html);
		expect(text).toContain("Article Title");
		expect(text).toContain("First paragraph");
	});

	test("extractReadableText handles plain text gracefully", async () => {
		const { extractReadableText } = await import("../tools/research.js");
		const text = extractReadableText("Just plain text, no HTML");
		expect(text).toContain("Just plain text");
	});
});
```

**Step 2: Run tests — verify they fail**

```bash
cd web && bun test server/__tests__/tools-research.test.ts
```

**Step 3: Implement research tools**

Create `web/server/tools/research.ts`:

```typescript
/**
 * Research tools — fetch URLs and optionally save to intake.
 */
import * as cheerio from "cheerio";
import { loadContentStore, saveContentStore } from "../lib/content-store.js";

/**
 * Extract readable text content from HTML.
 * Prefers <article>, <main>, or <body> content.
 * Strips nav, header, footer, script, style elements.
 */
export function extractReadableText(html: string): string {
	const $ = cheerio.load(html);

	// Remove non-content elements
	$("script, style, nav, header, footer, aside, [role='navigation'], [role='banner']").remove();

	// Prefer article or main content
	const article = $("article").text().trim();
	if (article.length > 100) return article;

	const main = $("main").text().trim();
	if (main.length > 100) return main;

	return $("body").text().trim() || html;
}

export async function fetchUrl(params: {
	url: string;
}): Promise<{ title: string; text: string; url: string; error?: string }> {
	try {
		const response = await fetch(params.url, {
			headers: {
				"User-Agent": "Distill/1.0 (content research tool)",
				Accept: "text/html, application/json, text/plain",
			},
			redirect: "follow",
		});

		if (!response.ok) {
			return {
				title: "",
				text: "",
				url: params.url,
				error: `HTTP ${response.status}: ${response.statusText}`,
			};
		}

		const contentType = response.headers.get("content-type") ?? "";
		const body = await response.text();

		if (contentType.includes("text/html")) {
			const $ = cheerio.load(body);
			const title = $("title").text().trim() || $("h1").first().text().trim() || params.url;
			const text = extractReadableText(body);
			return { title, text: text.slice(0, 50000), url: params.url };
		}

		// JSON or plain text
		return {
			title: params.url,
			text: body.slice(0, 50000),
			url: params.url,
		};
	} catch (err) {
		return {
			title: "",
			text: "",
			url: params.url,
			error: err instanceof Error ? err.message : "Fetch failed",
		};
	}
}

export async function saveToIntake(params: {
	url: string;
	tags?: string[];
	notes?: string;
}): Promise<{ saved: boolean; slug: string; title: string; error?: string }> {
	const fetched = await fetchUrl({ url: params.url });
	if (fetched.error) {
		return { saved: false, slug: "", title: "", error: fetched.error };
	}

	// Save as a new ContentStore record
	const store = loadContentStore();
	const baseSlug = fetched.title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "")
		.slice(0, 60);

	let slug = baseSlug || "research";
	let counter = 1;
	while (store[slug]) {
		slug = `${baseSlug}-${counter}`;
		counter++;
	}

	const body = params.notes
		? `${params.notes}\n\n---\n\nSource: ${params.url}\n\n${fetched.text}`
		: `Source: ${params.url}\n\n${fetched.text}`;

	const now = new Date().toISOString();
	store[slug] = {
		slug,
		content_type: "digest",
		title: fetched.title,
		body,
		status: "draft",
		created_at: now,
		source_dates: [now.split("T")[0] ?? now],
		tags: params.tags ?? ["research"],
		images: [],
		platforms: {},
		chat_history: [],
		metadata: { source_url: params.url },
		file_path: "",
	};

	saveContentStore(store);
	return { saved: true, slug, title: fetched.title };
}
```

**Step 4: Run tests — verify they pass**

```bash
cd web && bun test server/__tests__/tools-research.test.ts
```

**Step 5: Commit**

```bash
cd web && git add server/tools/research.ts server/__tests__/tools-research.test.ts
git commit -m "feat: add research tools (fetch URL, save to intake)"
```

---

### Task 5: Publishing Tools Module

**Files:**
- Create: `web/server/tools/publishing.ts`
- Test: `web/server/__tests__/tools-publishing.test.ts`

**Step 1: Write tests**

Create `web/server/__tests__/tools-publishing.test.ts`:

```typescript
import { afterAll, beforeAll, describe, expect, mock, test } from "bun:test";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { setConfig, resetConfig } from "../lib/config.js";
import { saveContentStore } from "../lib/content-store.js";
import type { ContentStoreData } from "../lib/content-store.js";

const FIXTURES = join(import.meta.dir, "fixtures");

function seedStore(): void {
	const store: ContentStoreData = {
		"pub-test": {
			slug: "pub-test",
			content_type: "weekly",
			title: "Publish Test",
			body: "# Content",
			status: "ready",
			created_at: "2026-02-21T00:00:00Z",
			source_dates: [],
			tags: [],
			images: [],
			platforms: {
				ghost: {
					platform: "ghost",
					content: "Ghost adapted",
					published: false,
					published_at: null,
					external_id: "",
				},
			},
			chat_history: [],
			metadata: {},
			file_path: "",
		},
	};
	saveContentStore(store);
}

describe("Publishing tools", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
		mkdirSync(FIXTURES, { recursive: true });
		seedStore();
	});

	afterAll(() => {
		resetConfig();
	});

	test("checkPublishReady returns error when Postiz not configured", async () => {
		const { publishContent } = await import("../tools/publishing.js");
		const result = await publishContent({
			slug: "pub-test",
			platforms: ["ghost"],
			mode: "draft",
		});
		expect(result.error).toContain("not configured");
	});

	test("listPostizIntegrations returns error when not configured", async () => {
		const { listPostizIntegrations } = await import("../tools/publishing.js");
		const result = await listPostizIntegrations();
		expect(result.configured).toBe(false);
	});
});
```

**Step 2: Run tests — verify they fail**

```bash
cd web && bun test server/__tests__/tools-publishing.test.ts
```

**Step 3: Implement publishing tools**

Create `web/server/tools/publishing.ts`:

```typescript
/**
 * Publishing tools — manage Postiz publishing and scheduling.
 */
import { getContentRecord, loadContentStore, saveContentStore } from "../lib/content-store.js";
import { createPost, isPostizConfigured, listIntegrations } from "../lib/postiz.js";

const PLATFORM_PROVIDER_MAP: Record<string, string> = {
	x: "x",
	linkedin: "linkedin",
	slack: "slack",
};

export async function listPostizIntegrations(): Promise<{
	configured: boolean;
	integrations: Array<{ id: string; name: string; provider: string }>;
}> {
	if (!isPostizConfigured()) {
		return { configured: false, integrations: [] };
	}
	try {
		const integrations = await listIntegrations();
		return { configured: true, integrations };
	} catch {
		return { configured: false, integrations: [] };
	}
}

export async function publishContent(params: {
	slug: string;
	platforms: string[];
	mode: string;
	scheduled_at?: string;
}): Promise<{
	results: Array<{ platform: string; success: boolean; error?: string }>;
	error?: string;
}> {
	if (!isPostizConfigured()) {
		return { results: [], error: "Postiz not configured" };
	}

	const record = getContentRecord(params.slug);
	if (!record) {
		return { results: [], error: `Content "${params.slug}" not found` };
	}

	let integrations: Awaited<ReturnType<typeof listIntegrations>> = [];
	try {
		integrations = await listIntegrations();
	} catch {
		return { results: [], error: "Failed to fetch Postiz integrations" };
	}

	const results: Array<{ platform: string; success: boolean; error?: string }> = [];
	const store = loadContentStore();
	const liveRecord = store[params.slug];
	if (!liveRecord) return { results: [], error: "Record not found in store" };

	for (const platform of params.platforms) {
		const entry = liveRecord.platforms[platform];
		if (!entry?.content) {
			results.push({ platform, success: false, error: "No adapted content" });
			continue;
		}
		if (entry.published) {
			results.push({ platform, success: false, error: "Already published" });
			continue;
		}

		const provider = PLATFORM_PROVIDER_MAP[platform] ?? platform;
		const integration = integrations.find((i) => i.provider.includes(provider));
		if (!integration) {
			results.push({ platform, success: false, error: `No Postiz integration for ${platform}` });
			continue;
		}

		try {
			await createPost(entry.content, [integration.id], {
				postType: params.mode,
				scheduledAt: params.scheduled_at,
			});
			entry.published = true;
			entry.published_at = new Date().toISOString();
			results.push({ platform, success: true });
		} catch (err) {
			results.push({
				platform,
				success: false,
				error: err instanceof Error ? err.message : "Unknown error",
			});
		}
	}

	saveContentStore(store);
	return { results };
}

export async function listPostizPosts(params: {
	status?: string;
	limit?: number;
}): Promise<{ posts: unknown[]; error?: string }> {
	if (!isPostizConfigured()) {
		return { posts: [], error: "Postiz not configured" };
	}

	// Postiz API: GET /posts — not currently in postiz.ts, so we call it directly
	try {
		const { getConfig } = await import("../lib/config.js");
		const config = getConfig();
		const url = `${config.POSTIZ_URL.replace(/\/$/, "")}/posts`;
		const resp = await fetch(url, {
			headers: {
				Authorization: config.POSTIZ_API_KEY,
				Accept: "application/json",
			},
		});
		if (!resp.ok) return { posts: [], error: `Postiz API: ${resp.status}` };
		const data = await resp.json();
		const posts = Array.isArray(data) ? data : (data as Record<string, unknown>).posts ?? [];
		return { posts: (posts as unknown[]).slice(0, params.limit ?? 20) };
	} catch (err) {
		return { posts: [], error: err instanceof Error ? err.message : "Failed" };
	}
}
```

**Step 4: Run tests — verify they pass**

```bash
cd web && bun test server/__tests__/tools-publishing.test.ts
```

**Step 5: Commit**

```bash
cd web && git add server/tools/publishing.ts server/__tests__/tools-publishing.test.ts
git commit -m "feat: add publishing tools (Postiz publish, schedule, list)"
```

---

### Task 6: Extract Image Tools

**Files:**
- Create: `web/server/tools/images.ts`
- Modify: `web/server/routes/studio.ts` (remove inline generateImage, import from tools)

This is a thin re-export wrapper so images.ts follows the same pattern as other tool modules.

**Step 1: Create image tools module**

Create `web/server/tools/images.ts`:

```typescript
/**
 * Image generation tool — wraps server/lib/images.ts.
 */
import { getConfig } from "../lib/config.js";
import { generateImage as generate, isImageConfigured } from "../lib/images.js";
import { loadContentStore, saveContentStore } from "../lib/content-store.js";

export { isImageConfigured } from "../lib/images.js";

export async function generateImage(params: {
	prompt: string;
	mood: string;
	slug?: string;
}): Promise<{ url?: string; alt?: string; mood?: string; error?: string }> {
	const config = getConfig();
	const imageResult = await generate(params.prompt, {
		outputDir: config.OUTPUT_DIR,
		mood: params.mood,
		slug: params.slug ?? "studio",
	});

	if (!imageResult) {
		return { error: "Image generation not available or failed" };
	}

	// Save to ContentStore if slug provided
	if (params.slug) {
		const store = loadContentStore();
		const record = store[params.slug];
		if (record) {
			record.images.push({
				filename: imageResult.filename,
				role: "hero",
				prompt: params.prompt,
				relative_path: imageResult.relativePath,
			});
			saveContentStore(store);
		}
	}

	return {
		url: `/api/studio/images/${imageResult.relativePath}`,
		alt: params.prompt,
		mood: params.mood,
	};
}
```

**Step 2: Verify build**

```bash
cd web && bun run check
```

**Step 3: Commit**

```bash
cd web && git add server/tools/images.ts
git commit -m "feat: extract image tool to server/tools/images.ts"
```

---

### Task 7: Refactor Studio Chat to Use Tool Modules

**Files:**
- Modify: `web/server/routes/studio.ts`

Replace the ~120 lines of inline tool definitions with imports from `server/tools/*`. The chat endpoint becomes a thin orchestrator.

**Step 1: Refactor studio.ts chat endpoint**

Replace the tools section (lines ~602-705) in `POST /api/studio/chat` with:

```typescript
import { tool } from "ai";
import { z } from "zod";
import { updateSource, savePlatform, listContent, getContent, updateStatus, createContent } from "../tools/content.js";
import { runPipeline, runJournal, runBlog, runIntake, addSeed, addNote } from "../tools/pipeline.js";
import { fetchUrl, saveToIntake } from "../tools/research.js";
import { publishContent, listPostizIntegrations, listPostizPosts } from "../tools/publishing.js";
import { generateImage as generateImageTool, isImageConfigured } from "../tools/images.js";

// Inside the chat endpoint, replace the inline tools object with:
tools: {
	// --- Content ---
	updateSourceContent: tool({
		description: "Update the original source post. Call when the author asks to edit/rewrite the source notes.",
		inputSchema: z.object({
			content: z.string().describe("Full updated source content (markdown)"),
			title: z.string().optional().describe("Updated title, if changed"),
		}),
		execute: async (params) => updateSource({ slug: slug ?? "", ...params }),
	}),
	savePlatformContent: tool({
		description: "Save adapted content for the target platform. Call every time you write or revise platform content.",
		inputSchema: z.object({
			content: z.string().describe("Full adapted content for the platform"),
		}),
		execute: async ({ content: c }) => savePlatform({ slug: slug ?? "", platform, content: c }),
	}),
	listContent: tool({
		description: "List all content items in the studio. Use to browse available posts.",
		inputSchema: z.object({
			type: z.string().optional().describe("Filter by type: weekly, thematic, journal, etc."),
			status: z.string().optional().describe("Filter by status: draft, review, ready, published"),
		}),
		execute: async (params) => listContent(params),
	}),
	getContent: tool({
		description: "Get full content record by slug.",
		inputSchema: z.object({ slug: z.string() }),
		execute: async (params) => getContent(params),
	}),
	updateStatus: tool({
		description: "Change content status (draft, review, ready, published, archived).",
		inputSchema: z.object({
			slug: z.string(),
			status: z.enum(["draft", "review", "ready", "published", "archived"]),
		}),
		execute: async (params) => updateStatus(params),
	}),
	createContent: tool({
		description: "Create a new content item in the studio.",
		inputSchema: z.object({
			title: z.string(),
			body: z.string(),
			content_type: z.enum(["weekly", "thematic", "journal", "digest", "seed"]),
			tags: z.array(z.string()).optional(),
		}),
		execute: async (params) => createContent(params),
	}),

	// --- Pipeline ---
	runPipeline: tool({
		description: "Run the full distill pipeline: sessions → journal → intake → blog. Takes a few minutes.",
		inputSchema: z.object({
			project: z.string().optional().describe("Project name from .distill.toml"),
			skip_journal: z.boolean().optional(),
			skip_intake: z.boolean().optional(),
			skip_blog: z.boolean().optional(),
		}),
		execute: async (params) => runPipeline(params),
	}),
	runJournal: tool({
		description: "Generate journal entries from coding sessions.",
		inputSchema: z.object({
			project: z.string().optional(),
			date: z.string().optional().describe("Specific date (YYYY-MM-DD)"),
			since: z.string().optional().describe("Generate since this date"),
			force: z.boolean().optional(),
		}),
		execute: async (params) => runJournal(params),
	}),
	runBlog: tool({
		description: "Generate blog posts from journal entries.",
		inputSchema: z.object({
			project: z.string().optional(),
			type: z.enum(["weekly", "thematic", "all"]).optional(),
			week: z.string().optional().describe("Specific week (e.g., 2026-W08)"),
			force: z.boolean().optional(),
		}),
		execute: async (params) => runBlog(params),
	}),
	runIntake: tool({
		description: "Run content ingestion from RSS feeds, browser history, etc.",
		inputSchema: z.object({
			project: z.string().optional(),
			sources: z.string().optional().describe("Comma-separated source names"),
			use_defaults: z.boolean().optional(),
		}),
		execute: async (params) => runIntake(params),
	}),
	addSeed: tool({
		description: "Add a seed idea to the pipeline for future blog posts.",
		inputSchema: z.object({
			text: z.string().describe("The seed idea"),
			tags: z.string().optional().describe("Comma-separated tags"),
		}),
		execute: async (params) => addSeed(params),
	}),
	addNote: tool({
		description: "Add an editorial note to steer content direction.",
		inputSchema: z.object({
			text: z.string().describe("The editorial note"),
			target: z.string().optional().describe("Target (e.g., 'week:2026-W08')"),
		}),
		execute: async (params) => addNote(params),
	}),

	// --- Research ---
	fetchUrl: tool({
		description: "Fetch a URL and extract readable text. Use to read articles, papers, or documentation.",
		inputSchema: z.object({
			url: z.string().url().describe("URL to fetch"),
		}),
		execute: async (params) => fetchUrl(params),
	}),
	saveToIntake: tool({
		description: "Fetch a URL and save the content to the intake pipeline for future synthesis.",
		inputSchema: z.object({
			url: z.string().url().describe("URL to fetch and save"),
			tags: z.array(z.string()).optional(),
			notes: z.string().optional().describe("Your notes about why this is interesting"),
		}),
		execute: async (params) => saveToIntake(params),
	}),

	// --- Publishing ---
	listIntegrations: tool({
		description: "List connected Postiz platform integrations.",
		inputSchema: z.object({}),
		execute: async () => listPostizIntegrations(),
	}),
	publish: tool({
		description: "Publish content to social platforms via Postiz.",
		inputSchema: z.object({
			slug: z.string(),
			platforms: z.array(z.string()).describe("Platform names: x, linkedin, slack, ghost"),
			mode: z.enum(["draft", "schedule", "now"]),
			scheduled_at: z.string().optional().describe("ISO datetime for scheduled posts"),
		}),
		execute: async (params) => publishContent(params),
	}),
	listPosts: tool({
		description: "List recent and upcoming posts from Postiz.",
		inputSchema: z.object({
			status: z.string().optional(),
			limit: z.number().optional(),
		}),
		execute: async (params) => listPostizPosts(params),
	}),

	// --- Images ---
	generateImage: tool({
		description: "Generate a hero image for content.",
		inputSchema: z.object({
			prompt: z.string().describe("Visual metaphor — describe the scene, not the article topic"),
			mood: z.enum(["reflective", "energetic", "cautionary", "triumphant", "intimate", "technical", "playful", "somber"]),
		}),
		execute: async (params) => generateImageTool({ ...params, slug: slug ?? undefined }),
	}),
},
```

Also update the system prompt to describe all available tools.

**Step 2: Verify build and tests**

```bash
cd web && bun run check
cd web && bun test server
```

Expected: tsc clean, biome clean, all existing tests pass

**Step 3: Commit**

```bash
cd web && git add server/routes/studio.ts
git commit -m "refactor: replace inline chat tools with server/tools/* imports"
```

---

### Task 8: MCP Server

**Files:**
- Create: `web/server/mcp/server.ts`
- Test: `web/server/__tests__/mcp-server.test.ts`

**Step 1: Write tests**

Create `web/server/__tests__/mcp-server.test.ts`:

```typescript
import { describe, expect, test } from "bun:test";

describe("MCP server", () => {
	test("createMcpServer returns a server with tools registered", async () => {
		const { createMcpServer } = await import("../mcp/server.js");
		const server = createMcpServer();
		expect(server).toBeDefined();
	});
});
```

**Step 2: Implement MCP server**

Create `web/server/mcp/server.ts`:

```typescript
/**
 * MCP Server — exposes distill tools over Model Context Protocol.
 *
 * Used by Claude Code CLI and external agents via stdio transport.
 * Wraps the same tool functions used by Studio chat.
 */
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { listContent, getContent, updateSource, savePlatform, updateStatus, createContent } from "../tools/content.js";
import { runPipeline, runJournal, runBlog, runIntake, addSeed, addNote } from "../tools/pipeline.js";
import { fetchUrl, saveToIntake } from "../tools/research.js";
import { publishContent, listPostizIntegrations, listPostizPosts } from "../tools/publishing.js";
import { generateImage, isImageConfigured } from "../tools/images.js";

export function createMcpServer(): McpServer {
	const server = new McpServer({
		name: "distill",
		version: "1.0.0",
	});

	// --- Content ---
	server.registerTool("list_content", {
		description: "List all content items in the studio.",
		inputSchema: { type: z.string().optional(), status: z.string().optional() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await listContent(params)) }],
	}));

	server.registerTool("get_content", {
		description: "Get full content record by slug.",
		inputSchema: { slug: z.string() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await getContent(params)) }],
	}));

	server.registerTool("update_source", {
		description: "Update the source post content.",
		inputSchema: { slug: z.string(), content: z.string(), title: z.string().optional() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await updateSource(params)) }],
	}));

	server.registerTool("save_platform", {
		description: "Save adapted content for a platform.",
		inputSchema: { slug: z.string(), platform: z.string(), content: z.string() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await savePlatform(params)) }],
	}));

	server.registerTool("update_status", {
		description: "Change content status.",
		inputSchema: { slug: z.string(), status: z.enum(["draft", "review", "ready", "published", "archived"]) },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await updateStatus(params)) }],
	}));

	server.registerTool("create_content", {
		description: "Create a new content item.",
		inputSchema: { title: z.string(), body: z.string(), content_type: z.string(), tags: z.array(z.string()).optional() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await createContent(params)) }],
	}));

	// --- Pipeline ---
	server.registerTool("run_pipeline", {
		description: "Run the full distill pipeline (sessions → journal → intake → blog).",
		inputSchema: {
			project: z.string().optional(),
			skip_journal: z.boolean().optional(),
			skip_intake: z.boolean().optional(),
			skip_blog: z.boolean().optional(),
		},
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await runPipeline(params)) }],
	}));

	server.registerTool("run_journal", {
		description: "Generate journal entries from coding sessions.",
		inputSchema: {
			project: z.string().optional(),
			date: z.string().optional(),
			since: z.string().optional(),
			force: z.boolean().optional(),
		},
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await runJournal(params)) }],
	}));

	server.registerTool("run_blog", {
		description: "Generate blog posts from journal entries.",
		inputSchema: {
			project: z.string().optional(),
			type: z.string().optional(),
			week: z.string().optional(),
			force: z.boolean().optional(),
		},
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await runBlog(params)) }],
	}));

	server.registerTool("run_intake", {
		description: "Run content ingestion from feeds and sources.",
		inputSchema: {
			project: z.string().optional(),
			sources: z.string().optional(),
			use_defaults: z.boolean().optional(),
		},
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await runIntake(params)) }],
	}));

	server.registerTool("add_seed", {
		description: "Add a seed idea to the pipeline.",
		inputSchema: { text: z.string(), tags: z.string().optional() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await addSeed(params)) }],
	}));

	server.registerTool("add_note", {
		description: "Add an editorial steering note.",
		inputSchema: { text: z.string(), target: z.string().optional() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await addNote(params)) }],
	}));

	// --- Research ---
	server.registerTool("fetch_url", {
		description: "Fetch a URL and extract readable text content.",
		inputSchema: { url: z.string() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await fetchUrl(params)) }],
	}));

	server.registerTool("save_to_intake", {
		description: "Fetch a URL and save it to the intake pipeline for future synthesis.",
		inputSchema: { url: z.string(), tags: z.array(z.string()).optional(), notes: z.string().optional() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await saveToIntake(params)) }],
	}));

	// --- Publishing ---
	server.registerTool("list_integrations", {
		description: "List connected Postiz platform integrations.",
		inputSchema: {},
	}, async () => ({
		content: [{ type: "text", text: JSON.stringify(await listPostizIntegrations()) }],
	}));

	server.registerTool("publish", {
		description: "Publish content to social platforms via Postiz.",
		inputSchema: {
			slug: z.string(),
			platforms: z.array(z.string()),
			mode: z.enum(["draft", "schedule", "now"]),
			scheduled_at: z.string().optional(),
		},
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await publishContent(params)) }],
	}));

	server.registerTool("list_posts", {
		description: "List recent/upcoming posts from Postiz.",
		inputSchema: { status: z.string().optional(), limit: z.number().optional() },
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await listPostizPosts(params)) }],
	}));

	// --- Images ---
	server.registerTool("generate_image", {
		description: "Generate a hero image for content using AI.",
		inputSchema: {
			prompt: z.string(),
			mood: z.enum(["reflective", "energetic", "cautionary", "triumphant", "intimate", "technical", "playful", "somber"]),
			slug: z.string().optional(),
		},
	}, async (params) => ({
		content: [{ type: "text", text: JSON.stringify(await generateImage(params)) }],
	}));

	return server;
}

/**
 * Start MCP server over stdio.
 * Called by `distill mcp` CLI command.
 */
export async function startMcpServer(): Promise<void> {
	const server = createMcpServer();
	const transport = new StdioServerTransport();
	await server.connect(transport);
}

// Run directly: bun server/mcp/server.ts
if (import.meta.main) {
	startMcpServer().catch(console.error);
}
```

**Step 3: Run tests and build**

```bash
cd web && bun test server/__tests__/mcp-server.test.ts
cd web && bun run check
```

**Step 4: Commit**

```bash
cd web && git add server/mcp/server.ts server/__tests__/mcp-server.test.ts
git commit -m "feat: add MCP server exposing all distill tools over stdio"
```

---

### Task 9: CLI `distill mcp` Command

**Files:**
- Modify: `src/cli.py`

Add a `mcp` command that spawns the MCP server process over stdio.

**Step 1: Add the command**

In `src/cli.py`, add:

```python
@app.command()
def mcp(
    output: str = typer.Option("./insights", "--output", "-o", help="Output directory"),
):
    """Start the MCP server for external agent access to distill tools."""
    import subprocess
    import sys

    env = {
        **dict(os.environ),
        "OUTPUT_DIR": str(Path(output).resolve()),
    }

    # Check if PROJECT_DIR should be set from config
    try:
        from distill.config import load_config
        config = load_config()
        if config.project_dir:
            env["PROJECT_DIR"] = str(config.project_dir)
    except Exception:
        pass

    server_path = Path(__file__).parent.parent / "web" / "server" / "mcp" / "server.ts"
    subprocess.run(
        ["bun", str(server_path)],
        env=env,
        stdin=sys.stdin,
        stdout=sys.stdout,
        stderr=sys.stderr,
    )
```

**Step 2: Test it starts**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | uv run python -m distill mcp --output ./insights 2>/dev/null | head -c 500
```

Expected: JSON-RPC response with server info

**Step 3: Commit**

```bash
git add src/cli.py
git commit -m "feat: add distill mcp command for external agent access"
```

---

### Task 10: Update System Prompt & Frontend Tool Handlers

**Files:**
- Modify: `web/server/routes/studio.ts` (system prompt)
- Modify: `web/src/components/studio/AgentChat.tsx` (tool result chips for new tools)

**Step 1: Update system prompt**

The system prompt in the chat endpoint should mention all available tools:

```typescript
const systemPrompt = `${platformPrompt}

Here are the author's source notes to work with:

---
${content}
---

You are a powerful content assistant with full access to the distill platform. You can:

**Content:** Update the source post, save platform content, list/get/create content items, change status.
**Pipeline:** Run the full pipeline, journal, blog, or intake individually. Add seeds and editorial notes.
**Research:** Fetch any URL to read articles/papers. Save interesting links to the intake pipeline.
**Publishing:** List Postiz integrations, publish to platforms, schedule posts, view recent posts.
${isImageConfigured() ? "**Images:** Generate hero images with mood-based styles." : ""}

When you write or revise content for the platform, call savePlatformContent.
When editing the source post, call updateSourceContent with the FULL updated content.
Be a thoughtful collaborator — ask questions, suggest angles, explain your choices.`;
```

**Step 2: Add tool result chips in AgentChat**

Add visual indicators for pipeline, research, and publish tool calls. In the `msg.parts.map` rendering section, add handlers for the new tool types. Use a generic "action completed" chip pattern:

```tsx
// Generic tool result chip for pipeline/research/publish tools
const TOOL_LABELS: Record<string, { label: string; color: string }> = {
	runPipeline: { label: "Pipeline completed", color: "indigo" },
	runJournal: { label: "Journal generated", color: "indigo" },
	runBlog: { label: "Blog generated", color: "indigo" },
	runIntake: { label: "Intake completed", color: "indigo" },
	addSeed: { label: "Seed added", color: "amber" },
	addNote: { label: "Note added", color: "amber" },
	fetchUrl: { label: "URL fetched", color: "cyan" },
	saveToIntake: { label: "Saved to intake", color: "cyan" },
	publish: { label: "Published", color: "green" },
	listContent: { label: "Content listed", color: "zinc" },
	createContent: { label: "Content created", color: "green" },
};
```

Render these as small chips similar to the existing "Content saved to ghost" chip.

**Step 3: Verify build and tests**

```bash
cd web && bun run check
cd web && bun test server
cd web && npx vitest run
```

**Step 4: Commit**

```bash
cd web && git add server/routes/studio.ts src/components/studio/AgentChat.tsx
git commit -m "feat: update system prompt and add tool result chips for all tools"
```

---

### Task 11: Build Verification

**Step 1: Type check**

```bash
cd web && npx tsc --noEmit
```

Expected: 0 errors

**Step 2: Lint**

```bash
cd web && npx @biomejs/biome check src/ server/ shared/
```

Expected: 0 errors

**Step 3: All server tests**

```bash
cd web && bun test server
```

Expected: all pass (126 existing + new tool tests)

**Step 4: All frontend tests**

```bash
cd web && npx vitest run
```

Expected: 25 pass

**Step 5: Smoke test MCP server**

```bash
echo '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"test","version":"1.0"}}}' | OUTPUT_DIR=./insights bun web/server/mcp/server.ts 2>/dev/null | head -c 500
```

Expected: JSON-RPC response with server capabilities and 18 tools listed

**Step 6: Smoke test Studio chat**

Start dev server, open Studio, send "list all my content" — should call `listContent` tool and return results.
