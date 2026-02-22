import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Hono } from "hono";
import {
	BlogMemorySchema,
	BlogStateSchema,
	type BriefingPublishItem,
	type DailyBriefing,
	IntakeFrontmatterSchema,
	JournalFrontmatterSchema,
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
	const [journalFiles, intakeRaw, seedsRaw, blogMemory, blogState] = await Promise.all([
		listFiles(join(OUTPUT_DIR, "journal"), new RegExp(`^journal-${date}.*\\.md$`)),
		readMarkdown(join(OUTPUT_DIR, "intake", `intake-${date}.md`)),
		readFile(join(OUTPUT_DIR, ".distill-seeds.json"), "utf-8").catch(() => "[]"),
		readJson(join(OUTPUT_DIR, "blog", ".blog-memory.json"), BlogMemorySchema),
		readJson(join(OUTPUT_DIR, "blog", ".blog-state.json"), BlogStateSchema),
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

	// --- Publish queue ---
	const publishQueue: BriefingPublishItem[] = [];
	const memoryPosts = blogMemory?.posts ?? [];
	const statePosts = blogState?.posts ?? [];

	if (memoryPosts.length > 0) {
		for (const post of memoryPosts) {
			for (const platform of TARGET_PLATFORMS) {
				publishQueue.push({
					slug: post.slug,
					title: post.title,
					type: platform,
					status: post.platforms_published.includes(platform) ? "published" : "draft",
				});
			}
		}
	} else {
		for (const post of statePosts) {
			for (const platform of TARGET_PLATFORMS) {
				publishQueue.push({
					slug: post.slug,
					title: post.slug,
					type: platform,
					status: "draft",
				});
			}
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
	};

	return c.json(response);
});

export default app;
