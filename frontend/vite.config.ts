import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Semua permintaan /api diteruskan ke backend FastAPI (tidak perlu CORS saat pengembangan).
const target = process.env.VITE_API_PROXY ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { "/api": { target, changeOrigin: true } },
    watch: process.env.CHOKIDAR_USEPOLLING ? { usePolling: true } : undefined,
  },
});
