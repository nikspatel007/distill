import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import type { BlogPost } from "../../shared/schemas.js";
import { DateBadge } from "../components/shared/DateBadge.js";
import { ProjectFilterPills } from "../components/shared/ProjectFilterPills.js";
import { TagBadge } from "../components/shared/TagBadge.js";
import { relativeDate } from "../lib/dates.js";

const LAST_VISIT_KEY = "blog-last-visit";

function isRecent(dateStr: string): boolean {
	const now = new Date();
	const then = new Date(dateStr);
	const diffMs = now.getTime() - then.getTime();
	return diffMs < 7 * 24 * 60 * 60 * 1000;
}

export default function BlogList() {
	const [filterProject, setFilterProject] = useState<string | null>(null);
	const [lastVisit, setLastVisit] = useState<string | null>(null);

	useEffect(() => {
		setLastVisit(localStorage.getItem(LAST_VISIT_KEY));
		const timer = setTimeout(() => {
			localStorage.setItem(LAST_VISIT_KEY, new Date().toISOString());
		}, 2000);
		return () => clearTimeout(timer);
	}, []);

	const { data, isLoading } = useQuery<{ posts: BlogPost[] }>({
		queryKey: ["blog"],
		queryFn: async () => {
			const res = await fetch("/api/blog/posts");
			if (!res.ok) throw new Error("Failed to load blog posts");
			return res.json();
		},
	});

	if (isLoading)
		return (
			<div className="mx-auto max-w-5xl p-6">
				<div className="animate-pulse text-zinc-400">Loading blog posts...</div>
			</div>
		);

	const allPosts = data?.posts ?? [];
	const projectNames = [...new Set(allPosts.flatMap((p) => p.projects))].sort();
	const filtered = filterProject
		? allPosts.filter((p) => p.projects.includes(filterProject))
		: allPosts;

	const posts = [...filtered].sort((a, b) => b.date.localeCompare(a.date));

	return (
		<div className="mx-auto max-w-5xl p-6">
			<div className="space-y-6">
				<h2 className="text-2xl font-bold">Blog ({posts.length})</h2>

				<ProjectFilterPills
					projectNames={projectNames}
					filterProject={filterProject}
					onFilterChange={setFilterProject}
				/>

				{posts.length === 0 ? (
					<p className="text-zinc-500">
						{filterProject
							? `No blog posts for project "${filterProject}".`
							: "No blog posts yet. Run `distill blog` to generate some."}
					</p>
				) : (
					<div className="space-y-2">
						{posts.map((post) => {
							const isNew = lastVisit ? post.date > lastVisit.slice(0, 10) : false;
							const recent = isRecent(post.date);
							const published = post.platformsPublished.length > 0;

							return (
								<Link
									key={post.slug}
									to="/blog/$slug"
									params={{ slug: post.slug }}
									className="block rounded-lg border border-zinc-200 p-4 transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
								>
									<div className="flex items-center justify-between">
										<div className="flex items-center gap-2">
											<span
												className={`font-medium ${recent ? "" : "text-zinc-600 dark:text-zinc-400"}`}
											>
												{post.title}
											</span>
											{isNew && (
												<span className="rounded-full bg-indigo-100 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
													New
												</span>
											)}
											<span
												className={`rounded-full px-2 py-0.5 text-xs font-medium ${
													post.postType === "weekly"
														? "bg-blue-50 text-blue-700 dark:bg-blue-950 dark:text-blue-300"
														: "bg-green-50 text-green-700 dark:bg-green-950 dark:text-green-300"
												}`}
											>
												{post.postType}
											</span>
											{published ? (
												<span className="rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700 dark:bg-green-900 dark:text-green-300">
													Published
												</span>
											) : (
												<span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700 dark:bg-amber-900 dark:text-amber-300">
													Draft
												</span>
											)}
										</div>
										<div className="flex items-center gap-2">
											<span className="text-xs text-zinc-500 dark:text-zinc-400">
												{relativeDate(post.date)}
											</span>
											<DateBadge date={post.date} />
										</div>
									</div>
									<div className="mt-2 flex flex-wrap gap-1">
										{post.themes.map((t) => (
											<TagBadge key={t} tag={t} />
										))}
									</div>
								</Link>
							);
						})}
					</div>
				)}
			</div>
		</div>
	);
}
