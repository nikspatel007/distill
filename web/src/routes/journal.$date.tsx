import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "@tanstack/react-router";
import { PenLine } from "lucide-react";
import { useState } from "react";
import type { JournalDetail } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { EditToggle } from "../components/shared/EditToggle.js";
import { MarkdownEditor } from "../components/shared/MarkdownEditor.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";
import { useMarkdownSave } from "../lib/useMarkdownSave.js";

export default function JournalDetailPage() {
	const { date } = useParams({ from: "/journal/$date" });
	const [isEditing, setIsEditing] = useState(false);
	const navigate = useNavigate();
	const queryClient = useQueryClient();

	const { data, isLoading, error } = useQuery<JournalDetail>({
		queryKey: ["journal", date],
		queryFn: async () => {
			const res = await fetch(`/api/journal/${date}`);
			if (!res.ok) throw new Error("Journal entry not found");
			return res.json();
		},
	});

	const { editedContent, setEditedContent, isDirty, save, isSaving, saveSuccess } = useMarkdownSave(
		{
			endpoint: `/api/journal/${date}`,
			queryKey: ["journal", date],
			originalContent: data?.content ?? "",
		},
	);

	const createPostMutation = useMutation({
		mutationFn: async () => {
			const res = await fetch("/api/studio/items", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					title: `Post from ${date}`,
					body: data?.content ?? "",
					content_type: "journal",
					source_date: date,
					tags: data?.meta.projects ?? [],
				}),
			});
			if (!res.ok) throw new Error("Failed to create post");
			return res.json() as Promise<{ slug: string }>;
		},
		onSuccess: (result) => {
			queryClient.invalidateQueries({ queryKey: ["studio-items"] });
			navigate({ to: "/studio/$slug", params: { slug: result.slug } });
		},
	});

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

	return (
		<div className="mx-auto max-w-5xl p-6">
			<div className="space-y-4">
				<div className="flex items-center justify-between">
					<Link
						to="/journal"
						className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
					>
						&larr; Journal
					</Link>
					<div className="flex items-center gap-2">
						<button
							type="button"
							onClick={() => createPostMutation.mutate()}
							disabled={createPostMutation.isPending}
							className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
						>
							<PenLine className="h-3.5 w-3.5" />
							{createPostMutation.isPending ? "Creating..." : "Write Post"}
						</button>
						<EditToggle
							isEditing={isEditing}
							onToggle={() => setIsEditing(!isEditing)}
							onSave={save}
							isSaving={isSaving}
							isDirty={isDirty}
							saveSuccess={saveSuccess}
						/>
					</div>
				</div>

				<div className="flex items-center gap-3">
					<DateBadge date={data.meta.date} />
					<span className="text-sm text-zinc-500">{data.meta.style}</span>
					<span className="text-sm text-zinc-500">{data.meta.sessionsCount} sessions</span>
					<span className="text-sm text-zinc-500">{data.meta.durationMinutes}m</span>
				</div>

				{isEditing ? (
					<MarkdownEditor value={editedContent} onChange={setEditedContent} onSave={save} />
				) : (
					<MarkdownRenderer content={data.content} />
				)}
			</div>
		</div>
	);
}
