import { Hono } from "hono";
import { cors } from "hono/cors";
import { logger } from "hono/logger";
import { getConfig } from "./lib/config.js";
import { authMiddleware } from "./lib/auth.js";
import briefRoutes from "./routes/brief.js";
import shareRoutes from "./routes/share.js";
import feedRoutes from "./routes/feed.js";
import sessionRoutes from "./routes/session.js";
import userRoutes from "./routes/user.js";
import chatRoutes from "./routes/chat.js";
import pipelineRoutes from "./routes/pipeline.js";

const app = new Hono();

// Middleware
app.use("*", logger());
app.use("/api/*", cors());

// Health check (no auth)
app.get("/api/health", (c) => c.json({ status: "ok", version: "0.1.0" }));

// Auth-protected API routes
app.use("/api/*", authMiddleware);
app.route("/api/user", userRoutes);
app.route("/api/brief", briefRoutes);
app.route("/api/share", shareRoutes);
app.route("/api/feed", feedRoutes);
app.route("/api/sessions", sessionRoutes);
app.route("/api/chat", chatRoutes);
app.route("/api/pipeline", pipelineRoutes);

export type AppType = typeof app;
export { app };

// Start server when run directly
if (import.meta.main) {
  const config = getConfig();
  Bun.serve({ fetch: app.fetch, port: config.PORT });
  console.log(`Distill product API on port ${config.PORT}`);
}
