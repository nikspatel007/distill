import { afterAll, beforeAll, describe, expect, test } from "bun:test";
import { resetConfig, setConfig } from "../lib/config.js";

describe("Pipeline tools", () => {
	beforeAll(() => {
		setConfig({
			OUTPUT_DIR: "/tmp/distill-test-output",
			PORT: 6109,
			PROJECT_DIR: "/tmp/distill-test-project",
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
	});

	afterAll(() => {
		resetConfig();
	});

	test("runPipeline builds correct base command with uv, --output, --dir", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("run", {});
		expect(cmd).toEqual([
			"uv",
			"run",
			"python",
			"-m",
			"distill",
			"run",
			"--output",
			"/tmp/distill-test-output",
			"--dir",
			"/tmp/distill-test-project",
		]);
	});

	test("runPipeline applies skip flags correctly", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("run", {
			skip_journal: true,
			skip_blog: true,
		});
		expect(cmd).toContain("--skip-journal");
		expect(cmd).toContain("--skip-blog");
		expect(cmd).not.toContain("--skip-intake");
	});

	test("runPipeline includes force flag when set", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("run", { force: true });
		expect(cmd).toContain("--force");
	});

	test("journal command includes --global and --date", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("journal", { date: "2026-02-21" });
		expect(cmd).toContain("--global");
		expect(cmd).toContain("--date");
		expect(cmd).toContain("2026-02-21");
	});

	test("journal command includes --since", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("journal", { since: "2026-01-01" });
		expect(cmd).toContain("--global");
		expect(cmd).toContain("--since");
		expect(cmd).toContain("2026-01-01");
	});

	test("journal command includes --force when set", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("journal", { force: true });
		expect(cmd).toContain("--force");
	});

	test("blog command includes --type", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("blog", { type: "weekly" });
		expect(cmd).toContain("--type");
		expect(cmd).toContain("weekly");
	});

	test("blog command includes --week", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("blog", { week: "2026-W07" });
		expect(cmd).toContain("--week");
		expect(cmd).toContain("2026-W07");
	});

	test("blog command includes --force when set", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("blog", { force: true });
		expect(cmd).toContain("--force");
	});

	test("intake command includes --use-defaults", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("intake", { use_defaults: true });
		expect(cmd).toContain("--use-defaults");
	});

	test("intake command includes --sources", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("intake", { sources: "rss,browser" });
		expect(cmd).toContain("--sources");
		expect(cmd).toContain("rss,browser");
	});

	test("seed command includes text as positional arg", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("seed", {
			text: "Explore LLM agents for testing",
		});
		expect(cmd).toContain("Explore LLM agents for testing");
		// Text should come after the command
		const seedIndex = cmd.indexOf("seed");
		const textIndex = cmd.indexOf("Explore LLM agents for testing");
		expect(textIndex).toBeGreaterThan(seedIndex);
	});

	test("seed command includes --tags", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("seed", {
			text: "Build better test framework",
			tags: "testing,quality",
		});
		expect(cmd).toContain("Build better test framework");
		expect(cmd).toContain("--tags");
		expect(cmd).toContain("testing,quality");
	});

	test("note command includes text as positional arg", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("note", {
			text: "Focus on performance this week",
		});
		expect(cmd).toContain("Focus on performance this week");
		// Text should come after the command
		const noteIndex = cmd.indexOf("note");
		const textIndex = cmd.indexOf("Focus on performance this week");
		expect(textIndex).toBeGreaterThan(noteIndex);
	});

	test("note command includes --target", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const cmd = buildPipelineCommand("note", {
			text: "Emphasize architecture",
			target: "week:2026-W07",
		});
		expect(cmd).toContain("Emphasize architecture");
		expect(cmd).toContain("--target");
		expect(cmd).toContain("week:2026-W07");
	});

	test("commands without project dir support skip --dir", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");
		const blogCmd = buildPipelineCommand("blog", {});
		expect(blogCmd).not.toContain("--dir");

		const intakeCmd = buildPipelineCommand("intake", {});
		expect(intakeCmd).not.toContain("--dir");

		const seedCmd = buildPipelineCommand("seed", { text: "Test idea" });
		expect(seedCmd).not.toContain("--dir");

		const noteCmd = buildPipelineCommand("note", { text: "Test note" });
		expect(noteCmd).not.toContain("--dir");
	});

	test("all commands include --output when OUTPUT_DIR is set", async () => {
		const { buildPipelineCommand } = await import("../tools/pipeline.js");

		const runCmd = buildPipelineCommand("run", {});
		expect(runCmd).toContain("--output");
		expect(runCmd).toContain("/tmp/distill-test-output");

		const journalCmd = buildPipelineCommand("journal", {});
		expect(journalCmd).toContain("--output");
		expect(journalCmd).toContain("/tmp/distill-test-output");

		const blogCmd = buildPipelineCommand("blog", {});
		expect(blogCmd).toContain("--output");
		expect(blogCmd).toContain("/tmp/distill-test-output");

		const intakeCmd = buildPipelineCommand("intake", {});
		expect(intakeCmd).toContain("--output");
		expect(intakeCmd).toContain("/tmp/distill-test-output");
	});
});
