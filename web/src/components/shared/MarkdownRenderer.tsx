import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Props {
	content: string;
}

export function MarkdownRenderer({ content }: Props) {
	// Convert Obsidian wiki links [[target|label]] to markdown links
	const processed = content.replace(
		/\[\[([^\]|]+)(?:\|([^\]]+))?\]\]/g,
		(_, target, label) => `[${label ?? target}](#${target})`,
	);

	return (
		<div className="prose prose-zinc dark:prose-invert max-w-none">
			<ReactMarkdown remarkPlugins={[remarkGfm]}>{processed}</ReactMarkdown>
		</div>
	);
}
