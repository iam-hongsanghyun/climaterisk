import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Backend port mirrors CLIMATERISK_BACKEND_PORT (default 8099). The dev server
// proxies /api so the frontend can use same-origin relative URLs.
const BACKEND_PORT = process.env.CLIMATERISK_BACKEND_PORT ?? "8099";
const FRONTEND_PORT = Number(process.env.CLIMATERISK_FRONTEND_PORT ?? "5174");

export default defineConfig({
  plugins: [react()],
  server: {
    port: FRONTEND_PORT,
    proxy: {
      "/api": {
        target: `http://127.0.0.1:${BACKEND_PORT}`,
        changeOrigin: true,
      },
    },
  },
});
