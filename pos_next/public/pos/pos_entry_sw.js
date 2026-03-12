/**
 * POS entry Service Worker - scope /pos/
 * Caches /pos/ document and app assets so F5 works offline (no white page).
 * Must be served at /pos/sw.js so scope is /pos/.
 */
const CACHE_NAME = "pos-shell-v2";

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.add("/pos/").catch(() => {}))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => k.startsWith("pos-shell-") && k !== CACHE_NAME)
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  const path = url.pathname;

  // Navigation to /pos/*: serve from cache when offline
  if (event.request.mode === "navigate" && path.startsWith("/pos")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          const clone = response.clone();
          caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
          return response;
        })
        .catch(() =>
          caches
            .match(event.request)
            .then((cached) => cached || caches.match("/pos/"))
        )
    );
    return;
  }

  // App assets (JS, CSS, manifest) under /assets/pos_next/pos/: cache and serve when offline
  if (path.startsWith("/assets/pos_next/pos/")) {
    event.respondWith(
      fetch(event.request)
        .then((response) => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((c) => c.put(event.request, clone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
  }
});
