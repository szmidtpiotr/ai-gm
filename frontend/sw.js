// Service Worker — AI-GM Web Push handler
// Receives push events when browser is in background/closed

self.addEventListener('push', function(event) {
    if (!event.data) return;
    let data;
    try {
        data = event.data.json();
    } catch (e) {
        data = { title: 'AI-GM', body: event.data.text(), url: '/' };
    }
    const options = {
        body: data.body || '',
        icon: data.icon || '/graj/icon-192.png',
        badge: data.badge || '/graj/icon-192.png',
        data: { url: data.url || '/' },
        requireInteraction: false,
    };
    if (data.image) options.image = data.image;
    if (data.vibrate) options.vibrate = data.vibrate;
    event.waitUntil(
        self.registration.showNotification(data.title || 'AI-GM', options)
    );
});

self.addEventListener('notificationclick', function(event) {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || '/';
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(clientList) {
            for (const client of clientList) {
                if (client.url.includes(self.location.origin) && 'focus' in client) {
                    client.navigate(url);
                    return client.focus();
                }
            }
            if (clients.openWindow) {
                return clients.openWindow(url);
            }
        })
    );
});
