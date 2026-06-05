// OfferAgent Web App JavaScript
// HTMX configuration and utilities

document.body.addEventListener('htmx:configRequest', function(event) {
    // Add session token to all HTMX requests
    const token = getCookie('session_token');
    if (token) {
        event.detail.headers['X-Session-Token'] = token;
    }
});

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return null;
}

// Notification polling
function initNotifications() {
    const badge = document.getElementById('notif-badge');
    if (!badge) return;

    loadNotificationCount();
    setInterval(loadNotificationCount, 30000);
}

function loadNotificationCount() {
    fetch('/api/notifications/unread-count')
        .then(r => r.json())
        .then(data => {
            const badge = document.getElementById('notif-badge');
            if (data.count > 0) {
                badge.textContent = data.count > 99 ? '99+' : data.count;
                badge.classList.remove('hidden');
            } else {
                badge.classList.add('hidden');
            }
        })
        .catch(() => {});
}

initNotifications();
