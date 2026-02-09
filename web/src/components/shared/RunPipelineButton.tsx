import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { PipelineStatus } from "../../../shared/schemas.js";

export default function RunPipelineButton() {
	const queryClient = useQueryClient();
	const [showLog, setShowLog] = useState(false);

	const { data: status } = useQuery<PipelineStatus>({
		queryKey: ["pipeline-status"],
		queryFn: async () => {
			const res = await fetch("/api/pipeline/status");
			if (!res.ok) throw new Error("Failed to fetch status");
			return res.json();
		},
		refetchInterval: (query) => {
			const data = query.state.data;
			return data?.status === "running" ? 2000 : false;
		},
	});

	const runMutation = useMutation({
		mutationFn: async () => {
			const res = await fetch("/api/pipeline/run", { method: "POST" });
			if (res.status === 409) throw new Error("Pipeline is already running");
			if (!res.ok) throw new Error("Failed to start pipeline");
			return res.json();
		},
		onSuccess: () => {
			queryClient.invalidateQueries({ queryKey: ["pipeline-status"] });
		},
		onSettled: () => {
			// When the mutation settles, start polling via the query
			queryClient.invalidateQueries({ queryKey: ["pipeline-status"] });
		},
	});

	const isRunning = status?.status === "running";
	const isCompleted = status?.status === "completed";
	const isFailed = status?.status === "failed";

	const handleRun = () => {
		setShowLog(false);
		runMutation.mutate();
	};

	const handleDone = () => {
		// Invalidate dashboard and all data queries when pipeline completes
		queryClient.invalidateQueries({ queryKey: ["dashboard"] });
		queryClient.invalidateQueries({ queryKey: ["journal"] });
		queryClient.invalidateQueries({ queryKey: ["blog"] });
		queryClient.invalidateQueries({ queryKey: ["reading"] });
		queryClient.invalidateQueries({ queryKey: ["seeds"] });
	};

	// Auto-invalidate when transitioning to completed/failed
	if ((isCompleted || isFailed) && runMutation.isSuccess) {
		handleDone();
		runMutation.reset();
	}

	return (
		<div className="space-y-2">
			<div className="flex items-center gap-3">
				<button
					type="button"
					onClick={handleRun}
					disabled={isRunning || runMutation.isPending}
					className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
				>
					{isRunning ? (
						<span className="flex items-center gap-2">
							<span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-white border-t-transparent" />
							Running...
						</span>
					) : (
						"Run Pipeline"
					)}
				</button>

				{isCompleted && (
					<span className="text-sm text-green-600">
						Completed{" "}
						{status?.completedAt ? `at ${new Date(status.completedAt).toLocaleTimeString()}` : ""}
					</span>
				)}

				{isFailed && (
					<span className="text-sm text-red-600">
						Failed{status?.error ? `: ${status.error}` : ""}
					</span>
				)}

				{(isCompleted || isFailed) && status?.log && (
					<button
						type="button"
						onClick={() => setShowLog(!showLog)}
						className="text-sm text-zinc-500 underline hover:text-zinc-700"
					>
						{showLog ? "Hide log" : "View log"}
					</button>
				)}

				{runMutation.error && (
					<span className="text-sm text-red-600">{runMutation.error.message}</span>
				)}
			</div>

			{showLog && status?.log && (
				<pre className="max-h-60 overflow-auto rounded-lg bg-zinc-100 p-3 text-xs text-zinc-700 dark:bg-zinc-900 dark:text-zinc-300">
					{status.log}
				</pre>
			)}
		</div>
	);
}
