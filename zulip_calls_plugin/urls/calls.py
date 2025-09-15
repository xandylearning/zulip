from django.urls import path

from ..views import (
    create_call,
    respond_to_call,
    end_call,
    get_call_status,
    get_call_history,
    initiate_quick_call,
    create_embedded_call,
    embedded_call_view,
    get_embedded_calls_script,
    get_calls_override_script,
)

# Plugin URL patterns for call functionality
urlpatterns = [
    # Quick call endpoint (Option A from feature spec)
    path("api/v1/calls/initiate", initiate_quick_call, name="initiate_quick_call"),

    # Full call management endpoints (Option B/C from feature spec)
    path("api/v1/calls/create", create_call, name="create_call"),
    path("api/v1/calls/<str:call_id>/respond", respond_to_call, name="respond_to_call"),
    path("api/v1/calls/<str:call_id>/end", end_call, name="end_call"),
    path("api/v1/calls/<str:call_id>/status", get_call_status, name="get_call_status"),

    # Embedded call endpoints
    path("api/v1/calls/create-embedded", create_embedded_call, name="create_embedded_call"),
    path("calls/embed/<str:call_id>", embedded_call_view, name="embedded_call_view"),
    path("calls/script", get_embedded_calls_script, name="get_embedded_calls_script"),
    path("calls/override.js", get_calls_override_script, name="get_calls_override_script"),

    # Call history endpoint
    path("api/v1/calls/history", get_call_history, name="get_call_history"),
]