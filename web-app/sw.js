// Service Worker for 价值投资研究平台
const CACHE_NAME = 'value-investing-v1';
const STATIC_CACHE = 'static-v1';
const DATA_CACHE = 'data-v1';

// Static resources to pre-cache
const PRECACHE_URLS = [
  './',
  './index.html',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png',
];

// CDN resources to cache on first use
const CDN_URLS = [
  'https://cdn.tailwindcss.com',
  'https://unpkg.com/vue@3/dist/vue.global.prod.js',
  'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js',
  'https://cdn.jsdelivr.net/npm/marked/marked.min.js',
];

// Install: pre-cache core resources
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
  self.skipWaiting();
});

// Activate: clean up old caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) => {
      return Promise.all(
        names
          .filter((name) => name !== STATIC_CACHE && name !== DATA_CACHE)
          .map((name) => caches.delete(name))
      );
    })
  );
  self.clients.claim();
});

// Fetch: different strategies for different resources
self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // JSON data files: Network First (try network, fall back to cache)
  if (url.pathname.endsWith('.json') && url.origin === self.location.origin) {
    event.respondWith(networkFirst(event.request, DATA_CACHE));
    return;
  }

  // CDN resources: Cache First (use cache, fall back to network)
  if (CDN_URLS.some((cdn) => event.request.url.startsWith(cdn))) {
    event.respondWith(cacheFirst(event.request, STATIC_CACHE));
    return;
  }

  // Same-origin static resources: Cache First
  if (url.origin === self.location.origin) {
    event.respondWith(cacheFirst(event.request, STATIC_CACHE));
    return;
  }

  // All other requests: network only
  event.respondWith(fetch(event.request));
});

// Cache First strategy
async function cacheFirst(request, cacheName) {
  const cached = await caches.match(request);
  if (cached) return cached;

  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    return new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
  }
}

// Network First strategy
async function networkFirst(request, cacheName) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(cacheName);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await caches.match(request);
    if (cached) return cached;
    return new Response('{"error":"offline"}', {
      status: 503,
      headers: { 'Content-Type': 'application/json' },
    });
  }
}
