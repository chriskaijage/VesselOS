# Notification Sound System Updates

## Overview
Enhanced notification system to support sound notifications for **all notification types including messages**, with **one-time sound playback per notification** (no repeats).

## Changes Made

### 1. **notification-handler.js** Updates

#### Added Sound Tracking
- **New Property**: `this.playedSounds = new Set()`
- Tracks which notifications have already had their sound played
- Prevents sound from repeating for the same notification

#### Enhanced handleNotification() Method
- **Checks sound played status** before playing sound
- **Marks notification immediately** when sound plays (prevents duplicate sounds)
- Returns early if sound already played for notification ID
- Ensures each notification sound plays exactly once

```javascript
// Before: Could repeat sounds
async handleNotification(notification) {
    if (this.soundEnabled) {
        await this.playSound(type);  // Would play again on polling
    }
}

// After: Plays sound exactly once
async handleNotification(notification) {
    if (this.playedSounds.has(notification.id)) {
        return;  // Already played sound for this notification
    }
    if (this.soundEnabled) {
        this.playedSounds.add(notification.id);  // Mark as played
        await this.playSound(type);  // Play once
    }
}
```

#### Improved getNotificationType() Method
- **Detects message notifications** via multiple fields:
  - `notification.type === 'message'`
  - `notification.message_id`
  - `notification.sender_id`
  - `notification.message` + `notification.sender_name`
- **Sound plays for all message types** automatically
- **Default type**: Falls back to 'message' (ensures sound plays)
- **Priority detection**:
  - Errors with critical/high severity → alert sound
  - Success type → success sound
  - Messages → message sound

```javascript
getNotificationType(notification) {
    // Message detection with multiple fallbacks
    if (notification.type === 'message' || 
        notification.message_id || 
        notification.sender_id) {
        return 'message';  // Triggers notification.mp3
    }
    // ... error and success detection ...
    return 'message';  // Default to message sound
}
```

#### Enhanced clearAll() Method
- **Resets played sounds** when clearing notifications
- Allows same notifications to play sound again if they reappear
- Proper cleanup of tracking

### 2. **app.py** /api/notifications Endpoint Updates

#### Improved Notification Response
- **Includes message type** in response for sound detection
- **Standardizes type field** - converts 'normal' or 'info' to 'message'
- **Unique ID format** - prefixes with 'notif_' for consistency

```python
# Standardize message notification types for sound
if notification['type'] in ['normal', 'message', 'info']:
    notification['type'] = 'message'

# Ensure unique ID format
notification['id'] = f"notif_{notification['id']}"
```

## How It Works

### Sound Playback Flow
1. **New notification arrives** via polling (`/api/notifications`)
2. **Handler checks**: Has sound already played for this notification ID? 
3. **If NO**:
   - Mark notification ID in `playedSounds` Set
   - Determine notification type (message/alert/error/success)
   - Play corresponding sound file (once)
4. **If YES**: Skip sound (already played)
5. **Then**: Show browser notification and toast (always displayed)

### Multi-Type Message Support
Messages now trigger sounds via these mechanisms:

#### Type 1: System Notifications
```javascript
notification.type = 'message'
notification.type = 'normal'  // Converts to 'message'
notification.type = 'info'    // Converts to 'message'
```

#### Type 2: Direct Messages
```javascript
notification.message_id = 'MSG_123'     // Message field detected
notification.sender_id = 'user_456'     // From user detected
notification.message = 'Hello!'         // Message content
```

#### Type 3: User-to-User Messages
- Created by `/api/messaging/send` endpoint
- Created by `/api/messaging/quick-send` endpoint
- Automatically creates notification with type='message'
- Sound plays via handler detection

## Sound Files Required

Place in `static/sounds/`:

| Sound | File | Use Case |
|-------|------|----------|
| Message | notification.mp3 | Regular messages, info |
| Alert | alert.mp3 | Warnings, high priority |
| Success | success.mp3 | Confirmations, completed tasks |
| Error | error.mp3 | Errors, failures |

**Audio Specs**: ~0.5-2 seconds, 256-512 KB MP3 files

## Testing Sound Notifications

### Test 1: Message Sound (Should play once)
```javascript
// In browser console
window.notificationHandler.handleNotification({
    id: 'test_msg_001',
    title: 'Test Message',
    message: 'This is a test message',
    type: 'message',
    created_at: new Date().toISOString()
});
// Listen for notification.mp3 sound
// Polling again should NOT replay sound
```

### Test 2: Message with Sender (Should detect and play)
```javascript
window.notificationHandler.handleNotification({
    id: 'test_msg_002',
    title: 'John Doe',
    message: 'Hello there!',
    sender_id: 'user_123',
    message_id: 'MSG_456',
    created_at: new Date().toISOString()
});
// Should automatically detect as message and play sound
```

### Test 3: No Sound Repeat (Clear confirmation)
```javascript
const notif = {
    id: 'test_msg_003',
    title: 'No Repeat Test',
    message: 'Sound should play once',
    type: 'message',
    created_at: new Date().toISOString()
};

// First call - plays sound
window.notificationHandler.handleNotification(notif);

// Same notification again (simulates polling) - NO sound
window.notificationHandler.handleNotification(notif);
console.log('Played sounds:', window.notificationHandler.playedSounds);
// Should show: Played sounds: Set(1) { 'test_msg_003' }
```

### Test 4: Quick Send Message Sound
1. Open messaging interface
2. Send a message to another user
3. Recipient should hear sound notification (once)
4. Message appears in toast and browser notification

## Features Preserved

✅ **Desktop Notifications** - Continue to show (with or without sound)
✅ **In-App Toasts** - Continue to display with animations
✅ **Badge Counter** - Still updates with unread count
✅ **User Preferences** - Sound toggle still respected
✅ **Quiet Hours** - Still enforced
✅ **Device Mute Detection** - Still active
✅ **All Notification Types** - Alert, Success, Error all work

## New Features

✨ **Message Sound Support** - Messages now trigger sound
✨ **One-Time Playback** - Each notification plays sound exactly once
✨ **Smart Type Detection** - Recognizes messages from multiple fields
✨ **Fallback Safety** - Defaults to message type if unclear
✨ **Tracking Cleanup** - Sound tracking resets with notifications

## Browser Compatibility

| Browser | Desktop | Mobile | Notes |
|---------|---------|--------|-------|
| Chrome | ✅ Full | ✅ Full | Complete support |
| Firefox | ✅ Full | ✅ Full | Complete support |
| Safari | ✅ Full | ⚠️ Limited | May require user interaction |
| Edge | ✅ Full | ✅ Full | Complete support |

## Performance Impact

- **Memory**: +minimal (one Set per page load)
- **CPU**: Negligible (simple Set lookup)
- **Network**: No changes
- **Polling**: Same 5-second intervals

## Database Schema

No changes required. Uses existing `notifications` table with `type` field.

```sql
-- Already exists
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT,                    -- Used for sound type
    action_url TEXT,
    created_at DATETIME,
    is_read BOOLEAN DEFAULT 0
);
```

## Configuration

### Global Settings
```javascript
// notification-handler.js
this.soundEnabled = true;           // Enable/disable all sounds
this.notificationPermission = 'default';  // Browser permission status
this.isSystemMuted = false;         // Device mute detection
```

### User Preferences
- Managed via `/api/user/notification-preferences`
- Stored per user in database
- Sound toggle applies to all notification types

## Troubleshooting

### Sound Not Playing
1. **Check sound files exist**: `static/sounds/notification.mp3`, etc.
2. **Check browser permission**: Check browser notification permission
3. **Check device mute**: Ensure device is not muted
4. **Check setting**: Open notification preferences, enable sound
5. **Check console**: Look for errors in browser dev tools

### Sound Repeating
- Should not happen with this update
- If occurs, clear browser cache and reload
- Check `playedSounds` Set in console: `window.notificationHandler.playedSounds`

### Message Sound Not Triggering
1. **Check message type**: Should be 'message' or 'normal'
2. **Check notification creation**: Verify message creates notification via `create_notification()`
3. **Check detection**: Ensure `message_id` or `sender_id` fields present
4. **Test directly**: Use browser console test above

## Future Enhancements

- [ ] Per-notification sound customization
- [ ] Scheduled sound playback
- [ ] Sound volume adjustment per type
- [ ] VoiceOver/screen reader audio cues
- [ ] Haptic feedback patterns per type
- [ ] Smart sound selection based on priority
- [ ] Notification grouping with single sound

## Git Commit

```
feat: Implement one-time sound playback for all notifications including messages

- Add playedSounds Set to track notifications that have had sound played
- Prevent sound from repeating on same notification
- Enhance getNotificationType() to detect message notifications
- Update /api/notifications endpoint to standardize message types
- Ensure message notifications always trigger sound
- Sound plays exactly once per unique notification ID
- All notification types (message, alert, success, error) supported
- Desktop notifications and toasts continue to display always
```

## Migration Notes

No database migrations needed. System is backward compatible.

## Support

For issues with notification sounds:
1. Check browser console for errors
2. Verify sound files in `static/sounds/`
3. Test with browser console commands above
4. Check notification preferences settings
5. Review browser notification permissions
