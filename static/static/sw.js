/**
 * Service Worker for VesselOS
 * Handles background notifications even when the app is not in focus
 */

const CACHE_NAME = 'vesselOS-v1';
const urlsToCache = [
    '/',
    '/static/images/logo.png'
];

// Install event - cache resources
self.addEventListener('install', (event) => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then((cache) => cache.addAll(urlsToCache))
            .catch(error => console.log('Cache installation error:', error))
    );
    self.skipWaiting();
});

// Activate event - clean up old caches
self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((cacheNames) => {
            return Promise.all(
                cacheNames.map((cacheName) => {
                    if (cacheName !== CACHE_NAME) {
                        return caches.delete(cacheName);
                    }
                })
            );
        })
    );
    self.clients.claim();
});

// Handle push notifications from server
self.addEventListener('push', (event) => {
    console.log('Push notification received:', event);
    
    let notificationData = {
        title: 'VesselOS',
        body: 'You have a new notification',
        icon: '/static/images/logo.png',
        badge: '/static/images/logo.png',
        tag: 'default-notification'
    };

    if (event.data) {
        try {
            const data = event.data.json();
            notificationData = {
                title: data.title || notificationData.title,
                body: data.body || notificationData.body,
                icon: data.icon || notificationData.icon,
                badge: data.badge || notificationData.badge,
                tag: data.tag || notificationData.tag,
                data: data.data || {}
            };
        } catch (error) {
            console.error('Error parsing push notification data:', error);
            notificationData.body = event.data.text();
        }
    }

    event.waitUntil(
        self.registration.showNotification(notificationData.title, {
            body: notificationData.body,
            icon: notificationData.icon,
            badge: notificationData.badge,
            tag: notificationData.tag,
            requireInteraction: false,
            vibrate: [200, 100, 200],
            data: notificationData.data
        })
    );
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
    console.log('Notification clicked:', event.notification.tag);
    event.notification.close();

    // Focus or open the window
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true })
            .then((clientList) => {
                // Check if there's already a window/tab open
                for (let i = 0; i < clientList.length; i++) {
                    const client = clientList[i];
                    if (client.url === '/' && 'focus' in client) {
                        return client.focus();
                    }
                }
                // If not, open a new window
                if (clients.openWindow) {
                    return clients.openWindow('/');
                }
            })
    );
});

// Handle notification close
self.addEventListener('notificationclose', (event) => {
    console.log('Notification closed:', event.notification.tag);
});

// Fetch event - serve from cache, fallback to network
self.addEventListener('fetch', (event) => {
    // Only handle GET requests
    if (event.request.method !== 'GET') {
        return;
    }

    event.respondWith(
        caches.match(event.request)
            .then((response) => {
                // Cache hit - return response
                if (response) {
                    return response;
                }
                return fetch(event.request).then((response) => {
                    // Check if we received a valid response
                    if (!response || response.status !== 200 || response.type === 'error') {
                        return response;
                    }

                    // Clone the response
                    const responseToCache = response.clone();
                    caches.open(CACHE_NAME)
                        .then((cache) => {
                            cache.put(event.request, responseToCache);
                        });

                    return response;
                });
            })
            .catch(() => {
                // Network request failed, try to return a cached response
                return caches.match(event.request)
                    .catch(() => {
                        // Return a generic offline page or message
                        return new Response('Offline - unable to fetch resource');
                    });
            })
    );
});

// Periodic background sync for notifications
if ('periodicSync' in self.registration) {
    self.addEventListener('periodicsync', (event) => {
        if (event.tag === 'check-notifications') {
            event.waitUntil(checkForNotifications());
        }
    });
}

/**
 * Check for new notifications from the server
 */
async function checkForNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const data = await response.json();

        if (data.success && data.notifications && data.notifications.length > 0) {
            const unreadNotifications = data.notifications.filter(n => !n.is_read);
            
            if (unreadNotifications.length > 0) {
                const latestNotification = unreadNotifications[0];
                
                // Show notification
                await self.registration.showNotification(
                    latestNotification.title || 'New Notification',
                    {
                        body: latestNotification.message || '',
                        icon: '/static/images/logo.png',
                        badge: '/static/images/logo.png',
                        tag: `notification-${latestNotification.id}`,
                        requireInteraction: false
                    }
                );
            }
        }
    } catch (error) {
        console.error('Error checking notifications in service worker:', error);
    }
}
