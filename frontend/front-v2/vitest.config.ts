import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Testy jednostkowe/komponentowe front-v2 (ŻAR). Osobne od `vite build` — build
// nadal typechecky przez `tsc --noEmit` (pliki *.test.* wykluczone w tsconfig.json).
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
