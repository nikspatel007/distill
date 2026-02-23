import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";

// Use dynamic import to control env vars before module loads
let troopxTools: typeof import("../tools/troopx.js");

describe("TroopX Tools", () => {
	const testDir = join(tmpdir(), `troopx-test-${Date.now()}`);

	beforeEach(async () => {
		// Set up test directory structure
		mkdirSync(join(testDir, "memory"), { recursive: true });
		mkdirSync(join(testDir, "knowledge"), { recursive: true });

		writeFileSync(
			join(testDir, "memory", "MEMORY-dev.md"),
			"# Dev Memory\n\nAlways use batch queries.",
		);
		writeFileSync(
			join(testDir, "knowledge", "learnings.md"),
			"# Learnings\n\n- Use connection pooling",
		);

		// Set env vars before importing
		process.env["TROOPX_PROJECT_DIR"] = testDir;
		process.env["TROOPX_HOME"] = join(testDir, "home");
		// Ensure DB connection will fail gracefully
		process.env["TROOPX_DB_URL"] = "postgresql://invalid:invalid@localhost:1/invalid";

		// Fresh import
		troopxTools = await import("../tools/troopx.js");
	});

	afterEach(() => {
		rmSync(testDir, { recursive: true, force: true });
		delete process.env["TROOPX_PROJECT_DIR"];
		delete process.env["TROOPX_HOME"];
		delete process.env["TROOPX_DB_URL"];
	});

	test("getTroopxMemory reads project memory files", async () => {
		const result = await troopxTools.getTroopxMemory({});
		const devMemory = result.memories.find(
			(m) => m.role === "dev" && m.source === "project-memory",
		);
		expect(devMemory).toBeDefined();
		expect(devMemory?.content).toContain("batch queries");
	});

	test("getTroopxMemory reads knowledge learnings", async () => {
		const result = await troopxTools.getTroopxMemory({});
		const knowledge = result.memories.find((m) => m.source === "knowledge");
		expect(knowledge).toBeDefined();
		expect(knowledge?.content).toContain("connection pooling");
	});

	test("getTroopxMemory filters by role", async () => {
		const result = await troopxTools.getTroopxMemory({ role: "dev" });
		const devMemories = result.memories.filter((m) => m.role === "dev");
		expect(devMemories.length).toBeGreaterThan(0);
		// Knowledge (role=team) should not appear when filtering by role
		const knowledge = result.memories.filter((m) => m.source === "knowledge");
		expect(knowledge.length).toBe(0);
	});

	test("searchTroopx returns error when DB unavailable", async () => {
		const result = await troopxTools.searchTroopx({ query: "test" });
		expect(result.error).toBeDefined();
		expect(result.results).toEqual([]);
	});

	test("listTroopxWorkflows returns error when DB unavailable", async () => {
		const result = await troopxTools.listTroopxWorkflows({});
		expect(result.error).toBeDefined();
		expect(result.workflows).toEqual([]);
	});

	test("getTroopxWorkflow returns error when DB unavailable", async () => {
		const result = await troopxTools.getTroopxWorkflow({ workflow_id: "test-id" });
		expect(result.error).toBeDefined();
	});
});
