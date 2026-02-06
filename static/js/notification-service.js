/**
 * Notification Service - Handles Web Push Notifications with Sound
 * Manages browser notifications, sound playback, and permission requests
 */

class NotificationService {
    constructor() {
        this.notificationSound = '/static/sounds/notification.wav';
        this.soundEnabled = localStorage.getItem('soundEnabled') !== 'false'; // Default: enabled
        this.browserNotificationsEnabled = localStorage.getItem('browserNotificationsEnabled') !== 'false'; // Default: enabled
        this.lastNotificationTime = 0;
        this.notificationDebounceMs = 1000; // Prevent duplicate notifications within 1 second
        this.serviceWorkerRegistration = null;
        
        this.init();
    }

    /**
     * Initialize the notification service
     * Register service worker and request permissions
     */
    async init() {
        try {
            // Register service worker for background notifications
            if ('serviceWorker' in navigator) {
                this.serviceWorkerRegistration = await navigator.serviceWorker.register('/static/sw.js', {
                    scope: '/'
                }).catch(error => {
                    console.warn('Service Worker registration failed:', error);
                    // Service worker is optional for the notification system to work
                });
            }

            // Request notification permission on first visit or when not yet determined
            if ('Notification' in window) {
                if (Notification.permission === 'default') {
                    this.requestPermission();
                } else if (Notification.permission === 'granted') {
                    console.log('Notifications already enabled');
                }
            }

            // Load user notification preferences from backend
            await this.loadUserPreferences();
        } catch (error) {
            console.error('Failed to initialize notification service:', error);
        }
    }

    /**
     * Request permission for browser notifications
     * Shows system permission dialog
     */
    async requestPermission() {
        if (!('Notification' in window)) {
            console.warn('Notifications not supported in this browser');
            return false;
        }

        if (Notification.permission === 'granted') {
            console.log('Notification permission already granted');
            return true;
        }

        if (Notification.permission === 'denied') {
            console.log('Notification permission denied by user');
            return false;
        }

        try {
            const permission = await Notification.requestPermission();
            if (permission === 'granted') {
                console.log('Notification permission granted');
                this.browserNotificationsEnabled = true;
                localStorage.setItem('browserNotificationsEnabled', 'true');
                
                // Show a test notification
                this.showTestNotification();
                return true;
            } else {
                this.browserNotificationsEnabled = false;
                localStorage.setItem('browserNotificationsEnabled', 'false');
                return false;
            }
        } catch (error) {
            console.error('Error requesting notification permission:', error);
            return false;
        }
    }

    /**
     * Show a test notification to confirm browser notifications are working
     */
    showTestNotification() {
        if (Notification.permission === 'granted') {
            new Notification('VesselOS', {
                title: 'Notifications Enabled',
                body: 'You will now receive notifications for important updates',
                icon: '/static/images/logo.png',
                badge: '/static/images/logo.png',
                tag: 'test-notification',
                requireInteraction: false
            });
        }
    }

    /**
     * Play notification sound
     * Respects user's device notification settings
     */
    async playSound() {
        if (!this.soundEnabled) {
            return;
        }

        try {
            const audio = new Audio(this.notificationSound);
            audio.volume = 0.7; // 70% volume to respect device settings
            
            // Try to play, catch if user's browser has autoplay restrictions
            const playPromise = audio.play();
            if (playPromise !== undefined) {
                await playPromise;
            }
        } catch (error) {
            console.warn('Could not play notification sound:', error);
            // This is expected on some browsers with autoplay restrictions
        }
    }

    /**
     * Show browser push notification
     * @param {Object} notificationData - Notification data
     * @param {string} notificationData.title - Notification title
     * @param {string} notificationData.body - Notification body/message
     * @param {string} notificationData.type - Notification type (info, success, warning, danger)
     * @param {string} notificationData.icon - Optional icon URL
     * @param {string} notificationData.tag - Optional unique tag to prevent duplicates
     * @param {boolean} notificationData.requireInteraction - Keep notification until user interacts
     */
    async showBrowserNotification(notificationData) {
        // Check if browser notifications are enabled
        if (Notification.permission !== 'granted') {
            console.log('Browser notifications not enabled');
            return false;
        }

        // Debounce: prevent duplicate notifications
        const now = Date.now();
        if (now - this.lastNotificationTime < this.notificationDebounceMs) {
            console.log('Notification debounced (too soon after last one)');
            return false;
        }
        this.lastNotificationTime = now;

        try {
            // Determine notification icon based on type
            const iconMap = {
                'danger': '/static/images/icon-danger.png',
                'warning': '/static/images/icon-warning.png',
                'success': '/static/images/icon-success.png',
                'info': '/static/images/logo.png'
            };

            const options = {
                icon: notificationData.icon || iconMap[notificationData.type] || '/static/images/logo.png',
                badge: '/static/images/logo.png',
                body: notificationData.body || '',
                tag: notificationData.tag || `notification-${Date.now()}`,
                requireInteraction: notificationData.requireInteraction || false,
                timestamp: Date.now(),
                vibrate: [200, 100, 200], // Vibration pattern for devices that support it
                actions: [
                    {
                        action: 'close',
                        title: 'Close'
                    },
                    {
                        action: 'focus',
                        title: 'View'
                    }
                ]
            };

            // Show the notification
            const notification = new Notification(notificationData.title, options);

            // Handle notification click
            notification.onclick = (event) => {
                event.preventDefault();
                window.focus();
                notification.close();
            };

            // Handle notification close
            notification.onclose = () => {
                console.log('Notification closed');
            };

            // Handle notification error
            notification.onerror = (error) => {
                console.error('Notification error:', error);
            };

            return true;
        } catch (error) {
            console.error('Error showing browser notification:', error);
            return false;
        }
    }

    /**
     * Check for new notifications from the server
     * Called periodically to fetch new notifications
     */
    async checkForNewNotifications() {
        try {
            const response = await fetch('/api/notifications');
            const data = await response.json();

            if (data.success && data.notifications && data.notifications.length > 0) {
                // Get the most recent unread notification
                const unreadNotifications = data.notifications.filter(n => !n.is_read);
                
                if (unreadNotifications.length > 0) {
                    const latestNotification = unreadNotifications[0];
                    
                    // Show browser notification
                    this.showBrowserNotification({
                        title: latestNotification.title || 'New Notification',
                        body: latestNotification.message || '',
                        type: latestNotification.type || 'info',
                        tag: `notification-${latestNotification.id}`
                    });

                    // Play sound
                    await this.playSound();
                }
            }
        } catch (error) {
            console.error('Error checking for new notifications:', error);
        }
    }

    /**
     * Toggle sound notifications on/off
     */
    toggleSound(enabled) {
        this.soundEnabled = enabled;
        localStorage.setItem('soundEnabled', enabled ? 'true' : 'false');
        console.log('Sound notifications ' + (enabled ? 'enabled' : 'disabled'));
    }

    /**
     * Toggle browser notifications on/off
     */
    toggleBrowserNotifications(enabled) {
        this.browserNotificationsEnabled = enabled;
        localStorage.setItem('browserNotificationsEnabled', enabled ? 'true' : 'false');
        
        if (enabled && Notification.permission === 'default') {
            this.requestPermission();
        }
        
        console.log('Browser notifications ' + (enabled ? 'enabled' : 'disabled'));
    }

    /**
     * Get current notification settings
     */
    getSettings() {
        return {
            soundEnabled: this.soundEnabled,
            browserNotificationsEnabled: this.browserNotificationsEnabled,
            notificationPermission: Notification.permission
        };
    }

    /**
     * Load user notification preferences from backend
     */
    async loadUserPreferences() {
        try {
            const response = await fetch('/api/user/notification-preferences');
            if (response.ok) {
                const data = await response.json();
                if (data.success && data.preferences) {
                    this.soundEnabled = data.preferences.sound_enabled !== false;
                    this.browserNotificationsEnabled = data.preferences.browser_notifications !== false;
                }
            }
        } catch (error) {
            console.warn('Could not load user preferences:', error);
        }
    }

    /**
     * Save user notification preferences to backend
     */
    async saveUserPreferences() {
        try {
            const response = await fetch('/api/user/notification-preferences', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    sound_enabled: this.soundEnabled,
                    browser_notifications: this.browserNotificationsEnabled
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                return data.success;
            }
        } catch (error) {
            console.error('Error saving preferences:', error);
        }
        return false;
    }
}

// Initialize the notification service globally
const notificationService = new NotificationService();
