import { getDb, schema } from "../db/index.js";
import { runPipelineForUser } from "./intake.js";

export async function runDailyPipeline() {
  const db = getDb();
  const users = await db.select({ id: schema.users.id }).from(schema.users);

  console.log(`Running daily pipeline for ${users.length} users`);

  const results = [];
  for (const user of users) {
    try {
      console.log(`Processing user ${user.id}...`);
      const result = await runPipelineForUser(user.id);
      console.log(
        `  Ingested: ${result.itemsIngested}, Highlights: ${result.highlightsGenerated}, Errors: ${result.errors.length}`,
      );
      results.push(result);
    } catch (err) {
      console.error(`Pipeline failed for user ${user.id}:`, err);
      results.push({ userId: user.id, error: String(err) });
    }
  }

  return results;
}

// Run when executed directly
if (import.meta.main) {
  runDailyPipeline()
    .then((results) => {
      console.log(`Pipeline complete. Processed ${results.length} users.`);
      process.exit(0);
    })
    .catch((err) => {
      console.error("Pipeline failed:", err);
      process.exit(1);
    });
}
