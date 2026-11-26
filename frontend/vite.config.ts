import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// In dev, /api is proxied to FastAPI. In production Firebase Hosting rewrites /api/** to Cloud Run,
// so the SPA and the API share one origin (no CORS, no API URL baked into the bundle).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { port: 5173, proxy: { "/api": "http://localhost:8000" } },
  build: { chunkSizeWarningLimit: 2500 },
});
