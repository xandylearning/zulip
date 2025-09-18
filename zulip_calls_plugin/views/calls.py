import uuid
import logging
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

# Import plugin models
from ..models import Call, CallEvent

logger = logging.getLogger(__name__)


def generate_jitsi_url(call_id: str) -> tuple[str, str]:
    """Generate Jitsi meeting URL and room ID"""
    from django.conf import settings

    room_id = f"{getattr(settings, 'JITSI_MEETING_PREFIX', 'zulip-call-')}{call_id}"
    jitsi_url = f"{getattr(settings, 'JITSI_SERVER_URL', 'https://meet.jit.si')}/{room_id}"

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
        payload_data_to_encrypt = {
            'type': 'call',
            'call_id': call_data.get('call_id'),
            'sender_id': call_data.get('sender_id'),
            'sender_name': call_data.get('sender_name'),
            'sender_avatar_url': f"/avatar/{call_data.get('sender_id')}",
            'call_type': call_data.get('call_type'),
            'jitsi_url': call_data.get('jitsi_url'),
            'timeout_seconds': getattr(settings, 'CALL_NOTIFICATION_TIMEOUT', 120),
            'realm_uri': recipient.realm.url,
            'realm_name': recipient.realm.name,
            'realm_url': recipient.realm.url,
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
        
        gcm_options = { }

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


def send_call_response_notification(user_profile: UserProfile, call: Call, response: str) -> None:
    """Send notification about call response using correct Zulip API with fallback support"""
    from zerver.models import PushDevice, PushDeviceToken
    from zerver.lib.push_notifications import send_push_notifications, send_push_notifications_legacy
    from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
    
    payload_data_to_encrypt = {
        'type': 'call_response',
        'call_id': str(call.call_id),
        'response': response,
        'receiver_name': call.receiver.full_name,
        'call_type': call.call_type,
        'realm_uri': user_profile.realm.url,
        'realm_name': user_profile.realm.name,
        'realm_url': user_profile.realm.url,
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
            "priority": "normal",
            "time_to_live": 60
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


def send_call_event(user_profile: UserProfile, call: Call, event_type: str) -> None:
    """Send real-time event about call status - simplified version"""
    # For now, just log the event. In a full implementation, this would integrate
    # with Zulip's real-time event system
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
        # Update call state to timeout
        call.state = 'timeout'
        call.ended_at = timezone.now()
        call.save()
        
        # Create timeout event
        CallEvent.objects.create(
            call=call,
            event_type='timeout',
            user=call.sender,
            metadata={'reason': 'automatic_cleanup', 'timeout_minutes': call_timeout_minutes}
        )
        
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
def initiate_quick_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Quick call implementation - generates Jitsi room and sends notification"""
    try:
        # Get request parameters
        recipient_email = request.POST.get("recipient_email")
        is_video_call = request.POST.get("is_video_call", "true").lower() == "true"

        if not recipient_email:
            return JsonResponse({
                "result": "error",
                "message": "recipient_email is required"
            }, status=400)

        # Generate unique room ID
        room_id = str(uuid.uuid4())[:12]  # Short ID for easier joining

        # Get Jitsi server URL (use realm setting or fallback)
        jitsi_server = getattr(user_profile.realm, "jitsi_server_url", None) or "https://meet.jit.si"

        # Add URL parameters to make the initiator a moderator
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

        call_url = f"{jitsi_server}/zulip-call-{room_id}{moderator_params}#config.prejoinPageEnabled=false"

        # Find recipient user with domain flexibility
        recipient = None
        tried_emails = []

        # Try the email as provided - use email field for API compatibility
        try:
            recipient = get_user_by_delivery_email(recipient_email, user_profile.realm)
        except UserProfile.DoesNotExist:
            # Fallback: try to find by the public email field
            try:
                recipient = UserProfile.objects.get(email=recipient_email, realm=user_profile.realm)
                logger.info(f"Found user by public email field: '{recipient_email}'")
            except UserProfile.DoesNotExist:
                tried_emails.append(recipient_email)

            # Try multiple domain variations
            domain_variations = []

            if "@dev.zulip.xandylearning.in" in recipient_email:
                # Try Gmail for dev.zulip.xandylearning.in users
                username = recipient_email.split('@')[0]
                domain_variations = [
                    f"{username}@gmail.com",
                    f"{username}@zulip.com",
                    f"{username}@zulipdev.com"
                ]
            elif "@zulipdev.com" in recipient_email:
                domain_variations = [recipient_email.replace("@zulipdev.com", "@zulip.com")]
            elif "@zulip.com" in recipient_email:
                domain_variations = [recipient_email.replace("@zulip.com", "@zulipdev.com")]

            for alternative_email in domain_variations:
                try:
                    recipient = get_user_by_delivery_email(alternative_email, user_profile.realm)
                    logger.info(f"Found user with alternative email: '{alternative_email}' instead of '{recipient_email}'")
                    break
                except UserProfile.DoesNotExist:
                    tried_emails.append(alternative_email)

        if not recipient:
            return JsonResponse({
                "result": "error",
                "message": f"Recipient not found. Tried: {', '.join(tried_emails)}"
            }, status=404)

        # Prepare call data
        call_data = {
            "type": "call_invitation",
            "call_url": call_url,
            "room_id": room_id,
            "is_video_call": is_video_call,
            "caller_name": user_profile.full_name,
            "caller_id": user_profile.id,
            "caller_email": user_profile.delivery_email,
        }

        # Send push notification to recipient
        send_call_push_notification(recipient, call_data)

        return JsonResponse({
            "result": "success",
            "call_url": call_url,
            "room_id": room_id,
            "message": "Call initiated successfully"
        })

    except Exception as e:
        logger.error(f"Failed to initiate quick call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to initiate call: {str(e)}"
        }, status=500)


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def create_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """Create a new call with full database tracking"""
    try:
        with transaction.atomic():
            # Get request parameters
            recipient_email = request.POST.get("recipient_email")
            is_video_call = request.POST.get("is_video_call", "true").lower() == "true"

            if not recipient_email:
                return JsonResponse({
                    "result": "error",
                    "message": "recipient_email is required"
                }, status=400)

            # Find recipient with domain flexibility
            recipient = None
            tried_emails = []

            # Try the email as provided - use email field for API compatibility
            try:
                recipient = get_user_by_delivery_email(recipient_email, user_profile.realm)
            except UserProfile.DoesNotExist:
                # Fallback: try to find by the public email field
                try:
                    recipient = UserProfile.objects.get(email=recipient_email, realm=user_profile.realm)
                    logger.info(f"Found user by public email field: '{recipient_email}'")
                except UserProfile.DoesNotExist:
                    tried_emails.append(recipient_email)

                # Try multiple domain variations
                domain_variations = []

                if "@dev.zulip.xandylearning.in" in recipient_email:
                    # Try Gmail for dev.zulip.xandylearning.in users
                    username = recipient_email.split('@')[0]
                    domain_variations = [
                        f"{username}@gmail.com",
                        f"{username}@zulip.com",
                        f"{username}@zulipdev.com"
                    ]
                elif "@zulipdev.com" in recipient_email:
                    domain_variations = [recipient_email.replace("@zulipdev.com", "@zulip.com")]
                elif "@zulip.com" in recipient_email:
                    domain_variations = [recipient_email.replace("@zulip.com", "@zulipdev.com")]

                for alternative_email in domain_variations:
                    try:
                        recipient = get_user_by_delivery_email(alternative_email, user_profile.realm)
                        logger.info(f"Found user with alternative email: '{alternative_email}' instead of '{recipient_email}'")
                        break
                    except UserProfile.DoesNotExist:
                        tried_emails.append(alternative_email)

            if not recipient:
                return JsonResponse({
                    "result": "error",
                    "message": f"Recipient not found. Tried: {', '.join(tried_emails)}"
                }, status=404)

            # Check if users are the same
            if user_profile.id == recipient.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Cannot call yourself"
                }, status=400)

            # Check for existing active calls
            existing_call = Call.objects.filter(
                models.Q(initiator=user_profile, recipient=recipient) |
                models.Q(initiator=recipient, recipient=user_profile),
                state__in=["initiated", "ringing", "active"]
            ).first()

            if existing_call:
                return JsonResponse({
                    "result": "error",
                    "message": "Call already in progress with this user",
                    "existing_call_id": str(existing_call.call_id)
                }, status=409)

            # Create call record
            call = Call.objects.create(
                call_type="video" if is_video_call else "audio",
                initiator=user_profile,
                recipient=recipient,
                jitsi_room_name=f"zulip-call-{uuid.uuid4().hex[:12]}",
                realm=user_profile.realm
            )

            # Generate Jitsi URLs - separate URLs for moderator and participant
            jitsi_server = getattr(user_profile.realm, "jitsi_server_url", None) or "https://meet.jit.si"
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
                    "recipient_email": recipient_email,
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

            send_call_push_notification(recipient, push_data)

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
            if call.recipient.id != user_profile.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Not authorized to respond to this call"
                }, status=403)

            # Check call state
            if call.state not in ["initiated", "ringing"]:
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
                call.state = "active"
                call.started_at = timezone.now()
                event_type = "accepted"

                # Notify caller
                notification_data = {
                    "type": "call_accepted",
                    "call_id": str(call.call_id),
                    "call_url": call.jitsi_room_url,
                    "accepter_name": user_profile.full_name,
                }
                send_call_push_notification(call.initiator, notification_data)

            else:
                call.state = "declined"
                call.ended_at = timezone.now()
                event_type = "declined"

            call.save()

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
            if (call.initiator.id != user_profile.id and
                call.recipient.id != user_profile.id):
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
        if (call.initiator.id != user_profile.id and
            call.recipient.id != user_profile.id):
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
                "started_at": call.started_at.isoformat() if call.started_at else None,
                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                "initiator": {
                    "user_id": call.initiator.id,
                    "full_name": call.initiator.full_name,
                    "email": call.initiator.delivery_email,
                },
                "recipient": {
                    "user_id": call.recipient.id,
                    "full_name": call.recipient.full_name,
                    "email": call.recipient.delivery_email,
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

        # Get calls where user was initiator or recipient
        calls = Call.objects.filter(
            models.Q(initiator=user_profile) | models.Q(recipient=user_profile),
            realm=user_profile.realm
        ).order_by("-created_at")[offset:offset + limit]

        call_list = []
        for call in calls:
            other_user = call.recipient if call.initiator.id == user_profile.id else call.initiator

            call_list.append({
                "call_id": str(call.call_id),
                "call_type": call.call_type,
                "state": call.state,
                "was_initiator": call.initiator.id == user_profile.id,
                "other_user": {
                    "user_id": other_user.id,
                    "full_name": other_user.full_name,
                    "email": other_user.delivery_email,
                },
                "created_at": call.created_at.isoformat(),
                "started_at": call.started_at.isoformat() if call.started_at else None,
                "ended_at": call.ended_at.isoformat() if call.ended_at else None,
                "duration_seconds": (
                    int((call.ended_at - call.started_at).total_seconds())
                    if call.started_at and call.ended_at else None
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


@require_http_methods(["POST"])
@zulip_login_required
def create_embedded_call(request: HttpRequest) -> JsonResponse:
    """Create a call and immediately redirect to meeting interface"""
    try:
        with transaction.atomic():
            # Get request parameters
            recipient_email = request.POST.get("recipient_email")
            is_video_call = request.POST.get("is_video_call", "true").lower() == "true"
            redirect_to_meeting = request.POST.get("redirect_to_meeting", "false").lower() == "true"

            if not recipient_email:
                return JsonResponse({
                    "result": "error",
                    "message": "recipient_email is required"
                }, status=400)

            # Debug logging
            logger.info(f"Attempting to create call: recipient_email='{recipient_email}', realm='{request.user.realm.string_id}'")

            # Find recipient - try multiple email formats
            recipient = None
            tried_emails = []

            # Try the email as provided - use email field for API compatibility
            try:
                recipient = get_user_by_delivery_email(recipient_email, request.user.realm)
            except UserProfile.DoesNotExist:
                # Fallback: try to find by the public email field
                try:
                    recipient = UserProfile.objects.get(email=recipient_email, realm=request.user.realm)
                    logger.info(f"Found user by public email field: '{recipient_email}'")
                except UserProfile.DoesNotExist:
                    tried_emails.append(recipient_email)

                # Try multiple domain variations
                domain_variations = []

                if "@dev.zulip.xandylearning.in" in recipient_email:
                    # Try Gmail for dev.zulip.xandylearning.in users
                    username = recipient_email.split('@')[0]
                    domain_variations = [
                        f"{username}@gmail.com",
                        f"{username}@zulip.com",
                        f"{username}@zulipdev.com"
                    ]
                elif "@zulipdev.com" in recipient_email:
                    domain_variations = [recipient_email.replace("@zulipdev.com", "@zulip.com")]
                elif "@zulip.com" in recipient_email:
                    domain_variations = [recipient_email.replace("@zulip.com", "@zulipdev.com")]

                for alternative_email in domain_variations:
                    try:
                        recipient = get_user_by_delivery_email(alternative_email, request.user.realm)
                        logger.info(f"Found user with alternative email: '{alternative_email}' instead of '{recipient_email}'")
                        break
                    except UserProfile.DoesNotExist:
                        tried_emails.append(alternative_email)

            if not recipient:
                # Debug: List some users in the realm to see what emails exist
                from zerver.models import UserProfile as ZulipUserProfile
                realm_users = ZulipUserProfile.objects.filter(realm=request.user.realm)[:10]
                user_emails = [f"'{u.delivery_email}'" for u in realm_users]
                logger.error(f"User not found after trying: {tried_emails}, realm='{request.user.realm.string_id}'")
                logger.error(f"Available users in realm: {', '.join(user_emails)}")
                
                # Provide a more helpful error message
                available_users_text = ', '.join(user_emails[:5])
                if len(user_emails) > 5:
                    available_users_text += f" and {len(user_emails) - 5} more"
                
                return JsonResponse({
                    "result": "error",
                    "message": f"Recipient not found. Tried: {', '.join(tried_emails)}. Available users: {available_users_text}",
                    "available_users": user_emails[:10],  # Include more users in response
                    "tried_emails": tried_emails
                }, status=404)

            # Check if users are the same
            if request.user.id == recipient.id:
                return JsonResponse({
                    "result": "error",
                    "message": "Cannot call yourself"
                }, status=400)

            # Create call record
            call = Call.objects.create(
                call_type="video" if is_video_call else "audio",
                sender=request.user,
                receiver=recipient,
                jitsi_room_name=f"zulip-call-{uuid.uuid4().hex[:12]}",
                realm=request.user.realm
            )

            # Generate Jitsi URLs - separate URLs for moderator and participant
            jitsi_server = getattr(request.user.realm, "jitsi_server_url", None) or "https://meet.jit.si"
            base_room_url = f"{jitsi_server}/{call.jitsi_room_name}"

            # Moderator URL (for initiator) with special parameters
            moderator_params = (
                f"?userInfo.displayName={request.user.full_name}"
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
                user=request.user,
                metadata={
                    "recipient_email": recipient_email,
                    "is_video_call": is_video_call,
                    "embedded": True
                }
            )

            # Send push notification to recipient with participant URL
            push_data = {
                "type": "call_invitation_embedded",
                "call_id": str(call.call_id),
                "call_url": participant_url,  # Participant URL for the recipient
                "call_type": call.call_type,
                "caller_name": request.user.full_name,
                "caller_id": request.user.id,
                "room_name": call.jitsi_room_name,
                "embedded_url": f"/calls/embed/{call.call_id}",
            }

            send_call_push_notification(recipient, push_data)

            # Return response with moderator URL for the initiator
            response_data = {
                "result": "success",
                "call_id": str(call.call_id),
                "call_url": moderator_url,  # Moderator URL for the initiator
                "participant_url": participant_url,  # Available if needed
                "embedded_url": f"/calls/embed/{call.call_id}",  # Embedded interface URL
                "call_type": call.call_type,
                "room_name": call.jitsi_room_name,
                "recipient": {
                    "user_id": recipient.id,
                    "full_name": recipient.full_name,
                    "email": recipient.delivery_email,
                }
            }

            # If redirect_to_meeting is requested, return the moderator URL for immediate redirect
            if redirect_to_meeting:
                response_data["action"] = "redirect"
                response_data["redirect_url"] = moderator_url

            return JsonResponse(response_data)

    except Exception as e:
        logger.error(f"Failed to create embedded call: {e}")
        return JsonResponse({
            "result": "error",
            "message": f"Failed to create embedded call: {str(e)}"
        }, status=500)


@zulip_login_required
def embedded_call_view(request, call_id: str):
    """Serve the embedded call interface"""
    try:
        call = get_object_or_404(Call, call_id=call_id, realm=request.user.realm)

        # Check authorization - user must be participant in the call
        if (call.sender.id != request.user.id and
            call.receiver.id != request.user.id):
            return HttpResponse("Not authorized to join this call", status=403)

        # Check if call is still active/joinable
        if call.state in ["ended", "declined", "cancelled"]:
            return HttpResponse("This call has ended", status=410)

        # Get Jitsi server URL
        jitsi_server = getattr(request.user.realm, "jitsi_server_url", None) or "https://meet.jit.si"
        base_room_url = f"{jitsi_server}/{call.jitsi_room_name}"

        # Determine if current user is the initiator (gets moderator privileges)
        is_initiator = call.sender.id == request.user.id
        
        # Generate appropriate URL parameters based on user role
        if is_initiator:
            # Moderator URL (for initiator) with special parameters
            url_params = (
                f"?userInfo.displayName={request.user.full_name}"
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
        else:
            # Participant URL (for recipient) without moderator privileges
            url_params = (
                f"?userInfo.displayName={request.user.full_name}"
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

        # Determine other participant
        other_user = call.receiver if call.sender.id == request.user.id else call.sender

        context = {
            "call_id": str(call.call_id),
            "call_url": f"{base_room_url}{url_params}#config.prejoinPageEnabled=false",
            "room_name": call.jitsi_room_name,
            "jitsi_server": jitsi_server,
            "is_video_call": call.call_type == "video",
            "call_type": call.call_type,
            "caller_name": call.sender.full_name,
            "recipient_name": call.receiver.full_name,
            "current_user_name": request.user.full_name,
            "is_initiator": is_initiator,
        }

        # Mark call as active if this is the first time someone joins
        if call.state == "initiated":
            call.state = "active"
            call.answered_at = timezone.now()
            call.save()

            # Create event
            CallEvent.objects.create(
                call=call,
                event_type="accepted",
                user=request.user
            )

        return render(request, "embedded_call.html", context)

    except Exception as e:
        logger.error(f"Failed to serve embedded call: {e}")
        return HttpResponse("Error loading call interface", status=500)


def get_embedded_calls_script(request):
    """Serve the embedded calls JavaScript and CSS"""
    return render(request, "embedded_calls_script.html", {
        'STATIC_URL': '/static/',
    })


@require_http_methods(["GET"])
def get_calls_override_script(request):
    """Serve the calls override JavaScript that integrates with Zulip"""
    from django.http import HttpResponse
    import os

    # Find the correct path to the JavaScript file
    # Try multiple possible locations
    possible_paths = [
        '/srv/zulip/zulip_calls_plugin/static/js/calls_override.js',
        os.path.join(os.path.dirname(__file__), '..', 'static', 'js', 'calls_override.js'),
        './zulip_calls_plugin/static/js/calls_override.js',
    ]

    js_content = None
    for js_path in possible_paths:
        try:
            with open(js_path, 'r') as f:
                js_content = f.read()
                break
        except FileNotFoundError:
            continue

    if js_content is None:
        # Fallback: return the JavaScript inline
        js_content = '''
/**
 * Zulip Calls Plugin - Aggressive Override
 * This script forcefully replaces Zulip's call button behavior
 */
(function() {
    'use strict';

    console.log('🔵 Zulip Calls Plugin: Starting aggressive override...');

    // Multiple override strategies
    function startOverride() {
        // Strategy 1: Override the compose_call_ui function
        overrideComposeCallUI();

        // Strategy 2: Override click handlers directly
        overrideClickHandlers();

        // Strategy 3: Intercept at DOM level
        interceptButtonClicks();

        console.log('🟢 Zulip Calls Plugin: All override strategies active');
    }

    // Strategy 1: Function override
    function overrideComposeCallUI() {
        function tryOverride() {
            if (window.compose_call_ui && window.compose_call_ui.generate_and_insert_audio_or_video_call_link) {
                const original = window.compose_call_ui.generate_and_insert_audio_or_video_call_link;

                window.compose_call_ui.generate_and_insert_audio_or_video_call_link = function($target, is_audio_call) {
                    console.log('🚀 INTERCEPTED Zulip call function! is_audio:', is_audio_call);
                    createEmbeddedCall($target, !is_audio_call);
                    return; // Don't call original
                };

                console.log('✅ Successfully overrode compose_call_ui function');
                return true;
            }
            return false;
        }

        if (!tryOverride()) {
            // Keep trying until Zulip loads
            setTimeout(tryOverride, 100);
        }
    }

    // Strategy 2: Direct click handler override
    function overrideClickHandlers() {
        // Remove ALL existing handlers and add ours
        $(document).off('click', '.video_link, .audio_link');

        // Add our handlers with high priority
        $(document).on('click.zulip-calls-plugin', '.video_link', function(e) {
            console.log('🎥 VIDEO BUTTON CLICKED - Our handler!');
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            createEmbeddedCall($(this), true);
            return false;
        });

        $(document).on('click.zulip-calls-plugin', '.audio_link', function(e) {
            console.log('🎤 AUDIO BUTTON CLICKED - Our handler!');
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            createEmbeddedCall($(this), false);
            return false;
        });

        console.log('✅ Click handlers overridden');
    }

    // Strategy 3: DOM-level interception
    function interceptButtonClicks() {
        // Use capture phase to intercept before other handlers
        document.addEventListener('click', function(e) {
            const target = e.target.closest('.video_link, .audio_link');
            if (target) {
                console.log('🎯 DOM LEVEL INTERCEPT:', target.className);
                e.preventDefault();
                e.stopPropagation();
                e.stopImmediatePropagation();

                const isVideo = target.classList.contains('video_link');
                createEmbeddedCall($(target), isVideo);
                return false;
            }
        }, true); // Use capture phase

        console.log('✅ DOM level interceptor active');
    }

    function createEmbeddedCall($button, isVideoCall) {
        console.log('🚀 Creating embedded call, isVideo:', isVideoCall);

        // Get recipient
        const recipientEmail = getRecipientEmail();
        console.log('📧 Recipient:', recipientEmail);

        if (!recipientEmail) {
            if (window.ui_report && window.ui_report.error) {
                ui_report.error('Please select a recipient for the call');
            } else {
                alert('Please select a recipient for the call');
            }
            return;
        }

        // Show loading
        $button.addClass('loading-call').prop('disabled', true);

        // Make API call
        $.ajax({
            url: '/api/v1/calls/create-embedded',
            method: 'POST',
            headers: {
                'X-CSRFToken': getCsrfToken()
            },
            data: {
                recipient_email: recipientEmail,
                is_video_call: isVideoCall,
                redirect_to_meeting: true
            },
            success: function(response) {
                console.log('📞 Call API response:', response);

                if (response.result === 'success' && response.redirect_url) {
                    // Open meeting immediately
                    console.log('🌐 Opening meeting:', response.redirect_url);
                    window.open(response.redirect_url, '_blank', 'width=1200,height=800,resizable=yes,menubar=no,toolbar=no');

                    // Insert link in compose
                    insertCallLink(response, isVideoCall);

                    // Show success
                    if (window.ui_report && window.ui_report.success) {
                        ui_report.success(`${isVideoCall ? 'Video' : 'Audio'} call started!`);
                    }
                } else {
                    throw new Error(response.message || 'Failed to create call');
                }
            },
            error: function(xhr) {
                console.error('❌ Call creation failed:', xhr);
                const msg = xhr.responseJSON?.message || 'Failed to create call';
                if (window.ui_report && window.ui_report.error) {
                    ui_report.error(msg);
                } else {
                    alert('Error: ' + msg);
                }
            },
            complete: function() {
                $button.removeClass('loading-call').prop('disabled', false);
            }
        });
    }

    function insertCallLink(response, isVideoCall) {
        const $textarea = $('textarea#compose-textarea');
        const callType = isVideoCall ? 'video' : 'audio';
        const link = `[Join ${callType} call](${response.redirect_url})`;
        const currentValue = $textarea.val();
        const newValue = currentValue + (currentValue ? '\n\n' : '') + link;

        $textarea.val(newValue).trigger('input').focus();
        console.log('📝 Inserted call link in compose');
    }

    function getRecipientEmail() {
        // Try multiple methods to get the actual email address
        let recipient = null;
        console.log('🔍 Starting recipient search...');

        // Method 1: Check if we're in a private message context using compose_state
        if (window.compose_state) {
            console.log('🔍 Compose state available');
            const messageType = window.compose_state.get_message_type();
            console.log('🔍 Message type:', messageType);

            if (messageType === "private") {
                // First try to get from the compose state (this returns emails)
                const recipients = window.compose_state.private_message_recipient_emails();
                console.log('🔍 Compose state recipients:', recipients);
                if (recipients) {
                    recipient = recipients.split(',')[0].trim();
                    console.log('📧 Found recipient via compose_state emails:', recipient);
                    return recipient;
                }
            }
        }

        // Method 2: If not composing but viewing a DM conversation, get recipient from narrow
        if (window.narrow_state && window.narrow_state.filter) {
            console.log('🔍 Narrow state available');
            const currentFilter = window.narrow_state.filter();
            console.log('🔍 Current filter:', currentFilter);

            if (currentFilter && currentFilter.is_conversation_view()) {
                console.log('🔍 Is conversation view');
                const termTypes = currentFilter.sorted_term_types();
                console.log('🔍 Term types:', termTypes);

                if (termTypes.includes("dm")) {
                    console.log('🔍 Has DM terms');
                    // Get the recipient IDs from the narrow
                    const recipientIds = currentFilter.operands("dm");
                    console.log('🔍 Recipient IDs from narrow:', recipientIds);

                    if (recipientIds && recipientIds.length > 0) {
                        // Get the first recipient's email using people.get_by_user_id
                        const firstRecipientId = recipientIds[0];
                        console.log('🔍 First recipient ID:', firstRecipientId);
                        if (window.people && window.people.get_by_user_id) {
                            const user = window.people.get_by_user_id(firstRecipientId);
                            console.log('🔍 User from people API:', user);

                            if (user && user.email) {
                                console.log('📧 Found recipient via narrow:', user.email);
                                return user.email;
                            }
                        }
                    }
                }
            }
        }

        // Method 3: Direct input fallback (might contain display names, needs conversion)
        const $dmInput = $('#private_message_recipient');
        if ($dmInput.length && $dmInput.val()) {
            const inputValue = $dmInput.val().trim().split(',')[0].trim();

            // Try to convert display name to email if people API is available
            if (window.people && window.people.get_by_name) {
                const user = window.people.get_by_name(inputValue);
                if (user && user.email) {
                    console.log('📧 Found recipient via input name lookup:', user.email);
                    return user.email;
                }
            }

            // If it already looks like an email, use it directly
            if (inputValue.includes('@')) {
                console.log('📧 Found recipient via direct input (email):', inputValue);
                return inputValue;
            }

            console.log('⚠️ Found input but could not convert to email:', inputValue);
        }

        console.log('❌ No recipient found');
        return null;
    }

    function getCsrfToken() {
        return $('input[name="csrfmiddlewaretoken"]').val() ||
               $('[name="csrfmiddlewaretoken"]').val() ||
               document.querySelector('[name="csrfmiddlewaretoken"]')?.value;
    }

    // Add CSS for loading state
    const style = document.createElement('style');
    style.textContent = `
        .loading-call {
            opacity: 0.5 !important;
            cursor: wait !important;
        }
        .loading-call::after {
            content: " (Creating call...)";
            font-size: 10px;
        }
    `;
    document.head.appendChild(style);

    // Start override when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startOverride);
    } else {
        startOverride();
    }

    // Also start after a delay to catch late-loading Zulip components
    setTimeout(startOverride, 1000);
    setTimeout(startOverride, 3000);

    // Export for debugging
    window.zulipCallsPlugin = {
        createEmbeddedCall,
        getRecipientEmail,
        startOverride,
        version: 'v2-aggressive'
    };

    console.log('🎉 Zulip Calls Plugin v2 loaded!');
})();
'''

    return HttpResponse(js_content, content_type='application/javascript')


# New Enhanced API Endpoints for comprehensive Jitsi calling

@csrf_exempt
@authenticated_rest_api_view(webhook_client_name="Zulip")
def start_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Start a new video or audio call with enhanced features
    """
    try:
        # Extract and validate parameters
        raw_user_id = request.POST.get("user_id") or request.GET.get("user_id")
        call_type = (request.POST.get("call_type") or request.GET.get("call_type") or "").strip()

        if raw_user_id is None:
            raise JsonableError("Missing required parameter: user_id")
        try:
            user_id = int(raw_user_id)
        except (TypeError, ValueError):
            raise JsonableError("Invalid user_id; must be an integer")

        if call_type not in ['video', 'audio']:
            raise JsonableError("Invalid call type. Must be 'video' or 'audio")

        # Get receiver user
        try:
            receiver = UserProfile.objects.get(id=user_id)
        except UserProfile.DoesNotExist:
            raise JsonableError("User not found")

        # Check if users are in the same realm
        if user_profile.realm_id != receiver.realm_id:
            raise JsonableError("Cannot call users from different organizations")

        # Check if receiver is the same as sender
        if user_profile.id == receiver.id:
            raise JsonableError("Cannot call yourself")

        # Clean up any stale calls for both users before checking
        check_and_cleanup_user_calls(user_profile)
        check_and_cleanup_user_calls(receiver)

        # Check if receiver has an active call (after cleanup)
        active_calls = Call.objects.filter(
            receiver=receiver,
            state__in=['calling', 'ringing', 'accepted']
        ).exists()

        if active_calls:
            raise JsonableError("User is currently in another call")

        # Check if sender has an active call (after cleanup)
        sender_active_calls = Call.objects.filter(
            sender=user_profile,
            state__in=['calling', 'ringing', 'accepted']
        ).exists()

        if sender_active_calls:
            raise JsonableError("You are currently in another call")

        # Generate unique call ID and Jitsi URL
        call_id = str(uuid.uuid4())
        jitsi_url, room_id = generate_jitsi_url(call_id)

        # Create call record
        with transaction.atomic():
            call = Call.objects.create(
                call_id=call_id,
                sender=user_profile,
                receiver=receiver,
                realm=user_profile.realm,
                call_type=call_type,
                jitsi_room_url=jitsi_url,
                jitsi_room_id=room_id,
                jitsi_room_name=room_id,
                state='calling'
            )

        # Send push notification to receiver
        notification_data = {
            'call_id': str(call.call_id),
            'sender_id': user_profile.id,
            'sender_name': user_profile.full_name,
            'call_type': call_type,
            'jitsi_url': jitsi_url,
        }
        send_call_push_notification(receiver, notification_data)

        # Send real-time event to receiver
        send_call_event(receiver, call, 'call_started')

        logger.info(f"Call started: {call_id} from {user_profile.id} to {receiver.id}")

        return JsonResponse({
            'result': 'success',
            'call_id': str(call_id),
            'jitsi_url': jitsi_url,
            'timeout_seconds': getattr(__import__('django.conf', fromlist=['settings']).settings, 'CALL_NOTIFICATION_TIMEOUT', 120)
        })

    except Exception as e:
        logger.error(f"Error starting call: {str(e)}")
        raise


@csrf_exempt
@authenticated_rest_api_view(webhook_client_name="Zulip")
def respond_to_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Respond to an incoming call (accept/reject)
    """
    try:
        # Extract parameters
        call_id = (request.POST.get("call_id") or request.GET.get("call_id") or "").strip()
        response = (request.POST.get("response") or request.GET.get("response") or "").strip()

        if not call_id:
            raise JsonableError("Missing required parameter: call_id")
        if response not in ['accept', 'reject']:
            raise JsonableError("Invalid response. Must be 'accept' or 'reject'")

        # Get call
        try:
            call = Call.objects.get(call_id=call_id, receiver=user_profile)
        except Call.DoesNotExist:
            raise JsonableError("Call not found or you're not the receiver")

        # Check if call can be answered
        if not call.can_be_answered():
            raise JsonableError(f"Call cannot be answered. Current status: {call.state}")

        # Update call state
        with transaction.atomic():
            call.state = 'accepted' if response == 'accept' else 'rejected'
            call.answered_at = timezone.now()
            call.save()

        # Send notification to sender
        send_call_response_notification(call.sender, call, response)

        # Send real-time events
        send_call_event(call.sender, call, f'call_{response}d')
        if response == 'accept':
            send_call_event(call.receiver, call, 'call_accepted')

        logger.info(f"Call {call_id} {response}ed by {user_profile.id}")

        response_data = {'status': 'ok', 'call_status': call.state}
        if response == 'accept':
            response_data['jitsi_url'] = call.jitsi_room_url

        return JsonResponse({'result': 'success', **response_data})

    except Exception as e:
        logger.error(f"Error responding to call: {str(e)}")
        raise


@csrf_exempt
@authenticated_rest_api_view(webhook_client_name="Zulip")
def end_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    End an active call
    """
    try:
        call_id = (request.POST.get("call_id") or request.GET.get("call_id") or "").strip()
        if not call_id:
            raise JsonableError("Missing required parameter: call_id")

        # Get call where user is either sender or receiver
        try:
            call = Call.objects.get(
                models.Q(call_id=call_id) &
                (models.Q(sender=user_profile) | models.Q(receiver=user_profile))
            )
        except Call.DoesNotExist:
            raise JsonableError("Call not found")

        # Only end if call is active
        if not call.is_active():
            raise JsonableError(f"Call is not active. Current status: {call.state}")

        # Update call state
        with transaction.atomic():
            call.state = 'ended'
            call.ended_at = timezone.now()
            call.save()

        # Notify other participant
        other_user = call.receiver if call.sender == user_profile else call.sender
        send_call_event(other_user, call, 'call_ended')

        logger.info(f"Call {call_id} ended by {user_profile.id}")

        return JsonResponse({'result': 'success', 'status': 'ok'})

    except Exception as e:
        logger.error(f"Error ending call: {str(e)}")
        raise


@csrf_exempt
@authenticated_json_view
def get_call_history(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Get call history for the user
    """
    try:
        raw_limit = request.GET.get("limit")
        try:
            limit = int(raw_limit) if raw_limit is not None else 50
        except (TypeError, ValueError):
            raise JsonableError("Invalid limit; must be an integer")

        calls = Call.objects.filter(
            models.Q(sender=user_profile) | models.Q(receiver=user_profile),
            realm=user_profile.realm
        ).order_by('-created_at')[:limit]

        call_data = []
        for call in calls:
            other_user = call.receiver if call.sender == user_profile else call.sender
            call_data.append({
                'call_id': str(call.call_id),
                'user_id': other_user.id,
                'user_name': other_user.full_name,
                'call_type': call.call_type,
                'state': call.state,
                'is_outgoing': call.sender == user_profile,
                'created_at': call.created_at.isoformat(),
                'answered_at': call.answered_at.isoformat() if call.answered_at else None,
                'ended_at': call.ended_at.isoformat() if call.ended_at else None,
                'duration': call.duration.total_seconds() if call.duration else None,
            })

        return json_success(request, {'calls': call_data})

    except Exception as e:
        logger.error(f"Error getting call history: {str(e)}")
        raise


@csrf_exempt
@authenticated_rest_api_view(webhook_client_name="Zulip")
def end_call(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    End a specific call by call_id
    """
    try:
        call_id = request.POST.get("call_id") or request.GET.get("call_id")
        if not call_id:
            raise JsonableError("Missing required parameter: call_id")

        try:
            call = Call.objects.get(call_id=call_id)
        except Call.DoesNotExist:
            raise JsonableError("Call not found")

        # Check if user is a participant in this call
        if call.sender != user_profile and call.receiver != user_profile:
            raise JsonableError("You are not a participant in this call")

        # Check if call is already ended
        if call.state in ['ended', 'rejected', 'timeout', 'cancelled']:
            raise JsonableError("Call is already ended")

        # End the call
        call.state = 'ended'
        call.ended_at = timezone.now()
        call.save()

        # Create end event
        CallEvent.objects.create(
            call=call,
            event_type='ended',
            user=user_profile,
            metadata={'reason': 'manual_end'}
        )

        # Send notification to the other participant
        other_user = call.receiver if call.sender == user_profile else call.sender
        send_call_response_notification(other_user, call, 'ended')

        logger.info(f"Call {call_id} ended by user {user_profile.id}")

        return JsonResponse({
            'result': 'success',
            'message': 'Call ended successfully',
            'call_id': str(call_id)
        })

    except Exception as e:
        logger.error(f"Error ending call: {str(e)}")
        raise


@csrf_exempt
@authenticated_rest_api_view(webhook_client_name="Zulip")
def end_all_user_calls(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    End all active calls for the current user
    """
    try:
        count = end_user_active_calls(user_profile, 'manual_end_all')
        
        return JsonResponse({
            'result': 'success',
            'message': f'Ended {count} active calls',
            'calls_ended': count
        })

    except Exception as e:
        logger.error(f"Error ending all user calls: {str(e)}")
        raise


@csrf_exempt
@authenticated_rest_api_view(webhook_client_name="Zulip")
def cleanup_stale_calls_endpoint(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Manually trigger cleanup of stale calls (admin function)
    """
    try:
        # Check if user has admin privileges (optional security check)
        if not user_profile.is_realm_admin:
            raise JsonableError("Admin privileges required")

        count = cleanup_stale_calls()
        
        return JsonResponse({
            'result': 'success',
            'message': f'Cleaned up {count} stale calls',
            'calls_cleaned': count
        })

    except Exception as e:
        logger.error(f"Error cleaning up stale calls: {str(e)}")
        raise


@csrf_exempt
@authenticated_rest_api_view(webhook_client_name="Zulip")
def get_user_active_calls(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    """
    Get all active calls for the current user
    """
    try:
        # Clean up stale calls first
        check_and_cleanup_user_calls(user_profile)
        
        # Get active calls
        active_calls = Call.objects.filter(
            models.Q(sender=user_profile) | models.Q(receiver=user_profile),
            state__in=['calling', 'ringing', 'accepted']
        ).order_by('-created_at')

        call_data = []
        for call in active_calls:
            call_data.append({
                'call_id': str(call.call_id),
                'call_type': call.call_type,
                'state': call.state,
                'sender_id': call.sender.id,
                'sender_name': call.sender.full_name,
                'receiver_id': call.receiver.id,
                'receiver_name': call.receiver.full_name,
                'jitsi_url': call.jitsi_room_url,
                'created_at': call.created_at.isoformat(),
                'is_outgoing': call.sender == user_profile,
            })

        return JsonResponse({
            'result': 'success',
            'active_calls': call_data,
            'count': len(call_data)
        })

    except Exception as e:
        logger.error(f"Error getting active calls: {str(e)}")
        raise