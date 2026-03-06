import { Hono } from "hono";
import { streamText } from "ai";
import { anthropic } from "@ai-sdk/anthropic";
import { eq, and, desc } from "drizzle-orm";
import { getDb, schema } from "../db/index.js";

const app = new Hono();

// POST /api/chat — AI chat about your reading/sessions
app.post("/", async (c) => {
  const user = c.get("user");
  const { messages, date } = await c.req.json();
  const resolvedDate = date === "today" ? new Date().toISOString().slice(0, 10) : date;

  const db = getDb();

  // Load context: brief + recent sessions
  const [brief] = await db.select()
    .from(schema.readingBriefs)
    .where(and(
      eq(schema.readingBriefs.userId, user.id),
      eq(schema.readingBriefs.date, resolvedDate),
    ));

  const recentSessions = await db.select()
    .from(schema.sessions)
    .where(eq(schema.sessions.userId, user.id))
    .orderBy(desc(schema.sessions.sessionTimestamp))
    .limit(5);

  // Build context
  let context = `Date: ${resolvedDate}\n\n`;

  if (brief?.highlights && Array.isArray(brief.highlights) && brief.highlights.length > 0) {
    context += "## Today's Reading Highlights\n";
    for (const h of brief.highlights) {
      context += `- **${h.title}** (${h.source}): ${h.summary}\n`;
    }
    context += "\n";
  }

  if (brief?.connection) {
    context += `## Connection Insight\n${brief.connection.explanation}\n\n`;
  }

  if (recentSessions.length > 0) {
    context += "## Recent Coding Sessions\n";
    for (const s of recentSessions) {
      context += `- **${s.project}**: ${s.summary ?? "No summary"} (${s.durationMinutes}min)\n`;
    }
    context += "\n";
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return c.json({ error: "ANTHROPIC_API_KEY not configured" }, 503);
  }

  const result = streamText({
    model: anthropic("claude-sonnet-4-5-20250929"),
    system: `You are Distill, a personal intelligence assistant. You help the user understand their reading, coding sessions, and learning trajectory.

Here is today's context:
${context}

Guidelines:
- Be concise and insightful
- Reference specific highlights and sessions when relevant
- Help surface connections and patterns
- Keep responses under 200 words unless asked for more detail`,
    messages,
  });

  return result.toTextStreamResponse();
});

export default app;
