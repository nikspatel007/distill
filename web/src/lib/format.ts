/**
 * Convert an ugly project path or kebab-case name into a human-readable title.
 *
 * Examples:
 *   "-Users-nikpatel-Documents-GitHub-distill" -> "Distill"
 *   "my-cool-project"                          -> "My Cool Project"
 *   "my_cool_project"                         -> "My Cool Project"
 */
export function formatProjectName(name: string): string {
	// Strip leading separators and split on common path separators
	let cleaned = name.replace(/^[-_/\\]+/, "");

	// If it looks like a path (contains multiple segments separated by - that look like dirs),
	// take the last meaningful segment
	const segments = cleaned.split(/[-/\\]/);
	if (segments.length > 3) {
		// Likely a path like "Users-nikpatel-Documents-GitHub-distill"
		// Take the last non-empty segment
		const last = segments.filter(Boolean).pop();
		if (last) cleaned = last;
	}

	// Convert kebab-case or snake_case to Title Case
	const titled = cleaned
		.split(/[-_]+/)
		.filter(Boolean)
		.map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
		.join(" ");

	// Truncate if needed
	if (titled.length > 30) {
		return `${titled.slice(0, 27)}...`;
	}

	return titled;
}
