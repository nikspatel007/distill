import { createClient } from "@supabase/supabase-js";
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

export async function authMiddleware(c: Context, next: Next) {
  const config = getConfig();
  const authHeader = c.req.header("Authorization");

  if (!authHeader?.startsWith("Bearer ")) {
    return c.json({ error: "Missing authorization header" }, 401);
  }

  const token = authHeader.slice(7);
  const supabase = createClient(config.SUPABASE_URL, config.SUPABASE_ANON_KEY);

  const { data, error } = await supabase.auth.getUser(token);
  if (error || !data.user) {
    return c.json({ error: "Invalid or expired token" }, 401);
  }

  c.set("user", { id: data.user.id, email: data.user.email });
  await next();
}
