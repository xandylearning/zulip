"""
Plugin configuration and integration utilities
"""

from django.conf import settings
from django.urls import include, path


class CallsPluginConfig:
    """Configuration manager for the Zulip Calls Plugin"""

    PLUGIN_NAME = "zulip_calls_plugin"
    PLUGIN_VERSION = "1.0.0"

    @classmethod
    def is_installed(cls) -> bool:
        """Check if the plugin is currently installed and active"""
        return cls.PLUGIN_NAME in settings.INSTALLED_APPS

    @classmethod
    def get_url_patterns(cls):
        """Get URL patterns for the plugin"""
        from .urls import urlpatterns
        return [
            path("", include((urlpatterns, cls.PLUGIN_NAME), namespace="calls")),
        ]

    @classmethod
    def get_required_settings(cls) -> dict:
        """Get required Django settings for the plugin"""
        return {
            "INSTALLED_APPS_ADDITION": [cls.PLUGIN_NAME],
            "MIGRATION_MODULES": {
                cls.PLUGIN_NAME: f"{cls.PLUGIN_NAME}.migrations"
            }
        }