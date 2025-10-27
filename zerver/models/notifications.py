from django.db import models
from django.utils.timezone import now as timezone_now
from typing_extensions import override

from zerver.models.realms import Realm
from zerver.models.streams import Stream
from zerver.models.users import UserProfile


class NotificationTemplate(models.Model):
    """Templates for broadcast notifications that admins can create and reuse."""

    name = models.CharField(max_length=100, db_index=True)
    content = models.TextField(help_text="Markdown content of the template")
    creator = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    created_time = models.DateTimeField(default=timezone_now, db_index=True)
    last_edit_time = models.DateTimeField(default=timezone_now)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = [["realm", "name"]]
        ordering = ["-last_edit_time"]

    @override
    def __str__(self) -> str:
        return f"{self.realm.string_id} / {self.name}"


class BroadcastNotification(models.Model):
    """Stores broadcast notifications sent by admins."""

    # Target type choices
    TARGET_USERS = "users"
    TARGET_CHANNELS = "channels"
    TARGET_BROADCAST = "broadcast"
    TARGET_TYPE_CHOICES = [
        (TARGET_USERS, "Specific Users"),
        (TARGET_CHANNELS, "Channels"),
        (TARGET_BROADCAST, "Broadcast All"),
    ]

    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    sender = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="sent_notifications"
    )
    template = models.ForeignKey(
        NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True
    )
    subject = models.CharField(max_length=255, help_text="Notification title/subject")
    content = models.TextField(help_text="Markdown content of the notification")
    attachment_paths = models.JSONField(
        default=list, help_text="List of file attachment paths"
    )
    sent_time = models.DateTimeField(default=timezone_now, db_index=True)
    target_type = models.CharField(
        max_length=20, choices=TARGET_TYPE_CHOICES, default=TARGET_USERS
    )
    target_ids = models.JSONField(
        default=list, help_text="List of user or channel IDs targeted"
    )

    class Meta:
        ordering = ["-sent_time"]

    @override
    def __str__(self) -> str:
        return f"{self.subject} - {self.sender.email} ({self.sent_time})"


class NotificationRecipient(models.Model):
    """Tracks individual recipients and their notification status."""

    # Status choices
    STATUS_QUEUED = "queued"
    STATUS_SENT = "sent"
    STATUS_DELIVERED = "delivered"
    STATUS_READ = "read"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_QUEUED, "Queued"),
        (STATUS_SENT, "Sent"),
        (STATUS_DELIVERED, "Delivered"),
        (STATUS_READ, "Read"),
        (STATUS_FAILED, "Failed"),
    ]

    notification = models.ForeignKey(
        BroadcastNotification, on_delete=models.CASCADE, related_name="recipients"
    )
    recipient_user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="received_notifications"
    )
    recipient_channel = models.ForeignKey(
        Stream, on_delete=models.SET_NULL, null=True, blank=True
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED, db_index=True
    )
    sent_time = models.DateTimeField(null=True, blank=True)
    delivered_time = models.DateTimeField(null=True, blank=True)
    read_time = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)
    message_id = models.IntegerField(
        null=True, blank=True, help_text="ID of the actual Zulip message sent"
    )

    class Meta:
        unique_together = [["notification", "recipient_user", "recipient_channel"]]
        ordering = ["-sent_time"]
        indexes = [
            models.Index(fields=["notification", "status"]),
            models.Index(fields=["recipient_user", "status"]),
        ]

    @override
    def __str__(self) -> str:
        channel_info = f" in {self.recipient_channel.name}" if self.recipient_channel else ""
        return f"{self.recipient_user.email}{channel_info} - {self.status}"

