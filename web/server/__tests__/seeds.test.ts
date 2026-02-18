import { afterAll, beforeEach, describe, expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const TMP_DIR = join(import.meta.dir, "fixtures", "_tmp_seeds");

describe("Seeds API", () => {
	beforeEach(async () => {
		await mkdir(TMP_DIR, { recursive: true });
		await writeFile(
			join(TMP_DIR, ".distill-seeds.json"),
			JSON.stringify([
				{
					id: "seed-1",
					text: "Test seed idea",
					tags: ["test"],
					created_at: "2026-02-09T10:00:00Z",
					used: false,
					used_in: null,
				},
			]),
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

	test("GET /api/seeds returns seeds", async () => {
		const res = await app.request("/api/seeds");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.seeds).toHaveLength(1);
		expect(data.seeds[0].text).toBe("Test seed idea");
	});

	test("POST /api/seeds creates a new seed", async () => {
		const res = await app.request("/api/seeds", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text: "New seed", tags: ["new"] }),
		});
		expect(res.status).toBe(201);
		const seed = await res.json();
		expect(seed.text).toBe("New seed");
		expect(seed.tags).toContain("new");
		expect(seed).toHaveProperty("id");

		// Verify it was persisted
		const listRes = await app.request("/api/seeds");
		const data = await listRes.json();
		expect(data.seeds).toHaveLength(2);
	});

	test("POST /api/seeds rejects empty text", async () => {
		const res = await app.request("/api/seeds", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text: "", tags: [] }),
		});
		expect(res.status).toBe(400);
	});

	test("DELETE /api/seeds/:id removes a seed", async () => {
		const res = await app.request("/api/seeds/seed-1", { method: "DELETE" });
		expect(res.status).toBe(200);

		const listRes = await app.request("/api/seeds");
		const data = await listRes.json();
		expect(data.seeds).toHaveLength(0);
	});

	test("DELETE /api/seeds/:id returns 404 for nonexistent", async () => {
		const res = await app.request("/api/seeds/nonexistent", { method: "DELETE" });
		expect(res.status).toBe(404);
	});
});
