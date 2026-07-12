import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Served under /graj/ on the DEV nginx (alongside the legacy /front SPA at /).
// base + router basename must both be /graj so assets and routes resolve there.
export default defineConfig({
  base: "/graj/",
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    host: true,
  },
});
