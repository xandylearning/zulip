import uuid
import logging
import json
from datetime import timedelta
from typing import Dict, Any

from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
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
    zulip_login_required,
    authenticated_json_view
)
from zerver.models import UserProfile
from zerver.models.users import get_user_by_delivery_email
from zerver.lib.push_notifications import send_push_notifications
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.tornado.django_api import send_event_on_commit

# Import plugin models
from ..models import Call, CallEvent

logger = logging.getLogger(__name__)


def generate_jitsi_url(call_id: str) -> tuple[str, str]:
    """Generate Jitsi meeting URL and room ID"""
    from django.conf import settings

    room_id = f"{getattr(settings, 'JITSI_MEETING_PREFIX', 'zulip-call-')}{call_id}"
    jitsi_url = f"{getattr(settings, 'JITSI_SERVER_URL', 'https://dev.meet.xandylearning.in')}/{room_id}"

    return jitsi_url, room_id


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
            'call_type': call_data.get('call_type', 'voice'),
            'user_id': str(recipient.id),
            'time': str(int(timezone.now().timestamp())),
        }

        # Send specialized FCM call notifications
        success_count = send_fcm_call_notifications(
            devices=list(fcm_devices),
            call_data=enhanced_call_data,
            realm_host=recipient.realm.host,
            realm_url=recipient.realm.url,
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


def send_call_event(user_profile: UserProfile, call: Call, event_type: str, extra_data: dict = None) -> None:
    """Send real-time WebSocket event about call status using Zulip's event system"""
    try:
        # Prepare event data for WebSocket
        event_data = {
            'type': 'call_event',
            'event_type': event_type,
            'call_id': str(call.call_id),
            'call_type': call.call_type,
            'sender_id': call.sender.id,
            'sender_name': call.sender.full_name,
            'receiver_id': call.receiver.id,
            'receiver_name': call.receiver.full_name,
            'jitsi_url': call.jitsi_room_url,
            'state': call.state,
            'created_at': call.created_at.isoformat(),
            'timestamp': timezone.now().isoformat(),
        }

        # Add extra data if provided
        if extra_data:
            event_data.update(extra_data)

        # Send WebSocket event to the user
        send_event_on_commit(
            realm=user_profile.realm,
            event=event_data,
            users=[user_profile.id]
        )

        logger.info(f"WebSocket call event {event_type} sent to user {user_profile.id} for call {call.call_id}")

    except Exception as e:
        logger.error(f"Failed to send call event: {str(e)}")
        # Fallback to logging
        logger.info(f"Call event {event_type} for call {call.call_id} to user {user_profile.id}")


def cleanup_stale_calls() -> int:
    """Clean up stale calls that are stuck in active states"""
    from django.conf import settings
    from datetime import timedelta
    
    # Get timeout settings
    call_timeout_minutes = getattr(settings, 'CALL_TIMEOUT_MINUTES', 30)
    stale_threshold = timezone.now() - timedelta(minutes=call_timeout_minutes)
    
    # Find calls that are stuck in active states for too long
    stale_calls = Call.objects.filter(
        state__in=['calling', 'ringing', 'accepted'],
        created_at__lt=stale_threshold
    )
    
    count = 0
    for call in stale_calls:
        # Update call state with finer semantics
        now_ts = timezone.now()
        if call.state == 'ringing':
            call.state = 'missed'
            call.ended_at = now_ts
        elif call.state in ['calling', 'accepted']:
            call.state = 'timeout'
            call.ended_at = now_ts
        else:
            call.state = 'timeout'
            call.ended_at = now_ts
        call.save()
        
        # Create timeout event
        event_type = 'missed' if call.state == 'missed' else 'timeout'
        CallEvent.objects.create(
            call=call,
            event_type=event_type,
            user=call.sender,
            metadata={'reason': 'automatic_cleanup', 'timeout_minutes': call_timeout_minutes}
        )

        # Emit WebSocket events to both participants
        try:
            send_call_event(call.sender, call, event_type, {'auto': True})
        except Exception:
            pass
        try:
            send_call_event(call.receiver, call, event_type, {'auto': True})
        except Exception:
            pass
        
        logger.info(f"Cleaned up stale call {call.call_id} (timeout after {call_timeout_minutes} minutes)")
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




@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def create_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Create a new call with full database tracking"""
    try:
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

            # Check if caller is already in an active call
            caller_in_call = Call.objects.filter(
                models.Q(sender=user_profile) | models.Q(receiver=user_profile),
                state__in=["calling", "ringing", "accepted"]
            ).first()

            if caller_in_call:
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
                return JsonResponse({
                    "result": "error",
                    "message": "The recipient is already in a call",
                    "existing_call_id": str(receiver_in_call.call_id)
                }, status=409)

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

            # Send push notification with participant URL
            push_data = {
                "type": "call_invitation",
                "call_id": str(call.call_id),
                "call_url": participant_url,  # Participant URL for the recipient
                "call_type": call.call_type,
                "caller_name": user_profile.full_name,
                "caller_id": user_profile.id,
                "room_name": call.jitsi_room_name,
            }

            # Send legacy push notification (for compatibility)
            send_call_push_notification(recipient, push_data)

            # Send specialized FCM call notification in exact format specified
            fcm_call_data = {
                "call_id": str(call.call_id),
                "sender_id": str(user_profile.id),
                "sender_name": user_profile.full_name,
                "call_type": call.call_type,
                "jitsi_url": participant_url,
            }
            send_fcm_call_notification(recipient, fcm_call_data)

            return JsonResponse({
                "result": "success",
                "call_id": str(call.call_id),
                "call_url": moderator_url,  # Moderator URL for the initiator
                "participant_url": participant_url,  # Available if needed
                "call_type": call.call_type,
                "room_name": call.jitsi_room_name,
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
def respond_to_call(request: HttpRequest, user_profile: UserProfile, call_id: str) -> JsonResponse:
    """Accept or decline a call invitation with full tracking"""
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

                # Notify caller
                notification_data = {
                    "type": "call_accepted",
                    "call_id": str(call.call_id),
                    "call_url": call.jitsi_room_url,
                    "accepter_name": user_profile.full_name,
                }
                send_call_push_notification(call.sender, notification_data)

            else:
                call.state = "rejected"
                call.ended_at = timezone.now()
                event_type = "declined"

            call.save()

            # Emit WebSocket events to both participants
            try:
                send_call_event(call.sender, call, event_type)
            except Exception:
                pass
            try:
                send_call_event(call.receiver, call, event_type)
            except Exception:
                pass

            # Create event
            CallEvent.objects.create(
                call=call,
                event_type=event_type,
                user=user_profile
            )

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

            # Mark call as ended
            call.state = "ended"
            call.ended_at = timezone.now()
            call.save()

            # Create event
            CallEvent.objects.create(
                call=call,
                event_type="ended",
                user=user_profile
            )

            # Emit WebSocket events to both participants
            try:
                send_call_event(call.sender, call, 'ended')
            except Exception:
                pass
            try:
                send_call_event(call.receiver, call, 'ended')
            except Exception:
                pass

            return JsonResponse({
                "result": "success",
                "message": "Call ended successfully"
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

            # Notify both users via WS
            try:
                send_call_event(call.sender, call, 'cancelled')
            except Exception:
                pass
            try:
                send_call_event(call.receiver, call, 'cancelled')
            except Exception:
                pass

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

        return JsonResponse({
            "result": "success",
            "call": {
                "call_id": str(call.call_id),
                "state": call.state,
                "call_url": call.jitsi_room_url,
                "call_type": call.call_type,
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
    """Get call history for the user"""
    try:
        # Get query parameters
        limit = min(int(request.GET.get("limit", 50)), 100)
        offset = int(request.GET.get("offset", 0))

        # Get calls where user was sender or receiver
        calls = Call.objects.filter(
            models.Q(sender=user_profile) | models.Q(receiver=user_profile),
            realm=user_profile.realm
        ).order_by("-created_at")[offset:offset + limit]

        call_list = []
        for call in calls:
            other_user = call.receiver if call.sender.id == user_profile.id else call.sender

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

        return JsonResponse({
            "result": "success",
            "calls": call_list,
            "has_more": len(call_list) == limit
        })

    except Exception as e:
        logger.error(f"Failed to get call history: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get call history: {str(e)}"
        }, status=500)






# Essential API Endpoints for Flutter Integration

@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
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

        # Use the existing create_call function
        response = create_call(request, user_profile)
        
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
        call_id = (request.POST.get("call_id") or request.GET.get("call_id") or "").strip()
        status = (request.POST.get("status") or request.GET.get("status") or "").strip()

        if not call_id:
            raise JsonableError("Missing required parameter: call_id")
        if status not in ['ringing']:
            raise JsonableError("Invalid status. Must be 'ringing'")

        # Get call
        try:
            call = Call.objects.get(call_id=call_id, receiver=user_profile)
        except Call.DoesNotExist:
            raise JsonableError("Call not found or you're not the receiver")

        # Check if call can be acknowledged
        if call.state not in ['calling']:
            raise JsonableError(f"Call cannot be acknowledged. Current status: {call.state}")

        # Update call state to ringing
        with transaction.atomic():
            call.state = 'ringing'
            call.save()

            # Create acknowledgment event
            CallEvent.objects.create(
                call=call,
                event_type='acknowledged',
                user=user_profile,
                metadata={'status': status}
            )

        # Send WebSocket event to sender (participant_ringing)
        send_call_event(call.sender, call, 'participant_ringing', {
            'receiver_name': user_profile.full_name,
            'receiver_id': user_profile.id
        })

        logger.info(f"Call {call_id} acknowledged by {user_profile.id}")

        return JsonResponse({
            'result': 'success',
            'call_status': call.state,
            'message': 'Call acknowledged successfully'
        })

    except Exception as e:
        logger.error(f"Error acknowledging call: {str(e)}")
        raise