import argparse
from typing import Any
from typing_extensions import override

from zerver.lib.management import ZulipBaseCommand
from zerver.models import UserProfile, RealmUserDefault, ScheduledEmail, Realm
from zerver.lib.send_email import clear_scheduled_emails

class Command(ZulipBaseCommand):
    help = """Disable email notifications for messages (offline, stream, followed topics, digest) for all users."""

    @override
    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        self.add_realm_args(parser, help="The realm to update. If not specified, updates all realms.")

    @override
    def handle(self, *args: Any, **options: Any) -> None:
        realm = self.get_realm(options)
        
        if realm:
            realms = [realm]
        else:
            realms = list(Realm.objects.all())

        for realm in realms:
            print(f"Processing realm: {realm.string_id}")
            
            # Update Defaults for new users
            defaults, created = RealmUserDefault.objects.get_or_create(realm=realm)
            defaults.enable_offline_email_notifications = False
            defaults.enable_stream_email_notifications = False
            defaults.enable_followed_topic_email_notifications = False
            defaults.enable_digest_emails = False
            defaults.save()
            print(f"  Updated default settings for new users.")

            # Update Existing Users
            # We filter for human users (is_bot=False) and active users.
            # Inactive users might not need updates, but it doesn't hurt.
            users = UserProfile.objects.filter(realm=realm, is_bot=False, is_active=True)
            count = users.count()
            print(f"  Updating {count} active users...")

            # Bulk update
            users.update(
                enable_offline_email_notifications=False,
                enable_stream_email_notifications=False,
                enable_followed_topic_email_notifications=False,
                enable_digest_emails=False
            )
            
            # Clear scheduled digests
            # This is important because we just disabled digests, so pending ones should be removed.
            user_ids = list(users.values_list('id', flat=True))
            
            chunk_size = 1000
            if user_ids:
                print(f"  Clearing scheduled digest emails for {len(user_ids)} users...")
                for i in range(0, len(user_ids), chunk_size):
                    chunk = user_ids[i:i + chunk_size]
                    clear_scheduled_emails(chunk, ScheduledEmail.DIGEST)
            
            print(f"  Done with realm {realm.string_id}.")
