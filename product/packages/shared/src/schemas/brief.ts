import { z } from "zod";

export const ReadingHighlightSchema = z.object({
  title: z.string(),
  source: z.string(),
  url: z.string().default(""),
  summary: z.string(),
  tags: z.array(z.string()).default([]),
  imageUrl: z.string().nullable().default(null),
  imagePrompt: z.string().nullable().default(null),
});

export const DraftPostSchema = z.object({
  platform: z.string(),
  content: z.string(),
  charCount: z.number().default(0),
  sourceHighlights: z.array(z.string()).default([]),
  imageUrl: z.string().nullable().default(null),
});

export const ConnectionInsightSchema = z.object({
  today: z.string(),
  past: z.string(),
  connectionType: z.string(),
  explanation: z.string(),
  strength: z.number().default(0),
});

export const TopicTrendSchema = z.object({
  topic: z.string(),
  status: z.enum(["trending", "cooling", "emerging", "stable"]),
  count: z.number().default(0),
  recentCount: z.number().default(0),
  firstSeen: z.string().default(""),
  lastSeen: z.string().default(""),
  sparkline: z.array(z.number()).default([]),
});

export const DiscoveryItemSchema = z.object({
  title: z.string(),
  url: z.string(),
  source: z.string().default(""),
  summary: z.string().default(""),
  topic: z.string().default(""),
  contentType: z.string().default("article"),
});

export const ReadingBriefSchema = z.object({
  id: z.number().optional(),
  userId: z.string().uuid().optional(),
  date: z.string(),
  generatedAt: z.string().default(""),
  highlights: z.array(ReadingHighlightSchema).default([]),
  drafts: z.array(DraftPostSchema).default([]),
  connection: ConnectionInsightSchema.nullable().default(null),
  learningPulse: z.array(TopicTrendSchema).default([]),
  discoveries: z.array(DiscoveryItemSchema).default([]),
});

export type ReadingHighlight = z.infer<typeof ReadingHighlightSchema>;
export type DraftPost = z.infer<typeof DraftPostSchema>;
export type ConnectionInsight = z.infer<typeof ConnectionInsightSchema>;
export type TopicTrend = z.infer<typeof TopicTrendSchema>;
export type DiscoveryItem = z.infer<typeof DiscoveryItemSchema>;
export type ReadingBrief = z.infer<typeof ReadingBriefSchema>;
