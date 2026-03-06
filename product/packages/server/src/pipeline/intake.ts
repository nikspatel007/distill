import { eq, and, isNull, desc, gte } from "drizzle-orm";
import { getDb, schema } from "../db/index.js";
import { fetchFeeds } from "./rss.js";
import { extractMetadata } from "./metadata.js";
import {
  extractHighlights,
  generateDrafts,
  findConnection,
} from "./brief.js";
import type { ContentForBrief } from "./brief.js";

export interface PipelineResult {
  userId: string;
  date: string;
  itemsIngested: number;
  highlightsGenerated: number;
  draftsGenerated: number;
  errors: string[];
}

export async function runPipelineForUser(
  userId: string,
): Promise<PipelineResult> {
  const db = getDb();
  const date = new Date().toISOString().slice(0, 10);
  const errors: string[] = [];
  let itemsIngested = 0;

  // 1. Collect RSS feeds
  const defaultFeeds = await db
    .select()
    .from(schema.defaultFeeds)
    .where(eq(schema.defaultFeeds.active, true));

  const feedUrls = defaultFeeds.map((f) => f.url);

  // 2. Fetch RSS items
  let rssItems: Awaited<ReturnType<typeof fetchFeeds>> = [];
  try {
    rssItems = await fetchFeeds(feedUrls);
  } catch (err) {
    errors.push(`RSS fetch failed: ${err}`);
  }

  // 3. Store RSS items as content_items
  for (const item of rssItems) {
    try {
      await db
        .insert(schema.contentItems)
        .values({
          userId,
          source: "rss",
          url: item.url,
          title: item.title,
          summary: item.summary,
          tags: item.tags,
          publishedAt: new Date(item.publishedAt),
        })
        .onConflictDoNothing();
      itemsIngested++;
    } catch {
      // Skip duplicates
    }
  }

  // 4. Process pending shared URLs
  const pendingShares = await db
    .select()
    .from(schema.sharedUrls)
    .where(
      and(
        eq(schema.sharedUrls.userId, userId),
        isNull(schema.sharedUrls.processedAt),
      ),
    );

  for (const share of pendingShares) {
    try {
      const metadata = await extractMetadata(share.url);
      await db.insert(schema.contentItems).values({
        userId,
        source: "manual",
        url: share.url,
        title: metadata.title || share.url,
        summary: metadata.description,
      });
      await db
        .update(schema.sharedUrls)
        .set({ processedAt: new Date(), title: metadata.title || null })
        .where(eq(schema.sharedUrls.id, share.id));
      itemsIngested++;
    } catch (err) {
      errors.push(`Failed to process share ${share.url}: ${err}`);
    }
  }

  // 5. Gather today's content for brief generation
  const todayStart = new Date(`${date}T00:00:00Z`);
  const todayItems = await db
    .select()
    .from(schema.contentItems)
    .where(
      and(
        eq(schema.contentItems.userId, userId),
        gte(schema.contentItems.ingestedAt, todayStart),
      ),
    )
    .orderBy(desc(schema.contentItems.ingestedAt))
    .limit(50);

  const contentForBrief: ContentForBrief[] = todayItems.map((item) => ({
    title: item.title,
    url: item.url ?? "",
    summary: item.summary ?? "",
    source: item.source,
    siteName: item.url ? new URL(item.url).hostname : item.source,
    tags: (item.tags as string[]) ?? [],
  }));

  // 6. Generate highlights
  let highlights: Awaited<ReturnType<typeof extractHighlights>> = [];
  try {
    highlights = await extractHighlights(contentForBrief);
  } catch (err) {
    errors.push(`Highlight extraction failed: ${err}`);
  }

  // 7. Generate drafts
  let drafts: Awaited<ReturnType<typeof generateDrafts>> = [];
  try {
    drafts = await generateDrafts(highlights);
  } catch (err) {
    errors.push(`Draft generation failed: ${err}`);
  }

  // 8. Find connection to past
  let connection = null;
  try {
    // Build past context from recent sessions + briefs
    const recentSessions = await db
      .select()
      .from(schema.sessions)
      .where(eq(schema.sessions.userId, userId))
      .orderBy(desc(schema.sessions.sessionTimestamp))
      .limit(10);

    const pastContext = recentSessions
      .map((s) => `[${s.project}] ${s.summary ?? "Session"}`)
      .join("\n");

    if (pastContext) {
      connection = await findConnection(
        highlights.map((h) => ({ title: h.title, summary: h.summary })),
        pastContext,
      );
    }
  } catch (err) {
    errors.push(`Connection engine failed: ${err}`);
  }

  // 9. Save reading brief
  try {
    await db
      .insert(schema.readingBriefs)
      .values({
        userId,
        date,
        highlights: highlights.map((h) => ({
          title: h.title,
          source: h.source,
          url: h.url,
          summary: h.summary,
          tags: h.tags,
          imageUrl: null,
          imagePrompt: h.imagePrompt ?? null,
        })),
        drafts: drafts.map((d) => ({
          platform: d.platform,
          content: d.content,
          charCount: d.charCount,
          sourceHighlights: d.sourceHighlights,
          imageUrl: null,
        })),
        connection: connection
          ? {
              today: connection.today,
              past: connection.past,
              connectionType: connection.connectionType,
              explanation: connection.explanation,
              strength: connection.strength,
            }
          : null,
        learningPulse: [],
        discoveries: [],
      })
      .onConflictDoNothing();
  } catch (err) {
    errors.push(`Brief save failed: ${err}`);
  }

  // 10. Create feed items for highlights (if user has sharing enabled)
  try {
    const [userProfile] = await db
      .select()
      .from(schema.users)
      .where(eq(schema.users.id, userId));

    const prefs = userProfile?.preferences as { shareHighlights?: boolean } | null;
    if (prefs?.shareHighlights) {
      for (const h of highlights) {
        await db.insert(schema.feedItems).values({
          userId,
          type: "highlight",
          title: h.title,
          summary: h.summary,
          url: h.url,
        });
      }
    }
  } catch (err) {
    errors.push(`Feed item creation failed: ${err}`);
  }

  return {
    userId,
    date,
    itemsIngested,
    highlightsGenerated: highlights.length,
    draftsGenerated: drafts.length,
    errors,
  };
}
