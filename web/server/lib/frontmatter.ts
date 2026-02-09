/**
 * YAML frontmatter parser — extracts frontmatter and body from markdown.
 */
import type { ZodType } from "zod";

const FRONTMATTER_RE = /^---\n([\s\S]*?)\n---\n?([\s\S]*)$/;
const FRONTMATTER_BLOCK_RE = /^(---\n[\s\S]*?\n---\n?)/;

export interface ParsedMarkdown<T> {
	frontmatter: T;
	content: string;
}

/**
 * Parse a simple YAML-like frontmatter block.
 * Handles scalar values, simple arrays (both inline and indented).
 */
function parseSimpleYaml(yaml: string): Record<string, unknown> {
	const result: Record<string, unknown> = {};
	const lines = yaml.split("\n");
	let currentKey = "";
	let currentArray: string[] | null = null;

	for (const line of lines) {
		// Skip empty lines
		if (line.trim() === "") continue;

		// Indented array item (  - value)
		const arrayItemMatch = line.match(/^\s+-\s+(.+)$/);
		if (arrayItemMatch && currentArray) {
			currentArray.push(arrayItemMatch[1]?.trim() ?? "");
			continue;
		}

		// Save any pending array
		if (currentArray) {
			result[currentKey] = currentArray;
			currentArray = null;
		}

		// Key: value pair
		const kvMatch = line.match(/^(\w[\w_]*)\s*:\s*(.*)$/);
		if (kvMatch) {
			const key = kvMatch[1] ?? "";
			const value = kvMatch[2]?.trim() ?? "";

			if (value === "" || value === "[]") {
				// Start of an array block or empty array
				currentKey = key;
				currentArray = value === "[]" ? null : [];
				if (value === "[]") {
					result[key] = [];
				}
				continue;
			}

			// Inline array: [a, b, c]
			if (value.startsWith("[") && value.endsWith("]")) {
				const inner = value.slice(1, -1);
				result[key] = inner
					? inner.split(",").map((s) => s.trim().replace(/^['"]|['"]$/g, ""))
					: [];
				continue;
			}

			// Numeric
			if (/^-?\d+(\.\d+)?$/.test(value)) {
				result[key] = Number(value);
				continue;
			}

			// Boolean
			if (value === "true") {
				result[key] = true;
				continue;
			}
			if (value === "false") {
				result[key] = false;
				continue;
			}

			// String (strip quotes if present)
			result[key] = value.replace(/^['"]|['"]$/g, "");
		}
	}

	// Save any final pending array
	if (currentArray) {
		result[currentKey] = currentArray;
	}

	return result;
}

/**
 * Extract the raw frontmatter block (---\n...\n---\n) from a markdown string.
 * Returns the exact bytes — no re-serialization — so metadata is preserved.
 */
export function extractFrontmatterBlock(raw: string): string | null {
	const match = raw.match(FRONTMATTER_BLOCK_RE);
	return match?.[1] ?? null;
}

/**
 * Reconstruct a full markdown file by preserving the original frontmatter
 * block and replacing the body with new content.
 */
export function reconstructMarkdown(raw: string, newBody: string): string {
	const block = extractFrontmatterBlock(raw);
	if (!block) return newBody;

	// Ensure frontmatter block ends with exactly one newline
	const normalizedBlock = block.endsWith("\n") ? block : `${block}\n`;
	return `${normalizedBlock}\n${newBody}\n`;
}

/**
 * Parse a markdown file with YAML frontmatter, validating against a Zod schema.
 * Returns null if no frontmatter or validation fails.
 */
export function parseFrontmatter<Output, Input = unknown>(
	raw: string,
	// biome-ignore lint/suspicious/noExplicitAny: Zod's ZodDef requires any
	schema: ZodType<Output, any, Input>,
): ParsedMarkdown<Output> | null {
	const match = raw.match(FRONTMATTER_RE);
	if (!match) return null;

	const yamlStr = match[1] ?? "";
	const content = match[2] ?? "";

	try {
		const parsed = parseSimpleYaml(yamlStr);
		const validated = schema.parse(parsed);
		return { frontmatter: validated, content: content.trim() };
	} catch {
		return null;
	}
}
