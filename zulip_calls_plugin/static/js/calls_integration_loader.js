/**
 * Zulip Calls Plugin Loader
 *
 * This script loads the embedded calls functionality and integrates it with Zulip's compose system.
 * It should be included after Zulip's main JavaScript loads.
 */

(function() {
    'use strict';

    // Check if calls plugin is enabled
    function isCallsPluginEnabled() {
        // You can check this through a server-side rendered variable or API call
        return true; // For now, always enabled
    }

    // Load the embedded calls script dynamically
    function loadEmbeddedCallsScript() {
        const script = document.createElement('script');
        script.src = '/static/js/embedded_calls.js';
        script.onload = function() {
            console.log('Zulip Calls Plugin: Embedded calls loaded successfully');

            // Initialize the embedded calls system
            if (window.embeddedCalls && window.embeddedCalls.overrideCallButtons) {
                window.embeddedCalls.overrideCallButtons();
            }
        };
        script.onerror = function() {
            console.warn('Zulip Calls Plugin: Failed to load embedded calls script');
        };
        document.head.appendChild(script);
    }

    // Initialize when DOM is ready
    function initializeCallsPlugin() {
        if (!isCallsPluginEnabled()) {
            console.log('Zulip Calls Plugin: Plugin not enabled');
            return;
        }

        // Wait for jQuery and other dependencies
        if (typeof $ === 'undefined') {
            setTimeout(initializeCallsPlugin, 100);
            return;
        }

        console.log('Zulip Calls Plugin: Initializing...');
        loadEmbeddedCallsScript();
    }

    // Start initialization
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initializeCallsPlugin);
    } else {
        initializeCallsPlugin();
    }

    // Also listen for page navigation in single-page app
    window.addEventListener('popstate', function() {
        setTimeout(function() {
            if (window.embeddedCalls && window.embeddedCalls.overrideCallButtons) {
                window.embeddedCalls.overrideCallButtons();
            }
        }, 500);
    });

})();