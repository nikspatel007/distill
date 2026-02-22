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

	test("returns error when platform content missing", async () => {
		setConfig({
			OUTPUT_DIR: tempDir,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "http://localhost:9999",
			POSTIZ_API_KEY: "fake-key",
		});

		// Seed ContentStore with a record but no platform content
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
		expect(result.results[0]?.error).toBe("No adapted content for platform");
	});

	test("returns error when platform already published", async () => {
		setConfig({
			OUTPUT_DIR: tempDir,
			PORT: 6109,
			PROJECT_DIR: "",
			POSTIZ_URL: "http://localhost:9999",
			POSTIZ_API_KEY: "fake-key",
		});

		// Seed ContentStore with already-published platform content
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

		const result = await publishContent({
			slug: "pub-test",
			platforms: ["ghost"],
			mode: "draft",
		});
		expect(result.results).toHaveLength(1);
		expect(result.results[0]?.platform).toBe("ghost");
		expect(result.results[0]?.success).toBe(false);
		expect(result.results[0]?.error).toBe("Already published");
	});
});
