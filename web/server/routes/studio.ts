import { spawn } from "node:child_process";
import { basename, join } from "node:path";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";
import {
	BlogFrontmatterSchema,
	type ChatMessage,
	ChatMessageSchema,
	type PlatformContent,
	type ReviewItem,
	StudioChatRequestSchema,
	StudioPublishRequestSchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readMarkdown } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { createPost, isPostizConfigured, listIntegrations } from "../lib/postiz.js";
import { getReviewItem, loadReviewQueue, upsertReviewItem } from "../lib/review-queue.js";

const app = new Hono();

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
 * Reads blog files from OUTPUT_DIR/blog/weekly and OUTPUT_DIR/blog/themes,
 * merges with review queue state to show status.
 */
app.get("/api/studio/items", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const files = await collectStudioFiles(OUTPUT_DIR);
	const queue = await loadReviewQueue();

	const items: Array<{
		slug: string;
		title: string;
		type: string;
		status: string;
		generated_at: string;
		platforms_ready: number;
		platforms_published: number;
	}> = [];

	for (const file of files) {
		const raw = await readMarkdown(file);
		if (!raw) continue;
		const parsed = parseFrontmatter(raw, BlogFrontmatterSchema);
		if (!parsed) continue;

		const slug = parsed.frontmatter.slug ?? basename(file, ".md");
		const postType = parsed.frontmatter.post_type ?? "unknown";
		const date = parsed.frontmatter.date ?? "";

		// Check review queue for existing item
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
 * Finds the blog markdown file, parses frontmatter, reads content,
 * and creates or loads review item from queue.
 */
app.get("/api/studio/items/:slug", async (c) => {
	const slug = c.req.param("slug");
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
		// Map post_type to ReviewItem type enum
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
	});
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
// ---------------------------------------------------------------------------
app.post("/api/studio/publish/:slug", zValidator("json", StudioPublishRequestSchema), async (c) => {
	const slug = c.req.param("slug");
	const body = c.req.valid("json");

	if (!isPostizConfigured()) {
		return c.json({ error: "Postiz not configured" }, 503);
	}

	const item = await getReviewItem(slug);
	if (!item) {
		return c.json({ error: "Review item not found" }, 404);
	}

	let integrations: Awaited<ReturnType<typeof listIntegrations>> = [];
	try {
		integrations = await listIntegrations();
	} catch {
		return c.json({ error: "Failed to fetch integrations" }, 502);
	}

	const results: Array<{ platform: string; success: boolean; error?: string }> = [];

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

	// Check if all platforms are published
	const allPublished = Object.values(item.platforms).every((p) => p.published);
	if (allPublished && Object.keys(item.platforms).length > 0) {
		item.status = "published";
	}

	await upsertReviewItem(item);
	return c.json({ results });
});

// ---------------------------------------------------------------------------
// PUT /api/studio/items/:slug/platform/:platform — save adapted content
// ---------------------------------------------------------------------------
const PlatformContentBodySchema = z.object({ content: z.string() });

app.put(
	"/api/studio/items/:slug/platform/:platform",
	zValidator("json", PlatformContentBodySchema),
	async (c) => {
		const slug = c.req.param("slug");
		const platform = c.req.param("platform");
		const { content } = c.req.valid("json");

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
// PUT /api/studio/items/:slug/chat — save chat history
// ---------------------------------------------------------------------------
const ChatHistoryBodySchema = z.object({
	chat_history: z.array(ChatMessageSchema),
});

app.put("/api/studio/items/:slug/chat", zValidator("json", ChatHistoryBodySchema), async (c) => {
	const slug = c.req.param("slug");
	const { chat_history } = c.req.valid("json");

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
	x: `You are adapting a blog post for X/Twitter. Create a thread of 6-10 tweets.
Rules:
- Each tweet MUST be under 280 characters
- Separate tweets with "---" on its own line
- First tweet hooks the reader
- Last tweet links back or has a call to action
- Use conversational, punchy tone
- No hashtags in tweets`,

	linkedin: `You are adapting a blog post for LinkedIn. Write a single post of 1200-1800 characters.
Rules:
- Open with a hook (question, bold claim, or surprising stat)
- Write in first person, conversational but professional
- Use short paragraphs (1-2 sentences)
- Add line breaks between paragraphs for readability
- End with a question or call to action
- No emojis in the first line`,

	slack: `You are adapting a blog post for a Slack channel. Write a concise summary of 800-1400 characters.
Rules:
- Use Slack mrkdwn: *bold*, _italic_, \`code\`, > quote
- Start with a one-line summary
- Break into bullet points for key insights
- Keep it scannable
- End with a discussion question`,

	ghost: `You are helping refine a blog post for Ghost (newsletter/website).
Rules:
- Maintain the essay structure
- Suggest improvements to clarity, flow, and engagement
- The content should work as a standalone newsletter
- Keep the author's voice intact`,
};

app.post("/api/studio/chat", zValidator("json", StudioChatRequestSchema), async (c) => {
	const body = c.req.valid("json");
	const { content, platform, message, history } = body;

	const platformPrompt =
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

	const fullPrompt = `${platformPrompt}

Here is the blog post to work with:

---
${content}
---
${historyBlock}
User's direction: ${message}

Respond with two sections:
1. RESPONSE: Your conversational response to the user
2. ADAPTED_CONTENT: The full adapted content for this platform

Format:
RESPONSE:
<your response>

ADAPTED_CONTENT:
<the adapted content>`;

	try {
		const result = await new Promise<string>((resolve, reject) => {
			const proc = spawn("claude", ["-p", fullPrompt], {
				stdio: ["pipe", "pipe", "pipe"],
				timeout: 120_000,
			});
			let stdout = "";
			let stderr = "";
			proc.stdout.on("data", (data: Buffer) => {
				stdout += data.toString();
			});
			proc.stderr.on("data", (data: Buffer) => {
				stderr += data.toString();
			});
			proc.on("close", (code: number | null) => {
				if (code === 0) resolve(stdout);
				else reject(new Error(`claude exited with code ${code}: ${stderr}`));
			});
			proc.on("error", reject);
		});

		const responseMatch = result.match(/RESPONSE:\s*([\s\S]*?)(?=ADAPTED_CONTENT:|$)/);
		const contentMatch = result.match(/ADAPTED_CONTENT:\s*([\s\S]*?)$/);
		const response = responseMatch?.[1]?.trim() ?? result.trim();
		const adaptedContent = contentMatch?.[1]?.trim() ?? "";

		return c.json({ response, adapted_content: adaptedContent });
	} catch (err) {
		const errMessage = err instanceof Error ? err.message : "Unknown error";
		return c.json({ error: `Chat failed: ${errMessage}` }, 500);
	}
});

export default app;
