import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "react-router-dom";

// Fonty ŻAR — bundlowane (offline-safe), nie Google CDN.
import "@fontsource/literata/400.css";
import "@fontsource/literata/400-italic.css";
import "@fontsource/literata/500.css";
import "@fontsource/literata/600.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/jetbrains-mono/500.css";

// Ikony Phosphor (@phosphor-icons/react) — jeden zestaw w całym UI (sekcja 6),
// importowane jako komponenty per-użycie.
import "./index.css";
import { queryClient } from "./lib/queryClient";
import { router } from "./routes/router";
import { ToastProvider } from "./components/ui/toast";
import { initClog } from "./lib/clog";
import { registerServiceWorker } from "./lib/pwa";

// Viewport height fix: iOS Safari nie aktualizuje dvh po schowaniu klawiatury —
// --app-h śledzi visualViewport.height i łata lukę pod contentem (#1278-ish).
function _syncVH() {
  const h = window.visualViewport?.height ?? window.innerHeight;
  document.documentElement.style.setProperty("--app-h", `${h}px`);
}
_syncVH();
window.visualViewport?.addEventListener("resize", _syncVH);
window.addEventListener("resize", _syncVH);

// FE17 (#1266) — RUM (F-74): buforuje zdarzenia → POST /api/client-logs.
// Init przed renderem, żeby złapać wczesne błędy i page_loaded.
initClog();
// FE17 (#1266) — PWA (F-73): rejestracja service workera (offline shell + push).
registerServiceWorker();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <RouterProvider router={router} />
      </ToastProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
