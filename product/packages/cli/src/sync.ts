/**
 * Sync logic for pushing session data to the Distill cloud API.
 *
 * Reads JSONL session files, redacts secrets, extracts summaries,
 * and sends batches to the API.
 */

import { readFile } from "node:fs/promises";
import type { SessionSummary } from "@distill/shared";
import type { ScannedSession } from "./scanner.js";
import { redactSecrets } from "./redactor.js";

/** A parsed JSONL message (minimal shape). */
interface JsonlMessage {
  type?: string;
  role?: string;
  content?: string | Array<{ text?: string }>;
  message?: {
    role?: string;
    content?: string | Array<{ text?: string }>;
  };
  tool_name?: string;
  tool_input?: Record<string, unknown>;
}

/**
 * Extract a human-readable summary from a session's JSONL content.
 *
 * Looks for the first user message as a proxy for the session intent,
 * and counts tool uses and assistant messages for metadata.
 */
function extractSummary(lines: string[]): {
  summary: string;
  toolsUsed: string[];
  filesModified: number;
} {
  let firstUserMessage = "";
  const toolsUsed = new Set<string>();
  const filesModified = new Set<string>();

  for (const line of lines) {
    if (!line.trim()) continue;

    let msg: JsonlMessage;
    try {
      msg = JSON.parse(line) as JsonlMessage;
    } catch {
      continue;
    }

    // Extract first user message as summary
    const role = msg.role ?? msg.message?.role;
    if (role === "user" && !firstUserMessage) {
      const content = msg.content ?? msg.message?.content;
      if (typeof content === "string") {
        firstUserMessage = content.slice(0, 200);
      } else if (Array.isArray(content)) {
        const textPart = content.find((c) => c.text);
        if (textPart?.text) {
          firstUserMessage = textPart.text.slice(0, 200);
        }
      }
    }

    // Track tool usage
    if (msg.tool_name) {
      toolsUsed.add(msg.tool_name);
    }

    // Track file modifications (common tool patterns)
    if (msg.tool_name === "write" || msg.tool_name === "edit") {
      const path = msg.tool_input?.["file_path"] ?? msg.tool_input?.["path"];
      if (typeof path === "string") {
        filesModified.add(path);
      }
    }
  }

  return {
    summary: firstUserMessage || "No summary available",
    toolsUsed: Array.from(toolsUsed),
    filesModified: filesModified.size,
  };
}

/**
 * Estimate session duration from JSONL timestamps.
 * Returns duration in minutes, defaulting to 0 if timestamps aren't found.
 */
function estimateDuration(lines: string[]): number {
  let firstTimestamp: number | null = null;
  let lastTimestamp: number | null = null;

  for (const line of lines) {
    if (!line.trim()) continue;
    try {
      const msg = JSON.parse(line) as Record<string, unknown>;
      const ts = msg["timestamp"] ?? msg["created_at"] ?? msg["ts"];
      if (typeof ts === "string") {
        const parsed = Date.parse(ts);
        if (!isNaN(parsed)) {
          if (firstTimestamp === null) firstTimestamp = parsed;
          lastTimestamp = parsed;
        }
      } else if (typeof ts === "number") {
        const normalized = ts > 1e12 ? ts : ts * 1000; // handle seconds vs ms
        if (firstTimestamp === null) firstTimestamp = normalized;
        lastTimestamp = normalized;
      }
    } catch {
      continue;
    }
  }

  if (firstTimestamp !== null && lastTimestamp !== null) {
    return Math.round((lastTimestamp - firstTimestamp) / 60000);
  }
  return 0;
}

/**
 * Process a scanned session into a SessionSummary ready for the API.
 */
async function processSession(session: ScannedSession): Promise<SessionSummary> {
  const raw = await readFile(session.filePath, "utf-8");
  const redacted = redactSecrets(raw);
  const lines = redacted.split("\n").filter((l) => l.trim());

  const { summary, toolsUsed, filesModified } = extractSummary(lines);
  const durationMinutes = estimateDuration(lines);

  return {
    sessionId: session.sessionId,
    project: session.project,
    summary,
    keyCommits: [],
    toolsUsed,
    durationMinutes,
    filesModified,
    timestamp: new Date(session.lastModified).toISOString(),
  };
}

/** Batch size for API uploads. */
const BATCH_SIZE = 20;

/**
 * Sync sessions to the Distill cloud API.
 *
 * Reads each JSONL file, redacts secrets, extracts summary metadata,
 * and POSTs batches to /api/sessions/sync.
 *
 * @returns Number of sessions successfully synced.
 */
export async function syncSessions(
  sessions: ScannedSession[],
  apiUrl: string,
  token: string,
): Promise<number> {
  if (sessions.length === 0) {
    console.log("No new sessions to sync.");
    return 0;
  }

  console.log(`Processing ${sessions.length} session(s)...`);

  let synced = 0;

  // Process in batches
  for (let i = 0; i < sessions.length; i += BATCH_SIZE) {
    const batch = sessions.slice(i, i + BATCH_SIZE);
    const summaries: SessionSummary[] = [];

    for (const session of batch) {
      try {
        const summary = await processSession(session);
        summaries.push(summary);
      } catch (err) {
        const message = err instanceof Error ? err.message : String(err);
        console.warn(`  Skipping ${session.sessionId}: ${message}`);
      }
    }

    if (summaries.length === 0) continue;

    // POST to API
    try {
      const response = await fetch(`${apiUrl}/api/sessions/sync`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${token}`,
        },
        body: JSON.stringify({ sessions: summaries }),
      });

      if (!response.ok) {
        const body = await response.text();
        console.error(`  API error (${response.status}): ${body}`);
        continue;
      }

      synced += summaries.length;
      const batchEnd = Math.min(i + BATCH_SIZE, sessions.length);
      console.log(`  Synced batch ${Math.floor(i / BATCH_SIZE) + 1}: ${summaries.length} session(s) [${i + 1}-${batchEnd}]`);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      console.error(`  Network error: ${message}`);
    }
  }

  return synced;
}
