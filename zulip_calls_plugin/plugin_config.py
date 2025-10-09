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

    @classmethod
    def get_default_jitsi_settings(cls) -> dict:
        """Get default Jitsi integration settings"""
        return {
            # Jitsi Integration Settings
            'JITSI_SERVER_URL': "https://dev.meet.xandylearning.in",  # Custom Jitsi server
            'JITSI_MEETING_PREFIX': "zulip-call-",
            'JITSI_API_ENABLED': True,

            # Call Settings
            'CALL_NOTIFICATION_TIMEOUT': 120,  # 2 minutes in seconds
            'CALL_RING_TIMEOUT': 30,  # 30 seconds before showing "ringing"
            'CALL_MAX_DURATION': 3600,  # 1 hour max call duration
            'CALL_CLEANUP_INTERVAL': 300,  # 5 minutes - cleanup old calls

            # Push Notification Settings for Calls
            'CALL_PUSH_NOTIFICATION_ENABLED': True,
            'CALL_PUSH_NOTIFICATION_SOUND': "call_ring.wav",  # Custom ringtone

            # Feature Flags
            'ENABLE_VIDEO_CALLS': True,
            'ENABLE_AUDIO_CALLS': True,
            'ENABLE_CALL_HISTORY': True,
        }

    @classmethod
    def apply_settings(cls):
        """Apply plugin settings to Django settings"""
        defaults = cls.get_default_jitsi_settings()

        # Apply defaults only if not already set
        for key, value in defaults.items():
            if not hasattr(settings, key):
                setattr(settings, key, value)