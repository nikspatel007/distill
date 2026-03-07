import { Hono } from "hono";
import { anthropic } from "@ai-sdk/anthropic";
import { convertToModelMessages, stepCountIs, streamText, tool } from "ai";
import { eq, and, desc, sql } from "drizzle-orm";
import { z } from "zod";
import { getDb, schema } from "../db/index.js";
import {
  CreateStudioItemSchema,
  UpdateStudioItemSchema,
  SavePlatformContentSchema,
  StudioChatRequestSchema,
  StudioPublishRequestSchema,
  GhostPublishRequestSchema,
  GenerateImageSchema,
  StudioMoodEnum,
} from "@distill/shared";
import { PLATFORM_PROMPTS } from "../lib/prompts.js";
import { getConfig } from "../lib/config.js";

const STUDIO_MODEL = process.env.STUDIO_MODEL ?? "claude-sonnet-4-6";
import {
  listIntegrations,
  createPost,
  isPostizConfigured,
} from "../lib/postiz.js";
import {
  getGhostTargets,
  createGhostClient,
} from "../lib/ghost.js";
import { generateImage, isImageGenConfigured } from "../pipeline/images.js";
import { uploadImage } from "../lib/storage.js";

const app = new Hono();

/** Map platform names to Postiz provider identifiers. */
const PLATFORM_PROVIDER_MAP: Record<string, string> = {
  x: "x",
  linkedin: "linkedin",
  slack: "slack",
};

// ---------------------------------------------------------------------------
// CRUD
// ---------------------------------------------------------------------------

/**
 * GET /items — list user's studio items.
 * Ordered by status (drafts first) then date descending.
 */
app.get("/items", async (c) => {
  const user = c.get("user");
  const db = getDb();

  const items = await db
    .select()
    .from(schema.studioItems)
    .where(eq(schema.studioItems.userId, user.id))
    .orderBy(
      sql`CASE WHEN ${schema.studioItems.status} = 'draft' THEN 0 ELSE 1 END`,
      desc(schema.studioItems.updatedAt),
    );

  const result = items.map((item) => {
    const platforms = (item.platformContents ?? {}) as Record<
      string,
      { content: string; published: boolean; publishedAt: string | null; externalId: string | null }
    >;
    const platformsReady = Object.values(platforms).filter(
      (p) => p.content && p.content.length > 0,
    ).length;
    const platformsPublished = Object.values(platforms).filter((p) => p.published).length;

    return {
      id: item.id,
      title: item.title,
      slug: item.slug,
      contentType: item.contentType,
      status: item.status,
      platformsReady,
      platformsPublished,
      createdAt: item.createdAt.toISOString(),
      updatedAt: item.updatedAt.toISOString(),
    };
  });

  return c.json({ items: result });
});

/**
 * GET /items/:slug — get single item with its images.
 */
app.get("/items/:slug", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const db = getDb();

  const [item] = await db
    .select()
    .from(schema.studioItems)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    );

  if (!item) {
    return c.json({ error: "Item not found" }, 404);
  }

  const images = await db
    .select()
    .from(schema.studioImages)
    .where(eq(schema.studioImages.studioItemId, item.id))
    .orderBy(desc(schema.studioImages.createdAt));

  return c.json({
    id: item.id,
    userId: item.userId,
    title: item.title,
    slug: item.slug,
    content: item.content,
    contentType: item.contentType,
    status: item.status,
    platformContents: item.platformContents,
    chatHistory: item.chatHistory,
    tags: item.tags,
    createdAt: item.createdAt.toISOString(),
    updatedAt: item.updatedAt.toISOString(),
    images: images.map((img) => ({
      id: img.id,
      studioItemId: img.studioItemId,
      url: img.url,
      prompt: img.prompt,
      role: img.role,
      createdAt: img.createdAt.toISOString(),
    })),
  });
});

/**
 * POST /items — create a new studio item.
 * Generates slug from title, ensures uniqueness per user.
 */
app.post("/items", async (c) => {
  const user = c.get("user");
  const body = CreateStudioItemSchema.parse(await c.req.json());
  const db = getDb();

  // Generate base slug from title
  const baseSlug = body.title
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);

  // Ensure uniqueness per user
  let slug = baseSlug;
  let counter = 1;
  // eslint-disable-next-line no-constant-condition
  while (true) {
    const [existing] = await db
      .select({ id: schema.studioItems.id })
      .from(schema.studioItems)
      .where(
        and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
      );
    if (!existing) break;
    slug = `${baseSlug}-${counter}`;
    counter++;
  }

  const now = new Date();
  const [created] = await db
    .insert(schema.studioItems)
    .values({
      userId: user.id,
      title: body.title,
      slug,
      content: body.content ?? null,
      contentType: body.contentType,
      status: "draft",
      tags: body.tags ?? [],
      platformContents: {},
      chatHistory: [],
      createdAt: now,
      updatedAt: now,
    })
    .returning();

  return c.json({ id: created!.id, slug, created: true }, 201);
});

/**
 * PUT /items/:slug — update fields on an item.
 */
app.put("/items/:slug", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const body = UpdateStudioItemSchema.parse(await c.req.json());
  const db = getDb();

  const updates: Record<string, unknown> = { updatedAt: new Date() };
  if (body.title !== undefined) updates["title"] = body.title;
  if (body.content !== undefined) updates["content"] = body.content;
  if (body.status !== undefined) updates["status"] = body.status;
  if (body.tags !== undefined) updates["tags"] = body.tags;

  const [updated] = await db
    .update(schema.studioItems)
    .set(updates)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    )
    .returning();

  if (!updated) {
    return c.json({ error: "Item not found" }, 404);
  }

  return c.json({ success: true, slug: updated.slug });
});

/**
 * DELETE /items/:slug — delete item (images cascade via FK).
 */
app.delete("/items/:slug", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const db = getDb();

  const [deleted] = await db
    .delete(schema.studioItems)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    )
    .returning({ id: schema.studioItems.id });

  if (!deleted) {
    return c.json({ error: "Item not found" }, 404);
  }

  return c.json({ success: true });
});

// ---------------------------------------------------------------------------
// Platform Content
// ---------------------------------------------------------------------------

/**
 * PUT /items/:slug/platform/:platform — save adapted content to platformContents JSONB.
 */
app.put("/items/:slug/platform/:platform", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const platform = c.req.param("platform");
  const { content } = SavePlatformContentSchema.parse(await c.req.json());
  const db = getDb();

  // Load current item
  const [item] = await db
    .select()
    .from(schema.studioItems)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    );

  if (!item) {
    return c.json({ error: "Item not found" }, 404);
  }

  const platforms = (item.platformContents ?? {}) as Record<
    string,
    { content: string; published: boolean; publishedAt: string | null; externalId: string | null }
  >;
  platforms[platform] = {
    content,
    published: platforms[platform]?.published ?? false,
    publishedAt: platforms[platform]?.publishedAt ?? null,
    externalId: platforms[platform]?.externalId ?? null,
  };

  await db
    .update(schema.studioItems)
    .set({ platformContents: platforms, updatedAt: new Date() })
    .where(eq(schema.studioItems.id, item.id));

  return c.json({ success: true });
});

// ---------------------------------------------------------------------------
// Chat (streaming)
// ---------------------------------------------------------------------------

/**
 * POST /chat — streaming AI chat using AI SDK.
 */
app.post("/chat", async (c) => {
  const user = c.get("user");
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return c.json({ error: "ANTHROPIC_API_KEY not configured" }, 503);
  }

  const { messages, content, platform, slug } = StudioChatRequestSchema.parse(
    await c.req.json(),
  );

  const db = getDb();

  // Build platform content summary if slug is provided
  let platformSummary = "";
  let studioItemId: number | null = null;
  if (slug) {
    const [item] = await db
      .select()
      .from(schema.studioItems)
      .where(
        and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
      );
    if (item) {
      studioItemId = item.id;
      const platforms = (item.platformContents ?? {}) as Record<
        string,
        { content: string; published: boolean }
      >;
      platformSummary = Object.entries(platforms)
        .map(([p, rec]) => {
          const len = rec.content?.length ?? 0;
          const status = rec.published ? "published" : len > 0 ? "ready" : "empty";
          return `  - ${p}: ${status}${len > 0 ? ` (${len} chars)` : ""}`;
        })
        .join("\n");
    }
  }

  const platformPrompt =
    PLATFORM_PROMPTS[platform] ??
    `You are adapting content for ${platform}.

After writing the adapted content, ALWAYS call the savePlatformContent tool with the full content.`;

  const systemPrompt = `${platformPrompt}

Content slug: ${slug ?? "unknown"}
Current platform tab: ${platform}
${platformSummary ? `\nPlatform content status:\n${platformSummary}\n` : ""}
Here are the author's source notes to work with:

---
${content}
---

Be a thoughtful collaborator. Ask questions, suggest angles, explain your choices.

IMPORTANT: When saving content, ALWAYS specify the platform explicitly based on context. If the author mentions "LinkedIn", save to linkedin. If they mention "Twitter" or "X", save to x. Do NOT rely on the active tab -- determine the platform from what the author is discussing.

When you write or revise content for a platform, call savePlatformContent with the content AND the platform name (ghost, x, linkedin, slack).
When the author asks you to edit, rewrite, or improve the source post itself, call the updateSourceContent tool with the complete updated post. Always send the FULL updated content, not just the changed section.`;

  // Convert incoming {role, content} messages to UIMessage format with .parts
  const uiMessages = messages.map((msg, i) => ({
    id: `msg-${i}`,
    role: msg.role as "user" | "assistant",
    parts: [{ type: "text" as const, text: msg.content }],
  }));

  // Convert UI wire format to model messages
  const modelMessages = await convertToModelMessages(
    uiMessages as Parameters<typeof convertToModelMessages>[0],
  );

  const userId = user.id;

  const result = streamText({
    model: anthropic(STUDIO_MODEL),
    system: systemPrompt,
    messages: modelMessages,
    tools: {
      savePlatformContent: tool({
        description:
          "Save adapted content for a platform. Specify the platform explicitly (x, linkedin, slack, ghost).",
        inputSchema: z.object({
          content: z.string().describe("Full adapted content for the platform"),
          platform: z
            .enum(["ghost", "x", "linkedin", "slack", "reddit"])
            .optional()
            .describe("Target platform. Infer from context."),
        }),
        execute: async (params) => {
          const targetPlatform = params.platform ?? platform;
          const targetSlug = slug;
          if (!targetSlug) return { error: "No slug provided" };

          const [item] = await db
            .select()
            .from(schema.studioItems)
            .where(
              and(
                eq(schema.studioItems.userId, userId),
                eq(schema.studioItems.slug, targetSlug),
              ),
            );
          if (!item) return { error: "Item not found" };

          const platforms = (item.platformContents ?? {}) as Record<
            string,
            { content: string; published: boolean; publishedAt: string | null; externalId: string | null }
          >;
          platforms[targetPlatform] = {
            content: params.content,
            published: platforms[targetPlatform]?.published ?? false,
            publishedAt: platforms[targetPlatform]?.publishedAt ?? null,
            externalId: platforms[targetPlatform]?.externalId ?? null,
          };

          await db
            .update(schema.studioItems)
            .set({ platformContents: platforms, updatedAt: new Date() })
            .where(eq(schema.studioItems.id, item.id));

          return { success: true, platform: targetPlatform, chars: params.content.length };
        },
      }),

      updateSourceContent: tool({
        description:
          "Update the original source post. Call when the author asks to edit/rewrite the source notes.",
        inputSchema: z.object({
          content: z.string().describe("Full updated source content (markdown)"),
          title: z.string().optional().describe("Updated title, if changed"),
        }),
        execute: async (params) => {
          const targetSlug = slug;
          if (!targetSlug) return { error: "No slug provided" };

          const updates: Record<string, unknown> = {
            content: params.content,
            updatedAt: new Date(),
          };
          if (params.title) updates["title"] = params.title;

          const [updated] = await db
            .update(schema.studioItems)
            .set(updates)
            .where(
              and(
                eq(schema.studioItems.userId, userId),
                eq(schema.studioItems.slug, targetSlug),
              ),
            )
            .returning({ slug: schema.studioItems.slug });

          if (!updated) return { error: "Item not found" };
          return { success: true, slug: updated.slug };
        },
      }),

      listContent: tool({
        description: "List all content items in the studio.",
        inputSchema: z.object({
          type: z.string().optional().describe("Filter by contentType"),
          status: z.string().optional().describe("Filter by status"),
        }),
        execute: async (params) => {
          let query = db
            .select({
              slug: schema.studioItems.slug,
              title: schema.studioItems.title,
              contentType: schema.studioItems.contentType,
              status: schema.studioItems.status,
              updatedAt: schema.studioItems.updatedAt,
            })
            .from(schema.studioItems)
            .where(eq(schema.studioItems.userId, userId))
            .orderBy(desc(schema.studioItems.updatedAt))
            .limit(50);

          const items = await query;

          let filtered = items;
          if (params.type) {
            filtered = filtered.filter((i) => i.contentType === params.type);
          }
          if (params.status) {
            filtered = filtered.filter((i) => i.status === params.status);
          }

          return {
            items: filtered.map((i) => ({
              slug: i.slug,
              title: i.title,
              contentType: i.contentType,
              status: i.status,
              updatedAt: i.updatedAt.toISOString(),
            })),
          };
        },
      }),

      getContent: tool({
        description: "Get full content record by slug.",
        inputSchema: z.object({ slug: z.string() }),
        execute: async (params) => {
          const [item] = await db
            .select()
            .from(schema.studioItems)
            .where(
              and(
                eq(schema.studioItems.userId, userId),
                eq(schema.studioItems.slug, params.slug),
              ),
            );
          if (!item) return { error: "Not found" };
          return {
            slug: item.slug,
            title: item.title,
            content: item.content,
            contentType: item.contentType,
            status: item.status,
            tags: item.tags,
          };
        },
      }),

      updateStatus: tool({
        description: "Change content status (draft, ready, published).",
        inputSchema: z.object({
          slug: z.string(),
          status: z.enum(["draft", "ready", "published"]),
        }),
        execute: async (params) => {
          const [updated] = await db
            .update(schema.studioItems)
            .set({ status: params.status, updatedAt: new Date() })
            .where(
              and(
                eq(schema.studioItems.userId, userId),
                eq(schema.studioItems.slug, params.slug),
              ),
            )
            .returning({ slug: schema.studioItems.slug, status: schema.studioItems.status });

          if (!updated) return { error: "Not found" };
          return { success: true, slug: updated.slug, status: updated.status };
        },
      }),
    },
    stopWhen: stepCountIs(5),
  });

  return result.toUIMessageStreamResponse();
});

/**
 * PUT /items/:slug/chat — persist chat history to chatHistory JSONB column.
 */
app.put("/items/:slug/chat", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const { chatHistory } = z
    .object({ chatHistory: z.array(z.any()) })
    .parse(await c.req.json());
  const db = getDb();

  const [updated] = await db
    .update(schema.studioItems)
    .set({ chatHistory, updatedAt: new Date() })
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    )
    .returning({ id: schema.studioItems.id });

  if (!updated) {
    return c.json({ error: "Item not found" }, 404);
  }

  return c.json({ success: true });
});

// ---------------------------------------------------------------------------
// Publishing
// ---------------------------------------------------------------------------

/**
 * GET /platforms — list Postiz integrations.
 */
app.get("/platforms", async (c) => {
  if (!isPostizConfigured()) {
    return c.json({ integrations: [], configured: false });
  }

  try {
    const integrations = await listIntegrations();
    return c.json({ integrations, configured: true });
  } catch {
    return c.json({ integrations: [], configured: false });
  }
});

/**
 * POST /publish/:slug — publish to Postiz (draft/schedule/now).
 */
app.post("/publish/:slug", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const body = StudioPublishRequestSchema.parse(await c.req.json());
  const db = getDb();

  if (!isPostizConfigured()) {
    return c.json({ error: "Postiz not configured" }, 503);
  }

  // Load item
  const [item] = await db
    .select()
    .from(schema.studioItems)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    );

  if (!item) {
    return c.json({ error: "Item not found" }, 404);
  }

  let integrations: Awaited<ReturnType<typeof listIntegrations>> = [];
  try {
    integrations = await listIntegrations();
  } catch {
    return c.json({ error: "Failed to fetch integrations" }, 502);
  }

  const platforms = (item.platformContents ?? {}) as Record<
    string,
    { content: string; published: boolean; publishedAt: string | null; externalId: string | null }
  >;

  const results: Array<{ platform: string; success: boolean; error?: string }> = [];

  for (const platformName of body.platforms) {
    const entry = platforms[platformName];
    if (!entry?.content) {
      results.push({ platform: platformName, success: false, error: "No adapted content" });
      continue;
    }
    if (entry.published) {
      results.push({ platform: platformName, success: false, error: "Already published" });
      continue;
    }

    const provider = PLATFORM_PROVIDER_MAP[platformName] ?? platformName;
    const integration = integrations.find((i) => i.provider === provider);
    if (!integration) {
      results.push({
        platform: platformName,
        success: false,
        error: `No integration for ${platformName}`,
      });
      continue;
    }

    try {
      await createPost(entry.content, [integration.id], {
        postType: body.mode,
        scheduledAt: body.scheduledAt,
        provider,
      });
      entry.published = true;
      entry.publishedAt = new Date().toISOString();
      results.push({ platform: platformName, success: true });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      results.push({ platform: platformName, success: false, error: message });
    }
  }

  // Check if all platforms are now published
  const allPublished =
    Object.values(platforms).length > 0 &&
    Object.values(platforms).every((p) => p.published);
  const newStatus = allPublished ? "published" : item.status;

  await db
    .update(schema.studioItems)
    .set({ platformContents: platforms, status: newStatus, updatedAt: new Date() })
    .where(eq(schema.studioItems.id, item.id));

  return c.json({ results });
});

/**
 * GET /ghost/targets — list Ghost targets.
 */
app.get("/ghost/targets", async (c) => {
  const targets = getGhostTargets();
  return c.json({
    targets: targets.map((t) => ({
      name: t.name,
      label: t.label,
      configured: t.configured,
    })),
  });
});

/**
 * POST /ghost/publish/:slug — publish to Ghost CMS.
 */
app.post("/ghost/publish/:slug", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const body = GhostPublishRequestSchema.parse(await c.req.json());
  const db = getDb();

  // Load item
  const [item] = await db
    .select()
    .from(schema.studioItems)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    );

  if (!item) {
    return c.json({ error: "Item not found" }, 404);
  }

  const ghost = createGhostClient(body.target);
  if (!ghost) {
    return c.json({ error: `Ghost target '${body.target}' not configured` }, 503);
  }

  // Use platform-adapted content for ghost if available, otherwise use source content
  const platforms = (item.platformContents ?? {}) as Record<
    string,
    { content: string; published: boolean; publishedAt: string | null; externalId: string | null }
  >;
  const ghostContent = platforms["ghost"]?.content ?? item.content;
  if (!ghostContent) {
    return c.json({ error: "No content available to publish" }, 400);
  }

  // Strip leading H1 (Ghost uses title field)
  const markdown = ghostContent.replace(/^#\s+.+\n*/, "");

  // Check for hero image
  const [heroImage] = await db
    .select()
    .from(schema.studioImages)
    .where(
      and(
        eq(schema.studioImages.studioItemId, item.id),
        eq(schema.studioImages.role, "hero"),
      ),
    )
    .limit(1);

  try {
    // Upload hero image to Ghost if available
    let featureImage: string | undefined;
    if (heroImage) {
      const ghostImageUrl = await ghost.uploadImageFromUrl(heroImage.url);
      if (ghostImageUrl) featureImage = ghostImageUrl;
    }

    const post = await ghost.createPost(item.title, markdown, {
      status: body.status,
      tags: body.tags,
      featureImage,
    });

    // Update platformContents with ghost_{target} key
    const ghostKey = `ghost_${body.target}`;
    platforms[ghostKey] = {
      content: ghostContent,
      published: true,
      publishedAt: new Date().toISOString(),
      externalId: post.id,
    };

    await db
      .update(schema.studioItems)
      .set({ platformContents: platforms, updatedAt: new Date() })
      .where(eq(schema.studioItems.id, item.id));

    return c.json({
      success: true,
      post: {
        id: post.id,
        url: post.url,
        title: post.title,
        status: post.status,
      },
    });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Unknown error";
    return c.json({ error: `Ghost publish failed: ${message}` }, 502);
  }
});

// ---------------------------------------------------------------------------
// Images
// ---------------------------------------------------------------------------

/**
 * POST /items/:slug/image — generate a single image, upload to Supabase, store record.
 */
app.post("/items/:slug/image", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const { prompt, mood } = GenerateImageSchema.parse(await c.req.json());
  const db = getDb();

  if (!isImageGenConfigured()) {
    return c.json({ error: "Image generation not configured (GOOGLE_AI_API_KEY)" }, 503);
  }

  // Load item
  const [item] = await db
    .select({ id: schema.studioItems.id })
    .from(schema.studioItems)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    );

  if (!item) {
    return c.json({ error: "Item not found" }, 404);
  }

  const generated = await generateImage(prompt);
  if (!generated) {
    return c.json({ error: "Image generation failed" }, 500);
  }

  // Upload to Supabase storage
  const storagePath = `studio/${user.id}/${slug}/${Date.now()}.png`;
  const publicUrl = await uploadImage(storagePath, generated.base64, generated.mimeType);
  if (!publicUrl) {
    return c.json({ error: "Image upload failed" }, 500);
  }

  // Store record in studio_images
  const [imageRecord] = await db
    .insert(schema.studioImages)
    .values({
      studioItemId: item.id,
      url: publicUrl,
      prompt: generated.prompt,
      role: "hero",
    })
    .returning();

  return c.json({
    id: imageRecord!.id,
    url: publicUrl,
    prompt: generated.prompt,
    role: "hero",
    createdAt: imageRecord!.createdAt.toISOString(),
  });
});

/**
 * POST /items/:slug/images/batch — extract 3 prompts from content via AI, generate all in parallel.
 */
app.post("/items/:slug/images/batch", async (c) => {
  const user = c.get("user");
  const slug = c.req.param("slug");
  const { mood } = z
    .object({ mood: StudioMoodEnum.default("reflective") })
    .parse(await c.req.json());
  const db = getDb();

  if (!isImageGenConfigured()) {
    return c.json({ error: "Image generation not configured (GOOGLE_AI_API_KEY)" }, 503);
  }

  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    return c.json({ error: "ANTHROPIC_API_KEY not configured for prompt extraction" }, 503);
  }

  // Load item
  const [item] = await db
    .select()
    .from(schema.studioItems)
    .where(
      and(eq(schema.studioItems.userId, user.id), eq(schema.studioItems.slug, slug)),
    );

  if (!item) {
    return c.json({ error: "Item not found" }, 404);
  }

  if (!item.content) {
    return c.json({ error: "Item has no content to generate images from" }, 400);
  }

  // Extract image prompts from content via AI SDK
  const { generateText } = await import("ai");
  const extractionResult = await generateText({
    model: anthropic(STUDIO_MODEL),
    system: `You are an image prompt generator for editorial blog posts. Given a blog post, generate exactly 3 image prompts: 1 hero image and 2 inline images.

Return ONLY valid JSON -- no markdown fences, no explanation. The JSON should be an array of objects:
[
  { "role": "hero", "prompt": "..." },
  { "role": "inline", "prompt": "..." },
  { "role": "inline", "prompt": "..." }
]

Each prompt should describe a visual metaphor or scene -- NOT the article topic literally. Think editorial photography: evocative, atmospheric, symbolic. Focus on composition, lighting, and mood (${mood}).`,
    prompt: `Generate 3 image prompts for this blog post:\n\nTitle: ${item.title}\n\n${item.content.slice(0, 3000)}`,
  });

  let imagePrompts: Array<{ role: string; prompt: string }>;
  try {
    const cleaned = extractionResult.text.replace(/```json\n?|\n?```/g, "").trim();
    imagePrompts = JSON.parse(cleaned);
    if (!Array.isArray(imagePrompts) || imagePrompts.length === 0) {
      throw new Error("Expected array of prompts");
    }
  } catch {
    return c.json({ error: "Failed to extract image prompts from content" }, 500);
  }

  // Generate all images in parallel
  const imageResults = await Promise.allSettled(
    imagePrompts.slice(0, 3).map(async (ip) => {
      const generated = await generateImage(ip.prompt);
      if (!generated) throw new Error("Generation failed");

      const storagePath = `studio/${user.id}/${slug}/${Date.now()}-${ip.role}.png`;
      const publicUrl = await uploadImage(storagePath, generated.base64, generated.mimeType);
      if (!publicUrl) throw new Error("Upload failed");

      return { url: publicUrl, prompt: generated.prompt, role: ip.role };
    }),
  );

  // Store successful results in studio_images
  const responseImages: Array<{
    url: string | null;
    role: string;
    error: string | null;
  }> = [];

  for (let i = 0; i < imageResults.length; i++) {
    const result = imageResults[i]!;
    if (result.status === "fulfilled") {
      await db.insert(schema.studioImages).values({
        studioItemId: item.id,
        url: result.value.url,
        prompt: result.value.prompt,
        role: result.value.role,
      });
      responseImages.push({ url: result.value.url, role: result.value.role, error: null });
    } else {
      const role = imagePrompts[i]?.role ?? "unknown";
      responseImages.push({ url: null, role, error: "Generation or upload failed" });
    }
  }

  const generated = responseImages.filter((r) => r.url !== null);
  return c.json({
    generated: generated.length,
    total_requested: imagePrompts.length,
    images: responseImages,
  });
});

export default app;
