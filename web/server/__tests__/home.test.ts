import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const TMP_DIR = join(import.meta.dir, "fixtures", "_tmp_home");

describe("GET /api/home/:date", () => {
	beforeAll(async () => {
		// Create directory structure
		const journalDir = join(TMP_DIR, "journal");
		const intakeDir = join(TMP_DIR, "intake");
		const blogDir = join(TMP_DIR, "blog");
		await mkdir(journalDir, { recursive: true });
		await mkdir(intakeDir, { recursive: true });
		await mkdir(blogDir, { recursive: true });

		// Journal with brief in frontmatter
		await writeFile(
			join(journalDir, "journal-2026-02-22-dev-journal.md"),
			[
				"---",
				"date: 2026-02-22",
				"type: journal",
				"style: dev-journal",
				"sessions_count: 3",
				"duration_minutes: 120",
				"tags:",
				"  - typescript",
				"  - testing",
				"projects:",
				"  - distill",
				"brief:",
				"  - Built the daily briefing API endpoint",
				"  - Added home route with aggregated data",
				"  - Fixed publish queue status tracking",
				"created: 2026-02-22T22:00:00",
				"---",
				"",
				"# Dev Journal: February 22, 2026",
				"",
				"Today was productive.",
			].join("\n"),
			"utf-8",
		);

		// Intake with highlights in frontmatter
		await writeFile(
			join(intakeDir, "intake-2026-02-22.md"),
			[
				"---",
				"date: 2026-02-22",
				"type: intake",
				"sources:",
				"  - rss",
				"  - browser",
				"item_count: 12",
				"items: 12",
				"tags:",
				"  - ai",
				"  - tools",
				"highlights:",
				"  - New Bun 1.2 release with improved test runner",
				"  - Hono v4 adds streaming support",
				"created: 2026-02-22T12:00:00",
				"---",
				"",
				"# Intake Digest: February 22, 2026",
				"",
				"A collection of articles.",
			].join("\n"),
			"utf-8",
		);

		// Seeds file with used and unused seeds
		await writeFile(
			join(TMP_DIR, ".distill-seeds.json"),
			JSON.stringify([
				{
					id: "seed-001",
					text: "Write about local-first content pipelines",
					tags: ["local-first", "architecture"],
					created_at: "2026-02-22T10:00:00Z",
					used: false,
					used_in: null,
				},
				{
					id: "seed-002",
					text: "Compare social scheduling tools",
					tags: ["social", "tools"],
					created_at: "2026-02-21T15:00:00Z",
					used: true,
					used_in: "intake-2026-02-21",
				},
				{
					id: "seed-003",
					text: "Explore PWA patterns for dashboards",
					tags: ["pwa", "frontend"],
					created_at: "2026-02-20T09:00:00Z",
					used: false,
					used_in: null,
				},
			]),
			"utf-8",
		);

		// Blog memory with publish status
		await writeFile(
			join(blogDir, ".blog-memory.json"),
			JSON.stringify({
				posts: [
					{
						slug: "weekly-2026-W08",
						title: "Week 8: Daily Briefing",
						post_type: "weekly",
						date: "2026-02-22",
						key_points: ["Added briefing endpoint"],
						themes_covered: ["dashboard"],
						examples_used: [],
						platforms_published: ["obsidian", "twitter"],
						postiz_ids: ["post-abc"],
					},
					{
						slug: "theme-local-first",
						title: "Local-First Content Pipelines",
						post_type: "thematic",
						date: "2026-02-20",
						key_points: ["File-based storage"],
						themes_covered: ["local-first"],
						examples_used: [],
						platforms_published: ["obsidian"],
						postiz_ids: [],
					},
				],
			}),
			"utf-8",
		);

		// Blog state
		await writeFile(
			join(blogDir, ".blog-state.json"),
			JSON.stringify({
				posts: [
					{
						slug: "weekly-2026-W08",
						post_type: "weekly",
						generated_at: "2026-02-22T10:00:00Z",
						source_dates: ["2026-02-17", "2026-02-18", "2026-02-19", "2026-02-20", "2026-02-21"],
						file_path: "blog/weekly/weekly-2026-W08.md",
					},
					{
						slug: "theme-local-first",
						post_type: "thematic",
						generated_at: "2026-02-20T14:00:00Z",
						source_dates: ["2026-02-15", "2026-02-18"],
						file_path: "blog/themes/theme-local-first.md",
					},
				],
			}),
			"utf-8",
		);

		setConfig({
			OUTPUT_DIR: TMP_DIR,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
	});

	afterAll(async () => {
		resetConfig();
		await rm(TMP_DIR, { recursive: true, force: true });
	});

	test("returns full briefing for a specific date", async () => {
		const res = await app.request("/api/home/2026-02-22");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.date).toBe("2026-02-22");

		// Journal brief
		expect(data.journal).toBeDefined();
		expect(data.journal.brief).toHaveLength(3);
		expect(data.journal.brief[0]).toBe("Built the daily briefing API endpoint");
		expect(data.journal.hasFullEntry).toBe(true);
		expect(data.journal.date).toBe("2026-02-22");
		expect(data.journal.sessionsCount).toBe(3);
		expect(data.journal.durationMinutes).toBe(120);

		// Intake highlights
		expect(data.intake).toBeDefined();
		expect(data.intake.highlights).toHaveLength(2);
		expect(data.intake.highlights[0]).toBe("New Bun 1.2 release with improved test runner");
		expect(data.intake.itemCount).toBe(12);
		expect(data.intake.hasFullDigest).toBe(true);
		expect(data.intake.date).toBe("2026-02-22");

		// Seeds (only unused)
		expect(data.seeds).toHaveLength(2);
		expect(data.seeds.every((s: { used: boolean }) => !s.used)).toBe(true);
		expect(data.seeds[0].id).toBe("seed-001");

		// Publish queue
		expect(data.publishQueue.length).toBeGreaterThan(0);
	});

	test("resolves 'today' to latest available date", async () => {
		const res = await app.request("/api/home/today");
		expect(res.status).toBe(200);

		const data = await res.json();
		// Latest journal date in fixtures is 2026-02-22
		expect(data.date).toBe("2026-02-22");
		expect(data.journal.brief).toHaveLength(3);
	});

	test("returns empty briefing for date with no data", async () => {
		const res = await app.request("/api/home/2025-01-01");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.date).toBe("2025-01-01");

		// Empty journal
		expect(data.journal.brief).toEqual([]);
		expect(data.journal.hasFullEntry).toBe(false);
		expect(data.journal.sessionsCount).toBe(0);
		expect(data.journal.durationMinutes).toBe(0);

		// Empty intake
		expect(data.intake.highlights).toEqual([]);
		expect(data.intake.itemCount).toBe(0);
		expect(data.intake.hasFullDigest).toBe(false);

		// Seeds still returned (not date-specific)
		expect(data.seeds).toHaveLength(2);

		// Publish queue still returned (not date-specific)
		expect(data.publishQueue.length).toBeGreaterThan(0);
	});

	test("publish queue includes blog posts with correct status", async () => {
		const res = await app.request("/api/home/2026-02-22");
		const data = await res.json();

		const queue = data.publishQueue as Array<{
			slug: string;
			title: string;
			type: string;
			status: string;
		}>;

		// weekly-2026-W08 is published to twitter
		const twitterPublished = queue.find(
			(q) => q.slug === "weekly-2026-W08" && q.type === "twitter",
		);
		expect(twitterPublished).toBeDefined();
		expect(twitterPublished?.status).toBe("published");

		// weekly-2026-W08 is NOT published to reddit
		const redditDraft = queue.find(
			(q) => q.slug === "weekly-2026-W08" && q.type === "reddit",
		);
		expect(redditDraft).toBeDefined();
		expect(redditDraft?.status).toBe("draft");

		// theme-local-first is NOT published to any social platform
		const themeTwitter = queue.find(
			(q) => q.slug === "theme-local-first" && q.type === "twitter",
		);
		expect(themeTwitter).toBeDefined();
		expect(themeTwitter?.status).toBe("draft");
	});
});
