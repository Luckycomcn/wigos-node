import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Django host the dev server proxies /api, /admin and /static to. Override with
// VITE_PROXY_TARGET (e.g. http://backend:8000 inside docker-compose).
const proxyTarget = process.env.VITE_PROXY_TARGET || "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    watch: {
      usePolling: true,
    },
    proxy: {
      "/api": { target: proxyTarget, changeOrigin: true },
      "/admin": { target: proxyTarget, changeOrigin: true },
      "/static": { target: proxyTarget, changeOrigin: true },
    },
  },
});
