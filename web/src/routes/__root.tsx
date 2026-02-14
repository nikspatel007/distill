import { Outlet } from "@tanstack/react-router";
import { Component, type ErrorInfo, type ReactNode } from "react";
import { Sidebar } from "../components/layout/Sidebar.js";

interface ErrorBoundaryProps {
	children: ReactNode;
}

interface ErrorBoundaryState {
	hasError: boolean;
	error: Error | null;
}

class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
	constructor(props: ErrorBoundaryProps) {
		super(props);
		this.state = { hasError: false, error: null };
	}

	static getDerivedStateFromError(error: Error): ErrorBoundaryState {
		return { hasError: true, error };
	}

	componentDidCatch(error: Error, info: ErrorInfo) {
		console.error("Uncaught error:", error, info);
	}

	render() {
		if (this.state.hasError) {
			return (
				<div className="flex flex-col items-center justify-center gap-4 py-20">
					<h2 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">
						Something went wrong
					</h2>
					<p className="text-sm text-zinc-500">
						{this.state.error?.message ?? "An unexpected error occurred."}
					</p>
					<button
						type="button"
						onClick={() => this.setState({ hasError: false, error: null })}
						className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
					>
						Try again
					</button>
				</div>
			);
		}
		return this.props.children;
	}
}

export function RootLayout() {
	return (
		<div className="flex h-screen">
			<Sidebar />
			<main className="flex-1 overflow-y-auto p-6">
				<div className="mx-auto max-w-5xl">
					<ErrorBoundary>
						<Outlet />
					</ErrorBoundary>
				</div>
			</main>
		</div>
	);
}
