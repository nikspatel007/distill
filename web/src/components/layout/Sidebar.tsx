import { Link } from "@tanstack/react-router";
import type { LucideIcon } from "lucide-react";
import {
	BookMarked,
	BookOpen,
	FolderKanban,
	LayoutDashboard,
	PenLine,
	Settings,
	Wand2,
} from "lucide-react";

const navItems: { to: string; label: string; icon: LucideIcon }[] = [
	{ to: "/", label: "Dashboard", icon: LayoutDashboard },
	{ to: "/projects", label: "Projects", icon: FolderKanban },
	{ to: "/journal", label: "Journal", icon: BookOpen },
	{ to: "/blog", label: "Blog", icon: PenLine },
	{ to: "/reading", label: "Reading", icon: BookMarked },
	{ to: "/studio", label: "Studio", icon: Wand2 },
	{ to: "/settings", label: "Settings", icon: Settings },
];

// Mobile: the 5 things you actually use on your phone
const mobileTabItems: { to: string; label: string; icon: LucideIcon }[] = [
	{ to: "/", label: "Home", icon: LayoutDashboard },
	{ to: "/journal", label: "Journal", icon: BookOpen },
	{ to: "/blog", label: "Blog", icon: PenLine },
	{ to: "/studio", label: "Studio", icon: Wand2 },
	{ to: "/reading", label: "Reading", icon: BookMarked },
];

export function Sidebar() {
	return (
		<>
			{/* Desktop sidebar — hidden on mobile */}
			<nav className="hidden md:flex w-56 flex-col border-r border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900">
				<div className="p-4">
					<Link to="/" className="group">
						<h1 className="text-lg font-bold tracking-tight group-hover:text-indigo-600 dark:group-hover:text-indigo-400">
							Distill
						</h1>
					</Link>
					<p className="text-xs text-zinc-500">Knowledge cockpit</p>
				</div>
				<ul className="flex-1 space-y-0.5 px-2">
					{navItems.map((item) => (
						<li key={item.to}>
							<Link
								to={item.to}
								className="flex items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors hover:bg-zinc-100 dark:hover:bg-zinc-800 [&.active]:bg-indigo-50 [&.active]:text-indigo-700 dark:[&.active]:bg-indigo-950 dark:[&.active]:text-indigo-300"
								activeProps={{ className: "active" }}
							>
								<item.icon className="h-4 w-4" />
								{item.label}
							</Link>
						</li>
					))}
				</ul>
				<div className="border-t border-zinc-200 p-4 text-xs text-zinc-400 dark:border-zinc-800">
					distill v0.1.0
				</div>
			</nav>

			{/* Mobile: bottom tab bar only — clean, no hamburger, no top bar */}
			<nav className="fixed bottom-0 left-0 right-0 z-40 flex border-t border-zinc-200 bg-white/95 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/95 md:hidden pb-[env(safe-area-inset-bottom)]">
				{mobileTabItems.map((item) => (
					<Link
						key={item.to}
						to={item.to}
						className="flex flex-1 flex-col items-center gap-0.5 py-2.5 text-xs text-zinc-500 transition-colors [&.active]:text-indigo-600 dark:[&.active]:text-indigo-400"
						activeProps={{ className: "active" }}
					>
						<item.icon className="h-5 w-5" />
						{item.label}
					</Link>
				))}
			</nav>
		</>
	);
}
