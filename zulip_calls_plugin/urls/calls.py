from django.urls import path

from ..views import (
    create_call,
    create_embedded_call,
    respond_to_call,
    end_call,
    cancel_call,
    get_call_status,
    get_call_history,
    acknowledge_call,
    heartbeat,
    # Group call endpoints
    create_group_call,
    invite_to_group_call,
    join_group_call,
    leave_group_call,
    decline_group_call,
    end_group_call,
    get_group_call_status,
    get_group_call_participants,
)

urlpatterns = [
    # 1-to-1 call management
    path("api/v1/calls/create", create_call, name="create_call"),
    path("api/v1/calls/create-embedded", create_embedded_call, name="create_embedded_call"),
    path("api/v1/calls/<str:call_id>/respond", respond_to_call, name="respond_to_call"),
    path("api/v1/calls/<str:call_id>/end", end_call, name="end_call"),
    path("api/v1/calls/<str:call_id>/cancel", cancel_call, name="cancel_call"),
    path("api/v1/calls/<str:call_id>/status", get_call_status, name="get_call_status"),
    path("api/v1/calls/history", get_call_history, name="get_call_history"),
    path("api/v1/calls/acknowledge", acknowledge_call, name="acknowledge_call"),
    path("api/v1/calls/heartbeat", heartbeat, name="heartbeat"),
    # Group call endpoints
    path("api/v1/calls/group/create", create_group_call, name="create_group_call"),
    path("api/v1/calls/group/<str:call_id>/invite", invite_to_group_call, name="invite_to_group_call"),
    path("api/v1/calls/group/<str:call_id>/join", join_group_call, name="join_group_call"),
    path("api/v1/calls/group/<str:call_id>/leave", leave_group_call, name="leave_group_call"),
    path("api/v1/calls/group/<str:call_id>/decline", decline_group_call, name="decline_group_call"),
    path("api/v1/calls/group/<str:call_id>/end", end_group_call, name="end_group_call"),
    path("api/v1/calls/group/<str:call_id>/status", get_group_call_status, name="get_group_call_status"),
    path("api/v1/calls/group/<str:call_id>/participants", get_group_call_participants, name="get_group_call_participants"),
]