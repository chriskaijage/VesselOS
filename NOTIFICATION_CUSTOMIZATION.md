# Notification System - Customization Guide

## Overview

This guide explains how to customize and extend the notification system for your specific needs.

## Quick Customizations

### 1. Change Notification Sound

Replace the sound file:
1. Prepare a new audio file (WAV, MP3, or OGG format)
2. Copy to `/static/sounds/`
3. Update path in `notification-service.js` (line ~8):
   ```javascript
   this.notificationSound = '/static/sounds/your-custom-sound.wav';
   ```
4. Test: `notificationService.playSound();`

### 2. Change Sound Volume

In `notification-service.js` (playSound method):
```javascript
const audio = new Audio(this.notificationSound);
audio.volume = 0.7;  // Change 0.7 to desired volume (0-1)
```

### 3. Change Polling Frequency

In `templates/base.html` (search for "setInterval"):
```javascript
// Every 10 seconds
setInterval(() => {
    notificationService.checkForNewNotifications();
}, 10000);

// Every 60 seconds
setInterval(() => {
    notificationService.checkForNewNotifications();
}, 60000);
```

### 4. Change Notification Icons

In `notification-service.js` (showBrowserNotification method):
```javascript
const iconMap = {
    'danger': '/static/images/your-danger-icon.png',
    'warning': '/static/images/your-warning-icon.png',
    'success': '/static/images/your-success-icon.png',
    'info': '/static/images/your-info-icon.png'
};
```

## Advanced Customizations

### Multiple Sounds by Type

```javascript
// In notification-service.js constructor
constructor() {
    this.sounds = {
        'danger': '/static/sounds/alert.wav',
        'warning': '/static/sounds/warning.wav',
        'success': '/static/sounds/success.wav',
        'info': '/static/sounds/info.wav'
    };
}

// New method to play by type
async playSoundForType(type) {
    const soundFile = this.sounds[type] || this.sounds['info'];
    const audio = new Audio(soundFile);
    audio.volume = 0.7;
    await audio.play();
}

// Use in showBrowserNotification
await this.playSoundForType(notificationData.type);
```

### Do Not Disturb Hours

```python
# In app.py - new endpoint
@app.route('/api/user/quiet-hours', methods=['GET', 'POST'])
@login_required
def quiet_hours():
    if request.method == 'POST':
        data = request.get_json()
        start_time = data.get('start_time')  # HH:MM format
        end_time = data.get('end_time')
        
        # Save to database
        c.execute("""
            INSERT OR REPLACE INTO quiet_hours
            (user_id, start_time, end_time)
            VALUES (?, ?, ?)
        """, (current_user.id, start_time, end_time))
        conn.commit()
        
        return jsonify({'success': True})
```

```javascript
// Check if in quiet hours before playing sound
function isQuietHours() {
    const now = new Date();
    const currentTime = now.getHours() + ':' + String(now.getMinutes()).padStart(2, '0');
    
    // Compare with user's quiet hours
    // Return true if in quiet period
}

// Modified playSound
async playSound() {
    if (!this.soundEnabled || isQuietHours()) {
        return;  // Skip sound during quiet hours
    }
    // ... rest of playSound code
}
```

### Notification Categories

```python
# Add to notification_preferences table
ALTER TABLE notification_preferences ADD COLUMN
    notify_maintenance INTEGER DEFAULT 1;
ALTER TABLE notification_preferences ADD COLUMN
    notify_emergency INTEGER DEFAULT 1;
ALTER TABLE notification_preferences ADD COLUMN
    notify_system INTEGER DEFAULT 1;
```

```javascript
// Filter notifications by category in checkForNewNotifications
const preferences = notificationService.getSettings();

if (notification.category === 'maintenance' && !preferences.notify_maintenance) {
    return;  // Skip this notification
}
```

### Email Notifications

```python
import smtplib
from email.mime.text import MIMEText

def send_notification_email(user_email, title, message):
    """Send email notification to user."""
    msg = MIMEText(f"<h3>{title}</h3><p>{message}</p>", 'html')
    msg['Subject'] = f"[VesselOS] {title}"
    msg['From'] = os.environ.get('MAIL_FROM')
    msg['To'] = user_email
    
    # Send via configured email service
    # This is placeholder - configure with your email settings
    try:
        server = smtplib.SMTP(os.environ.get('MAIL_SERVER'))
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        app.logger.error(f"Email send failed: {e}")
        return False

# Check preference before sending
@app.route('/api/user/notification-preferences')
def get_preferences():
    # ... existing code ...
    if data.get('email_notifications'):
        send_notification_email(user.email, notif['title'], notif['message'])
```

### Push Notifications (Server-Sent)

Instead of polling, use server-sent events:

```python
# Flask endpoint for server-sent events
@app.route('/api/notifications/stream')
@login_required
def notification_stream():
    def generate():
        last_check = datetime.now()
        while True:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("""
                SELECT id, title, message, type, created_at
                FROM notifications
                WHERE user_id = ? AND created_at > ?
                ORDER BY created_at DESC
            """, (current_user.id, last_check))
            
            notifications = c.fetchall()
            conn.close()
            
            if notifications:
                for notif in notifications:
                    yield f"data: {json.dumps(dict(notif))}\n\n"
                last_check = datetime.now()
            
            time.sleep(1)  # Check every second
    
    return Response(generate(), mimetype='text/event-stream')
```

```javascript
// JavaScript to consume server-sent events
const eventSource = new EventSource('/api/notifications/stream');

eventSource.addEventListener('message', (event) => {
    const notification = JSON.parse(event.data);
    
    notificationService.showBrowserNotification({
        title: notification.title,
        body: notification.message,
        type: notification.type
    });
    
    notificationService.playSound();
});

eventSource.addEventListener('error', (event) => {
    eventSource.close();
});
```

### Custom Notification Actions

```javascript
// In showBrowserNotification
const options = {
    // ... existing options ...
    actions: [
        {
            action: 'approve',
            title: 'Approve',
            icon: '/static/images/approve.png'
        },
        {
            action: 'reject',
            title: 'Reject',
            icon: '/static/images/reject.png'
        },
        {
            action: 'close',
            title: 'Close',
            icon: '/static/images/close.png'
        }
    ]
};

const notification = new Notification(notificationData.title, options);

// Handle action clicks
notification.addEventListener('click', (event) => {
    if (event.action === 'approve') {
        // Send approval request
        fetch(`/api/notification/${notificationData.id}/approve`, {
            method: 'POST'
        });
    } else if (event.action === 'reject') {
        // Send rejection request
        fetch(`/api/notification/${notificationData.id}/reject`, {
            method: 'POST'
        });
    }
    notification.close();
});
```

### Rate Limiting per User

```python
# Track notification frequency
def check_notification_rate_limit(user_id):
    """Check if user is getting too many notifications."""
    conn = get_db_connection()
    c = conn.cursor()
    
    # Count notifications sent in last minute
    c.execute("""
        SELECT COUNT(*) as count
        FROM notifications
        WHERE user_id = ? AND created_at > datetime('now', '-1 minute')
    """, (user_id,))
    
    count = c.fetchone()['count']
    conn.close()
    
    # Limit to 10 per minute per user
    return count < 10

# Use in notification creation
if check_notification_rate_limit(user_id):
    # Create notification
else:
    # Batch notifications or defer
    app.logger.warning(f"Rate limit hit for user {user_id}")
```

### Notification History/Archive

```python
@app.route('/api/notifications/archive', methods=['GET'])
@login_required
def archive_notifications():
    """Get archived notifications."""
    conn = get_db_connection()
    c = conn.cursor()
    
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 20, type=int)
    offset = (page - 1) * limit
    
    c.execute("""
        SELECT id, title, message, type, created_at, is_read
        FROM notifications
        WHERE user_id = ?
        ORDER BY created_at DESC
        LIMIT ? OFFSET ?
    """, (current_user.id, limit, offset))
    
    notifications = [dict(zip([col[0] for col in c.description], row)) 
                    for row in c.fetchall()]
    
    conn.close()
    
    return jsonify({
        'success': True,
        'notifications': notifications,
        'page': page,
        'limit': limit
    })
```

## Configuration Examples

### Strict Notifications (Minimal Notifications)
```javascript
notificationService.toggleSound(false);
notificationService.toggleBrowserNotifications(false);
notificationService.saveUserPreferences();
```

### Verbose Notifications (All Notifications)
```javascript
// Change debounce time
this.notificationDebounceMs = 100;  // Very short debounce

// Lower polling interval
// Change in base.html to 5000 (5 seconds)
```

### Mobile-Optimized
```javascript
// Longer debounce for mobile
this.notificationDebounceMs = 2000;

// Longer polling for battery life
// Change in base.html to 60000 (60 seconds)

// Vibration pattern
vibrate: [100, 50, 100]  // In showBrowserNotification
```

## Testing Customizations

### Test in Console
```javascript
// Test custom sound
new Audio('/static/sounds/custom.wav').play();

// Test quiet hours
console.log(isQuietHours());

// Test rate limiting
// Create multiple notifications quickly

// Test push stream
const es = new EventSource('/api/notifications/stream');
es.onmessage = (e) => console.log(JSON.parse(e.data));
```

### Test Actions
```javascript
// Manually trigger notification with actions
const notif = new Notification('Test', {
    body: 'Test notification',
    actions: [
        {action: 'yes', title: 'Yes'},
        {action: 'no', title: 'No'}
    ]
});

notif.onclick = (e) => {
    console.log('Action:', e.action);
};
```

## Performance Tuning

### High-Load Optimization
```python
# Batch notifications together
def batch_notifications(user_id, notifications):
    """Send multiple notifications as one."""
    if len(notifications) > 1:
        combined_message = f"{len(notifications)} new notifications"
        create_notification(user_id, "Updates", combined_message, "info")
    else:
        for notif in notifications:
            create_notification(user_id, notif['title'], notif['message'], notif['type'])
```

### Low-Bandwidth Optimization
```javascript
// Reduce polling frequency
// Change in base.html to 60000 (60 seconds)

// Skip non-critical notifications
if (notificationData.type === 'info') {
    return;  // Skip info notifications to save bandwidth
}
```

### Low-Latency Optimization
```javascript
// Use server-sent events instead of polling
// See "Push Notifications" section above

// Or use WebSockets for real-time delivery
// Requires websocket library (flask-socketio, etc.)
```

---

For more examples, see the source code. All files are well-commented. Feel free to extend based on your needs!
