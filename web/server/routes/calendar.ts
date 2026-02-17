import { readFile, readdir } from "node:fs/promises";
import { join } from "node:path";
import { Hono } from "hono";
import { getConfig } from "../lib/config.js";

const app = new Hono();

app.get("/api/calendar", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const calDir = join(OUTPUT_DIR, "content-calendar");

	try {
		const files = await readdir(calDir);
		const calendars = files
			.filter((f) => f.endsWith(".json"))
			.map((f) => f.replace(".json", ""))
			.sort()
			.reverse();
		return c.json({ calendars });
	} catch {
		return c.json({ calendars: [] });
	}
});

app.get("/api/calendar/:date", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const date = c.req.param("date");
	const filePath = join(OUTPUT_DIR, "content-calendar", `${date}.json`);

	try {
		const content = await readFile(filePath, "utf-8");
		return c.json(JSON.parse(content));
	} catch {
		return c.json({ error: "Calendar not found" }, 404);
	}
});

export default app;
