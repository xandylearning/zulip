from django.apps import AppConfig
from django.conf import settings
import logging
import os

logger = logging.getLogger(__name__)


class EventListenersConfig(AppConfig):
    """Configuration for the Event Listeners Django app"""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'zerver.event_listeners'
    verbose_name = 'Event Listeners'

    def ready(self):
        """Called when Django app is ready"""
        # Prevent initialization in Django's auto-reloader process
        # Only run in the actual worker process
        if os.environ.get('RUN_MAIN') != 'true' and os.environ.get('SERVER_SOFTWARE') != 'test':
            # This is the reloader process, skip initialization
            return

        # Register event listeners only if enabled in settings
        if getattr(settings, 'EVENT_LISTENERS_ENABLED', False):
            self.register_event_listeners()
            logger.info("Event Listeners app initialized")

    def register_event_listeners(self):
        """Register default event listeners"""
        from . import signals  # Import signals to register them
        from .registry import event_listener_registry

        # Import examples to register the decorators
        try:
            from . import examples
            logger.debug("Imported examples module")
        except ImportError as e:
            logger.warning(f"Could not import examples: {e}")

        # Register built-in listeners
        event_listener_registry.autodiscover_listeners()

        logger.info(f"Registered {len(event_listener_registry.listeners)} event listeners")