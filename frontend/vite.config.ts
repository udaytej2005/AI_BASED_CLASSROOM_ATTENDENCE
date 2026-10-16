/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig, loadEnv } from "vite";

// The browser only ever talks to the frontend origin. Requests to /api are proxied
// server-side to the FastAPI backend, so no backend address is embedded in browser code.
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "");
  const apiTarget = env.API_PROXY_TARGET || "http://127.0.0.1:8000";

  return {
    plugins: [react(), tailwindcss()],
    server: {
      host: "0.0.0.0",
      port: 5173,
      // Allow the sandbox preview host to reach the dev server.
      allowedHosts: true,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: false },
      },
    },
    preview: {
      host: "0.0.0.0",
      port: 4173,
      allowedHosts: true,
      proxy: {
        "/api": { target: apiTarget, changeOrigin: false },
      },
    },
    test: {
      environment: "jsdom",
      setupFiles: ["./tests/setup.ts"],
      include: ["tests/**/*.test.{ts,tsx}"],
      css: false,
    },
  };
});
