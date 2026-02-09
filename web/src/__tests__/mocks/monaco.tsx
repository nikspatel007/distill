/**
 * Mock for @monaco-editor/react used in vitest/jsdom environment.
 * Renders a textarea that behaves like the editor for testing purposes.
 */
import type { ReactNode } from "react";

interface MockEditorProps {
	value?: string;
	onChange?: (value: string | undefined) => void;
	onMount?: (editor: unknown, monaco: unknown) => void;
	height?: string;
	language?: string;
	theme?: string;
	options?: Record<string, unknown>;
}

function MockEditor({ value, onChange }: MockEditorProps): ReactNode {
	return (
		<textarea
			data-testid="monaco-editor"
			value={value}
			onChange={(e) => onChange?.(e.target.value)}
		/>
	);
}

export default MockEditor;
