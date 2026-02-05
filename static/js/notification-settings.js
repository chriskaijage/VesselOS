/**
 * Notification Settings UI Component
 * Handles the UI for notification preferences
 */

class NotificationSettingsUI {
    constructor() {
        this.initialized = false;
    }

    /**
     * Initialize notification settings UI
     * Should be called when the settings component is loaded
     */
    init() {
        this.setupEventListeners();
        this.updateUIState();
        this.initialized = true;
    }

    /**
     * Setup event listeners for notification settings
     */
    setupEventListeners() {
        // Sound toggle
        const soundToggle = document.getElementById('soundNotificationsToggle');
        if (soundToggle) {
            soundToggle.addEventListener('change', (e) => {
                const enabled = e.target.checked;
                notificationService.toggleSound(enabled);
                notificationService.saveUserPreferences();
                this.showSettingsSaved();
            });
        }

        // Browser notifications toggle
        const browserToggle = document.getElementById('browserNotificationsToggle');
        if (browserToggle) {
            browserToggle.addEventListener('change', async (e) => {
                const enabled = e.target.checked;
                if (enabled) {
                    const permission = await notificationService.requestPermission();
                    if (!permission) {
                        e.target.checked = false;
                        this.showPermissionDenied();
                    }
                } else {
                    notificationService.toggleBrowserNotifications(false);
                }
                notificationService.saveUserPreferences();
                this.updateUIState();
                this.showSettingsSaved();
            });
        }

        // Test notification button
        const testButton = document.getElementById('testNotificationBtn');
        if (testButton) {
            testButton.addEventListener('click', async () => {
                await this.sendTestNotification();
            });
        }

        // Request permission button
        const requestPermBtn = document.getElementById('requestNotificationPermBtn');
        if (requestPermBtn) {
            requestPermBtn.addEventListener('click', async () => {
                const success = await notificationService.requestPermission();
                if (success) {
                    this.updateUIState();
                    this.showPermissionGranted();
                } else {
                    this.showPermissionDenied();
                }
            });
        }
    }

    /**
     * Update UI state based on current settings
     */
    updateUIState() {
        const soundToggle = document.getElementById('soundNotificationsToggle');
        const browserToggle = document.getElementById('browserNotificationsToggle');
        const permissionStatus = document.getElementById('notificationPermissionStatus');
        const requestPermBtn = document.getElementById('requestNotificationPermBtn');

        const settings = notificationService.getSettings();

        // Update toggles
        if (soundToggle) {
            soundToggle.checked = settings.soundEnabled;
        }

        if (browserToggle) {
            browserToggle.checked = settings.browserNotificationsEnabled;
        }

        // Update permission status
        if (permissionStatus) {
            const statusMap = {
                'granted': { class: 'success', icon: 'check-circle', text: 'Enabled' },
                'denied': { class: 'danger', icon: 'times-circle', text: 'Blocked' },
                'default': { class: 'warning', icon: 'question-circle', text: 'Not Requested' }
            };

            const status = statusMap[settings.notificationPermission];
            permissionStatus.innerHTML = `
                <i class="fas fa-${status.icon} text-${status.class}"></i>
                <span class="ms-2">Permission: <strong class="text-${status.class}">${status.text}</strong></span>
            `;
        }

        // Show/hide request permission button
        if (requestPermBtn) {
            if (settings.notificationPermission === 'default') {
                requestPermBtn.style.display = 'block';
            } else {
                requestPermBtn.style.display = 'none';
            }
        }
    }

    /**
     * Send a test notification
     */
    async sendTestNotification() {
        const testBtn = document.getElementById('testNotificationBtn');
        if (testBtn) {
            testBtn.disabled = true;
            testBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Sending...';
        }

        try {
            // Show browser notification
            await notificationService.showBrowserNotification({
                title: 'Test Notification',
                body: 'This is a test notification from the Marine Service System',
                type: 'success'
            });

            // Play sound
            await notificationService.playSound();

            this.showAlert('success', 'Test notification sent! Check your browser notifications.');
        } catch (error) {
            console.error('Error sending test notification:', error);
            this.showAlert('danger', 'Failed to send test notification. Check console for details.');
        } finally {
            if (testBtn) {
                testBtn.disabled = false;
                testBtn.innerHTML = '<i class="fas fa-bell me-2"></i>Send Test Notification';
            }
        }
    }

    /**
     * Show success message
     */
    showSettingsSaved() {
        this.showAlert('success', 'Notification settings saved successfully!', 3000);
    }

    /**
     * Show permission granted message
     */
    showPermissionGranted() {
        this.showAlert('success', 'Notification permission granted! You will now receive notifications.', 4000);
    }

    /**
     * Show permission denied message
     */
    showPermissionDenied() {
        this.showAlert('warning', 'Notification permission was blocked. You can enable it in your browser settings.', 5000);
    }

    /**
     * Show alert message
     */
    showAlert(type, message, duration = 4000) {
        const alertDiv = document.createElement('div');
        alertDiv.className = `alert alert-${type} alert-dismissible fade show shadow`;
        alertDiv.style.position = 'fixed';
        alertDiv.style.top = '80px';
        alertDiv.style.right = '20px';
        alertDiv.style.zIndex = '1050';
        alertDiv.style.minWidth = '300px';
        alertDiv.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;

        document.body.appendChild(alertDiv);

        if (duration) {
            setTimeout(() => {
                alertDiv.remove();
            }, duration);
        }
    }
}

// Initialize notification settings UI when DOM is ready
let notificationSettingsUI;
document.addEventListener('DOMContentLoaded', () => {
    notificationSettingsUI = new NotificationSettingsUI();
    // Only initialize if we're on a page with notification settings
    if (document.getElementById('soundNotificationsToggle') || 
        document.getElementById('browserNotificationsToggle')) {
        notificationSettingsUI.init();
    }
});
