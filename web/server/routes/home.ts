import { readFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { Hono } from "hono";
import {
	BlogMemorySchema,
	BlogStateSchema,
	type BriefingPublishItem,
	ContentItemsResponseSchema,
	type DailyBriefing,
	IntakeFrontmatterSchema,
	JournalFrontmatterSchema,
	type ReadingItemBrief,
	SeedIdeaSchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readJson, readMarkdown } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";

const app = new Hono();

const TARGET_PLATFORMS = ["twitter", "linkedin", "reddit"] as const;

/**
 * Find the latest journal date by scanning journal filenames.
 */
async function findLatestDate(outputDir: string): Promise<string | null> {
	const files = await listFiles(join(outputDir, "journal"), /^journal-.*\.md$/);
	const dates = files
		.map((f) => f.match(/journal-(\d{4}-\d{2}-\d{2})/)?.[1])
		.filter((d): d is string => d !== null)
		.sort()
		.reverse();
	return dates[0] ?? null;
}

/**
 * Find the latest intake archive date.
 */
async function findLatestArchiveDate(outputDir: string): Promise<string | null> {
	const files = await listFiles(join(outputDir, "intake", "archive"), /^\d{4}-\d{2}-\d{2}\.json$/);
	const dates = files
		.map((f) => basename(f, ".json"))
		.filter((d): d is string => d !== null)
		.sort()
		.reverse();
	return dates[0] ?? null;
}

app.get("/api/home/:date", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	let date = c.req.param("date");

	// Resolve "today" to the latest available journal date
	if (date === "today") {
		const latestDate = await findLatestDate(OUTPUT_DIR);
		if (!latestDate) {
			// No journal files at all — return empty briefing for today's date
			const today = new Date().toISOString().split("T")[0] ?? date;
			date = today;
		} else {
			date = latestDate;
		}
	}

	// Load all data in parallel
	const [journalFiles, intakeRaw, seedsRaw, blogMemory, blogState, intakeArchive] =
		await Promise.all([
			listFiles(join(OUTPUT_DIR, "journal"), new RegExp(`^journal-${date}.*\\.md$`)),
			readMarkdown(join(OUTPUT_DIR, "intake", `intake-${date}.md`)),
			readFile(join(OUTPUT_DIR, ".distill-seeds.json"), "utf-8").catch(() => "[]"),
			readJson(join(OUTPUT_DIR, "blog", ".blog-memory.json"), BlogMemorySchema),
			readJson(join(OUTPUT_DIR, "blog", ".blog-state.json"), BlogStateSchema),
			readJson(
				join(OUTPUT_DIR, "intake", "archive", `${date}.json`),
				ContentItemsResponseSchema,
			),
		]);

	// --- Journal brief ---
	let journalBrief: string[] = [];
	let hasFullEntry = false;
	let sessionsCount = 0;
	let durationMinutes = 0;

	if (journalFiles.length > 0) {
		const journalPath = journalFiles[0] ?? "";
		const journalRaw = await readMarkdown(journalPath);
		if (journalRaw) {
			hasFullEntry = true;
			const parsed = parseFrontmatter(journalRaw, JournalFrontmatterSchema);
			if (parsed) {
				journalBrief = parsed.frontmatter.brief;
				sessionsCount = parsed.frontmatter.sessions_count;
				durationMinutes = parsed.frontmatter.duration_minutes;
			}
		}
	}

	// --- Intake highlights ---
	let highlights: string[] = [];
	let itemCount = 0;
	let hasFullDigest = false;

	if (intakeRaw) {
		hasFullDigest = true;
		const parsed = parseFrontmatter(intakeRaw, IntakeFrontmatterSchema);
		if (parsed) {
			highlights = parsed.frontmatter.highlights;
			itemCount = parsed.frontmatter.items || parsed.frontmatter.item_count;
		}
	}

	// --- Seeds (unused only) ---
	let seeds: Array<{ id: string; text: string; tags: string[]; created_at: string; used: boolean; used_in: string | null }> = [];
	try {
		const rawSeeds = JSON.parse(seedsRaw) as unknown[];
		const parsed = rawSeeds
			.map((s) => {
				try {
					return SeedIdeaSchema.parse(s);
				} catch {
					return null;
				}
			})
			.filter((s): s is NonNullable<typeof s> => s !== null);
		seeds = parsed.filter((s) => !s.used);
	} catch {}

	// --- Reading items (from intake archive) ---
	let readingItems: ReadingItemBrief[] = [];
	let archiveData = intakeArchive;

	// If no archive for the exact date, try the latest available
	if (!archiveData) {
		const latestArchiveDate = await findLatestArchiveDate(OUTPUT_DIR);
		if (latestArchiveDate) {
			archiveData = await readJson(
				join(OUTPUT_DIR, "intake", "archive", `${latestArchiveDate}.json`),
				ContentItemsResponseSchema,
			);
		}
	}

	if (archiveData) {
		// Filter to actual reading content (not coding sessions)
		const READING_SOURCES = new Set(["rss", "browser", "substack", "reddit", "gmail"]);
		readingItems = archiveData.items
			.filter((item) => READING_SOURCES.has(item.source) && item.url)
			.slice(0, 10)
			.map((item) => ({
				id: item.id,
				title: item.title,
				url: item.url,
				source: item.source,
				excerpt: item.excerpt,
				site_name: item.site_name,
				word_count: item.word_count,
			}));
	}

	// --- Publish queue (deduplicated: one entry per post) ---
	const publishQueue: BriefingPublishItem[] = [];
	const memoryPosts = blogMemory?.posts ?? [];
	const statePosts = blogState?.posts ?? [];

	if (memoryPosts.length > 0) {
		for (const post of memoryPosts) {
			const publishedCount = TARGET_PLATFORMS.filter((p) =>
				post.platforms_published.includes(p),
			).length;
			const total = TARGET_PLATFORMS.length;
			publishQueue.push({
				slug: post.slug,
				title: post.title,
				type: post.post_type,
				status: publishedCount === total ? "published" : "draft",
				platforms_published: publishedCount,
				platforms_ready: publishedCount,
				platforms_total: total,
			});
		}
	} else {
		for (const post of statePosts) {
			publishQueue.push({
				slug: post.slug,
				title: post.slug,
				type: post.post_type,
				status: "draft",
				platforms_published: 0,
				platforms_ready: 0,
				platforms_total: TARGET_PLATFORMS.length,
			});
		}
	}

	const response: DailyBriefing = {
		date,
		journal: {
			brief: journalBrief,
			hasFullEntry,
			date,
			sessionsCount,
			durationMinutes,
		},
		intake: {
			highlights,
			itemCount,
			hasFullDigest,
			date,
		},
		publishQueue,
		seeds,
		readingItems,
	};

	return c.json(response);
});

/**
 * POST /api/home/brainstorm — assemble today's context into a Studio draft for brainstorming.
 */
app.post("/api/home/brainstorm", async (c) => {
	const { OUTPUT_DIR } = getConfig();

	// Find latest journal date
	const latestDate = await findLatestDate(OUTPUT_DIR);
	const date = latestDate ?? new Date().toISOString().split("T")[0] ?? "";

	// Load data in parallel
	const [journalFiles, intakeRaw, seedsRaw, archiveData] = await Promise.all([
		listFiles(join(OUTPUT_DIR, "journal"), new RegExp(`^journal-${date}.*\\.md$`)),
		readMarkdown(join(OUTPUT_DIR, "intake", `intake-${date}.md`)),
		readFile(join(OUTPUT_DIR, ".distill-seeds.json"), "utf-8").catch(() => "[]"),
		readJson(
			join(OUTPUT_DIR, "intake", "archive", `${date}.json`),
			ContentItemsResponseSchema,
		),
	]);

	const sections: string[] = [];
	const today = new Date().toLocaleDateString("en-US", {
		weekday: "long",
		month: "long",
		day: "numeric",
		year: "numeric",
	});
	sections.push(`# Brainstorm — ${today}\n`);
	sections.push(
		"Use everything below to help me figure out what to write about today. Suggest 3-5 angles with a one-line pitch for each, then let's discuss.\n",
	);

	// Journal
	if (journalFiles.length > 0) {
		const journalPath = journalFiles[0] ?? "";
		const journalRaw = await readMarkdown(journalPath);
		if (journalRaw) {
			const parsed = parseFrontmatter(journalRaw, JournalFrontmatterSchema);
			if (parsed) {
				sections.push("## What I built today\n");
				for (const b of parsed.frontmatter.brief) {
					sections.push(`- ${b}`);
				}
				sections.push("");
			}
		}
	}

	// Intake highlights
	if (intakeRaw) {
		const parsed = parseFrontmatter(intakeRaw, IntakeFrontmatterSchema);
		if (parsed?.frontmatter.highlights.length) {
			sections.push("## Intake highlights\n");
			for (const h of parsed.frontmatter.highlights) {
				sections.push(`- ${h}`);
			}
			sections.push("");
		}
	}

	// Top reading items
	if (archiveData) {
		const READING_SOURCES = new Set(["rss", "browser", "substack", "reddit", "gmail"]);
		const readItems = archiveData.items
			.filter((item) => READING_SOURCES.has(item.source) && item.url)
			.slice(0, 10);
		if (readItems.length > 0) {
			sections.push("## What I read\n");
			for (const item of readItems) {
				const excerpt =
					item.excerpt && item.excerpt !== item.title ? ` — ${item.excerpt.slice(0, 120)}` : "";
				sections.push(`- [${item.title}](${item.url}) (${item.site_name || item.source})${excerpt}`);
			}
			sections.push("");
		}
	}

	// Seeds
	try {
		const rawSeeds = JSON.parse(seedsRaw) as unknown[];
		const unused = rawSeeds
			.map((s) => {
				try {
					return SeedIdeaSchema.parse(s);
				} catch {
					return null;
				}
			})
			.filter((s): s is NonNullable<typeof s> => s !== null && !s.used);
		if (unused.length > 0) {
			sections.push("## Seed ideas\n");
			for (const seed of unused) {
				sections.push(`- ${seed.text}`);
			}
			sections.push("");
		}
	} catch {}

	const body = sections.join("\n");

	return c.json({ title: `Brainstorm — ${date}`, body, date });
});

export default app;
