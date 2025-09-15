"""
Zulip Calls Plugin

A modular plugin that adds video/voice calling functionality to Zulip.
Can be easily installed or removed without affecting core Zulip functionality.

Features:
- Video and audio calling with Jitsi Meet integration
- Call invitations with push notifications
- Call history tracking
- Accept/decline functionality
- Database models for call management

Usage:
- Run: python manage.py install_calls_plugin
- Remove: python manage.py uninstall_calls_plugin
"""

__version__ = "1.0.0"
__author__ = "Zulip Community"