interface EditToggleProps {
	isEditing: boolean;
	onToggle: () => void;
	onSave: () => void;
	isSaving: boolean;
	isDirty: boolean;
	saveSuccess: boolean;
}

export function EditToggle({
	isEditing,
	onToggle,
	onSave,
	isSaving,
	isDirty,
	saveSuccess,
}: EditToggleProps) {
	return (
		<div className="flex items-center gap-2">
			<button
				type="button"
				onClick={onToggle}
				className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors ${
					isEditing
						? "bg-zinc-200 text-zinc-800 dark:bg-zinc-700 dark:text-zinc-200"
						: "bg-zinc-100 text-zinc-600 hover:bg-zinc-200 dark:bg-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-700"
				}`}
			>
				{isEditing ? "Preview" : "Edit"}
			</button>
			{isEditing && (
				<>
					<button
						type="button"
						onClick={onSave}
						disabled={isSaving || !isDirty}
						className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
					>
						{isSaving ? "Saving..." : "Save"}
					</button>
					{saveSuccess && <span className="text-sm text-green-600 dark:text-green-400">Saved</span>}
				</>
			)}
		</div>
	);
}
