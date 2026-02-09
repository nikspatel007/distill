import { basename, join } from "node:path";
import { Hono } from "hono";
import {
	type IntakeDigest,
	IntakeFrontmatterSchema,
	SaveMarkdownSchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readMarkdown, writeMarkdown } from "../lib/files.js";
import { parseFrontmatter, reconstructMarkdown } from "../lib/frontmatter.js";

const app = new Hono();

app.get("/api/reading/digests", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const files = await listFiles(join(OUTPUT_DIR, "intake"), /^intake-.*\.md$/);

	const digests: IntakeDigest[] = [];
	for (const file of files) {
		const raw = await readMarkdown(file);
		if (!raw) continue;
		const parsed = parseFrontmatter(raw, IntakeFrontmatterSchema);
		if (parsed) {
			digests.push({
				date: parsed.frontmatter.date ?? "",
				sources: parsed.frontmatter.sources,
				itemCount: parsed.frontmatter.item_count,
				tags: parsed.frontmatter.tags,
				filename: basename(file),
			});
		}
	}

	digests.sort((a, b) => b.date.localeCompare(a.date));
	return c.json({ digests });
});

app.get("/api/reading/digests/:date", async (c) => {
	const date = c.req.param("date");
	const { OUTPUT_DIR } = getConfig();
	const files = await listFiles(join(OUTPUT_DIR, "intake"), new RegExp(`^intake-${date}.*\\.md$`));

	if (files.length === 0) return c.json({ error: "Digest not found" }, 404);

	const file = files[0];
	if (!file) return c.json({ error: "Digest not found" }, 404);
	const raw = await readMarkdown(file);
	if (!raw) return c.json({ error: "Could not read file" }, 500);

	const parsed = parseFrontmatter(raw, IntakeFrontmatterSchema);
	if (!parsed) return c.json({ error: "Could not parse frontmatter" }, 500);

	return c.json({
		meta: {
			date: parsed.frontmatter.date ?? "",
			sources: parsed.frontmatter.sources,
			itemCount: parsed.frontmatter.item_count,
			tags: parsed.frontmatter.tags,
			filename: basename(file),
		},
		content: parsed.content,
	});
});

app.put("/api/reading/digests/:date", async (c) => {
	const date = c.req.param("date");
	const { OUTPUT_DIR } = getConfig();

	const body = await c.req.json();
	const parsed = SaveMarkdownSchema.safeParse(body);
	if (!parsed.success) return c.json({ error: "Invalid request body" }, 400);

	const files = await listFiles(join(OUTPUT_DIR, "intake"), new RegExp(`^intake-${date}.*\\.md$`));

	if (files.length === 0) return c.json({ error: "Digest not found" }, 404);

	const file = files[0];
	if (!file) return c.json({ error: "Digest not found" }, 404);
	const raw = await readMarkdown(file);
	if (!raw) return c.json({ error: "Could not read file" }, 500);

	const updated = reconstructMarkdown(raw, parsed.data.content);

	try {
		await writeMarkdown(file, updated, OUTPUT_DIR);
	} catch (err) {
		const message = err instanceof Error ? err.message : "Write failed";
		return c.json({ error: message }, 403);
	}

	return c.json({ success: true });
});

export default app;
