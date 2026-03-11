/**
 * Nexus AI Service Worker
 * Enables PWA install + offline static asset caching.
 * API / WebSocket calls always go to network (never cached).
 */

const CACHE_NAME = 'nexus-v1';
const STATIC_PRECACHE = [
  '/',
  '/static/style.css',
  '/static/app.js',
  '/static/icon-192.png',
];

// ── Install: precache static assets ──
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => cache.addAll(STATIC_PRECACHE))
      .then(() => self.skipWaiting())
  );
});

// ── Activate: delete old caches ──
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
      )
    ).then(() => self.clients.claim())
  );
});

// ── Fetch: network-first for API, cache-first for static ──
self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);

  // Never cache API, WebSocket, or non-GET requests
  if (
    e.request.method !== 'GET' ||
    url.pathname.startsWith('/api/') ||
    url.pathname.startsWith('/ws') ||
    url.protocol === 'ws:' ||
    url.protocol === 'wss:'
  ) {
    e.respondWith(
      fetch(e.request).catch(() =>
        new Response(JSON.stringify({ error: 'offline' }), {
          status: 503,
          headers: { 'Content-Type': 'application/json' },
        })
      )
    );
    return;
  }

  // Static / page: cache-first, update in background
  e.respondWith(
    caches.match(e.request).then(cached => {
      const fetchPromise = fetch(e.request).then(res => {
        if (res.ok) {
          caches.open(CACHE_NAME).then(c => c.put(e.request, res.clone()));
        }
        return res;
      });
      return cached || fetchPromise;
    })
  );
});

// ── Push notifications (Web Push) ──
self.addEventListener('push', (e) => {
  const data = e.data?.json() || {};
  e.waitUntil(
    self.registration.showNotification(data.title || 'Nexus AI', {
      body: data.body || '',
      icon: '/static/icon-192.png',
      badge: '/static/icon-192.png',
      vibrate: [200, 100, 200],
      tag: data.tag || 'nexus',
      renotify: true,
      data: { url: data.url || '/' },
    })
  );
});

self.addEventListener('notificationclick', (e) => {
  e.notification.close();
  e.waitUntil(
    clients.matchAll({ type: 'window' }).then(wins => {
      const target = e.notification.data.url;
      for (const w of wins) {
        if (w.url === target && 'focus' in w) return w.focus();
      }
      return clients.openWindow(target);
    })
  );
});
