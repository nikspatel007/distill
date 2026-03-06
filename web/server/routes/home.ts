import { readFile, writeFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { convertToModelMessages, stepCountIs, streamText } from "ai";
import { Hono } from "hono";
import { z } from "zod";
import {
	BlogMemorySchema,
	BlogStateSchema,
	type BriefingPublishItem,
	ContentItemsResponseSchema,
	type DailyBriefing,
	DiscoveryResultSchema,
	IntakeFrontmatterSchema,
	JournalFrontmatterSchema,
	type ReadingItemBrief,
	ReadingBriefSchema,
	SeedIdeaSchema,
} from "../../shared/schemas.js";
import { getModel, isAgentConfigured } from "../lib/agent.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readJson, readMarkdown } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { createPost, isPostizConfigured, listIntegrations } from "../lib/postiz.js";

const app = new Hono();

const TARGET_PLATFORMS = ["twitter", "linkedin", "reddit"] as const;

const HomeChatRequestSchema = z.object({
	messages: z.array(z.any()),
	date: z.string().default("today"),
});

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
	const [journalFiles, intakeRaw, seedsRaw, blogMemory, blogState, intakeArchive, readingBriefRaw, discoveriesRaw] =
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
			readJson(join(OUTPUT_DIR, ".distill-reading-brief.json"), z.array(ReadingBriefSchema)),
			readJson(join(OUTPUT_DIR, ".distill-discoveries.json"), z.array(DiscoveryResultSchema)),
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

	// --- Reading brief ---
	let readingBrief = null;
	if (readingBriefRaw) {
		const match = readingBriefRaw.find((b) => b.date === date);
		if (match) readingBrief = match;
	}

	// --- Discoveries ---
	let discovery = null;
	if (discoveriesRaw) {
		const match = discoveriesRaw.find((d) => d.date === date);
		if (match) discovery = match;
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
		readingBrief,
		discovery,
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

app.patch("/api/home/drafts/:date/:platform", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const date = c.req.param("date");
	const platform = c.req.param("platform");
	const { content } = await c.req.json<{ content: string }>();

	const briefPath = join(OUTPUT_DIR, ".distill-reading-brief.json");
	const raw = await readFile(briefPath, "utf-8").catch(() => "[]");
	const briefs = JSON.parse(raw) as Array<Record<string, unknown>>;

	const briefIdx = briefs.findIndex((b) => b.date === date);
	if (briefIdx === -1) return c.json({ error: "Brief not found" }, 404);

	const brief = briefs[briefIdx] as Record<string, unknown>;
	const drafts = (brief.drafts as Array<Record<string, unknown>>) ?? [];
	const draftIdx = drafts.findIndex((d) => d.platform === platform);

	if (draftIdx === -1) {
		drafts.push({ platform, content, char_count: content.length, source_highlights: [] });
	} else {
		drafts[draftIdx] = { ...drafts[draftIdx], content, char_count: content.length };
	}

	brief.drafts = drafts;
	briefs[briefIdx] = brief;
	await writeFile(briefPath, JSON.stringify(briefs, null, 2));

	return c.json({ success: true });
});

app.post("/api/home/drafts/:date/:platform/publish", async (c) => {
	if (!isPostizConfigured()) {
		return c.json({ error: "Postiz not configured" }, 503);
	}

	const date = c.req.param("date");
	const platform = c.req.param("platform");
	const { OUTPUT_DIR } = getConfig();

	// Load the draft content
	const briefPath = join(OUTPUT_DIR, ".distill-reading-brief.json");
	const raw = await readFile(briefPath, "utf-8").catch(() => "[]");
	const briefs = JSON.parse(raw) as Array<Record<string, unknown>>;
	const brief = briefs.find((b) => b.date === date);
	if (!brief) return c.json({ error: "Brief not found" }, 404);

	const drafts = (brief.drafts as Array<Record<string, unknown>>) ?? [];
	const draft = drafts.find((d) => d.platform === platform);
	if (!draft) return c.json({ error: "Draft not found" }, 404);

	const content = draft.content as string;

	// Map platform to Postiz provider
	const providerMap: Record<string, string> = {
		linkedin: "linkedin",
		x: "x",
		twitter: "x",
	};
	const provider = providerMap[platform] ?? platform;

	// Find matching integration
	const integrations = await listIntegrations();
	const matching = integrations.filter(
		(i) => i.provider.toLowerCase().includes(provider),
	);

	if (matching.length === 0) {
		return c.json({ error: `No ${provider} integration found in Postiz` }, 404);
	}

	const integrationIds = matching.map((i) => i.id);
	await createPost(content, integrationIds, { postType: "draft", provider });

	return c.json({ success: true, platform: provider, integrations: matching.length });
});

app.post("/api/home/chat", async (c) => {
	if (!isAgentConfigured()) {
		return c.json({ error: "ANTHROPIC_API_KEY not configured" }, 503);
	}

	const body = await c.req.json();
	const { messages, date } = HomeChatRequestSchema.parse(body);
	const { OUTPUT_DIR } = getConfig();

	// Resolve date
	let resolvedDate = date;
	if (resolvedDate === "today") {
		const latestDate = await findLatestDate(OUTPUT_DIR);
		resolvedDate = latestDate ?? new Date().toISOString().split("T")[0] ?? "";
	}

	// Load context in parallel
	const [readingBriefRaw, discoveriesRaw, memoryRaw, journalFiles] = await Promise.all([
		readJson(join(OUTPUT_DIR, ".distill-reading-brief.json"), z.array(ReadingBriefSchema)),
		readJson(join(OUTPUT_DIR, ".distill-discoveries.json"), z.array(DiscoveryResultSchema)),
		readFile(join(OUTPUT_DIR, ".unified-memory.json"), "utf-8").catch(() => "{}"),
		listFiles(join(OUTPUT_DIR, "journal"), new RegExp(`^journal-${resolvedDate}.*\\.md$`)),
	]);

	// Build context sections
	const contextSections: string[] = [];

	// Reading brief
	const brief = readingBriefRaw?.find((b) => b.date === resolvedDate);
	if (brief) {
		contextSections.push("## Today's Reading Brief");
		for (const h of brief.highlights) {
			contextSections.push(`- **${h.title}** (${h.source}): ${h.summary}`);
		}
		if (brief.connection) {
			contextSections.push(`\n**Connection:** ${brief.connection.explanation}`);
		}
		if (brief.learning_pulse.length > 0) {
			contextSections.push("\n**Learning Pulse:**");
			for (const t of brief.learning_pulse) {
				contextSections.push(`- ${t.topic}: ${t.status} (${t.count} mentions)`);
			}
		}
	}

	// Discoveries
	const discovery = discoveriesRaw?.find((d) => d.date === resolvedDate);
	if (discovery && discovery.items.length > 0) {
		contextSections.push("\n## Recommended Reading");
		for (const item of discovery.items) {
			contextSections.push(`- [${item.title}](${item.url}) — ${item.summary}`);
		}
	}

	// Memory threads
	try {
		const memory = JSON.parse(memoryRaw);
		const threads = memory.threads ?? [];
		if (threads.length > 0) {
			contextSections.push("\n## Active Learning Threads");
			for (const thread of threads.slice(0, 5)) {
				contextSections.push(`- **${thread.theme ?? thread.name ?? "Thread"}**: ${thread.summary ?? ""}`);
			}
		}
	} catch {}

	// Journal
	if (journalFiles.length > 0) {
		const journalPath = journalFiles[0] ?? "";
		const journalRaw = await readMarkdown(journalPath);
		if (journalRaw) {
			contextSections.push("\n## Today's Journal");
			contextSections.push(journalRaw.slice(0, 1500));
		}
	}

	const contextText = contextSections.join("\n");

	const systemPrompt = `You are the user's personal intelligence assistant for Distill — a system that ingests everything they read and build, then synthesizes highlights and tracks their learning trajectory.

You have access to today's reading brief, learning pulse, active threads, and journal. Answer questions about their reading patterns, help them connect ideas, and suggest angles worth exploring.

## Today's Context (${resolvedDate})

${contextText || "No data available for this date yet. The user may need to run the pipeline first."}

## Guidelines
- Be concise and conversational — this is a mobile-friendly chat
- Reference specific articles, topics, and connections from the context
- When asked about patterns, reference the learning pulse data
- When asked what to explore, reference the discovery recommendations
- Help the user connect dots between what they're reading and building
- Keep responses under 200 words unless the user asks for detail`;

	const modelMessages = await convertToModelMessages(
		messages as Parameters<typeof convertToModelMessages>[0],
	);

	const result = streamText({
		model: getModel(),
		system: systemPrompt,
		messages: modelMessages,
		stopWhen: stepCountIs(3),
	});

	return result.toUIMessageStreamResponse();
});

export default app;
