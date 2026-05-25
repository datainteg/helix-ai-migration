import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Vite config — Helix public website (separate from authenticated frontend app).
// Dev port 5173 (Vite default); build emits to website/dist for static hosting.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: { port: 5173, host: true },
  build: { outDir: "dist", sourcemap: false },
});
