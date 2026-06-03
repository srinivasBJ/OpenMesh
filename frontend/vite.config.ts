import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

const apiProxyTarget = process.env.VITE_API_PROXY_TARGET || "http://localhost:8000";
const wsProxyTarget =
  process.env.VITE_WS_PROXY_TARGET ||
  apiProxyTarget.replace(/^http/, "ws").replace(/\/api$/, "");

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "./src") } },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: apiProxyTarget, changeOrigin: true },
      "/ws": { target: wsProxyTarget, ws: true },
    },
  },
});
