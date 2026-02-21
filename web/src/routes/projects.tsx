import { useQuery } from "@tanstack/react-query";
import { Link } from "@tanstack/react-router";
import type { ProjectSummary } from "../../shared/schemas.js";
import { formatProjectName } from "../lib/format.js";

export default function ProjectList() {
	const { data, isLoading } = useQuery<{ projects: ProjectSummary[] }>({
		queryKey: ["projects"],
		queryFn: async () => {
			const res = await fetch("/api/projects");
			if (!res.ok) throw new Error("Failed to load projects");
			return res.json();
		},
	});

	if (isLoading)
		return (
			<div className="mx-auto max-w-5xl p-6">
				<div className="animate-pulse text-zinc-400">Loading projects...</div>
			</div>
		);

	const projects = data?.projects ?? [];

	return (
		<div className="mx-auto max-w-5xl p-6">
			<div className="space-y-6">
				<h2 className="text-2xl font-bold">Projects</h2>
				{projects.length === 0 ? (
					<p className="text-zinc-500">
						No projects found. Add <code>[[projects]]</code> to your <code>.distill.toml</code> or
						run sessions with project context.
					</p>
				) : (
					<div className="grid gap-4 sm:grid-cols-2">
						{projects.map((project) => (
							<Link
								key={project.name}
								to="/projects/$name"
								params={{ name: project.name }}
								className="block rounded-lg border border-zinc-200 p-4 transition-colors hover:bg-zinc-50 dark:border-zinc-800 dark:hover:bg-zinc-900"
							>
								<div className="flex items-center justify-between">
									<span className="text-lg font-semibold">{formatProjectName(project.name)}</span>
									{project.lastSeen && (
										<span className="text-xs text-zinc-500">Last active: {project.lastSeen}</span>
									)}
								</div>
								{project.description && (
									<p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
										{project.description}
									</p>
								)}
								<div className="mt-3 flex items-center gap-4 text-xs text-zinc-500">
									<span>{project.journalCount} journals</span>
									<span>{project.blogCount} blogs</span>
									<span>{project.totalSessions} sessions</span>
									{project.totalDurationMinutes > 0 && (
										<span>{Math.round(project.totalDurationMinutes / 60)}h total</span>
									)}
								</div>
								{project.tags.length > 0 && (
									<div className="mt-2 flex flex-wrap gap-1">
										{project.tags.slice(0, 3).map((t) => (
											<span
												key={t}
												className="rounded bg-zinc-100 px-1.5 py-0.5 text-xs dark:bg-zinc-800"
											>
												{t}
											</span>
										))}
										{project.tags.length > 3 && (
											<span className="px-1 py-0.5 text-xs text-zinc-400">
												+{project.tags.length - 3} more
											</span>
										)}
									</div>
								)}
							</Link>
						))}
					</div>
				)}
			</div>
		</div>
	);
}
