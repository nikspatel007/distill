import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const FIXTURES = join(import.meta.dir, "fixtures");

describe("GET /api/journal", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 3001,
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("returns journal entries", async () => {
		const res = await app.request("/api/journal");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data).toHaveProperty("entries");
		expect(data.entries.length).toBeGreaterThan(0);
	});

	test("entries have expected fields", async () => {
		const res = await app.request("/api/journal");
		const data = await res.json();
		const entry = data.entries[0];

		expect(entry).toHaveProperty("date");
		expect(entry).toHaveProperty("style");
		expect(entry).toHaveProperty("sessionsCount");
		expect(entry).toHaveProperty("durationMinutes");
		expect(entry).toHaveProperty("tags");
		expect(entry).toHaveProperty("projects");
		expect(entry).toHaveProperty("filename");
	});

	test("entries are sorted by date descending", async () => {
		const res = await app.request("/api/journal");
		const data = await res.json();

		for (let i = 0; i < data.entries.length - 1; i++) {
			expect(data.entries[i].date >= data.entries[i + 1].date).toBe(true);
		}
	});
});

describe("GET /api/journal/:date", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 3001,
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("returns a specific journal entry", async () => {
		const res = await app.request("/api/journal/2026-02-09");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data).toHaveProperty("meta");
		expect(data).toHaveProperty("content");
		expect(data.meta.date).toBe("2026-02-09");
		expect(data.content).toContain("Dev Journal");
	});

	test("returns 404 for nonexistent date", async () => {
		const res = await app.request("/api/journal/2099-01-01");
		expect(res.status).toBe(404);
	});
});
