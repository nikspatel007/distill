import { Hono } from "hono";
import { eq, desc } from "drizzle-orm";
import { getDb, schema } from "../db/index.js";
import { SyncSessionsRequestSchema } from "@distill/shared";

const app = new Hono();

// POST /api/sessions/sync — sync sessions from CLI
app.post("/sync", async (c) => {
  const user = c.get("user");
  const body = await c.req.json();
  const parsed = SyncSessionsRequestSchema.parse(body);
  const db = getDb();

  let synced = 0;
  for (const session of parsed.sessions) {
    await db.insert(schema.sessions).values({
      userId: user.id,
      sessionId: session.sessionId,
      project: session.project,
      summary: session.summary,
      keyCommits: session.keyCommits,
      toolsUsed: session.toolsUsed,
      durationMinutes: session.durationMinutes,
      filesModified: session.filesModified,
      sessionTimestamp: new Date(session.timestamp),
    }).onConflictDoNothing(); // skip already-synced sessions
    synced++;
  }

  return c.json({ synced, total: parsed.sessions.length });
});

// GET /api/sessions — list synced sessions
app.get("/", async (c) => {
  const user = c.get("user");
  const limit = Number(c.req.query("limit") ?? "20");
  const db = getDb();
  const rows = await db.select()
    .from(schema.sessions)
    .where(eq(schema.sessions.userId, user.id))
    .orderBy(desc(schema.sessions.sessionTimestamp))
    .limit(limit);
  return c.json(rows);
});

export default app;
