from django.apps import AppConfig


class ZulipCallsPluginConfig(AppConfig):
    """Django app configuration for the Zulip Calls Plugin"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "zulip_calls_plugin"
    verbose_name = "Zulip Calls Plugin"

    def ready(self) -> None:
        """Initialize the plugin when Django starts"""
        # Import any signal handlers or initialization code here
        pass