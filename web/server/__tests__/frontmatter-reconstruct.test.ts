import { describe, expect, test } from "bun:test";
import { mkdir, rm, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { writeMarkdown } from "../lib/files.js";
import { extractFrontmatterBlock, reconstructMarkdown } from "../lib/frontmatter.js";

describe("extractFrontmatterBlock", () => {
	test("extracts frontmatter block from markdown", () => {
		const raw = `---
date: 2026-02-09
type: journal
---

# Content`;

		const block = extractFrontmatterBlock(raw);
		expect(block).toBe("---\ndate: 2026-02-09\ntype: journal\n---\n");
	});

	test("returns null for no frontmatter", () => {
		expect(extractFrontmatterBlock("Just content")).toBeNull();
	});

	test("preserves exact frontmatter bytes", () => {
		const raw = `---
title: "Week 6: Building"
date: 2026-02-07
tags:
  - pipeline
  - web
---

# Body`;

		const block = extractFrontmatterBlock(raw);
		expect(block).toContain('title: "Week 6: Building"');
		expect(block).toContain("  - pipeline");
		expect(block).toContain("  - web");
	});
});

describe("reconstructMarkdown", () => {
	test("replaces body while preserving frontmatter", () => {
		const raw = `---
date: 2026-02-09
type: journal
---

# Old Content

Old body text.`;

		const result = reconstructMarkdown(raw, "# New Content\n\nNew body text.");
		expect(result).toContain("date: 2026-02-09");
		expect(result).toContain("# New Content");
		expect(result).toContain("New body text.");
		expect(result).not.toContain("Old body text.");
	});

	test("returns just body when no frontmatter", () => {
		const result = reconstructMarkdown("No frontmatter", "New content");
		expect(result).toBe("New content");
	});

	test("preserves complex frontmatter exactly", () => {
		const raw = `---
title: "Test Post"
tags:
  - one
  - two
projects: [distill]
---

Body`;

		const result = reconstructMarkdown(raw, "Updated body");
		expect(result).toContain('title: "Test Post"');
		expect(result).toContain("  - one");
		expect(result).toContain("projects: [distill]");
		expect(result).toContain("Updated body");
	});
});

describe("writeMarkdown security", () => {
	const tmpDir = join(import.meta.dir, "tmp-write-test");

	test("rejects path traversal", async () => {
		await mkdir(tmpDir, { recursive: true });
		try {
			await writeMarkdown(join(tmpDir, "../../../etc/passwd"), "hack", tmpDir);
			expect(true).toBe(false); // should not reach
		} catch (err) {
			expect((err as Error).message).toBe("Path traversal not allowed");
		} finally {
			await rm(tmpDir, { recursive: true, force: true });
		}
	});

	test("rejects writing to non-existent file", async () => {
		await mkdir(tmpDir, { recursive: true });
		try {
			await writeMarkdown(join(tmpDir, "does-not-exist.md"), "content", tmpDir);
			expect(true).toBe(false); // should not reach
		} catch {
			// Expected — access() throws for non-existent file
		} finally {
			await rm(tmpDir, { recursive: true, force: true });
		}
	});

	test("allows writing to existing file within base", async () => {
		await mkdir(tmpDir, { recursive: true });
		const file = join(tmpDir, "test.md");
		await writeFile(file, "original");
		try {
			await writeMarkdown(file, "updated", tmpDir);
			const content = await Bun.file(file).text();
			expect(content).toBe("updated");
		} finally {
			await rm(tmpDir, { recursive: true, force: true });
		}
	});
});
