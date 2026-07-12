/**
 * Tiny RUM (Real-User Monitoring) client — front-v2 port of legacy js/clog.js (F-74).
 *
 * Buffers events and POSTs them in batches to /api/client-logs, where the backend
 * logs each one as structured JSON for promtail → Loki → Grafana.
 *
 * Auto-captures: page load, window.onerror, unhandledrejection, clicks on any
 * [data-clog] element, and a beacon flush on tab hide / pagehide.
 *
 * Public API on window.clog: event/info/warn/error/setContext/flushNow.
 */

type Attrs = Record<string, unknown>;
type Level = "info" | "warn" | "error";

interface ClogApi {
  event: (name: string, attrs?: Attrs) => void;
  info: (name: string, attrs?: Attrs) => void;
  warn: (name: string, attrs?: Attrs) => void;
  error: (name: string, attrs?: Attrs) => void;
  setContext: (kv: Attrs) => void;
  flushNow: () => void;
}

declare global {
  interface Window {
    clog?: ClogApi;
  }
}

const ENDPOINT = "/api/client-logs";
const FLUSH_INTERVAL_MS = 2500;
const MAX_BATCH = 30;
const MAX_QUEUE = 200;
const BUILD_TAG = "front-v2";

let initialized = false;

export function initClog(): ClogApi {
  if (window.clog) return window.clog;

  const sessionId =
    "sess-" + Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 8);

  const state = {
    queue: [] as Record<string, unknown>[],
    context: {
      session_id: sessionId,
      build: BUILD_TAG,
      page: location.pathname,
    } as Attrs,
    flushing: false,
    timer: null as ReturnType<typeof setTimeout> | null,
  };

  function nowIso(): string | null {
    try {
      return new Date().toISOString();
    } catch {
      return null;
    }
  }

  function enqueue(level: Level, name: string, attrs?: Attrs, extras?: Attrs) {
    if (state.queue.length >= MAX_QUEUE) state.queue.shift();
    const evt: Record<string, unknown> = Object.assign(
      { level, event: String(name || "event"), ts: nowIso(), url: location.href },
      state.context,
      extras || {},
    );
    if (attrs && typeof attrs === "object") evt.attrs = attrs;
    state.queue.push(evt);
    scheduleFlush();
  }

  function scheduleFlush() {
    if (state.timer != null) return;
    state.timer = setTimeout(() => flush(false), FLUSH_INTERVAL_MS);
  }

  function flush(useBeacon: boolean) {
    if (state.timer != null) {
      clearTimeout(state.timer);
      state.timer = null;
    }
    if (state.flushing || state.queue.length === 0) return;

    const batch = state.queue.splice(0, MAX_BATCH);
    const body = JSON.stringify({ events: batch });

    if (useBeacon && navigator.sendBeacon) {
      try {
        const blob = new Blob([body], { type: "application/json" });
        navigator.sendBeacon(ENDPOINT, blob);
        return;
      } catch {
        /* fall through to fetch */
      }
    }

    state.flushing = true;
    fetch(ENDPOINT, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body,
      keepalive: true,
    })
      .catch(() => {
        const merged = batch.concat(state.queue);
        state.queue = merged.slice(-MAX_QUEUE);
      })
      .finally(() => {
        state.flushing = false;
        if (state.queue.length > 0) scheduleFlush();
      });
  }

  function safeStringify(v: unknown): string | null {
    if (v == null) return null;
    try {
      if (typeof v === "string") return v;
      return JSON.stringify(v);
    } catch {
      return String(v);
    }
  }

  const clog: ClogApi = {
    event: (name, attrs) => enqueue("info", name, attrs),
    info: (name, attrs) => enqueue("info", name, attrs),
    warn: (name, attrs) => enqueue("warn", name, attrs),
    error: (name, attrs) => enqueue("error", name, attrs),
    setContext: (kv) => {
      if (kv && typeof kv === "object") Object.assign(state.context, kv);
    },
    flushNow: () => flush(false),
  };

  // Auto-capture: errors.
  window.addEventListener("error", (e) => {
    enqueue("error", "window_error", undefined, {
      message: e.message,
      error: {
        message: e.message,
        filename: e.filename,
        lineno: e.lineno,
        colno: e.colno,
        stack: e.error && e.error.stack ? String(e.error.stack) : null,
      },
    });
  });

  window.addEventListener("unhandledrejection", (e) => {
    let msg = "";
    let stack: string | null = null;
    try {
      const r = (e as PromiseRejectionEvent).reason;
      if (r && typeof r === "object") {
        msg = r.message || safeStringify(r) || "";
        stack = r.stack ? String(r.stack) : null;
      } else {
        msg = safeStringify(r) || "";
      }
    } catch {
      msg = "unknown rejection";
    }
    enqueue("error", "unhandled_rejection", undefined, {
      message: msg,
      error: { message: msg, stack },
    });
  });

  // Auto-capture: clicks on [data-clog].
  document.addEventListener(
    "click",
    (e) => {
      const target = e.target as Element | null;
      const tag = target && target.closest ? target.closest("[data-clog]") : null;
      if (tag) {
        enqueue("info", "click", undefined, {
          tag: tag.getAttribute("data-clog"),
          element: (tag.tagName || "").toLowerCase(),
          disabled: (tag as HTMLButtonElement).disabled === true,
          id: tag.id || null,
        });
      }
    },
    true,
  );

  // Flush on tab hide / unload (beacon survives teardown).
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") flush(true);
  });
  window.addEventListener("pagehide", () => flush(true));

  // First-load event so we know the page came up.
  enqueue("info", "page_loaded", undefined, {
    user_agent: navigator.userAgent,
    viewport: window.innerWidth + "x" + window.innerHeight,
    is_touch: "ontouchstart" in window,
  });

  window.clog = clog;
  initialized = true;
  return clog;
}

export function isClogReady(): boolean {
  return initialized;
}
