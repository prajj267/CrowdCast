import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// Dev server proxies /api to the FastAPI backend (uvicorn on 127.0.0.1:8000, CLAUDE.md §10).
// 127.0.0.1, not localhost: localhost tries IPv6 first on this machine.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://127.0.0.1:8000", changeOrigin: true } },
  },
});
