/**
 * Typed file readers and writers for JSON and Markdown files.
 */
import { access, readFile, readdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import type { ZodType } from "zod";

/**
 * Read and validate a JSON file against a Zod schema.
 * Returns null if the file doesn't exist or fails validation.
 */
export async function readJson<Output, Input = unknown>(
	path: string,
	// biome-ignore lint/suspicious/noExplicitAny: Zod's ZodDef requires any
	schema: ZodType<Output, any, Input>,
): Promise<Output | null> {
	try {
		const raw = await readFile(path, "utf-8");
		const data = JSON.parse(raw);
		return schema.parse(data);
	} catch {
		return null;
	}
}

/**
 * Read a markdown file and return its contents.
 * Returns null if the file doesn't exist.
 */
export async function readMarkdown(path: string): Promise<string | null> {
	try {
		return await readFile(path, "utf-8");
	} catch {
		return null;
	}
}

/**
 * Write markdown content to a file within baseDir.
 * Validates the file exists and the resolved path stays within baseDir
 * to prevent path traversal attacks.
 */
export async function writeMarkdown(
	filePath: string,
	content: string,
	baseDir: string,
): Promise<void> {
	const resolvedBase = resolve(baseDir);
	const resolvedFile = resolve(filePath);

	if (!resolvedFile.startsWith(resolvedBase)) {
		throw new Error("Path traversal not allowed");
	}

	// Ensure file exists (no arbitrary file creation)
	await access(resolvedFile);
	await writeFile(resolvedFile, content, "utf-8");
}

/**
 * List files in a directory matching an optional pattern.
 * Returns empty array if directory doesn't exist.
 */
export async function listFiles(dir: string, pattern?: RegExp): Promise<string[]> {
	try {
		const entries = await readdir(dir);
		const filtered = pattern ? entries.filter((f) => pattern.test(f)) : entries;
		return filtered.map((f) => join(dir, f)).sort();
	} catch {
		return [];
	}
}
