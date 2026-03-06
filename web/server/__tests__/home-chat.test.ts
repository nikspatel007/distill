import { describe, expect, test } from "bun:test";
import { setConfig } from "../lib/config.js";

// Set test config before importing app
setConfig({ OUTPUT_DIR: import.meta.dir + "/fixtures", PORT: 6109 });

import { app } from "../index.js";

describe("POST /api/home/chat", () => {
	test("returns 503 when ANTHROPIC_API_KEY not set", async () => {
		const originalKey = process.env["ANTHROPIC_API_KEY"];
		delete process.env["ANTHROPIC_API_KEY"];

		try {
			const res = await app.request("/api/home/chat", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					messages: [{ role: "user", parts: [{ type: "text", text: "hello" }] }],
					date: "2026-03-05",
				}),
			});
			expect(res.status).toBe(503);
			const data = await res.json();
			expect((data as { error: string }).error).toContain("ANTHROPIC_API_KEY");
		} finally {
			if (originalKey) process.env["ANTHROPIC_API_KEY"] = originalKey;
		}
	});
});
