import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    target: "es2022",
    outDir: "dist",
    sourcemap: true,
    reportCompressedSize: true,
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1:8765",
      "/nextgen": "http://127.0.0.1:8765",
      "/health": "http://127.0.0.1:8765",
      "/ready": "http://127.0.0.1:8765",
    },
  },
});
