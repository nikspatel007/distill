/**
 * Auth helpers for Distill CLI.
 *
 * Manages Supabase authentication: login via browser, token storage,
 * and token retrieval for API calls.
 */

import { readFile, writeFile, mkdir } from "node:fs/promises";
import { join, dirname } from "node:path";
import { homedir } from "node:os";
import { createClient } from "@supabase/supabase-js";

const CREDENTIALS_PATH = join(homedir(), ".distill-credentials.json");

/** Stored credentials shape. */
interface StoredCredentials {
  accessToken: string;
  refreshToken: string;
  expiresAt: number;
  apiUrl: string;
}

/** Supabase project config — set via env or defaults. */
function getSupabaseConfig(): { url: string; anonKey: string } {
  const url = process.env["SUPABASE_URL"] ?? "https://auth.distill.dev";
  const anonKey = process.env["SUPABASE_ANON_KEY"] ?? "";
  return { url, anonKey };
}

/**
 * Interactive login flow.
 *
 * Creates a Supabase client, generates an OAuth URL, opens the browser,
 * and waits for the user to complete authentication. Stores the resulting
 * tokens to ~/.distill-credentials.json.
 */
export async function login(apiUrl: string): Promise<void> {
  const { url: supabaseUrl, anonKey } = getSupabaseConfig();

  if (!anonKey) {
    console.error("Error: SUPABASE_ANON_KEY environment variable is required for login.");
    console.error("Set it to your Supabase project's anon/public key.");
    process.exit(1);
  }

  const supabase = createClient(supabaseUrl, anonKey);

  // Start OAuth flow — this generates a URL the user visits in their browser
  const { data, error } = await supabase.auth.signInWithOAuth({
    provider: "github",
    options: {
      redirectTo: `${apiUrl}/auth/callback`,
    },
  });

  if (error || !data.url) {
    console.error("Failed to start login flow:", error?.message ?? "No URL returned");
    process.exit(1);
  }

  console.log("\nOpening browser for authentication...");
  console.log(`If the browser doesn't open, visit:\n  ${data.url}\n`);

  // Open the URL in the default browser
  const openCmd = process.platform === "darwin"
    ? "open"
    : process.platform === "win32"
      ? "start"
      : "xdg-open";

  const proc = Bun.spawn([openCmd, data.url], {
    stdout: "ignore",
    stderr: "ignore",
  });
  await proc.exited;

  console.log("Waiting for authentication to complete...");
  console.log("After authenticating, paste the access token here:");

  // Read token from stdin
  const reader = Bun.stdin.stream().getReader();
  const { value } = await reader.read();
  reader.releaseLock();

  const input = value ? new TextDecoder().decode(value).trim() : "";

  if (!input) {
    console.error("No token provided. Login cancelled.");
    process.exit(1);
  }

  // Store the credentials
  const credentials: StoredCredentials = {
    accessToken: input,
    refreshToken: "",
    expiresAt: Date.now() + 7 * 24 * 60 * 60 * 1000, // 7 days default
    apiUrl,
  };

  await saveCredentials(credentials);
  console.log("Login successful! Credentials saved.");
}

/** Save credentials to disk. */
async function saveCredentials(credentials: StoredCredentials): Promise<void> {
  await mkdir(dirname(CREDENTIALS_PATH), { recursive: true });
  await writeFile(CREDENTIALS_PATH, JSON.stringify(credentials, null, 2), "utf-8");
  // Restrict file permissions to owner only
  const { chmod } = await import("node:fs/promises");
  await chmod(CREDENTIALS_PATH, 0o600);
}

/** Load stored credentials. Returns null if not found or expired. */
async function loadCredentials(): Promise<StoredCredentials | null> {
  try {
    const raw = await readFile(CREDENTIALS_PATH, "utf-8");
    const parsed: unknown = JSON.parse(raw);
    if (
      parsed &&
      typeof parsed === "object" &&
      "accessToken" in parsed &&
      "expiresAt" in parsed
    ) {
      const creds = parsed as StoredCredentials;
      if (creds.expiresAt > Date.now()) {
        return creds;
      }
      // Token expired
      return null;
    }
    return null;
  } catch {
    return null;
  }
}

/** Retrieve the stored access token. Returns null if not logged in. */
export async function getToken(): Promise<string | null> {
  const creds = await loadCredentials();
  return creds?.accessToken ?? null;
}

/** Check whether a valid (non-expired) token exists. */
export async function isLoggedIn(): Promise<boolean> {
  const creds = await loadCredentials();
  return creds !== null;
}

/** Get the stored API URL, falling back to the default. */
export async function getStoredApiUrl(): Promise<string> {
  const creds = await loadCredentials();
  return creds?.apiUrl ?? "https://api.distill.dev";
}
