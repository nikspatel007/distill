import { basename, join } from "node:path";
import { Hono } from "hono";
import {
	ContentItemsResponseSchema,
	type IntakeDigest,
	IntakeFrontmatterSchema,
	SaveMarkdownSchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readJson, readMarkdown, writeMarkdown } from "../lib/files.js";
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

app.get("/api/reading/items", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const dateParam = c.req.query("date");
	const sourceParam = c.req.query("source");
	const pageParam = Number.parseInt(c.req.query("page") ?? "1", 10);
	const limitParam = Number.parseInt(c.req.query("limit") ?? "50", 10);
	const page = Number.isNaN(pageParam) || pageParam < 1 ? 1 : pageParam;
	const limit = Number.isNaN(limitParam) || limitParam < 1 ? 50 : Math.min(limitParam, 200);

	// If no date, list available archive dates
	if (!dateParam) {
		const files = await listFiles(
			join(OUTPUT_DIR, "intake", "archive"),
			/^\d{4}-\d{2}-\d{2}\.json$/,
		);
		const dates = files
			.map((f) => basename(f, ".json"))
			.sort()
			.reverse();
		return c.json({ dates, items: [], item_count: 0, available_sources: [] });
	}

	const archivePath = join(OUTPUT_DIR, "intake", "archive", `${dateParam}.json`);
	const archive = await readJson(archivePath, ContentItemsResponseSchema);

	if (!archive) {
		return c.json({
			date: dateParam,
			item_count: 0,
			items: [],
			available_sources: [],
			page: 1,
			total_pages: 1,
			total_items: 0,
		});
	}

	// Compute available_sources from ALL items before filtering
	const availableSources = [...new Set(archive.items.map((i) => i.source))].sort();

	// Filter by source if requested
	const filtered = sourceParam
		? archive.items.filter((i) => i.source === sourceParam)
		: archive.items;

	// Apply pagination AFTER source filtering
	const totalItems = filtered.length;
	const totalPages = Math.max(1, Math.ceil(totalItems / limit));
	const safePage = Math.min(page, totalPages);
	const start = (safePage - 1) * limit;
	const items = filtered.slice(start, start + limit);

	return c.json({
		date: archive.date,
		item_count: items.length,
		items,
		available_sources: availableSources,
		page: safePage,
		total_pages: totalPages,
		total_items: totalItems,
	});
});

export default app;
