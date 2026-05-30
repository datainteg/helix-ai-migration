import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

// Vite config â€” Helix public website (separate from authenticated frontend app).
// Dev port 5173 (Vite default); build emits to website/dist for static hosting.
// Dev-only: the index.html ships a strict prod CSP (upgrade-insecure-requests +
// script-src 'self') that breaks the Vite dev server (forces https on http dev
// assets and blocks HMR's inline scripts/websocket). Strip the CSP <meta> when
// SERVING; the production `vite build` keeps it untouched.
const stripCspInDev = {
  name: "helix-strip-csp-dev",
  apply: "serve" as const,
  transformIndexHtml(html: string) {
    return html.replace(/\s*<meta http-equiv="Content-Security-Policy"[\s\S]*?\/>/i, "");
  },
};

export default defineConfig({
  plugins: [react(), stripCspInDev],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  // `allowedHosts: true` lets the dev server answer requests for any Host
  // header (e.g. when reached by docker service name in a dev container).
  // Dev-server only — the production build emits static files, so no impact.
  server: { port: 5173, host: true, allowedHosts: true },
  build: { outDir: "dist", sourcemap: false },
});
