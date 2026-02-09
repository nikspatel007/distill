import { basename, join } from "node:path";
import { Hono } from "hono";
import {
	BlogFrontmatterSchema,
	BlogMemorySchema,
	type BlogPost,
	SaveMarkdownSchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readJson, readMarkdown, writeMarkdown } from "../lib/files.js";
import { parseFrontmatter, reconstructMarkdown } from "../lib/frontmatter.js";

const app = new Hono();

async function collectBlogFiles(outputDir: string): Promise<string[]> {
	const [weeklyFiles, thematicFiles] = await Promise.all([
		listFiles(join(outputDir, "blog", "weekly"), /\.md$/),
		listFiles(join(outputDir, "blog", "themes"), /\.md$/),
	]);
	return [...weeklyFiles, ...thematicFiles];
}

app.get("/api/blog/posts", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const [files, blogMemory] = await Promise.all([
		collectBlogFiles(OUTPUT_DIR),
		readJson(join(OUTPUT_DIR, "blog", ".blog-memory.json"), BlogMemorySchema),
	]);

	const posts: BlogPost[] = [];
	for (const file of files) {
		const raw = await readMarkdown(file);
		if (!raw) continue;
		const parsed = parseFrontmatter(raw, BlogFrontmatterSchema);
		if (parsed) {
			const slug = parsed.frontmatter.slug ?? basename(file, ".md");
			const memoryPost = blogMemory?.posts.find((p) => p.slug === slug);
			posts.push({
				slug,
				title: parsed.frontmatter.title ?? slug,
				postType: parsed.frontmatter.post_type ?? "unknown",
				date: parsed.frontmatter.date ?? "",
				tags: parsed.frontmatter.tags,
				themes: parsed.frontmatter.themes,
				filename: basename(file),
				platformsPublished: memoryPost?.platforms_published ?? [],
			});
		}
	}

	posts.sort((a, b) => b.date.localeCompare(a.date));
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

	return c.json({
		meta: {
			slug,
			title: parsed.frontmatter.title ?? slug,
			postType: parsed.frontmatter.post_type ?? "unknown",
			date: parsed.frontmatter.date ?? "",
			tags: parsed.frontmatter.tags,
			themes: parsed.frontmatter.themes,
			filename: basename(match),
			platformsPublished: memoryPost?.platforms_published ?? [],
		},
		content: parsed.content,
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
