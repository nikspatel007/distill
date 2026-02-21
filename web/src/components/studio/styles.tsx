/**
 * Shared style constants for Studio pages.
 */
export const TYPE_STYLES: Record<string, string> = {
	weekly: "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
	thematic: "bg-purple-50 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
	digest: "bg-orange-50 text-orange-700 dark:bg-orange-950 dark:text-orange-300",
	"daily-social": "bg-pink-50 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
	daily_social: "bg-pink-50 text-pink-700 dark:bg-pink-950 dark:text-pink-300",
	seed: "bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
	reading_list: "bg-teal-50 text-teal-700 dark:bg-teal-950 dark:text-teal-300",
	journal: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
};
export const DEFAULT_TYPE_STYLE = "bg-zinc-50 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";

export const STATUS_STYLES: Record<string, string> = {
	draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
	review: "bg-indigo-50 text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300",
	ready: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
	published: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
	archived: "bg-zinc-50 text-zinc-400 dark:bg-zinc-900 dark:text-zinc-500",
};
export const DEFAULT_STATUS_STYLE = "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";

export function StatusBadge({ status }: { status: string }) {
	return (
		<span
			className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? DEFAULT_STATUS_STYLE}`}
		>
			{status}
		</span>
	);
}
