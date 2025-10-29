from django.apps import AppConfig
import logging

class ZulipCallsPluginConfig(AppConfig):
    """Django app configuration for the Zulip Calls Plugin"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "zulip_calls_plugin"
    verbose_name = "Zulip Calls Plugin"

    def ready(self) -> None:
        """Initialize the plugin when Django starts"""
        # Apply plugin settings
        from .plugin_config import CallsPluginConfig
        CallsPluginConfig.apply_settings()
        logging.info("Zulip Calls Plugin initialized")
        # Import any signal handlers or initialization code here
        pass