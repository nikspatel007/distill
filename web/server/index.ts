/**
 * Hono server — mounts API routes and serves static React build.
 */
import { Hono } from "hono";
import { serveStatic } from "hono/bun";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { getConfig } from "./lib/config.js";
import blog from "./routes/blog.js";
import calendar from "./routes/calendar.js";
import config from "./routes/config.js";
import dashboard from "./routes/dashboard.js";
import home from "./routes/home.js";
import journal from "./routes/journal.js";
import memory from "./routes/memory.js";
import notes from "./routes/notes.js";
import pipeline from "./routes/pipeline.js";
import projects from "./routes/projects.js";
import publish from "./routes/publish.js";
import reading from "./routes/reading.js";
import seeds from "./routes/seeds.js";
import studio from "./routes/studio.js";

const app = new Hono();

// Middleware
app.use("*", logger());
app.use("/api/*", cors());

// API routes
app.route("/", config);
app.route("/", pipeline);
app.route("/", dashboard);
app.route("/", home);
app.route("/", journal);
app.route("/", blog);
app.route("/", calendar);
app.route("/", reading);
app.route("/", projects);
app.route("/", publish);
app.route("/", studio);
app.route("/", seeds);
app.route("/", notes);
app.route("/", memory);

// Health check
app.get("/api/health", (c) => c.json({ status: "ok" }));

// Static files + SPA fallback (serve built frontend when dist/ exists)
import { existsSync } from "node:fs";
import { resolve } from "node:path";

const distDir = resolve(import.meta.dir, "../dist");
if (existsSync(distDir)) {
	app.use("/*", serveStatic({ root: "./dist" }));
	// SPA fallback — serve index.html for non-API routes
	app.get("*", serveStatic({ path: "./dist/index.html" }));
}

// Export type for Hono RPC client
export type AppType = typeof app;
export { app };

// Start server when run directly
if (import.meta.main) {
	const config = getConfig();
	const hasTLS = config.TLS_CERT && config.TLS_KEY;

	console.log(`Reading data from: ${config.OUTPUT_DIR}`);

	// Always start HTTP server
	Bun.serve({
		fetch: app.fetch,
		port: config.PORT,
	});
	console.log(`Distill web server (HTTP) on port ${config.PORT}`);

	// Also start HTTPS if TLS certs are configured
	if (hasTLS) {
		const tlsPort = config.TLS_PORT;
		Bun.serve({
			fetch: app.fetch,
			port: tlsPort,
			tls: {
				certFile: config.TLS_CERT,
				keyFile: config.TLS_KEY,
			},
		});
		console.log(`Distill web server (HTTPS) on port ${tlsPort}`);
	}
}
