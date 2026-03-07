"""Zulip Calls Plugin Views"""

from .calls import (
    create_call,
    respond_to_call,
    end_call,
    cancel_call,
    get_call_status,
    get_call_history,
    create_embedded_call,
    acknowledge_call,
    heartbeat,
    cleanup_stale_calls,
    # Group call functions
    create_group_call,
    invite_to_group_call,
    join_group_call,
    leave_group_call,
    decline_group_call,
    end_group_call,
    get_group_call_status,
    get_group_call_participants,
)

__all__ = [
    "create_call",
    "respond_to_call",
    "end_call",
    "cancel_call",
    "get_call_status",
    "get_call_history",
    "create_embedded_call",
    "acknowledge_call",
    "heartbeat",
    "cleanup_stale_calls",
    # Group call functions
    "create_group_call",
    "invite_to_group_call",
    "join_group_call",
    "leave_group_call",
    "decline_group_call",
    "end_group_call",
    "get_group_call_status",
    "get_group_call_participants",
]