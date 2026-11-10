// Shows offline.html when Trials' server is off, instead of the browser's "can't connect" page.
// Only page loads go through here; everything else goes straight to the network. Bump VERSION when offline.html changes.
const VERSION = "trials-offline-3";

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.add(new Request("/offline.html", { cache: "reload" }))));
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((key) => key !== VERSION).map((key) => caches.delete(key))))
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  if (event.request.mode !== "navigate") return;
  event.respondWith(fetch(event.request).catch(() => caches.match("/offline.html", { cacheName: VERSION })));
});
