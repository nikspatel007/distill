import { describe, expect, test } from "bun:test";
import { getModel, isAgentConfigured } from "../lib/agent.js";

const ENV_KEY = "ANTHROPIC_API_KEY";

function getKey(): string | undefined {
	return process.env[ENV_KEY];
}
function setKey(value: string | undefined): void {
	process.env[ENV_KEY] = value as string;
}
function clearKey(): void {
	process.env[ENV_KEY] = "";
}

describe("isAgentConfigured", () => {
	test("returns false when no API key", () => {
		const orig = getKey();
		clearKey();
		expect(isAgentConfigured()).toBe(false);
		setKey(orig as string);
	});

	test("returns true when API key is set", () => {
		const orig = getKey();
		setKey("sk-test");
		expect(isAgentConfigured()).toBe(true);
		if (orig) setKey(orig);
		else clearKey();
	});
});

describe("getModel", () => {
	test("returns a model object", () => {
		const model = getModel();
		expect(model).toBeDefined();
		expect(model.modelId).toBe("claude-sonnet-4-5-20250929");
	});
});
