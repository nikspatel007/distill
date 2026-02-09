import { mkdir, readFile, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { zValidator } from "@hono/zod-validator";
import { Hono } from "hono";
import { z } from "zod";
import { CreateNoteSchema, type EditorialNote, EditorialNoteSchema } from "../../shared/schemas.js";
import { getConfig } from "../lib/config.js";

const app = new Hono();

const NOTES_FILE = ".distill-notes.json";

async function loadNotes(outputDir: string): Promise<EditorialNote[]> {
	try {
		const raw = await readFile(join(outputDir, NOTES_FILE), "utf-8");
		return z.array(EditorialNoteSchema).parse(JSON.parse(raw));
	} catch {
		return [];
	}
}

async function saveNotes(outputDir: string, notes: EditorialNote[]): Promise<void> {
	await mkdir(outputDir, { recursive: true });
	await writeFile(join(outputDir, NOTES_FILE), JSON.stringify(notes, null, 2), "utf-8");
}

app.get("/api/notes", async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const notes = await loadNotes(OUTPUT_DIR);
	return c.json({ notes });
});

app.post("/api/notes", zValidator("json", CreateNoteSchema), async (c) => {
	const { OUTPUT_DIR } = getConfig();
	const body = c.req.valid("json");
	const notes = await loadNotes(OUTPUT_DIR);

	const id = Math.random().toString(36).slice(2, 14);
	const newNote: EditorialNote = {
		id,
		text: body.text,
		target: body.target,
		created_at: new Date().toISOString(),
		used: false,
	};

	notes.push(newNote);
	await saveNotes(OUTPUT_DIR, notes);
	return c.json(newNote, 201);
});

app.delete("/api/notes/:id", async (c) => {
	const id = c.req.param("id");
	const { OUTPUT_DIR } = getConfig();
	const notes = await loadNotes(OUTPUT_DIR);
	const filtered = notes.filter((n) => n.id !== id);

	if (filtered.length === notes.length) {
		return c.json({ error: "Note not found" }, 404);
	}

	await saveNotes(OUTPUT_DIR, filtered);
	return c.json({ success: true });
});

export default app;
