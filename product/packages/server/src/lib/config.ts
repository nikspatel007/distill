import { z } from "zod";

const EnvSchema = z.object({
  DATABASE_URL: z.string().min(1),
  PORT: z.coerce.number().default(6107),
  SUPABASE_URL: z.string().min(1),
  SUPABASE_ANON_KEY: z.string().min(1),
  SUPABASE_SERVICE_ROLE_KEY: z.string().default(""),
  ANTHROPIC_API_KEY: z.string().default(""),
  GOOGLE_AI_API_KEY: z.string().default(""),
  NODE_ENV: z.string().default("development"),
  // Postiz (social media scheduler)
  POSTIZ_URL: z.string().default(""),
  POSTIZ_API_KEY: z.string().default(""),
  // Ghost CMS (primary instance)
  GHOST_URL: z.string().default(""),
  GHOST_ADMIN_API_KEY: z.string().default(""),
  GHOST_LABEL: z.string().default(""),
  // Ghost CMS (personal instance)
  GHOST_PERSONAL_URL: z.string().default(""),
  GHOST_PERSONAL_ADMIN_API_KEY: z.string().default(""),
  GHOST_PERSONAL_LABEL: z.string().default(""),
});

export type ServerConfig = z.infer<typeof EnvSchema>;

let _config: ServerConfig | null = null;

export function getConfig(): ServerConfig {
  if (_config) return _config;
  _config = EnvSchema.parse(process.env);
  return _config;
}

export function setConfig(overrides: Partial<z.input<typeof EnvSchema>>): void {
  _config = EnvSchema.parse({ ...process.env, ...overrides });
}
