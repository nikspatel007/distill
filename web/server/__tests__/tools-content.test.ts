import { afterEach, beforeAll, beforeEach, describe, expect, test } from "bun:test";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { resetConfig, setConfig } from "../lib/config.js";
import type { ContentStoreRecord } from "../lib/content-store.js";

let tempDir: string;

// Dynamic import to ensure config is set first
let tools: typeof import("../tools/content.js");

beforeAll(async () => {
	// Import tools module - will be used after config is set in beforeEach
	tools = await import("../tools/content.js");
});

beforeEach(async () => {
	// Create unique temp directory for each test
	tempDir = await mkdtemp(join(tmpdir(), "tools-content-test-"));
	setConfig({
		OUTPUT_DIR: tempDir,
		PORT: 6109,
		PROJECT_DIR: "",
		POSTIZ_URL: "",
		POSTIZ_API_KEY: "",
	});

	// Seed initial content store with one test record
	const seedStore = {
		records: [
			{
				slug: "test-post",
				content_type: "weekly",
				title: "Test Post",
				body: "Test content here",
				status: "draft",
				created_at: "2026-02-21T10:00:00Z",
				source_dates: ["2026-02-21"],
				tags: ["test", "blog"],
				images: [],
				platforms: {},
				chat_history: [],
				metadata: {},
				file_path: "",
			},
		],
	};
	await writeFile(join(tempDir, ".distill-content-store.json"), JSON.stringify(seedStore, null, 2));
});

afterEach(async () => {
	resetConfig();
	await rm(tempDir, { recursive: true, force: true });
});

/** Narrow getContent result to ContentStoreRecord (throws on error). */
function asRecord(result: ContentStoreRecord | { error: string }): ContentStoreRecord {
	if ("error" in result && typeof result.error === "string" && !("slug" in result)) {
		throw new Error(`Unexpected error: ${result.error}`);
	}
	return result as ContentStoreRecord;
}

describe("listContent", () => {
	test("returns all items when no filters", async () => {
		const result = await tools.listContent({});
		expect(result.items).toHaveLength(1);
		const item = result.items[0];
		expect(item?.slug).toBe("test-post");
		expect(item?.title).toBe("Test Post");
		expect(item?.type).toBe("weekly");
		expect(item?.status).toBe("draft");
	});

	test("filters by type", async () => {
		const result = await tools.listContent({ type: "weekly" });
		expect(result.items).toHaveLength(1);

		const result2 = await tools.listContent({ type: "thematic" });
		expect(result2.items).toHaveLength(0);
	});

	test("filters by status", async () => {
		const result = await tools.listContent({ status: "draft" });
		expect(result.items).toHaveLength(1);

		const result2 = await tools.listContent({ status: "published" });
		expect(result2.items).toHaveLength(0);
	});

	test("filters by type and status", async () => {
		const result = await tools.listContent({ type: "weekly", status: "draft" });
		expect(result.items).toHaveLength(1);

		const result2 = await tools.listContent({ type: "weekly", status: "published" });
		expect(result2.items).toHaveLength(0);
	});
});

describe("getContent", () => {
	test("returns full record for valid slug", async () => {
		const record = asRecord(await tools.getContent({ slug: "test-post" }));
		expect(record.slug).toBe("test-post");
		expect(record.title).toBe("Test Post");
		expect(record.body).toBe("Test content here");
		expect(record.tags).toEqual(["test", "blog"]);
	});

	test("returns error for missing slug", async () => {
		const result = await tools.getContent({ slug: "nonexistent" });
		expect("error" in result).toBe(true);
		expect((result as { error: string }).error).toBe("Content not found");
	});
});

describe("updateSource", () => {
	test("updates body content", async () => {
		const result = await tools.updateSource({
			slug: "test-post",
			content: "Updated content",
		});
		expect(result.saved).toBe(true);

		const record = asRecord(await tools.getContent({ slug: "test-post" }));
		expect(record.body).toBe("Updated content");
		expect(record.title).toBe("Test Post"); // Unchanged
	});

	test("updates body and title", async () => {
		const result = await tools.updateSource({
			slug: "test-post",
			content: "New content",
			title: "Updated Title",
		});
		expect(result.saved).toBe(true);

		const record = asRecord(await tools.getContent({ slug: "test-post" }));
		expect(record.body).toBe("New content");
		expect(record.title).toBe("Updated Title");
	});

	test("returns error for missing slug", async () => {
		const result = await tools.updateSource({
			slug: "nonexistent",
			content: "Test",
		});
		expect(result.saved).toBe(false);
		expect(result.error).toBe("Content not found");
	});
});

describe("savePlatform", () => {
	test("saves platform-specific content", async () => {
		const result = await tools.savePlatform({
			slug: "test-post",
			platform: "x",
			content: "Tweet version of the post",
		});
		expect(result.saved).toBe(true);
		expect(result.platform).toBe("x");

		const record = asRecord(await tools.getContent({ slug: "test-post" }));
		// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
		const xPlatform = record.platforms["x"];
		expect(xPlatform).toBeDefined();
		expect(xPlatform?.content).toBe("Tweet version of the post");
		expect(xPlatform?.published).toBe(false);
	});

	test("saves multiple platforms", async () => {
		await tools.savePlatform({
			slug: "test-post",
			platform: "x",
			content: "X version",
		});
		await tools.savePlatform({
			slug: "test-post",
			platform: "linkedin",
			content: "LinkedIn version",
		});

		const record = asRecord(await tools.getContent({ slug: "test-post" }));
		expect(Object.keys(record.platforms)).toHaveLength(2);
		// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
		expect(record.platforms["x"]).toBeDefined();
		// biome-ignore lint/complexity/useLiteralKeys: tsc noPropertyAccessFromIndexSignature
		expect(record.platforms["linkedin"]).toBeDefined();
	});

	test("returns error for missing slug", async () => {
		const result = await tools.savePlatform({
			slug: "nonexistent",
			platform: "x",
			content: "Test",
		});
		expect(result.saved).toBe(false);
		expect(result.error).toBe("Content not found");
		expect(result.platform).toBe("x");
	});
});

describe("updateStatus", () => {
	test("updates status to review", async () => {
		const result = await tools.updateStatus({
			slug: "test-post",
			status: "review",
		});
		expect(result.saved).toBe(true);

		const record = asRecord(await tools.getContent({ slug: "test-post" }));
		expect(record.status).toBe("review");
	});

	test("updates status to published", async () => {
		const result = await tools.updateStatus({
			slug: "test-post",
			status: "published",
		});
		expect(result.saved).toBe(true);

		const record = asRecord(await tools.getContent({ slug: "test-post" }));
		expect(record.status).toBe("published");
	});

	test("rejects invalid status", async () => {
		const result = await tools.updateStatus({
			slug: "test-post",
			status: "invalid",
		});
		expect(result.saved).toBe(false);
		expect(result.error).toBe("Invalid status: invalid");
	});

	test("returns error for missing slug", async () => {
		const result = await tools.updateStatus({
			slug: "nonexistent",
			status: "review",
		});
		expect(result.saved).toBe(false);
		expect(result.error).toBe("Content not found");
	});
});

describe("deleteContent", () => {
	test("deletes existing content", async () => {
		const result = await tools.deleteContent({ slug: "test-post" });
		expect(result.deleted).toBe(true);

		// Verify it's gone
		const getResult = await tools.getContent({ slug: "test-post" });
		expect("error" in getResult).toBe(true);
	});

	test("returns error for missing slug", async () => {
		const result = await tools.deleteContent({ slug: "nonexistent" });
		expect(result.deleted).toBe(false);
		expect(result.error).toBe("Content not found");
	});
});

describe("createContent", () => {
	test("creates new content with generated slug", async () => {
		const result = await tools.createContent({
			title: "My New Post",
			body: "Content for the new post",
			content_type: "journal",
			tags: ["vermas", "testing"],
		});
		expect(result.created).toBe(true);
		expect(result.slug).toBe("my-new-post");

		const record = asRecord(await tools.getContent({ slug: "my-new-post" }));
		expect(record.title).toBe("My New Post");
		expect(record.body).toBe("Content for the new post");
		expect(record.content_type).toBe("journal");
		expect(record.status).toBe("draft");
		expect(record.tags).toEqual(["vermas", "testing"]);
	});

	test("generates unique slug for duplicate titles", async () => {
		const result1 = await tools.createContent({
			title: "Duplicate Title",
			body: "First post",
			content_type: "weekly",
		});
		expect(result1.slug).toBe("duplicate-title");

		const result2 = await tools.createContent({
			title: "Duplicate Title",
			body: "Second post",
			content_type: "weekly",
		});
		expect(result2.slug).toBe("duplicate-title-1");

		const result3 = await tools.createContent({
			title: "Duplicate Title",
			body: "Third post",
			content_type: "weekly",
		});
		expect(result3.slug).toBe("duplicate-title-2");
	});

	test("normalizes slug from title", async () => {
		const result = await tools.createContent({
			title: "Post With Special Characters!!! @#$% And Spaces",
			body: "Content",
			content_type: "thematic",
		});
		expect(result.slug).toBe("post-with-special-characters-and-spaces");
	});

	test("creates content without tags", async () => {
		const result = await tools.createContent({
			title: "No Tags Post",
			body: "Content",
			content_type: "digest",
		});
		expect(result.created).toBe(true);

		const record = asRecord(await tools.getContent({ slug: "no-tags-post" }));
		expect(record.tags).toEqual([]);
	});

	test("truncates long slugs to 60 characters", async () => {
		const result = await tools.createContent({
			title: "This is a very long title that should be truncated to sixty characters maximum",
			body: "Content",
			content_type: "weekly",
		});
		expect(result.slug.length).toBeLessThanOrEqual(60);
		// The slug is truncated at 60 chars, which may cut mid-word
		expect(result.slug).toMatch(/^this-is-a-very-long-title-that-should-be-truncated-to-six/);
	});
});
