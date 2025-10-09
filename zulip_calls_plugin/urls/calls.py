from django.urls import path

from ..views import (
    create_call,
    respond_to_call,
    end_call,
    cancel_call,
    get_call_status,
    get_call_history,
    acknowledge_call,
)

# Essential API endpoints for Flutter integration
urlpatterns = [
    # Core call management endpoints
    path("api/v1/calls/create", create_call, name="create_call"),
    path("api/v1/calls/<str:call_id>/respond", respond_to_call, name="respond_to_call"),
    path("api/v1/calls/<str:call_id>/end", end_call, name="end_call"),
    path("api/v1/calls/<str:call_id>/cancel", cancel_call, name="cancel_call"),
    path("api/v1/calls/<str:call_id>/status", get_call_status, name="get_call_status"),
    path("api/v1/calls/history", get_call_history, name="get_call_history"),
    
    # Flutter-specific endpoints
    path("api/v1/calls/acknowledge", acknowledge_call, name="acknowledge_call"),
]