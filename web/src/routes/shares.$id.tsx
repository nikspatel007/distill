import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "@tanstack/react-router";
import type { ShareItem } from "../../shared/schemas.js";
import { MarkdownRenderer } from "../components/shared/MarkdownRenderer.js";

export default function ShareDetail() {
	const { id } = useParams({ from: "/shares/$id" });

	const { data, isLoading, error } = useQuery<{ share: ShareItem }>({
		queryKey: ["share", id],
		queryFn: async () => {
			const res = await fetch(`/api/shares/${id}`);
			if (!res.ok) throw new Error("Share not found");
			return res.json();
		},
	});

	if (isLoading)
		return (
			<div className="mx-auto max-w-3xl p-4 md:p-6">
				<div className="animate-pulse text-zinc-400">Loading...</div>
			</div>
		);
	if (error || !data)
		return (
			<div className="mx-auto max-w-3xl p-4 md:p-6">
				<div className="text-red-500">Share not found</div>
			</div>
		);

	const share = data.share;
	const domain = extractDomain(share.url);
	const displayTitle = share.title || domain;
	const date = new Date(share.created_at).toLocaleDateString();

	return (
		<div className="mx-auto max-w-3xl p-4 md:p-6">
			<div className="space-y-4">
				<Link
					to="/shares"
					className="text-sm text-zinc-500 hover:text-zinc-800 dark:hover:text-zinc-200"
				>
					&larr; Shares
				</Link>

				<div className="space-y-2">
					<h1 className="text-2xl font-bold">{displayTitle}</h1>
					<div className="flex flex-wrap items-center gap-3 text-sm text-zinc-500">
						{share.author && <span>by {share.author}</span>}
						<span>{date}</span>
						<a
							href={share.url}
							target="_blank"
							rel="noopener noreferrer"
							className="text-indigo-500 hover:underline"
						>
							{domain} &nearr;
						</a>
						{share.used_in && (
							<span className="rounded bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
								{share.used_in}
							</span>
						)}
					</div>
					{share.note && (
						<p className="text-sm italic text-zinc-500 border-l-2 border-indigo-300 pl-3">
							{share.note}
						</p>
					)}
				</div>

				{share.excerpt ? (
					<div className="rounded-lg border border-zinc-200 p-6 dark:border-zinc-800">
						<MarkdownRenderer content={share.excerpt} />
					</div>
				) : (
					<div className="rounded-lg border border-zinc-200 p-6 dark:border-zinc-800 text-center">
						<p className="text-zinc-500">
							Content not yet fetched. It will be extracted when the next intake
							runs.
						</p>
						<a
							href={share.url}
							target="_blank"
							rel="noopener noreferrer"
							className="mt-2 inline-block text-indigo-500 hover:underline"
						>
							Open original &nearr;
						</a>
					</div>
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
