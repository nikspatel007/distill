/**
 * TroopX tools — query workflow data, blackboard entries, and agent memories.
 *
 * Connects to TroopX PostgreSQL database for live queries.
 * Falls back gracefully if DB is not available.
 */
import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import pg from "pg";

const { Pool } = pg;

// Lazy singleton pool
let pool: pg.Pool | null = null;
let poolFailed = false;

function getDbUrl(): string {
	return process.env["TROOPX_DB_URL"] ?? "postgresql://troopx:troopx@localhost:15432/troopx";
}

function getPool(): pg.Pool | null {
	if (poolFailed) return null;
	if (!pool) {
		try {
			pool = new Pool({
				connectionString: getDbUrl(),
				max: 3,
				idleTimeoutMillis: 30000,
				connectionTimeoutMillis: 5000,
			});
			pool.on("error", () => {
				poolFailed = true;
				pool = null;
			});
		} catch {
			poolFailed = true;
			return null;
		}
	}
	return pool;
}

async function query(sql: string, params: unknown[] = []): Promise<pg.QueryResult | null> {
	const p = getPool();
	if (!p) return null;
	try {
		return await p.query(sql, params);
	} catch {
		return null;
	}
}

/**
 * Search across blackboard entries, workflow descriptions, and escalation reasons.
 */
export async function searchTroopx(params: {
	query: string;
	limit?: number;
}): Promise<{ results: unknown[]; error?: string }> {
	const limit = params.limit ?? 20;
	const pattern = `%${params.query}%`;

	const result = await query(
		`(
			SELECT 'blackboard' AS type, namespace || '/' || key AS title,
				   LEFT(value, 500) AS snippet, contributor_role AS author,
				   workflow_id, created_at
			FROM blackboard_entries
			WHERE value ILIKE $1 OR key ILIKE $1 OR namespace ILIKE $1
			ORDER BY created_at DESC
			LIMIT $2
		)
		UNION ALL
		(
			SELECT 'workflow' AS type, task_description AS title,
				   status AS snippet, '' AS author,
				   workflow_id, started_at AS created_at
			FROM router_workflow_metadata
			WHERE task_description ILIKE $1
			ORDER BY started_at DESC
			LIMIT $2
		)
		UNION ALL
		(
			SELECT 'escalation' AS type, reason AS title,
				   LEFT(context, 500) AS snippet, '' AS author,
				   workflow_id, created_at
			FROM router_escalations
			WHERE reason ILIKE $1 OR context ILIKE $1
			ORDER BY created_at DESC
			LIMIT $2
		)
		ORDER BY created_at DESC
		LIMIT $2`,
		[pattern, limit],
	);

	if (!result) {
		return { results: [], error: "TroopX DB not available" };
	}

	return { results: result.rows };
}

/**
 * Get full workflow details: metadata, blackboard entries, signals, escalations.
 */
export async function getTroopxWorkflow(params: {
	workflow_id: string;
}): Promise<{ workflow: unknown; error?: string }> {
	const metaResult = await query(
		`SELECT workflow_id, task_description, status, started_at, ended_at
		 FROM router_workflow_metadata WHERE workflow_id = $1`,
		[params.workflow_id],
	);

	if (!metaResult) {
		return { workflow: null, error: "TroopX DB not available" };
	}

	if (metaResult.rows.length === 0) {
		return { workflow: null, error: "Workflow not found" };
	}

	const meta = metaResult.rows[0];

	const [bbResult, sigResult, escResult, msgResult] = await Promise.all([
		query(
			`SELECT namespace, key, LEFT(value, 1000) AS value, contributor_role, created_at
			 FROM blackboard_entries WHERE workflow_id = $1 ORDER BY created_at`,
			[params.workflow_id],
		),
		query(
			`SELECT signal_type, message, role, created_at
			 FROM router_signals WHERE workflow_id = $1 ORDER BY created_at`,
			[params.workflow_id],
		),
		query(
			`SELECT reason, context, response_signal, created_at
			 FROM router_escalations WHERE workflow_id = $1 ORDER BY created_at`,
			[params.workflow_id],
		),
		query(
			`SELECT body, from_agent_id, to_agent_id, created_at
			 FROM router_messages WHERE workflow_id = $1 ORDER BY created_at LIMIT 50`,
			[params.workflow_id],
		),
	]);

	return {
		workflow: {
			...meta,
			blackboard: bbResult?.rows ?? [],
			signals: sigResult?.rows ?? [],
			escalations: escResult?.rows ?? [],
			messages: msgResult?.rows ?? [],
		},
	};
}

/**
 * List recent workflows with status and brief description.
 */
export async function listTroopxWorkflows(params: {
	limit?: number;
	status?: string;
	pattern?: string;
}): Promise<{ workflows: unknown[]; error?: string }> {
	const limit = params.limit ?? 20;
	const conditions: string[] = [];
	const values: unknown[] = [];
	let paramIdx = 1;

	if (params.status) {
		conditions.push(`status = $${paramIdx}`);
		values.push(params.status);
		paramIdx++;
	}

	if (params.pattern) {
		conditions.push(`task_description ILIKE $${paramIdx}`);
		values.push(`%${params.pattern}%`);
		paramIdx++;
	}

	const where = conditions.length > 0 ? `WHERE ${conditions.join(" AND ")}` : "";

	values.push(limit);

	const result = await query(
		`SELECT workflow_id, task_description, status, started_at, ended_at
		 FROM router_workflow_metadata
		 ${where}
		 ORDER BY started_at DESC
		 LIMIT $${paramIdx}`,
		values,
	);

	if (!result) {
		return { workflows: [], error: "TroopX DB not available" };
	}

	return { workflows: result.rows };
}

/**
 * Read agent working memories and learnings from the file system.
 */
export async function getTroopxMemory(params: {
	role?: string;
}): Promise<{
	memories: Array<{ role: string; source: string; content: string }>;
	error?: string;
}> {
	const memories: Array<{ role: string; source: string; content: string }> = [];

	// Project-level memories
	const projectDir = process.env["TROOPX_PROJECT_DIR"] ?? "";
	if (projectDir) {
		const memoryDir = join(projectDir, "memory");
		try {
			const files = await readdir(memoryDir);
			for (const file of files) {
				if (!file.startsWith("MEMORY-") || !file.endsWith(".md")) continue;
				const role = file.replace("MEMORY-", "").replace(".md", "");
				if (params.role && role !== params.role) continue;
				const content = await readFile(join(memoryDir, file), "utf-8");
				if (content.trim()) {
					memories.push({ role, source: "project-memory", content });
				}
			}
		} catch {
			// Directory doesn't exist
		}

		// Knowledge/learnings
		if (!params.role) {
			try {
				const learnings = await readFile(join(projectDir, "knowledge", "learnings.md"), "utf-8");
				if (learnings.trim()) {
					memories.push({ role: "team", source: "knowledge", content: learnings });
				}
			} catch {
				// File doesn't exist
			}
		}
	}

	// Home-level roster
	const troopxHome = process.env["TROOPX_HOME"] ?? join(process.env["HOME"] ?? "", ".troopx");
	const rosterDir = join(troopxHome, "roster");
	try {
		const roles = await readdir(rosterDir);
		for (const role of roles) {
			if (params.role && role !== params.role) continue;
			try {
				const content = await readFile(join(rosterDir, role, "CLAUDE.md"), "utf-8");
				if (content.trim()) {
					memories.push({ role, source: "roster-identity", content });
				}
			} catch {
				// File doesn't exist for this role
			}
		}
	} catch {
		// Roster directory doesn't exist
	}

	return { memories };
}
