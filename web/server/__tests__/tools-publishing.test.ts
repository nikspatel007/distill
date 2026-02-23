import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { resetConfig, setConfig } from "../lib/config.js";
import { saveContentStore } from "../lib/content-store.js";
import type { ContentStoreData } from "../lib/content-store.js";
import { listPostizIntegrations, publishContent } from "../tools/publishing.js";

let tempDir: string;

beforeEach(async () => {
	tempDir = await mkdtemp(join(tmpdir(), "tools-publishing-test-"));
	setConfig({
		OUTPUT_DIR: tempDir,
		PORT: 6109,
		PROJECT_DIR: "",
		POSTIZ_URL: "",
		POSTIZ_API_KEY: "",
	});
});

afterEach(async () => {
	resetConfig();
	await rm(tempDir, { recursive: true, force: true });
});

describe("listPostizIntegrations", () => {
	test("returns configured: false when not configured", async () => {
		const result = await listPostizIntegrations();
		expect(result.configured).toBe(false);
		expect(result.integrations).toEqual([]);
	});
});

describe("publishContent", () => {
	test("returns error when not configured", async () => {
		const result = await publishContent({
			slug: "test-post",
			platforms: ["x"],
			mode: "draft",
		});
		expect(result.error).toBe("Postiz not configured");
		expect(result.results).toEqual([]);
	});

	test("returns error when record not found", async () => {
		setConfig({
			OUTPUT_DIR: tempDir,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "http://localhost:9999",
			POSTIZ_API_KEY: "fake-key",
		});

		const result = await publishContent({
			slug: "nonexistent-slug",
			platforms: ["x"],
			mode: "draft",
		});
		expect(result.error).toBe("Content record not found");
		expect(result.results).toEqual([]);
	});

	test("returns error when no content and no body", async () => {
		setConfig({
			OUTPUT_DIR: tempDir,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "http://localhost:9999",
			POSTIZ_API_KEY: "fake-key",
		});

		// Seed ContentStore with a record with empty body and no platform content
		const store: ContentStoreData = {
			"pub-test": {
				slug: "pub-test",
				content_type: "weekly",
				title: "Test Post",
				body: "",
				status: "ready",
				created_at: "2026-02-21T10:00:00Z",
				source_dates: ["2026-02-21"],
				tags: [],
				images: [],
				platforms: {},
				chat_history: [],
				metadata: {},
				file_path: "",
			},
		};
		saveContentStore(store);

		const result = await publishContent({
			slug: "pub-test",
			platforms: ["x"],
			mode: "draft",
		});
		expect(result.results).toHaveLength(1);
		expect(result.results[0]?.platform).toBe("x");
		expect(result.results[0]?.success).toBe(false);
		expect(result.results[0]?.error).toBe("No content for platform");
	});

	test("falls back to body when no platform content", async () => {
		setConfig({
			OUTPUT_DIR: tempDir,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "http://localhost:9999",
			POSTIZ_API_KEY: "fake-key",
		});

		// Seed ContentStore with body but no platform-specific content
		const store: ContentStoreData = {
			"pub-test": {
				slug: "pub-test",
				content_type: "weekly",
				title: "Test Post",
				body: "Body content used as fallback",
				status: "ready",
				created_at: "2026-02-21T10:00:00Z",
				source_dates: ["2026-02-21"],
				tags: [],
				images: [],
				platforms: {},
				chat_history: [],
				metadata: {},
				file_path: "",
			},
		};
		saveContentStore(store);

		// Will fail at integration lookup (Postiz not reachable) but should
		// NOT fail with "No content for platform" since body is the fallback
		const result = await publishContent({
			slug: "pub-test",
			platforms: ["x"],
			mode: "draft",
		});
		expect(result.results).toHaveLength(1);
		expect(result.results[0]?.platform).toBe("x");
		expect(result.results[0]?.success).toBe(false);
		// Fails at integration, not at content
		expect(result.results[0]?.error).toContain("No Postiz integration");
	});

	test("returns error for unknown platform provider", async () => {
		setConfig({
			OUTPUT_DIR: tempDir,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "http://localhost:9999",
			POSTIZ_API_KEY: "fake-key",
		});

		const store: ContentStoreData = {
			"pub-test": {
				slug: "pub-test",
				content_type: "weekly",
				title: "Test Post",
				body: "Test content",
				status: "ready",
				created_at: "2026-02-21T10:00:00Z",
				source_dates: ["2026-02-21"],
				tags: [],
				images: [],
				platforms: {
					ghost: {
						platform: "ghost",
						content: "Published content",
						published: true,
						published_at: "2026-02-21T10:00:00Z",
						external_id: "ghost-123",
					},
				},
				chat_history: [],
				metadata: {},
				file_path: "",
			},
		};
		saveContentStore(store);

		// Ghost isn't a Postiz platform — published via Ghost API directly
		const result = await publishContent({
			slug: "pub-test",
			platforms: ["ghost"],
			mode: "draft",
		});
		expect(result.results).toHaveLength(1);
		expect(result.results[0]?.platform).toBe("ghost");
		expect(result.results[0]?.success).toBe(false);
		expect(result.results[0]?.error).toBe("Unknown platform provider mapping");
	});
});
