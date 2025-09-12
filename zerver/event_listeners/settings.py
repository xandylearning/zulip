"""
Settings configuration for the Event Listeners Django app plugin.

Add these settings to your Zulip settings file to configure the event listeners plugin.
"""

# =============================================================================
# EVENT LISTENERS PLUGIN CONFIGURATION
# =============================================================================

# Enable the event listeners plugin
EVENT_LISTENERS_ENABLED = True

# Event listener configuration
EVENT_LISTENERS_CONFIG = {
    # Queue configuration
    'QUEUE_CONFIG': {
        'max_retries': 3,
        'retry_delay': 5,  # seconds
        'batch_size': 100,
        'timeout': 30,  # seconds
    },
    
    # Logging configuration
    'LOGGING': {
        'level': 'INFO',
        'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        'file': None,  # Set to file path for file logging
    },
    
    # Statistics configuration
    'STATISTICS': {
        'enabled': True,
        'retention_days': 30,  # Keep stats for 30 days
        'aggregation_interval': 300,  # 5 minutes
    },
    
    # Filter configuration
    'FILTERS': {
        'default_realm_filter': None,  # None means all realms
        'default_user_filter': None,   # None means all users
        'max_event_age': 3600,        # Ignore events older than 1 hour
    },
    
    # Performance configuration
    'PERFORMANCE': {
        'max_concurrent_handlers': 10,
        'handler_timeout': 30,
        'memory_threshold': 100 * 1024 * 1024,  # 100MB
    },
    
    # Default listeners to enable
    'DEFAULT_LISTENERS': [
        'message_logger',           # Basic message logging
        'user_status_tracker',      # User status tracking
        'stream_activity_monitor',  # Stream activity monitoring
        # 'ai_mentoring_demo',      # Uncomment to enable AI mentoring demo
        # 'comprehensive_analytics', # Uncomment for comprehensive analytics
    ],
    
    # Listener-specific configuration
    'LISTENER_CONFIG': {
        'message_logger': {
            'log_level': 'INFO',
            'max_content_length': 200,
        },
        'ai_mentoring_demo': {
            'response_delay_min': 30,    # Minimum delay before AI response (seconds)
            'response_delay_max': 300,   # Maximum delay before AI response (seconds)
            'learning_enabled': True,
            'response_probability': 0.7, # Probability of AI responding
        },
        'comprehensive_analytics': {
            'export_interval': 3600,     # Export analytics every hour
            'export_format': 'json',
        },
    },
}

# Integration with existing Zulip settings
if EVENT_LISTENERS_ENABLED:
    # Add to INSTALLED_APPS
    INSTALLED_APPS = globals().get('INSTALLED_APPS', [])
    if 'zerver.event_listeners' not in INSTALLED_APPS:
        INSTALLED_APPS.append('zerver.event_listeners')
    
    # Add logging configuration
    LOGGING = globals().get('LOGGING', {'version': 1, 'loggers': {}})
    if 'loggers' not in LOGGING:
        LOGGING['loggers'] = {}
    
    LOGGING['loggers']['zerver.event_listeners'] = {
        'handlers': ['console'],
        'level': EVENT_LISTENERS_CONFIG['LOGGING']['level'],
        'propagate': False,
    }

# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================

# The event listeners app will create the following tables:
# - event_listeners_eventlistener
# - event_listeners_eventlog  
# - event_listeners_listenerstats
# - event_listeners_listenerconfig
#
# Run migrations after enabling: ./manage.py migrate event_listeners

# =============================================================================
# MANAGEMENT COMMANDS
# =============================================================================

# Available management commands:
# 1. Run event listeners daemon:
#    ./manage.py run_event_listeners [--listeners LISTENER1,LISTENER2] [--queue-name QUEUE]
#
# 2. List available listeners:
#    ./manage.py list_event_listeners [--show-stats] [--show-config]
#
# 3. Example usage:
#    ./manage.py run_event_listeners --listeners message_logger,user_status_tracker
#    ./manage.py list_event_listeners --show-stats

# =============================================================================
# PRODUCTION DEPLOYMENT NOTES
# =============================================================================

# For production deployment:
# 1. Set EVENT_LISTENERS_ENABLED = True in your production settings
# 2. Run migrations: ./manage.py migrate event_listeners
# 3. Configure logging to write to files rather than console
# 4. Set up monitoring for the event listener processes
# 5. Consider running listeners in separate processes or containers
# 6. Configure appropriate resource limits and timeouts
# 7. Set up log rotation for event listener logs
# 8. Monitor memory usage and performance metrics

# Example production configuration:
"""
EVENT_LISTENERS_CONFIG = {
    'LOGGING': {
        'file': '/var/log/zulip/event_listeners.log',
        'level': 'WARNING',  # Reduce verbosity in production
    },
    'PERFORMANCE': {
        'max_concurrent_handlers': 5,  # Conservative for production
        'handler_timeout': 15,
        'memory_threshold': 50 * 1024 * 1024,  # 50MB limit
    },
    'STATISTICS': {
        'retention_days': 7,  # Shorter retention in production
    },
}
"""