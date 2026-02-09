import { join } from "node:path";
import { Hono } from "hono";
import { UnifiedMemorySchema } from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";
import { readJson } from "../lib/files.js";

const app = new Hono();

app.get("/api/memory", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const memory = await readJson(join(OUTPUT_DIR, ".distill-memory.json"), UnifiedMemorySchema);

	if (!memory) {
		return c.json({
			entries: [],
			threads: [],
			entities: {},
			published: [],
		});
	}

	return c.json(memory);
});

app.get("/api/memory/threads", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const memory = await readJson(join(OUTPUT_DIR, ".distill-memory.json"), UnifiedMemorySchema);
	const threads = memory?.threads ?? [];
	return c.json({ threads });
});

app.get("/api/memory/entities", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const memory = await readJson(join(OUTPUT_DIR, ".distill-memory.json"), UnifiedMemorySchema);
	const entities = memory?.entities ?? {};
	// Sort by mention count descending
	const sorted = Object.values(entities).sort(
		(a, b) => (b.mention_count ?? 1) - (a.mention_count ?? 1),
	);
	return c.json({ entities: sorted });
});

export default app;
