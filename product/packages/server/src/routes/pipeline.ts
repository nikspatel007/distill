import { Hono } from "hono";
import { runPipelineForUser } from "../pipeline/intake.js";

const app = new Hono();

// POST /api/pipeline/run — trigger pipeline for current user
app.post("/run", async (c) => {
  const user = c.get("user");
  try {
    const result = await runPipelineForUser(user.id);
    return c.json(result);
  } catch (err) {
    return c.json({ error: String(err) }, 500);
  }
});

export default app;
