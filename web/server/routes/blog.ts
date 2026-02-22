import { basename, join } from "node:path";
import { Hono } from "hono";
import {
	BlogFrontmatterSchema,
	BlogMemorySchema,
	SaveMarkdownSchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { getContentRecord } from "../lib/content-store.js";
import { listFiles, readJson, readMarkdown, writeMarkdown } from "../lib/files.js";
import { parseFrontmatter, reconstructMarkdown } from "../lib/frontmatter.js";
import { collectBlogFiles, loadBlogPosts } from "../lib/loaders.js";

const app = new Hono();

app.get("/api/blog/posts", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const posts = await loadBlogPosts(OUTPUT_DIR);
	return c.json({ posts });
});

app.get("/api/blog/posts/:slug", async (c) => {
	const slug = c.req.param("slug");
	const { OUTPUT_DIR } = getConfig();

	const files = await collectBlogFiles(OUTPUT_DIR);
	const match = files.find((f) => basename(f, ".md") === slug || f.includes(slug));

	if (!match) return c.json({ error: "Blog post not found" }, 404);

	const raw = await readMarkdown(match);
	if (!raw) return c.json({ error: "Could not read file" }, 500);

	const parsed = parseFrontmatter(raw, BlogFrontmatterSchema);
	if (!parsed) return c.json({ error: "Could not parse frontmatter" }, 500);

	const blogMemory = await readJson(
		join(OUTPUT_DIR, "blog", ".blog-memory.json"),
		BlogMemorySchema,
	);
	const memoryPost = blogMemory?.posts.find((p) => p.slug === slug);

	// Pull images: ContentStore metadata + disk scan for untracked images
	const storeRecord = getContentRecord(slug);
	const storeImages = storeRecord?.images ?? [];
	const knownFiles = new Set(storeImages.map((img) => img.filename));
	const images = [...storeImages];

	for (const subdir of ["blog/images", "studio/images"]) {
		const diskFiles = await listFiles(join(OUTPUT_DIR, subdir), /\.png$/);
		for (const filePath of diskFiles) {
			const fname = basename(filePath);
			if (!fname.startsWith(`${slug}-`) || knownFiles.has(fname)) continue;
			knownFiles.add(fname);
			images.push({
				filename: fname,
				role: fname.includes("hero") ? "hero" : "inline",
				prompt: "",
				relative_path: `${subdir}/${fname}`,
			});
		}
	}

	return c.json({
		meta: {
			slug,
			title: parsed.frontmatter.title ?? slug,
			postType: parsed.frontmatter.post_type ?? "unknown",
			date: parsed.frontmatter.date ?? "",
			tags: parsed.frontmatter.tags,
			themes: parsed.frontmatter.themes,
			projects: parsed.frontmatter.projects,
			filename: basename(match),
			platformsPublished: memoryPost?.platforms_published ?? [],
		},
		content: parsed.content,
		images,
	});
});

app.put("/api/blog/posts/:slug", async (c) => {
	const slug = c.req.param("slug");
	const { OUTPUT_DIR } = getConfig();

	const body = await c.req.json();
	const parsed = SaveMarkdownSchema.safeParse(body);
	if (!parsed.success) return c.json({ error: "Invalid request body" }, 400);

	const files = await collectBlogFiles(OUTPUT_DIR);
	const match = files.find((f) => basename(f, ".md") === slug || f.includes(slug));

	if (!match) return c.json({ error: "Blog post not found" }, 404);

	const raw = await readMarkdown(match);
	if (!raw) return c.json({ error: "Could not read file" }, 500);

	const updated = reconstructMarkdown(raw, parsed.data.content);

	try {
		await writeMarkdown(match, updated, OUTPUT_DIR);
	} catch (err) {
		const message = err instanceof Error ? err.message : "Write failed";
		return c.json({ error: message }, 403);
	}

	return c.json({ success: true });
});

export default app;
