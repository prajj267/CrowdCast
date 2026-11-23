/// <reference types="vitest/config" />
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
  // Component and data-preparation tests (doc 17 §2.7): jsdom, files next to the code.
  test: {
    environment: "jsdom",
    include: ["src/**/*.test.{ts,tsx}"],
    setupFiles: ["./src/test/setup.ts"],
    // tokens.css is read as text by the contrast test (otherwise Vitest stubs CSS as "").
    css: { include: [/tokens\.css/] },
  },
});
