/**
 * Config routes -- read/write .distill.toml from the web UI.
 */
import { dirname } from "node:path";
import { Hono } from "hono";
import { getConfig } from "../lib/config.js";
import { readConfig, writeConfig } from "../lib/toml.js";

const configRoutes = new Hono();

function getProjectDir(): string {
	const config = getConfig();
	if (config.PROJECT_DIR) return config.PROJECT_DIR;
	// Fall back to parent of OUTPUT_DIR or CWD
	return dirname(config.OUTPUT_DIR) || process.cwd();
}

configRoutes.get("/api/config", async (c) => {
	const projectDir = getProjectDir();
	const config = await readConfig(projectDir);
	return c.json(config);
});

configRoutes.put("/api/config", async (c) => {
	const projectDir = getProjectDir();
	const existing = await readConfig(projectDir);
	const updates = (await c.req.json()) as Record<string, unknown>;

	// Deep merge: only merge top-level sections that are provided
	const merged = { ...existing };
	for (const [key, value] of Object.entries(updates)) {
		if (value !== null && typeof value === "object" && !Array.isArray(value)) {
			merged[key as keyof typeof merged] = {
				...((existing[key as keyof typeof existing] as Record<string, unknown>) ?? {}),
				...(value as Record<string, unknown>),
			} as never;
		} else {
			(merged as Record<string, unknown>)[key] = value;
		}
	}

	await writeConfig(projectDir, merged);
	return c.json(merged);
});

configRoutes.get("/api/config/sources", async (c) => {
	const projectDir = getProjectDir();
	const config = await readConfig(projectDir);

	const sources = [
		{ source: "rss", configured: true, label: "RSS Feeds" },
		{
			source: "browser",
			configured: config.intake?.browser_history ?? false,
			label: "Browser History",
		},
		{
			source: "substack",
			configured: (config.intake?.substack_blogs ?? []).length > 0,
			label: "Substack",
		},
		{ source: "linkedin", configured: false, label: "LinkedIn" },
		{ source: "twitter", configured: false, label: "Twitter/X" },
		{ source: "reddit", configured: Boolean(config.reddit?.client_id), label: "Reddit" },
		{ source: "youtube", configured: Boolean(config.youtube?.api_key), label: "YouTube" },
		{ source: "gmail", configured: false, label: "Gmail" },
	];

	return c.json({ sources });
});

export default configRoutes;
