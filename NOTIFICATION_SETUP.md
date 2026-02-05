# Notification System - Complete Technical Setup

## Overview

This document provides complete technical details for the web push notification system implementation.

## Architecture

### Core Components

1. **NotificationService** (JavaScript class)
   - Handles all notification logic
   - Manages browser permissions
   - Plays sounds
   - Polls for new notifications
   - Saves preferences to backend

2. **NotificationSettingsUI** (JavaScript class)
   - UI component for user settings
   - Manages toggle switches
   - Shows permission status
   - Sends test notifications

3. **Service Worker (sw.js)**
   - Registers automatically
   - Handles background notifications
   - Caches assets
   - Non-blocking initialization

4. **Backend API** (Flask)
   - `/api/user/notification-preferences` - GET/POST
   - Validates user identity
   - CSRF protected
   - Saves to database

5. **Database**
   - `notifications` table - existing
   - `notification_preferences` table - new

## Files

### notification-service.js

Main notification service class. Key methods:

```javascript
class NotificationService {
    // Initialize service and register service worker
    async init()
    
    // Request browser notification permission
    async requestPermission()
    
    // Show test notification
    showTestNotification()
    
    // Play notification sound
    async playSound()
    
    // Show desktop notification
    async showBrowserNotification(notificationData)
    
    // Poll for new notifications from server
    async checkForNewNotifications()
    
    // Toggle sound on/off
    toggleSound(enabled)
    
    // Toggle browser notifications on/off
    toggleBrowserNotifications(enabled)
    
    // Get current settings
    getSettings()
    
    // Load preferences from backend
    async loadUserPreferences()
    
    // Save preferences to backend
    async saveUserPreferences()
}
```

### notification-settings.js

UI component for settings page. Key methods:

```javascript
class NotificationSettingsUI {
    // Initialize event listeners
    init()
    
    // Setup all event handlers
    setupEventListeners()
    
    // Update UI based on current state
    updateUIState()
    
    // Send test notification
    async sendTestNotification()
    
    // Show feedback message
    showAlert(type, message, duration)
}
```

### sw.js (Service Worker)

```javascript
// Install event - cache resources
addEventListener('install', (event) => { ... })

// Activate event - clean up old caches
addEventListener('activate', (event) => { ... })

// Push notification from server
addEventListener('push', (event) => { ... })

// User clicks notification
addEventListener('notificationclick', (event) => { ... })

// User closes notification
addEventListener('notificationclose', (event) => { ... })

// Fetch event - serve from cache, fallback to network
addEventListener('fetch', (event) => { ... })

// Periodic background sync
addEventListener('periodicsync', (event) => { ... })
```

## Database Schema

### notifications table (existing)
```sql
CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    title TEXT NOT NULL,
    message TEXT NOT NULL,
    type TEXT DEFAULT 'info',
    action_url TEXT,
    is_read INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
```

### notification_preferences table (new)
```sql
CREATE TABLE notification_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL UNIQUE,
    sound_enabled INTEGER DEFAULT 1,
    browser_notifications INTEGER DEFAULT 1,
    email_notifications INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users (user_id)
)
```

## API Endpoints

### GET /api/user/notification-preferences

Get user's notification preferences.

**Request:**
```http
GET /api/user/notification-preferences
Authorization: Bearer <user_token>
```

**Response (200 OK):**
```json
{
    "success": true,
    "preferences": {
        "sound_enabled": true,
        "browser_notifications": true,
        "email_notifications": true
    }
}
```

**Response (default if not found):**
```json
{
    "success": true,
    "preferences": {
        "sound_enabled": true,
        "browser_notifications": true,
        "email_notifications": true
    }
}
```

### POST /api/user/notification-preferences

Save user's notification preferences.

**Request:**
```http
POST /api/user/notification-preferences
Content-Type: application/json
Authorization: Bearer <user_token>

{
    "sound_enabled": true,
    "browser_notifications": true,
    "email_notifications": true
}
```

**Response (200 OK):**
```json
{
    "success": true,
    "message": "Notification preferences saved successfully"
}
```

**Response (400 Bad Request):**
```json
{
    "success": false,
    "error": "Error message"
}
```

## Implementation Details

### Permission Request Flow

```
Page Load
    ↓
NotificationService.init()
    ↓
Check if 'serviceWorker' in navigator
    ↓
Register sw.js
    ↓
Check Notification.permission
    ├─ 'granted' → Skip request
    ├─ 'denied' → User previously denied
    └─ 'default' → Show request dialog
    ↓
Notification.requestPermission()
    ↓
User clicks Allow/Deny
    ↓
Store preference in localStorage
    ↓
Load from backend
```

### Notification Display Flow

```
Backend Creates Notification
    ↓
INSERT INTO notifications table
    ↓
Frontend Polling (every 30 seconds)
    ↓
GET /api/notifications
    ↓
Check for unread notifications
    ↓
NotificationService.checkForNewNotifications()
    ↓
Get user preferences
    ├─ Sound enabled? → playSound()
    └─ Browser notif enabled? → showBrowserNotification()
    ↓
Desktop Notification Appears
    ↓
User clicks or closes
```

### Settings Save Flow

```
User toggles setting in Profile
    ↓
JavaScript event handler fires
    ↓
notificationService.toggleSound/toggleBrowserNotifications()
    ↓
notificationService.saveUserPreferences()
    ↓
POST /api/user/notification-preferences
    ↓
Validate user with @login_required
    ↓
Validate CSRF token with @csrf_protect
    ↓
Check if preference exists
    ├─ Yes → UPDATE
    └─ No → INSERT
    ↓
Save to notification_preferences table
    ↓
Return success to frontend
    ↓
Show success message
```

## Configuration

### Polling Interval
**File:** `templates/base.html`
**Line:** ~5625 (search for "setInterval")
**Default:** 30000ms (30 seconds)

### Notification Sound
**File:** `static/js/notification-service.js`
**Line:** ~8 (in constructor)
**Current:** `/static/sounds/notification.wav`

### Sound Volume
**File:** `static/js/notification-service.js`
**Line:** ~165 (in playSound method)
**Current:** 0.7 (70%)

### Debounce Duration
**File:** `static/js/notification-service.js`
**Line:** ~13 (in constructor)
**Current:** 1000ms (1 second)

## Security

### CSRF Protection
```python
@csrf_protect  # Decorator on POST endpoints
```
Validates token from request.form or request.headers

### User Isolation
```python
@login_required  # User must be authenticated
WHERE user_id = ?  # Only fetch own preferences
```

### Permission Scoping
- Browser handles permission at system level
- No cross-origin requests
- Limited to same origin scope

### Data Validation
```python
# Validate boolean values
sound_enabled = data.get('sound_enabled', True)
browser_notifications = data.get('browser_notifications', True)
```

## Performance Optimization

### Polling
- **Frequency:** Every 30 seconds (configurable)
- **Impact:** ~100ms per request
- **Optimization:** Only checks unread notifications

### Debouncing
- **Duration:** 1 second between notifications
- **Purpose:** Prevent duplicate notifications
- **Implementation:** Track lastNotificationTime

### Service Worker
- **Startup:** Non-blocking
- **Caching:** Only essential assets
- **Fallback:** Works without Service Worker

### Database
- **Query:** Limited to 20 most recent
- **Index:** On (user_id, is_read) recommended
- **Load:** Minimal (simple SELECT)

## Browser Compatibility

### Notification API
- Chrome 22+
- Firefox 4+
- Safari 6+
- Edge 14+

### Service Workers
- Chrome 40+
- Firefox 44+
- Safari 11.1+
- Edge 17+

### Audio API
- Chrome 14+
- Firefox 25+
- Safari 6+
- Edge 12+

### Storage API
- All modern browsers

## Error Handling

### Service Worker Registration
```javascript
navigator.serviceWorker.register('/static/sw.js')
    .catch(error => {
        console.warn('Service Worker registration failed:', error);
        // Continue without Service Worker (fallback)
    });
```

### Notification Permission
```javascript
Notification.requestPermission()
    .then(permission => {
        if (permission === 'granted') {
            // Proceed
        }
    })
    .catch(error => {
        console.error('Permission request failed:', error);
    });
```

### Sound Playback
```javascript
audio.play()
    .catch(error => {
        console.warn('Audio playback failed:', error);
        // Continue without sound
    });
```

## Testing

### Unit Tests
```javascript
// Test permission request
notificationService.requestPermission()
    .then(granted => {
        assert(granted === true);
    });

// Test sound playback
notificationService.playSound()
    .then(() => {
        console.log('Sound played successfully');
    });

// Test settings toggle
notificationService.toggleSound(false);
assert(notificationService.soundEnabled === false);
```

### Integration Tests
```python
# Test API endpoint
response = client.get('/api/user/notification-preferences')
assert response.status_code == 200
assert 'preferences' in response.json

# Test preference save
response = client.post('/api/user/notification-preferences', 
    json={'sound_enabled': False})
assert response.json['success'] == True
```

### End-to-End Tests
```javascript
// User flow
1. Open app
2. Receive permission request
3. Grant permission
4. Get test notification
5. Hear sound
6. Open profile settings
7. Toggle sound off
8. Verify setting saved
9. Reload page
10. Verify setting persists
```

## Deployment Checklist

- [ ] Verify `/static/sounds/notification.wav` exists
- [ ] Run database initialization (`init_db()`)
- [ ] Test permission request on first visit
- [ ] Test notification sound on desktop
- [ ] Test settings save/load
- [ ] Test with browser minimized
- [ ] Check Service Worker in DevTools
- [ ] Verify no console errors
- [ ] Test across browsers (Chrome, Firefox, Safari, Edge)
- [ ] Test on mobile browsers

## Troubleshooting Guide

### Notifications not showing
1. Check browser console for errors
2. Verify Notification.permission === 'granted'
3. Check Service Worker registration status
4. Try hard refresh (Ctrl+Shift+R)
5. Check browser settings for this site

### Sound not playing
1. Verify file exists: `/static/sounds/notification.wav`
2. Check audio volume is not muted
3. Check browser audio permission
4. Check audiocontext permission
5. Test audio: `new Audio('/static/sounds/notification.wav').play()`

### Settings not saving
1. Check browser console for errors
2. Verify CSRF token in request
3. Check database connectivity
4. Verify `notification_preferences` table exists
5. Check user is authenticated

### Service Worker issues
1. Not critical - system works without it
2. Check DevTools → Application → Service Workers
3. Try unregistering and re-registering
4. Check for JavaScript errors in sw.js
5. Hard refresh to clear cache

---

This is a complete technical reference for the notification system. For quick start, see NOTIFICATION_QUICK_START.md.
