// Service Worker für TutorFlow PWA
const CACHE_NAME = 'tutorflow-v1';
const STATIC_CACHE_NAME = 'tutorflow-static-v1';
const DYNAMIC_CACHE_NAME = 'tutorflow-dynamic-v1';

// Dateien, die beim Installieren gecacht werden sollen
const STATIC_FILES = [
  '/',
  '/static/icons/icon-192x192.png',
  '/static/icons/icon-512x512.png',
];

// Install Event - Cache statische Dateien
self.addEventListener('install', (event) => {
  console.log('[Service Worker] Installing...');
  event.waitUntil(
    caches.open(STATIC_CACHE_NAME)
      .then((cache) => {
        console.log('[Service Worker] Caching static files');
        return cache.addAll(STATIC_FILES);
      })
      .catch((error) => {
        console.error('[Service Worker] Error caching static files:', error);
      })
  );
  self.skipWaiting();
});

// Activate Event - Alte Caches löschen
self.addEventListener('activate', (event) => {
  console.log('[Service Worker] Activating...');
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheName !== STATIC_CACHE_NAME && cacheName !== DYNAMIC_CACHE_NAME) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  return self.clients.claim();
});

// Fetch Event - Network First Strategy für API, Cache First für statische Dateien
self.addEventListener('fetch', (event) => {
  const { request } = event;
  const url = new URL(request.url);

  // Skip non-GET requests
  if (request.method !== 'GET') {
    return;
  }

  // Skip cross-origin requests
  if (url.origin !== location.origin) {
    return;
  }

  // API Requests: Network First
  if (url.pathname.startsWith('/api/') || url.pathname.includes('/api/')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Clone response before caching
          const responseToCache = response.clone();
          caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
          return response;
        })
        .catch(() => {
          // Fallback to cache if network fails
          return caches.match(request);
        })
    );
    return;
  }

  // Static files: Cache First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(request).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(request).then((response) => {
          const responseToCache = response.clone();
          caches.open(STATIC_CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
          return response;
        });
      })
    );
    return;
  }

  // HTML Pages: Network First with Cache Fallback
  if (request.headers.get('accept').includes('text/html')) {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const responseToCache = response.clone();
          caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
            cache.put(request, responseToCache);
          });
          return response;
        })
        .catch(() => {
          return caches.match(request).then((cachedResponse) => {
            if (cachedResponse) {
              return cachedResponse;
            }
            // Fallback to offline page if available
            return caches.match('/');
          });
        })
    );
    return;
  }

  // Default: Network First
  event.respondWith(
    fetch(request)
      .then((response) => {
        const responseToCache = response.clone();
        caches.open(DYNAMIC_CACHE_NAME).then((cache) => {
          cache.put(request, responseToCache);
        });
        return response;
      })
      .catch(() => {
        return caches.match(request);
      })
  );
});

// Background Sync (optional, für Offline-Funktionalität)
self.addEventListener('sync', (event) => {
  console.log('[Service Worker] Background sync:', event.tag);
  // Hier können Offline-Aktionen synchronisiert werden
});

// Push Notifications (optional)
self.addEventListener('push', (event) => {
  console.log('[Service Worker] Push notification received');
  // Push-Benachrichtigungen können hier implementiert werden
});
