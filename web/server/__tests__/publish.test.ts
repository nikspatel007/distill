import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const FIXTURES = join(import.meta.dir, "fixtures");

describe("GET /api/publish/queue", () => {
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

	test("returns publish queue", async () => {
		const res = await app.request("/api/publish/queue");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data).toHaveProperty("queue");
		expect(data).toHaveProperty("postizConfigured", false);
		expect(data.queue.length).toBeGreaterThan(0);
	});

	test("queue items have expected shape", async () => {
		const res = await app.request("/api/publish/queue");
		const data = await res.json();
		const item = data.queue[0];

		expect(item).toHaveProperty("slug");
		expect(item).toHaveProperty("title");
		expect(item).toHaveProperty("postType");
		expect(item).toHaveProperty("platform");
		expect(item).toHaveProperty("published");
	});

	test("marks already-published platforms correctly", async () => {
		const res = await app.request("/api/publish/queue");
		const data = await res.json();

		// weekly-2026-W06 is published to twitter
		const twitterItem = data.queue.find(
			(q: { slug: string; platform: string }) =>
				q.slug === "weekly-2026-W06" && q.platform === "twitter",
		);
		expect(twitterItem).toBeDefined();
		expect(twitterItem.published).toBe(true);

		// weekly-2026-W06 is NOT published to reddit
		const redditItem = data.queue.find(
			(q: { slug: string; platform: string }) =>
				q.slug === "weekly-2026-W06" && q.platform === "reddit",
		);
		expect(redditItem).toBeDefined();
		expect(redditItem.published).toBe(false);
	});
});

describe("POST /api/publish/:slug", () => {
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

	test("returns 503 when Postiz is not configured", async () => {
		const res = await app.request("/api/publish/weekly-2026-W06", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ platform: "twitter", mode: "draft" }),
		});
		expect(res.status).toBe(503);
	});
});

describe("GET /api/publish/integrations", () => {
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

	test("returns not configured when Postiz is not set", async () => {
		const res = await app.request("/api/publish/integrations");
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.configured).toBe(false);
		expect(data.integrations).toEqual([]);
	});
});
