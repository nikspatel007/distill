import { afterAll, beforeEach, describe, expect, test } from "bun:test";
import { access, mkdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { readConfig, writeConfig } from "../lib/toml.js";

const TMP_DIR = join(import.meta.dir, "fixtures", "_tmp_toml");

describe("TOML helpers", () => {
	beforeEach(async () => {
		await rm(TMP_DIR, { recursive: true, force: true });
		await mkdir(TMP_DIR, { recursive: true });
	});

	afterAll(async () => {
		await rm(TMP_DIR, { recursive: true, force: true });
	});

	test("readConfig returns {} for nonexistent dir", async () => {
		const config = await readConfig(join(TMP_DIR, "nonexistent"));
		expect(config).toEqual({});
	});

	test("writeConfig + readConfig roundtrip preserves data", async () => {
		const original = {
			output: { directory: "./insights" },
			journal: { style: "casual", target_word_count: 800 },
			blog: { platforms: ["obsidian", "ghost"], include_diagrams: true },
			reddit: { client_id: "abc", client_secret: "def", username: "user1" },
		};

		await writeConfig(TMP_DIR, original);
		const result = await readConfig(TMP_DIR);

		expect(result.output?.directory).toBe("./insights");
		expect(result.journal?.style).toBe("casual");
		expect(result.journal?.target_word_count).toBe(800);
		expect(result.blog?.platforms).toEqual(["obsidian", "ghost"]);
		expect(result.blog?.include_diagrams).toBe(true);
		expect(result.reddit?.client_id).toBe("abc");
		expect(result.reddit?.client_secret).toBe("def");
		expect(result.reddit?.username).toBe("user1");
	});

	test("writeConfig creates the file", async () => {
		const filePath = join(TMP_DIR, ".distill.toml");

		// Verify file doesn't exist yet
		await expect(access(filePath)).rejects.toThrow();

		await writeConfig(TMP_DIR, { output: { directory: "./test" } });

		// File should now exist (access resolves without throwing)
		await access(filePath);
	});
});
