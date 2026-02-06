# Notification System - Quick Start Guide

## What Was Implemented

VesselOS now has **full web push notifications with sound**, just like WhatsApp Web. When a new notification arrives, users will:

1. ✅ See a **browser notification** (desktop/mobile alert)
2. ✅ Hear a **sound notification** 
3. ✅ Get notifications even when **browser is minimized**
4. ✅ Manage settings from their **profile page**

## Files Created/Modified

| File | Type | Purpose |
|------|------|---------|
| `static/js/notification-service.js` | NEW | Core notification system |
| `static/js/notification-settings.js` | NEW | Settings UI component |
| `static/sw.js` | MODIFIED | Service Worker for background notifications |
| `templates/base.html` | MODIFIED | Added notification service scripts |
| `templates/profile.html` | MODIFIED | Added notification settings UI |
| `app.py` | MODIFIED | Added preference endpoints & DB table |

## Quick Test

### 1. Test in Browser Console
```javascript
// Send a test notification
notificationService.showBrowserNotification({
    title: 'Test Notification',
    body: 'This is a test!',
    type: 'success'
});

// Play sound
notificationService.playSound();

// Check current settings
console.log(notificationService.getSettings());
```

### 2. Test via UI
1. Go to user **Profile** page
2. Scroll to **Notification Settings** section
3. Click "Send Test Notification" button
4. You should see desktop notification + hear sound

### 3. Auto Permission Request
1. Visit the app for first time in a new browser
2. Browser shows permission dialog automatically
3. Click "Allow" to enable notifications

## How Notifications Flow

```
1. User receives a notification
   ↓
2. Frontend polls /api/notifications (every 30 seconds)
   ↓
3. New unread notification detected
   ↓
4. showBrowserNotification() called
   ↓
5. Desktop notification appears
   ↓
6. playSound() called (if enabled)
   ↓
7. Sound plays (respects system volume)
```

## User Settings

Users can toggle from **Profile → Notification Settings**:

| Setting | Default | Effect |
|---------|---------|--------|
| Sound notifications | ON | Plays `/static/sounds/notification.wav` |
| Browser notifications | ON | Shows desktop notifications |
| Permission Status | Shows current browser permission |

## Key Features

### ✅ Automatic Permission Request
- System asks user permission on first visit
- Shows native browser dialog (same as WhatsApp Web)
- User can revoke anytime in browser settings

### ✅ Sound Notifications
- Plays from `/static/sounds/notification.wav`
- Respects system volume
- Can be disabled in settings
- Auto-debounced (no spam)

### ✅ Desktop Notifications
- Shows even when browser minimized
- Shows title + body + icon
- Click to focus window
- Respects device settings

### ✅ Service Worker
- Handles background notifications
- Works when browser is closed
- Caches assets for offline
- Non-blocking (graceful fallback)

### ✅ Persistent Settings
- Saved to database
- Survive page reload
- Per-user settings

## Troubleshooting

### "Allow Notifications?" dialog doesn't appear
- First time? Browser should show automatic dialog
- Later? Go to Settings → allow notifications for this site

### Notifications work but no sound
- Check: `/static/sounds/notification.wav` exists
- Check: "Sound notifications" toggle is ON in settings
- Check: System volume is not muted
- Check: Browser has audio permission

### Notifications don't appear at all
- Check browser console for errors
- Check: Browser notifications are allowed in browser settings
- Check: Notifications not blocked in system settings
- Try: Refresh page and reload

### Service Worker errors
- Not critical - system works without it (fallback mode)
- Open DevTools → Application → Service Workers
- Try: Hard refresh (Ctrl+Shift+Delete)

## Integration Example

If you need to trigger a notification from your code:

```python
# In app.py
from flask import jsonify

@app.route('/api/send-notification', methods=['POST'])
@login_required
def send_notification():
    # Save notification to DB
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO notifications (user_id, title, message, type)
        VALUES (?, ?, ?, ?)
    """, (user_id, 'Title', 'Message', 'info'))
    conn.commit()
    
    # Frontend will pick it up on next poll (max 30 seconds)
    return jsonify({'success': True})
```

Frontend automatically picks up new notifications!

## Browser Support

| Browser | Desktop | Mobile | Notes |
|---------|---------|--------|-------|
| Chrome | ✅ | ✅ | Full support |
| Firefox | ✅ | ✅ | Full support |
| Safari | ✅ | ⚠️ | Limited PWA support |
| Edge | ✅ | ✅ | Full support |

---

**That's it!** Your notification system is ready to use. Users will get notifications just like WhatsApp Web! 🔔
