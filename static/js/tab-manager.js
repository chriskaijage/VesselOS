/**
 * Tab Manager - Handles auto-refresh and manual refresh for all tabs
 * Features: 3-second auto-refresh, loading indicators, refresh buttons
 */

class TabManager {
    constructor(containerSelector = '[role="tablist"]', autoRefreshInterval = 3000) {
        this.container = document.querySelector(containerSelector);
        this.autoRefreshInterval = autoRefreshInterval;
        this.refreshIntervals = new Map();
        this.isLoading = new Map();
        this.init();
    }

    init() {
        if (!this.container) return;

        // Find all tab buttons
        const tabs = this.container.querySelectorAll('[data-bs-toggle="tab"]');
        
        tabs.forEach(tab => {
            const targetId = tab.getAttribute('data-bs-target');
            if (!targetId) return;

            // Add refresh button to each tab
            this.addRefreshButton(tab, targetId);

            // Add click listener to start auto-refresh when tab is activated
            tab.addEventListener('shown.bs.tab', () => {
                this.startAutoRefresh(targetId);
            });

            // Add click listener to stop auto-refresh when tab is deactivated
            tab.addEventListener('hidden.bs.tab', () => {
                this.stopAutoRefresh(targetId);
            });

            // Initialize as not loading
            this.isLoading.set(targetId, false);
        });

        // Start auto-refresh for the active tab
        const activeTab = this.container.querySelector('[data-bs-toggle="tab"].active');
        if (activeTab) {
            const targetId = activeTab.getAttribute('data-bs-target');
            this.startAutoRefresh(targetId);
        }
    }

    /**
     * Add a refresh button to the tab header
     */
    addRefreshButton(tabElement, targetId) {
        // Check if button already exists
        if (tabElement.querySelector('.tab-refresh-btn')) return;

        // Create refresh button
        const refreshBtn = document.createElement('button');
        refreshBtn.className = 'tab-refresh-btn ms-2';
        refreshBtn.type = 'button';
        refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
        refreshBtn.title = 'Refresh this tab';
        refreshBtn.style.cssText = `
            background: none;
            border: none;
            color: inherit;
            cursor: pointer;
            padding: 2px 6px;
            font-size: 0.9rem;
            transition: transform 0.3s ease;
        `;

        // Add hover effect
        refreshBtn.addEventListener('mouseenter', () => {
            if (!this.isLoading.get(targetId)) {
                refreshBtn.style.transform = 'rotate(180deg)';
            }
        });

        refreshBtn.addEventListener('mouseleave', () => {
            refreshBtn.style.transform = 'rotate(0deg)';
        });

        // Add click handler
        refreshBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            this.refreshTab(targetId, refreshBtn);
        });

        tabElement.appendChild(refreshBtn);
    }

    /**
     * Refresh a specific tab content
     */
    async refreshTab(targetId, refreshBtn = null) {
        if (this.isLoading.get(targetId)) return; // Don't refresh if already loading

        this.isLoading.set(targetId, true);

        // Get refresh button if not provided
        if (!refreshBtn) {
            const tab = this.container.querySelector(`[data-bs-target="${targetId}"]`);
            refreshBtn = tab ? tab.querySelector('.tab-refresh-btn') : null;
        }

        // Show loading state
        if (refreshBtn) {
            refreshBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            refreshBtn.style.opacity = '0.6';
            refreshBtn.disabled = true;
        }

        // Show loading indicator in tab content
        const tabContent = document.querySelector(targetId);
        if (tabContent) {
            const originalContent = tabContent.innerHTML;
            tabContent.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin fa-2x text-primary"></i></div>';

            // Try to call the tab's refresh function if it exists
            try {
                // Look for refresh function in window (e.g., refreshDetailsTab, refreshTimelineTab)
                const tabName = targetId.replace('#', '').replace(/-/g, '_');
                const refreshFunctionName = `refresh${tabName.charAt(0).toUpperCase() + tabName.slice(1)}Tab`;
                
                if (typeof window[refreshFunctionName] === 'function') {
                    await window[refreshFunctionName]();
                } else {
                    // Fallback: try generic refresh with the tab name
                    console.warn(`Refresh function '${refreshFunctionName}' not found for tab '${targetId}'`);
                    tabContent.innerHTML = originalContent; // Restore original content if no refresh function
                }
            } catch (error) {
                console.error(`Error refreshing tab ${targetId}:`, error);
                tabContent.innerHTML = '<div class="alert alert-danger"><i class="fas fa-exclamation-triangle"></i> Error loading tab content</div>';
            }
        }

        // Restore button state
        if (refreshBtn) {
            setTimeout(() => {
                refreshBtn.innerHTML = '<i class="fas fa-sync-alt"></i>';
                refreshBtn.style.opacity = '1';
                refreshBtn.disabled = false;
                this.isLoading.set(targetId, false);
            }, 500);
        }
    }

    /**
     * Start auto-refresh for a tab
     */
    startAutoRefresh(targetId) {
        // Stop any existing interval
        this.stopAutoRefresh(targetId);

        // Set new interval
        const interval = setInterval(() => {
            this.refreshTab(targetId);
        }, this.autoRefreshInterval);

        this.refreshIntervals.set(targetId, interval);
    }

    /**
     * Stop auto-refresh for a tab
     */
    stopAutoRefresh(targetId) {
        const interval = this.refreshIntervals.get(targetId);
        if (interval) {
            clearInterval(interval);
            this.refreshIntervals.delete(targetId);
        }
    }

    /**
     * Stop all auto-refreshes
     */
    stopAll() {
        this.refreshIntervals.forEach((interval) => {
            clearInterval(interval);
        });
        this.refreshIntervals.clear();
    }

    /**
     * Update auto-refresh interval
     */
    setAutoRefreshInterval(newInterval) {
        this.autoRefreshInterval = newInterval;
        // Restart all active intervals
        const activeTab = this.container.querySelector('[data-bs-toggle="tab"].active');
        if (activeTab) {
            const targetId = activeTab.getAttribute('data-bs-target');
            this.startAutoRefresh(targetId);
        }
    }
}

// Auto-initialize all tab containers on page load
document.addEventListener('DOMContentLoaded', () => {
    // Find all tab containers and initialize them
    const tabContainers = document.querySelectorAll('[role="tablist"]');
    tabContainers.forEach(container => {
        // Create a unique key for each tab manager
        const containerId = container.id || 'tab-' + Math.random().toString(36).substr(2, 9);
        window['tabManager_' + containerId] = new TabManager('[id="' + containerId + '"]', 3000);
    });

    // Also initialize without ID for backward compatibility
    if (tabContainers.length === 0) {
        const mainTabs = document.querySelector('[role="tablist"]');
        if (mainTabs && !window.globalTabManager) {
            window.globalTabManager = new TabManager('[role="tablist"]', 3000);
        }
    }
});

/**
 * Helper function to create a generic tab refresh function
 * Usage: createTabRefresher('tabName', apiEndpoint, processorFunction)
 */
function createTabRefresher(tabName, apiEndpoint, processorFunction) {
    const functionName = `refresh${tabName.charAt(0).toUpperCase() + tabName.slice(1)}Tab`;
    
    window[functionName] = async function() {
        try {
            const response = await fetch(apiEndpoint);
            const data = await response.json();

            if (data.success) {
                if (processorFunction) {
                    processorFunction(data);
                } else {
                    console.log(`Refreshed ${tabName} tab with data:`, data);
                }
            } else {
                throw new Error(data.error || 'Failed to load data');
            }
        } catch (error) {
            console.error(`Error refreshing ${tabName}:`, error);
            throw error;
        }
    };
}

/**
 * Utility to add loading state to any element
 */
function showLoading(element) {
    if (!element) return;
    element.innerHTML = '<div class="text-center py-4"><i class="fas fa-spinner fa-spin fa-2x text-primary"></i><p class="mt-2">Loading...</p></div>';
}

function hideLoading(element) {
    if (!element) return;
    // This is handled by the actual content load
}
