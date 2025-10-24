"""
LMS Integration Django App Configuration
"""

import logging
import os
from django.apps import AppConfig

logger = logging.getLogger(__name__)


class LmsIntegrationConfig(AppConfig):
    """Configuration for the LMS Integration Django app"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'lms_integration'
    verbose_name = 'LMS Integration'

    def ready(self):
        """Initialize LMS Integration app when Django is ready"""
        # Prevent initialization in Django's auto-reloader process
        # Only run in the actual worker process
        if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('SERVER_SOFTWARE') != 'test':
            # This is the reloader process, skip initialization
            return

        # Only log initialization once (not for each worker process)
        logger.info("=" * 60)
        logger.info("🎓 LMS INTEGRATION APP INITIALIZED")
        logger.info("=" * 60)

        # Register event listeners here if needed
        self._register_event_listeners()

    def _register_event_listeners(self):
        """Register event listeners for LMS activities"""
        try:
            from zerver.event_listeners.registry import event_listener_registry
            from lms_integration.event_listeners import LMSActivityEventHandler

            # Check if already registered to prevent duplicates
            if 'lms_activity' in event_listener_registry.list_listeners():
                logger.debug("LMS Activity Event Handler already registered")
                return

            # Register the LMS activity event handler using the registry
            event_listener_registry.register('lms_activity', LMSActivityEventHandler)
            logger.info("✅ LMS Activity Event Handler registered")

        except Exception as e:
            logger.error(f"❌ Failed to register LMS event listeners: {e}")
