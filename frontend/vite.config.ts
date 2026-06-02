import react from "@vitejs/plugin-react";
import path from "node:path";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    // Proxy API calls to the backend in dev so cookies are same-origin.
    proxy: {
      "/api": { target: "http://localhost:8010", changeOrigin: true },
    },
  },
});
