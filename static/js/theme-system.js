/**
 * Theme System Utilities
 * Provides comprehensive theme management and CSS variable handling for all templates
 * 
 * Available Themes:
 * - purple (default)
 * - blue-ocean
 * - teal-marine
 * - emerald
 * - indigo
 * - rose
 * - amber
 */

// ==================== THEME SYSTEM ====================

/**
 * Get the current theme from localStorage
 * @returns {string} Current theme name
 */
function getCurrentTheme() {
    return localStorage.getItem('selectedTheme') || 'purple';
}

/**
 * Get a specific CSS variable value
 * @param {string} variableName - Name of the CSS variable (without --)
 * @returns {string} The value of the CSS variable
 */
function getCSSVariable(variableName) {
    return getComputedStyle(document.documentElement)
        .getPropertyValue(`--${variableName}`).trim();
}

/**
 * Get all current CSS variables
 * @returns {object} Object containing all CSS variable values
 */
function getAllCSSVariables() {
    const root = getComputedStyle(document.documentElement);
    const variables = {};
    
    const importantVars = [
        'primary-color',
        'secondary-color',
        'accent-color',
        'success-green',
        'warning-orange',
        'danger-red',
        'info-blue',
        'text-primary',
        'text-secondary',
        'text-muted',
        'bg-primary',
        'bg-secondary',
        'border-color'
    ];
    
    importantVars.forEach(varName => {
        variables[varName] = root.getPropertyValue(`--${varName}`).trim();
    });
    
    return variables;
}

/**
 * Get theme colors for use in charts, visualizations, etc.
 * @returns {object} Object with theme color information
 */
function getThemeColors() {
    return {
        primary: getCSSVariable('primary-color'),
        secondary: getCSSVariable('secondary-color'),
        accent: getCSSVariable('accent-color'),
        success: getCSSVariable('success-green'),
        warning: getCSSVariable('warning-orange'),
        danger: getCSSVariable('danger-red'),
        info: getCSSVariable('info-blue'),
        textPrimary: getCSSVariable('text-primary'),
        textSecondary: getCSSVariable('text-secondary'),
        textMuted: getCSSVariable('text-muted'),
        bgPrimary: getCSSVariable('bg-primary'),
        bgSecondary: getCSSVariable('bg-secondary'),
        borderColor: getCSSVariable('border-color')
    };
}

/**
 * Listen for theme changes in any child template
 * @param {function} callback - Function to execute when theme changes
 * @example
 * onThemeChange((theme) => {
 *     console.log('New theme:', theme);
 *     // Re-render your components with new colors
 * });
 */
function onThemeChange(callback) {
    document.addEventListener('themeChanged', (event) => {
        callback(event.detail.theme);
    });
}

/**
 * Update Chart.js charts to use current theme colors
 * @param {object} chart - Chart.js chart instance
 * @example
 * updateChartTheme(myChart);
 */
function updateChartTheme(chart) {
    if (!chart) return;
    
    const colors = getThemeColors();
    
    // Update datasets
    if (chart.data.datasets) {
        chart.data.datasets.forEach((dataset, index) => {
            if (index === 0) {
                dataset.borderColor = colors.primary;
                dataset.backgroundColor = colors.primary + '30';
            } else if (index === 1) {
                dataset.borderColor = colors.secondary;
                dataset.backgroundColor = colors.secondary + '30';
            } else if (index === 2) {
                dataset.borderColor = colors.accent;
                dataset.backgroundColor = colors.accent + '30';
            }
        });
    }
    
    // Update chart options
    if (chart.options && chart.options.plugins && chart.options.plugins.legend) {
        chart.options.plugins.legend.labels.color = colors.textPrimary;
    }
    
    chart.update();
}

/**
 * Update all Chart.js charts on page
 * @example
 * updateAllCharts();
 */
function updateAllCharts() {
    if (typeof Chart !== 'undefined' && Chart.instances) {
        Chart.instances.forEach(chart => {
            updateChartTheme(chart);
        });
    }
}

/**
 * Get Bootstrap color variant based on theme
 * @param {string} type - 'primary', 'secondary', 'success', 'danger', 'warning', 'info'
 * @returns {string} Bootstrap color class
 */
function getBootstrapColor(type) {
    const colorMap = {
        'primary': 'primary',
        'secondary': 'secondary',
        'success': 'success',
        'danger': 'danger',
        'warning': 'warning',
        'info': 'info',
        'accent': 'primary'
    };
    return colorMap[type] || 'primary';
}

/**
 * Generate color palette from current theme
 * @returns {object} Color palette object
 */
function getThemePalette() {
    const primary = getCSSVariable('primary-color');
    const secondary = getCSSVariable('secondary-color');
    const accent = getCSSVariable('accent-color');
    
    return {
        light: {
            primary: lightenColor(primary, 30),
            secondary: lightenColor(secondary, 30),
            accent: lightenColor(accent, 30)
        },
        normal: {
            primary: primary,
            secondary: secondary,
            accent: accent
        },
        dark: {
            primary: darkenColor(primary, 20),
            secondary: darkenColor(secondary, 20),
            accent: darkenColor(accent, 20)
        }
    };
}

/**
 * Lighten a color by percentage
 * @param {string} color - Hex color code
 * @param {number} percent - Percentage to lighten (0-100)
 * @returns {string} Lightened hex color
 */
function lightenColor(color, percent) {
    const num = parseInt(color.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.min(255, (num >> 16) + amt);
    const G = Math.min(255, (num >> 8 & 0x00FF) + amt);
    const B = Math.min(255, (num & 0x0000FF) + amt);
    return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
}

/**
 * Darken a color by percentage
 * @param {string} color - Hex color code
 * @param {number} percent - Percentage to darken (0-100)
 * @returns {string} Darkened hex color
 */
function darkenColor(color, percent) {
    const num = parseInt(color.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.max(0, (num >> 16) - amt);
    const G = Math.max(0, (num >> 8 & 0x00FF) - amt);
    const B = Math.max(0, (num & 0x0000FF) - amt);
    return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
}

/**
 * Apply theme colors to a specific element
 * @param {element} element - DOM element
 * @param {string} colorType - Type of color ('primary', 'secondary', etc.)
 * @param {string} property - CSS property ('background-color', 'color', 'border-color')
 */
function applyThemeColor(element, colorType, property = 'background-color') {
    if (!element) return;
    const colors = getThemeColors();
    const color = colors[colorType] || colors.primary;
    element.style[property] = color;
}

/**
 * Register theme initialization for custom components
 * Automatically applies theme on page load and on theme changes
 * @param {function} initFunction - Function to call on theme change
 * @example
 * registerThemeComponent(() => {
 *     myComponent.updateColors(getThemeColors());
 * });
 */
function registerThemeComponent(initFunction) {
    // Initialize on load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initFunction);
    } else {
        initFunction();
    }
    
    // Re-initialize on theme change
    onThemeChange(initFunction);
}

// ==================== AUTO-INITIALIZATION ====================

// Initialize theme system on page load
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log('✅ Theme System initialized');
        console.log('📊 Current Theme:', getCurrentTheme());
        console.log('🎨 Colors:', getThemeColors());
    });
} else {
    console.log('✅ Theme System ready');
}

// Listen for theme changes and log them
onThemeChange((theme) => {
    console.log('🎨 Theme changed to:', theme);
    console.log('📊 New colors:', getThemeColors());
});
