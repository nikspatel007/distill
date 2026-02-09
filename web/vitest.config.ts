import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
	plugins: [react(), tailwindcss()],
	resolve: {
		alias: {
			"@shared": new URL("./shared", import.meta.url).pathname,
			"@": new URL("./src", import.meta.url).pathname,
			"@monaco-editor/react": new URL("./src/__tests__/mocks/monaco.tsx", import.meta.url).pathname,
		},
	},
	test: {
		environment: "jsdom",
		globals: true,
		setupFiles: ["./src/__tests__/setup.ts"],
		include: ["src/**/*.test.{ts,tsx}"],
	},
});
