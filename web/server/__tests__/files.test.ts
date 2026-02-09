import { describe, expect, test } from "bun:test";
import { join } from "node:path";
import { z } from "zod";
import { listFiles, readJson, readMarkdown } from "../lib/files.js";

const FIXTURES = join(import.meta.dir, "fixtures");

describe("readJson", () => {
	test("reads and validates a valid JSON file", async () => {
		const schema = z.object({
			posts: z.array(z.object({ slug: z.string() })),
		});
		const result = await readJson(join(FIXTURES, "blog", ".blog-state.json"), schema);
		expect(result).not.toBeNull();
		expect(result?.posts).toHaveLength(2);
		expect(result?.posts[0]?.slug).toBe("weekly-2026-W06");
	});

	test("returns null for nonexistent file", async () => {
		const schema = z.object({});
		const result = await readJson(join(FIXTURES, "nonexistent.json"), schema);
		expect(result).toBeNull();
	});

	test("returns null for invalid schema", async () => {
		const schema = z.object({
			required_field: z.string(),
		});
		const result = await readJson(join(FIXTURES, "blog", ".blog-state.json"), schema);
		expect(result).toBeNull();
	});
});

describe("readMarkdown", () => {
	test("reads a markdown file", async () => {
		const result = await readMarkdown(
			join(FIXTURES, "journal", "journal-2026-02-09-dev-journal.md"),
		);
		expect(result).not.toBeNull();
		expect(result).toContain("Dev Journal: February 09, 2026");
	});

	test("returns null for nonexistent file", async () => {
		const result = await readMarkdown(join(FIXTURES, "nonexistent.md"));
		expect(result).toBeNull();
	});
});

describe("listFiles", () => {
	test("lists files in a directory", async () => {
		const files = await listFiles(join(FIXTURES, "journal"));
		expect(files.length).toBeGreaterThan(0);
	});

	test("filters by pattern", async () => {
		const files = await listFiles(join(FIXTURES, "journal"), /\.md$/);
		expect(files.length).toBeGreaterThan(0);
		for (const f of files) {
			expect(f).toMatch(/\.md$/);
		}
	});

	test("returns empty for nonexistent directory", async () => {
		const files = await listFiles(join(FIXTURES, "nonexistent"));
		expect(files).toEqual([]);
	});
});
