import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { resetConfig, setConfig } from "../lib/config.js";
import {
	getReviewItem,
	loadReviewQueue,
	saveReviewQueue,
	upsertReviewItem,
} from "../lib/review-queue.js";

let tempDir: string;

beforeEach(async () => {
	tempDir = await mkdtemp(join(tmpdir(), "review-queue-"));
	setConfig({
		OUTPUT_DIR: tempDir,
		PORT: 3001,
		PROJECT_DIR: "",
		POSTIZ_URL: "",
		POSTIZ_API_KEY: "",
	});
});

afterEach(async () => {
	resetConfig();
	await rm(tempDir, { recursive: true, force: true });
});

describe("loadReviewQueue", () => {
	test("returns empty queue when file missing", async () => {
		const queue = await loadReviewQueue();
		expect(queue.items).toEqual([]);
	});

	test("parses existing queue file", async () => {
		const data = {
			items: [
				{
					slug: "test-post",
					title: "Test",
					type: "thematic",
					status: "draft",
					generated_at: "2026-02-18T10:00:00",
					platforms: {},
					chat_history: [],
				},
			],
		};
		const { writeFile: wf } = await import("node:fs/promises");
		await wf(join(tempDir, ".distill-review-queue.json"), JSON.stringify(data));
		const queue = await loadReviewQueue();
		expect(queue.items).toHaveLength(1);
		expect(queue.items[0]?.slug).toBe("test-post");
	});
});

describe("saveReviewQueue", () => {
	test("writes queue to disk", async () => {
		await saveReviewQueue({
			items: [
				{
					slug: "a",
					title: "A",
					type: "weekly",
					status: "draft",
					generated_at: "2026-02-18T10:00:00",
					source_content: "",
					platforms: {},
					chat_history: [],
				},
			],
		});
		const raw = await readFile(join(tempDir, ".distill-review-queue.json"), "utf-8");
		const parsed = JSON.parse(raw);
		expect(parsed.items).toHaveLength(1);
	});
});

describe("getReviewItem", () => {
	test("returns null for missing slug", async () => {
		expect(await getReviewItem("nonexistent")).toBeNull();
	});
});

describe("upsertReviewItem", () => {
	test("inserts new item", async () => {
		await upsertReviewItem({
			slug: "new",
			title: "New",
			type: "thematic",
			status: "draft",
			generated_at: "2026-02-18T10:00:00",
			source_content: "",
			platforms: {},
			chat_history: [],
		});
		const item = await getReviewItem("new");
		expect(item?.slug).toBe("new");
	});

	test("updates existing item", async () => {
		await upsertReviewItem({
			slug: "up",
			title: "Up",
			type: "weekly",
			status: "draft",
			generated_at: "2026-02-18T10:00:00",
			source_content: "",
			platforms: {},
			chat_history: [],
		});
		await upsertReviewItem({
			slug: "up",
			title: "Updated",
			type: "weekly",
			status: "ready",
			generated_at: "2026-02-18T10:00:00",
			source_content: "",
			platforms: {},
			chat_history: [],
		});
		const item = await getReviewItem("up");
		expect(item?.title).toBe("Updated");
		expect(item?.status).toBe("ready");
	});
});
