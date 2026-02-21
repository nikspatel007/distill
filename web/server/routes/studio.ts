import { basename, join } from "node:path";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";
import {
	BlogFrontmatterSchema,
	type ChatMessage,
	ChatMessageSchema,
	CreateStudioItemSchema,
	type PlatformContent,
	type ReviewItem,
	StudioChatRequestSchema,
	StudioPublishRequestSchema,
} from "../../shared/schemas.js";
import { callAgent, callAgentStreaming, isAgentConfigured } from "../lib/agent.js";
import { getConfig } from "../lib/config.js";
import {
	getContentRecord,
	loadContentStore,
	saveContentStore,
	updateContentRecord,
} from "../lib/content-store.js";
import { listFiles, readMarkdown } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { createPost, isPostizConfigured, listIntegrations } from "../lib/postiz.js";
import { getReviewItem, loadReviewQueue, upsertReviewItem } from "../lib/review-queue.js";

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
			images: storeRecord.images,
		});
	}

	// 2. Fallback: file-system + review queue
	const { OUTPUT_DIR } = getConfig();
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
			platforms: {},
			chat_history: [],
		};
		await upsertReviewItem(review);
	}

	return c.json({
		slug,
		title: parsed.frontmatter.title ?? slug,
		type: parsed.frontmatter.post_type ?? "unknown",
		content: parsed.content,
		frontmatter: parsed.frontmatter,
		review,
		content_store: false,
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

	const results: Array<{ platform: string; success: boolean; error?: string }> = [];

	if (storeRecord) {
		// Publish from ContentStore
		const store = loadContentStore();
		const liveRecord = store[slug];
		if (!liveRecord) {
			return c.json({ error: "Record not found in store" }, 404);
		}

		for (const platform of body.platforms) {
			const platformEntry = liveRecord.platforms[platform];
			if (!platformEntry?.content) {
				results.push({ platform, success: false, error: "No adapted content" });
				continue;
			}
			if (platformEntry.published) {
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
				await createPost(platformEntry.content, [integration.id], {
					postType: body.mode,
					scheduledAt: body.scheduled_at,
				});
				platformEntry.published = true;
				platformEntry.published_at = new Date().toISOString();
				results.push({ platform, success: true });
			} catch (err) {
				const message = err instanceof Error ? err.message : "Unknown error";
				results.push({ platform, success: false, error: message });
			}
		}

		const allPublished = Object.values(liveRecord.platforms).every((p) => p.published);
		if (allPublished && Object.keys(liveRecord.platforms).length > 0) {
			liveRecord.status = "published";
		}

		saveContentStore(store);
		return c.json({ results });
	}

	// Publish from review queue (backward compat)
	// reviewItem is guaranteed non-null here (we returned 404 above if both are null)
	const item = reviewItem as NonNullable<typeof reviewItem>;

	for (const platform of body.platforms) {
		const platformEntry = item.platforms[platform];
		if (!platformEntry?.content) {
			results.push({ platform, success: false, error: "No adapted content" });
			continue;
		}
		if (platformEntry.published) {
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
			await createPost(platformEntry.content, [integration.id], {
				postType: body.mode,
				scheduledAt: body.scheduled_at,
			});
			platformEntry.published = true;
			results.push({ platform, success: true });
		} catch (err) {
			const message = err instanceof Error ? err.message : "Unknown error";
			results.push({ platform, success: false, error: message });
		}
	}

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
// POST /api/studio/chat — Claude-powered content adaptation
// ---------------------------------------------------------------------------

const PLATFORM_PROMPTS: Record<string, string> = {
	x: `You are helping craft content for X/Twitter. Create a thread of 3-8 tweets.
Rules:
- Each tweet MUST be under 280 characters
- Separate tweets with "---" on its own line
- First tweet hooks the reader with a bold insight or question
- Last tweet has a call to action
- Use conversational, punchy tone — write like a person, not a brand
- No hashtags in tweets
- The source material is journal notes — extract the most interesting insight and build around it`,

	linkedin: `You are helping craft a LinkedIn post from the author's notes. Write a single post of 1200-1800 characters.
Rules:
- Open with a hook (question, bold claim, or surprising insight from the journal)
- Write in first person, conversational but professional
- Use short paragraphs (1-2 sentences)
- Add line breaks between paragraphs for readability
- End with a question or call to action
- No emojis in the first line
- The source material is journal notes — find the compelling narrative and shape it for a professional audience`,

	slack: `You are helping craft a Slack message from the author's notes. Write 800-1400 characters.
Rules:
- Use Slack mrkdwn: *bold*, _italic_, \`code\`, > quote
- Start with a one-line summary
- Break into bullet points for key insights
- Keep it scannable
- End with a discussion question
- The source material is journal notes — distill the key learnings`,

	ghost: `You are helping shape a blog post or newsletter from the author's journal notes.
Rules:
- Help the author find the narrative arc in their notes
- Suggest a structure: hook, story, insight, takeaway
- The content should work as a standalone newsletter or blog post
- Keep the author's voice — don't over-polish
- Ask clarifying questions if the direction isn't clear
- Focus on what makes this interesting to someone who wasn't there`,
};

/**
 * Build the user prompt from chat request fields.
 */
function buildChatPrompt(
	content: string,
	platform: string,
	message: string,
	history: ChatMessage[],
): { systemPrompt: string; userPrompt: string } {
	const systemPrompt =
		PLATFORM_PROMPTS[platform] ?? `You are adapting a blog post for ${platform}.`;

	let historyBlock = "";
	if (history.length > 0) {
		const formatted = history
			.map((msg: ChatMessage) => {
				const role = msg.role === "user" ? "Human" : "Assistant";
				return `${role}: ${msg.content}`;
			})
			.join("\n\n");
		historyBlock = `\nPrevious conversation:\n${formatted}\n`;
	}

	const userPrompt = `Here are the author's notes/journal to work with:

---
${content}
---
${historyBlock}
Author's direction: ${message}

Respond with two sections:
1. RESPONSE: Your conversational response — be a thoughtful collaborator. Ask questions, suggest angles, explain your choices. Keep it brief (2-4 sentences).
2. ADAPTED_CONTENT: The full crafted content for this platform. If the author is still exploring direction, write your best draft based on what you know so far — they'll iterate.

Format:
RESPONSE:
<your response>

ADAPTED_CONTENT:
<the adapted content>`;

	return { systemPrompt, userPrompt };
}

/**
 * Parse RESPONSE / ADAPTED_CONTENT sections from Claude's output.
 */
function parseChatResponse(raw: string): { response: string; adapted_content: string } {
	const responseMatch = raw.match(/RESPONSE:\s*([\s\S]*?)(?=ADAPTED_CONTENT:|$)/);
	const contentMatch = raw.match(/ADAPTED_CONTENT:\s*([\s\S]*?)$/);
	return {
		response: responseMatch?.[1]?.trim() ?? raw.trim(),
		adapted_content: contentMatch?.[1]?.trim() ?? "",
	};
}

// POST /api/studio/chat — blocking (non-streaming) chat
app.post("/api/studio/chat", zValidator("json", StudioChatRequestSchema), async (c) => {
	const body = c.req.valid("json");
	const { content, platform, message, history } = body;

	if (!isAgentConfigured()) {
		return c.json({ error: "ANTHROPIC_API_KEY not configured" }, 503);
	}

	const { systemPrompt, userPrompt } = buildChatPrompt(content, platform, message, history);

	try {
		const raw = await callAgent(userPrompt, systemPrompt);
		return c.json(parseChatResponse(raw));
	} catch (err) {
		const errMessage = err instanceof Error ? err.message : "Unknown error";
		return c.json({ error: `Chat failed: ${errMessage}` }, 500);
	}
});

// POST /api/studio/chat/stream — SSE streaming chat
app.post("/api/studio/chat/stream", zValidator("json", StudioChatRequestSchema), async (c) => {
	const body = c.req.valid("json");
	const { content, platform, message, history } = body;

	if (!isAgentConfigured()) {
		return c.json({ error: "ANTHROPIC_API_KEY not configured" }, 503);
	}

	const { systemPrompt, userPrompt } = buildChatPrompt(content, platform, message, history);
	const agentStream = callAgentStreaming(userPrompt, systemPrompt);

	const encoder = new TextEncoder();
	const stream = new ReadableStream({
		async start(controller) {
			try {
				let fullText = "";
				for await (const msg of agentStream) {
					// Stream partial text deltas
					if (msg.type === "stream_event") {
						const event = (
							msg as { event?: { type?: string; delta?: { type?: string; text?: string } } }
						).event;
						if (
							event?.type === "content_block_delta" &&
							event.delta?.type === "text_delta" &&
							event.delta.text
						) {
							fullText += event.delta.text;
							controller.enqueue(
								encoder.encode(
									`data: ${JSON.stringify({ type: "text_delta", text: event.delta.text })}\n\n`,
								),
							);
						}
					}
				}

				// Send parsed final result
				const parsed = parseChatResponse(fullText);
				controller.enqueue(
					encoder.encode(`data: ${JSON.stringify({ type: "done", ...parsed })}\n\n`),
				);
				controller.close();
			} catch (err) {
				const errMessage = err instanceof Error ? err.message : "Unknown error";
				controller.enqueue(
					encoder.encode(`data: ${JSON.stringify({ type: "error", error: errMessage })}\n\n`),
				);
				controller.close();
			}
		},
	});

	return new Response(stream, {
		headers: {
			"Content-Type": "text/event-stream",
			"Cache-Control": "no-cache",
			Connection: "keep-alive",
		},
	});
});

// ---------------------------------------------------------------------------
// GET /api/studio/images/* — serve content images from output_dir
// ---------------------------------------------------------------------------
app.get("/api/studio/images/*", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const imagePath = c.req.path.replace("/api/studio/images/", "");
	const fullPath = join(OUTPUT_DIR, imagePath);

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
