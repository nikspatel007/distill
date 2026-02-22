import { basename, join, resolve } from "node:path";
import { zValidator } from "@hono/zod-validator";
import { convertToModelMessages, stepCountIs, streamText, tool } from "ai";
import { Hono } from "hono";
import { z } from "zod";
import {
	BlogFrontmatterSchema,
	ChatMessageSchema,
	CreateStudioItemSchema,
	type PlatformContent,
	type ReviewItem,
	StudioChatRequestSchema,
	StudioPublishRequestSchema,
} from "../../shared/schemas.js";
import { getModel, isAgentConfigured } from "../lib/agent.js";
import { getConfig } from "../lib/config.js";
import {
	deleteContentRecord,
	getContentRecord,
	loadContentStore,
	saveContentStore,
	updateContentRecord,
} from "../lib/content-store.js";
import { listFiles, readMarkdown } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { createPost, isPostizConfigured, listIntegrations } from "../lib/postiz.js";
import { PLATFORM_PROMPTS } from "../lib/prompts.js";
import { getReviewItem, loadReviewQueue, upsertReviewItem } from "../lib/review-queue.js";
import {
	createContent,
	getContent,
	listContent,
	savePlatform,
	updateSource,
	updateStatus as updateStatusTool,
} from "../tools/content.js";
import { generateImage as generateImageTool, isImageConfigured } from "../tools/images.js";
import {
	addNote,
	addSeed,
	runBlog,
	runIntake,
	runJournal,
	runPipeline,
} from "../tools/pipeline.js";
import { listPostizIntegrations, listPostizPosts, publishContent } from "../tools/publishing.js";
import { fetchUrl, saveToIntake } from "../tools/research.js";

const app = new Hono();

/**
 * Map ContentStore content_type (underscore) to API type (hyphen).
 * "daily_social" -> "daily-social", others pass through.
 */
function mapContentType(contentType: string): string {
	if (contentType === "daily_social") return "daily-social";
	if (contentType === "reading_list") return "reading-list";
	return contentType;
}

/**
 * Scan disk for images matching a slug.
 * Looks in blog/images/ and studio/images/ for files named slug-*.png.
 * Returns image records, merging with any existing records (deduped by filename).
 */
async function discoverImages(
	outputDir: string,
	slug: string,
	existing: Array<{ filename: string; role: string; prompt: string; relative_path: string }>,
): Promise<Array<{ filename: string; role: string; prompt: string; relative_path: string }>> {
	const known = new Set(existing.map((img) => img.filename));
	const result = [...existing];

	for (const subdir of ["blog/images", "studio/images"]) {
		const files = await listFiles(join(outputDir, subdir), /\.png$/);
		for (const filePath of files) {
			const fname = basename(filePath);
			if (!fname.startsWith(`${slug}-`) || known.has(fname)) continue;
			known.add(fname);
			const role = fname.includes("hero") ? "hero" : "inline";
			result.push({
				filename: fname,
				role,
				prompt: "",
				relative_path: `${subdir}/${fname}`,
			});
		}
	}

	return result;
}

/**
 * Collect all blog markdown files from weekly + themes directories.
 */
async function collectStudioFiles(outputDir: string): Promise<string[]> {
	const [weeklyFiles, thematicFiles] = await Promise.all([
		listFiles(join(outputDir, "blog", "weekly"), /\.md$/),
		listFiles(join(outputDir, "blog", "themes"), /\.md$/),
	]);
	return [...weeklyFiles, ...thematicFiles];
}

/**
 * GET /api/studio/items — list all publishable content items.
 * Merges ContentStore records with file-system blog scan.
 * ContentStore records are primary; .md files not in the store fall back
 * to frontmatter parsing + review queue state.
 */
app.get("/api/studio/items", async (c) => {
	const { OUTPUT_DIR } = getConfig();

	const items: Array<{
		slug: string;
		title: string;
		type: string;
		status: string;
		generated_at: string;
		platforms_ready: number;
		platforms_published: number;
	}> = [];

	// Track slugs we've already added from the ContentStore
	const seenSlugs = new Set<string>();

	// 1. Load all ContentStore records first (primary source)
	const store = loadContentStore();
	for (const record of Object.values(store)) {
		seenSlugs.add(record.slug);

		const platformsReady = Object.values(record.platforms).filter(
			(p) => p.content && p.content.length > 0,
		).length;
		const platformsPublished = Object.values(record.platforms).filter((p) => p.published).length;

		items.push({
			slug: record.slug,
			title: record.title,
			type: mapContentType(record.content_type),
			status: record.status,
			generated_at: record.created_at,
			platforms_ready: platformsReady,
			platforms_published: platformsPublished,
		});
	}

	// 2. Fallback: scan .md files for items not yet in ContentStore
	const files = await collectStudioFiles(OUTPUT_DIR);
	const queue = await loadReviewQueue();

	for (const file of files) {
		const raw = await readMarkdown(file);
		if (!raw) continue;
		const parsed = parseFrontmatter(raw, BlogFrontmatterSchema);
		if (!parsed) continue;

		const slug = parsed.frontmatter.slug ?? basename(file, ".md");
		if (seenSlugs.has(slug)) continue; // Already added from ContentStore

		const postType = parsed.frontmatter.post_type ?? "unknown";
		const date = parsed.frontmatter.date ?? "";

		const reviewItem = queue.items.find((i) => i.slug === slug);

		const platformsReady = reviewItem
			? Object.values(reviewItem.platforms).filter((p) => p.enabled && p.content).length
			: 0;
		const platformsPublished = reviewItem
			? Object.values(reviewItem.platforms).filter((p) => p.published).length
			: 0;

		items.push({
			slug,
			title: parsed.frontmatter.title ?? slug,
			type: postType,
			status: reviewItem?.status ?? "draft",
			generated_at: reviewItem?.generated_at ?? date,
			platforms_ready: platformsReady,
			platforms_published: platformsPublished,
		});
	}

	// Sort: drafts first, then by generated_at descending
	items.sort((a, b) => {
		if (a.status === "draft" && b.status !== "draft") return -1;
		if (a.status !== "draft" && b.status === "draft") return 1;
		return b.generated_at.localeCompare(a.generated_at);
	});

	return c.json({ items });
});

/**
 * GET /api/studio/items/:slug — get single item with full content.
 * Prefers ContentStore; falls back to .md file + review queue.
 */
app.get("/api/studio/items/:slug", async (c) => {
	const slug = c.req.param("slug");
	const { OUTPUT_DIR } = getConfig();

	// 1. Try ContentStore first
	const storeRecord = getContentRecord(slug);
	if (storeRecord) {
		// Convert ContentStore platforms to ReviewItem-compatible format for backward compat
		const reviewPlatforms: Record<string, PlatformContent> = {};
		for (const [key, plat] of Object.entries(storeRecord.platforms)) {
			reviewPlatforms[key] = {
				enabled: true,
				content: plat.content || null,
				published: plat.published,
				postiz_id: plat.external_id || null,
			};
		}

		// Default ghost content to the source body (the body IS the newsletter)
		// biome-ignore lint/complexity/useLiteralKeys: TS noPropertyAccessFromIndexSignature
		if (!reviewPlatforms["ghost"] && storeRecord.body) {
			// biome-ignore lint/complexity/useLiteralKeys: TS noPropertyAccessFromIndexSignature
			reviewPlatforms["ghost"] = {
				enabled: true,
				content: storeRecord.body,
				published: false,
				postiz_id: null,
			};
		}

		const review: ReviewItem = {
			slug: storeRecord.slug,
			title: storeRecord.title,
			type: mapContentType(storeRecord.content_type) as ReviewItem["type"],
			status:
				storeRecord.status === "review" || storeRecord.status === "archived"
					? "draft"
					: (storeRecord.status as "draft" | "ready" | "published"),
			generated_at: storeRecord.created_at,
			source_content: storeRecord.body,
			platforms: reviewPlatforms,
			chat_history: storeRecord.chat_history.map((msg) => ({
				role: msg.role as "user" | "assistant",
				content: msg.content,
				timestamp: msg.timestamp,
			})),
		};

		// Discover images from disk (supplements ContentStore metadata)
		const images = await discoverImages(OUTPUT_DIR, slug, storeRecord.images ?? []);

		return c.json({
			slug: storeRecord.slug,
			title: storeRecord.title,
			type: mapContentType(storeRecord.content_type),
			content: storeRecord.body,
			frontmatter: {
				title: storeRecord.title,
				date: storeRecord.created_at,
				type: "blog",
				post_type: mapContentType(storeRecord.content_type),
				tags: storeRecord.tags,
				themes: [],
				projects: [],
			},
			review,
			content_store: true,
			store_status: storeRecord.status,
			images,
		});
	}

	// 2. Fallback: file-system + review queue
	const files = await collectStudioFiles(OUTPUT_DIR);
	const match = files.find((f) => basename(f, ".md") === slug || f.includes(slug));

	if (!match) return c.json({ error: "Item not found" }, 404);

	const raw = await readMarkdown(match);
	if (!raw) return c.json({ error: "Could not read file" }, 500);

	const parsed = parseFrontmatter(raw, BlogFrontmatterSchema);
	if (!parsed) return c.json({ error: "Could not parse frontmatter" }, 500);

	// Load or create review item
	let review = await getReviewItem(slug);
	if (!review) {
		const postType = parsed.frontmatter.post_type ?? "unknown";
		const typeMap: Record<string, ReviewItem["type"]> = {
			weekly: "weekly",
			thematic: "thematic",
			"daily-social": "daily-social",
			intake: "intake",
		};
		const reviewType = typeMap[postType] ?? "thematic";

		review = {
			slug,
			title: parsed.frontmatter.title ?? slug,
			type: reviewType,
			status: "draft",
			generated_at: parsed.frontmatter.date ?? new Date().toISOString(),
			source_content: parsed.content,
			platforms: {
				ghost: { enabled: true, content: parsed.content, published: false, postiz_id: null },
			},
			chat_history: [],
		};
		await upsertReviewItem(review);
	}

	// Default ghost content to the source body
	// biome-ignore lint/complexity/useLiteralKeys: TS noPropertyAccessFromIndexSignature
	if (!review.platforms["ghost"] && parsed.content) {
		// biome-ignore lint/complexity/useLiteralKeys: TS noPropertyAccessFromIndexSignature
		review.platforms["ghost"] = {
			enabled: true,
			content: parsed.content,
			published: false,
			postiz_id: null,
		};
	}

	// Discover images from disk
	const images = await discoverImages(OUTPUT_DIR, slug, []);

	return c.json({
		slug,
		title: parsed.frontmatter.title ?? slug,
		type: parsed.frontmatter.post_type ?? "unknown",
		content: parsed.content,
		frontmatter: parsed.frontmatter,
		review,
		content_store: false,
		images,
	});
});

/**
 * POST /api/studio/items — create a new Studio item from journal content.
 * Creates a ContentStore record and returns the slug for navigation.
 */
app.post("/api/studio/items", zValidator("json", CreateStudioItemSchema), async (c) => {
	const body = c.req.valid("json");
	const store = loadContentStore();

	// Generate a slug from the title
	const baseSlug = body.title
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "-")
		.replace(/^-|-$/g, "")
		.slice(0, 60);

	// Ensure uniqueness
	let slug = baseSlug;
	let counter = 1;
	while (store[slug]) {
		slug = `${baseSlug}-${counter}`;
		counter++;
	}

	const now = new Date().toISOString();
	store[slug] = {
		slug,
		content_type: body.content_type as
			| "journal"
			| "weekly"
			| "thematic"
			| "reading_list"
			| "digest"
			| "daily_social"
			| "seed",
		title: body.title,
		body: body.body,
		status: "draft",
		created_at: now,
		source_dates: body.source_date ? [body.source_date] : [],
		tags: body.tags,
		images: [],
		platforms: {},
		chat_history: [],
		metadata: {},
		file_path: "",
	};

	saveContentStore(store);
	return c.json({ slug, created: true });
});

/**
 * GET /api/studio/platforms — list connected Postiz integrations.
 */
app.get("/api/studio/platforms", async (c) => {
	const configured = isPostizConfigured();
	if (!configured) {
		return c.json({ integrations: [], configured: false });
	}

	try {
		const integrations = await listIntegrations();
		return c.json({ integrations, configured: true });
	} catch {
		return c.json({ integrations: [], configured: false });
	}
});

/** Map platform names to Postiz provider identifiers. */
const PLATFORM_PROVIDER_MAP: Record<string, string> = {
	x: "x",
	linkedin: "linkedin",
	slack: "slack",
};

/** Shared publish-to-platform logic for both ContentStore and review queue entries. */
async function publishPlatforms(
	platforms: string[],
	getPlatformEntry: (
		platform: string,
	) => { content?: string | null; published?: boolean; published_at?: string | null } | undefined,
	integrations: Awaited<ReturnType<typeof listIntegrations>>,
	postOptions: { postType?: string; scheduledAt?: string },
): Promise<Array<{ platform: string; success: boolean; error?: string }>> {
	const results: Array<{ platform: string; success: boolean; error?: string }> = [];

	for (const platform of platforms) {
		const entry = getPlatformEntry(platform);
		if (!entry?.content) {
			results.push({ platform, success: false, error: "No adapted content" });
			continue;
		}
		if (entry.published) {
			results.push({ platform, success: false, error: "Already published" });
			continue;
		}

		const provider = PLATFORM_PROVIDER_MAP[platform] ?? platform;
		const integration = integrations.find((i) => i.provider.includes(provider));
		if (!integration) {
			results.push({ platform, success: false, error: `No integration for ${platform}` });
			continue;
		}

		try {
			await createPost(entry.content, [integration.id], postOptions);
			entry.published = true;
			if ("published_at" in entry) {
				entry.published_at = new Date().toISOString();
			}
			results.push({ platform, success: true });
		} catch (err) {
			const message = err instanceof Error ? err.message : "Unknown error";
			results.push({ platform, success: false, error: message });
		}
	}

	return results;
}

// ---------------------------------------------------------------------------
// POST /api/studio/publish/:slug — publish to Postiz
// Prefers ContentStore; falls back to review queue.
// ---------------------------------------------------------------------------
app.post("/api/studio/publish/:slug", zValidator("json", StudioPublishRequestSchema), async (c) => {
	const slug = c.req.param("slug");
	const body = c.req.valid("json");

	if (!isPostizConfigured()) {
		return c.json({ error: "Postiz not configured" }, 503);
	}

	// Determine source: ContentStore (primary) or review queue (fallback)
	const storeRecord = getContentRecord(slug);
	const reviewItem = storeRecord ? null : await getReviewItem(slug);

	if (!storeRecord && !reviewItem) {
		return c.json({ error: "Review item not found" }, 404);
	}

	let integrations: Awaited<ReturnType<typeof listIntegrations>> = [];
	try {
		integrations = await listIntegrations();
	} catch {
		return c.json({ error: "Failed to fetch integrations" }, 502);
	}

	const postOptions = { postType: body.mode, scheduledAt: body.scheduled_at };

	if (storeRecord) {
		// Publish from ContentStore
		const store = loadContentStore();
		const liveRecord = store[slug];
		if (!liveRecord) {
			return c.json({ error: "Record not found in store" }, 404);
		}

		const results = await publishPlatforms(
			body.platforms,
			(p) => liveRecord.platforms[p],
			integrations,
			postOptions,
		);

		const allPublished = Object.values(liveRecord.platforms).every((p) => p.published);
		if (allPublished && Object.keys(liveRecord.platforms).length > 0) {
			liveRecord.status = "published";
		}

		saveContentStore(store);
		return c.json({ results });
	}

	// Publish from review queue (backward compat)
	const item = reviewItem as NonNullable<typeof reviewItem>;

	const results = await publishPlatforms(
		body.platforms,
		(p) => item.platforms[p],
		integrations,
		postOptions,
	);

	const allPublished = Object.values(item.platforms).every((p) => p.published);
	if (allPublished && Object.keys(item.platforms).length > 0) {
		item.status = "published";
	}

	await upsertReviewItem(item);
	return c.json({ results });
});

// ---------------------------------------------------------------------------
// PUT /api/studio/items/:slug/platform/:platform — save adapted content
// Prefers ContentStore; falls back to review queue.
// ---------------------------------------------------------------------------
const PlatformContentBodySchema = z.object({ content: z.string() });

app.put(
	"/api/studio/items/:slug/platform/:platform",
	zValidator("json", PlatformContentBodySchema),
	async (c) => {
		const slug = c.req.param("slug");
		const platform = c.req.param("platform");
		const { content } = c.req.valid("json");

		// Try ContentStore first
		const storeRecord = getContentRecord(slug);
		if (storeRecord) {
			const store = loadContentStore();
			const record = store[slug];
			if (!record) return c.json({ error: "Record not found" }, 404);

			const existing = record.platforms[platform] ?? {
				platform,
				content: "",
				published: false,
				published_at: null,
				external_id: "",
			};
			existing.content = content;
			record.platforms[platform] = existing;
			saveContentStore(store);
			return c.json({ success: true });
		}

		// Fallback: review queue
		const item = await getReviewItem(slug);
		if (!item) return c.json({ error: "Review item not found" }, 404);

		const existing: PlatformContent = item.platforms[platform] ?? {
			enabled: true,
			content: null,
			published: false,
			postiz_id: null,
		};
		existing.content = content;
		item.platforms[platform] = existing;

		await upsertReviewItem(item);
		return c.json({ success: true });
	},
);

// ---------------------------------------------------------------------------
// PUT /api/studio/items/:slug/status — update status in ContentStore
// ---------------------------------------------------------------------------
const StatusBodySchema = z.object({
	status: z.enum(["draft", "review", "ready", "published", "archived"]),
});

app.put("/api/studio/items/:slug/status", zValidator("json", StatusBodySchema), async (c) => {
	const slug = c.req.param("slug");
	const { status } = c.req.valid("json");

	// Try ContentStore first
	const updated = updateContentRecord(slug, { status });
	if (updated) {
		return c.json({ success: true, status: updated.status });
	}

	// Fallback: review queue
	const item = await getReviewItem(slug);
	if (!item) return c.json({ error: "Item not found" }, 404);

	// Map ContentStore statuses to review queue statuses
	const statusMap: Record<string, ReviewItem["status"]> = {
		draft: "draft",
		review: "draft",
		ready: "ready",
		published: "published",
		archived: "published",
	};
	item.status = statusMap[status] ?? "draft";
	await upsertReviewItem(item);
	return c.json({ success: true, status: item.status });
});

// ---------------------------------------------------------------------------
// DELETE /api/studio/items/:slug — permanently delete a content item
// ---------------------------------------------------------------------------
app.delete("/api/studio/items/:slug", async (c) => {
	const slug = c.req.param("slug");
	const deleted = deleteContentRecord(slug);
	if (!deleted) return c.json({ error: "Content not found" }, 404);
	return c.json({ success: true });
});

// ---------------------------------------------------------------------------
// POST /api/studio/items/:slug/image — generate an image for a content item
// ---------------------------------------------------------------------------
const GenerateImageSchema = z.object({
	prompt: z.string().min(1),
	mood: z.enum([
		"reflective",
		"energetic",
		"cautionary",
		"triumphant",
		"intimate",
		"technical",
		"playful",
		"somber",
	]),
});

app.post("/api/studio/items/:slug/image", zValidator("json", GenerateImageSchema), async (c) => {
	const slug = c.req.param("slug");
	if (!isImageConfigured()) {
		return c.json({ error: "Image generation not configured (GOOGLE_AI_API_KEY)" }, 503);
	}
	const { prompt, mood } = c.req.valid("json");
	const result = await generateImageTool({ prompt, mood, slug });
	if (result.error) {
		return c.json({ error: result.error }, 500);
	}
	return c.json(result);
});

// ---------------------------------------------------------------------------
// PUT /api/studio/items/:slug/chat — save chat history
// Prefers ContentStore; falls back to review queue.
// ---------------------------------------------------------------------------
const ChatHistoryBodySchema = z.object({
	chat_history: z.array(ChatMessageSchema),
});

app.put("/api/studio/items/:slug/chat", zValidator("json", ChatHistoryBodySchema), async (c) => {
	const slug = c.req.param("slug");
	const { chat_history } = c.req.valid("json");

	// Try ContentStore first
	const storeRecord = getContentRecord(slug);
	if (storeRecord) {
		const store = loadContentStore();
		const record = store[slug];
		if (!record) return c.json({ error: "Record not found" }, 404);

		record.chat_history = chat_history.map((msg) => ({
			role: msg.role,
			content: msg.content,
			timestamp: msg.timestamp,
		}));
		saveContentStore(store);
		return c.json({ success: true });
	}

	// Fallback: review queue
	const item = await getReviewItem(slug);
	if (!item) return c.json({ error: "Review item not found" }, 404);

	item.chat_history = chat_history;
	await upsertReviewItem(item);
	return c.json({ success: true });
});

// ---------------------------------------------------------------------------
// POST /api/studio/chat — AI SDK streaming chat with tools
// ---------------------------------------------------------------------------

app.post("/api/studio/chat", zValidator("json", StudioChatRequestSchema), async (c) => {
	if (!isAgentConfigured()) {
		return c.json({ error: "ANTHROPIC_API_KEY not configured" }, 503);
	}

	const { messages, content, platform, slug } = c.req.valid("json");

	const platformPrompt =
		PLATFORM_PROMPTS[platform] ??
		`You are adapting content for ${platform}.

After writing the adapted content, ALWAYS call the savePlatformContent tool with the full content.`;

	const systemPrompt = `${platformPrompt}

Here are the author's source notes to work with:

---
${content}
---

Be a thoughtful collaborator. Ask questions, suggest angles, explain your choices.

When you write or revise content for the platform, call the savePlatformContent tool with the full content.
When the author asks you to edit, rewrite, or improve the source post itself, call the updateSourceContent tool with the complete updated post. Always send the FULL updated content, not just the changed section.${isImageConfigured() ? "\nYou can generate images to accompany the content using the generateImage tool. Generate a hero image when you write the first draft, or when the author asks for one." : ""}

You also have access to tools for:
- Content management: listContent, getContent, updateStatus, createContent
- Pipeline: runPipeline, runJournal, runBlog, runIntake, addSeed, addNote
- Research: fetchUrl (read any URL), saveToIntake (save URL content for future synthesis)
- Publishing: listIntegrations (connected platforms), publish (post to social), listPosts (recent/upcoming)

Use these when the author asks about the broader content pipeline, wants to research a topic, or manage other content.`;

	// Convert UI wire format (parts-based) to model messages (role + content).
	// Messages arrive as opaque wire format from TextStreamChatTransport.
	const modelMessages = await convertToModelMessages(
		messages as Parameters<typeof convertToModelMessages>[0],
	);

	const result = streamText({
		model: getModel(),
		system: systemPrompt,
		messages: modelMessages,
		tools: {
			// --- Content ---
			updateSourceContent: tool({
				description:
					"Update the original source post. Call when the author asks to edit/rewrite the source notes.",
				inputSchema: z.object({
					content: z.string().describe("Full updated source content (markdown)"),
					title: z.string().optional().describe("Updated title, if changed"),
				}),
				execute: async (params) => updateSource({ slug: slug ?? "", ...params }),
			}),
			savePlatformContent: tool({
				description:
					"Save adapted content for the target platform. Call every time you write or revise platform content.",
				inputSchema: z.object({
					content: z.string().describe("Full adapted content for the platform"),
				}),
				execute: async ({ content: c }) => savePlatform({ slug: slug ?? "", platform, content: c }),
			}),
			listContent: tool({
				description: "List all content items in the studio. Use to browse available posts.",
				inputSchema: z.object({
					type: z.string().optional().describe("Filter by type: weekly, thematic, journal, etc."),
					status: z
						.string()
						.optional()
						.describe("Filter by status: draft, review, ready, published"),
				}),
				execute: async (params) => listContent(params),
			}),
			getContent: tool({
				description: "Get full content record by slug.",
				inputSchema: z.object({ slug: z.string() }),
				execute: async (params) => getContent(params),
			}),
			updateStatus: tool({
				description: "Change content status (draft, review, ready, published, archived).",
				inputSchema: z.object({
					slug: z.string(),
					status: z.enum(["draft", "review", "ready", "published", "archived"]),
				}),
				execute: async (params) => updateStatusTool(params),
			}),
			createContent: tool({
				description: "Create a new content item in the studio.",
				inputSchema: z.object({
					title: z.string(),
					body: z.string(),
					content_type: z.enum(["weekly", "thematic", "journal", "digest", "seed"]),
					tags: z.array(z.string()).optional(),
				}),
				execute: async (params) => createContent(params),
			}),

			// --- Pipeline ---
			runPipeline: tool({
				description:
					"Run the full distill pipeline: sessions -> journal -> intake -> blog. Takes a few minutes.",
				inputSchema: z.object({
					project: z.string().optional().describe("Project name from .distill.toml"),
					skip_journal: z.boolean().optional(),
					skip_intake: z.boolean().optional(),
					skip_blog: z.boolean().optional(),
				}),
				execute: async (params) => runPipeline(params),
			}),
			runJournal: tool({
				description: "Generate journal entries from coding sessions.",
				inputSchema: z.object({
					project: z.string().optional(),
					date: z.string().optional().describe("Specific date (YYYY-MM-DD)"),
					since: z.string().optional().describe("Generate since this date"),
					force: z.boolean().optional(),
				}),
				execute: async (params) => runJournal(params),
			}),
			runBlog: tool({
				description: "Generate blog posts from journal entries.",
				inputSchema: z.object({
					project: z.string().optional(),
					type: z.enum(["weekly", "thematic", "all"]).optional(),
					week: z.string().optional().describe("Specific week (e.g., 2026-W08)"),
					force: z.boolean().optional(),
				}),
				execute: async (params) => runBlog(params),
			}),
			runIntake: tool({
				description: "Run content ingestion from RSS feeds, browser history, etc.",
				inputSchema: z.object({
					project: z.string().optional(),
					sources: z.string().optional().describe("Comma-separated source names"),
					use_defaults: z.boolean().optional(),
				}),
				execute: async (params) => runIntake(params),
			}),
			addSeed: tool({
				description: "Add a seed idea to the pipeline for future blog posts.",
				inputSchema: z.object({
					text: z.string().describe("The seed idea"),
					tags: z.string().optional().describe("Comma-separated tags"),
				}),
				execute: async (params) => addSeed(params),
			}),
			addNote: tool({
				description: "Add an editorial note to steer content direction.",
				inputSchema: z.object({
					text: z.string().describe("The editorial note"),
					target: z.string().optional().describe("Target (e.g., 'week:2026-W08')"),
				}),
				execute: async (params) => addNote(params),
			}),

			// --- Research ---
			fetchUrl: tool({
				description:
					"Fetch a URL and extract readable text. Use to read articles, papers, or documentation.",
				inputSchema: z.object({
					url: z.string().url().describe("URL to fetch"),
				}),
				execute: async (params) => fetchUrl(params),
			}),
			saveToIntake: tool({
				description:
					"Fetch a URL and save the content to the intake pipeline for future synthesis.",
				inputSchema: z.object({
					url: z.string().url().describe("URL to fetch and save"),
					tags: z.array(z.string()).optional(),
					notes: z.string().optional().describe("Your notes about why this is interesting"),
				}),
				execute: async (params) => saveToIntake(params),
			}),

			// --- Publishing ---
			listIntegrations: tool({
				description: "List connected Postiz platform integrations.",
				inputSchema: z.object({}),
				execute: async () => listPostizIntegrations(),
			}),
			publish: tool({
				description: "Publish content to social platforms via Postiz.",
				inputSchema: z.object({
					slug: z.string(),
					platforms: z.array(z.string()).describe("Platform names: x, linkedin, slack, ghost"),
					mode: z.enum(["draft", "schedule", "now"]),
					scheduled_at: z.string().optional().describe("ISO datetime for scheduled posts"),
				}),
				execute: async (params) => publishContent(params),
			}),
			listPosts: tool({
				description: "List recent and upcoming posts from Postiz.",
				inputSchema: z.object({
					status: z.string().optional(),
					limit: z.number().optional(),
				}),
				execute: async (params) => listPostizPosts(params),
			}),

			// --- Images ---
			...(isImageConfigured()
				? {
						generateImage: tool({
							description: "Generate a hero image for content.",
							inputSchema: z.object({
								prompt: z
									.string()
									.describe("Visual metaphor — describe the scene, not the article topic"),
								mood: z.enum([
									"reflective",
									"energetic",
									"cautionary",
									"triumphant",
									"intimate",
									"technical",
									"playful",
									"somber",
								]),
							}),
							execute: async (params) => generateImageTool({ ...params, slug: slug ?? undefined }),
						}),
					}
				: {}),
		},
		stopWhen: stepCountIs(3),
	});

	return result.toUIMessageStreamResponse();
});

// ---------------------------------------------------------------------------
// GET /api/studio/images/* — serve content images from output_dir
// ---------------------------------------------------------------------------
app.get("/api/studio/images/*", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const imagePath = c.req.path.replace("/api/studio/images/", "");
	const fullPath = resolve(join(OUTPUT_DIR, imagePath));

	// Prevent path traversal outside OUTPUT_DIR
	if (!fullPath.startsWith(resolve(OUTPUT_DIR))) {
		return c.json({ error: "Forbidden" }, 403);
	}

	try {
		const file = Bun.file(fullPath);
		if (!(await file.exists())) {
			return c.json({ error: "Image not found" }, 404);
		}
		return new Response(file);
	} catch {
		return c.json({ error: "Failed to read image" }, 500);
	}
});

export default app;
