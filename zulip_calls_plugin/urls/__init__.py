"""Zulip Calls Plugin URL Configuration"""

from typing import Any

from .calls import urlpatterns

# Empty i18n_urlpatterns since this plugin doesn't have internationalized URLs
i18n_urlpatterns: Any = []

__all__ = ["urlpatterns", "i18n_urlpatterns"]
