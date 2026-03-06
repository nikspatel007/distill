#!/usr/bin/env bun
/**
 * Distill CLI — watches ~/.claude/ directories and syncs session data
 * to the Distill cloud API.
 *
 * Commands:
 *   distill login              — Authenticate with Distill
 *   distill sync --once        — One-shot scan, redact, and push
 *   distill sync --watch       — Watch mode (continuous sync)
 *   distill sync --self-host   — Override API base URL
 *   distill status             — Show sync status
 */

import { Command } from "commander";
import { watch } from "chokidar";
import { join } from "node:path";
import { homedir } from "node:os";
import { login, getToken, isLoggedIn, getStoredApiUrl } from "./auth.js";
import { scanSessions, loadSyncState, saveSyncState } from "./scanner.js";
import { syncSessions } from "./sync.js";

const DEFAULT_API_URL = "https://api.distill.dev";

const program = new Command();

program
  .name("distill")
  .description("Distill CLI — sync Claude sessions to the cloud")
  .version("0.1.0");

// ── login ────────────────────────────────────────────────────────────────────

program
  .command("login")
  .description("Authenticate with Distill via browser")
  .option("--api-url <url>", "API base URL", DEFAULT_API_URL)
  .action(async (opts: { apiUrl: string }) => {
    await login(opts.apiUrl);
  });

// ── sync ─────────────────────────────────────────────────────────────────────

program
  .command("sync")
  .description("Sync Claude sessions to the Distill API")
  .option("--once", "One-shot sync (scan, redact, push, exit)")
  .option("--watch", "Watch mode — continuously sync on file changes")
  .option("--self-host <url>", "Override API base URL")
  .action(async (opts: { once?: boolean; watch?: boolean; selfHost?: string }) => {
    // Resolve API URL
    const apiUrl = opts.selfHost
      ?? process.env["DISTILL_API_URL"]
      ?? (await getStoredApiUrl())
      ?? DEFAULT_API_URL;

    // Check auth
    const token = await getToken();
    if (!token) {
      console.error("Not logged in. Run `distill login` first.");
      process.exit(1);
    }

    const claudeDir = join(homedir(), ".claude", "projects");

    if (opts.watch) {
      // ── Watch mode ──
      console.log(`Watching ${claudeDir} for changes...`);
      console.log(`API: ${apiUrl}`);
      console.log("Press Ctrl+C to stop.\n");

      // Do an initial sync
      await runOneSync(claudeDir, apiUrl, token);

      // Set up file watcher
      const watcher = watch(join(claudeDir, "**", "*.jsonl"), {
        ignoreInitial: true,
        awaitWriteFinish: {
          stabilityThreshold: 2000,
          pollInterval: 500,
        },
      });

      // Debounce: collect changes for 5 seconds before syncing
      let debounceTimer: ReturnType<typeof setTimeout> | null = null;

      const triggerSync = () => {
        if (debounceTimer) clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
          await runOneSync(claudeDir, apiUrl, token);
        }, 5000);
      };

      watcher.on("add", (path) => {
        console.log(`New session: ${path}`);
        triggerSync();
      });

      watcher.on("change", (path) => {
        console.log(`Updated session: ${path}`);
        triggerSync();
      });

      // Keep the process alive
      await new Promise(() => {});
    } else {
      // ── One-shot mode (default) ──
      await runOneSync(claudeDir, apiUrl, token);
    }
  });

// ── status ───────────────────────────────────────────────────────────────────

program
  .command("status")
  .description("Show sync status")
  .action(async () => {
    const loggedIn = await isLoggedIn();
    const state = await loadSyncState();
    const syncedCount = Object.keys(state.syncedSessions).length;

    console.log("Distill Sync Status");
    console.log("─".repeat(40));
    console.log(`  Logged in:       ${loggedIn ? "Yes" : "No"}`);

    if (state.lastSyncTime > 0) {
      const lastSync = new Date(state.lastSyncTime);
      const ago = formatTimeAgo(state.lastSyncTime);
      console.log(`  Last sync:       ${lastSync.toLocaleString()} (${ago})`);
    } else {
      console.log("  Last sync:       Never");
    }

    console.log(`  Sessions synced: ${syncedCount}`);

    if (loggedIn) {
      const apiUrl = await getStoredApiUrl();
      console.log(`  API endpoint:    ${apiUrl}`);
    }
  });

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Run a single sync cycle: scan for new sessions, sync them, update state.
 */
async function runOneSync(baseDir: string, apiUrl: string, token: string): Promise<void> {
  const state = await loadSyncState();
  const sessions = await scanSessions(baseDir, state.lastSyncTime);

  if (sessions.length === 0) {
    console.log("Everything up to date.");
    return;
  }

  console.log(`Found ${sessions.length} new/modified session(s).`);
  const synced = await syncSessions(sessions, apiUrl, token);

  if (synced > 0) {
    // Update state
    const now = Date.now();
    for (const session of sessions) {
      state.syncedSessions[session.sessionId] = session.lastModified;
    }
    state.lastSyncTime = now;
    await saveSyncState(state);
    console.log(`Sync complete: ${synced} session(s) pushed.`);
  }
}

/**
 * Format a timestamp as a human-readable "time ago" string.
 */
function formatTimeAgo(timestamp: number): string {
  const seconds = Math.floor((Date.now() - timestamp) / 1000);
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ── Run ──────────────────────────────────────────────────────────────────────

program.parse();
