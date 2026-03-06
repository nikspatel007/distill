import { z } from "zod";

export const SessionSummarySchema = z.object({
  sessionId: z.string(),
  project: z.string(),
  summary: z.string(),
  keyCommits: z.array(z.string()).default([]),
  toolsUsed: z.array(z.string()).default([]),
  durationMinutes: z.number().default(0),
  filesModified: z.number().default(0),
  timestamp: z.string(),
});

export const SyncSessionsRequestSchema = z.object({
  sessions: z.array(SessionSummarySchema),
});

export type SessionSummary = z.infer<typeof SessionSummarySchema>;
export type SyncSessionsRequest = z.infer<typeof SyncSessionsRequestSchema>;
