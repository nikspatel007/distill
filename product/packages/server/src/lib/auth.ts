import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import type { Context, Next } from "hono";
import { getConfig } from "./config.js";

export type AuthUser = {
  id: string;
  email?: string;
};

// Extend Hono context with user
declare module "hono" {
  interface ContextVariableMap {
    user: AuthUser;
  }
}

let _supabase: SupabaseClient | null = null;

function getSupabase(): SupabaseClient {
  if (!_supabase) {
    const config = getConfig();
    _supabase = createClient(config.SUPABASE_URL, config.SUPABASE_ANON_KEY);
  }
  return _supabase;
}

// Cache verified tokens for 5 minutes to avoid hitting Supabase on every request
const tokenCache = new Map<string, { user: AuthUser; expiresAt: number }>();
const CACHE_TTL_MS = 5 * 60 * 1000;

function getCachedUser(token: string): AuthUser | null {
  const entry = tokenCache.get(token);
  if (!entry) return null;
  if (Date.now() > entry.expiresAt) {
    tokenCache.delete(token);
    return null;
  }
  return entry.user;
}

function cacheUser(token: string, user: AuthUser) {
  // Evict old entries if cache grows too large
  if (tokenCache.size > 1000) {
    const now = Date.now();
    for (const [key, val] of tokenCache) {
      if (now > val.expiresAt) tokenCache.delete(key);
    }
  }
  tokenCache.set(token, { user, expiresAt: Date.now() + CACHE_TTL_MS });
}

export async function authMiddleware(c: Context, next: Next) {
  const authHeader = c.req.header("Authorization");

  if (!authHeader?.startsWith("Bearer ")) {
    return c.json({ error: "Missing authorization header" }, 401);
  }

  const token = authHeader.slice(7);

  // Check cache first
  const cached = getCachedUser(token);
  if (cached) {
    c.set("user", cached);
    return next();
  }

  // Verify with Supabase
  const supabase = getSupabase();
  const { data, error } = await supabase.auth.getUser(token);
  if (error || !data.user) {
    return c.json({ error: "Invalid or expired token" }, 401);
  }

  const user: AuthUser = { id: data.user.id, email: data.user.email };
  cacheUser(token, user);
  c.set("user", user);
  await next();
}
