interface Props {
	tag: string;
}

export function TagBadge({ tag }: Props) {
	return (
		<span className="inline-flex items-center rounded-full bg-indigo-50 px-2 py-0.5 text-xs font-medium text-indigo-700 dark:bg-indigo-950 dark:text-indigo-300">
			{tag}
		</span>
	);
}
