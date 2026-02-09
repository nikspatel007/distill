/**
 * Pipeline routes — trigger and monitor distill pipeline runs from the web UI.
 */
import { type ChildProcess, spawn } from "node:child_process";
import { Hono } from "hono";
import { getConfig } from "../lib/config.js";

interface PipelineState {
	status: "idle" | "running" | "completed" | "failed";
	log: string;
	startedAt: string | null;
	completedAt: string | null;
	error: string | null;
	process: ChildProcess | null;
}

const state: PipelineState = {
	status: "idle",
	log: "",
	startedAt: null,
	completedAt: null,
	error: null,
	process: null,
};

function getProjectDir(): string {
	const config = getConfig();
	if (config.PROJECT_DIR) return config.PROJECT_DIR;
	return process.cwd();
}

const pipelineRoutes = new Hono();

pipelineRoutes.post("/api/pipeline/run", (c) => {
	if (state.status === "running") {
		return c.json({ error: "Pipeline is already running" }, 409);
	}

	const config = getConfig();
	const projectDir = getProjectDir();
	const id = `run-${Date.now()}`;

	state.status = "running";
	state.log = "";
	state.startedAt = new Date().toISOString();
	state.completedAt = null;
	state.error = null;

	const child = spawn(
		"python",
		["-m", "distill", "run", "--dir", projectDir, "--output", config.OUTPUT_DIR],
		{
			cwd: projectDir,
			stdio: ["ignore", "pipe", "pipe"],
			env: { ...process.env },
		},
	);

	state.process = child;

	child.stdout?.on("data", (data: Buffer) => {
		state.log += data.toString();
	});

	child.stderr?.on("data", (data: Buffer) => {
		state.log += data.toString();
	});

	child.on("close", (code) => {
		state.completedAt = new Date().toISOString();
		state.process = null;
		if (code === 0) {
			state.status = "completed";
		} else {
			state.status = "failed";
			state.error = `Process exited with code ${code}`;
		}
	});

	child.on("error", (err) => {
		state.completedAt = new Date().toISOString();
		state.process = null;
		state.status = "failed";
		state.error = err.message;
	});

	return c.json({ id, started: true });
});

pipelineRoutes.get("/api/pipeline/status", (c) => {
	return c.json({
		status: state.status,
		log: state.log,
		startedAt: state.startedAt,
		completedAt: state.completedAt,
		error: state.error,
	});
});

export default pipelineRoutes;

// Exported for testing
export { state as _pipelineState };
