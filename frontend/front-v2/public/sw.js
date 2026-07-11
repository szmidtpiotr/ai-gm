/* AI-GM front-v2 service worker (FE17 · F-73).
 *
 * Two jobs:
 *   1) PWA offline shell — precache the app shell, runtime-cache built assets so
 *      /graj/ opens (and re-opens) without the network; navigations fall back to
 *      the cached index shell when offline.
 *   2) Web Push — receive push events + handle notification clicks (ported from
 *      the legacy /sw.js).
 *
 * Runtime-cache strategy (rather than a hashed precache manifest) keeps this SW
 * dependency-free: Vite fingerprints asset names at build time, so we cache them
 * lazily on first fetch instead of listing them here.
 */

const VERSION = 'v2-fe17-1';
const SHELL_CACHE = 'aigm-v2-shell-' + VERSION;
const ASSET_CACHE = 'aigm-v2-assets-' + VERSION;
const BASE = '/graj/';

// Stable, always-present shell files (public/ assets — not fingerprinted).
const SHELL_ASSETS = [
  BASE,
  BASE + 'index.html',
  BASE + 'manifest.webmanifest',
  BASE + 'icon-192.png',
  BASE + 'icon-512.png',
  BASE + 'apple-touch-icon.png',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_ASSETS).catch(() => {}))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter(
              (k) =>
                (k.startsWith('aigm-v2-shell-') && k !== SHELL_CACHE) ||
                (k.startsWith('aigm-v2-assets-') && k !== ASSET_CACHE)
            )
            .map((k) => caches.delete(k))
        )
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;

  const url = new URL(req.url);
  // Never touch cross-origin (fonts CDN etc.) or the API — always live network.
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/api/')) return;
  // Only manage our own /graj/ subtree.
  if (!url.pathname.startsWith(BASE)) return;

  // Navigations → network-first, fall back to cached shell (offline SPA boot).
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() =>
        caches.match(BASE + 'index.html').then((r) => r || caches.match(BASE))
      )
    );
    return;
  }

  // Static assets (hashed JS/CSS/fonts/images) → stale-while-revalidate.
  event.respondWith(
    caches.open(ASSET_CACHE).then((cache) =>
      cache.match(req).then((cached) => {
        const network = fetch(req)
          .then((res) => {
            if (res && res.ok && res.type === 'basic') {
              cache.put(req, res.clone());
            }
            return res;
          })
          .catch(() => cached);
        return cached || network;
      })
    )
  );
});

// ── Web Push (ported from legacy /sw.js) ────────────────────────────────────
self.addEventListener('push', (event) => {
  if (!event.data) return;
  let data;
  try {
    data = event.data.json();
  } catch (e) {
    data = { title: 'AI-GM', body: event.data.text(), url: BASE };
  }
  const options = {
    body: data.body || '',
    icon: data.icon || BASE + 'icon-192.png',
    badge: data.badge || BASE + 'icon-192.png',
    data: { url: data.url || BASE },
    requireInteraction: false,
  };
  if (data.image) options.image = data.image;
  if (data.vibrate) options.vibrate = data.vibrate;
  event.waitUntil(self.registration.showNotification(data.title || 'AI-GM', options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const url = (event.notification.data && event.notification.data.url) || BASE;
  event.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clientList) => {
      for (const client of clientList) {
        if (client.url.includes(self.location.origin) && 'focus' in client) {
          client.navigate(url);
          return client.focus();
        }
      }
      if (clients.openWindow) return clients.openWindow(url);
    })
  );
});
