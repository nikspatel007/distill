/**
 * Ghost CMS API routes — deterministic publish endpoints.
 */
import { join, resolve } from "node:path";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";
import { getConfig } from "../lib/config.js";
import { getContentRecord, loadContentStore, saveContentStore } from "../lib/content-store.js";
import { createGhostClient, getGhostTargets } from "../lib/ghost.js";

const app = new Hono();

/**
 * GET /api/ghost/targets — list configured Ghost targets.
 */
app.get("/api/ghost/targets", (c) => {
	const targets = getGhostTargets().map(({ name, label, configured }) => ({
		name,
		label,
		configured,
	}));
	return c.json({ targets });
});

/**
 * POST /api/ghost/publish/:slug — publish content to a Ghost target.
 */
const GhostPublishBodySchema = z.object({
	target: z.string().min(1),
	status: z.enum(["draft", "published"]).default("draft"),
	tags: z.array(z.string()).default([]),
});

app.post("/api/ghost/publish/:slug", zValidator("json", GhostPublishBodySchema), async (c) => {
	const slug = c.req.param("slug");
	const { target, status, tags } = c.req.valid("json");

	// Get content from ContentStore
	const record = getContentRecord(slug);
	if (!record) {
		return c.json({ error: "Content not found" }, 404);
	}

	// Create Ghost client for the target (dynamic — matches any configured target name)
	const client = createGhostClient(target);
	if (!client) {
		return c.json({ error: `Ghost target "${target}" is not configured` }, 503);
	}

	// Use the body as Ghost content (it IS the newsletter/blog post)
	let markdown = record.body;
	if (!markdown) {
		return c.json({ error: "No content body to publish" }, 400);
	}

	// Strip leading H1 from markdown (Ghost uses title field, so H1 would duplicate)
	markdown = markdown.replace(/^#\s+.+\n+/, "");

	// Upload hero image if present
	let featureImageUrl: string | undefined;
	const heroImage = record.images.find((img) => img.role === "hero");
	if (heroImage?.relative_path) {
		const { OUTPUT_DIR } = getConfig();
		const imagePath = resolve(join(OUTPUT_DIR, heroImage.relative_path));
		const uploaded = await client.uploadImage(imagePath);
		if (uploaded) {
			featureImageUrl = uploaded;
		}
	}

	try {
		const post = await client.createPost(record.title, markdown, {
			status,
			tags,
			featureImage: featureImageUrl,
		});

		// Update ContentStore — platform key is ghost_{target_name}
		const platformKey = `ghost_${target}`;
		const store = loadContentStore();
		const liveRecord = store[slug];
		if (liveRecord) {
			liveRecord.platforms[platformKey] = {
				platform: platformKey,
				content: markdown,
				published: true,
				published_at: new Date().toISOString(),
				external_id: post.id,
			};
			if (liveRecord.status === "draft" || liveRecord.status === "review") {
				liveRecord.status = "ready";
			}
			saveContentStore(store);
		}

		return c.json({
			post_id: post.id,
			url: post.url,
			target,
			status: post.status,
		});
	} catch (err) {
		const message = err instanceof Error ? err.message : "Unknown error";
		return c.json({ error: `Ghost publish failed: ${message}` }, 502);
	}
});

export default app;
