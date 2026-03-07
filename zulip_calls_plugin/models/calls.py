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
        ("network_failure", "Network Failure"),
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
    
    # Heartbeat tracking
    last_heartbeat_sender = models.DateTimeField(null=True, blank=True)
    last_heartbeat_receiver = models.DateTimeField(null=True, blank=True)
    is_backgrounded = models.BooleanField(default=False)

    # Moderator and notifications
    moderator = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="moderated_calls",
        null=True, blank=True, help_text="User who initiated the call and has moderator privileges"
    )
    is_missed_notified = models.BooleanField(
        default=False, help_text="Whether missed call notification has been sent"
    )

    # Metadata
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        app_label = "zulip_calls_plugin"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["sender", "receiver"], name="call_participants_idx"),
            models.Index(fields=["state"], name="call_status_idx"),
            models.Index(fields=["created_at"], name="call_created_at_idx"),
            models.Index(fields=["-created_at", "call_id"], name="call_history_cursor_idx"),
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
        ("participant_left", "Participant Left"),
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


class GroupCall(models.Model):
    """Model for managing group video/voice calls"""

    CALL_TYPES = [
        ("video", "Video Call"),
        ("audio", "Audio Call"),
    ]

    CALL_STATES = [
        ("active", "Active"),
        ("ended", "Ended"),
    ]

    call_id = models.UUIDField(primary_key=True, default=uuid.uuid4, db_index=True)
    call_type = models.CharField(max_length=10, choices=CALL_TYPES)
    state = models.CharField(max_length=20, choices=CALL_STATES, default="active")

    # Creator/host of the call
    host = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="hosted_group_calls"
    )

    # Associated stream/topic or DM group (optional)
    stream = models.ForeignKey(
        "zerver.Stream", on_delete=models.SET_NULL, null=True, blank=True
    )
    topic = models.CharField(max_length=255, null=True, blank=True)

    # Call details
    jitsi_room_name = models.CharField(max_length=255)
    jitsi_room_url = models.URLField()
    max_participants = models.IntegerField(default=50)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        app_label = "zulip_calls_plugin"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["host"], name="group_call_host_idx"),
            models.Index(fields=["state"], name="group_call_state_idx"),
            models.Index(fields=["created_at"], name="group_call_created_idx"),
            models.Index(fields=["stream", "topic"], name="group_call_stream_topic_idx"),
        ]

    @override
    def __str__(self) -> str:
        title = self.title or "Untitled Group Call"
        return f"GroupCall {self.call_id}: {title} (host: {self.host.full_name})"

    @property
    def duration(self):
        """Calculate call duration if call has ended"""
        if self.ended_at:
            return self.ended_at - self.created_at
        return None

    def is_active(self) -> bool:
        """Check if call is currently active"""
        return self.state == "active"

    def get_active_participant_count(self) -> int:
        """Get count of currently joined participants"""
        return self.participants.filter(state="joined").count()

    def get_participant_ids(self) -> list[int]:
        """Get list of all participant user IDs"""
        return list(self.participants.values_list("user_id", flat=True))


class GroupCallParticipant(models.Model):
    """Track participants in a group call"""

    PARTICIPANT_STATES = [
        ("invited", "Invited"),
        ("ringing", "Ringing"),
        ("joined", "Joined"),
        ("declined", "Declined"),
        ("left", "Left"),
        ("missed", "Missed"),
    ]

    call = models.ForeignKey(
        GroupCall, on_delete=models.CASCADE, related_name="participants"
    )
    user = models.ForeignKey(
        UserProfile, on_delete=models.CASCADE, related_name="group_call_participations"
    )
    state = models.CharField(max_length=20, choices=PARTICIPANT_STATES, default="invited")
    is_host = models.BooleanField(default=False)

    # Timestamps
    invited_at = models.DateTimeField(auto_now_add=True, db_index=True)
    joined_at = models.DateTimeField(null=True, blank=True)
    left_at = models.DateTimeField(null=True, blank=True)

    # Heartbeat tracking
    last_heartbeat = models.DateTimeField(null=True, blank=True)

    class Meta:
        app_label = "zulip_calls_plugin"
        unique_together = [["call", "user"]]
        indexes = [
            models.Index(fields=["call", "state"], name="group_participant_call_state_idx"),
            models.Index(fields=["user", "state"], name="group_participant_user_state_idx"),
            models.Index(
                fields=["call", "last_heartbeat"], name="group_participant_heartbeat_idx"
            ),
        ]

    @override
    def __str__(self) -> str:
        return f"Participant {self.user.full_name} in call {self.call.call_id} ({self.state})"

    def is_active(self) -> bool:
        """Check if participant is currently active in the call"""
        return self.state in ["invited", "ringing", "joined"]

    def has_joined(self) -> bool:
        """Check if participant has joined the call"""
        return self.state == "joined"

    @property
    def duration_in_call(self):
        """Calculate how long participant has been in call"""
        if self.joined_at:
            end_time = self.left_at or timezone.now()
            return end_time - self.joined_at
        return None