import { Hono } from "hono";
import { eq, and, desc, inArray } from "drizzle-orm";
import { getDb, schema } from "../db/index.js";

const app = new Hono();

// GET /api/feed — social feed (items from followed users + own)
app.get("/", async (c) => {
  const user = c.get("user");
  const limit = Number(c.req.query("limit") ?? "50");
  const db = getDb();

  // Get list of followed user IDs
  const followRows = await db.select({ followingId: schema.follows.followingId })
    .from(schema.follows)
    .where(eq(schema.follows.followerId, user.id));

  const followingIds = followRows.map(r => r.followingId);
  const allIds = [user.id, ...followingIds];

  // Get feed items from self + followed users
  const items = await db.select({
    id: schema.feedItems.id,
    userId: schema.feedItems.userId,
    type: schema.feedItems.type,
    title: schema.feedItems.title,
    summary: schema.feedItems.summary,
    url: schema.feedItems.url,
    imageUrl: schema.feedItems.imageUrl,
    metadata: schema.feedItems.metadata,
    createdAt: schema.feedItems.createdAt,
    displayName: schema.users.displayName,
    avatarUrl: schema.users.avatarUrl,
  })
    .from(schema.feedItems)
    .innerJoin(schema.users, eq(schema.feedItems.userId, schema.users.id))
    .where(inArray(schema.feedItems.userId, allIds))
    .orderBy(desc(schema.feedItems.createdAt))
    .limit(limit);

  return c.json(items);
});

// GET /api/feed/following — list users you follow
app.get("/following", async (c) => {
  const user = c.get("user");
  const db = getDb();
  const following = await db.select({
    id: schema.users.id,
    displayName: schema.users.displayName,
    avatarUrl: schema.users.avatarUrl,
  })
    .from(schema.follows)
    .innerJoin(schema.users, eq(schema.follows.followingId, schema.users.id))
    .where(eq(schema.follows.followerId, user.id));

  return c.json(following);
});

// POST /api/feed/follow — follow a user
app.post("/follow", async (c) => {
  const user = c.get("user");
  const { userId } = await c.req.json();
  if (userId === user.id) return c.json({ error: "Cannot follow yourself" }, 400);
  const db = getDb();
  await db.insert(schema.follows).values({
    followerId: user.id,
    followingId: userId,
  }).onConflictDoNothing();
  return c.json({ ok: true });
});

// DELETE /api/feed/follow/:userId — unfollow
app.delete("/follow/:userId", async (c) => {
  const user = c.get("user");
  const targetId = c.req.param("userId");
  const db = getDb();
  await db.delete(schema.follows).where(
    and(
      eq(schema.follows.followerId, user.id),
      eq(schema.follows.followingId, targetId),
    ),
  );
  return c.json({ ok: true });
});

export default app;
