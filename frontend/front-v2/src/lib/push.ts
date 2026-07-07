/**
 * Web Push subscription flow (FE17 · F-73) — front-v2 port of the legacy
 * enablePushNotifications() in js/app.js.
 *
 * Critical ordering (#593): Notification.requestPermission() MUST fire
 * synchronously inside the click gesture, before any await, or mobile browsers
 * silently suppress the prompt. enablePush() therefore takes the permission
 * promise as its first synchronous step.
 *
 * Each step pushes a diagnostic line so a failure is visible on screen instead
 * of needing a remote debugging round.
 */

import { apiFetch } from "./api";
import { getAccessToken } from "./auth";

export interface PushStep {
  step: string;
  ok: boolean | null; // true=ok, false=fail, null=pending
  detail?: string;
}

export type PushProgress = (steps: PushStep[]) => void;

const SW_URL = "/v2/sw.js";
const SW_SCOPE = "/v2/";
const ICON = "/v2/icon-192.png";

function urlBase64ToUint8Array(base64String: string): Uint8Array<ArrayBuffer> {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const raw = atob(base64);
  // Back the array with a concrete ArrayBuffer so the type is Uint8Array<ArrayBuffer>
  // (satisfies BufferSource for applicationServerKey under TS 5.5+ typed-array generics).
  const buf = new ArrayBuffer(raw.length);
  const out = new Uint8Array(buf);
  for (let i = 0; i < raw.length; i++) out[i] = raw.charCodeAt(i);
  return out;
}

function registerSW(): Promise<ServiceWorkerRegistration | null> {
  if (!("serviceWorker" in navigator)) return Promise.resolve(null);
  return navigator.serviceWorker.register(SW_URL, { scope: SW_SCOPE }).catch(() => null);
}

/** Read-only inspection — never requests permission or subscribes. */
export async function pushDiagnostics(): Promise<PushStep[]> {
  const steps: PushStep[] = [];
  const sw = "serviceWorker" in navigator;
  const pm = "PushManager" in window;
  const nt = "Notification" in window;
  steps.push({ step: "Wsparcie przeglądarki", ok: sw && pm && nt, detail: `SW=${sw} Push=${pm} Notif=${nt}` });
  steps.push({ step: "Bezpieczny kontekst (HTTPS)", ok: window.isSecureContext, detail: location.origin });
  steps.push({ step: "Zalogowany", ok: !!getAccessToken() });
  if (nt) {
    steps.push({
      step: "Zgoda przeglądarki",
      ok: Notification.permission === "granted",
      detail: Notification.permission + (Notification.permission === "denied" ? " — odblokuj w 🔒 obok adresu" : ""),
    });
  }
  const diag = await apiFetch<Record<string, unknown>>("/push/diagnostics").catch(() => null);
  if (diag) {
    steps.push({
      step: "Serwer gotowy",
      ok: !!diag.configured && !!diag.pywebpush_installed && !!diag.private_key_loadable,
      detail: `configured=${diag.configured}, pywebpush=${diag.pywebpush_installed}, klucz_ok=${diag.private_key_loadable}`,
    });
  } else {
    steps.push({ step: "Serwer gotowy", ok: false, detail: "/api/push/diagnostics nieosiągalny" });
  }
  if (sw) {
    try {
      const reg = await navigator.serviceWorker.getRegistration(SW_SCOPE);
      const ex = reg ? await reg.pushManager.getSubscription() : null;
      steps.push({ step: "Istniejąca subskrypcja", ok: !!ex, detail: ex ? ex.endpoint.slice(0, 40) + "…" : "brak (kliknij „Włącz”)" });
    } catch (e) {
      steps.push({ step: "Istniejąca subskrypcja", ok: false, detail: String((e as Error)?.message || e) });
    }
  }
  return steps;
}

/**
 * Enable push on this device. Returns the final diagnostic trail.
 * @param onProgress optional callback fired after every step so a UI can render live.
 */
export async function enablePush(onProgress?: PushProgress): Promise<PushStep[]> {
  const steps: PushStep[] = [];
  const push = (step: string, ok: boolean | null, detail?: string) => {
    steps.push({ step, ok, detail });
    onProgress?.([...steps]);
  };

  if (!("serviceWorker" in navigator) || !("PushManager" in window) || !("Notification" in window)) {
    push("Wsparcie przeglądarki", false, "brak serviceWorker/PushManager/Notification");
    return steps;
  }
  push("Wsparcie przeglądarki", true);

  if (!getAccessToken()) {
    push("Zalogowany", false, "brak tokenu — zaloguj się i spróbuj ponownie");
    return steps;
  }
  push("Zalogowany", true);

  // CRITICAL: requestPermission() synchronously, in-gesture, before any await.
  let permPromise: Promise<NotificationPermission>;
  if (Notification.permission === "granted") {
    permPromise = Promise.resolve("granted");
    push("Zgoda przeglądarki", true, "już przyznana");
  } else if (Notification.permission === "denied") {
    push("Zgoda przeglądarki", false, "ZABLOKOWANA — odblokuj w 🔒 obok adresu, odśwież");
    return steps;
  } else {
    permPromise = Notification.requestPermission();
  }

  try {
    const perm = await permPromise;
    if (perm !== "granted") {
      push("Zgoda przeglądarki", false, "odpowiedź: " + perm);
      return steps;
    }
    if (Notification.permission === "granted" && steps[steps.length - 1].step !== "Zgoda przeglądarki") {
      push("Zgoda przeglądarki", true, "przyznana");
    }

    const diag = await apiFetch<Record<string, unknown>>("/push/diagnostics").catch(() => null);
    if (diag) {
      push(
        "Serwer gotowy",
        !!diag.configured && !!diag.pywebpush_installed && !!diag.private_key_loadable,
        `configured=${diag.configured}, pywebpush=${diag.pywebpush_installed}, klucz_ok=${diag.private_key_loadable}`,
      );
    }

    const vapid = await apiFetch<{ publicKey?: string }>("/push/vapid-public-key").catch(() => null);
    if (!vapid || !vapid.publicKey) {
      push("Klucz VAPID", false, "serwer nie zwrócił klucza");
      return steps;
    }
    push("Klucz VAPID", true, vapid.publicKey.slice(0, 12) + "…");

    const reg = await registerSW();
    if (!reg) {
      push("Service worker", false, "rejestracja nieudana");
      return steps;
    }
    await navigator.serviceWorker.ready;
    push("Service worker", true, "scope " + reg.scope);

    // Drop any stale subscription (a different VAPID key makes subscribe() throw).
    const existing = await reg.pushManager.getSubscription();
    if (existing) {
      try {
        await existing.unsubscribe();
      } catch {
        /* ignore */
      }
    }

    let sub: PushSubscription;
    try {
      sub = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapid.publicKey),
      });
    } catch (e) {
      const err = e as Error;
      push("Subskrypcja push", false, (err?.name ? err.name + ": " : "") + (err?.message || String(e)));
      return steps;
    }
    push("Subskrypcja push", true, sub.endpoint.slice(0, 40) + "…");

    const json = sub.toJSON();
    try {
      await apiFetch("/users/push-subscription", {
        method: "POST",
        body: { endpoint: json.endpoint, keys: json.keys },
      });
    } catch (e) {
      const err = e as Error & { status?: number };
      push("Zapis na serwer", false, (err?.status ? "HTTP " + err.status + ": " : "") + (err?.message || String(e)));
      return steps;
    }
    push("Zapis na serwer", true, "zapisano — urządzenie widoczne w admin → Push");

    // Immediate local proof.
    try {
      await reg.showNotification("AI-GM", {
        body: "🔔 Powiadomienia włączone — będziesz dostawać info o swojej turze.",
        icon: ICON,
      });
    } catch {
      /* ignore */
    }
    return steps;
  } catch (e) {
    push("Błąd", false, String((e as Error)?.message || e));
    return steps;
  }
}

export function pushSupported(): boolean {
  return "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
}
