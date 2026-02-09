import { Outlet } from "@tanstack/react-router";
import { Sidebar } from "../components/layout/Sidebar.js";

export function RootLayout() {
	return (
		<div className="flex h-screen">
			<Sidebar />
			<main className="flex-1 overflow-y-auto p-6">
				<Outlet />
			</main>
		</div>
	);
}
