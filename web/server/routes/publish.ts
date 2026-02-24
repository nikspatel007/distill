import { join } from "node:path";
import { Hono } from "hono";
import {
	BlogMemorySchema,
	BlogStateSchema,
	type PublishQueueItem,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { readJson } from "../lib/files.js";
import { isPostizConfigured, listIntegrations } from "../lib/postiz.js";

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

export default app;
