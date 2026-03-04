import { useEffect, useState } from "react";
import { useSearch } from "@tanstack/react-router";

export default function Share() {
	const search = useSearch({ strict: false }) as Record<string, string | undefined>;
	const sharedUrl = search.url ?? extractUrl(search.text) ?? "";
	const [status, setStatus] = useState<"saving" | "saved" | "error">("saving");

	useEffect(() => {
		if (!sharedUrl) {
			setStatus("error");
			return;
		}

		fetch(`/api/shares?url=${encodeURIComponent(sharedUrl)}`)
			.then((res) => {
				if (!res.ok) throw new Error("Failed");
				setStatus("saved");
				// Auto-close after a brief delay (PWA share target)
				setTimeout(() => window.close(), 1500);
			})
			.catch(() => setStatus("error"));
	}, [sharedUrl]);

	return (
		<div className="flex min-h-screen items-center justify-center bg-zinc-950 p-4">
			<div className="text-center space-y-3">
				{status === "saving" && (
					<>
						<div className="text-4xl">&#x2697;</div>
						<p className="text-zinc-400">Saving...</p>
					</>
				)}
				{status === "saved" && (
					<>
						<div className="text-4xl">&#10003;</div>
						<p className="text-zinc-300 font-medium">Saved to Distill</p>
						<p className="text-sm text-zinc-500 break-all max-w-sm">{sharedUrl}</p>
					</>
				)}
				{status === "error" && (
					<>
						<div className="text-4xl">&#x2717;</div>
						<p className="text-zinc-300 font-medium">
							{sharedUrl ? "Failed to save" : "No URL received"}
						</p>
						{sharedUrl && (
							<p className="text-sm text-zinc-500 break-all max-w-sm">{sharedUrl}</p>
						)}
						<a href="/shares" className="text-sm text-indigo-400 hover:underline">
							Open Shares
						</a>
					</>
				)}
			</div>
		</div>
	);
}

/** Extract a URL from freeform text (some apps share "Title - https://...") */
function extractUrl(text?: string): string | undefined {
	if (!text) return undefined;
	const match = text.match(/https?:\/\/[^\s]+/);
	return match?.[0];
}
