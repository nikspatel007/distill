import { z } from "zod";

// --- Content types & statuses ---

export const StudioContentTypeEnum = z.enum([
  "journal",
  "weekly",
  "thematic",
  "digest",
  "seed",
]);

export const StudioStatusEnum = z.enum(["draft", "ready", "published"]);

export const StudioPlatformEnum = z.enum([
  "ghost",
  "x",
  "linkedin",
  "reddit",
  "slack",
]);

export const StudioMoodEnum = z.enum([
  "reflective",
  "energetic",
  "cautionary",
  "triumphant",
  "intimate",
  "technical",
  "playful",
  "somber",
]);

// --- Platform content (JSONB map entry) ---

export const PlatformContentEntrySchema = z.object({
  content: z.string(),
  published: z.boolean().default(false),
  publishedAt: z.string().nullable().default(null),
  externalId: z.string().nullable().default(null),
});

export type PlatformContentEntry = z.infer<typeof PlatformContentEntrySchema>;

// --- Chat message ---

export const StudioChatMessageSchema = z.object({
  role: z.enum(["user", "assistant"]),
  content: z.string(),
  timestamp: z.string().optional(),
});

// --- Full Studio Item ---

export const StudioItemSchema = z.object({
  id: z.number(),
  userId: z.string(),
  title: z.string(),
  slug: z.string(),
  content: z.string().nullable(),
  contentType: StudioContentTypeEnum,
  status: StudioStatusEnum,
  platformContents: z.record(z.string(), PlatformContentEntrySchema).nullable(),
  chatHistory: z.array(StudioChatMessageSchema).nullable(),
  tags: z.array(z.string()).nullable(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type StudioItem = z.infer<typeof StudioItemSchema>;

// --- List view summary ---

export const StudioItemListSchema = z.object({
  id: z.number(),
  title: z.string(),
  slug: z.string(),
  contentType: z.string(),
  status: z.string(),
  platformsReady: z.number(),
  platformsPublished: z.number(),
  createdAt: z.string(),
  updatedAt: z.string(),
});

export type StudioItemList = z.infer<typeof StudioItemListSchema>;

// --- Create ---

export const CreateStudioItemSchema = z.object({
  title: z.string().min(1),
  content: z.string().optional(),
  contentType: StudioContentTypeEnum.default("journal"),
  tags: z.array(z.string()).optional(),
});

export type CreateStudioItem = z.infer<typeof CreateStudioItemSchema>;

// --- Update ---

export const UpdateStudioItemSchema = z.object({
  title: z.string().min(1).optional(),
  content: z.string().optional(),
  status: StudioStatusEnum.optional(),
  tags: z.array(z.string()).optional(),
});

export type UpdateStudioItem = z.infer<typeof UpdateStudioItemSchema>;

// --- Save platform content ---

export const SavePlatformContentSchema = z.object({
  content: z.string(),
});

// --- Chat request ---

export const StudioChatRequestSchema = z.object({
  messages: z.array(z.any()),
  content: z.string(),
  platform: z.string(),
  slug: z.string().optional(),
});

// --- Publish request ---

export const StudioPublishRequestSchema = z.object({
  platforms: z.array(z.string()),
  mode: z.enum(["draft", "schedule", "now"]).default("draft"),
  scheduledAt: z.string().optional(),
});

// --- Studio image ---

export const StudioImageSchema = z.object({
  id: z.number(),
  studioItemId: z.number(),
  url: z.string(),
  prompt: z.string(),
  role: z.enum(["hero", "inline"]).default("hero"),
  createdAt: z.string(),
});

export type StudioImage = z.infer<typeof StudioImageSchema>;

// --- Generate image ---

export const GenerateImageSchema = z.object({
  prompt: z.string().min(1),
  mood: StudioMoodEnum,
});

// --- Ghost publish ---

export const GhostPublishRequestSchema = z.object({
  target: z.string().min(1),
  status: z.enum(["draft", "published"]).default("draft"),
  tags: z.array(z.string()).default([]),
});
