import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// During `vite dev` the API is proxied to the FastAPI process on :8080.
// In production the same FastAPI process serves the built assets.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8080",
    },
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
