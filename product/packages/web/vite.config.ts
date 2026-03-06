import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 6108,
    proxy: {
      "/api": {
        target: "http://localhost:6107",
        changeOrigin: true,
      },
    },
  },
});
