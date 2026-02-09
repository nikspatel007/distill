import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdir } from "node:fs/promises";
import { join } from "node:path";
import { app } from "../index.js";
import { resetConfig, setConfig } from "../lib/config.js";
import { _pipelineState } from "../routes/pipeline.js";

const TMP_DIR = join(import.meta.dir, "fixtures", "_tmp_pipeline");

describe("Pipeline API", () => {
	beforeEach(async () => {
		await mkdir(TMP_DIR, { recursive: true });
		setConfig({
			OUTPUT_DIR: TMP_DIR,
			PORT: 3001,
			PROJECT_DIR: TMP_DIR,
			POSTIZ_URL: "",
			POSTIZ_API_KEY: "",
		});
		// Reset pipeline state
		_pipelineState.status = "idle";
		_pipelineState.log = "";
		_pipelineState.startedAt = null;
		_pipelineState.completedAt = null;
		_pipelineState.error = null;
		_pipelineState.process = null;
	});

	afterEach(() => {
		// Kill any running process
		if (_pipelineState.process) {
			_pipelineState.process.kill();
			_pipelineState.process = null;
		}
		_pipelineState.status = "idle";
		resetConfig();
	});

	test("GET /api/pipeline/status returns idle initially", async () => {
		const res = await app.request("/api/pipeline/status");
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.status).toBe("idle");
		expect(data.log).toBe("");
		expect(data.startedAt).toBeNull();
		expect(data.completedAt).toBeNull();
		expect(data.error).toBeNull();
	});

	test("POST /api/pipeline/run returns started response", async () => {
		const res = await app.request("/api/pipeline/run", { method: "POST" });
		expect(res.status).toBe(200);
		const data = await res.json();
		expect(data.started).toBe(true);
		expect(data.id).toMatch(/^run-/);

		// startedAt should be set regardless of whether the process is still alive
		expect(_pipelineState.startedAt).toBeTruthy();

		// Clean up — process may have already exited in test environment
		if (_pipelineState.process) {
			_pipelineState.process.kill();
		}
	});

	test("POST /api/pipeline/run rejects if already running", async () => {
		_pipelineState.status = "running";

		const res = await app.request("/api/pipeline/run", { method: "POST" });
		expect(res.status).toBe(409);
		const data = await res.json();
		expect(data.error).toContain("already running");
	});

	test("GET /api/pipeline/status shows completed state", async () => {
		_pipelineState.status = "completed";
		_pipelineState.log = "Pipeline complete!\n  Total outputs: 3";
		_pipelineState.startedAt = "2026-02-09T10:00:00Z";
		_pipelineState.completedAt = "2026-02-09T10:01:00Z";

		const res = await app.request("/api/pipeline/status");
		const data = await res.json();
		expect(data.status).toBe("completed");
		expect(data.log).toContain("Pipeline complete");
		expect(data.completedAt).toBeTruthy();
	});

	test("GET /api/pipeline/status shows failed state", async () => {
		_pipelineState.status = "failed";
		_pipelineState.error = "Process exited with code 1";
		_pipelineState.startedAt = "2026-02-09T10:00:00Z";
		_pipelineState.completedAt = "2026-02-09T10:00:30Z";

		const res = await app.request("/api/pipeline/status");
		const data = await res.json();
		expect(data.status).toBe("failed");
		expect(data.error).toContain("code 1");
	});
});
