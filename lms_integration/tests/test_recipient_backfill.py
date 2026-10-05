"""
Regression tests for the LMS user-sync recipient bug.

Background
----------
The LMS bulk user-sync path (``UserSync._bulk_create_lms_users``) could leave
``UserProfile.recipient_id`` NULL for synced users. When someone later tried to
send a 1:1 direct message to such a user, ``recipient_for_user_profiles`` built
an in-memory ``Recipient`` with ``id=None`` (from the NULL ``recipient_id``),
and ``Message.objects.bulk_create`` rejected it with::

    ValueError: bulk_create() prohibited to prevent data loss due to
    unsaved related object 'recipient'.

These tests cover both halves of the fix:

* ``DMToUserWithMissingRecipientTest`` reproduces the production crash and
  verifies that a user with a personal Recipient can receive DMs.
* ``BackfillMissingRecipientsMigrationTest`` verifies that the data-repair
  routine restores ``recipient_id`` for already-broken users.
"""

from django.core.exceptions import ObjectDoesNotExist

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Recipient, Subscription, UserProfile


class DMToUserWithMissingRecipientTest(ZulipTestCase):
    """Sending a DM must work even after data was once corrupted, and must
    fail loudly while it is corrupted (so we never silently regress)."""

    def _break_recipient(self, user: UserProfile) -> None:
        """Simulate the corrupt state produced by the old bulk-sync path:
        a UserProfile with no personal Recipient back-reference."""
        Subscription.objects.filter(
            user_profile=user,
            recipient__type=Recipient.PERSONAL,
            recipient__type_id=user.id,
        ).delete()
        Recipient.objects.filter(type=Recipient.PERSONAL, type_id=user.id).delete()
        user.recipient = None
        user.save(update_fields=["recipient"])

    def test_dm_to_user_with_null_recipient_fails(self) -> None:
        """Reproduces the production bug: a DM target with NULL recipient_id
        causes bulk_create to reject an unsaved Recipient."""
        sender = self.example_user("hamlet")
        receiver = self.example_user("cordelia")
        self._break_recipient(receiver)

        receiver.refresh_from_db()
        self.assertIsNone(receiver.recipient_id)

        # The send path constructs Recipient(id=receiver.recipient_id=None),
        # which bulk_create refuses.
        with self.assertRaises(ValueError):
            self.send_personal_message(sender, receiver, content="hello")

    def test_dm_to_user_with_recipient_succeeds(self) -> None:
        """Once the recipient back-reference exists, DMs send normally.
        This is the post-fix / post-backfill state."""
        sender = self.example_user("hamlet")
        receiver = self.example_user("cordelia")

        # Sanity: the default test users already have a personal Recipient.
        receiver.refresh_from_db()
        self.assertIsNotNone(receiver.recipient_id)

        message_id = self.send_personal_message(sender, receiver, content="hello")
        self.assertIsNotNone(message_id)


class BackfillMissingRecipientsTest(ZulipTestCase):
    """Directly exercises the backfill routine used by the data migration."""

    def _break_recipient(self, user: UserProfile) -> None:
        Subscription.objects.filter(
            user_profile=user,
            recipient__type=Recipient.PERSONAL,
            recipient__type_id=user.id,
        ).delete()
        Recipient.objects.filter(type=Recipient.PERSONAL, type_id=user.id).delete()
        user.recipient = None
        user.save(update_fields=["recipient"])

    def test_backfill_restores_recipient_and_subscription(self) -> None:
        from lms_integration.lib.recipient_backfill import (
            backfill_missing_personal_recipients,
        )

        broken = self.example_user("cordelia")
        self._break_recipient(broken)
        broken.refresh_from_db()
        self.assertIsNone(broken.recipient_id)

        repaired_count = backfill_missing_personal_recipients(
            UserProfile, Recipient, Subscription
        )
        self.assertGreaterEqual(repaired_count, 1)

        broken.refresh_from_db()
        self.assertIsNotNone(broken.recipient_id)

        # The recipient must be the canonical personal recipient for this user.
        recipient = broken.recipient
        self.assertEqual(recipient.type, Recipient.PERSONAL)
        self.assertEqual(recipient.type_id, broken.id)

        # A matching personal subscription must exist.
        self.assertTrue(
            Subscription.objects.filter(
                user_profile=broken, recipient=recipient
            ).exists()
        )

    def test_backfill_is_idempotent(self) -> None:
        from lms_integration.lib.recipient_backfill import (
            backfill_missing_personal_recipients,
        )

        broken = self.example_user("cordelia")
        self._break_recipient(broken)

        first = backfill_missing_personal_recipients(
            UserProfile, Recipient, Subscription
        )
        self.assertGreaterEqual(first, 1)

        # Running again repairs nothing new.
        second = backfill_missing_personal_recipients(
            UserProfile, Recipient, Subscription
        )
        self.assertEqual(second, 0)

    def test_backfill_after_dm_send_works(self) -> None:
        """End-to-end: break, backfill, then DM must succeed."""
        sender = self.example_user("hamlet")
        receiver = self.example_user("cordelia")
        self._break_recipient(receiver)

        from lms_integration.lib.recipient_backfill import (
            backfill_missing_personal_recipients,
        )

        backfill_missing_personal_recipients(UserProfile, Recipient, Subscription)

        message_id = self.send_personal_message(sender, receiver, content="hi again")
        self.assertIsNotNone(message_id)
