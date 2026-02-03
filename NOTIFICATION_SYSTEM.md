# Sound Notification System Documentation

## Overview

This comprehensive sound notification system provides multi-channel notifications that respect device settings and user preferences. It includes:

- **Sound notifications** with device volume awareness
- **Browser desktop notifications** (with permission)
- **In-app toast notifications** with visual feedback
- **Vibration support** on mobile devices
- **Quiet hours** to silence notifications during specific times
- **User preference storage** to remember settings
- **Device mute detection** to respect system audio settings
- **Badge counter** on browser tab
- **Text-to-speech** support for accessibility (optional)

## Installation

### 1. Include in base.html

Add the following to your `templates/base.html` in the `<head>` section:

```html
<!-- Notification System -->
<link rel="stylesheet" href="{{ url_for('static', filename='css/notifications.css') }}">
<script src="{{ url_for('static', filename='js/notification-handler.js') }}"></script>

<!-- Include settings panel -->
{% include 'notification-setup.html' %}
```

### 2. Add Notification Sounds

Place audio files in `static/sounds/`:
- `notification.mp3` - Standard message notification (256-512 KB)
- `alert.mp3` - Critical alerts (256-512 KB)
- `success.mp3` - Success notifications (256-512 KB)
- `error.mp3` - Error notifications (256-512 KB)

**Audio Recommendations:**
- Format: MP3 or OGG (browser compatible)
- Duration: 0.5-2 seconds
- Sample Rate: 44.1 kHz
- Bitrate: 128 kbps

### 3. Update Your Theme

Add a settings button to your navigation/dashboard:

```html
<button onclick="window.showNotificationSettings()" class="btn btn-icon">
    <i class="icon-bell"></i> Notification Settings
</button>
```

## API Endpoints

### Get Notification Preferences
```
GET /api/user/notification-preferences
Response:
{
    "success": true,
    "sound_enabled": true,
    "notifications_enabled": true,
    "vibration_enabled": true,
    "notification_type": "all",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00"
}
```

### Update Notification Preferences
```
POST /api/user/notification-preferences
Body:
{
    "sound_enabled": true,
    "notifications_enabled": true,
    "vibration_enabled": true,
    "notification_type": "all",
    "quiet_hours_start": "22:00",
    "quiet_hours_end": "08:00"
}
```

## JavaScript API

### Access Notification Handler

The notification handler is available globally as `window.notificationHandler`

### Methods

#### Initialize
```javascript
// Automatically initialized on page load
// Requests permissions from user
```

#### Send Notification Manually
```javascript
window.notificationHandler.handleNotification({
    id: 'notif_12345',
    title: 'New Message',
    message: 'You have a new message from John',
    type: 'message',
    severity: 'normal',
    created_at: new Date().toISOString(),
    action_url: '/messages/123'
});
```

#### Toggle Sound
```javascript
// Enable sound
window.notificationHandler.toggleSound(true);

// Disable sound
window.notificationHandler.toggleSound(false);

// Toggle
window.notificationHandler.toggleSound();
```

#### Toggle Desktop Notifications
```javascript
// Enable desktop notifications (requests permission)
await window.notificationHandler.toggleNotifications(true);

// Disable
await window.notificationHandler.toggleNotifications(false);
```

#### Play Sound Manually
```javascript
// Play specific sound type
window.notificationHandler.playSound('alert');  // alert, success, error, message
```

#### Speak Notification (Text-to-Speech)
```javascript
window.notificationHandler.speakNotification('You have a new notification');
```

#### Clear All Notifications
```javascript
window.notificationHandler.clearAll();
```

## Notification Object Structure

```javascript
{
    id: 'notification_id',           // Unique identifier
    title: 'Notification Title',     // Main heading
    message: 'Full message text',    // Detailed message
    type: 'message',                 // message, alert, success, error
    severity: 'normal',              // normal, high, critical
    action_url: '/path/to/action',   // Optional: where to navigate on click
    created_at: '2026-02-03T...',    // ISO timestamp
    sender_id: 123,                  // Optional: who sent it
    action_buttons: [                // Optional: action buttons
        {
            label: 'Accept',
            action: 'accept',
            style: 'primary'
        }
    ]
}
```

## Notification Types & Sounds

| Type | Icon | Color | Sound | Use Case |
|------|------|-------|-------|----------|
| message | 💬 | Blue | notification.mp3 | Regular messages, info |
| alert | ⚠️ | Orange | alert.mp3 | Warnings, important notices |
| success | ✅ | Green | success.mp3 | Completed actions, confirmations |
| error | ❌ | Red | error.mp3 | Errors, failures, critical issues |

## Device Setting Compliance

### Device Mute Detection
The system respects device mute/silent settings:
- **iOS**: Respects silent switch
- **Android**: Respects vibration settings
- **Windows/Mac**: Respects system volume

### Quiet Hours
Users can set quiet hours to automatically silence notifications:
- Configure start and end times
- Notifications still appear visually
- Sound suppressed during quiet hours
- Desktop notifications still work (configurable)

### Vibration
- Enabled on mobile devices by default
- Can be disabled in settings
- Uses Vibration API for haptic feedback

## Browser Compatibility

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| Web Notifications API | ✅ | ✅ | ✅ | ✅ |
| Audio Playback | ✅ | ✅ | ✅ | ✅ |
| Vibration API | ✅ | ✅ | ✅ | ✅ |
| Speech Synthesis | ✅ | ✅ | ✅ | ✅ |
| Service Worker | ✅ | ✅ | ✅ | ✅ |
| Badge API | ✅ | ❌ | ❌ | ✅ |

## Accessibility

The notification system is fully accessible:
- High contrast mode support
- Reduced motion preferences respected
- Screen reader compatible
- Keyboard navigable settings
- Text-to-speech support

## Security Considerations

1. **Permission-based**: Requires explicit user permission for desktop notifications
2. **HTTPS only**: Desktop notifications only work on HTTPS
3. **User control**: Users can disable at any time
4. **Data privacy**: No notification data sent to third parties
5. **XSS protection**: All notification content sanitized

## Troubleshooting

### Sound Not Playing
1. Check browser notification permissions
2. Verify audio files exist in `static/sounds/`
3. Check system volume and mute status
4. Check quiet hours settings
5. Ensure sound_enabled is true in preferences

### Desktop Notifications Not Appearing
1. Browser permission required - check browser notification settings
2. Must be on HTTPS
3. Check if notifications_enabled is true
4. Verify browser hasn't blocked notifications for site

### Vibration Not Working
1. Only works on mobile/touch devices
2. Requires vibration_enabled in preferences
3. Check device vibration settings
4. Some browsers limit vibration duration

### Audio Context Issues
```javascript
// If audio context errors occur:
// Check browser console for errors
// Verify CORS headers on audio files
// Ensure audio files are accessible
```

## Performance Optimization

1. **Lazy Loading**: Notification handler loads after page content
2. **Debounced Checks**: Polls every 5 seconds (configurable)
3. **Memory Efficient**: Clears old notifications from memory
4. **Minimal Overhead**: ~50KB JavaScript, ~20KB CSS
5. **Sound Caching**: Audio files cached by browser

## Database Schema

Required `user_settings` table columns:
```sql
user_id INTEGER PRIMARY KEY
sound_enabled BOOLEAN DEFAULT TRUE
notifications_enabled BOOLEAN DEFAULT TRUE
vibration_enabled BOOLEAN DEFAULT TRUE
notification_type TEXT DEFAULT 'all'
quiet_hours_start TIME
quiet_hours_end TIME
```

## Testing

### Manual Testing Checklist
- [ ] Sound plays on notification
- [ ] Sound respects device mute
- [ ] Desktop notification shows
- [ ] In-app toast displays
- [ ] Badge updates on tab
- [ ] Quiet hours silence sound
- [ ] Settings persist on refresh
- [ ] Works on mobile devices
- [ ] Vibration works (mobile)
- [ ] Clicking notification navigates

### Automated Testing
```javascript
// Test sound playback
await window.notificationHandler.playSound('success');

// Test toast notification
window.notificationHandler.showInAppNotification(
    { title: 'Test', message: 'Testing notifications' },
    'message'
);

// Test desktop notification
await window.notificationHandler.showBrowserNotification(
    { title: 'Test', message: 'Desktop notification' },
    'message'
);
```

## Advanced Configuration

### Custom Sound URLs
```javascript
window.notificationHandler.soundUrls = {
    message: '/custom/sounds/message.mp3',
    alert: '/custom/sounds/alert.mp3',
    success: '/custom/sounds/success.mp3',
    error: '/custom/sounds/error.mp3'
};
```

### Custom Notification Position
```javascript
// Change container position
const container = document.getElementById('notification-container');
container.classList.add('bottom-left');  // top-right (default), bottom-left, bottom-right, top-left
```

### Disable Auto-Polling
```javascript
// Override the polling interval
// Modify startNotificationListener() in notification-handler.js
setInterval(() => this.checkForNewNotifications(), 10000); // 10 seconds
```

## License & Attribution

This notification system is part of the Marine Service System and follows the same license as the main application.

## Support

For issues or questions:
1. Check browser console for errors
2. Review notification preferences
3. Verify audio files are accessible
4. Check device/OS notification settings
5. Review this documentation
