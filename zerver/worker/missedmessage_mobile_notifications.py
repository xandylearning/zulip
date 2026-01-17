# Documented in https://zulip.readthedocs.io/en/latest/subsystems/queuing.html
import logging
from typing import Any

from django.conf import settings
from typing_extensions import override

from zerver.lib.push_notifications import (
    handle_push_notification,
    handle_remove_push_notification,
    initialize_push_notifications,
)
from zerver.lib.push_registration import handle_register_push_device_to_bouncer
from zerver.lib.queue import retry_event
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.worker.base import QueueProcessingWorker, assign_queue

logger = logging.getLogger(__name__)


@assign_queue("missedmessage_mobile_notifications")
class PushNotificationsWorker(QueueProcessingWorker):
    # The use of aioapns in the backend means that we cannot use
    # SIGALRM to limit how long a consume takes, as SIGALRM does not
    # play well with asyncio.
    MAX_CONSUME_SECONDS = None

    @override
    def __init__(
        self,
        threaded: bool = False,
        disable_timeout: bool = False,
        worker_num: int | None = None,
    ) -> None:
        if settings.MOBILE_NOTIFICATIONS_SHARDS > 1 and worker_num is not None:  # nocoverage
            self.queue_name += f"_shard{worker_num}"
        super().__init__(threaded, disable_timeout, worker_num)

    @override
    def start(self) -> None:
        # initialize_push_notifications doesn't strictly do anything
        # beyond printing some logging warnings if push notifications
        # are not available in the current configuration.
        initialize_push_notifications()
        super().start()

    @override
    def consume(self, event: dict[str, Any]) -> None:
        try:
            event_type = event.get("type")
            user_profile_id = event.get("user_profile_id")

            # Enhanced logging for diagnostics
            if event_type == "register_push_device_to_bouncer":
                logger.info(
                    "Worker processing device registration to bouncer for user: %s",
                    event["payload"].get("user_profile_id", "unknown")
                )
                handle_register_push_device_to_bouncer(event["payload"])
            elif event_type == "remove":
                message_ids = event["message_ids"]
                logger.info(
                    "Worker processing push notification removal for user: %s, messages: %s",
                    user_profile_id, message_ids
                )
                handle_remove_push_notification(event["user_profile_id"], message_ids)
            else:
                # This is the main push notification processing path
                message_id = event.get("message_id", "unknown")
                trigger = event.get("trigger", "unknown")
                logger.info(
                    "Worker started processing push notification: user_id=%s, message_id=%s, trigger=%s, event_type=%s",
                    user_profile_id, message_id, trigger, event_type or "push_notification"
                )
                handle_push_notification(event["user_profile_id"], event)
                logger.info(
                    "Worker completed push notification processing: user_id=%s, message_id=%s",
                    user_profile_id, message_id
                )
        except PushNotificationBouncerRetryLaterError:

            def failure_processor(event: dict[str, Any]) -> None:
                # For register_push_device_to_bouncer events, user_profile_id is in payload
                if event.get("type") == "register_push_device_to_bouncer":
                    user_profile_id = event["payload"]["user_profile_id"]
                else:
                    # For other events (like push notifications), user_profile_id is at top level
                    user_profile_id = event["user_profile_id"]
                
                logger.warning(
                    "Maximum retries exceeded for trigger:%s event:push_notification",
                    user_profile_id,
                )

            retry_event(self.queue_name, event, failure_processor)
