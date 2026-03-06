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
