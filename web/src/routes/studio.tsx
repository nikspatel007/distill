import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { DateBadge } from "../components/shared/DateBadge.js";

interface StudioItem {
	slug: string;
	title: string;
	type: string;
	status: string;
	generated_at: string;
	platforms_ready: number;
	platforms_published: number;
}

export default function Studio() {
	const { data, isLoading } = useQuery<{ items: StudioItem[] }>({
		queryKey: ["studio-items"],
		queryFn: async () => {
			const res = await fetch("/api/studio/items");
			if (!res.ok) throw new Error("Failed to load studio items");
			return res.json();
		},
	});

	if (isLoading) {
		return <div className="animate-pulse text-zinc-400">Loading content...</div>;
	}

	const items = data?.items ?? [];

	return (
		<div className="space-y-6">
			<div>
				<h2 className="text-2xl font-bold">Content Studio</h2>
				<p className="mt-1 text-sm text-zinc-500">
					Review, refine with Claude, and publish your content.
				</p>
			</div>

			{items.length === 0 ? (
				<div className="rounded-lg border border-zinc-200 p-8 text-center dark:border-zinc-800">
					<p className="text-zinc-500">
						No content yet. Run{" "}
						<code className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800">
							distill blog
						</code>{" "}
						to generate content.
					</p>
				</div>
			) : (
				<div className="space-y-2">
					{items.map((item) => (
						<Link
							key={item.slug}
							to="/studio/$slug"
							params={{ slug: item.slug }}
							className="flex items-center justify-between rounded-lg border border-zinc-200 p-4 transition-colors hover:border-indigo-300 hover:bg-indigo-50/50 dark:border-zinc-800 dark:hover:border-indigo-800 dark:hover:bg-indigo-950/30"
						>
							<div className="flex items-center gap-3">
								<div>
									<div className="flex items-center gap-2">
										<span className="font-medium">{item.title}</span>
										<span
											className={`rounded-full px-2 py-0.5 text-xs font-medium ${
												item.type === "weekly"
													? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
													: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
											}`}
										>
											{item.type}
										</span>
									</div>
									<div className="mt-1 flex items-center gap-3 text-xs text-zinc-500">
										<DateBadge date={item.generated_at} />
										{item.platforms_ready > 0 && (
											<span>
												{item.platforms_ready} platform
												{item.platforms_ready !== 1 ? "s" : ""} ready
											</span>
										)}
										{item.platforms_published > 0 && (
											<span className="text-green-600">{item.platforms_published} published</span>
										)}
									</div>
								</div>
							</div>
							<StatusBadge status={item.status} />
						</Link>
					))}
				</div>
			)}
		</div>
	);
}

const STATUS_STYLES: Record<string, string> = {
	draft: "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400",
	ready: "bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300",
	published: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300",
};

const DEFAULT_STATUS_STYLE = "bg-zinc-100 text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400";

function StatusBadge({ status }: { status: string }) {
	return (
		<span
			className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${STATUS_STYLES[status] ?? DEFAULT_STATUS_STYLE}`}
		>
			{status}
		</span>
	);
}
