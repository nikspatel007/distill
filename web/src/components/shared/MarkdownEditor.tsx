import Editor, { type OnMount } from "@monaco-editor/react";
import { useCallback, useRef } from "react";

interface MarkdownEditorProps {
	value: string;
	onChange: (value: string) => void;
	onSave?: () => void;
}

export function MarkdownEditor({ value, onChange, onSave }: MarkdownEditorProps) {
	const editorRef = useRef<Parameters<OnMount>[0] | null>(null);

	const handleMount: OnMount = useCallback(
		(editor, monaco) => {
			editorRef.current = editor;

			// Register Cmd/Ctrl+S keybinding
			editor.addAction({
				id: "save-markdown",
				label: "Save",
				keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS],
				run: () => {
					onSave?.();
				},
			});
		},
		[onSave],
	);

	return (
		<div className="overflow-hidden rounded-lg border border-zinc-200 dark:border-zinc-700">
			<Editor
				height="60vh"
				language="markdown"
				theme="vs-dark"
				value={value}
				onChange={(v) => onChange(v ?? "")}
				onMount={handleMount}
				options={{
					wordWrap: "on",
					minimap: { enabled: false },
					automaticLayout: true,
					fontSize: 14,
					lineNumbers: "on",
					scrollBeyondLastLine: false,
					padding: { top: 12 },
				}}
			/>
		</div>
	);
}
