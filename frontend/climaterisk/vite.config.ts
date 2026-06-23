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
  build: {
    // Split the heavy viz libs into their own cacheable vendor chunks so no single
    // bundle dominates (keeps the chunk-size warning quiet and first load fast).
    chunkSizeWarningLimit: 1300,
    rollupOptions: {
      output: {
        manualChunks: {
          maplibre: ["maplibre-gl", "@mapbox/mapbox-gl-draw"],
          charts: ["recharts"],
          grid: ["ag-grid-community", "ag-grid-react"],
          leaflet: ["leaflet", "react-leaflet"],
        },
      },
    },
  },
});
