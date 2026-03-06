/**
 * Session file scanner.
 *
 * Walks ~/.claude/projects/ looking for session JSONL files.
 * Tracks last sync time to only pick up new/modified files.
 */

import { readdir, stat, readFile, writeFile, mkdir } from "node:fs/promises";
import { join, basename, dirname } from "node:path";
import { homedir } from "node:os";

/** Information about a discovered session file. */
export interface ScannedSession {
  sessionId: string;
  project: string;
  filePath: string;
  lastModified: number;
}

/** Persisted sync state. */
interface SyncState {
  lastSyncTime: number;
  syncedSessions: Record<string, number>; // sessionId -> lastModified at sync time
}

const SYNC_STATE_PATH = join(homedir(), ".distill-sync-state.json");

/** Load the persisted sync state, or return a fresh default. */
export async function loadSyncState(): Promise<SyncState> {
  try {
    const raw = await readFile(SYNC_STATE_PATH, "utf-8");
    const parsed: unknown = JSON.parse(raw);
    if (parsed && typeof parsed === "object" && "lastSyncTime" in parsed) {
      return parsed as SyncState;
    }
    return { lastSyncTime: 0, syncedSessions: {} };
  } catch {
    return { lastSyncTime: 0, syncedSessions: {} };
  }
}

/** Save sync state after a successful sync. */
export async function saveSyncState(state: SyncState): Promise<void> {
  await mkdir(dirname(SYNC_STATE_PATH), { recursive: true });
  await writeFile(SYNC_STATE_PATH, JSON.stringify(state, null, 2), "utf-8");
}

/**
 * Scan for session JSONL files under a base directory.
 *
 * @param baseDir - Root directory to scan (default: ~/.claude/projects)
 * @param since - Only return files modified after this timestamp (epoch ms). 0 = all files.
 * @returns Array of scanned session metadata.
 */
export async function scanSessions(
  baseDir?: string,
  since: number = 0,
): Promise<ScannedSession[]> {
  const root = baseDir ?? join(homedir(), ".claude", "projects");
  const sessions: ScannedSession[] = [];

  let projectDirs: string[];
  try {
    projectDirs = await readdir(root);
  } catch {
    // Directory doesn't exist yet
    return sessions;
  }

  for (const projectName of projectDirs) {
    const projectPath = join(root, projectName);

    let projectStat;
    try {
      projectStat = await stat(projectPath);
    } catch {
      continue;
    }
    if (!projectStat.isDirectory()) continue;

    let files: string[];
    try {
      files = await readdir(projectPath);
    } catch {
      continue;
    }

    for (const file of files) {
      if (!file.endsWith(".jsonl")) continue;

      const filePath = join(projectPath, file);
      let fileStat;
      try {
        fileStat = await stat(filePath);
      } catch {
        continue;
      }

      const lastModified = fileStat.mtimeMs;
      if (since > 0 && lastModified <= since) continue;

      const sessionId = basename(file, ".jsonl");
      sessions.push({
        sessionId,
        project: projectName,
        filePath,
        lastModified,
      });
    }
  }

  return sessions;
}
