import { describe, expect, test } from "bun:test";
import { z } from "zod";
import { JournalFrontmatterSchema } from "../../shared/schemas.js";
import { parseFrontmatter } from "../lib/frontmatter.js";

describe("parseFrontmatter", () => {
	test("parses valid frontmatter", () => {
		const raw = `---
date: 2026-02-09
type: journal
style: dev-journal
sessions_count: 4
duration_minutes: 180
tags:
  - journal
  - web
projects:
  - distill
created: 2026-02-09T22:00:00
---

# My Journal Entry

Content here.`;

		const result = parseFrontmatter(raw, JournalFrontmatterSchema);
		expect(result).not.toBeNull();
		expect(result?.frontmatter.date).toBe("2026-02-09");
		expect(result?.frontmatter.style).toBe("dev-journal");
		expect(result?.frontmatter.sessions_count).toBe(4);
		expect(result?.frontmatter.duration_minutes).toBe(180);
		expect(result?.frontmatter.tags).toContain("journal");
		expect(result?.frontmatter.tags).toContain("web");
		expect(result?.frontmatter.projects).toContain("distill");
		expect(result?.content).toContain("# My Journal Entry");
		expect(result?.content).toContain("Content here.");
	});

	test("returns null for no frontmatter", () => {
		const result = parseFrontmatter("Just plain text", JournalFrontmatterSchema);
		expect(result).toBeNull();
	});

	test("returns null for invalid frontmatter", () => {
		const schema = z.object({
			required: z.string(),
		});
		const raw = `---
other: value
---

Content`;
		const result = parseFrontmatter(raw, schema);
		expect(result).toBeNull();
	});

	test("handles empty tags array", () => {
		const raw = `---
date: 2026-02-09
type: journal
style: dev-journal
sessions_count: 0
duration_minutes: 0
tags: []
---

Content`;

		const result = parseFrontmatter(raw, JournalFrontmatterSchema);
		expect(result).not.toBeNull();
		expect(result?.frontmatter.tags).toEqual([]);
	});

	test("handles frontmatter with no trailing newline", () => {
		const raw = `---
date: 2026-02-09
type: journal
style: dev-journal
sessions_count: 1
duration_minutes: 30
---
Content immediately after.`;

		const result = parseFrontmatter(raw, JournalFrontmatterSchema);
		expect(result).not.toBeNull();
		expect(result?.content).toContain("Content immediately after.");
	});
});
