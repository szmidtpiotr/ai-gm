/**
 * Tiny RUM (Real-User Monitoring) client.
 *
 * Buffers events and POSTs them in batches to /api/client-logs, where the
 * backend logs each one as structured JSON for promtail → Loki → Grafana.
 *
 * Public API:
 *   clog.event(name, attrs)              // info-level event
 *   clog.error(message, attrs)           // error-level
 *   clog.warn(message, attrs)            // warn-level
 *   clog.setContext({user_id, campaign_id, screen, ...})
 *
 * Auto-captures:
 *   - window.onerror, unhandledrejection
 *   - clicks on [data-clog] (or any button if data-clog-auto-clicks)
 *   - flush on visibilitychange (sendBeacon if available)
 */
(function () {
  'use strict';

  const ENDPOINT = '/api/client-logs';
  const FLUSH_INTERVAL_MS = 2500;
  const MAX_BATCH = 30;
  const MAX_QUEUE = 200;

  const sessionId =
    'sess-' +
    Date.now().toString(36) +
    '-' +
    Math.random().toString(36).slice(2, 8);
  const buildTag = 'front-mobile-v1';

  const state = {
    queue: [],
    context: {
      session_id: sessionId,
      build: buildTag,
      page: location.pathname,
    },
    flushing: false,
    timer: null,
  };

  function nowIso() {
    try {
      return new Date().toISOString();
    } catch (_e) {
      return null;
    }
  }

  function enqueue(level, name, attrs, extras) {
    if (state.queue.length >= MAX_QUEUE) {
      // Drop oldest to keep most recent.
      state.queue.shift();
    }
    const evt = Object.assign(
      {
        level: level,
        event: String(name || 'event'),
        ts: nowIso(),
        url: location.href,
      },
      state.context,
      extras || {}
    );
    if (attrs && typeof attrs === 'object') {
      evt.attrs = attrs;
    }
    state.queue.push(evt);
    scheduleFlush();
  }

  function scheduleFlush() {
    if (state.timer != null) return;
    state.timer = setTimeout(flush, FLUSH_INTERVAL_MS);
  }

  function flush(useBeacon) {
    if (state.timer != null) {
      clearTimeout(state.timer);
      state.timer = null;
    }
    if (state.flushing || state.queue.length === 0) return;

    const batch = state.queue.splice(0, MAX_BATCH);
    const body = JSON.stringify({ events: batch });

    if (useBeacon && navigator.sendBeacon) {
      try {
        const blob = new Blob([body], { type: 'application/json' });
        navigator.sendBeacon(ENDPOINT, blob);
        return;
      } catch (_e) {
        // fall through to fetch
      }
    }

    state.flushing = true;
    fetch(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: body,
      keepalive: true,
    })
      .catch(function () {
        // Network glitch — re-queue at front (cap to MAX_QUEUE).
        const merged = batch.concat(state.queue);
        state.queue = merged.slice(-MAX_QUEUE);
      })
      .finally(function () {
        state.flushing = false;
        if (state.queue.length > 0) scheduleFlush();
      });
  }

  function safeStringify(v) {
    if (v == null) return null;
    try {
      if (typeof v === 'string') return v;
      return JSON.stringify(v);
    } catch (_e) {
      return String(v);
    }
  }

  // === Public API ===
  const clog = {
    event: function (name, attrs) {
      enqueue('info', name, attrs);
    },
    info: function (name, attrs) {
      enqueue('info', name, attrs);
    },
    warn: function (name, attrs) {
      enqueue('warn', name, attrs);
    },
    error: function (name, attrs) {
      enqueue('error', name, attrs);
    },
    setContext: function (kv) {
      if (!kv || typeof kv !== 'object') return;
      Object.assign(state.context, kv);
    },
    flushNow: function () {
      flush(false);
    },
    _state: state,
  };

  // === Auto-capture: errors ===
  window.addEventListener('error', function (e) {
    enqueue('error', 'window_error', null, {
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

  window.addEventListener('unhandledrejection', function (e) {
    let msg = '';
    let stack = null;
    try {
      const r = e.reason;
      if (r && typeof r === 'object') {
        msg = r.message || safeStringify(r);
        stack = r.stack ? String(r.stack) : null;
      } else {
        msg = safeStringify(r);
      }
    } catch (_e) {
      msg = 'unknown rejection';
    }
    enqueue('error', 'unhandled_rejection', null, {
      message: msg,
      error: { message: msg, stack: stack },
    });
  });

  // === Auto-capture: clicks on [data-clog] or buttons with data-clog-auto ===
  document.addEventListener(
    'click',
    function (e) {
      const tag = e.target && e.target.closest ? e.target.closest('[data-clog]') : null;
      if (tag) {
        enqueue('info', 'click', null, {
          tag: tag.getAttribute('data-clog'),
          element: (tag.tagName || '').toLowerCase(),
          disabled: !!tag.disabled,
          id: tag.id || null,
        });
      }
    },
    true
  );

  // === Flush on tab hide / unload (use beacon to survive teardown) ===
  document.addEventListener('visibilitychange', function () {
    if (document.visibilityState === 'hidden') {
      flush(true);
    }
  });
  window.addEventListener('pagehide', function () {
    flush(true);
  });

  // First-load event so we know the page came up.
  enqueue('info', 'page_loaded', null, {
    user_agent: navigator.userAgent,
    viewport: window.innerWidth + 'x' + window.innerHeight,
    is_touch: 'ontouchstart' in window,
  });

  window.clog = clog;
})();
