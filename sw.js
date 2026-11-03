// Ballot Buddy service worker: the app opens from the home screen and still works in a dead zone at the polls.
// Network first (the guide changes during the day), falling back to the last copy saved on the phone.
// The account API is never cached.
const CACHE = "ballot-buddy-v1";
self.addEventListener("install", e => self.skipWaiting());
self.addEventListener("activate", e => e.waitUntil((async () => {
  for (const k of await caches.keys()) if (k !== CACHE) await caches.delete(k);
  await self.clients.claim();
})()));
self.addEventListener("fetch", e => {
  const u = new URL(e.request.url);
  if (e.request.method !== "GET" || u.pathname.includes("/api/")) return;
  if (u.origin !== location.origin && !/\/ballot\/photos\//.test(u.pathname)) return;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    try {
      const r = await fetch(e.request);
      if (r.ok || r.type === "opaque") c.put(e.request, r.clone());
      return r;
    } catch (err) {
      const hit = await c.match(e.request, {ignoreSearch: u.pathname.endsWith(".html") || u.pathname.endsWith("/")});
      if (hit) return hit;
      throw err;
    }
  })());
});
