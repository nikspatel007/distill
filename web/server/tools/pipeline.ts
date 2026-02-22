import { getConfig } from "../lib/config.js";

// Parameter interfaces
interface RunParams {
	project?: string;
	skip_journal?: boolean;
	skip_intake?: boolean;
	skip_blog?: boolean;
	force?: boolean;
}

interface JournalParams {
	project?: string;
	date?: string;
	since?: string;
	force?: boolean;
}

interface BlogParams {
	project?: string;
	type?: string;
	week?: string;
	force?: boolean;
}

interface IntakeParams {
	project?: string;
	sources?: string;
	use_defaults?: boolean;
}

interface SeedParams {
	text: string;
	tags?: string;
}

interface NoteParams {
	text: string;
	target?: string;
}

type PipelineParams =
	| RunParams
	| JournalParams
	| BlogParams
	| IntakeParams
	| SeedParams
	| NoteParams;

// Exported for testing
export function buildPipelineCommand(command: string, params: PipelineParams): string[] {
	const config = getConfig();
	const args = ["uv", "run", "python", "-m", "distill", command];

	// Always add --output if available
	if (config.OUTPUT_DIR) {
		args.push("--output", config.OUTPUT_DIR);
	}

	// Add --dir for commands that need project dir
	if (config.PROJECT_DIR && ["run", "journal", "analyze"].includes(command)) {
		args.push("--dir", config.PROJECT_DIR);
	}

	// Command-specific flags
	if (command === "run") {
		const p = params as RunParams;
		if (p.skip_journal) args.push("--skip-journal");
		if (p.skip_intake) args.push("--skip-intake");
		if (p.skip_blog) args.push("--skip-blog");
		if (p.force) args.push("--force");
	} else if (command === "journal") {
		const p = params as JournalParams;
		// Always add --global for journal
		args.push("--global");
		if (p.date) args.push("--date", p.date);
		if (p.since) args.push("--since", p.since);
		if (p.force) args.push("--force");
	} else if (command === "blog") {
		const p = params as BlogParams;
		if (p.type) args.push("--type", p.type);
		if (p.week) args.push("--week", p.week);
		if (p.force) args.push("--force");
	} else if (command === "intake") {
		const p = params as IntakeParams;
		if (p.use_defaults) args.push("--use-defaults");
		if (p.sources) args.push("--sources", p.sources);
	} else if (command === "seed") {
		const p = params as SeedParams;
		// Positional arg comes first, then flags
		if (p.text) args.push(p.text);
		if (p.tags) args.push("--tags", p.tags);
	} else if (command === "note") {
		const p = params as NoteParams;
		// Positional arg comes first, then flags
		if (p.text) args.push(p.text);
		if (p.target) args.push("--target", p.target);
	}

	return args;
}

// Actual execution function (not tested — calls subprocess)
async function execPipeline(
	command: string,
	params: PipelineParams,
): Promise<{ success: boolean; output: string; error?: string }> {
	const args = buildPipelineCommand(command, params);
	try {
		const proc = Bun.spawn(args, {
			stdout: "pipe",
			stderr: "pipe",
			cwd: process.cwd(),
		});
		const stdout = await new Response(proc.stdout).text();
		const stderr = await new Response(proc.stderr).text();
		const exitCode = await proc.exited;
		if (exitCode !== 0) {
			return {
				success: false,
				output: stdout,
				error: stderr || `Exit code ${exitCode}`,
			};
		}
		return {
			success: true,
			output: stdout || "Command completed successfully.",
		};
	} catch (err) {
		return {
			success: false,
			output: "",
			error: err instanceof Error ? err.message : "Unknown error",
		};
	}
}

// Export all tool functions
export async function runPipeline(
	params: RunParams,
): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("run", params);
}

export async function runJournal(
	params: JournalParams,
): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("journal", params);
}

export async function runBlog(
	params: BlogParams,
): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("blog", params);
}

export async function runIntake(
	params: IntakeParams,
): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("intake", params);
}

export async function addSeed(
	params: SeedParams,
): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("seed", params);
}

export async function addNote(
	params: NoteParams,
): Promise<{ success: boolean; output: string; error?: string }> {
	return execPipeline("note", params);
}
