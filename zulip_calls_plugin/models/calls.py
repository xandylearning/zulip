import uuid
from django.db import models
from django.utils import timezone
from typing_extensions import override

# Import Zulip models - these will be available when plugin is installed
from zerver.models import Realm, UserProfile


class Call(models.Model):
    """Model for managing video/voice calls"""

    CALL_TYPES = [
        ("video", "Video Call"),
        ("audio", "Audio Call"),
    ]

    CALL_STATES = [
        ("calling", "Calling"),
        ("ringing", "Ringing"),
        ("accepted", "Accepted"),
        ("rejected", "Rejected"),
        ("timeout", "Timeout"),
        ("ended", "Ended"),
        ("missed", "Missed"),
        ("cancelled", "Cancelled"),
    ]

    call_id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_index=True)
    call_type = models.CharField(max_length=10, choices=CALL_TYPES)
    state = models.CharField(max_length=20, choices=CALL_STATES, default="calling")

    # Participants (renamed for consistency with guide)
    sender = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="calls_sent"
    )
    receiver = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="calls_received"
    )

    # Call details
    jitsi_room_name = models.CharField(max_length=255)
    jitsi_room_url = models.URLField()
    jitsi_room_id = models.CharField(max_length=100, null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    answered_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        app_label = "zulip_calls_plugin"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sender", "receiver"], name="call_participants_idx"),
            models.Index(fields=["state"], name="call_status_idx"),
            models.Index(fields=["created_at"], name="call_created_at_idx"),
        ]

    @override
    def __str__(self) -> str:
        return f"Call {self.call_id}: {self.sender.full_name} -> {self.receiver.full_name}"

    @property
    def duration(self):
        """Calculate call duration if call was answered and ended"""
        if self.answered_at and self.ended_at:
            return self.ended_at - self.answered_at
        return None

    def is_active(self):
        """Check if call is currently active"""
        return self.state in ['calling', 'ringing', 'accepted']

    def can_be_answered(self):
        """Check if call can still be answered"""
        # Allow answering calls that are calling, ringing, or even rejected
        # (in case the user wants to change their mind quickly)
        return self.state in ['calling', 'ringing', 'rejected']

    # Keep backward compatibility aliases
    @property
    def initiator(self):
        return self.sender

    @property
    def recipient(self):
        return self.receiver

    @property
    def started_at(self):
        return self.answered_at


class CallEvent(models.Model):
    """Model for tracking call events and history"""

    EVENT_TYPES = [
        ("initiated", "Call Initiated"),
        ("ringing", "Call Ringing"),
        ("accepted", "Call Accepted"),
        ("declined", "Call Declined"),
        ("missed", "Call Missed"),
        ("ended", "Call Ended"),
        ("cancelled", "Call Cancelled"),
    ]

    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name="events")
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        app_label = "zulip_calls_plugin"
        ordering = ["-timestamp"]

    @override
    def __str__(self) -> str:
        return f"{self.event_type} by {self.user.full_name} for call {self.call.call_id}"