import dayjs from "dayjs";

interface Props {
	date: string;
	className?: string;
}

export function DateBadge({ date, className = "" }: Props) {
	const d = dayjs(date);
	const relative = d.isValid() ? d.format("MMM D") : date;
	return (
		<span
			className={`inline-flex items-center rounded-full bg-zinc-100 px-2.5 py-0.5 text-xs font-medium text-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 ${className}`}
		>
			{relative}
		</span>
	);
}
