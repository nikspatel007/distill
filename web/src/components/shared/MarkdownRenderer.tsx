import mermaid from "mermaid";
import { useEffect, useId, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

mermaid.initialize({ startOnLoad: false, theme: "neutral" });

function MermaidBlock({ code }: { code: string }) {
	const id = useId().replace(/:/g, "-");
	const ref = useRef<HTMLDivElement>(null);
	const [svg, setSvg] = useState<string | null>(null);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		let cancelled = false;
		mermaid
			.render(`mermaid${id}`, code.trim())
			.then(({ svg: rendered }) => {
				if (!cancelled) setSvg(rendered);
			})
			.catch((err) => {
				if (!cancelled) setError(String(err));
			});
		return () => {
			cancelled = true;
		};
	}, [code, id]);

	if (error) {
		return (
			<pre className="overflow-x-auto rounded bg-red-50 p-3 text-xs text-red-600 dark:bg-red-950 dark:text-red-400">
				{code}
			</pre>
		);
	}

	if (!svg)
		return <div className="animate-pulse py-4 text-sm text-zinc-400">Rendering diagram...</div>;

	return (
		// biome-ignore lint/security/noDangerouslySetInnerHtml: mermaid produces trusted SVG
		<div ref={ref} className="my-4 flex justify-center" dangerouslySetInnerHTML={{ __html: svg }} />
	);
}

interface Props {
	content: string;
	className?: string;
}

export function MarkdownRenderer({ content, className }: Props) {
	// Convert Obsidian wiki links [[target|label]] to markdown links
	const processed = content.replace(
		/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
		(_, target, label) => `[${label ?? target}](#${target})`,
	);

	return (
		<div className={className ?? "prose prose-zinc dark:prose-invert max-w-none"}>
			<ReactMarkdown
				remarkPlugins={[remarkGfm]}
				components={{
					code({ className: codeClass, children, ...rest }) {
						const match = /language-mermaid/.exec(codeClass ?? "");
						if (match) {
							return <MermaidBlock code={String(children).replace(/\n$/, "")} />;
						}
						return (
							<code className={codeClass} {...rest}>
								{children}
							</code>
						);
					},
				}}
			>
				{processed}
			</ReactMarkdown>
		</div>
	);
}
