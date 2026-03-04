import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import type { ShareItem } from "../../shared/schemas.js";

export default function Shares() {
	const queryClient = useQueryClient();
	const [newUrl, setNewUrl] = useState("");
	const [newNote, setNewNote] = useState("");
	const [showUsed, setShowUsed] = useState(false);

	const { data, isLoading } = useQuery<{ shares: ShareItem[] }>({
		queryKey: ["shares"],
		queryFn: async () => {
			const res = await fetch("/api/shares");
			if (!res.ok) throw new Error("Failed to load shares");
			return res.json();
		},
	});

	const addShare = useMutation({
		mutationFn: async ({ url, note }: { url: string; note: string }) => {
			const res = await fetch("/api/shares", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ url, note, tags: [] }),
			});
			if (!res.ok) throw new Error("Failed to add share");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["shares"] });
			queryClient.invalidateQueries({ queryKey: ["dashboard"] });
			setNewUrl("");
			setNewNote("");
		},
	});

	const removeShare = useMutation({
		mutationFn: async (id: string) => {
			const res = await fetch(`/api/shares/${id}`, { method: "DELETE" });
			if (!res.ok) throw new Error("Failed to remove share");
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["shares"] });
			queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		},
	});

	const allShares = data?.shares ?? [];
	const pending = allShares.filter((s) => !s.used);
	const used = allShares.filter((s) => s.used);

	return (
		<div className="mx-auto max-w-3xl p-4 md:p-6">
			<div className="space-y-6">
				<div>
					<h2 className="text-2xl font-bold">Shared Links</h2>
					<p className="mt-1 text-sm text-zinc-500">
						URLs shared from your phone or CLI. Pending links are included in the next
						intake digest.
					</p>
				</div>

				{/* Add form */}
				<div className="rounded-lg border border-zinc-200 p-4 dark:border-zinc-800 space-y-3">
					<input
						type="url"
						value={newUrl}
						onChange={(e) => setNewUrl(e.target.value)}
						placeholder="https://..."
						className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
						onKeyDown={(e) => {
							if (e.key === "Enter" && newUrl.trim()) {
								addShare.mutate({ url: newUrl.trim(), note: newNote.trim() });
							}
						}}
					/>
					<textarea
						value={newNote}
						onChange={(e) => setNewNote(e.target.value)}
						placeholder="Note (optional)"
						rows={2}
						className="w-full rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
					/>
					<button
						type="button"
						disabled={!newUrl.trim() || addShare.isPending}
						onClick={() => addShare.mutate({ url: newUrl.trim(), note: newNote.trim() })}
						className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
					>
						Add
					</button>
				</div>

				{/* Pending list */}
				{isLoading && <p className="text-sm text-zinc-500">Loading...</p>}

				{!isLoading && pending.length === 0 && (
					<p className="text-sm text-zinc-500">No pending shares.</p>
				)}

				{pending.length > 0 && (
					<div className="space-y-3">
						<h3 className="text-sm font-semibold text-zinc-600 dark:text-zinc-400">
							Pending ({pending.length})
						</h3>
						{pending.map((share) => (
							<ShareCard
								key={share.id}
								share={share}
								onRemove={() => removeShare.mutate(share.id)}
							/>
						))}
					</div>
				)}

				{/* Used section */}
				{used.length > 0 && (
					<div className="space-y-3">
						<button
							type="button"
							onClick={() => setShowUsed(!showUsed)}
							className="text-sm font-semibold text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
						>
							{showUsed ? "Hide" : "Show"} processed ({used.length})
						</button>
						{showUsed &&
							used.map((share) => (
								<ShareCard key={share.id} share={share} used />
							))}
					</div>
				)}
			</div>
		</div>
	);
}

function ShareCard({
	share,
	onRemove,
	used,
}: {
	share: ShareItem;
	onRemove?: () => void;
	used?: boolean;
}) {
	const navigate = useNavigate();
	const date = new Date(share.created_at).toLocaleDateString();
	const displayTitle = share.title || extractDomain(share.url);
	const hasContent = !!share.excerpt;

	return (
		<div
			onClick={() => navigate({ to: "/shares/$id", params: { id: share.id } })}
			className={`rounded-lg border p-4 cursor-pointer transition-colors hover:border-indigo-400 dark:hover:border-indigo-600 ${used ? "border-zinc-100 bg-zinc-50 dark:border-zinc-800 dark:bg-zinc-900/50 opacity-60" : "border-zinc-200 dark:border-zinc-800"}`}
		>
			<div className="flex items-start justify-between gap-2">
				<div className="min-w-0 flex-1 space-y-1">
					<div className="flex items-center gap-2">
						<span className="text-sm font-medium text-indigo-600 dark:text-indigo-400">
							{displayTitle}
						</span>
						{!hasContent && (
							<span className="text-xs text-zinc-400 bg-zinc-100 dark:bg-zinc-800 px-1.5 py-0.5 rounded">
								not fetched
							</span>
						)}
					</div>
					{share.author && (
						<p className="text-xs text-zinc-500">by {share.author}</p>
					)}
					{hasContent && (
						<p className="text-sm text-zinc-600 dark:text-zinc-400 line-clamp-2">
							{share.excerpt?.replace(/[#*>\-`]/g, "").slice(0, 200)}
						</p>
					)}
					{share.note && (
						<p className="text-sm italic text-zinc-500">{share.note}</p>
					)}
					<div className="flex items-center gap-2 text-xs text-zinc-400">
						<span>{date}</span>
						<span className="text-zinc-300 dark:text-zinc-700">|</span>
						<a
							href={share.url}
							target="_blank"
							rel="noopener noreferrer"
							className="truncate max-w-xs hover:text-indigo-500"
							onClick={(e) => e.stopPropagation()}
						>
							{share.url}
						</a>
						{share.used_in && (
							<>
								<span className="text-zinc-300 dark:text-zinc-700">|</span>
								<span>Used in: {share.used_in}</span>
							</>
						)}
					</div>
				</div>
				{onRemove && !used && (
					<button
						type="button"
						onClick={(e) => {
							e.stopPropagation();
							onRemove();
						}}
						className="text-xs text-zinc-400 hover:text-red-500 shrink-0"
					>
						Remove
					</button>
				)}
			</div>
		</div>
	);
}

function extractDomain(url: string): string {
	try {
		return new URL(url).hostname.replace("www.", "");
	} catch {
		return url;
	}
}
