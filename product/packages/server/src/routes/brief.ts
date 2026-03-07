import { Hono } from "hono";
import { eq, and, desc } from "drizzle-orm";
import { getDb, schema } from "../db/index.js";

const app = new Hono();

// GET /api/brief?date=2026-03-06 — get reading brief for date
app.get("/", async (c) => {
  const user = c.get("user");
  const date = c.req.query("date") ?? new Date().toISOString().slice(0, 10);
  const db = getDb();
  const [brief] = await db.select()
    .from(schema.readingBriefs)
    .where(and(
      eq(schema.readingBriefs.userId, user.id),
      eq(schema.readingBriefs.date, date),
    ));
  if (!brief) {
    return c.json({ date, highlights: [], drafts: [], connection: null, learningPulse: [], discoveries: [] });
  }
  return c.json(brief);
});

// GET /api/brief/latest — get most recent brief
app.get("/latest", async (c) => {
  const user = c.get("user");
  const db = getDb();
  const [brief] = await db.select()
    .from(schema.readingBriefs)
    .where(eq(schema.readingBriefs.userId, user.id))
    .orderBy(desc(schema.readingBriefs.date))
    .limit(1);
  if (!brief) {
    return c.json({ date: new Date().toISOString().slice(0, 10), highlights: [], drafts: [], connection: null, learningPulse: [], discoveries: [], generatedAt: "" });
  }
  return c.json({ ...brief, generatedAt: brief.createdAt });
});

export default app;
