import { afterAll, afterEach, beforeAll, describe, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const FIXTURES = join(import.meta.dir, "fixtures");
const INTAKE_FILE = join(FIXTURES, "intake", "intake-2026-02-09.md");
let originalContent: string;

describe("PUT /api/reading/digests/:date", () => {
	beforeAll(async () => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 3001,
			PROJECT_DIR: "",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
		originalContent = await readFile(INTAKE_FILE, "utf-8");
	});

	afterEach(async () => {
		await Bun.write(INTAKE_FILE, originalContent);
	});

	afterAll(() => {
		resetConfig();
	});

	test("saves updated digest content", async () => {
		const res = await app.request("/api/reading/digests/2026-02-09", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "# Updated Digest\n\nNew digest content." }),
		});
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.success).toBe(true);

		const updated = await readFile(INTAKE_FILE, "utf-8");
		expect(updated).toContain("# Updated Digest");
		expect(updated).toContain("New digest content.");
		expect(updated).toContain("date: 2026-02-09");
		expect(updated).toContain("type: intake");
	});

	test("returns 404 for nonexistent date", async () => {
		const res = await app.request("/api/reading/digests/2099-01-01", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "test" }),
		});
		expect(res.status).toBe(404);
	});

	test("returns 400 for invalid body", async () => {
		const res = await app.request("/api/reading/digests/2026-02-09", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ text: "wrong" }),
		});
		expect(res.status).toBe(400);
	});

	test("preserves frontmatter after save", async () => {
		await app.request("/api/reading/digests/2026-02-09", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "# Edited Digest" }),
		});

		const res = await app.request("/api/reading/digests/2026-02-09");
		const data = await res.json();
		expect(data.meta.date).toBe("2026-02-09");
		expect(data.meta.sources).toContain("rss");
		expect(data.meta.itemCount).toBe(15);
		expect(data.content).toContain("# Edited Digest");
	});
});
