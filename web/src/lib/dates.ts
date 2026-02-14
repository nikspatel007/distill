/**
 * Return a human-readable relative date string for a given ISO date.
 */
export function relativeDate(dateStr: string): string {
	const now = new Date();
	const then = new Date(dateStr);

	// Strip time components for day-level comparison
	const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
	const thenStart = new Date(then.getFullYear(), then.getMonth(), then.getDate());

	const diffMs = todayStart.getTime() - thenStart.getTime();
	const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

	if (diffDays <= 0) return "today";
	if (diffDays === 1) return "yesterday";
	if (diffDays < 7) return `${diffDays} days ago`;

	if (diffDays < 30) {
		const weeks = Math.floor(diffDays / 7);
		return `${weeks} week${weeks > 1 ? "s" : ""} ago`;
	}

	const months = Math.floor(diffDays / 30);
	return `${months} month${months > 1 ? "s" : ""} ago`;
}
