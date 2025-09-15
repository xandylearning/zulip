"""
Context processor for Zulip Calls Plugin
Adds calls plugin configuration to all templates
"""

from django.conf import settings
from django.http import HttpRequest
from typing import Dict, Any


def calls_plugin_context(request: HttpRequest) -> Dict[str, Any]:
    """Add calls plugin context to all templates"""

    # Only add context for authenticated users
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {}

    return {
        'calls_plugin_enabled': True,
        'calls_plugin_js_url': '/calls/script',
        'calls_plugin_static_url': settings.STATIC_URL + 'js/embedded_calls.js',
    }