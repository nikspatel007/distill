import { ChevronDown, ChevronUp, ExternalLink } from "lucide-react";
import { useState } from "react";
import type { ContentItem } from "../../../shared/schemas.js";

const SOURCE_BADGE_COLORS: Record<string, string> = {
	browser: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
	rss: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
	substack: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200",
	gmail: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
	linkedin: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
	reddit: "bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200",
	youtube: "bg-rose-100 text-rose-800 dark:bg-rose-900 dark:text-rose-200",
	twitter: "bg-sky-100 text-sky-800 dark:bg-sky-900 dark:text-sky-200",
};

const DEFAULT_BADGE = "bg-zinc-100 text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300";

interface Props {
	item: ContentItem;
}

export function ContentItemCard({ item }: Props) {
	const [expanded, setExpanded] = useState<boolean>(false);
	const badgeColor = SOURCE_BADGE_COLORS[item.source] ?? DEFAULT_BADGE;

	return (
		<button
			type="button"
			className="w-full cursor-pointer rounded-lg border border-zinc-200 p-4 text-left transition-colors hover:border-zinc-300 hover:bg-zinc-50 dark:border-zinc-800 dark:hover:border-zinc-700 dark:hover:bg-zinc-900"
			onClick={() => setExpanded((prev) => !prev)}
		>
			<div className="flex items-start justify-between gap-3">
				<div className="min-w-0 flex-1">
					<span className="font-medium">{item.title || "(untitled)"}</span>
					{expanded && item.url && (
						<a
							href={item.url}
							target="_blank"
							rel="noopener noreferrer"
							className="ml-1.5 inline-flex items-center text-indigo-600 hover:text-indigo-800 dark:text-indigo-400 dark:hover:text-indigo-300"
							onClick={(e) => e.stopPropagation()}
						>
							<ExternalLink className="h-3.5 w-3.5" />
						</a>
					)}
					{item.site_name && <span className="ml-2 text-sm text-zinc-500">{item.site_name}</span>}
				</div>
				<span className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${badgeColor}`}>
					{item.source}
				</span>
			</div>

			{item.excerpt && (
				<p
					className={`mt-2 text-sm text-zinc-600 dark:text-zinc-400 ${expanded ? "" : "line-clamp-2"}`}
				>
					{item.excerpt}
				</p>
			)}

			<div className="mt-2 flex items-center justify-between gap-2">
				<div className="flex flex-wrap items-center gap-1.5 text-xs text-zinc-500">
					{item.author && <span>by {item.author}</span>}
					{item.word_count > 0 && <span>{item.word_count.toLocaleString()} words</span>}
					{(expanded ? item.tags : item.tags.slice(0, 3)).map((tag) => (
						<span key={tag} className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">
							{tag}
						</span>
					))}
					{!expanded && item.tags.length > 3 && (
						<span className="text-xs text-zinc-400">+{item.tags.length - 3} more</span>
					)}
				</div>
				{expanded ? (
					<ChevronUp className="h-4 w-4 shrink-0 text-zinc-400" />
				) : (
					<ChevronDown className="h-4 w-4 shrink-0 text-zinc-400" />
				)}
			</div>
		</button>
	);
}
