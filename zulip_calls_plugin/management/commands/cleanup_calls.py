"""
Management command to trigger call cleanup via the RabbitMQ queue.

This command should be run periodically (e.g., every 30 seconds) via cron or systemd timer.
It enqueues a cleanup event that will be processed by the CallCleanupWorker.

Example crontab entry (run every 30 seconds):
    * * * * * cd /home/zulip/deployments/current && ./manage.py cleanup_calls
    * * * * * sleep 30 && cd /home/zulip/deployments/current && ./manage.py cleanup_calls

Or using systemd timer (preferred for production):
    See zulip_calls_plugin/systemd/ for timer configuration.
"""

import logging
from datetime import timedelta
from typing import Any

from django.utils import timezone
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand, abort_unless_locked
from zerver.lib.queue import queue_json_publish
from zulip_calls_plugin.models import Call

logger = logging.getLogger(__name__)


class Command(ZulipBaseCommand):
    help = """Enqueue call cleanup events for processing stale and missed calls.

This command triggers the CallCleanupWorker to clean up:
- Stale 1-to-1 calls (missed, timed out, network failures)
- Expired call queue entries
- Stale group call participants (missed invitations, heartbeat timeouts)
- Auto-end group calls with no active participants

Run this periodically (recommended: every 30 seconds) via cron or systemd timer.

For old call cleanup, use --cleanup-old-calls flag.
"""

    def add_arguments(self, parser):
        parser.add_argument(
            '--cleanup-old-calls',
            action='store_true',
            help='Also cleanup ended calls older than specified days (runs synchronously)'
        )
        parser.add_argument(
            '--old-calls-days',
            type=int,
            default=30,
            help='Delete ended calls older than this many days (requires --cleanup-old-calls)'
        )

    @override
    @abort_unless_locked
    def handle(self, *args: Any, **options: Any) -> None:
        """
        Enqueue a call cleanup event.

        The @abort_unless_locked decorator ensures only one instance runs at a time,
        preventing duplicate cleanup operations.
        """
        current_time = timezone.now()
        cleanup_old = options.get('cleanup_old_calls', False)
        old_calls_days = options.get('old_calls_days', 30)

        # Enqueue the periodic cleanup event to the call_cleanup queue
        event = {
            "trigger_time": current_time.isoformat(),
            "scheduled_by": "management_command",
        }

        queue_json_publish("call_cleanup", event)

        if options.get("verbosity", 1) >= 1:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Enqueued call cleanup event at {current_time.isoformat()}"
                )
            )

        # Optional: Cleanup old ended calls (runs synchronously, not via queue)
        # This is a separate operation from the periodic cleanup
        if cleanup_old:
            old_cutoff = current_time - timedelta(days=old_calls_days)
            old_calls = Call.objects.filter(
                state__in=['ended', 'rejected', 'timeout', 'missed', 'cancelled'],
                ended_at__lt=old_cutoff
            )

            old_count = old_calls.count()
            if old_count > 0:
                old_calls.delete()
                logger.info(f"Deleted {old_count} old call records older than {old_calls_days} days")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Deleted {old_count} old call records older than {old_calls_days} days"
                    )
                )
            else:
                self.stdout.write("No old call records to delete")

        # Report current stats (optional, only in verbose mode)
        if options.get("verbosity", 1) >= 2:
            active_calls = Call.objects.filter(
                state__in=['calling', 'ringing', 'accepted']
            ).count()
            self.stdout.write(f"Current active calls: {active_calls}")