from typing import Any

from django.db import transaction
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.models import Recipient, Subscription, UserProfile


class Command(ZulipBaseCommand):
    help = "Fix users with missing recipient records"

    @override
    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be fixed without making changes",
        )

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        dry_run = options["dry_run"]

        # Find all users without a recipient
        users_without_recipient = UserProfile.objects.filter(recipient_id=None)
        count = users_without_recipient.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No users with missing recipients found."))
            return

        self.stdout.write(f"Found {count} users with missing recipients:")
        for user in users_without_recipient:
            self.stdout.write(f"  - {user.id}: {user.delivery_email}")

        if dry_run:
            self.stdout.write(self.style.WARNING("\nDry run - no changes made."))
            return

        fixed_count = 0
        for user in users_without_recipient:
            with transaction.atomic():
                # Create the recipient
                recipient, created = Recipient.objects.get_or_create(
                    type_id=user.id,
                    type=Recipient.PERSONAL,
                )

                # Link recipient to user
                user.recipient = recipient
                user.save(update_fields=["recipient"])

                # Create subscription if missing
                Subscription.objects.get_or_create(
                    user_profile=user,
                    recipient=recipient,
                    defaults={"is_user_active": user.is_active},
                )

                fixed_count += 1
                self.stdout.write(f"Fixed: {user.delivery_email}")

        self.stdout.write(
            self.style.SUCCESS(f"\nSuccessfully fixed {fixed_count} users.")
        )
