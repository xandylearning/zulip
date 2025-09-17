from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from zulip_calls_plugin.models import Call
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = "Clean up old and timed-out calls"

    def add_arguments(self, parser):
        parser.add_argument(
            '--timeout-minutes',
            type=int,
            default=5,
            help='Timeout calls older than this many minutes'
        )
        parser.add_argument(
            '--cleanup-old-calls',
            action='store_true',
            help='Also cleanup ended calls older than specified days'
        )
        parser.add_argument(
            '--old-calls-days',
            type=int,
            default=30,
            help='Delete ended calls older than this many days'
        )

    def handle(self, *args, **options):
        timeout_minutes = options['timeout_minutes']
        cleanup_old = options['cleanup_old_calls']
        old_calls_days = options['old_calls_days']

        cutoff_time = timezone.now() - timedelta(minutes=timeout_minutes)

        # Mark old calling/ringing calls as timed out
        timed_out_calls = Call.objects.filter(
            state__in=['calling', 'ringing'],
            created_at__lt=cutoff_time
        )

        timeout_count = timed_out_calls.count()
        timed_out_calls.update(state='timeout', ended_at=timezone.now())

        logger.info(f"Marked {timeout_count} calls as timed out")
        self.stdout.write(
            self.style.SUCCESS(f"Successfully marked {timeout_count} calls as timed out")
        )

        # Cleanup old ended calls if requested
        if cleanup_old:
            old_cutoff = timezone.now() - timedelta(days=old_calls_days)
            old_calls = Call.objects.filter(
                state__in=['ended', 'rejected', 'timeout', 'missed', 'cancelled'],
                ended_at__lt=old_cutoff
            )

            old_count = old_calls.count()
            old_calls.delete()

            logger.info(f"Deleted {old_count} old call records")
            self.stdout.write(
                self.style.SUCCESS(f"Successfully deleted {old_count} old call records")
            )

        # Report current active calls
        active_calls = Call.objects.filter(
            state__in=['calling', 'ringing', 'accepted']
        ).count()

        self.stdout.write(f"Current active calls: {active_calls}")