import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useState } from "react";
import type { IntakeDigest, SeedIdea } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";

export default function Reading() {
	const queryClient = useQueryClient();
	const [newSeed, setNewSeed] = useState("");

	const { data: digestsData } = useQuery<{ digests: IntakeDigest[] }>({
		queryKey: ["reading"],
		queryFn: async () => {
			const res = await fetch("/api/reading/digests");
			if (!res.ok) throw new Error("Failed to load digests");
			return res.json();
		},
	});

	const { data: seedsData } = useQuery<{ seeds: SeedIdea[] }>({
		queryKey: ["seeds"],
		queryFn: async () => {
			const res = await fetch("/api/seeds");
			if (!res.ok) throw new Error("Failed to load seeds");
			return res.json();
		},
	});

	const addSeed = useMutation({
		mutationFn: async (text: string) => {
			const res = await fetch("/api/seeds", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ text, tags: [] }),
			});
			if (!res.ok) throw new Error("Failed to add seed");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["seeds"] });
			setNewSeed("");
		},
	});

	const deleteSeed = useMutation({
		mutationFn: async (id: string) => {
			const res = await fetch(`/api/seeds/${id}`, { method: "DELETE" });
			if (!res.ok) throw new Error("Failed to delete seed");
		},
		onSuccess: () => queryClient.invalidateQueries({ queryKey: ["seeds"] }),
	});

	const digests = digestsData?.digests ?? [];
	const seeds = seedsData?.seeds ?? [];

	return (
		<div className="space-y-8">
			<h2 className="text-2xl font-bold">Reading</h2>

			{/* Seeds section */}
			<section>
				<h3 className="mb-3 text-lg font-semibold">Seed Ideas</h3>
				<form
					className="mb-4 flex gap-2"
					onSubmit={(e) => {
						e.preventDefault();
						if (newSeed.trim()) addSeed.mutate(newSeed.trim());
					}}
				>
					<input
						type="text"
						value={newSeed}
						onChange={(e) => setNewSeed(e.target.value)}
						placeholder="Add a seed idea..."
						className="flex-1 rounded-lg border border-zinc-200 bg-white px-3 py-2 text-sm dark:border-zinc-700 dark:bg-zinc-900"
					/>
					<button
						type="submit"
						disabled={!newSeed.trim() || addSeed.isPending}
						className="rounded-lg bg-indigo-600 px-4 py-2 text-sm text-white hover:bg-indigo-700 disabled:opacity-50"
					>
						Add
					</button>
				</form>
				{seeds.length === 0 ? (
					<p className="text-sm text-zinc-500">No seeds yet.</p>
				) : (
					<div className="space-y-2">
						{seeds.map((seed) => (
							<div
								key={seed.id}
								className="flex items-center justify-between rounded-lg border border-zinc-200 p-3 dark:border-zinc-800"
							>
								<div>
									<span className={seed.used ? "text-zinc-400 line-through" : ""}>{seed.text}</span>
									{seed.tags.length > 0 && (
										<span className="ml-2 text-xs text-zinc-500">{seed.tags.join(", ")}</span>
									)}
								</div>
								<button
									type="button"
									onClick={() => deleteSeed.mutate(seed.id)}
									className="text-xs text-red-500 hover:text-red-700"
								>
									Delete
								</button>
							</div>
						))}
					</div>
				)}
			</section>

			{/* Digests section */}
			<section>
				<h3 className="mb-3 text-lg font-semibold">Intake Digests</h3>
				{digests.length === 0 ? (
					<p className="text-sm text-zinc-500">
						No intake digests yet. Run <code>distill intake</code> to generate some.
					</p>
				) : (
					<div className="space-y-2">
						{digests.map((d) => (
							<Link
								key={d.filename}
								to="/reading/$date"
								params={{ date: d.date }}
								className="block rounded-lg border border-zinc-200 p-4 transition-colors hover:border-zinc-400 dark:border-zinc-800 dark:hover:border-zinc-600"
							>
								<div className="flex items-center justify-between">
									<DateBadge date={d.date} />
									<span className="text-xs text-zinc-500">
										{d.itemCount} items from {d.sources.length} sources
									</span>
								</div>
							</Link>
						))}
					</div>
				)}
			</section>
		</div>
	);
}
