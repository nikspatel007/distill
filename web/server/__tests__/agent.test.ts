import { describe, expect, test } from "bun:test";
import { getModel, isAgentConfigured } from "../lib/agent.js";

describe("isAgentConfigured", () => {
	test("returns false when no API key", () => {
		const orig = process.env["ANTHROPIC_API_KEY"];
		delete process.env["ANTHROPIC_API_KEY"];
		expect(isAgentConfigured()).toBe(false);
		if (orig) process.env["ANTHROPIC_API_KEY"] = orig;
	});

	test("returns true when API key is set", () => {
		const orig = process.env["ANTHROPIC_API_KEY"];
		process.env["ANTHROPIC_API_KEY"] = "sk-test";
		expect(isAgentConfigured()).toBe(true);
		if (orig) process.env["ANTHROPIC_API_KEY"] = orig;
		else delete process.env["ANTHROPIC_API_KEY"];
	});
});

describe("getModel", () => {
	test("returns a model object", () => {
		const model = getModel();
		expect(model).toBeDefined();
		expect(model.modelId).toBe("claude-sonnet-4-5-20250929");
	});
});
