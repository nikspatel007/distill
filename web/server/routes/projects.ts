import { access, readFile } from "node:fs/promises";
import { basename, join } from "node:path";
import { Hono } from "hono";
import {
	type JournalEntry,
	JournalFrontmatterSchema,
	type ProjectSummary,
} from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { listFiles, readMarkdown } from "../lib/files.js";
import { parseFrontmatter } from "../lib/frontmatter.js";
import { loadBlogPosts, loadJournalEntries } from "../lib/loaders.js";
import { readConfig } from "../lib/toml.js";

const app = new Hono();

/** Load dedicated project journal entries from projects/{name}/journal/. */
async function loadProjectJournals(
	outputDir: string,
	projectName: string,
): Promise<JournalEntry[]> {
	const projectJournalDir = join(outputDir, "projects", projectName.toLowerCase(), "journal");
	let files: string[];
	try {
		files = await listFiles(projectJournalDir, /^journal-.*\.md$/);
	} catch {
		return [];
	}
	const entries: JournalEntry[] = [];
	for (const file of files) {
		const raw = await readMarkdown(file);
		if (!raw) continue;
		const parsed = parseFrontmatter(raw, JournalFrontmatterSchema);
		if (parsed) {
			entries.push({
				date: parsed.frontmatter.date,
				style: parsed.frontmatter.style,
				sessionsCount: parsed.frontmatter.sessions_count,
				durationMinutes: parsed.frontmatter.duration_minutes,
				tags: parsed.frontmatter.tags,
				projects: parsed.frontmatter.projects,
				filename: basename(file),
			});
		}
	}
	entries.sort((a, b) => b.date.localeCompare(a.date));
	return entries;
}

/** Check if a project note file exists. */
async function hasProjectNote(outputDir: string, projectName: string): Promise<boolean> {
	const slug = projectName.toLowerCase().replace(/[^a-z0-9]+/g, "-");
	const path = join(outputDir, "projects", `project-${slug}.md`);
	try {
		await access(path);
		return true;
	} catch {
		return false;
	}
}

/** Read project note content if it exists. */
async function readProjectNote(outputDir: string, projectName: string): Promise<string | null> {
	const slug = projectName.toLowerCase().replace(/[^a-z0-9]+/g, "-");
	const path = join(outputDir, "projects", `project-${slug}.md`);
	try {
		return await readFile(path, "utf-8");
	} catch {
		return null;
	}
}

app.get("/api/projects", async (c) => {
	const { OUTPUT_DIR, PROJECT_DIR } = getConfig();

	// Load config, journals, and blog posts in parallel
	const [tomlConfig, journals, blogs] = await Promise.all([
		readConfig(PROJECT_DIR || OUTPUT_DIR),
		loadJournalEntries(OUTPUT_DIR),
		loadBlogPosts(OUTPUT_DIR),
	]);

	// Collect all project names from config + frontmatter
	const configProjects = tomlConfig.projects ?? [];
	const configNames = new Set(configProjects.map((p) => p.name));

	const allProjectNames = new Set<string>(configNames);
	for (const j of journals) {
		for (const p of j.projects) allProjectNames.add(p);
	}
	for (const b of blogs) {
		for (const p of b.projects) allProjectNames.add(p);
	}

	// Check all project notes in parallel
	const projectNames = [...allProjectNames];
	const noteChecks = await Promise.all(
		projectNames.map(async (name) => [name, await hasProjectNote(OUTPUT_DIR, name)] as const),
	);
	const noteExists = new Map(noteChecks);

	// Build summaries
	const summaries: ProjectSummary[] = [];
	for (const name of allProjectNames) {
		const config = configProjects.find((p) => p.name === name);
		const projectJournals = journals.filter((j) => j.projects.includes(name));
		const projectBlogs = blogs.filter((b) => b.projects.includes(name));

		const totalSessions = projectJournals.reduce((s, j) => s + j.sessionsCount, 0);
		const totalDuration = projectJournals.reduce((s, j) => s + j.durationMinutes, 0);
		const dates = projectJournals.map((j) => j.date);
		const lastSeen = dates.length > 0 ? ([...dates].sort().reverse()[0] ?? "") : "";

		summaries.push({
			name,
			description: config?.description ?? "",
			url: config?.url ?? "",
			tags: config?.tags ?? [],
			journalCount: projectJournals.length,
			blogCount: projectBlogs.length,
			totalSessions,
			totalDurationMinutes: totalDuration,
			lastSeen,
			hasProjectNote: noteExists.get(name) ?? false,
		});
	}

	// Sort by last seen descending, then by name
	summaries.sort((a, b) => {
		if (a.lastSeen && b.lastSeen) return b.lastSeen.localeCompare(a.lastSeen);
		if (a.lastSeen) return -1;
		if (b.lastSeen) return 1;
		return a.name.localeCompare(b.name);
	});

	return c.json({ projects: summaries });
});

app.get("/api/projects/:name", async (c) => {
	const name = c.req.param("name");
	const { OUTPUT_DIR, PROJECT_DIR } = getConfig();

	const [tomlConfig, journals, blogs, noteContent, dedicatedJournals] = await Promise.all([
		readConfig(PROJECT_DIR || OUTPUT_DIR),
		loadJournalEntries(OUTPUT_DIR),
		loadBlogPosts(OUTPUT_DIR),
		readProjectNote(OUTPUT_DIR, name),
		loadProjectJournals(OUTPUT_DIR, name),
	]);

	const config = (tomlConfig.projects ?? []).find((p) => p.name === name);
	const projectJournals = journals.filter((j) => j.projects.includes(name));
	const projectBlogs = blogs.filter((b) => b.projects.includes(name));

	const totalSessions = projectJournals.reduce((s, j) => s + j.sessionsCount, 0);
	const totalDuration = projectJournals.reduce((s, j) => s + j.durationMinutes, 0);
	const allDates = [...projectJournals.map((j) => j.date), ...dedicatedJournals.map((j) => j.date)];
	const lastSeen = allDates.length > 0 ? ([...allDates].sort().reverse()[0] ?? "") : "";

	// If no config and no data, 404
	if (
		!config &&
		projectJournals.length === 0 &&
		projectBlogs.length === 0 &&
		dedicatedJournals.length === 0
	) {
		return c.json({ error: "Project not found" }, 404);
	}

	return c.json({
		summary: {
			name,
			description: config?.description ?? "",
			url: config?.url ?? "",
			tags: config?.tags ?? [],
			journalCount: projectJournals.length,
			blogCount: projectBlogs.length,
			totalSessions,
			totalDurationMinutes: totalDuration,
			lastSeen,
			hasProjectNote: noteContent !== null,
		},
		journals: projectJournals,
		blogs: projectBlogs,
		projectNoteContent: noteContent,
		projectJournals: dedicatedJournals,
	});
});

/** Read a specific project journal entry by date. */
app.get("/api/projects/:name/journal/:date", async (c) => {
	const name = c.req.param("name");
	const date = c.req.param("date");
	const { OUTPUT_DIR } = getConfig();

	const projectJournalDir = join(OUTPUT_DIR, "projects", name.toLowerCase(), "journal");
	const files = await listFiles(projectJournalDir, new RegExp(`^journal-${date}.*\\.md$`));

	if (files.length === 0) {
		return c.json({ error: "Project journal entry not found" }, 404);
	}

	const file = files[0];
	if (!file) return c.json({ error: "Project journal entry not found" }, 404);
	const raw = await readMarkdown(file);
	if (!raw) return c.json({ error: "Could not read file" }, 500);

	const parsed = parseFrontmatter(raw, JournalFrontmatterSchema);
	if (!parsed) return c.json({ error: "Could not parse frontmatter" }, 500);

	return c.json({
		meta: {
			date: parsed.frontmatter.date,
			style: parsed.frontmatter.style,
			sessionsCount: parsed.frontmatter.sessions_count,
			durationMinutes: parsed.frontmatter.duration_minutes,
			tags: parsed.frontmatter.tags,
			projects: parsed.frontmatter.projects,
			filename: basename(file),
		},
		content: parsed.content,
		project: name,
	});
});

export default app;
