import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdir, mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

let tempDir: string;

beforeEach(async () => {
	tempDir = await mkdtemp(join(tmpdir(), "studio-test-"));
	setConfig({
		OUTPUT_DIR: tempDir,
		PORT: 3001,
		PROJECT_DIR: "",
		POSTIZ_URL: "",
		POSTIZ_API_KEY: "",
	});
});

afterEach(async () => {
	resetConfig();
	await rm(tempDir, { recursive: true, force: true });
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

describe("GET /api/studio/items", () => {
	test("returns empty when no blog files", async () => {
		const res = await app.request("/api/studio/items");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data).toHaveProperty("items");
		expect(data.items).toEqual([]);
	});

	test("returns blog posts as studio items", async () => {
		await setupBlogFiles(tempDir);

		const res = await app.request("/api/studio/items");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.items).toHaveLength(2);

		const weekly = data.items.find((i: { slug: string }) => i.slug === "weekly-2026-W07");
		expect(weekly).toBeDefined();
		expect(weekly.title).toBe("Week 7 Synthesis");
		expect(weekly.type).toBe("weekly");
		expect(weekly.status).toBe("draft");

		const thematic = data.items.find(
			(i: { slug: string }) => i.slug === "agents-outnumber-decisions",
		);
		expect(thematic).toBeDefined();
		expect(thematic.title).toBe("When Agents Outnumber Decisions");
		expect(thematic.type).toBe("thematic");
	});
});

describe("GET /api/studio/items/:slug", () => {
	test("returns 404 for unknown slug", async () => {
		const res = await app.request("/api/studio/items/nonexistent-slug");
		expect(res.status).toBe(404);
	});

	test("returns full content for valid slug", async () => {
		await setupBlogFiles(tempDir);

		const res = await app.request("/api/studio/items/weekly-2026-W07");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.slug).toBe("weekly-2026-W07");
		expect(data.title).toBe("Week 7 Synthesis");
		expect(data.type).toBe("weekly");
		expect(data.content).toContain("week's content here");
		expect(data).toHaveProperty("frontmatter");
		expect(data).toHaveProperty("review");
		expect(data.review.slug).toBe("weekly-2026-W07");
		expect(data.review.type).toBe("weekly");
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
