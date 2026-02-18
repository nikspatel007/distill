import { afterAll, beforeEach, describe, expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const TMP_DIR = join(import.meta.dir, "fixtures", "_tmp_calendar");

describe("Calendar API", () => {
	beforeEach(async () => {
		const calDir = join(TMP_DIR, "content-calendar");
		await mkdir(calDir, { recursive: true });
		await writeFile(
			join(calDir, "2026-02-17.json"),
			JSON.stringify({
				date: "2026-02-17",
				ideas: [
					{
						title: "Test Idea",
						angle: "Test angle",
						source_url: "https://example.com",
						platform: "blog",
						rationale: "Test reason",
						pillars: ["AI architecture patterns"],
						tags: ["test"],
						status: "pending",
						ghost_post_id: null,
					},
				],
			}),
			"utf-8",
		);
		setConfig({
			OUTPUT_DIR: TMP_DIR,
			PORT: 3001,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
	});

	afterAll(async () => {
		resetConfig();
		await rm(TMP_DIR, { recursive: true, force: true });
	});

	test("GET /api/calendar returns calendar list", async () => {
		const res = await app.request("/api/calendar");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.calendars).toBeInstanceOf(Array);
		expect(data.calendars.length).toBeGreaterThanOrEqual(1);
		expect(data.calendars).toContain("2026-02-17");
	});

	test("GET /api/calendar/:date returns specific calendar", async () => {
		const res = await app.request("/api/calendar/2026-02-17");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.date).toBe("2026-02-17");
		expect(data.ideas).toHaveLength(1);
		expect(data.ideas[0].title).toBe("Test Idea");
		expect(data.ideas[0].platform).toBe("blog");
	});

	test("GET /api/calendar/:date returns 404 for missing date", async () => {
		const res = await app.request("/api/calendar/2099-01-01");
		expect(res.status).toBe(404);
	});
});
