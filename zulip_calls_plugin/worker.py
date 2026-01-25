"""
Zulip Calls Plugin - Queue Workers

This module provides RabbitMQ queue workers for the Zulip Calls Plugin,
following Zulip's worker infrastructure patterns.

Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
"""

import logging
from collections.abc import Mapping
from typing import Any

from django.utils import timezone
from typing_extensions import override

from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("call_cleanup")
class CallCleanupWorker(QueueProcessingWorker):
    """
    Worker to clean up stale and missed calls.

    This worker is triggered periodically by the cleanup_calls management command
    and processes call cleanup events using the existing cleanup_stale_calls()
    function. It also handles group call participant cleanup.

    The worker processes events containing:
    - trigger_time: When the cleanup was triggered
    - scheduled_by: Optional identifier of what triggered the cleanup
    """

    @override
    def consume(self, event: Mapping[str, Any]) -> None:
        """
        Process a call cleanup event.

        This method:
        1. Cleans up stale 1-to-1 calls using cleanup_stale_calls()
        2. Cleans up stale group call participants
        3. Logs the results

        Args:
            event: Event dict containing trigger_time and optional metadata
        """
        from .views.calls import cleanup_stale_calls, cleanup_expired_queue_entries
        from .models import GroupCall, GroupCallParticipant
        from .actions import do_send_missed_call_event
        from datetime import timedelta

        trigger_time = event.get("trigger_time", timezone.now().isoformat())
        scheduled_by = event.get("scheduled_by", "periodic")

        logger.info(
            f"Call cleanup triggered at {trigger_time} by {scheduled_by}"
        )

        # Clean up stale 1-to-1 calls
        try:
            stale_call_count = cleanup_stale_calls()
            logger.info(f"Cleaned up {stale_call_count} stale 1-to-1 calls")
        except Exception as e:
            logger.error(f"Error cleaning up stale calls: {e}", exc_info=True)
            stale_call_count = 0

        # Clean up expired queue entries
        try:
            expired_queue_count = cleanup_expired_queue_entries()
            logger.info(f"Cleaned up {expired_queue_count} expired queue entries")
        except Exception as e:
            logger.error(f"Error cleaning up queue entries: {e}", exc_info=True)
            expired_queue_count = 0

        # Clean up stale group call participants
        try:
            group_call_cleanup_count = self._cleanup_stale_group_calls()
            logger.info(
                f"Cleaned up {group_call_cleanup_count} stale group call participants"
            )
        except Exception as e:
            logger.error(f"Error cleaning up group calls: {e}", exc_info=True)
            group_call_cleanup_count = 0

        logger.info(
            f"Call cleanup completed: {stale_call_count} calls, "
            f"{expired_queue_count} queue entries, "
            f"{group_call_cleanup_count} group participants"
        )

    def _cleanup_stale_group_calls(self) -> int:
        """
        Clean up stale group call participants.

        This handles:
        1. Participants who haven't sent heartbeat in 60 seconds (in joined state)
        2. Participants in invited/ringing state for more than 90 seconds (missed)
        3. Entire calls with no active participants for more than 10 minutes

        Returns:
            Number of participants cleaned up
        """
        from .models import GroupCall, GroupCallParticipant
        from .actions import do_leave_group_call, do_end_group_call
        from datetime import timedelta

        now = timezone.now()
        count = 0

        # Scenario 1: Heartbeat timeout for joined participants (60 seconds)
        heartbeat_threshold = now - timedelta(seconds=60)
        stale_joined = GroupCallParticipant.objects.filter(
            state="joined",
            last_heartbeat__lt=heartbeat_threshold,
            call__state="active",
        ).select_related("user", "call")

        for participant in stale_joined:
            participant.state = "left"
            participant.left_at = now
            participant.save(update_fields=["state", "left_at"])

            # Notify other participants
            try:
                do_leave_group_call(
                    participant.call.realm,
                    participant.call,
                    participant.user
                )
            except Exception as e:
                logger.error(
                    f"Failed to send leave event for participant {participant.user.id}: {e}"
                )

            count += 1
            logger.debug(
                f"Group call {participant.call.call_id}: "
                f"Participant {participant.user.id} timed out (no heartbeat)"
            )

        # Scenario 2: Missed invitations (90 seconds in invited/ringing state)
        invitation_threshold = now - timedelta(seconds=90)
        missed_invitations = GroupCallParticipant.objects.filter(
            state__in=["invited", "ringing"],
            invited_at__lt=invitation_threshold,
            call__state="active",
        ).select_related("user", "call")

        for participant in missed_invitations:
            participant.state = "missed"
            participant.save(update_fields=["state"])

            # Optionally notify host about missed participant
            # (not sending event to avoid spam, just updating state)
            count += 1
            logger.debug(
                f"Group call {participant.call.call_id}: "
                f"Participant {participant.user.id} missed invitation"
            )

        # Scenario 3: Auto-end calls with no active participants for 10 minutes
        # A call is considered stale if:
        # - It's still in active state
        # - It has no joined participants
        # - It was created more than 10 minutes ago
        call_stale_threshold = now - timedelta(minutes=10)
        stale_calls = GroupCall.objects.filter(
            state="active",
            created_at__lt=call_stale_threshold,
        )

        for group_call in stale_calls:
            # Check if it has any joined participants
            has_active = group_call.participants.filter(state="joined").exists()

            if not has_active:
                # No active participants, end the call
                group_call.state = "ended"
                group_call.ended_at = now
                group_call.save(update_fields=["state", "ended_at"])

                # Update all non-final participants to left
                group_call.participants.filter(
                    state__in=["invited", "ringing"]
                ).update(state="missed")

                # Send end event
                try:
                    do_end_group_call(group_call.realm, group_call)
                except Exception as e:
                    logger.error(
                        f"Failed to send end event for group call {group_call.call_id}: {e}"
                    )

                count += 1
                logger.info(
                    f"Auto-ended stale group call {group_call.call_id} "
                    f"(no active participants for >10 minutes)"
                )

        return count
