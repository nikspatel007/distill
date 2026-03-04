import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import type { Context } from "hono";
import { Hono } from "hono";
import { z } from "zod";
import { type ShareItem, ShareItemSchema } from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";

const app = new Hono();

const SHARES_FILE = ".distill-shares.json";

async function loadShares(outputDir: string): Promise<ShareItem[]> {
	try {
		const raw = await readFile(join(outputDir, SHARES_FILE), "utf-8");
		return z.array(ShareItemSchema).parse(JSON.parse(raw));
	} catch {
		return [];
	}
}

async function saveShares(outputDir: string, shares: ShareItem[]): Promise<void> {
	await mkdir(outputDir, { recursive: true });
	await writeFile(join(outputDir, SHARES_FILE), JSON.stringify(shares, null, 2), "utf-8");
}

app.get("/api/shares", async (c) => {
	// If ?url= is present, this is a save request from iOS Shortcuts
	const urlParam = c.req.query("url");
	if (urlParam !== undefined) {
		const url = urlParam.trim();
		if (!url) {
			return c.json({ error: "url is required" }, 400);
		}
		const { OUTPUT_DIR } = getConfig();
		const shares = await loadShares(OUTPUT_DIR);
		const id = Math.random().toString(36).slice(2, 14);
		const newShare: ShareItem = {
			id,
			url,
			note: c.req.query("note") ?? "",
			tags: [],
			created_at: new Date().toISOString(),
			used: false,
			used_in: null,
		};
		shares.push(newShare);
		await saveShares(OUTPUT_DIR, shares);
		return c.json(newShare, 201);
	}

	const { OUTPUT_DIR } = getConfig();
	const shares = await loadShares(OUTPUT_DIR);
	return c.json({ shares });
});

async function handleCreate(c: Context) {
	const { OUTPUT_DIR } = getConfig();

	let raw: Record<string, unknown>;
	try {
		raw = (await c.req.json()) as Record<string, unknown>;
	} catch {
		return c.json({ error: "Invalid JSON" }, 400);
	}

	const url = typeof raw.url === "string" ? raw.url.trim() : "";
	if (!url) {
		return c.json({ error: "url is required" }, 400);
	}

	const note = typeof raw.note === "string" ? raw.note : "";
	const tags = Array.isArray(raw.tags)
		? raw.tags.filter((t): t is string => typeof t === "string")
		: [];

	const shares = await loadShares(OUTPUT_DIR);
	const id = Math.random().toString(36).slice(2, 14);
	const newShare: ShareItem = {
		id,
		url,
		note,
		tags,
		created_at: new Date().toISOString(),
		used: false,
		used_in: null,
	};

	shares.push(newShare);
	await saveShares(OUTPUT_DIR, shares);
	return c.json(newShare, 201);
}

// Accept both with and without trailing slash (iOS Shortcuts adds trailing slash)
app.post("/api/shares", handleCreate);
app.post("/api/shares/", handleCreate);


app.get("/api/shares/:id", async (c) => {
	const id = c.req.param("id");
	const { OUTPUT_DIR } = getConfig();
	const shares = await loadShares(OUTPUT_DIR);
	const share = shares.find((s) => s.id === id);
	if (!share) {
		return c.json({ error: "Share not found" }, 404);
	}
	return c.json({ share });
});

app.delete("/api/shares/:id", async (c) => {
	const id = c.req.param("id");
	const { OUTPUT_DIR } = getConfig();
	const shares = await loadShares(OUTPUT_DIR);
	const filtered = shares.filter((s) => s.id !== id);

	if (filtered.length === shares.length) {
		return c.json({ error: "Share not found" }, 404);
	}

	await saveShares(OUTPUT_DIR, filtered);
	return c.json({ success: true });
});

export default app;
