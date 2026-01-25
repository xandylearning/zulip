import uuid
import logging
import json
from datetime import timedelta
from collections.abc import Callable
from typing import Any, Dict

from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from functools import wraps
from django.utils import timezone
from django.db import transaction
from django.db import models
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.conf import settings

# Import Zulip components
from zerver.decorator import (
    authenticated_rest_api_view,
    get_basic_credentials,
    validate_api_key,
    full_webhook_client_name,
    rate_limit_user,
    validate_account_and_subdomain,
    zulip_login_required,
    authenticated_json_view,
)
from zerver.lib.exceptions import JsonableError, UnauthorizedError
from zerver.lib.push_notifications import send_push_notifications
from zerver.lib.request import RequestNotes
from zerver.lib.response import json_success
from zerver.models import UserProfile
from zerver.models.users import get_user_by_delivery_email

# Import plugin models
from ..models import Call, CallEvent, CallQueue

# Import action functions for event dispatch
from ..actions import (
    do_initiate_call,
    do_send_call_ringing_event,
    do_send_call_accepted_event,
    do_send_call_declined_event,
    do_send_call_ended_event,
    do_send_call_cancelled_event,
    do_send_missed_call_event,
)

logger = logging.getLogger(__name__)


def generate_jitsi_url(call_id: str) -> tuple[str, str]:
    """Generate Jitsi meeting URL and room ID"""
    from django.conf import settings

    room_id = f"{getattr(settings, 'JITSI_MEETING_PREFIX', 'zulip-call-')}{call_id}"
    jitsi_url = f"{getattr(settings, 'JITSI_SERVER_URL', 'https://dev.meet.xandylearning.in')}/{room_id}"

    return jitsi_url, room_id


def extract_request_data(request: HttpRequest, required_fields: list = None) -> dict:
    """
    Extract and validate request data from POST/GET parameters
    Returns a dictionary with extracted data and any validation errors
    """
    data = {}
    errors = []
    
    # Extract data from both POST and GET
    for key in (request.POST.keys() | request.GET.keys()):
        value = (request.POST.get(key) or request.GET.get(key) or "").strip()
        data[key] = value
    
    # Validate required fields
    if required_fields:
        for field in required_fields:
            if not data.get(field):
                errors.append(f"Missing required parameter: {field}")
    
    return {
        'data': data,
        'errors': errors,
        'has_errors': len(errors) > 0
    }


def send_call_push_notification(recipient: UserProfile, call_data: dict) -> None:
    """Send push notification for call events using correct Zulip API with fallback support"""
    from django.conf import settings
    from zerver.models import PushDevice, PushDeviceToken
    from zerver.lib.push_notifications import send_push_notifications, send_push_notifications_legacy
    from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError

    if not getattr(settings, 'CALL_PUSH_NOTIFICATION_ENABLED', True):
        return

    try:
        # Enhanced call notification data - format for Zulip's push notification system
        # Updated to support terminated app notifications with proper FCM format
        payload_data_to_encrypt = {
            'event': 'call',  # Use 'event' for consistency with FCM notification detection
            'type': 'call',   # Keep 'type' for backward compatibility
            'call_id': call_data.get('call_id'),
            'sender_id': call_data.get('sender_id'),
            'sender_full_name': call_data.get('sender_name'),  # Use 'sender_full_name' for FCM notification
            'sender_name': call_data.get('sender_name'),       # Keep 'sender_name' for backward compatibility
            'sender_avatar_url': f"/avatar/{call_data.get('sender_id')}",
            'call_type': call_data.get('call_type'),
            'jitsi_url': call_data.get('jitsi_url'),
            'timeout_seconds': getattr(settings, 'CALL_NOTIFICATION_TIMEOUT', 120),
            'realm_uri': recipient.realm.url,
            'realm_name': recipient.realm.name,
            'realm_url': recipient.realm.url,
            'server': recipient.realm.host,  # Add server info for FCM
            'user_id': str(recipient.id),    # Add user ID for FCM
            'time': str(int(timezone.now().timestamp())),  # Add timestamp for FCM
        }

        # Create legacy notification payloads for fallback
        call_type = call_data.get('call_type', 'call')
        sender_name = call_data.get('sender_name', 'Someone')
        
        apns_payload = {
            "alert": {
                "title": f"Incoming {call_type} call",
                "body": f"{sender_name} is calling you"
            },
            "badge": 1,
            "sound": "default",
            "custom": payload_data_to_encrypt
        }
        
        gcm_payload = {
            "title": f"Incoming {call_type} call",
            "content": f"{sender_name} is calling you",
            "custom": payload_data_to_encrypt
        }
        
        gcm_options = {
            "priority": "high"
        }

        # Check device registration status
        e2ee_devices = PushDevice.objects.filter(
            user=recipient, 
            bouncer_device_id__isnull=False
        ).exists()
        
        legacy_devices = PushDeviceToken.objects.filter(user=recipient).exists()
        
        if not e2ee_devices and not legacy_devices:
            logger.info(f"No registered devices for user {recipient.id}")
            return

        # Try E2EE push notifications first (for newer clients with bouncer registration)
        if e2ee_devices:
            try:
                send_push_notifications(recipient, payload_data_to_encrypt)
                logger.info(f"E2EE call push notification sent to user {recipient.id} for call {call_data.get('call_id')}")
                return  # Success, no need to try legacy
            except PushNotificationBouncerRetryLaterError as e:
                logger.warning(f"E2EE push notification bouncer retry error for user {recipient.id}: {e}")
                # Don't retry, just continue to legacy notifications
            except Exception as e:
                logger.warning(f"E2EE push notification failed for user {recipient.id}: {e}")
                # Continue to try legacy notifications
        
        # Send legacy push notifications (for older clients or when E2EE fails)
        if legacy_devices:
            try:
                send_push_notifications_legacy(recipient, apns_payload, gcm_payload, gcm_options)
                logger.info(f"Legacy call push notification sent to user {recipient.id} for call {call_data.get('call_id')}")
            except PushNotificationBouncerRetryLaterError as e:
                logger.warning(f"Legacy push notification bouncer retry error for user {recipient.id}: {e}")
                # Don't retry - call notifications are time-sensitive
            except Exception as e:
                logger.error(f"Legacy push notification failed for user {recipient.id}: {e}")
        
        logger.info(f"Call push notification processing completed for user {recipient.id} for call {call_data.get('call_id')}")

    except Exception as e:
        logger.error(f"Failed to send call push notification: {e}")


def send_missed_call_notification(recipient: UserProfile, call: Call) -> None:
    """Send push notification for missed call"""
    from django.conf import settings
    from zerver.models import PushDevice, PushDeviceToken
    from zerver.lib.push_notifications import send_push_notifications, send_push_notifications_legacy
    from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError

    if not getattr(settings, 'CALL_PUSH_NOTIFICATION_ENABLED', True):
        return

    try:
        # Prepare missed call notification data
        payload_data_to_encrypt = {
            'event': 'missed_call',
            'type': 'missed_call',
            'call_id': str(call.call_id),
            'sender_id': call.sender.id,
            'sender_full_name': call.sender.full_name,
            'sender_name': call.sender.full_name,
            'sender_avatar_url': f"/avatar/{call.sender.id}",
            'call_type': call.call_type,
            'timestamp': call.created_at.isoformat(),
            'time': str(int(call.created_at.timestamp())),
            'realm_uri': recipient.realm.url,
            'realm_name': recipient.realm.name,
            'realm_url': recipient.realm.url,
            'server': recipient.realm.host,
            'user_id': str(recipient.id),
        }

        # Create legacy notification payloads for fallback
        call_type = call.call_type
        sender_name = call.sender.full_name
        
        apns_payload = {
            "alert": {
                "title": "Missed call",
                "body": f"Missed {call_type} call from {sender_name}"
            },
            "badge": 1,
            "sound": "default",
            "custom": payload_data_to_encrypt
        }
        
        gcm_payload = {
            "title": "Missed call",
            "content": f"Missed {call_type} call from {sender_name}",
            "custom": payload_data_to_encrypt
        }
        
        gcm_options = {
            "priority": "high"
        }

        # Check device registration status
        e2ee_devices = PushDevice.objects.filter(
            user=recipient, 
            bouncer_device_id__isnull=False
        ).exists()
        
        legacy_devices = PushDeviceToken.objects.filter(user=recipient).exists()
        
        if not e2ee_devices and not legacy_devices:
            logger.info(f"No registered devices for user {recipient.id}")
            return

        # Try E2EE push notifications first
        if e2ee_devices:
            try:
                send_push_notifications(recipient, payload_data_to_encrypt)
                logger.info(f"E2EE missed call notification sent to user {recipient.id} for call {call.call_id}")
                return
            except PushNotificationBouncerRetryLaterError as e:
                logger.warning(f"E2EE push notification bouncer retry error for user {recipient.id}: {e}")
            except Exception as e:
                logger.warning(f"E2EE push notification failed for user {recipient.id}: {e}")
        
        # Send legacy push notifications
        if legacy_devices:
            try:
                send_push_notifications_legacy(recipient, apns_payload, gcm_payload, gcm_options)
                logger.info(f"Legacy missed call notification sent to user {recipient.id} for call {call.call_id}")
            except PushNotificationBouncerRetryLaterError as e:
                logger.warning(f"Legacy push notification bouncer retry error for user {recipient.id}: {e}")
            except Exception as e:
                logger.error(f"Legacy push notification failed for user {recipient.id}: {e}")
        
        logger.info(f"Missed call notification processing completed for user {recipient.id} for call {call.call_id}")

    except Exception as e:
        logger.error(f"Failed to send missed call notification: {e}")


def send_fcm_call_notification(recipient: UserProfile, call_data: dict) -> None:
    """
    Send FCM call notification using the specialized call notification format.

    This function sends FCM notifications in the exact format specified:
    {
      "to": "<device_fcm_token>",
      "priority": "high",
      "data": {
        "event": "call",
        "server": "your-org.example.com",
        "realm_url": "https://your-org.example.com",
        "realm_id": "1",
        "user_id": "123",
        "call_id": "abc123",
        "sender_id": "456",
        "sender_full_name": "Alice",
        "call_type": "video",
        "time": "1726930000"
      },
      "android": {
        "priority": "high",
        "notification": {
          "channel_id": "calls-1",
          "tag": "call:abc123",
          "title": "Incoming video call",
          "body": "From Alice",
          "sound": "default",
          "click_action": "android.intent.action.VIEW"
        }
      },
      "notification": {
        "title": "Incoming video call",
        "body": "From Alice"
      }
    }
    """
    from django.conf import settings
    from zerver.models import PushDeviceToken
    from zerver.lib.push_notifications import send_fcm_call_notifications

    if not getattr(settings, 'CALL_PUSH_NOTIFICATION_ENABLED', True):
        return

    try:
        # Get FCM devices for the recipient
        fcm_devices = PushDeviceToken.objects.filter(
            user=recipient,
            kind=PushDeviceToken.FCM
        )

        if not fcm_devices.exists():
            logger.info(f"No FCM devices registered for user {recipient.id}")
            return

        # Prepare call data with all required fields
        enhanced_call_data = {
            'call_id': call_data.get('call_id'),
            'sender_id': call_data.get('sender_id'),
            'sender_full_name': call_data.get('sender_name'),
            'sender_name': call_data.get('sender_name'),  # Add for backward compatibility
            'call_type': call_data.get('call_type', 'voice'),
            'jitsi_url': call_data.get('jitsi_url'),  # Include Jitsi URL
            'user_id': str(recipient.id),
            'time': str(int(timezone.now().timestamp())),
        }
        
        # Generate sender avatar URL if sender_id is available
        sender_id = call_data.get('sender_id')
        if sender_id:
            enhanced_call_data['sender_avatar_url'] = f"/avatar/{sender_id}"
        else:
            enhanced_call_data['sender_avatar_url'] = ""

        # Send specialized FCM call notifications
        success_count = send_fcm_call_notifications(
            devices=list(fcm_devices),
            call_data=enhanced_call_data,
            realm_host=recipient.realm.host,
            realm_url=recipient.realm.url,
            realm_id=recipient.realm.id,
        )

        logger.info(
            f"FCM call notification sent to {success_count}/{len(fcm_devices)} devices "
            f"for user {recipient.id} and call {call_data.get('call_id')}"
        )

    except Exception as e:
        logger.error(f"Failed to send FCM call notification: {e}")


def send_call_response_notification(user_profile: UserProfile, call: Call, response: str) -> None:
    """Send notification about call response using correct Zulip API with fallback support"""
    from zerver.models import PushDevice, PushDeviceToken
    from zerver.lib.push_notifications import send_push_notifications, send_push_notifications_legacy
    from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
    
    payload_data_to_encrypt = {
        'event': 'call_response',  # Use 'event' for FCM notification detection
        'type': 'call_response',   # Keep 'type' for backward compatibility
        'call_id': str(call.call_id),
        'response': response,
        'receiver_name': call.receiver.full_name,
        'sender_full_name': call.receiver.full_name,  # Add for FCM notification
        'call_type': call.call_type,
        'realm_uri': user_profile.realm.url,
        'realm_name': user_profile.realm.name,
        'realm_url': user_profile.realm.url,
        'server': user_profile.realm.host,  # Add server info for FCM
        'user_id': str(user_profile.id),    # Add user ID for FCM
        'time': str(int(timezone.now().timestamp())),  # Add timestamp for FCM
    }

    try:
        # Create legacy notification payloads for fallback
        response_text = "accepted" if response == "accept" else "declined"
        
        apns_payload = {
            "alert": {
                "title": f"Call {response_text}",
                "body": f"{call.receiver.full_name} {response_text} your call"
            },
            "badge": 1,
            "sound": "default",
            "custom": payload_data_to_encrypt
        }
        
        gcm_payload = {
            "title": f"Call {response_text}",
            "content": f"{call.receiver.full_name} {response_text} your call",
            "custom": payload_data_to_encrypt
        }
        
        gcm_options = {
            "priority": "high"
        }

        # Check device registration status
        e2ee_devices = PushDevice.objects.filter(
            user=user_profile, 
            bouncer_device_id__isnull=False
        ).exists()
        
        legacy_devices = PushDeviceToken.objects.filter(user=user_profile).exists()
        
        if not e2ee_devices and not legacy_devices:
            logger.info(f"No registered devices for user {user_profile.id}")
            return

        # Try E2EE push notifications first
        if e2ee_devices:
            try:
                send_push_notifications(user_profile, payload_data_to_encrypt)
                logger.info(f"E2EE call response notification sent to user {user_profile.id} for call {call.call_id}")
                return  # Success, no need to try legacy
            except PushNotificationBouncerRetryLaterError as e:
                logger.warning(f"E2EE push notification bouncer retry error for user {user_profile.id}: {e}")
                # Don't retry, just continue to legacy notifications
            except Exception as e:
                logger.warning(f"E2EE push notification failed for user {user_profile.id}: {e}")
        
        # Send legacy push notifications
        if legacy_devices:
            try:
                send_push_notifications_legacy(user_profile, apns_payload, gcm_payload, gcm_options)
                logger.info(f"Legacy call response notification sent to user {user_profile.id} for call {call.call_id}")
            except PushNotificationBouncerRetryLaterError as e:
                logger.warning(f"Legacy push notification bouncer retry error for user {user_profile.id}: {e}")
                # Don't retry - call notifications are time-sensitive
            except Exception as e:
                logger.error(f"Legacy push notification failed for user {user_profile.id}: {e}")
        
        logger.info(f"Call response notification processing completed for user {user_profile.id} for call {call.call_id}")
        
    except Exception as e:
        logger.error(f"Failed to send call response notification: {str(e)}")


def cleanup_stale_calls() -> int:
    """Clean up stale calls with multiple timeout scenarios"""
    from datetime import timedelta

    now = timezone.now()
    count = 0

    # Scenario 1: 90-second timeout for unanswered calls in ringing/calling state
    # This gives users plenty of time to acknowledge and respond
    unanswered_threshold = now - timedelta(seconds=90)
    unanswered_calls = Call.objects.filter(
        state__in=['calling', 'ringing'],  # Include both calling and ringing
        answered_at__isnull=True,
        created_at__lt=unanswered_threshold
    )

    for call in unanswered_calls:
        call.state = 'missed'
        call.ended_at = now
        call.save()

        # Send missed call notification if not already sent
        if not call.is_missed_notified:
            send_missed_call_notification(call.receiver, call)
            call.is_missed_notified = True
            call.save(update_fields=['is_missed_notified'])

        CallEvent.objects.create(
            call=call,
            event_type='missed',
            user=call.sender,
            metadata={'reason': 'unanswered_timeout', 'timeout_seconds': 90}
        )

        # Use action function to send missed call event
        do_send_missed_call_event(call.sender.realm, call, timeout_seconds=90)
        count += 1

    # Scenario 2: Network failure - 60 seconds no heartbeat for ACCEPTED calls only
    # Only check heartbeat for accepted calls to avoid ending calls during setup
    # Give participants 90 seconds to start sending heartbeats after acceptance
    # Extended timeouts to handle slow networks better
    network_threshold = now - timedelta(seconds=60)
    heartbeat_grace_period = now - timedelta(seconds=90)  # 90 seconds grace period
    
    active_calls = Call.objects.filter(
        state='accepted',
        answered_at__lt=heartbeat_grace_period  # Only check calls accepted more than 60 seconds ago
    )

    for call in active_calls:
        # Check if both participants have sent heartbeat
        sender_inactive = (
            call.last_heartbeat_sender is None or
            call.last_heartbeat_sender < network_threshold
        )
        receiver_inactive = (
            call.last_heartbeat_receiver is None or
            call.last_heartbeat_receiver < network_threshold
        )

        # End call if either participant has no heartbeat for 60 seconds
        if sender_inactive or receiver_inactive:
            call.state = 'network_failure'
            call.ended_at = now
            call.save()
            CallEvent.objects.create(
                call=call,
                event_type='ended',
                user=call.sender if sender_inactive else call.receiver,
                metadata={'reason': 'network_failure', 'timeout_seconds': 60}
            )

            # Use action function to send ended event with network_failure reason
            do_send_call_ended_event(call.sender.realm, call, reason='network_failure')
            count += 1

    # Scenario 3: Fallback - extremely stale calls (10 minutes)
    # Increased from 5 to 10 minutes for more safety
    stale_threshold = now - timedelta(minutes=10)
    stale_calls = Call.objects.filter(
        state__in=['calling', 'ringing', 'accepted'],
        created_at__lt=stale_threshold
    )

    for call in stale_calls:
        call.state = 'timeout'
        call.ended_at = now
        call.save()
        CallEvent.objects.create(
            call=call,
            event_type='timeout',
            user=call.sender,
            metadata={'reason': 'stale_cleanup', 'timeout_minutes': 10}
        )

        # Use action function to send ended event with timeout reason
        do_send_call_ended_event(call.sender.realm, call, reason='timeout_stale')
        count += 1

    if count > 0:
        logger.info(f"Cleaned up {count} stale calls")

    return count


def end_user_active_calls(user_profile: UserProfile, reason: str = 'manual_end') -> int:
    """End all active calls for a user"""
    active_calls = Call.objects.filter(
        models.Q(sender=user_profile) | models.Q(receiver=user_profile),
        state__in=['calling', 'ringing', 'accepted']
    )
    
    count = 0
    for call in active_calls:
        call.state = 'ended'
        call.ended_at = timezone.now()
        call.save()
        
        # Create end event
        CallEvent.objects.create(
            call=call,
            event_type='ended',
            user=user_profile,
            metadata={'reason': reason}
        )
        
        logger.info(f"Ended call {call.call_id} for user {user_profile.id} (reason: {reason})")
        count += 1
    
    return count


def check_and_cleanup_user_calls(user_profile: UserProfile) -> bool:
    """Check if user has active calls and clean them up if they're stale"""
    from django.conf import settings
    from datetime import timedelta
    
    call_timeout_minutes = getattr(settings, 'CALL_TIMEOUT_MINUTES', 30)
    stale_threshold = timezone.now() - timedelta(minutes=call_timeout_minutes)
    
    # Check for stale active calls
    stale_calls = Call.objects.filter(
        models.Q(sender=user_profile) | models.Q(receiver=user_profile),
        state__in=['calling', 'ringing', 'accepted'],
        created_at__lt=stale_threshold
    )
    
    if stale_calls.exists():
        # Clean up stale calls
        cleanup_stale_calls()
        return True
    
    return False


def process_call_queue(user_profile: UserProfile) -> int:
    """Process pending queued calls for a user who just became available"""
    from datetime import timedelta
    
    try:
        # Check if user is still in an active call
        active_call = Call.objects.filter(
            models.Q(sender=user_profile) | models.Q(receiver=user_profile),
            state__in=['calling', 'ringing', 'accepted']
        ).exists()
        
        if active_call:
            logger.info(f"User {user_profile.id} still in active call, not processing queue")
            return 0
        
        # Get oldest pending queue entry for this user
        queue_entry = CallQueue.objects.filter(
            busy_user=user_profile,
            status='pending',
            expires_at__gt=timezone.now()
        ).order_by('created_at').first()
        
        if not queue_entry:
            return 0
        
        # Check if caller is still available (not in another call)
        caller_in_call = Call.objects.filter(
            models.Q(sender=queue_entry.caller) | models.Q(receiver=queue_entry.caller),
            state__in=['calling', 'ringing', 'accepted']
        ).exists()
        
        if caller_in_call:
            # Caller is busy, mark queue as expired
            queue_entry.status = 'expired'
            queue_entry.save()
            logger.info(f"Queue entry {queue_entry.queue_id} expired - caller now busy")
            return 0
        
        # Create the actual call
        with transaction.atomic():
            call = Call.objects.create(
                call_type=queue_entry.call_type,
                sender=queue_entry.caller,
                receiver=user_profile,
                moderator=queue_entry.caller,
                jitsi_room_name=f"zulip-call-{uuid.uuid4().hex[:12]}",
                realm=user_profile.realm
            )
            
            # Generate Jitsi URLs
            jitsi_server = getattr(settings, 'JITSI_SERVER_URL', 'https://dev.meet.xandylearning.in')
            base_room_url = f"{jitsi_server}/{call.jitsi_room_name}"
            call.jitsi_room_url = base_room_url
            call.last_heartbeat_sender = timezone.now()
            call.save()
            
            # Mark queue entry as converted
            queue_entry.status = 'converted'
            queue_entry.converted_to_call_id = call.call_id
            queue_entry.save()
            
            # Create call event
            CallEvent.objects.create(
                call=call,
                event_type="initiated",
                user=queue_entry.caller,
                metadata={"from_queue": True, "queue_id": str(queue_entry.queue_id)}
            )
            
            # Prepare push notification data
            available_notification = {
                "call_id": str(call.call_id),
                "jitsi_url": call.jitsi_room_url,
                "call_type": call.call_type,
                "sender_name": user_profile.full_name,
                "sender_id": str(user_profile.id),
                "room_name": call.jitsi_room_name,
            }

            call_notification = {
                "call_id": str(call.call_id),
                "jitsi_url": call.jitsi_room_url,
                "call_type": call.call_type,
                "sender_name": queue_entry.caller.full_name,
                "sender_id": str(queue_entry.caller.id),
                "room_name": call.jitsi_room_name,
            }

            # Send push notifications after transaction commits to avoid nested atomic block errors
            transaction.on_commit(lambda: send_call_push_notification(queue_entry.caller, available_notification))
            transaction.on_commit(lambda: send_call_push_notification(user_profile, call_notification))
            
            logger.info(f"Processed queue entry {queue_entry.queue_id}, created call {call.call_id}")
            return 1
    
    except Exception as e:
        logger.error(f"Failed to process call queue for user {user_profile.id}: {e}")
        return 0


def cleanup_expired_queue_entries() -> int:
    """Clean up expired queue entries and notify callers"""
    now = timezone.now()
    count = 0
    
    # Find expired queue entries
    expired_entries = CallQueue.objects.filter(
        status='pending',
        expires_at__lte=now
    )
    
    for entry in expired_entries:
        entry.status = 'expired'
        entry.save()
        
        # Send notification to caller that user is still busy
        try:
            payload_data = {
                'event': 'call_queue_expired',
                'type': 'call_queue_expired',
                'queue_id': str(entry.queue_id),
                'busy_user_name': entry.busy_user.full_name,
                'busy_user_id': entry.busy_user.id,
                'call_type': entry.call_type,
            }
            
            from zerver.models import PushDevice, PushDeviceToken
            from zerver.lib.push_notifications import send_push_notifications
            
            if PushDevice.objects.filter(user=entry.caller, bouncer_device_id__isnull=False).exists():
                send_push_notifications(entry.caller, payload_data)
                logger.info(f"Sent queue expired notification to user {entry.caller.id}")
        except Exception as e:
            logger.error(f"Failed to send queue expired notification: {e}")
        
        count += 1
    
    if count > 0:
        logger.info(f"Cleaned up {count} expired queue entries")
    
    return count




def _create_call_impl(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Shared implementation for creating a call. Caller is responsible for auth."""
    try:
        # Clean up stale calls before processing
        cleanup_stale_calls()

        with transaction.atomic():
            # Get request parameters
            recipient_user_id = request.POST.get("user_id")
            is_video_call = request.POST.get("is_video_call", "true").lower() == "true"

            # Validate that user_id is provided
            if not recipient_user_id:
                return JsonResponse({
                    "result": "error",
                    "message": "user_id is required"
                }, status=400)

            # Direct lookup by user_id
            try:
                recipient = UserProfile.objects.get(id=int(recipient_user_id), realm=user_profile.realm)
                logger.info(f"Found user by user_id: {recipient_user_id}")
            except (UserProfile.DoesNotExist, ValueError) as e:
                return JsonResponse({
                    "result": "error",
                    "message": f"User not found with user_id: {recipient_user_id}"
                }, status=404)

            # Check if users are the same
            if user_profile.id == recipient.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Cannot call yourself"
                }, status=400)

            # Clean up any stale calls for both users before validation
            check_and_cleanup_user_calls(user_profile)
            check_and_cleanup_user_calls(recipient)

            # Check if caller is already in an active call OR recently ended call (prevent race conditions)
            recent_threshold = timezone.now() - timedelta(seconds=5)
            caller_in_call = Call.objects.filter(
                models.Q(sender=user_profile) | models.Q(receiver=user_profile),
                models.Q(state__in=["calling", "ringing", "accepted"]) |
                models.Q(state="ended", ended_at__gt=recent_threshold)
            ).first()

            if caller_in_call:
                if caller_in_call.state == "ended":
                    return JsonResponse({
                        "result": "error",
                        "message": "Please wait a moment before making another call",
                        "existing_call_id": str(caller_in_call.call_id)
                    }, status=429)  # Too Many Requests
                return JsonResponse({
                    "result": "error",
                    "message": "You are already in a call",
                    "existing_call_id": str(caller_in_call.call_id)
                }, status=409)

            # Check if receiver is already in an active call
            receiver_in_call = Call.objects.filter(
                models.Q(sender=recipient) | models.Q(receiver=recipient),
                state__in=["calling", "ringing", "accepted"]
            ).first()

            if receiver_in_call:
                # Queue the call instead of rejecting it
                queue_expiry = timezone.now() + timedelta(minutes=5)
                queue_entry = CallQueue.objects.create(
                    caller=user_profile,
                    busy_user=recipient,
                    call_type="video" if is_video_call else "audio",
                    expires_at=queue_expiry,
                    realm=user_profile.realm
                )
                
                logger.info(f"Queued call {queue_entry.queue_id} - recipient {recipient.id} is busy")
                
                return JsonResponse({
                    "result": "queued",
                    "queue_id": str(queue_entry.queue_id),
                    "message": f"{recipient.full_name} is currently in another call. You'll be notified when they're available.",
                    "expires_at": queue_expiry.isoformat(),
                    "position": "next"
                }, status=202)

            # Re-check in-transaction before creating the call to avoid race conditions
            recheck_active = Call.objects.select_for_update().filter(
                (
                    models.Q(sender=user_profile) | models.Q(receiver=user_profile) |
                    models.Q(sender=recipient) | models.Q(receiver=recipient)
                ),
                state__in=["calling", "ringing", "accepted"]
            ).exists()

            if recheck_active:
                return JsonResponse({
                    "result": "error",
                    "message": "A related active call already exists",
                }, status=409)

            # Create call record
            call = Call.objects.create(
                call_type="video" if is_video_call else "audio",
                sender=user_profile,
                receiver=recipient,
                moderator=user_profile,  # Sender is always the moderator
                jitsi_room_name=f"zulip-call-{uuid.uuid4().hex[:12]}",
                realm=user_profile.realm
            )

            # Generate Jitsi URLs - separate URLs for moderator and participant
            jitsi_server = getattr(settings, 'JITSI_SERVER_URL', 'https://dev.meet.xandylearning.in')
            base_room_url = f"{jitsi_server}/{call.jitsi_room_name}"

            # Moderator URL (for initiator) with special parameters
            moderator_params = (
                f"?userInfo.displayName={user_profile.full_name}"
                f"&config.startWithAudioMuted=false"
                f"&config.startWithVideoMuted=false"
                f"&config.enableWelcomePage=false"
                f"&config.enableClosePage=false"
                f"&config.prejoinPageEnabled=false"
            f"&config.prejoinConfig.enabled=false"
            f"&config.prejoinConfig.hideDisplayName=true"
            f"&config.prejoinConfig.hidePrejoinDisplayName=true"
                f"&config.requireDisplayName=false"
                f"&config.disableModeratorIndicator=true"
                f"&config.startScreenSharing=false"
                f"&config.enableInsecureRoomNameWarning=false"
                f"&interfaceConfig.SHOW_JITSI_WATERMARK=false"
                f"&interfaceConfig.SHOW_WATERMARK_FOR_GUESTS=false"
            )

            # Participant URL (for recipient) without moderator privileges
            participant_params = (
                f"?userInfo.displayName={recipient.full_name}"
                f"&config.startWithAudioMuted=true"
                f"&config.startWithVideoMuted=true"
                f"&config.enableWelcomePage=false"
                f"&config.enableClosePage=false"
                f"&config.prejoinPageEnabled=false"
            f"&config.prejoinConfig.enabled=false"
            f"&config.prejoinConfig.hideDisplayName=true"
            f"&config.prejoinConfig.hidePrejoinDisplayName=true"
                f"&config.requireDisplayName=false"
                f"&config.disableModeratorIndicator=true"
                f"&config.startScreenSharing=false"
                f"&config.enableInsecureRoomNameWarning=false"
                f"&interfaceConfig.SHOW_JITSI_WATERMARK=false"
                f"&interfaceConfig.SHOW_WATERMARK_FOR_GUESTS=false"
            )

            # Store the base URL and create specific URLs for each participant
            call.jitsi_room_url = base_room_url  # Base URL without parameters
            moderator_url = f"{base_room_url}{moderator_params}#config.prejoinPageEnabled=false"
            participant_url = f"{base_room_url}{participant_params}#config.prejoinPageEnabled=false"

            call.save()

            # Initialize sender heartbeat
            call.last_heartbeat_sender = timezone.now()
            call.save(update_fields=['last_heartbeat_sender'])

            # Create initial call event
            CallEvent.objects.create(
                call=call,
                event_type="initiated",
                user=user_profile,
                metadata={
                    "recipient_user_id": recipient_user_id,
                    "is_video_call": is_video_call
                }
            )

            # Use action function to send call events with offline detection
            initiate_status = do_initiate_call(user_profile.realm, call)

            # Prepare push notification data
            push_data = {
                "type": "call_invitation",
                "call_id": str(call.call_id),
                "jitsi_url": participant_url,  # Participant URL for the recipient
                "call_type": call.call_type,
                "sender_name": user_profile.full_name,
                "sender_id": str(user_profile.id),
                "room_name": call.jitsi_room_name,
            }

            fcm_call_data = {
                "call_id": str(call.call_id),
                "sender_id": str(user_profile.id),
                "sender_name": user_profile.full_name,
                "sender_full_name": user_profile.full_name,  # Add for consistency
                "call_type": call.call_type,
                "jitsi_url": participant_url,
                "sender_avatar_url": f"/avatar/{user_profile.id}",  # Include avatar URL
            }

            # Send push notifications after transaction commits to avoid nested atomic block errors
            # This also ensures notifications are only sent if the database transaction succeeds
            transaction.on_commit(lambda: send_call_push_notification(recipient, push_data))
            transaction.on_commit(lambda: send_fcm_call_notification(recipient, fcm_call_data))

            return JsonResponse({
                "result": "success",
                "call_id": str(call.call_id),
                "call_url": moderator_url,  # Moderator URL for the initiator
                "participant_url": participant_url,  # Available if needed
                "call_type": call.call_type,
                "room_name": call.jitsi_room_name,
                "receiver_online": initiate_status["receiver_online"],  # Add offline status
                "recipient": {
                    "user_id": recipient.id,
                    "full_name": recipient.full_name,
                    "email": recipient.delivery_email,
                }
            })

    except Exception as e:
        logger.error(f"Failed to create call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to create call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def create_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Create a new call with full database tracking (API Basic auth)."""
    return _create_call_impl(request, user_profile)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def respond_to_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Accept or decline a call invitation with full tracking"""
    try:
        # Don't run cleanup here - respond to call should work even if the call is recent

        with transaction.atomic():
            try:
                call = Call.objects.select_for_update().get(
                    call_id=call_id,
                    realm=user_profile.realm
                )
            except Call.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Call not found"
                }, status=404)

            # Check authorization
            if call.receiver.id != user_profile.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Not authorized to respond to this call"
                }, status=403)

            # Check call state
            if call.state not in ["calling", "ringing"]:
                return JsonResponse({
                    "result": "error",
                    "message": f"Cannot respond to call in state: {call.state}"
                }, status=400)

            response = request.POST.get("response")
            if response not in ["accept", "decline"]:
                return JsonResponse({
                    "result": "error",
                    "message": "Response must be 'accept' or 'decline'"
                }, status=400)

            if response == "accept":
                call.state = "accepted"
                call.answered_at = timezone.now()
                event_type = "accepted"

            else:
                call.state = "rejected"
                call.ended_at = timezone.now()
                event_type = "declined"

            call.save()

            # Create event record
            CallEvent.objects.create(
                call=call,
                event_type=event_type,
                user=user_profile
            )

            # Use action functions to send events to both participants
            if response == "accept":
                do_send_call_accepted_event(user_profile.realm, call)
            else:
                do_send_call_declined_event(user_profile.realm, call)
            
            # If call was declined, process queue for the receiver
            if response == "decline":
                try:
                    process_call_queue(call.receiver)
                except Exception as e:
                    logger.error(f"Failed to process queue after call decline: {e}")

            return JsonResponse({
                "result": "success",
                "action": response,
                "call_url": call.jitsi_room_url if response == "accept" else None,
                "message": f"Call {response}ed successfully"
            })

    except Exception as e:
        logger.error(f"Failed to respond to call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to respond to call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def end_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """End an ongoing call"""
    try:
        with transaction.atomic():
            try:
                call = Call.objects.select_for_update().get(
                    call_id=call_id,
                    realm=user_profile.realm
                )
            except Call.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Call not found"
                }, status=404)

            # Check authorization
            if (call.sender.id != user_profile.id and
                call.receiver.id != user_profile.id):
                return JsonResponse({
                    "result": "error",
                    "message": "Not authorized to end this call"
                }, status=403)

            # Check if user is moderator - moderators end call for everyone
            is_moderator = call.moderator and call.moderator.id == user_profile.id
            
            if is_moderator:
                # Moderator ends call for everyone
                call.state = "ended"
                call.ended_at = timezone.now()
                call.save()

                # Create event
                CallEvent.objects.create(
                    call=call,
                    event_type="ended",
                    user=user_profile,
                    metadata={"ended_by_moderator": True}
                )

                # Use action function to send ended event to both participants
                do_send_call_ended_event(user_profile.realm, call, reason="ended_by_moderator")

                # Process queue for both participants
                try:
                    process_call_queue(call.sender)
                    process_call_queue(call.receiver)
                except Exception as e:
                    logger.error(f"Failed to process queue after call end: {e}")

                return JsonResponse({
                    "result": "success",
                    "message": "Call ended successfully"
                })
            else:
                # Participant leaves call but doesn't end it for everyone
                # Create participant_left event
                CallEvent.objects.create(
                    call=call,
                    event_type="participant_left",
                    user=user_profile
                )

                # Notify other participant using direct event (not a standard action function)
                # This is a special case where we send to only one user
                other_user = call.sender if user_profile.id == call.receiver.id else call.receiver
                from ..actions import do_send_call_event
                do_send_call_event(
                    user_profile.realm,
                    call,
                    "participant_left",
                    [other_user.id],
                    extra_data={
                        'left_user_id': user_profile.id,
                        'left_user_name': user_profile.full_name
                    }
                )
                
                # Process queue for the user who left
                try:
                    process_call_queue(user_profile)
                except Exception as e:
                    logger.error(f"Failed to process queue after participant left: {e}")

                return JsonResponse({
                    "result": "success",
                    "message": "You have left the call"
                })

    except Exception as e:
        logger.error(f"Failed to end call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to end call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def cancel_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Cancel an outgoing call before it is accepted"""
    try:
        with transaction.atomic():
            try:
                call = Call.objects.select_for_update().get(
                    call_id=call_id,
                    realm=user_profile.realm
                )
            except Call.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Call not found"
                }, status=404)

            # Only sender can cancel while calling/ringing
            if call.sender.id != user_profile.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Not authorized to cancel this call"
                }, status=403)

            if call.state not in ["calling", "ringing"]:
                return JsonResponse({
                    "result": "error",
                    "message": f"Cannot cancel call in state: {call.state}"
                }, status=400)

            # Mark call as cancelled
            call.state = "cancelled"
            call.ended_at = timezone.now()
            call.save()

            # Record event
            CallEvent.objects.create(
                call=call,
                event_type="cancelled",
                user=user_profile
            )

            # Use action function to send cancelled event to both participants
            do_send_call_cancelled_event(user_profile.realm, call)

            return JsonResponse({
                "result": "success",
                "message": "Call cancelled successfully"
            })

    except Exception as e:
        logger.error(f"Failed to cancel call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to cancel call: {str(e)}"
        }, status=500)


@require_http_methods(["GET"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def get_call_status(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Get current status of a call"""
    try:
        # Don't run cleanup_stale_calls() here - it can cause race conditions
        # where calls are ended immediately after creation
        try:
            call = Call.objects.get(
                call_id=call_id,
                realm=user_profile.realm
            )
        except Call.DoesNotExist:
            return JsonResponse({
                "result": "error",
                "message": "Call not found"
            }, status=404)

        # Check authorization
        if (call.sender.id != user_profile.id and
            call.receiver.id != user_profile.id):
            return JsonResponse({
                "result": "error",
                "message": "Not authorized to view this call"
            }, status=403)

        # Map internal state to client-expected status values
        # The client expects: created, ringing, accepted, declined, ended, cancelled
        status_mapping = {
            'calling': 'created',      # Map 'calling' to 'created' for client
            'ringing': 'ringing',
            'accepted': 'accepted',
            'rejected': 'declined',    # Map 'rejected' to 'declined' for client
            'ended': 'ended',
            'cancelled': 'cancelled',
            'timeout': 'ended',        # Map 'timeout' to 'ended' for client
            'missed': 'ended',         # Map 'missed' to 'ended' for client
            'network_failure': 'ended', # Map 'network_failure' to 'ended' for client
        }

        # Get mapped status, default to 'ended' if state is not in mapping
        client_status = status_mapping.get(call.state, 'ended')

        return JsonResponse({
            "result": "success",
            "call": {
                "call_id": str(call.call_id),
                "caller_id": call.sender.id,      # Use caller_id as expected by client
                "recipient_id": call.receiver.id,  # Use recipient_id as expected by client
                "call_type": call.call_type,
                "status": client_status,           # Use 'status' field name as expected by client
                "jitsi_url": call.jitsi_room_url,
                "timestamp": int(call.created_at.timestamp()),  # Unix timestamp
                "duration": int(call.duration.total_seconds()) if call.duration else None,
                "is_moderator": call.moderator and call.moderator.id == user_profile.id,
                # Keep additional fields for backward compatibility
                "state": call.state,
                "call_url": call.jitsi_room_url,
                "created_at": call.created_at.isoformat(),
                "started_at": call.answered_at.isoformat() if call.answered_at else None,
                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                "sender": {
                    "user_id": call.sender.id,
                    "full_name": call.sender.full_name,
                    "email": call.sender.delivery_email,
                },
                "receiver": {
                    "user_id": call.receiver.id,
                    "full_name": call.receiver.full_name,
                    "email": call.receiver.delivery_email,
                },
            }
        })

    except Exception as e:
        logger.error(f"Failed to get call status: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get call status: {str(e)}"
        }, status=500)


@require_http_methods(["GET"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def get_call_history(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Get call history for the user with cursor-based pagination"""
    import base64
    try:
        # Get query parameters
        limit = min(int(request.GET.get("limit", 50)), 100)
        cursor = request.GET.get("cursor", "").strip()
        call_type_filter = request.GET.get("call_type", "").strip()  # video, audio, or empty for all
        status_filter = request.GET.get("status", "").strip()  # missed, answered, all

        # Base query - calls where user was sender or receiver
        query = Call.objects.filter(
            models.Q(sender=user_profile) | models.Q(receiver=user_profile),
            realm=user_profile.realm
        )

        # Apply call type filter if specified
        if call_type_filter in ['video', 'audio']:
            query = query.filter(call_type=call_type_filter)

        # Apply status filter if specified
        if status_filter == 'missed':
            query = query.filter(state='missed')
        elif status_filter == 'answered':
            query = query.filter(state__in=['accepted', 'ended'])

        # Parse cursor for pagination
        if cursor:
            try:
                decoded_cursor = base64.b64decode(cursor).decode('utf-8')
                cursor_parts = decoded_cursor.split('_', 1)
                if len(cursor_parts) == 2:
                    cursor_timestamp = cursor_parts[0]
                    cursor_call_id = cursor_parts[1]
                    
                    # Filter calls created before cursor or same time with lower call_id
                    query = query.filter(
                        models.Q(created_at__lt=cursor_timestamp) |
                        models.Q(created_at=cursor_timestamp, call_id__lt=cursor_call_id)
                    )
            except Exception as e:
                logger.warning(f"Invalid cursor format: {e}")
                # Continue without cursor if parsing fails

        # Order by created_at descending, then call_id for consistent ordering
        calls = query.order_by("-created_at", "-call_id")[:limit + 1]  # Fetch one extra to check has_more
        
        # Check if there are more results
        has_more = len(calls) > limit
        if has_more:
            calls = calls[:limit]  # Remove the extra record

        call_list = []
        last_call = None
        for call in calls:
            other_user = call.receiver if call.sender.id == user_profile.id else call.sender
            last_call = call

            call_list.append({
                "call_id": str(call.call_id),
                "call_type": call.call_type,
                "state": call.state,
                "was_initiator": call.sender.id == user_profile.id,
                "other_user": {
                    "user_id": other_user.id,
                    "full_name": other_user.full_name,
                    "email": other_user.delivery_email,
                },
                "created_at": call.created_at.isoformat(),
                "started_at": call.answered_at.isoformat() if call.answered_at else None,
                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                "duration_seconds": (
                    int((call.ended_at - call.answered_at).total_seconds())
                    if call.answered_at and call.ended_at else None
                )
            })

        # Generate next cursor if there are more results
        next_cursor = None
        if has_more and last_call:
            cursor_string = f"{last_call.created_at.isoformat()}_{str(last_call.call_id)}"
            next_cursor = base64.b64encode(cursor_string.encode('utf-8')).decode('utf-8')

        return JsonResponse({
            "result": "success",
            "calls": call_list,
            "next_cursor": next_cursor,
            "has_more": has_more
        })

    except Exception as e:
        logger.error(f"Failed to get call history: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get call history: {str(e)}"
        }, status=500)






# Essential API Endpoints for Flutter Integration


def session_or_basic_api_view(
    webhook_client_name: str = "Zulip",
) -> Callable:
    """Allow session auth (web app) or HTTP Basic auth (API clients) for the same endpoint."""

    def decorator(
        view_func: Callable[..., JsonResponse],
    ) -> Callable[..., HttpResponse]:
        @csrf_exempt
        @wraps(view_func)
        def _wrapped(
            request: HttpRequest, *args: object, **kwargs: object
        ) -> HttpResponse:
            # Prefer session when the user is already logged in (e.g. web app with cookies).
            if request.user.is_authenticated:
                user_profile = request.user
                rate_limit_user(request, user_profile, domain="api_by_user")
                validate_account_and_subdomain(request, user_profile)
                return view_func(request, user_profile, *args, **kwargs)

            # Otherwise require HTTP Basic auth for API clients.
            if "Authorization" not in request.headers:
                raise UnauthorizedError()

            try:
                role, api_key = get_basic_credentials(request)
                user_profile = validate_api_key(
                    request,
                    role,
                    api_key,
                    allow_webhook_access=True,
                    client_name=full_webhook_client_name(webhook_client_name),
                )
                request_notes = RequestNotes.get_notes(request)
                request_notes.is_webhook_view = True
            except JsonableError as e:
                raise UnauthorizedError(e.msg)

            rate_limit_user(request, user_profile, domain="api_by_user")
            return view_func(request, user_profile, *args, **kwargs)

        return _wrapped

    return decorator


@require_http_methods(["POST"])
@session_or_basic_api_view(webhook_client_name="Zulip")
def create_embedded_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Create an embedded call for integration with Zulip's compose functionality.
    This is a wrapper around create_call that provides embedded integration.
    """
    try:
        # Extract parameters
        recipient_user_id = request.POST.get("user_id")
        is_video_call = request.POST.get("is_video_call", "true").lower() == "true"
        redirect_to_meeting = request.POST.get("redirect_to_meeting", "false").lower() == "true"

        # Validate that user_id is provided
        if not recipient_user_id:
            return JsonResponse({
                "result": "error",
                "message": "user_id is required"
            }, status=400)

        # Use shared implementation (avoids re-running Basic auth when already session-authenticated)
        response = _create_call_impl(request, user_profile)
        
        if response.status_code == 200:
            data = json.loads(response.content)
            if data.get('result') == 'success':
                # If redirect is requested, return redirect format
                if redirect_to_meeting:
                    return JsonResponse({
                        "result": "success",
                        "action": "redirect",
                        "redirect_url": data.get('call_url'),
                        "call_id": data.get('call_id'),
                        "message": "Call created successfully"
                    })
                else:
                    return response
        
        return response

    except Exception as e:
        logger.error(f"Failed to create embedded call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to create embedded call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def acknowledge_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Acknowledge receipt of call notification (sets status to 'ringing')
    """
    try:
        # Extract and validate request data
        request_data = extract_request_data(request, required_fields=['call_id', 'status'])
        
        # Log request data for debugging
        logger.info(f"Acknowledge call request - User: {user_profile.id}")
        logger.info(f"Request data: {request_data['data']}")
        logger.info(f"Request POST data: {dict(request.POST)}")
        logger.info(f"Request GET data: {dict(request.GET)}")

        # Check for validation errors
        if request_data['has_errors']:
            error_msg = "; ".join(request_data['errors'])
            logger.error(f"Acknowledge call validation error: {error_msg}")
            return JsonResponse({
                "result": "error",
                "message": error_msg
            }, status=400)

        call_id = request_data['data']['call_id']
        status = request_data['data']['status']

        if status not in ['ringing']:
            error_msg = f"Invalid status parameter. Must be 'ringing'. Received: '{status}'"
            logger.error(f"Acknowledge call error: {error_msg}")
            return JsonResponse({
                "result": "error",
                "message": error_msg
            }, status=400)

        # Get call
        try:
            call = Call.objects.get(call_id=call_id, receiver=user_profile)
        except Call.DoesNotExist:
            error_msg = f"Call not found or you're not the receiver. Call ID: {call_id}, User: {user_profile.id}"
            logger.error(f"Acknowledge call error: {error_msg}")
            return JsonResponse({
                "result": "error",
                "message": "Call not found or you're not the receiver"
            }, status=404)

        # Check if call can be acknowledged - accept both 'calling' and 'ringing' states
        # This fixes the race condition where the call might already be in 'ringing' state
        if call.state not in ['calling', 'ringing']:
            error_msg = f"Call cannot be acknowledged. Must be in 'calling' or 'ringing' state. Current status: {call.state}"
            logger.error(f"Acknowledge call error: {error_msg}")
            return JsonResponse({
                "result": "error",
                "message": error_msg
            }, status=400)

        # Update call state to ringing
        with transaction.atomic():
            call.state = 'ringing'
            call.last_heartbeat_receiver = timezone.now()
            call.save(update_fields=['state', 'last_heartbeat_receiver'])

            # Create acknowledgment event
            CallEvent.objects.create(
                call=call,
                event_type='acknowledged',
                user=user_profile,
                metadata={'status': status}
            )

        # Use action function to send ringing event to sender
        do_send_call_ringing_event(user_profile.realm, call)

        logger.info(f"Call {call_id} acknowledged by {user_profile.id}")

        return JsonResponse({
            'result': 'success',
            'call_status': call.state,
            'message': 'Call acknowledged successfully'
        })

    except Exception as e:
        error_msg = f"Unexpected error acknowledging call: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": "Internal server error"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def heartbeat(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Update heartbeat timestamp for active call"""
    try:
        call_id = request.POST.get("call_id")
        if not call_id:
            raise JsonableError("call_id is required")
        
        call = Call.objects.get(call_id=call_id)
        
        # Check if user is participant
        if call.sender.id == user_profile.id:
            call.last_heartbeat_sender = timezone.now()
        elif call.receiver.id == user_profile.id:
            call.last_heartbeat_receiver = timezone.now()
        else:
            raise JsonableError("Not a participant in this call")
        
        # Update background state if provided
        is_backgrounded = request.POST.get("is_backgrounded", "false").lower() == "true"
        call.is_backgrounded = is_backgrounded
        
        call.save(update_fields=['last_heartbeat_sender', 'last_heartbeat_receiver', 'is_backgrounded'])
        
        return JsonResponse({"result": "success", "call_state": call.state})
    except Call.DoesNotExist:
        raise JsonableError("Call not found")
    except Exception as e:
        logger.error(f"Heartbeat error: {e}")
        raise


@require_http_methods(["GET"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def get_call_queue(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Get queued calls for the current user"""
    try:
        # Get pending queue entries where user is the busy_user
        queue_entries = CallQueue.objects.filter(
            busy_user=user_profile,
            status='pending',
            expires_at__gt=timezone.now()
        ).order_by('created_at')
        
        queue_list = []
        for entry in queue_entries:
            queue_list.append({
                "queue_id": str(entry.queue_id),
                "caller": {
                    "user_id": entry.caller.id,
                    "full_name": entry.caller.full_name,
                    "email": entry.caller.delivery_email,
                },
                "call_type": entry.call_type,
                "created_at": entry.created_at.isoformat(),
                "expires_at": entry.expires_at.isoformat(),
            })
        
        return JsonResponse({
            "result": "success",
            "queue": queue_list,
            "count": len(queue_list)
        })
    
    except Exception as e:
        logger.error(f"Failed to get call queue: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get call queue: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def cancel_queued_call(request: HttpRequest, user_profile: UserProfile, queue_id: str) -> JsonResponse:
    """Cancel a queued call"""
    try:
        with transaction.atomic():
            try:
                queue_entry = CallQueue.objects.select_for_update().get(
                    queue_id=queue_id,
                    realm=user_profile.realm
                )
            except CallQueue.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Queue entry not found"
                }, status=404)
            
            # Only caller can cancel
            if queue_entry.caller.id != user_profile.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Not authorized to cancel this queued call"
                }, status=403)
            
            # Check if already processed
            if queue_entry.status != 'pending':
                return JsonResponse({
                    "result": "error",
                    "message": f"Queue entry already {queue_entry.status}"
                }, status=400)
            
            # Mark as cancelled
            queue_entry.status = 'cancelled'
            queue_entry.save()
            
            logger.info(f"Cancelled queue entry {queue_id} by user {user_profile.id}")
            
            return JsonResponse({
                "result": "success",
                "message": "Queued call cancelled successfully"
            })
    
    except Exception as e:
        logger.error(f"Failed to cancel queued call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to cancel queued call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def leave_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Leave a call (for non-moderators) - same as end_call but explicit"""
    # This is now handled in end_call() function - it checks if user is moderator
    # If moderator: ends call for everyone
    # If participant: just leaves the call
    return end_call(request, user_profile, call_id)


# ============================================================================
# GROUP CALL ENDPOINTS
# ============================================================================


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def create_group_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Create a new group call.

    POST parameters:
    - call_type: "video" or "audio" (required)
    - title: Optional title for the call
    - stream_id: Optional stream ID to associate call with
    - topic: Optional topic name (requires stream_id)
    - user_ids: Optional comma-separated list of user IDs to invite immediately
    """
    from ..models import GroupCall, GroupCallParticipant
    from ..actions import do_create_group_call, do_invite_to_group_call

    try:
        with transaction.atomic():
            # Extract and validate parameters
            call_type = request.POST.get("call_type", "video").lower()
            if call_type not in ["video", "audio"]:
                return JsonResponse({
                    "result": "error",
                    "message": "call_type must be 'video' or 'audio'"
                }, status=400)

            title = request.POST.get("title", "").strip()
            stream_id = request.POST.get("stream_id", "").strip()
            topic = request.POST.get("topic", "").strip()

            # Validate stream/topic combination
            stream = None
            if stream_id:
                try:
                    from zerver.models import Stream
                    stream = Stream.objects.get(id=int(stream_id), realm=user_profile.realm)
                except (Stream.DoesNotExist, ValueError):
                    return JsonResponse({
                        "result": "error",
                        "message": f"Stream not found: {stream_id}"
                    }, status=404)

            # Generate Jitsi room details
            room_id = f"zulip-group-call-{uuid.uuid4().hex[:16]}"
            jitsi_server = getattr(settings, 'JITSI_SERVER_URL', 'https://dev.meet.xandylearning.in')
            jitsi_url = f"{jitsi_server}/{room_id}"

            # Create group call
            group_call = GroupCall.objects.create(
                call_type=call_type,
                host=user_profile,
                stream=stream,
                topic=topic if stream else None,
                jitsi_room_name=room_id,
                jitsi_room_url=jitsi_url,
                title=title if title else None,
                realm=user_profile.realm,
            )

            # Create host as first participant (already joined)
            GroupCallParticipant.objects.create(
                call=group_call,
                user=user_profile,
                state="joined",
                is_host=True,
                joined_at=timezone.now(),
                last_heartbeat=timezone.now(),
            )

            # Send group call created event
            do_create_group_call(user_profile.realm, group_call)

            # Invite users if specified
            user_ids_str = request.POST.get("user_ids", "").strip()
            invited_users = []
            if user_ids_str:
                try:
                    user_ids = [int(uid.strip()) for uid in user_ids_str.split(",")]
                    invited_users = list(
                        UserProfile.objects.filter(
                            id__in=user_ids,
                            realm=user_profile.realm,
                            is_active=True
                        ).exclude(id=user_profile.id)  # Don't invite host
                    )

                    if invited_users:
                        invite_results = do_invite_to_group_call(
                            user_profile.realm,
                            group_call,
                            user_profile,
                            invited_users
                        )

                        # Send push notifications to all invited users
                        for user in invited_users:
                            push_data = {
                                "call_id": str(group_call.call_id),
                                "sender_id": str(user_profile.id),
                                "sender_name": user_profile.full_name,
                                "call_type": group_call.call_type,
                                "jitsi_url": jitsi_url,
                                "title": title or "Group Call",
                            }
                            transaction.on_commit(
                                lambda u=user, d=push_data: send_call_push_notification(u, d)
                            )

                except (ValueError, TypeError) as e:
                    logger.warning(f"Invalid user_ids format: {e}")

            logger.info(
                f"Group call {group_call.call_id} created by {user_profile.id} "
                f"with {len(invited_users)} invites"
            )

            return JsonResponse({
                "result": "success",
                "call_id": str(group_call.call_id),
                "call_url": jitsi_url,
                "call_type": group_call.call_type,
                "title": group_call.title,
                "room_name": group_call.jitsi_room_name,
                "host": {
                    "user_id": user_profile.id,
                    "full_name": user_profile.full_name,
                },
                "invited_count": len(invited_users),
            })

    except Exception as e:
        logger.error(f"Failed to create group call: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to create group call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def invite_to_group_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """
    Invite users to an existing group call.

    POST parameters:
    - user_ids: Comma-separated list of user IDs to invite (required)
    """
    from ..models import GroupCall
    from ..actions import do_invite_to_group_call

    try:
        # Get the group call
        try:
            group_call = GroupCall.objects.get(
                call_id=call_id,
                realm=user_profile.realm
            )
        except GroupCall.DoesNotExist:
            return JsonResponse({
                "result": "error",
                "message": "Group call not found"
            }, status=404)

        # Check if call is still active
        if group_call.state != "active":
            return JsonResponse({
                "result": "error",
                "message": f"Cannot invite to ended call"
            }, status=400)

        # Check authorization - only host and joined participants can invite
        participant = group_call.participants.filter(user=user_profile).first()
        if not participant or participant.state not in ["joined"]:
            return JsonResponse({
                "result": "error",
                "message": "Only active participants can invite others"
            }, status=403)

        # Parse user IDs
        user_ids_str = request.POST.get("user_ids", "").strip()
        if not user_ids_str:
            return JsonResponse({
                "result": "error",
                "message": "user_ids parameter is required"
            }, status=400)

        try:
            user_ids = [int(uid.strip()) for uid in user_ids_str.split(",")]
        except ValueError:
            return JsonResponse({
                "result": "error",
                "message": "Invalid user_ids format"
            }, status=400)

        # Get valid users to invite
        users_to_invite = list(
            UserProfile.objects.filter(
                id__in=user_ids,
                realm=user_profile.realm,
                is_active=True
            )
        )

        if not users_to_invite:
            return JsonResponse({
                "result": "error",
                "message": "No valid users to invite"
            }, status=400)

        # Invite users using action function
        invite_results = do_invite_to_group_call(
            user_profile.realm,
            group_call,
            user_profile,
            users_to_invite
        )

        # Send push notifications to all invited users
        with transaction.atomic():
            for user in users_to_invite:
                push_data = {
                    "call_id": str(group_call.call_id),
                    "sender_id": str(user_profile.id),
                    "sender_name": user_profile.full_name,
                    "call_type": group_call.call_type,
                    "jitsi_url": group_call.jitsi_room_url,
                    "title": group_call.title or "Group Call",
                }
                transaction.on_commit(
                    lambda u=user, d=push_data: send_call_push_notification(u, d)
                )

        logger.info(
            f"Group call {call_id}: {len(users_to_invite)} users invited by {user_profile.id}"
        )

        return JsonResponse({
            "result": "success",
            "invited_count": len(users_to_invite),
            "online_count": len(invite_results["invited"]),
            "offline_count": len(invite_results["offline"]),
        })

    except Exception as e:
        logger.error(f"Failed to invite to group call: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to invite users: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def join_group_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Join an existing group call."""
    from ..models import GroupCall, GroupCallParticipant
    from ..actions import do_join_group_call

    try:
        with transaction.atomic():
            # Get the group call
            try:
                group_call = GroupCall.objects.select_for_update().get(
                    call_id=call_id,
                    realm=user_profile.realm
                )
            except GroupCall.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Group call not found"
                }, status=404)

            # Check if call is still active
            if group_call.state != "active":
                return JsonResponse({
                    "result": "error",
                    "message": "Call has ended"
                }, status=400)

            # Check participant limit
            active_count = group_call.get_active_participant_count()
            if active_count >= group_call.max_participants:
                return JsonResponse({
                    "result": "error",
                    "message": f"Call is full ({group_call.max_participants} participants)"
                }, status=400)

            # Get or create participant record
            participant, created = GroupCallParticipant.objects.get_or_create(
                call=group_call,
                user=user_profile,
                defaults={"state": "joined", "joined_at": timezone.now()}
            )

            if not created:
                # Update existing participant
                if participant.state == "joined":
                    return JsonResponse({
                        "result": "error",
                        "message": "Already in call"
                    }, status=400)

                participant.state = "joined"
                participant.joined_at = timezone.now()
                participant.save(update_fields=["state", "joined_at"])

            # Update heartbeat
            participant.last_heartbeat = timezone.now()
            participant.save(update_fields=["last_heartbeat"])

            # Send join event to all participants
            do_join_group_call(user_profile.realm, group_call, user_profile)

            logger.info(f"User {user_profile.id} joined group call {call_id}")

            return JsonResponse({
                "result": "success",
                "call_url": group_call.jitsi_room_url,
                "call_type": group_call.call_type,
                "title": group_call.title,
                "participant_count": group_call.get_active_participant_count(),
            })

    except Exception as e:
        logger.error(f"Failed to join group call: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to join call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def leave_group_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Leave a group call."""
    from ..models import GroupCall
    from ..actions import do_leave_group_call

    try:
        with transaction.atomic():
            # Get the group call
            try:
                group_call = GroupCall.objects.select_for_update().get(
                    call_id=call_id,
                    realm=user_profile.realm
                )
            except GroupCall.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Group call not found"
                }, status=404)

            # Get participant record
            try:
                participant = group_call.participants.select_for_update().get(
                    user=user_profile
                )
            except group_call.participants.model.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Not in this call"
                }, status=404)

            # Check if already left
            if participant.state in ["left", "declined", "missed"]:
                return JsonResponse({
                    "result": "error",
                    "message": "Already left call"
                }, status=400)

            # Update participant state
            participant.state = "left"
            participant.left_at = timezone.now()
            participant.save(update_fields=["state", "left_at"])

            # Send leave event to other participants
            do_leave_group_call(user_profile.realm, group_call, user_profile)

            logger.info(f"User {user_profile.id} left group call {call_id}")

            return JsonResponse({
                "result": "success",
                "message": "Left call successfully"
            })

    except Exception as e:
        logger.error(f"Failed to leave group call: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to leave call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def decline_group_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Decline a group call invitation."""
    from ..models import GroupCall
    from ..actions import do_decline_group_call

    try:
        with transaction.atomic():
            # Get the group call
            try:
                group_call = GroupCall.objects.select_for_update().get(
                    call_id=call_id,
                    realm=user_profile.realm
                )
            except GroupCall.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Group call not found"
                }, status=404)

            # Get participant record
            try:
                participant = group_call.participants.select_for_update().get(
                    user=user_profile
                )
            except group_call.participants.model.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Not invited to this call"
                }, status=404)

            # Can only decline if invited or ringing
            if participant.state not in ["invited", "ringing"]:
                return JsonResponse({
                    "result": "error",
                    "message": f"Cannot decline call in state: {participant.state}"
                }, status=400)

            # Update participant state
            participant.state = "declined"
            participant.save(update_fields=["state"])

            # Send decline event
            do_decline_group_call(user_profile.realm, group_call, user_profile)

            logger.info(f"User {user_profile.id} declined group call {call_id}")

            return JsonResponse({
                "result": "success",
                "message": "Call declined"
            })

    except Exception as e:
        logger.error(f"Failed to decline group call: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to decline call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def end_group_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """End a group call (host only)."""
    from ..models import GroupCall
    from ..actions import do_end_group_call

    try:
        with transaction.atomic():
            # Get the group call
            try:
                group_call = GroupCall.objects.select_for_update().get(
                    call_id=call_id,
                    realm=user_profile.realm
                )
            except GroupCall.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Group call not found"
                }, status=404)

            # Check if user is the host
            if group_call.host.id != user_profile.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Only the host can end the call"
                }, status=403)

            # Check if already ended
            if group_call.state == "ended":
                return JsonResponse({
                    "result": "error",
                    "message": "Call already ended"
                }, status=400)

            # End the call
            group_call.state = "ended"
            group_call.ended_at = timezone.now()
            group_call.save(update_fields=["state", "ended_at"])

            # Update all joined participants to left
            group_call.participants.filter(state="joined").update(
                state="left",
                left_at=timezone.now()
            )

            # Send end event to all participants
            do_end_group_call(user_profile.realm, group_call)

            logger.info(f"Group call {call_id} ended by host {user_profile.id}")

            return JsonResponse({
                "result": "success",
                "message": "Call ended successfully"
            })

    except Exception as e:
        logger.error(f"Failed to end group call: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to end call: {str(e)}"
        }, status=500)


@require_http_methods(["GET"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def get_group_call_status(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Get the current status of a group call."""
    from ..models import GroupCall

    try:
        # Get the group call
        try:
            group_call = GroupCall.objects.get(
                call_id=call_id,
                realm=user_profile.realm
            )
        except GroupCall.DoesNotExist:
            return JsonResponse({
                "result": "error",
                "message": "Group call not found"
            }, status=404)

        # Check if user is a participant
        is_participant = group_call.participants.filter(user=user_profile).exists()
        if not is_participant:
            return JsonResponse({
                "result": "error",
                "message": "Not authorized to view this call"
            }, status=403)

        # Get participant counts by state
        participants_data = group_call.participants.select_related("user").all()

        return JsonResponse({
            "result": "success",
            "call": {
                "call_id": str(group_call.call_id),
                "call_type": group_call.call_type,
                "state": group_call.state,
                "title": group_call.title,
                "jitsi_url": group_call.jitsi_room_url,
                "host": {
                    "user_id": group_call.host.id,
                    "full_name": group_call.host.full_name,
                },
                "stream_id": group_call.stream_id if group_call.stream else None,
                "topic": group_call.topic,
                "created_at": group_call.created_at.isoformat(),
                "ended_at": group_call.ended_at.isoformat() if group_call.ended_at else None,
                "participant_count": len([p for p in participants_data if p.state == "joined"]),
                "max_participants": group_call.max_participants,
            }
        })

    except Exception as e:
        logger.error(f"Failed to get group call status: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get call status: {str(e)}"
        }, status=500)


@require_http_methods(["GET"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def get_group_call_participants(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Get the list of participants in a group call."""
    from ..models import GroupCall

    try:
        # Get the group call
        try:
            group_call = GroupCall.objects.get(
                call_id=call_id,
                realm=user_profile.realm
            )
        except GroupCall.DoesNotExist:
            return JsonResponse({
                "result": "error",
                "message": "Group call not found"
            }, status=404)

        # Check if user is a participant
        is_participant = group_call.participants.filter(user=user_profile).exists()
        if not is_participant:
            return JsonResponse({
                "result": "error",
                "message": "Not authorized to view participants"
            }, status=403)

        # Get all participants with user info
        participants = group_call.participants.select_related("user").all()

        participants_list = []
        for p in participants:
            participants_list.append({
                "user_id": p.user.id,
                "full_name": p.user.full_name,
                "email": p.user.delivery_email,
                "state": p.state,
                "is_host": p.is_host,
                "invited_at": p.invited_at.isoformat(),
                "joined_at": p.joined_at.isoformat() if p.joined_at else None,
                "left_at": p.left_at.isoformat() if p.left_at else None,
            })

        return JsonResponse({
            "result": "success",
            "participants": participants_list,
            "total_count": len(participants_list),
            "joined_count": len([p for p in participants if p.state == "joined"]),
        })

    except Exception as e:
        logger.error(f"Failed to get group call participants: {e}", exc_info=True)
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get participants: {str(e)}"
        }, status=500)