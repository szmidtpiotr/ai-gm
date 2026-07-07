/**
 * PWA service-worker registration (FE17 · F-73).
 *
 * Registers /v2/sw.js at scope /v2/ so it controls the whole front-v2 subtree
 * (offline shell + runtime asset cache + web-push). Called once from main.tsx.
 * Registration is non-blocking and never throws into React render.
 */

const SW_URL = "/v2/sw.js";
const SW_SCOPE = "/v2/";

export function registerServiceWorker(): void {
  if (!("serviceWorker" in navigator)) return;
  // Register after load so it never competes with first paint / hydration.
  window.addEventListener("load", () => {
    navigator.serviceWorker.register(SW_URL, { scope: SW_SCOPE }).catch((err) => {
      // Non-fatal — app still works online without the SW.
      console.warn("[pwa] SW register failed", err);
      window.clog?.warn("sw_register_failed", { message: String(err?.message || err) });
    });
  });
}
