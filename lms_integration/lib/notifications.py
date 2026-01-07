"""
Notification System for LMS Integration.
Handles email notifications for users with placeholder email addresses.
"""

import logging
from typing import List, Optional, Dict, Any

from django.conf import settings

from zerver.models import UserProfile, Message, Recipient
from zerver.lib.email_notifications import (
    send_email_notifications_to_user,
    enqueue_welcome_emails,
    send_account_registered_email,
)
from zerver.lib.queue import queue_json_publish

# Import LMS integration email utilities
from .email_utils import (
    should_send_email_notification,
    should_show_inapp_notifications,
    should_log_notification_attempts,
    log_placeholder_email_attempt,
    is_placeholder_email,
)

logger = logging.getLogger(__name__)


class LMSNotificationHandler:
    """
    Handles notifications for LMS integration users, with special handling for placeholder emails.
    """

    @staticmethod
    def send_email_notification(
        user_profile: UserProfile,
        notification_type: str,
        context: Dict[str, Any],
        template_prefix: Optional[str] = None
    ) -> bool:
        """
        Send email notification to a user, with placeholder email handling.

        Args:
            user_profile: The UserProfile to notify
            notification_type: Type of notification (e.g., "message", "mention", "welcome")
            context: Template context for the notification
            template_prefix: Optional template prefix for email template selection

        Returns:
            True if notification was sent/queued, False if blocked due to placeholder email
        """
        # Check if we should send email notifications to this user
        if not should_send_email_notification(user_profile):
            # Log the blocked attempt if configured
            if should_log_notification_attempts(user_profile):
                log_placeholder_email_attempt(
                    user_profile,
                    f"email_notification_{notification_type}",
                    f"Blocked email notification of type '{notification_type}' to placeholder email"
                )

            logger.info(
                f"Blocked email notification '{notification_type}' to user {user_profile.full_name} "
                f"with placeholder email {user_profile.delivery_email}"
            )
            return False

        # For users with real emails, send normally
        try:
            # Use the appropriate Zulip notification function based on type
            if notification_type == "welcome":
                enqueue_welcome_emails(user_profile, realm_creation=False)
            elif notification_type == "account_registered":
                send_account_registered_email(user_profile, template_prefix or "zerver/emails/account_registered")
            else:
                # For other types, queue a generic email notification
                queue_json_publish(
                    "email_notifications",
                    {
                        "user_profile_id": user_profile.id,
                        "notification_type": notification_type,
                        "context": context,
                        "template_prefix": template_prefix,
                    },
                    lambda event: None,
                )

            logger.debug(f"Sent email notification '{notification_type}' to {user_profile.delivery_email}")
            return True

        except Exception as e:
            logger.error(
                f"Error sending email notification '{notification_type}' to {user_profile.delivery_email}: {e}"
            )
            return False

    @staticmethod
    def send_message_notification(
        user_profile: UserProfile,
        message: Message,
        mentioned: bool = False,
        wildcard_mentioned: bool = False
    ) -> Dict[str, bool]:
        """
        Send message notification to a user, with placeholder email handling.

        Args:
            user_profile: The UserProfile to notify
            message: The message that triggered the notification
            mentioned: Whether the user was mentioned
            wildcard_mentioned: Whether the user was mentioned via wildcard

        Returns:
            Dictionary indicating which notification types were sent
        """
        result = {
            "email_sent": False,
            "push_sent": False,
            "in_app_shown": True,  # In-app notifications are always shown
        }

        # Check if we should send email notifications to this user
        if should_send_email_notification(user_profile):
            try:
                # Send email notification for the message
                send_email_notifications_to_user(
                    user_profile,
                    [message],
                    mentioned=mentioned,
                    wildcard_mentioned=wildcard_mentioned,
                )
                result["email_sent"] = True
                logger.debug(f"Sent message email notification to {user_profile.delivery_email}")

            except Exception as e:
                logger.error(
                    f"Error sending message email notification to {user_profile.delivery_email}: {e}"
                )
        else:
            # Log the blocked attempt if configured
            if should_log_notification_attempts(user_profile):
                notification_context = f"message_id={message.id}, mentioned={mentioned}, wildcard={wildcard_mentioned}"
                log_placeholder_email_attempt(
                    user_profile,
                    "message_notification",
                    f"Blocked message email notification ({notification_context})"
                )

        # Check if we should show in-app notifications
        if not should_show_inapp_notifications(user_profile):
            result["in_app_shown"] = False

        # Push notifications are handled separately by Zulip's push notification system
        # They don't depend on email addresses, so we don't need to block them
        result["push_sent"] = True  # Assume push notifications work normally

        return result

    @staticmethod
    def bulk_send_notifications(
        user_profiles: List[UserProfile],
        notification_type: str,
        context: Dict[str, Any],
        template_prefix: Optional[str] = None
    ) -> Dict[str, int]:
        """
        Send notifications to multiple users, with placeholder email handling.

        Args:
            user_profiles: List of UserProfiles to notify
            notification_type: Type of notification
            context: Template context for the notification
            template_prefix: Optional template prefix

        Returns:
            Dictionary with counts of sent, blocked, and failed notifications
        """
        stats = {
            "sent": 0,
            "blocked": 0,
            "failed": 0,
        }

        for user_profile in user_profiles:
            try:
                sent = LMSNotificationHandler.send_email_notification(
                    user_profile,
                    notification_type,
                    context,
                    template_prefix
                )

                if sent:
                    stats["sent"] += 1
                else:
                    stats["blocked"] += 1

            except Exception as e:
                stats["failed"] += 1
                logger.error(
                    f"Error sending bulk notification to {user_profile.delivery_email}: {e}"
                )

        logger.info(
            f"Bulk notification '{notification_type}' completed: "
            f"{stats['sent']} sent, {stats['blocked']} blocked (placeholder emails), "
            f"{stats['failed']} failed"
        )

        return stats

    @staticmethod
    def send_admin_notification(
        admin_users: List[UserProfile],
        subject: str,
        message: str,
        notification_type: str = "admin_notification"
    ) -> Dict[str, int]:
        """
        Send administrative notifications to admin users.

        Args:
            admin_users: List of admin UserProfiles
            subject: Email subject
            message: Email message content
            notification_type: Type of admin notification

        Returns:
            Dictionary with notification statistics
        """
        context = {
            "subject": subject,
            "message": message,
            "notification_type": notification_type,
        }

        return LMSNotificationHandler.bulk_send_notifications(
            admin_users,
            notification_type,
            context
        )

    @staticmethod
    def get_notification_stats(realm) -> Dict[str, Any]:
        """
        Get statistics about notification capabilities for users in a realm.

        Args:
            realm: The Zulip realm to analyze

        Returns:
            Dictionary with notification statistics
        """
        from .email_utils import get_placeholder_email_stats

        # Get placeholder email stats
        placeholder_stats = get_placeholder_email_stats(realm)

        # Calculate notification impact
        notification_stats = {
            "total_users": placeholder_stats["total_users"],
            "users_with_email_notifications": placeholder_stats["real_email_users"],
            "users_without_email_notifications": placeholder_stats["placeholder_users"],
            "email_notification_coverage": round(
                (placeholder_stats["real_email_users"] / placeholder_stats["total_users"] * 100)
                if placeholder_stats["total_users"] > 0 else 0, 1
            ),
            "placeholder_percentage": placeholder_stats["placeholder_percentage"],
        }

        return notification_stats

    @staticmethod
    def notify_admin_of_placeholder_users(realm, placeholder_user_count: int) -> None:
        """
        Notify realm administrators about users with placeholder emails.

        Args:
            realm: The Zulip realm
            placeholder_user_count: Number of users with placeholder emails
        """
        # Get realm administrators
        admin_users = UserProfile.objects.filter(
            realm=realm,
            role__in=[UserProfile.ROLE_REALM_ADMINISTRATOR, UserProfile.ROLE_REALM_OWNER],
            is_active=True
        )

        # Filter out admins with placeholder emails to avoid notification loops
        real_email_admins = [
            admin for admin in admin_users
            if should_send_email_notification(admin)
        ]

        if not real_email_admins:
            logger.warning(
                f"No administrators with real email addresses found in realm {realm.string_id}. "
                f"Cannot notify about {placeholder_user_count} users with placeholder emails."
            )
            return

        subject = f"LMS Integration: {placeholder_user_count} users with placeholder emails"
        message = (
            f"The LMS integration has created {placeholder_user_count} users with placeholder email addresses. "
            f"These users will not receive email notifications but can still use Zulip normally. "
            f"\n\nTo enable email notifications for these users, update their email addresses in the LMS "
            f"and run a user sync, or update them manually in Zulip admin settings."
        )

        stats = LMSNotificationHandler.send_admin_notification(
            real_email_admins,
            subject,
            message,
            "lms_placeholder_email_report"
        )

        logger.info(
            f"Notified {stats['sent']} administrators about placeholder email users. "
            f"Blocked: {stats['blocked']}, Failed: {stats['failed']}"
        )


def patch_zulip_notifications():
    """
    Monkey patch Zulip's notification functions to use LMS notification handler.
    This ensures that placeholder email handling is applied throughout Zulip.
    """
    try:
        # Import Zulip's notification functions
        from zerver.lib import email_notifications
        from zerver.lib import push_notifications

        # Store original functions
        original_send_email_notifications = email_notifications.send_email_notifications_to_user
        original_send_welcome_emails = email_notifications.enqueue_welcome_emails

        def patched_send_email_notifications_to_user(user_profile, messages, **kwargs):
            """Patched version that checks for placeholder emails."""
            if not should_send_email_notification(user_profile):
                if should_log_notification_attempts(user_profile):
                    log_placeholder_email_attempt(
                        user_profile,
                        "email_notifications_patch",
                        f"Blocked email notifications for {len(messages)} messages"
                    )
                return

            return original_send_email_notifications(user_profile, messages, **kwargs)

        def patched_enqueue_welcome_emails(user_profile, **kwargs):
            """Patched version that checks for placeholder emails."""
            if not should_send_email_notification(user_profile):
                if should_log_notification_attempts(user_profile):
                    log_placeholder_email_attempt(
                        user_profile,
                        "welcome_email_patch",
                        "Blocked welcome email"
                    )
                return

            return original_send_welcome_emails(user_profile, **kwargs)

        # Apply patches
        email_notifications.send_email_notifications_to_user = patched_send_email_notifications_to_user
        email_notifications.enqueue_welcome_emails = patched_enqueue_welcome_emails

        logger.info("Successfully patched Zulip notification functions for LMS integration")

    except ImportError as e:
        logger.warning(f"Could not patch Zulip notification functions: {e}")
    except Exception as e:
        logger.error(f"Error patching Zulip notification functions: {e}")


# Optional: Auto-apply patches on module import
# Uncomment the line below if you want patches to be applied automatically
# patch_zulip_notifications()