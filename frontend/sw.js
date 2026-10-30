// Service worker: makes the app installable and lets it open offline,
// showing the data that was loaded last time.
const VERSION = "tm-v12";
const SHELL = ["/", "/index.html", "/style.css", "/i18n.js", "/app.js", "/icon.svg", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin) return;
  if (url.pathname.startsWith("/ical/") || url.pathname.includes("/file")) return;

  if (url.pathname.startsWith("/api/")) {
    // Network first, fall back to the last copy so the app still opens without signal
    e.respondWith(
      fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => caches.match(req).then((hit) => hit || new Response(
        JSON.stringify({ detail: "offline" }), { status: 503, headers: { "Content-Type": "application/json" } })))
    );
    return;
  }
  // App files: network first as well, so updates show up at once; cache when offline
  e.respondWith(
    fetch(req).then((res) => {
      if (res.ok) { const copy = res.clone(); caches.open(VERSION).then((c) => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req).then((hit) => hit || caches.match("/index.html")))
  );
});
