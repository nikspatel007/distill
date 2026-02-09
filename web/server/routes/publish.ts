import { join } from "node:path";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import {
	BlogMemorySchema,
	BlogStateSchema,
	type PublishQueueItem,
	PublishRequestSchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { readJson } from "../lib/files.js";
import { createPost, isPostizConfigured, listIntegrations } from "../lib/postiz.js";

const app = new Hono();

const TARGET_PLATFORMS = ["twitter", "linkedin", "reddit"];

app.get("/api/publish/queue", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const [blogMemory, blogState] = await Promise.all([
		readJson(join(OUTPUT_DIR, "blog", ".blog-memory.json"), BlogMemorySchema),
		readJson(join(OUTPUT_DIR, "blog", ".blog-state.json"), BlogStateSchema),
	]);

	const queue: PublishQueueItem[] = [];
	const memoryPosts = blogMemory?.posts ?? [];
	const statePosts = blogState?.posts ?? [];

	if (memoryPosts.length > 0) {
		for (const post of memoryPosts) {
			for (const platform of TARGET_PLATFORMS) {
				queue.push({
					slug: post.slug,
					title: post.title,
					postType: post.post_type,
					date: post.date,
					platform,
					published: post.platforms_published.includes(platform),
				});
			}
		}
	} else {
		for (const post of statePosts) {
			for (const platform of TARGET_PLATFORMS) {
				queue.push({
					slug: post.slug,
					title: post.slug,
					postType: post.post_type,
					date: post.generated_at,
					platform,
					published: false,
				});
			}
		}
	}

	return c.json({ queue, postizConfigured: isPostizConfigured() });
});

app.get("/api/publish/integrations", async (c) => {
	if (!isPostizConfigured()) {
		return c.json({ integrations: [], configured: false });
	}
	try {
		const integrations = await listIntegrations();
		return c.json({ integrations, configured: true });
	} catch {
		return c.json({ integrations: [], configured: true, error: "Failed to fetch integrations" });
	}
});

app.post("/api/publish/:slug", zValidator("json", PublishRequestSchema), async (c) => {
	const slug = c.req.param("slug");
	const body = c.req.valid("json");

	if (!isPostizConfigured()) {
		return c.json({ error: "Postiz not configured" }, 503);
	}

	// Read the blog post content
	const { OUTPUT_DIR } = getConfig();
	const blogMemory = await readJson(
		join(OUTPUT_DIR, "blog", ".blog-memory.json"),
		BlogMemorySchema,
	);
	const posts = blogMemory?.posts ?? [];
	const post = posts.find((p) => p.slug === slug);

	if (!post) {
		return c.json({ error: "Post not found in blog memory" }, 404);
	}

	try {
		// Find appropriate integration
		const integrations = await listIntegrations();
		const integrationId =
			body.integrationId ?? integrations.find((i) => i.provider.includes(body.platform))?.id;

		if (!integrationId) {
			return c.json({ error: `No integration found for platform: ${body.platform}` }, 400);
		}

		const keyPoints = post.key_points;
		const result = await createPost(`${post.title}\n\n${keyPoints.join("\n")}`, [integrationId], {
			postType: body.mode,
		});

		return c.json({ success: true, result });
	} catch (err) {
		const message = err instanceof Error ? err.message : "Unknown error";
		return c.json({ error: message }, 500);
	}
});

export default app;
