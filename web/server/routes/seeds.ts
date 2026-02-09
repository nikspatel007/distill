import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";
import { CreateSeedSchema, type SeedIdea, SeedIdeaSchema } from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";

const app = new Hono();

const SEEDS_FILE = ".distill-seeds.json";

async function loadSeeds(outputDir: string): Promise<SeedIdea[]> {
	try {
		const raw = await readFile(join(outputDir, SEEDS_FILE), "utf-8");
		return z.array(SeedIdeaSchema).parse(JSON.parse(raw));
	} catch {
		return [];
	}
}

async function saveSeeds(outputDir: string, seeds: SeedIdea[]): Promise<void> {
	await mkdir(outputDir, { recursive: true });
	await writeFile(join(outputDir, SEEDS_FILE), JSON.stringify(seeds, null, 2), "utf-8");
}

app.get("/api/seeds", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const seeds = await loadSeeds(OUTPUT_DIR);
	return c.json({ seeds });
});

app.post("/api/seeds", zValidator("json", CreateSeedSchema), async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const body = c.req.valid("json");
	const seeds = await loadSeeds(OUTPUT_DIR);

	const id = Math.random().toString(36).slice(2, 14);
	const newSeed: SeedIdea = {
		id,
		text: body.text,
		tags: body.tags,
		created_at: new Date().toISOString(),
		used: false,
		used_in: null,
	};

	seeds.push(newSeed);
	await saveSeeds(OUTPUT_DIR, seeds);
	return c.json(newSeed, 201);
});

app.delete("/api/seeds/:id", async (c) => {
	const id = c.req.param("id");
	const { OUTPUT_DIR } = getConfig();
	const seeds = await loadSeeds(OUTPUT_DIR);
	const filtered = seeds.filter((s) => s.id !== id);

	if (filtered.length === seeds.length) {
		return c.json({ error: "Seed not found" }, 404);
	}

	await saveSeeds(OUTPUT_DIR, filtered);
	return c.json({ success: true });
});

export default app;
