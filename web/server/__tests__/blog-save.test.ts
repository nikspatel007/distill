import { afterAll, afterEach, beforeAll, describe, expect, test } from "bun:test";
import { mkdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const FIXTURES = join(import.meta.dir, "fixtures");
const BLOG_DIR = join(FIXTURES, "blog", "weekly");
const BLOG_FILE = join(BLOG_DIR, "weekly-2026-W06.md");

const FIXTURE_CONTENT = `---
title: "Week 6: Building the Pipeline"
slug: weekly-2026-W06
post_type: weekly
generated_at: 2026-02-07T10:00:00Z
source_dates:
  - 2026-02-03
  - 2026-02-04
  - 2026-02-05
  - 2026-02-06
  - 2026-02-07
tags:
  - pipeline
  - architecture
---

# Week 6: Building the Pipeline

This week was all about getting the core content pipeline working end to end.`;

describe("PUT /api/blog/posts/:slug", () => {
	beforeAll(async () => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
		// Ensure the fixture directory and file exist (may have been cleaned by other tests)
		await mkdir(BLOG_DIR, { recursive: true });
		await Bun.write(BLOG_FILE, FIXTURE_CONTENT);
	});

	afterEach(async () => {
		// Restore the fixture after each test modifies it
		await mkdir(BLOG_DIR, { recursive: true });
		await Bun.write(BLOG_FILE, FIXTURE_CONTENT);
	});

	afterAll(async () => {
		resetConfig();
		// Clean up the directory we created
		await rm(BLOG_DIR, { recursive: true, force: true });
	});

	test("saves updated blog content", async () => {
		const res = await app.request("/api/blog/posts/weekly-2026-W06", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "# Updated Blog Post\n\nNew blog content." }),
		});
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.success).toBe(true);

		const updated = await readFile(BLOG_FILE, "utf-8");
		expect(updated).toContain("# Updated Blog Post");
		expect(updated).toContain("New blog content.");
		expect(updated).toContain("slug: weekly-2026-W06");
		expect(updated).toContain("post_type: weekly");
	});

	test("returns 404 for nonexistent slug", async () => {
		const res = await app.request("/api/blog/posts/does-not-exist", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "test" }),
		});
		expect(res.status).toBe(404);
	});

	test("returns 400 for invalid body", async () => {
		const res = await app.request("/api/blog/posts/weekly-2026-W06", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({}),
		});
		expect(res.status).toBe(400);
	});

	test("preserves frontmatter after save", async () => {
		await app.request("/api/blog/posts/weekly-2026-W06", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "# Edited Post" }),
		});

		const res = await app.request("/api/blog/posts/weekly-2026-W06");
		const data = await res.json();
		expect(data.meta.slug).toBe("weekly-2026-W06");
		expect(data.meta.title).toBe("Week 6: Building the Pipeline");
		expect(data.meta.postType).toBe("weekly");
		expect(data.content).toContain("# Edited Post");
	});
});
