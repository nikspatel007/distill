/**
 * Server configuration — Zod-validated environment variables.
 */
import { z } from "zod";

const EnvSchema = z.object({
	OUTPUT_DIR: z.string().min(1),
	PORT: z.coerce.number().default(6107),
	PROJECT_DIR: z.string().default(""),
	POSTIZ_URL: z.string().default(""),
	POSTIZ_API_KEY: z.string().default(""),
	GHOST_URL: z.string().default(""),
	GHOST_ADMIN_API_KEY: z.string().default(""),
	GHOST_LABEL: z.string().default(""),
	GHOST_PERSONAL_URL: z.string().default(""),
	GHOST_PERSONAL_ADMIN_API_KEY: z.string().default(""),
	GHOST_PERSONAL_LABEL: z.string().default(""),
	TLS_CERT: z.string().default(""),
	TLS_KEY: z.string().default(""),
	TLS_PORT: z.coerce.number().default(6117),
});

export type ServerConfig = z.infer<typeof EnvSchema>;
export type ServerConfigInput = z.input<typeof EnvSchema>;

let _config: ServerConfig | null = null;

export function getConfig(): ServerConfig {
	if (_config) return _config;
	_config = EnvSchema.parse(process.env);
	return _config;
}

export function setConfig(config: z.input<typeof EnvSchema>): void {
	_config = EnvSchema.parse(config);
}

export function resetConfig(): void {
	_config = null;
}
