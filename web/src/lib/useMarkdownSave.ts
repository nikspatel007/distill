import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";

interface UseMarkdownSaveOptions {
	endpoint: string;
	queryKey: readonly unknown[];
	originalContent: string;
}

export function useMarkdownSave({ endpoint, queryKey, originalContent }: UseMarkdownSaveOptions) {
	const queryClient = useQueryClient();
	const [editedContent, setEditedContent] = useState(originalContent);
	const [saveSuccess, setSaveSuccess] = useState(false);
	const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	// Resync when original content changes (e.g. after refetch)
	useEffect(() => {
		setEditedContent(originalContent);
	}, [originalContent]);

	// Clear success flash after 2s
	useEffect(() => {
		if (!saveSuccess) return;
		timerRef.current = setTimeout(() => setSaveSuccess(false), 2000);
		return () => {
			if (timerRef.current) clearTimeout(timerRef.current);
		};
	}, [saveSuccess]);

	const mutation = useMutation({
		mutationFn: async (content: string) => {
			const res = await fetch(endpoint, {
				method: "PUT",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({ content }),
			});
			if (!res.ok) {
				const data = await res.json().catch(() => ({ error: "Save failed" }));
				throw new Error(data.error ?? "Save failed");
			}
			return res.json();
		},
		onSuccess: () => {
			setSaveSuccess(true);
			queryClient.invalidateQueries({ queryKey: [...queryKey] });
		},
	});

	const save = useCallback(() => {
		mutation.mutate(editedContent);
	}, [mutation, editedContent]);

	const isDirty = editedContent !== originalContent;

	return {
		editedContent,
		setEditedContent,
		isDirty,
		save,
		isSaving: mutation.isPending,
		saveError: mutation.error,
		saveSuccess,
	};
}
