# Sound Notification System - Quick Integration Guide

## Step 1: Add Notification Files to Base Template

In your `templates/base.html`, add this to the `<head>` section:

```html
<!-- Notification System CSS and JS -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/notifications.css') }}">
<script defer src="{{ url_for('static', filename='js/notification-handler.js') }}"></script>

<!-- Notification Settings Panel -->
{% include 'notification-setup.html' %}
```

## Step 2: Add Notification Sound Files

Create sound files in `static/sounds/` directory:

**Option A: Use Free Sounds**
Download from:
- Notification: https://freepik.es/search/notification-sound
- Alert: https://freepik.es/search/alert-sound
- Success: https://freepik.es/search/success-sound
- Error: https://freepik.es/search/error-sound

**Option B: Generate Online**
- Bfxr (8-bit sounds): https://www.bfxr.net/
- Jsfxr (JavaScript): https://github.com/mneubrand/jsfxr
- Online sound effects: https://www.zapsplat.com/

Files needed:
```
static/sounds/
├── notification.mp3  (256-512 KB)
├── alert.mp3         (256-512 KB)
├── success.mp3       (256-512 KB)
└── error.mp3         (256-512 KB)
```

## Step 3: Add Settings Button to Navigation

In your navbar/dashboard template, add:

```html
<button class="btn btn-icon" onclick="window.showNotificationSettings()" 
        title="Notification Settings">
    <i class="icon-bell"></i>
</button>
```

Or as a menu item:

```html
<li class="nav-item">
    <a class="nav-link" href="#" onclick="window.showNotificationSettings(); return false;">
        <i class="icon-bell"></i> Notification Settings
    </a>
</li>
```

## Step 4: Test the System

Open browser console and run:

```javascript
// Test manual notification
window.notificationHandler.handleNotification({
    id: 'test_001',
    title: 'Test Notification',
    message: 'This is a test notification with sound',
    type: 'message',
    created_at: new Date().toISOString()
});

// Test alert sound
window.notificationHandler.playSound('alert');

// Check if notifications enabled
console.log(window.notificationHandler.notificationPermission);
console.log(window.notificationHandler.soundEnabled);
```

## Step 5: Handle Backend Notifications

When your backend sends notifications, dispatch custom event:

```python
# In app.py when creating a notification
@app.route('/api/send-notification')
@login_required
def api_send_notification():
    # ... create notification in database ...
    
    # Log this to trigger frontend pickup
    app.logger.info(f"New notification created for user {user_id}")
    
    # Return success
    return jsonify({'success': True})
```

The notification handler will automatically:
1. Poll for new notifications every 5 seconds
2. Play sound when found
3. Show desktop notification
4. Display in-app toast

## Step 6: Optional - Add User Settings Column

If you don't have `user_settings` table, create it:

```sql
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    sound_enabled BOOLEAN DEFAULT TRUE,
    notifications_enabled BOOLEAN DEFAULT TRUE,
    vibration_enabled BOOLEAN DEFAULT TRUE,
    notification_type TEXT DEFAULT 'all',
    quiet_hours_start TIME,
    quiet_hours_end TIME,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
```

Or update existing user table:

```sql
ALTER TABLE users ADD COLUMN sound_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN notifications_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN vibration_enabled BOOLEAN DEFAULT TRUE;
ALTER TABLE users ADD COLUMN quiet_hours_start TIME;
ALTER TABLE users ADD COLUMN quiet_hours_end TIME;
```

## Step 7: Request Notification Permission

Add this to your login/dashboard page:

```html
<script>
document.addEventListener('DOMContentLoaded', () => {
    // Auto-request notification permission on first visit
    if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission();
    }
});
</script>
```

## Features Summary

✅ **Sound Notifications**
- Plays sound when new notifications arrive
- Respects device mute/silent status
- Configurable volume (70%)
- Different sounds for different types

✅ **Desktop Notifications**
- Shows OS-level notifications
- Requires user permission
- Click to navigate to relevant page
- Auto-dismisses after 8 seconds (or requires interaction for alerts)

✅ **In-App Toasts**
- Always visible notification display
- Color-coded by type
- Auto-removes after 8 seconds
- Smooth animations

✅ **Device Compliance**
- Respects system volume settings
- Respects mute switch (iOS)
- Respects vibration preferences
- Follows quiet hours (configurable)

✅ **User Control**
- Easy toggle for sound
- Easy toggle for desktop notifications
- Vibration on/off
- Set quiet hours
- All preferences saved

✅ **Accessibility**
- Dark mode support
- High contrast mode
- Respects reduced motion preference
- Screen reader compatible
- Text-to-speech option

## Customization

### Change Notification Position
```html
<!-- In your CSS or inline -->
<script>
document.addEventListener('DOMContentLoaded', () => {
    const container = document.getElementById('notification-container');
    container.classList.add('bottom-left');  // Available: top-right (default), bottom-left, bottom-right, top-left
});
</script>
```

### Change Sound Files
```javascript
window.notificationHandler.soundUrls = {
    message: '/path/to/custom/message.mp3',
    alert: '/path/to/custom/alert.mp3',
    success: '/path/to/custom/success.mp3',
    error: '/path/to/custom/error.mp3'
};
```

### Change Polling Interval
Edit `static/js/notification-handler.js`, line ~65:
```javascript
setInterval(() => this.checkForNewNotifications(), 5000);  // Change 5000 to your preferred milliseconds
```

## Troubleshooting

**Sound not playing?**
1. Check browser notification permissions
2. Check system volume and mute status
3. Verify audio files exist: `/static/sounds/*.mp3`
4. Check browser console for errors
5. Try enabling in notification settings

**Desktop notifications not working?**
1. Requires HTTPS (or localhost)
2. Requires user permission - check browser notification settings
3. Check browser console for errors
4. Some browsers may block notifications - check filter in browser settings

**Vibration not working?**
1. Only works on mobile devices
2. Requires vibration_enabled in preferences
3. Check device vibration settings

## Browser Support

| Feature | Chrome | Firefox | Safari | Edge | Mobile |
|---------|--------|---------|--------|------|--------|
| Sound | ✅ | ✅ | ✅ | ✅ | ✅ |
| Desktop Notifications | ✅ | ✅ | ✅ | ✅ | ✅ |
| Vibration | ✅ | ✅ | ✅ | ✅ | ✅ |
| Badge | ✅ | ❌ | ❌ | ✅ | ✅ |

## Need Help?

See `NOTIFICATION_SYSTEM.md` for comprehensive documentation including:
- Complete API reference
- Notification object structure
- Advanced configuration
- Performance optimization
- Security considerations
- Testing procedures
