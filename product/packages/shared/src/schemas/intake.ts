import { z } from "zod";

export const ContentSourceEnum = z.enum([
  "rss", "browser", "substack", "reddit", "youtube",
  "gmail", "linkedin", "twitter", "session", "manual", "discovery",
]);

export const ContentItemSchema = z.object({
  id: z.number().optional(),
  userId: z.string().uuid().optional(),
  source: ContentSourceEnum,
  url: z.string().nullable().default(null),
  title: z.string(),
  summary: z.string().nullable().default(null),
  fullText: z.string().nullable().default(null),
  tags: z.array(z.string()).default([]),
  entities: z.array(z.string()).default([]),
  publishedAt: z.string().nullable().default(null),
  ingestedAt: z.string().default(""),
  imageUrl: z.string().nullable().default(null),
});

export const SharedUrlSchema = z.object({
  id: z.number().optional(),
  userId: z.string().uuid().optional(),
  url: z.string().url(),
  title: z.string().nullable().default(null),
  note: z.string().nullable().default(null),
  createdAt: z.string().default(""),
  processedAt: z.string().nullable().default(null),
});

export const CreateShareSchema = z.object({
  url: z.string().url(),
  note: z.string().optional(),
});

export const DefaultFeedSchema = z.object({
  id: z.number().optional(),
  url: z.string().url(),
  name: z.string().nullable().default(null),
  category: z.string().nullable().default(null),
  active: z.boolean().default(true),
});

export type ContentSource = z.infer<typeof ContentSourceEnum>;
export type ContentItem = z.infer<typeof ContentItemSchema>;
export type SharedUrl = z.infer<typeof SharedUrlSchema>;
export type CreateShare = z.infer<typeof CreateShareSchema>;
export type DefaultFeed = z.infer<typeof DefaultFeedSchema>;
