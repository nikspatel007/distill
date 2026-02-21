import { afterEach, beforeEach, describe, expect, mock, test } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

// Mock the @google/genai module
const mockGenerateContent = mock(() =>
	Promise.resolve({
		candidates: [
			{
				content: {
					parts: [
						{
							inlineData: {
								mimeType: "image/png",
								data: "iVBORw0KGgo=",
							},
						},
					],
				},
			},
		],
	}),
);

mock.module("@google/genai", () => ({
	GoogleGenAI: class {
		models = {
			generateContent: mockGenerateContent,
		};
	},
}));

const { isImageConfigured, generateImage, STYLE_PREFIXES } = await import("../lib/images.js");

const ENV_KEY = "GOOGLE_AI_API_KEY";

/** Save, set, and restore GOOGLE_AI_API_KEY without triggering biome/tsc lint. */
function getKey(): string | undefined {
	return process.env[ENV_KEY];
}
function setKey(value: string): void {
	process.env[ENV_KEY] = value;
}
function clearKey(): void {
	process.env[ENV_KEY] = "";
}
function restoreKey(orig: string | undefined): void {
	if (orig !== undefined) {
		process.env[ENV_KEY] = orig;
	} else {
		process.env[ENV_KEY] = "";
	}
}

let tempDir: string;

beforeEach(() => {
	tempDir = mkdtempSync(join(tmpdir(), "images-test-"));
});

afterEach(() => {
	rmSync(tempDir, { recursive: true, force: true });
});

describe("isImageConfigured", () => {
	test("returns false when no API key", () => {
		const orig = getKey();
		clearKey();
		expect(isImageConfigured()).toBe(false);
		restoreKey(orig);
	});

	test("returns true when API key is set", () => {
		const orig = getKey();
		setKey("test-key");
		expect(isImageConfigured()).toBe(true);
		restoreKey(orig);
	});
});

describe("STYLE_PREFIXES", () => {
	test("has all 8 moods", () => {
		const expected = [
			"reflective",
			"energetic",
			"cautionary",
			"triumphant",
			"intimate",
			"technical",
			"playful",
			"somber",
		];
		for (const mood of expected) {
			expect(STYLE_PREFIXES[mood]).toBeDefined();
		}
	});
});

describe("generateImage", () => {
	test("returns null when not configured", async () => {
		const orig = getKey();
		clearKey();
		const result = await generateImage("test prompt", { outputDir: tempDir });
		expect(result).toBeNull();
		restoreKey(orig);
	});

	test("generates image and returns metadata", async () => {
		const orig = getKey();
		setKey("test-key");

		const result = await generateImage("A sunset over the ocean", {
			outputDir: tempDir,
			mood: "reflective",
		});

		expect(result).not.toBeNull();
		expect(result?.filename).toMatch(/\.png$/);
		expect(result?.relativePath).toBeDefined();
		expect(mockGenerateContent).toHaveBeenCalled();

		restoreKey(orig);
	});
});
