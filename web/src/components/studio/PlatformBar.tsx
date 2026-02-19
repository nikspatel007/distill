import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { PlatformContent, PostizIntegration } from "../../../shared/schemas.js";

interface PlatformBarProps {
	slug: string;
	selectedPlatform: string;
	onSelectPlatform: (platform: string) => void;
	platforms: Record<string, PlatformContent>;
}

const PLATFORMS = [
	{
		key: "ghost",
		label: "Ghost",
		color: "bg-purple-100 text-purple-700 dark:bg-purple-950 dark:text-purple-300",
		activeColor: "bg-purple-600 text-white dark:bg-purple-500 dark:text-white",
	},
	{
		key: "x",
		label: "X",
		color: "bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300",
		activeColor: "bg-sky-600 text-white dark:bg-sky-500 dark:text-white",
	},
	{
		key: "linkedin",
		label: "LinkedIn",
		color: "bg-blue-100 text-blue-700 dark:bg-blue-950 dark:text-blue-300",
		activeColor: "bg-blue-600 text-white dark:bg-blue-500 dark:text-white",
	},
	{
		key: "slack",
		label: "Slack",
		color: "bg-emerald-100 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300",
		activeColor: "bg-emerald-600 text-white dark:bg-emerald-500 dark:text-white",
	},
];

export function PlatformBar({
	slug,
	selectedPlatform,
	onSelectPlatform,
	platforms,
}: PlatformBarProps) {
	const queryClient = useQueryClient();
	const [publishError, setPublishError] = useState<string | null>(null);

	const { data: integrationsData } = useQuery<{
		integrations: PostizIntegration[];
		configured: boolean;
	}>({
		queryKey: ["studio-platforms"],
		queryFn: async () => {
			const res = await fetch("/api/studio/platforms");
			if (!res.ok) throw new Error("Failed to load platforms");
			return res.json();
		},
	});

	const publishMutation = useMutation({
		mutationFn: async () => {
			const readyPlatforms = Object.entries(platforms)
				.filter(([, p]) => p.content && !p.published)
				.map(([key]) => key);

			const res = await fetch(`/api/studio/publish/${slug}`, {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ platforms: readyPlatforms, mode: "draft" }),
			});
			if (!res.ok) {
				const err = await res.json().catch(() => ({ error: "Unknown error" }));
				throw new Error(err.error || "Publish failed");
			}
			return res.json();
		},
		onSuccess: () => {
			setPublishError(null);
			queryClient.invalidateQueries({ queryKey: ["studio-item", slug] });
		},
		onError: (err: Error) => {
			setPublishError(err.message);
		},
	});

	const readyCount = Object.values(platforms).filter((p) => p.content && !p.published).length;
	const allPublished = Object.values(platforms).every((p) => !p.content || p.published);
	const _configured = integrationsData?.configured ?? false;

	return (
		<div className="flex items-center justify-between border-b border-zinc-200 px-4 py-2 dark:border-zinc-800">
			<div className="flex items-center gap-1.5">
				{PLATFORMS.map((p) => {
					const platformData = platforms[p.key];
					const hasContent = !!platformData?.content;
					const isPublished = !!platformData?.published;
					const isSelected = selectedPlatform === p.key;

					return (
						<button
							key={p.key}
							type="button"
							onClick={() => onSelectPlatform(p.key)}
							className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium transition-all ${
								isSelected
									? hasContent
										? p.activeColor
										: "bg-zinc-600 text-white dark:bg-zinc-500"
									: hasContent
										? p.color
										: "bg-zinc-100 text-zinc-400 dark:bg-zinc-800 dark:text-zinc-500"
							}`}
						>
							{isPublished && <span>&#10003;</span>}
							{p.label}
							{hasContent && !isSelected && (
								<span className="ml-0.5 inline-block h-1.5 w-1.5 rounded-full bg-current opacity-60" />
							)}
						</button>
					);
				})}
			</div>

			<div className="flex items-center gap-3">
				{publishError && <span className="text-xs text-red-500">{publishError}</span>}
				{readyCount > 0 && !allPublished && (
					<button
						type="button"
						onClick={() => publishMutation.mutate()}
						disabled={publishMutation.isPending}
						className="rounded-lg bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
					>
						{publishMutation.isPending ? "Publishing..." : `Publish ${readyCount}`}
					</button>
				)}
			</div>
		</div>
	);
}
