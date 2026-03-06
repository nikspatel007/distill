import { Hono } from "hono";
import { eq, and, desc, isNull } from "drizzle-orm";
import { getDb, schema } from "../db/index.js";
import { CreateShareSchema } from "@distill/shared";

const app = new Hono();

// GET /api/share — list user's shared URLs
app.get("/", async (c) => {
  const user = c.get("user");
  const db = getDb();
  const shares = await db.select()
    .from(schema.sharedUrls)
    .where(eq(schema.sharedUrls.userId, user.id))
    .orderBy(desc(schema.sharedUrls.createdAt))
    .limit(50);
  return c.json(shares);
});

// POST /api/share — share a URL
app.post("/", async (c) => {
  const user = c.get("user");
  const body = await c.req.json();
  const parsed = CreateShareSchema.parse(body);
  const db = getDb();

  const [share] = await db.insert(schema.sharedUrls).values({
    userId: user.id,
    url: parsed.url,
    note: parsed.note ?? null,
  }).returning();

  // Also create a feed item for followers
  await db.insert(schema.feedItems).values({
    userId: user.id,
    type: "share",
    title: parsed.url,
    summary: parsed.note ?? null,
    url: parsed.url,
  });

  return c.json(share, 201);
});

// GET /api/share/pending — get unprocessed shares (for pipeline)
app.get("/pending", async (c) => {
  const user = c.get("user");
  const db = getDb();
  const pending = await db.select()
    .from(schema.sharedUrls)
    .where(and(
      eq(schema.sharedUrls.userId, user.id),
      isNull(schema.sharedUrls.processedAt),
    ));
  return c.json(pending);
});

export default app;
