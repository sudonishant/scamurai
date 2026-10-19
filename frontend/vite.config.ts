import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The browser only ever calls relative /api URLs; Vite proxies them to FastAPI.
// Same proxy rules apply to the dev server and the production preview server.
const apiProxy = {
  "/api": { target: "http://127.0.0.1:8000", changeOrigin: true },
  "/health": { target: "http://127.0.0.1:8000", changeOrigin: true },
};

export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 5173,
    allowedHosts: true, // accept preview-proxy hosts in sandboxed environments
    proxy: apiProxy,
  },
  preview: {
    host: "0.0.0.0",
    port: 4173,
    allowedHosts: true,
    proxy: apiProxy,
  },
  build: {
    chunkSizeWarningLimit: 900,
  },
});
