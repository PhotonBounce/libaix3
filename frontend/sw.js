const urlParams = new URLSearchParams(self.location.search);
const VERSION = urlParams.get('v') || 'opsbrief-v1';
const STATIC_CACHE = `opsbrief-shell-${VERSION}`;
const API_CACHE = `opsbrief-api-${VERSION}`;

const STATIC_ASSETS = [
  '/',
  '/index.html',
  '/manifest.json',
  '/admin.html'
];

// Install: cache static shell
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(STATIC_CACHE)
      .then(cache => cache.addAll(STATIC_ASSETS))
      .then(() => self.skipWaiting())
  );
});

// Activate: clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(
        keys.filter(key => key !== STATIC_CACHE && key !== API_CACHE)
            .map(key => caches.delete(key))
      )
    ).then(() => self.clients.claim())
  );
});

// Fetch: static assets cache-first, API network-first with separate cache
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // API requests -> network-first, cache separately
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(
      fetch(request)
        .then(response => {
          // Only cache successful GET requests without auth headers
          if (request.method === 'GET' && !request.headers.has('Authorization') && !request.headers.has('X-Admin-Key') && response.ok) {
            const clone = response.clone();
            caches.open(API_CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        })
        .catch(() => caches.match(request))
    );
    return;
  }

  // Static assets -> cache-first
  if (request.method === 'GET') {
    event.respondWith(
      caches.match(request).then(cached =>
        cached || fetch(request).then(response => {
          if (response.ok) {
            const clone = response.clone();
            caches.open(STATIC_CACHE).then(cache => cache.put(request, clone));
          }
          return response;
        })
      )
    );
  }
});
