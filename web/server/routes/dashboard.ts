import { readFile } from "node:fs/promises";
import { join } from "node:path";
import { Hono } from "hono";
import {
	BlogMemorySchema,
	BlogStateSchema,
	type DashboardResponse,
	JournalFrontmatterSchema,
	UnifiedMemorySchema,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readJson } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";

const app = new Hono();

app.get("/api/dashboard", async (c) => {
	const { OUTPUT_DIR } = getConfig();

	// Load data files in parallel
	const [memory, blogMemory, blogState, journalFiles, intakeFiles, seedsRaw, notesRaw] =
		await Promise.all([
			readJson(join(OUTPUT_DIR, ".distill-memory.json"), UnifiedMemorySchema),
			readJson(join(OUTPUT_DIR, "blog", ".blog-memory.json"), BlogMemorySchema),
			readJson(join(OUTPUT_DIR, "blog", ".blog-state.json"), BlogStateSchema),
			listFiles(join(OUTPUT_DIR, "journal"), /^journal-.*\.md$/),
			listFiles(join(OUTPUT_DIR, "intake"), /^intake-.*\.md$/),
			readFile(join(OUTPUT_DIR, ".distill-seeds.json"), "utf-8").catch(() => "[]"),
			readFile(join(OUTPUT_DIR, ".distill-notes.json"), "utf-8").catch(() => "[]"),
		]);

	// Count seeds and notes
	let seedCount = 0;
	let activeNoteCount = 0;
	try {
		const seeds = JSON.parse(seedsRaw) as Array<{ used?: boolean }>;
		seedCount = seeds.filter((s) => !s.used).length;
	} catch {}
	try {
		const notes = JSON.parse(notesRaw) as Array<{ used?: boolean }>;
		activeNoteCount = notes.filter((n) => !n.used).length;
	} catch {}

	// Parse recent journals for metadata
	const recentJournalFiles = journalFiles.slice(-5).reverse();
	const recentJournals = [];
	for (const file of recentJournalFiles) {
		const raw = await readFile(file, "utf-8").catch(() => null);
		if (!raw) continue;
		const parsed = parseFrontmatter(raw, JournalFrontmatterSchema);
		if (parsed) {
			recentJournals.push({
				date: parsed.frontmatter.date,
				style: parsed.frontmatter.style,
				sessionsCount: parsed.frontmatter.sessions_count,
				durationMinutes: parsed.frontmatter.duration_minutes,
				projects: parsed.frontmatter.projects,
			});
		}
	}

	// Compute pending publish count: blog posts that have platforms NOT yet published
	const allPlatforms = ["twitter", "linkedin", "reddit"];
	let pendingPublish = 0;
	const blogPosts = blogMemory?.posts ?? [];
	for (const post of blogPosts) {
		const published = post.platforms_published;
		for (const platform of allPlatforms) {
			if (!published.includes(platform)) {
				pendingPublish++;
			}
		}
	}

	const threads = memory?.threads ?? [];
	const published = memory?.published ?? [];
	const statePosts = blogState?.posts ?? [];

	const response: DashboardResponse = {
		journalCount: journalFiles.length,
		blogCount: statePosts.length,
		intakeCount: intakeFiles.length,
		pendingPublish,
		recentJournals: recentJournals.map((j) => ({
			date: j.date,
			style: j.style ?? "dev-journal",
			sessionsCount: j.sessionsCount ?? 0,
			durationMinutes: j.durationMinutes ?? 0,
			projects: j.projects ?? [],
		})),
		activeThreads: threads
			.filter((t) => t.status === "active")
			.slice(0, 10)
			.map((t) => ({
				name: t.name,
				summary: t.summary,
				status: t.status ?? "active",
				first_seen: t.first_seen,
				last_seen: t.last_seen,
				mention_count: t.mention_count ?? 1,
			})),
		recentlyPublished: published
			.slice(-5)
			.reverse()
			.map((p) => ({
				slug: p.slug,
				title: p.title,
				post_type: p.post_type,
				date: p.date,
				platforms: p.platforms ?? [],
			})),
		seedCount,
		activeNoteCount,
	};

	return c.json(response);
});

export default app;
