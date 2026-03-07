"""
Call event actions following Zulip's action pattern.

This module provides action functions for sending call events via Zulip's
event system with proper offline detection and push notification handling.

Based on the pattern from zerver/actions/typing.py
"""

import logging
from typing import Any

from django.utils import timezone

from zerver.models import Realm, UserProfile
from zerver.tornado.django_api import send_event_on_commit
from zerver.tornado.event_queue import receiver_is_off_zulip

from .models import Call, GroupCall

logger = logging.getLogger(__name__)


def is_user_offline(user_profile_id: int) -> bool:
    """
    Check if user is offline using Zulip's presence system.

    Returns True if the user has no active event queues (no open Zulip sessions).
    This indicates they should receive push notifications instead of/in addition to events.

    Args:
        user_profile_id: The user ID to check

    Returns:
        True if user is offline/has no active sessions, False otherwise
    """
    return receiver_is_off_zulip(user_profile_id)


def do_send_call_event(
    realm: Realm,
    call: Call,
    op: str,
    user_ids_to_notify: list[int],
    extra_data: dict[str, Any] | None = None,
) -> None:
    """
    Send call event via Zulip's event system.

    This is the core function for sending 1-to-1 call events. Events are sent
    via Tornado's event queue system and will be delivered to all active clients.

    Args:
        realm: The realm the call belongs to
        call: The Call model instance
        op: Event operation (initiated, incoming_call, ringing, accepted, declined,
            ended, cancelled, missed)
        user_ids_to_notify: List of user IDs who should receive this event
        extra_data: Optional additional data to include in the event

    Example:
        do_send_call_event(
            realm=user.realm,
            call=call_instance,
            op="initiated",
            user_ids_to_notify=[caller.id],
        )
    """
    event: dict[str, Any] = {
        "type": "call",
        "op": op,
        "call_id": str(call.call_id),
        "call_type": call.call_type,
        "sender": {
            "user_id": call.sender.id,
            "full_name": call.sender.full_name,
            "avatar_url": f"/avatar/{call.sender.id}",
        },
        "receiver": {
            "user_id": call.receiver.id,
            "full_name": call.receiver.full_name,
            "avatar_url": f"/avatar/{call.receiver.id}",
        },
        "state": call.state,
        "jitsi_url": call.jitsi_room_url,
        "timestamp": timezone.now().isoformat(),
    }

    if extra_data:
        event.update(extra_data)

    send_event_on_commit(realm, event, user_ids_to_notify)
    logger.info(
        f"Call event '{op}' sent for call {call.call_id} to users {user_ids_to_notify}"
    )


def do_initiate_call(realm: Realm, call: Call) -> dict[str, bool]:
    """
    Handle call initiation with offline detection.

    This function:
    1. Checks if receiver is online/offline
    2. Sends "initiated" event to caller
    3. Sends "incoming_call" event to receiver (queued if offline)
    4. Returns status indicating if receiver was online

    The push notification should be sent separately by the caller, as this
    allows the caller to choose the appropriate push notification function
    (send_call_push_notification, send_fcm_call_notification, etc.).

    Args:
        realm: The realm the call belongs to
        call: The newly created Call instance

    Returns:
        Dictionary with key "receiver_online" indicating receiver's online status

    Example:
        status = do_initiate_call(user.realm, call)
        if not status["receiver_online"]:
            # Receiver is offline, send high-priority push notification
            send_call_push_notification(call.receiver, call_data)
    """
    receiver_offline = is_user_offline(call.receiver.id)

    # Always send event to caller (they initiated the call)
    do_send_call_event(realm, call, "initiated", [call.sender.id])

    # Send event to receiver with offline status indicator
    # If receiver is offline, event will be queued and delivered when they come online
    do_send_call_event(
        realm,
        call,
        "incoming_call",
        [call.receiver.id],
        extra_data={"receiver_was_offline": receiver_offline},
    )

    logger.info(
        f"Call {call.call_id} initiated by {call.sender.id} to {call.receiver.id} "
        f"(receiver_offline={receiver_offline})"
    )

    return {"receiver_online": not receiver_offline}


def do_send_call_ringing_event(realm: Realm, call: Call) -> None:
    """
    Send call ringing event when receiver acknowledges the call.

    Args:
        realm: The realm the call belongs to
        call: The Call instance in ringing state
    """
    # Notify sender that receiver has acknowledged and is ringing
    do_send_call_event(realm, call, "ringing", [call.sender.id])
    logger.info(f"Call {call.call_id} ringing event sent to sender {call.sender.id}")


def do_send_call_accepted_event(realm: Realm, call: Call) -> None:
    """
    Send call accepted event to both participants.

    Args:
        realm: The realm the call belongs to
        call: The Call instance in accepted state
    """
    # Notify both participants that call was accepted
    do_send_call_event(
        realm,
        call,
        "accepted",
        [call.sender.id, call.receiver.id],
    )
    logger.info(f"Call {call.call_id} accepted event sent to both participants")


def do_send_call_declined_event(realm: Realm, call: Call) -> None:
    """
    Send call declined event to both participants.

    Args:
        realm: The realm the call belongs to
        call: The Call instance in rejected/declined state
    """
    # Notify both participants that call was declined
    do_send_call_event(
        realm,
        call,
        "declined",
        [call.sender.id, call.receiver.id],
    )
    logger.info(f"Call {call.call_id} declined event sent to both participants")


def do_send_call_ended_event(
    realm: Realm, call: Call, reason: str | None = None
) -> None:
    """
    Send call ended event to both participants.

    Args:
        realm: The realm the call belongs to
        call: The Call instance that has ended
        reason: Optional reason for call ending (e.g., 'network_failure', 'normal')
    """
    extra_data = {"reason": reason} if reason else None

    # Notify both participants that call ended
    do_send_call_event(
        realm,
        call,
        "ended",
        [call.sender.id, call.receiver.id],
        extra_data=extra_data,
    )
    logger.info(
        f"Call {call.call_id} ended event sent to both participants (reason={reason})"
    )


def do_send_call_cancelled_event(realm: Realm, call: Call) -> None:
    """
    Send call cancelled event when caller cancels before receiver answers.

    Args:
        realm: The realm the call belongs to
        call: The Call instance in cancelled state
    """
    # Notify both participants that call was cancelled
    do_send_call_event(
        realm,
        call,
        "cancelled",
        [call.sender.id, call.receiver.id],
    )
    logger.info(f"Call {call.call_id} cancelled event sent to both participants")


def do_send_missed_call_event(
    realm: Realm, call: Call, timeout_seconds: int = 90
) -> None:
    """
    Send missed call events when call times out without answer.

    Sends "missed" event to BOTH caller and receiver so each side can update
    its call history UI and show appropriate missed-call notifications.

    Args:
        realm: The realm the call belongs to
        call: The Call instance that was missed
        timeout_seconds: How long the call rang before timing out (default 90)
    """
    do_send_call_event(
        realm,
        call,
        "missed",
        [call.sender.id, call.receiver.id],
        extra_data={
            "reason": "no_answer",
            "timeout_seconds": timeout_seconds,
        },
    )

    logger.info(
        f"Call {call.call_id} missed event sent to both participants "
        f"(sender={call.sender.id}, receiver={call.receiver.id}) "
        f"after {timeout_seconds}s timeout"
    )


def do_send_group_call_event(
    realm: Realm,
    group_call: GroupCall,
    op: str,
    user_ids_to_notify: list[int],
    extra_data: dict[str, Any] | None = None,
) -> None:
    """
    Send group call event via Zulip's event system.

    This is the core function for sending group call events. It constructs
    the event with current participant states and sends it to specified users.

    Args:
        realm: The realm the call belongs to
        group_call: The GroupCall model instance
        op: Event operation (created, participant_invited, participant_joined,
            participant_left, participant_declined, participant_missed, ended)
        user_ids_to_notify: List of user IDs who should receive this event
        extra_data: Optional additional data to include in the event

    Example:
        do_send_group_call_event(
            realm=user.realm,
            group_call=call_instance,
            op="created",
            user_ids_to_notify=[host.id],
        )
    """
    # Build participants list with current states
    participants = [
        {
            "user_id": p.user.id,
            "full_name": p.user.full_name,
            "avatar_url": f"/avatar/{p.user.id}",
            "state": p.state,
            "is_host": p.is_host,
        }
        for p in group_call.participants.select_related("user").all()
    ]

    event: dict[str, Any] = {
        "type": "group_call",
        "op": op,
        "call_id": str(group_call.call_id),
        "call_type": group_call.call_type,
        "host": {
            "user_id": group_call.host.id,
            "full_name": group_call.host.full_name,
            "avatar_url": f"/avatar/{group_call.host.id}",
        },
        "participants": participants,
        "jitsi_url": group_call.jitsi_room_url,
        "title": group_call.title,
        "stream_id": group_call.stream_id if group_call.stream else None,
        "topic": group_call.topic,
        "timestamp": timezone.now().isoformat(),
    }

    if extra_data:
        event.update(extra_data)

    send_event_on_commit(realm, event, user_ids_to_notify)
    logger.info(
        f"Group call event '{op}' sent for call {group_call.call_id} "
        f"to users {user_ids_to_notify}"
    )


def do_create_group_call(realm: Realm, group_call: GroupCall) -> None:
    """
    Send group call created event to the host.

    Args:
        realm: The realm the call belongs to
        group_call: The newly created GroupCall instance
    """
    do_send_group_call_event(
        realm,
        group_call,
        "created",
        [group_call.host.id],
    )
    logger.info(f"Group call {group_call.call_id} created by host {group_call.host.id}")


def do_invite_to_group_call(
    realm: Realm,
    group_call: GroupCall,
    inviter: UserProfile,
    invited_user_profiles: list[UserProfile],
) -> dict[str, list[int]]:
    """
    Invite users to a group call with offline detection.

    This function:
    1. Creates GroupCallParticipant records for invited users (if not exists)
    2. Checks each user's online status
    3. Sends "participant_invited" event to each invited user
    4. Notifies existing participants about new invites
    5. Returns lists of online/offline user IDs

    The caller should send push notifications to all invited users separately,
    with high priority for offline users.

    Args:
        realm: The realm the call belongs to
        group_call: The GroupCall instance
        inviter: The user who is inviting (usually the host)
        invited_user_profiles: List of UserProfile instances to invite

    Returns:
        Dictionary with "invited" (online users) and "offline" (offline users) lists

    Example:
        results = do_invite_to_group_call(realm, call, host, [user1, user2])
        for user_id in results["offline"]:
            # Send high-priority push to offline users
            send_group_call_push_notification(user, call, inviter)
    """
    from .models import GroupCallParticipant

    results: dict[str, list[int]] = {"invited": [], "offline": []}

    for user in invited_user_profiles:
        # Create or get participant record
        participant, created = GroupCallParticipant.objects.get_or_create(
            call=group_call,
            user=user,
            defaults={"state": "invited"},
        )

        # If participant already exists but left/declined, reset to invited
        if not created and participant.state in ["left", "declined", "missed"]:
            participant.state = "invited"
            participant.save(update_fields=["state"])

        # Check if user is offline
        is_offline = is_user_offline(user.id)

        # Send event to the invited user
        do_send_group_call_event(
            realm,
            group_call,
            "participant_invited",
            [user.id],
            extra_data={
                "inviter_id": inviter.id,
                "was_offline": is_offline,
            },
        )

        # Track online/offline status
        if is_offline:
            results["offline"].append(user.id)
        else:
            results["invited"].append(user.id)

    # Notify existing joined participants about new invites
    joined_participant_ids = list(
        group_call.participants.filter(state="joined")
        .exclude(user__in=invited_user_profiles)  # Don't notify the newly invited
        .values_list("user_id", flat=True)
    )

    if joined_participant_ids:
        do_send_group_call_event(
            realm,
            group_call,
            "participants_invited",
            joined_participant_ids,
            extra_data={
                "new_participants": [u.id for u in invited_user_profiles],
                "inviter_id": inviter.id,
            },
        )

    logger.info(
        f"Group call {group_call.call_id}: {len(invited_user_profiles)} users invited "
        f"({len(results['offline'])} offline, {len(results['invited'])} online)"
    )

    return results


def do_join_group_call(realm: Realm, group_call: GroupCall, user: UserProfile) -> None:
    """
    Send participant joined event to all active participants.

    Args:
        realm: The realm the call belongs to
        group_call: The GroupCall instance
        user: The user who joined
    """
    # Get all active participants (invited, ringing, or joined)
    active_participant_ids = list(
        group_call.participants.filter(
            state__in=["invited", "ringing", "joined"]
        ).values_list("user_id", flat=True)
    )

    if active_participant_ids:
        do_send_group_call_event(
            realm,
            group_call,
            "participant_joined",
            active_participant_ids,
            extra_data={"joined_user_id": user.id},
        )

    logger.info(
        f"Group call {group_call.call_id}: User {user.id} joined, "
        f"notified {len(active_participant_ids)} active participants"
    )


def do_leave_group_call(realm: Realm, group_call: GroupCall, user: UserProfile) -> None:
    """
    Send participant left event to all active participants.

    Args:
        realm: The realm the call belongs to
        group_call: The GroupCall instance
        user: The user who left
    """
    # Get all active participants (excluding the one who left)
    active_participant_ids = list(
        group_call.participants.filter(
            state__in=["invited", "ringing", "joined"]
        )
        .exclude(user=user)
        .values_list("user_id", flat=True)
    )

    if active_participant_ids:
        do_send_group_call_event(
            realm,
            group_call,
            "participant_left",
            active_participant_ids,
            extra_data={"left_user_id": user.id},
        )

    logger.info(
        f"Group call {group_call.call_id}: User {user.id} left, "
        f"notified {len(active_participant_ids)} active participants"
    )


def do_decline_group_call(
    realm: Realm, group_call: GroupCall, user: UserProfile
) -> None:
    """
    Send participant declined event to host and active participants.

    Args:
        realm: The realm the call belongs to
        group_call: The GroupCall instance
        user: The user who declined
    """
    # Notify host and joined participants
    notify_ids = [group_call.host.id]
    joined_ids = list(
        group_call.participants.filter(state="joined")
        .exclude(user=user)
        .values_list("user_id", flat=True)
    )
    notify_ids.extend(joined_ids)

    # Remove duplicates (host might also be joined)
    notify_ids = list(set(notify_ids))

    if notify_ids:
        do_send_group_call_event(
            realm,
            group_call,
            "participant_declined",
            notify_ids,
            extra_data={"declined_user_id": user.id},
        )

    logger.info(
        f"Group call {group_call.call_id}: User {user.id} declined, "
        f"notified {len(notify_ids)} participants"
    )


def do_end_group_call(realm: Realm, group_call: GroupCall) -> None:
    """
    Send group call ended event to all participants.

    Args:
        realm: The realm the call belongs to
        group_call: The GroupCall instance being ended
    """
    # Notify all participants regardless of state
    all_participant_ids = list(
        group_call.participants.values_list("user_id", flat=True)
    )

    if all_participant_ids:
        do_send_group_call_event(
            realm,
            group_call,
            "ended",
            all_participant_ids,
        )

    logger.info(
        f"Group call {group_call.call_id} ended, "
        f"notified {len(all_participant_ids)} participants"
    )
