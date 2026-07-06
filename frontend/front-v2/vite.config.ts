import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Served under /v2/ on the DEV nginx (alongside the legacy /front SPA at /).
// base + router basename must both be /v2 so assets and routes resolve there.
export default defineConfig({
  base: "/v2/",
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
