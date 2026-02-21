import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import { useState } from "react";
import type { ContentItemsResponse, IntakeDetail } from "../../shared/schemas.js";
import { ContentItemCard } from "../components/shared/ContentItemCard.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { EditToggle } from "../components/shared/EditToggle.js";
import { MarkdownEditor } from "../components/shared/MarkdownEditor.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { SourceFilterPills } from "../components/shared/SourceFilterPills.js";
import { useMarkdownSave } from "../lib/useMarkdownSave.js";

export default function ReadingDetailPage() {
	const { date } = useParams({ from: "/reading/$date" });
	const [isEditing, setIsEditing] = useState(false);
	const [filterSource, setFilterSource] = useState<string | null>(null);
	const [page, setPage] = useState(1);

	const { data, isLoading, error } = useQuery<IntakeDetail>({
		queryKey: ["reading", date],
		queryFn: async () => {
			const res = await fetch(`/api/reading/digests/${date}`);
			if (!res.ok) throw new Error("Digest not found");
			return res.json();
		},
	});

	const { data: itemsData, isLoading: itemsLoading } = useQuery<ContentItemsResponse>({
		queryKey: ["reading-items", date, filterSource, page],
		queryFn: async () => {
			const params = new URLSearchParams({ date });
			if (filterSource) params.set("source", filterSource);
			params.set("page", String(page));
			const res = await fetch(`/api/reading/items?${params.toString()}`);
			if (!res.ok) throw new Error("Failed to load items");
			return res.json();
		},
	});

	const { editedContent, setEditedContent, isDirty, save, isSaving, saveSuccess } = useMarkdownSave(
		{
			endpoint: `/api/reading/digests/${date}`,
			queryKey: ["reading", date],
			originalContent: data?.content ?? "",
		},
	);

	if (isLoading)
		return (
			<div className="mx-auto max-w-5xl p-6">
				<div className="animate-pulse text-zinc-400">Loading...</div>
			</div>
		);
	if (error)
		return (
			<div className="mx-auto max-w-5xl p-6">
				<div className="text-red-500">Error: {error.message}</div>
			</div>
		);
	if (!data) return null;

	const items = itemsData?.items ?? [];
	const availableSources = itemsData?.available_sources ?? [];
	const totalItems = itemsData?.total_items ?? 0;
	const totalPages = itemsData?.total_pages ?? 1;
	const currentPage = itemsData?.page ?? 1;

	const rangeStart = totalItems === 0 ? 0 : (currentPage - 1) * 50 + 1;
	const rangeEnd = rangeStart === 0 ? 0 : rangeStart + items.length - 1;

	return (
		<div className="mx-auto max-w-5xl p-6">
			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<Link
						to="/reading"
						className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
					>
						&larr; Reading
					</Link>
					<EditToggle
						isEditing={isEditing}
						onToggle={() => setIsEditing(!isEditing)}
						onSave={save}
						isSaving={isSaving}
						isDirty={isDirty}
						saveSuccess={saveSuccess}
					/>
				</div>

				<div className="flex items-center gap-3">
					<DateBadge date={data.meta.date} />
					<span className="text-sm text-zinc-500">
						{data.meta.itemCount} items from {data.meta.sources.length} sources
					</span>
				</div>

				{isEditing ? (
					<MarkdownEditor value={editedContent} onChange={setEditedContent} onSave={save} />
				) : (
					<MarkdownRenderer content={data.content} />
				)}

				{/* Content Items section */}
				<div className="border-t border-zinc-200 pt-6 dark:border-zinc-800">
					<h3 className="mb-3 text-lg font-semibold">Content Items ({totalItems})</h3>
					<SourceFilterPills
						sources={availableSources}
						filterSource={filterSource}
						onFilterChange={(s) => {
							setFilterSource(s);
							setPage(1);
						}}
					/>
					{itemsLoading ? (
						<div className="mt-4 animate-pulse text-zinc-400">Loading items...</div>
					) : items.length === 0 ? (
						<p className="mt-4 text-sm text-zinc-500">No content items for this date.</p>
					) : (
						<>
							<div className="mt-4 space-y-3">
								{items.map((item) => (
									<ContentItemCard key={item.id} item={item} />
								))}
							</div>
							{/* Pagination controls */}
							{totalPages > 1 && (
								<div className="mt-4 flex items-center justify-between text-sm">
									<span className="text-zinc-500">
										Showing {rangeStart}–{rangeEnd} of {totalItems} items
									</span>
									<div className="flex gap-2">
										<button
											type="button"
											disabled={currentPage <= 1}
											onClick={() => setPage((p) => Math.max(1, p - 1))}
											className="rounded border border-zinc-300 px-3 py-1 text-sm transition-colors hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800"
										>
											Prev
										</button>
										<span className="flex items-center px-2 text-zinc-500">
											{currentPage} / {totalPages}
										</span>
										<button
											type="button"
											disabled={currentPage >= totalPages}
											onClick={() => setPage((p) => p + 1)}
											className="rounded border border-zinc-300 px-3 py-1 text-sm transition-colors hover:bg-zinc-100 disabled:opacity-40 dark:border-zinc-700 dark:hover:bg-zinc-800"
										>
											Next
										</button>
									</div>
								</div>
							)}
						</>
					)}
				</div>
			</div>
		</div>
	);
}
