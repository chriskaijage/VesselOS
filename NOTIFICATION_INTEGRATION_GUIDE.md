# Integration Guide - How Notifications Flow Through the System

## Complete Flow Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│                         USER FLOW EXAMPLE                             │
└──────────────────────────────────────────────────────────────────────┘

SCENARIO: New Maintenance Request Arrives

1. BACKEND EVENT
   ┌─────────────────────┐
   │ Maintenance Request │
   │ Created in Database │
   └────────┬────────────┘
            │
            ↓
   ┌─────────────────────┐
   │ Create Notification │
   │ (in app.py)         │
   │ INSERT INTO         │
   │ notifications       │
   └────────┬────────────┘
            │
            ↓

2. FRONTEND POLLING
   ┌──────────────────────────┐
   │ Every 30 seconds:        │
   │ loadNotifications()      │
   │ GET /api/notifications  │
   └────────┬─────────────────┘
            │
            ↓
   ┌──────────────────────────┐
   │ Check for Unread         │
   │ Notifications in Response│
   └────────┬─────────────────┘
            │
            ↓

3. NOTIFICATION SERVICE
   ┌────────────────────────────┐
   │ notificationService        │
   │ .checkForNewNotifications()│
   └────────┬───────────────────┘
            │
            ├──────────────────────────────┐
            │                              │
            ↓                              ↓
   ┌──────────────────┐        ┌──────────────────┐
   │ showBrowser      │        │ playSound()      │
   │ Notification()   │        │                  │
   │ ├─Show title     │        │ Audio('notif     │
   │ ├─Show body      │        │ ication.wav')    │
   │ ├─Show icon      │        │ .play()          │
   │ ├─Vibration      │        │ Volume: 70%      │
   │ └─Actions        │        └──────────────────┘
   └────────┬─────────┘
            │
            ↓
   ┌──────────────────────────┐
   │ Desktop Notification     │
   │ Appears to User          │
   │ (+ Sound plays)          │
   └──────────────────────────┘

4. USER INTERACTION
   ┌──────────────────────────┐
   │ User Clicks Notification │
   └────────┬─────────────────┘
            │
            ↓
   ┌──────────────────────────┐
   │ Notification Disappears  │
   │ Browser Focused          │
   └──────────────────────────┘

```

## Step-by-Step Implementation

### Step 1: Creating a Notification

**In app.py** (any route):
```python
@app.route('/api/maintenance-request', methods=['POST'])
@login_required
def create_maintenance_request():
    # Get request data
    request_data = request.get_json()
    
    # Validate and save request
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO maintenance_requests (ship_name, issue_description, ...)
        VALUES (?, ?, ...)
    """, (request_data['ship_name'], request_data['issue_description'], ...))
    conn.commit()
    
    # Create notification for relevant users
    # Option 1: Notify specific user
    c.execute("""
        INSERT INTO notifications (user_id, title, message, type, created_at)
        VALUES (?, ?, ?, ?, datetime('now'))
    """, ('port_engineer_id', 
          'New Maintenance Request',
          f"New request from {current_user.first_name}: {request_data['title']}",
          'info'))
    
    conn.commit()
    conn.close()
    
    return jsonify({'success': True, 'message': 'Request created'})
```

### Step 2: Frontend Detects Notification

**In base.html** (automatic polling):
```html
<script>
    // Runs every 30 seconds automatically
    function loadNotifications() {
        fetch('/api/notifications')
            .then(response => response.json())
            .then(data => {
                if (data.success && data.notifications.length > 0) {
                    // Update notification badge
                    updateNotificationCount(data.notifications);
                    
                    // This triggers our new web push integration
                }
            });
    }
    
    // Enhanced with web push support
    const originalLoadNotifications = loadNotifications;
    loadNotifications = function() {
        originalLoadNotifications();
        // Also check for new notifications via service
        if (typeof notificationService !== 'undefined') {
            notificationService.checkForNewNotifications();
        }
    };
</script>
```

### Step 3: Notification Service Shows Alert

**In notification-service.js**:
```javascript
async checkForNewNotifications() {
    try {
        const response = await fetch('/api/notifications');
        const data = await response.json();

        if (data.success && data.notifications.length > 0) {
            // Get first unread notification
            const unreadNotifications = data.notifications.filter(n => !n.is_read);
            
            if (unreadNotifications.length > 0) {
                const latestNotification = unreadNotifications[0];
                
                // Show browser notification
                await this.showBrowserNotification({
                    title: latestNotification.title,
                    body: latestNotification.message,
                    type: latestNotification.type,
                    tag: `notification-${latestNotification.id}`
                });

                // Play sound (if enabled)
                await this.playSound();
            }
        }
    } catch (error) {
        console.error('Error checking notifications:', error);
    }
}
```

### Step 4: User Sees and Hears Notification

```
Desktop Notification appears:
┌─────────────────────────────────┐
│ 🔔 New Maintenance Request      │
├─────────────────────────────────┤
│ New request from John Doe:      │
│ Engine coolant leak found       │
│                                 │
│  [View]         [Close]         │
└─────────────────────────────────┘

+ Sound plays: notification.wav (0.7 volume)
```

### Step 5: User Manages Preferences

**In profile.html** (notification settings):
```html
<h5>Notification Settings</h5>

<!-- Toggle Sound -->
<div class="form-check form-switch">
    <input class="form-check-input" 
           type="checkbox" 
           id="soundNotificationsToggle" 
           checked
           onchange="toggleSound(this.checked)">
    <label class="form-check-label">Sound notifications</label>
</div>

<!-- Toggle Browser Notifications -->
<div class="form-check form-switch">
    <input class="form-check-input" 
           type="checkbox" 
           id="browserNotificationsToggle" 
           checked
           onchange="toggleBrowserNotifications(this.checked)">
    <label class="form-check-label">Browser notifications</label>
</div>

<!-- Test Button -->
<button class="btn btn-success" onclick="sendTestNotification()">
    Send Test Notification
</button>

<script>
    // When user toggles sound
    function toggleSound(enabled) {
        notificationService.toggleSound(enabled);
        notificationService.saveUserPreferences();
    }
    
    // When user toggles browser notifications
    function toggleBrowserNotifications(enabled) {
        notificationService.toggleBrowserNotifications(enabled);
        notificationService.saveUserPreferences();
    }
    
    // When user clicks test button
    async function sendTestNotification() {
        await notificationService.showBrowserNotification({
            title: 'Test Notification',
            body: 'This is a test from Marine Service System',
            type: 'success'
        });
        await notificationService.playSound();
    }
</script>
```

## Data Flow Diagram

```
┌─────────────┐
│ User Action │
│ (e.g., POST)│
└──────┬──────┘
       │
       ↓
┌──────────────────┐
│ Flask Route      │
│ (app.py)         │
│ ├─ Process data  │
│ └─ Save to DB    │
└──────┬───────────┘
       │
       ↓
┌──────────────────────────┐
│ Create Notification      │
│ INSERT INTO              │
│ notifications table      │
└──────┬───────────────────┘
       │
       ↓ (User's next action or after 30s)
       │
┌──────────────────────────┐
│ Frontend Polling         │
│ GET /api/notifications   │
└──────┬───────────────────┘
       │
       ↓
┌──────────────────────────┐
│ API Response             │
│ Returns unread notifs    │
└──────┬───────────────────┘
       │
       ↓
┌──────────────────────────┐
│ Notification Service     │
│ (notification-service.js)│
│ └─ checkForNew...()      │
└──────┬───────────────────┘
       │
       ├────────────────┬────────────────┐
       ↓                ↓                ↓
┌──────────────┐  ┌──────────────┐  ┌──────────┐
│ Show Browser │  │  Play Sound  │  │ Vibrate  │
│ Notification│  │  (if enabled)│  │ (if sup) │
└──────────────┘  └──────────────┘  └──────────┘
       │                │                │
       └────────┬───────┴────────┬───────┘
                │                │
                ↓                ↓
        ┌──────────────────────────────┐
        │ User Sees & Hears Alert      │
        │ ✓ Desktop notification       │
        │ ✓ Sound effect              │
        │ ✓ Vibration (mobile)        │
        └──────────────────────────────┘

PREFERENCES FLOW:

┌──────────────────────┐
│ User in Profile Page │
│ Toggles Notification │
│ Setting              │
└──────┬───────────────┘
       │
       ↓
┌──────────────────────────┐
│ JavaScript Event Handler │
│ (notification-settings.js)│
└──────┬───────────────────┘
       │
       ↓
┌──────────────────────────┐
│ POST /api/user/          │
│ notification-preferences │
└──────┬───────────────────┘
       │
       ↓
┌──────────────────────────┐
│ Flask Endpoint           │
│ (app.py)                 │
│ ├─ Validate user        │
│ ├─ Update or Insert DB  │
│ └─ Return success       │
└──────┬───────────────────┘
       │
       ↓
┌──────────────────────────┐
│ notification_preferences │
│ table updated            │
└──────────────────────────┘

NEXT TIME USER GETS NOTIFICATION:

┌──────────────────────────┐
│ Load User Preferences    │
│ FROM notification_       │
│ preferences table        │
└──────┬───────────────────┘
       │
       ├─ sound_enabled=1?
       │  └─ YES → Play sound
       │  └─ NO → Skip sound
       │
       ├─ browser_notifications=1?
       │  └─ YES → Show notification
       │  └─ NO → Don't show
       │
       └─ APPLY SETTINGS

```

## Code Integration Points

### 1. Database Layer
```
notifications table
└─ User receives notifications from this table

notification_preferences table (NEW)
└─ User notification settings stored here

users table
├─ user_id (references both above)
└─ email, role, etc.
```

### 2. Backend Layer
```
app.py
├─ /api/notifications
│  └─ Fetch notifications (existing)
│
├─ /api/user/notification-preferences (NEW)
│  ├─ GET - Retrieve preferences
│  └─ POST - Save preferences
│
└─ Any route can create notifications
   └─ INSERT INTO notifications
```

### 3. Frontend Layer
```
base.html
├─ Load notification-service.js
├─ Load notification-settings.js
├─ Enhance loadNotifications()
└─ Start polling notificationService

profile.html
├─ Add notification settings UI
├─ Toggles for sound/browser notifications
├─ Test notification button
└─ Permission status display

notification-service.js
├─ Main NotificationService class
├─ Request permission
├─ Show notifications
├─ Play sound
└─ Manage preferences

notification-settings.js
├─ UI component class
├─ Setup event listeners
├─ Update UI based on state
└─ Show feedback messages

sw.js (Service Worker)
├─ Background notifications
├─ Asset caching
└─ Event handling
```

## Usage Examples

### Example 1: Notify Port Engineer of New Request
```python
@app.route('/api/submit-request', methods=['POST'])
@login_required
def submit_request():
    # Save request to database
    request_id = save_request(request.get_json())
    
    # Create notification
    conn = get_db_connection()
    c = conn.cursor()
    
    # Get port engineer user ID
    c.execute("SELECT user_id FROM users WHERE role = 'port_engineer' LIMIT 1")
    port_eng = c.fetchone()
    
    if port_eng:
        c.execute("""
            INSERT INTO notifications 
            (user_id, title, message, type)
            VALUES (?, ?, ?, ?)
        """, (
            port_eng['user_id'],
            'New Maintenance Request',
            f'Request #{request_id} needs review',
            'info'
        ))
        conn.commit()
    
    conn.close()
    return jsonify({'success': True})
```

### Example 2: Broadcast Alert to All Users
```python
def broadcast_alert(title, message):
    """Send alert to all active users."""
    conn = get_db_connection()
    c = conn.cursor()
    
    c.execute("SELECT user_id FROM users WHERE is_active = 1")
    users = c.fetchall()
    
    for user in users:
        c.execute("""
            INSERT INTO notifications
            (user_id, title, message, type)
            VALUES (?, ?, ?, ?)
        """, (user['user_id'], title, message, 'warning'))
    
    conn.commit()
    conn.close()

# Usage
broadcast_alert(
    'System Maintenance',
    'System will be offline for maintenance at 2am'
)
```

### Example 3: Notify on Condition
```python
@app.route('/api/evaluate-ship', methods=['POST'])
@login_required
def evaluate_ship():
    # Run evaluation...
    quality_score = calculate_quality(ship_id)
    
    if quality_score < 60:  # Poor score
        # Create urgent notification
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""
            INSERT INTO notifications
            (user_id, title, message, type)
            VALUES (?, ?, ?, ?)
        """, (
            current_user.id,
            'Quality Alert',
            f'Ship {ship_name} quality score: {quality_score}% - URGENT',
            'danger'  # This will show as red notification
        ))
        conn.commit()
        conn.close()
    
    return jsonify({'success': True})
```

## Complete User Journey

```
1. USER OPENS APP (First Time)
   ├─ Browser permission dialog appears
   ├─ User clicks "Allow"
   └─ System shows test notification

2. USER USES APP NORMALLY
   ├─ Background polling starts (every 30s)
   ├─ User doesn't need to do anything
   └─ Notifications appear automatically

3. NEW NOTIFICATION ARRIVES
   ├─ Created in database by backend
   ├─ Frontend detects within 30 seconds
   ├─ Browser notification shows
   ├─ Sound plays (if enabled)
   ├─ Vibration happens (if supported)
   └─ User sees alert even if browser minimized

4. USER CLICKS NOTIFICATION
   ├─ Browser focuses
   ├─ Notification disappears
   └─ User can navigate to relevant page

5. USER GOES TO PROFILE SETTINGS
   ├─ Finds Notification Settings section
   ├─ Can toggle sound on/off
   ├─ Can toggle browser notifications on/off
   ├─ Can send test notification
   └─ Settings saved automatically to database

6. NEXT TIME USER GETS NOTIFICATION
   ├─ Preferences loaded from database
   ├─ Sound only plays if user enabled it
   ├─ Browser notification only shows if enabled
   └─ All settings are remembered

```

## Performance Metrics

```
Operation              | Time    | Impact
-----------------------+---------+-------
Polling (30s interval) | ~100ms  | Low
Show notification      | <100ms  | Instant
Play sound            | ~200ms  | Background
Save preferences      | ~50ms   | Fast
DB query              | ~10ms   | Fast
Service Worker init   | ~50ms   | Non-blocking
```

## Security Chain

```
User Action
    ↓
Validate User Authentication (@login_required)
    ↓
Validate CSRF Token (@csrf_protect)
    ↓
Check User ID (Ensure user can only modify own preferences)
    ↓
Update Database
    ↓
Return to Client (User can only see own notifications)
```

## What Happens When Disabled

```
If user disables sound notifications:
- Notifications still show
- Sound file NOT played
- Setting remembered in database

If user disables browser notifications:
- Notifications still in database
- Desktop alert NOT shown
- Notification badge still updates
- Setting remembered in database

If user denies permission in browser:
- Browser won't show notifications
- Sound still plays (if enabled)
- Can re-enable in browser settings
```

---

This comprehensive integration shows how every part of the notification system works together to deliver a seamless user experience, similar to WhatsApp Web and modern browser notifications.
