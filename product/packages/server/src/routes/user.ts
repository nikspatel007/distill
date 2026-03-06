import { Hono } from "hono";
import { eq } from "drizzle-orm";
import { getDb, schema } from "../db/index.js";

const app = new Hono();

// GET /api/user — get current user profile
app.get("/", async (c) => {
  const user = c.get("user");
  const db = getDb();
  const [profile] = await db.select().from(schema.users).where(eq(schema.users.id, user.id));
  if (!profile) {
    // Auto-create profile on first login
    const [newProfile] = await db.insert(schema.users).values({
      id: user.id,
      displayName: user.email?.split("@")[0] ?? "User",
      email: user.email,
    }).returning();
    return c.json(newProfile);
  }
  return c.json(profile);
});

// PUT /api/user — update profile
app.put("/", async (c) => {
  const user = c.get("user");
  const body = await c.req.json();
  const db = getDb();
  const [updated] = await db.update(schema.users)
    .set({
      displayName: body.displayName,
      avatarUrl: body.avatarUrl,
      timezone: body.preferences?.timezone,
      notificationsEnabled: body.preferences?.notificationsEnabled,
      sessionSharingEnabled: body.preferences?.sessionSharingEnabled,
      highlightSharingEnabled: body.preferences?.highlightSharingEnabled,
      updatedAt: new Date(),
    })
    .where(eq(schema.users.id, user.id))
    .returning();
  return c.json(updated);
});

export default app;
