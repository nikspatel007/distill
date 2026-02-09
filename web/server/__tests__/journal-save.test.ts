import { afterAll, afterEach, beforeAll, describe, expect, test } from "bun:test";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";

const FIXTURES = join(import.meta.dir, "fixtures");
const JOURNAL_FILE = join(FIXTURES, "journal", "journal-2026-02-09-dev-journal.md");
let originalContent: string;

describe("PUT /api/journal/:date", () => {
	beforeAll(async () => {
		setConfig({
			OUTPUT_DIR: FIXTURES,
			PORT: 3001,
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
		originalContent = await readFile(JOURNAL_FILE, "utf-8");
	});

	afterEach(async () => {
		// Restore original file after each test
		await Bun.write(JOURNAL_FILE, originalContent);
	});

	afterAll(() => {
		resetConfig();
	});

	test("saves updated content", async () => {
		const res = await app.request("/api/journal/2026-02-09", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "# Updated Journal\n\nNew content here." }),
		});
		expect(res.status).toBe(200);

		const data = await res.json();
		expect(data.success).toBe(true);

		// Verify file was updated
		const updated = await readFile(JOURNAL_FILE, "utf-8");
		expect(updated).toContain("# Updated Journal");
		expect(updated).toContain("New content here.");
		// Frontmatter should be preserved
		expect(updated).toContain("date: 2026-02-09");
		expect(updated).toContain("style: dev-journal");
	});

	test("returns 404 for nonexistent date", async () => {
		const res = await app.request("/api/journal/2099-01-01", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "test" }),
		});
		expect(res.status).toBe(404);
	});

	test("returns 400 for invalid body", async () => {
		const res = await app.request("/api/journal/2026-02-09", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ wrong: "field" }),
		});
		expect(res.status).toBe(400);
	});

	test("preserves frontmatter after save", async () => {
		await app.request("/api/journal/2026-02-09", {
			method: "PUT",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({ content: "# Saved Content" }),
		});

		// Read back via GET
		const res = await app.request("/api/journal/2026-02-09");
		const data = await res.json();
		expect(data.meta.date).toBe("2026-02-09");
		expect(data.meta.style).toBe("dev-journal");
		expect(data.meta.sessionsCount).toBe(4);
		expect(data.content).toContain("# Saved Content");
	});
});
