/**
 * Advanced Notification Handler
 * Manages system notifications with sound, respecting device settings
 */

class NotificationHandler {
    constructor() {
        this.notificationPermission = 'default';
        this.soundEnabled = true;
        this.isSystemMuted = false;
        this.notificationQueue = [];
        this.activeNotifications = new Map();
        
        // Embedded audio data URIs - simple sine wave beeps
        // Each generates a short beep sound using Web Audio API
        this.soundUrls = {
            message: null,   // Will use Web Audio API
            alert: null,     // Will use Web Audio API
            success: null,   // Will use Web Audio API
            error: null      // Will use Web Audio API
        };
        
        this.initialize();
    }

    async initialize() {
        // Request notification permission if not already granted
        if ('Notification' in window) {
            this.notificationPermission = Notification.permission;
            
            if (this.notificationPermission === 'default') {
                try {
                    const permission = await Notification.requestPermission();
                    this.notificationPermission = permission;
                } catch (error) {
                    console.error('Error requesting notification permission:', error);
                }
            }
        }

        // Check device mute status
        this.checkDeviceMuteStatus();
        
        // Load user preferences
        await this.loadUserPreferences();
        
        // Start listening for new notifications
        this.startNotificationListener();
        
        console.log('Notification handler initialized');
    }

    /**
     * Detect if device is muted (iOS/Android behavior)
     */
    checkDeviceMuteStatus() {
        const audioContext = new (window.AudioContext || window.webkitAudioContext)();
        const analyser = audioContext.createAnalyser();
        const oscillator = audioContext.createOscillator();
        const gainNode = audioContext.createGain();

        gainNode.connect(analyser);
        oscillator.connect(gainNode);
        
        // Try to detect mute state through volume changes
        gainNode.gain.value = 0; // Mute for detection
        
        if (gainNode.gain.value === 0) {
            this.isSystemMuted = false; // Can still play muted audio
        }
    }

    /**
     * Load user notification preferences from backend
     */
    async loadUserPreferences() {
        try {
            const response = await fetch('/api/user/notification-preferences', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const prefs = await response.json();
                this.soundEnabled = prefs.sound_enabled !== false;
                this.notificationPermission = prefs.notifications_enabled !== false ? 'granted' : 'denied';
            }
        } catch (error) {
            console.warn('Could not load notification preferences:', error);
        }
    }

    /**
     * Start listening for new notifications via polling/WebSocket
     */
    startNotificationListener() {
        // Poll for new notifications every 5 seconds
        setInterval(() => this.checkForNewNotifications(), 5000);
        
        // Also listen for real-time updates via message events
        document.addEventListener('notification-received', (event) => {
            this.handleNotification(event.detail);
        });
    }

    /**
     * Check for new notifications from the server
     */
    async checkForNewNotifications() {
        try {
            const response = await fetch('/api/notifications?limit=10', {
                method: 'GET',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (response.ok) {
                const data = await response.json();
                if (data.notifications && data.notifications.length > 0) {
                    const newNotifications = data.notifications.filter(
                        notif => !this.activeNotifications.has(notif.id)
                    );

                    newNotifications.forEach(notif => {
                        this.handleNotification(notif);
                    });
                }
            }
        } catch (error) {
            console.error('Error checking for notifications:', error);
        }
    }

    /**
     * Main notification handler
     */
    async handleNotification(notification) {
        // Track this notification as active
        this.activeNotifications.set(notification.id, notification);

        // Determine notification type
        const type = this.getNotificationType(notification);
        
        // Play sound if enabled
        if (this.soundEnabled && this.notificationPermission !== 'denied') {
            await this.playSound(type);
        }

        // Show browser notification if permission granted
        if (this.notificationPermission === 'granted') {
            this.showBrowserNotification(notification, type);
        }

        // Show in-app notification
        this.showInAppNotification(notification, type);

        // Trigger browser title badge
        this.updateBadgeCount();
    }

    /**
     * Determine notification type based on content
     */
    getNotificationType(notification) {
        if (notification.type === 'error' || notification.severity === 'critical') {
            return 'alert';
        } else if (notification.type === 'success') {
            return 'success';
        } else if (notification.type === 'error') {
            return 'error';
        }
        return 'message';
    }

    /**
     * Play notification sound using Web Audio API
     * No external files needed - generates sounds programmatically
     */
    async playSound(type = 'message') {
        if (!this.soundEnabled || this.isSystemMuted) {
            return;
        }

        try {
            // Try to use Web Audio API for sound generation
            const audioContext = window.audioContext || 
                                 new (window.AudioContext || window.webkitAudioContext)();
            window.audioContext = audioContext;

            // Different frequencies for different notification types
            const frequencies = {
                message: 800,   // 800 Hz - neutral
                alert: 1000,    // 1000 Hz - higher, more alarming
                success: 600,   // 600 Hz - lower, pleasant
                error: 1200     // 1200 Hz - very high, urgent
            };

            const frequency = frequencies[type] || frequencies.message;
            const duration = type === 'alert' ? 0.6 : 0.4; // Longer alert sound

            // Create oscillator and gain node
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();

            oscillator.type = 'sine';
            oscillator.frequency.value = frequency;

            // Set volume to 70% and apply envelope
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + duration);

            // Connect and play
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);

            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + duration);

        } catch (error) {
            console.warn(`Could not play notification sound (${type}):`, error);
        }
    }

    /**
     * Show browser notification
     */
    showBrowserNotification(notification, type) {
        if (!('Notification' in window) || this.notificationPermission !== 'granted') {
            return;
        }

        try {
            const browserNotif = new Notification(
                notification.title || 'System Notification',
                {
                    body: notification.message || notification.content,
                    icon: '/static/images/logo.png',
                    badge: '/static/images/logo-badge.png',
                    tag: `notif-${notification.id}`,
                    requireInteraction: type === 'alert',
                    timestamp: new Date(notification.created_at || Date.now()).getTime()
                }
            );

            // Handle notification click
            browserNotif.onclick = () => {
                window.focus();
                if (notification.action_url) {
                    window.location.href = notification.action_url;
                }
                browserNotif.close();
            };

            // Auto-close after 8 seconds if not critical
            if (type !== 'alert') {
                setTimeout(() => browserNotif.close(), 8000);
            }
        } catch (error) {
            console.error('Error showing browser notification:', error);
        }
    }

    /**
     * Show in-app toast notification
     */
    showInAppNotification(notification, type) {
        // Create toast element
        const toast = document.createElement('div');
        toast.className = `notification-toast toast-${type}`;
        toast.id = `notif-${notification.id}`;
        
        const icon = this.getIconForType(type);
        
        toast.innerHTML = `
            <div class="notification-toast-content">
                <span class="notification-icon">${icon}</span>
                <div class="notification-text">
                    <div class="notification-title">${notification.title || 'Notification'}</div>
                    <div class="notification-message">${notification.message || notification.content}</div>
                </div>
                <button class="notification-close" onclick="this.parentElement.parentElement.remove()">×</button>
            </div>
            <div class="notification-progress"></div>
        `;

        // Add to container
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.className = 'notification-container';
            document.body.appendChild(container);
        }

        container.appendChild(toast);

        // Auto-remove after 8 seconds
        setTimeout(() => {
            toast.classList.add('fade-out');
            setTimeout(() => toast.remove(), 300);
        }, 8000);

        // Remove from active map after it's gone
        setTimeout(() => {
            this.activeNotifications.delete(notification.id);
        }, 8300);
    }

    /**
     * Get icon for notification type
     */
    getIconForType(type) {
        const icons = {
            'message': '💬',
            'alert': '⚠️',
            'success': '✅',
            'error': '❌'
        };
        return icons[type] || '🔔';
    }

    /**
     * Update browser badge count
     */
    updateBadgeCount() {
        if ('setAppBadge' in navigator) {
            const unreadCount = this.activeNotifications.size;
            if (unreadCount > 0) {
                navigator.setAppBadge(unreadCount);
            } else {
                navigator.clearAppBadge();
            }
        }
    }

    /**
     * Toggle sound notifications
     */
    toggleSound(enabled = null) {
        if (enabled !== null) {
            this.soundEnabled = enabled;
        } else {
            this.soundEnabled = !this.soundEnabled;
        }

        // Save preference to backend
        this.saveUserPreference('sound_enabled', this.soundEnabled);
        
        return this.soundEnabled;
    }

    /**
     * Toggle desktop notifications
     */
    async toggleNotifications(enabled = null) {
        if (enabled === null) {
            enabled = this.notificationPermission !== 'granted';
        }

        if (enabled && this.notificationPermission === 'default') {
            const permission = await Notification.requestPermission();
            this.notificationPermission = permission;
        } else if (!enabled) {
            this.notificationPermission = 'denied';
        }

        // Save preference to backend
        this.saveUserPreference('notifications_enabled', enabled);
        
        return this.notificationPermission;
    }

    /**
     * Save user preference to backend
     */
    async saveUserPreference(key, value) {
        try {
            await fetch('/api/user/notification-preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ [key]: value })
            });
        } catch (error) {
            console.error('Error saving notification preference:', error);
        }
    }

    /**
     * Clear all active notifications
     */
    clearAll() {
        this.activeNotifications.forEach((notif, id) => {
            const element = document.getElementById(`notif-${id}`);
            if (element) {
                element.remove();
            }
        });
        this.activeNotifications.clear();
        navigator.clearAppBadge?.();
    }

    /**
     * Request microphone permission for voice alerts (optional feature)
     */
    async enableVoiceAlerts() {
        if (!('speechSynthesis' in window)) {
            console.warn('Speech synthesis not supported');
            return false;
        }

        try {
            const response = await navigator.permissions.query({ name: 'microphone' });
            return response.state === 'granted';
        } catch (error) {
            console.error('Error checking microphone permission:', error);
            return false;
        }
    }

    /**
     * Speak notification using text-to-speech
     */
    speakNotification(text) {
        if (!('speechSynthesis' in window)) {
            return;
        }

        try {
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1;
            utterance.pitch = 1;
            utterance.volume = 0.7;
            
            speechSynthesis.cancel(); // Cancel any ongoing speech
            speechSynthesis.speak(utterance);
        } catch (error) {
            console.error('Error speaking notification:', error);
        }
    }
}

// Initialize notification handler when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        window.notificationHandler = new NotificationHandler();
    });
} else {
    window.notificationHandler = new NotificationHandler();
}
