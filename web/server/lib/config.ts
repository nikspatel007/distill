/**
 * Server configuration — Zod-validated environment variables.
 */
import { z } from "zod";

const EnvSchema = z.object({
	OUTPUT_DIR: z.string().min(1),
	PORT: z.coerce.number().default(4321),
	PROJECT_DIR: z.string().default(""),
	POSTIZ_URL: z.string().default(""),
	POSTIZ_API_KEY: z.string().default(""),
});

export type ServerConfig = z.infer<typeof EnvSchema>;

let _config: ServerConfig | null = null;

export function getConfig(): ServerConfig {
	if (_config) return _config;
	_config = EnvSchema.parse(process.env);
	return _config;
}

export function setConfig(config: ServerConfig): void {
	_config = config;
}

export function resetConfig(): void {
	_config = null;
}
