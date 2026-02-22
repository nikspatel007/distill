import { describe, expect, test } from "bun:test";

describe("MCP server", () => {
	test("createMcpServer returns a server instance", async () => {
		const { createMcpServer } = await import("../mcp/server.js");
		const server = createMcpServer();
		expect(server).toBeDefined();
	});
});
