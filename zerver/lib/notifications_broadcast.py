"""Helper functions for broadcast notification system."""

from typing import Any

from django.db import transaction
from django.utils.timezone import now as timezone_now

from zerver.actions.message_send import (
    internal_send_private_message,
    internal_send_stream_message,
)
from zerver.lib.exceptions import JsonableError
from zerver.models import (
    BroadcastNotification,
    Message,
    NotificationRecipient,
    Realm,
    Stream,
    UserProfile,
)


def send_broadcast_notification(
    sender: UserProfile,
    realm: Realm,
    subject: str,
    content: str,
    target_type: str,
    target_ids: list[int],
    attachment_paths: list[str] | None = None,
    template_id: int | None = None,
    media_content: dict | None = None,
) -> BroadcastNotification:
    """
    Send a broadcast notification to specified recipients.
    
    Args:
        sender: The admin/owner sending the notification
        realm: The realm context
        subject: Notification subject/title
        content: Markdown content of the notification
        target_type: Type of targets ('users', 'channels', 'broadcast')
        target_ids: List of user or channel IDs
        attachment_paths: Optional list of file attachment paths
        template_id: Optional template ID used
        media_content: Optional rich media content for templates
        
    Returns:
        BroadcastNotification object
    """
    if attachment_paths is None:
        attachment_paths = []

    # Create the broadcast notification record
    with transaction.atomic():
        notification = BroadcastNotification.objects.create(
            realm=realm,
            sender=sender,
            template_id=template_id,
            subject=subject,
            content=content,
            attachment_paths=attachment_paths,
            target_type=target_type,
            target_ids=target_ids,
            media_content=media_content or {},
        )

        # Determine recipients based on target type
        # Use a dict to track unique (user_id, channel_id) combinations to prevent duplicates
        unique_recipients = {}
        
        if target_type == BroadcastNotification.TARGET_BROADCAST:
            # Send to all active users in the realm
            users = UserProfile.objects.filter(
                realm=realm, is_active=True, is_bot=False
            ).select_related("realm")
            for user in users:
                # For broadcast, channel_id is None
                key = (user.id, None)
                if key not in unique_recipients:
                    unique_recipients[key] = NotificationRecipient(
                        notification=notification,
                        recipient_user=user,
                        status=NotificationRecipient.STATUS_QUEUED,
                    )
                
        elif target_type == BroadcastNotification.TARGET_USERS:
            # Send to specific users - deduplicate target_ids first
            unique_target_ids = list(set(target_ids))
            users = UserProfile.objects.filter(
                realm=realm, id__in=unique_target_ids, is_active=True
            ).select_related("realm")
            for user in users:
                # For users, channel_id is None
                key = (user.id, None)
                if key not in unique_recipients:
                    unique_recipients[key] = NotificationRecipient(
                        notification=notification,
                        recipient_user=user,
                        status=NotificationRecipient.STATUS_QUEUED,
                    )
                
        elif target_type == BroadcastNotification.TARGET_CHANNELS:
            # Send to channels - create notification for all subscribers
            # Deduplicate target_ids first to prevent duplicate channel processing
            unique_target_ids = list(set(target_ids))
            channels = Stream.objects.filter(realm=realm, id__in=unique_target_ids)
            for channel in channels:
                # Get all subscribers of the channel
                subscribers = UserProfile.objects.filter(
                    subscription__recipient__type_id=channel.id,
                    subscription__active=True,
                    is_active=True,
                ).select_related("realm")
                for user in subscribers:
                    # For channels, use channel.id as the channel_id
                    key = (user.id, channel.id)
                    if key not in unique_recipients:
                        unique_recipients[key] = NotificationRecipient(
                            notification=notification,
                            recipient_user=user,
                            recipient_channel=channel,
                            status=NotificationRecipient.STATUS_QUEUED,
                        )
        
        # Convert dict values to list for bulk_create
        recipients_to_create = list(unique_recipients.values())

        # Bulk create recipients
        NotificationRecipient.objects.bulk_create(recipients_to_create)

    # Send actual messages
    _send_notification_messages(notification)
    
    return notification


def _build_rich_media_content(notification: BroadcastNotification) -> str:
    """Build formatted content from rich media template structure and media content."""
    if not notification.template or not notification.template.template_structure:
        return notification.content
    
    template_structure = notification.template.template_structure
    media_content = notification.media_content or {}
    content_parts = []
    
    # Process blocks in order
    blocks = template_structure.get("blocks", [])
    for block in blocks:
        block_type = block.get("type")
        block_id = block.get("id")
        
        if block_type == "text":
            # Text blocks - use content from media_content or fallback to block text
            text_content = media_content.get(block_id, block.get("text", ""))
            if text_content.strip():
                content_parts.append(text_content)
                
        elif block_type == "image":
            # Image blocks - add image link
            image_url = media_content.get(block_id, "")
            if image_url:
                content_parts.append(f"![Image]({image_url})")
                
        elif block_type == "video":
            # Video blocks - add video link
            video_url = media_content.get(block_id, "")
            if video_url:
                content_parts.append(f"[Video]({video_url})")
                
        elif block_type == "button":
            # Button blocks - add button as link
            button_text = block.get("text", "Button")
            button_url = media_content.get(block_id, "")
            if button_url:
                content_parts.append(f"[{button_text}]({button_url})")
    
    # Join all content parts with line breaks
    return "\n\n".join(content_parts) if content_parts else notification.content


def _send_notification_messages(notification: BroadcastNotification) -> None:
    """Send actual Zulip messages for a broadcast notification."""
    sender = notification.sender
    
    # Format the message content with subject
    formatted_content = f"**{notification.subject}**\n\n"
    
    # Check if this is a rich media template
    if notification.template and notification.template.template_type == "rich_media":
        # Build content from template structure and media_content
        formatted_content += _build_rich_media_content(notification)
    else:
        # Use standard content
        formatted_content += notification.content
    
    # Add attachment links if present
    if notification.attachment_paths:
        formatted_content += "\n\n**Attachments:**\n"
        for path in notification.attachment_paths:
            formatted_content += f"- [File]({path})\n"
    
    recipients = NotificationRecipient.objects.filter(
        notification=notification, status=NotificationRecipient.STATUS_QUEUED
    ).select_related("recipient_user", "recipient_channel")
    
    for recipient in recipients:
        try:
            # Send as direct message or channel message
            if recipient.recipient_channel:
                # Send to channel
                message_id = internal_send_stream_message(
                    sender=sender,
                    stream=recipient.recipient_channel,
                    topic_name="Broadcast Notification",
                    content=formatted_content,
                )
            else:
                # Send as DM
                message_id = internal_send_private_message(
                    sender=sender,
                    recipient_user=recipient.recipient_user,
                    content=formatted_content,
                )
            
            if message_id:
                # Store template data in the message for rich rendering
                if notification.template and notification.template.template_type == "rich_media":
                    try:
                        message = Message.objects.get(id=message_id)
                        message.broadcast_template_data = {
                            "template_id": notification.template.id,
                            "template_structure": notification.template.template_structure,
                            "media_content": notification.media_content,
                            "message_type": "broadcast_notification",
                            "broadcast_notification_id": notification.id,
                        }
                        message.save(update_fields=["broadcast_template_data"])
                    except Message.DoesNotExist:
                        pass  # Message not found, skip template data storage

                recipient.message_id = message_id
                recipient.status = NotificationRecipient.STATUS_SENT
                recipient.sent_time = timezone_now()
                recipient.save(update_fields=["message_id", "status", "sent_time"])
            else:
                recipient.status = NotificationRecipient.STATUS_FAILED
                recipient.error_message = "Failed to send message"
                recipient.save(update_fields=["status", "error_message"])
                
        except Exception as e:
            recipient.status = NotificationRecipient.STATUS_FAILED
            recipient.error_message = str(e)
            recipient.save(update_fields=["status", "error_message"])


def track_notification_delivery(recipient_id: int, status: str) -> None:
    """
    Update the delivery status of a notification recipient.
    
    Args:
        recipient_id: ID of the NotificationRecipient
        status: New status value
    """
    try:
        recipient = NotificationRecipient.objects.get(id=recipient_id)
        recipient.status = status
        
        if status == NotificationRecipient.STATUS_DELIVERED:
            recipient.delivered_time = timezone_now()
        elif status == NotificationRecipient.STATUS_READ:
            if not recipient.read_time:
                recipient.read_time = timezone_now()
                
        recipient.save()
    except NotificationRecipient.DoesNotExist:
        pass


def get_notification_statistics(notification_id: int) -> dict[str, Any]:
    """
    Get aggregated statistics for a broadcast notification.
    
    Args:
        notification_id: ID of the BroadcastNotification
        
    Returns:
        Dictionary with statistics
    """
    recipients = NotificationRecipient.objects.filter(notification_id=notification_id)
    
    total = recipients.count()
    status_counts = {
        "queued": recipients.filter(status=NotificationRecipient.STATUS_QUEUED).count(),
        "sent": recipients.filter(status=NotificationRecipient.STATUS_SENT).count(),
        "delivered": recipients.filter(status=NotificationRecipient.STATUS_DELIVERED).count(),
        "read": recipients.filter(status=NotificationRecipient.STATUS_READ).count(),
        "failed": recipients.filter(status=NotificationRecipient.STATUS_FAILED).count(),
    }
    
    return {
        "total_recipients": total,
        "status_breakdown": status_counts,
        "success_rate": (status_counts["sent"] + status_counts["delivered"] + status_counts["read"]) / total * 100 if total > 0 else 0,
        "failure_rate": status_counts["failed"] / total * 100 if total > 0 else 0,
    }

