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

        # Fix reset_queries to handle psycopg2 connections properly
        self._patch_reset_queries()

        # Register event listeners here if needed
        self._register_event_listeners()

    def _patch_reset_queries(self):
        """
        Monkey-patch reset_queries to handle psycopg2 connections.
        
        The core reset_queries function assumes all database connections have
        a 'queries' attribute, but psycopg2 connections don't. This patch
        adds proper error handling to prevent AttributeError exceptions.
        """
        try:
            from django.db import connections
            from zerver.lib import db_connections

            def safe_reset_queries() -> None:
                """Safely reset queries for all database connections."""
                for conn in connections.all():
                    if conn.connection is not None:
                        try:
                            # Only try to reset queries if the attribute exists and is writable
                            if hasattr(conn.connection, "queries"):
                                conn.connection.queries = []
                        except (AttributeError, TypeError):
                            # psycopg2 connections don't have a queries attribute
                            # This is expected and safe to ignore
                            pass

            # Replace the function in the module
            db_connections.reset_queries = safe_reset_queries
            logger.debug("✅ Patched reset_queries to handle psycopg2 connections")

        except Exception as e:
            logger.warning(f"Failed to patch reset_queries: {e}")

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
