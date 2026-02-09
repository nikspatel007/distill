import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { EditorialNote, PostizIntegration } from "../../shared/schemas.js";

export default function Settings() {
	const queryClient = useQueryClient();
	const [newNote, setNewNote] = useState("");
	const [newTarget, setNewTarget] = useState("");

	const { data: notesData } = useQuery<{ notes: EditorialNote[] }>({
		queryKey: ["notes"],
		queryFn: async () => {
			const res = await fetch("/api/notes");
			if (!res.ok) throw new Error("Failed to load notes");
			return res.json();
		},
	});

	const { data: integrationsData } = useQuery<{
		integrations: PostizIntegration[];
		configured: boolean;
	}>({
		queryKey: ["integrations"],
		queryFn: async () => {
			const res = await fetch("/api/publish/integrations");
			if (!res.ok) throw new Error("Failed");
			return res.json();
		},
	});

	const addNote = useMutation({
		mutationFn: async ({ text, target }: { text: string; target: string }) => {
			const res = await fetch("/api/notes", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ text, target }),
			});
			if (!res.ok) throw new Error("Failed to add note");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["notes"] });
			setNewNote("");
			setNewTarget("");
		},
	});

	const deleteNote = useMutation({
		mutationFn: async (id: string) => {
			const res = await fetch(`/api/notes/${id}`, { method: "DELETE" });
			if (!res.ok) throw new Error("Failed to delete note");
		},
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["notes"] }),
	});

	const notes = notesData?.notes ?? [];

	return (
		<div className="space-y-8">
			<h2 className="text-2xl font-bold">Settings</h2>

			{/* Postiz connection */}
			<section>
				<h3 className="mb-3 text-lg font-semibold">Postiz Connection</h3>
				{integrationsData?.configured ? (
					<div>
						<p className="mb-2 text-sm text-green-600">Connected</p>
						{(integrationsData.integrations ?? []).length > 0 && (
							<div className="space-y-1">
								{integrationsData.integrations.map((i) => (
									<div key={i.id} className="text-sm text-zinc-600 dark:text-zinc-400">
										{i.name} ({i.provider})
									</div>
								))}
							</div>
						)}
					</div>
				) : (
					<p className="text-sm text-zinc-500">
						Not configured. Set <code>POSTIZ_URL</code> and <code>POSTIZ_API_KEY</code> environment
						variables.
					</p>
				)}
			</section>

			{/* Editorial notes */}
			<section>
				<h3 className="mb-3 text-lg font-semibold">Editorial Notes</h3>
				<form
					className="mb-4 space-y-2"
					onSubmit={(e) => {
						e.preventDefault();
						if (newNote.trim()) addNote.mutate({ text: newNote.trim(), target: newTarget });
					}}
				>
					<input
						type="text"
						value={newNote}
						onChange={(e) => setNewNote(e.target.value)}
						placeholder="Add editorial direction..."
						className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
					/>
					<div className="flex gap-2">
						<input
							type="text"
							value={newTarget}
							onChange={(e) => setNewTarget(e.target.value)}
							placeholder="Target (e.g., week:2026-W06)"
							className="flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
						/>
						<button
							type="submit"
							disabled={!newNote.trim() || addNote.isPending}
							className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
						>
							Add Note
						</button>
					</div>
				</form>
				{notes.length === 0 ? (
					<p className="text-sm text-zinc-500">No editorial notes.</p>
				) : (
					<div className="space-y-2">
						{notes.map((note) => (
							<div
								key={note.id}
								className="flex items-start justify-between rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
							>
								<div>
									<span className={note.used ? "text-zinc-400 line-through" : ""}>{note.text}</span>
									{note.target && (
										<span className="ml-2 rounded bg-purple-50 px-1.5 py-0.5 text-xs text-purple-700 dark:bg-purple-950 dark:text-purple-300">
											{note.target}
										</span>
									)}
								</div>
								<button
									type="button"
									onClick={() => deleteNote.mutate(note.id)}
									className="ml-2 text-xs text-red-500 hover:text-red-700"
								>
									Delete
								</button>
							</div>
						))}
					</div>
				)}
			</section>
		</div>
	);
}
