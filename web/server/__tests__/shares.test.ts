import { afterAll, beforeEach, describe, expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const TMP_DIR = join(import.meta.dir, "fixtures", "_tmp_shares");

describe("Shares API", () => {
	beforeEach(async () => {
		await mkdir(TMP_DIR, { recursive: true });
		await writeFile(
			join(TMP_DIR, ".distill-shares.json"),
			JSON.stringify([
				{
					id: "share-1",
					url: "https://example.com/article",
					note: "good read",
					tags: ["test"],
					created_at: "2026-03-01T10:00:00Z",
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

	test("GET /api/shares returns shares", async () => {
		const res = await app.request("/api/shares");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.shares).toHaveLength(1);
		expect(data.shares[0].url).toBe("https://example.com/article");
	});

	test("POST /api/shares creates a new share", async () => {
		const res = await app.request("/api/shares", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ url: "https://new.example.com", note: "interesting", tags: [] }),
		});
		expect(res.status).toBe(201);
		const share = await res.json();
		expect(share.url).toBe("https://new.example.com");
		expect(share.note).toBe("interesting");
		expect(share).toHaveProperty("id");

		// Verify it was persisted
		const listRes = await app.request("/api/shares");
		const data = await listRes.json();
		expect(data.shares).toHaveLength(2);
	});

	test("POST /api/shares rejects empty URL", async () => {
		const res = await app.request("/api/shares", {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ url: "", note: "", tags: [] }),
		});
		expect(res.status).toBe(400);
	});

	test("DELETE /api/shares/:id removes a share", async () => {
		const res = await app.request("/api/shares/share-1", { method: "DELETE" });
		expect(res.status).toBe(200);

		const listRes = await app.request("/api/shares");
		const data = await listRes.json();
		expect(data.shares).toHaveLength(0);
	});

	test("DELETE /api/shares/:id returns 404 for nonexistent", async () => {
		const res = await app.request("/api/shares/nonexistent", { method: "DELETE" });
		expect(res.status).toBe(404);
	});

	test("GET /api/shares?url= saves via query param (iOS Shortcuts)", async () => {
		const res = await app.request("/api/shares?url=https://shortcut.example.com/article");
		expect(res.status).toBe(201);
		const share = await res.json();
		expect(share.url).toBe("https://shortcut.example.com/article");

		const listRes = await app.request("/api/shares");
		const data = await listRes.json();
		expect(data.shares).toHaveLength(2);
	});

	test("GET /api/shares?url= rejects empty URL", async () => {
		const res = await app.request("/api/shares?url=");
		expect(res.status).toBe(400);
	});
});
