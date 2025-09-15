import uuid
import logging
from django.http import JsonResponse, HttpResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from django.db import models
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

# Import Zulip components
from zerver.decorator import authenticated_rest_api_view, zulip_login_required
from zerver.models import UserProfile
from zerver.models.users import get_user_by_delivery_email
from zerver.lib.push_notifications import send_android_push_notification

# Import plugin models
from ..models import Call, CallEvent

logger = logging.getLogger(__name__)


def send_call_push_notification(recipient: UserProfile, call_data: dict) -> None:
    """Send FCM push notification for call events"""
    try:
        send_android_push_notification(
            user=recipient,
            data=call_data,
            priority="high"
        )
    except Exception as e:
        logger.error(f"Failed to send call push notification: {e}")


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
            f"&interfaceConfig.SHOW_JITSI_WATERMARK=false"
            f"&interfaceConfig.SHOW_WATERMARK_FOR_GUESTS=false"
        )

        call_url = f"{jitsi_server}/zulip-call-{room_id}{moderator_params}"

        # Find recipient user
        try:
            recipient = get_user_by_delivery_email(recipient_email, user_profile.realm)
        except UserProfile.DoesNotExist:
            return JsonResponse({
                "result": "error",
                "message": "Recipient not found"
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

            # Find recipient
            try:
                recipient = get_user_by_delivery_email(recipient_email, user_profile.realm)
            except UserProfile.DoesNotExist:
                return JsonResponse({
                    "result": "error",
                    "message": "Recipient not found"
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
                f"&interfaceConfig.SHOW_JITSI_WATERMARK=false"
                f"&interfaceConfig.SHOW_WATERMARK_FOR_GUESTS=false"
                f"&config.enableInsecureRoomNameWarning=false"
            )

            # Participant URL (for recipient) without moderator privileges
            participant_params = (
                f"?userInfo.displayName={recipient.full_name}"
                f"&config.startWithAudioMuted=true"
                f"&config.startWithVideoMuted=true"
                f"&config.enableWelcomePage=false"
                f"&config.enableClosePage=false"
                f"&config.prejoinPageEnabled=false"
                f"&interfaceConfig.SHOW_JITSI_WATERMARK=false"
            )

            # Store the base URL and create specific URLs for each participant
            call.jitsi_room_url = base_room_url  # Base URL without parameters
            moderator_url = f"{base_room_url}{moderator_params}"
            participant_url = f"{base_room_url}{participant_params}"

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

            # Try the email as provided
            try:
                recipient = get_user_by_delivery_email(recipient_email, request.user.realm)
            except UserProfile.DoesNotExist:
                tried_emails.append(recipient_email)

                # If it has @zulipdev.com, try @zulip.com instead
                if "@zulipdev.com" in recipient_email:
                    alternative_email = recipient_email.replace("@zulipdev.com", "@zulip.com")
                    try:
                        recipient = get_user_by_delivery_email(alternative_email, request.user.realm)
                        logger.info(f"Found user with alternative email: '{alternative_email}' instead of '{recipient_email}'")
                    except UserProfile.DoesNotExist:
                        tried_emails.append(alternative_email)

                # If it has @zulip.com, try @zulipdev.com instead
                elif "@zulip.com" in recipient_email:
                    alternative_email = recipient_email.replace("@zulip.com", "@zulipdev.com")
                    try:
                        recipient = get_user_by_delivery_email(alternative_email, request.user.realm)
                        logger.info(f"Found user with alternative email: '{alternative_email}' instead of '{recipient_email}'")
                    except UserProfile.DoesNotExist:
                        tried_emails.append(alternative_email)

            if not recipient:
                # Debug: List some users in the realm to see what emails exist
                from zerver.models import UserProfile as ZulipUserProfile
                realm_users = ZulipUserProfile.objects.filter(realm=request.user.realm)[:10]
                user_emails = [f"'{u.delivery_email}'" for u in realm_users]
                logger.error(f"User not found after trying: {tried_emails}, realm='{request.user.realm.string_id}'")
                logger.error(f"Available users in realm: {', '.join(user_emails)}")
                return JsonResponse({
                    "result": "error",
                    "message": f"Recipient not found. Tried: {', '.join(tried_emails)}. Available: {', '.join(user_emails[:5])}"
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
                initiator=request.user,
                recipient=recipient,
                jitsi_room_name=f"zulip-call-{uuid.uuid4().hex[:12]}",
                realm=request.user.realm
            )

            # Generate Jitsi URLs - separate URLs for moderator and participant
            jitsi_server = getattr(request.user.realm, "jitsi_server_url", None) or "https://meet.jit.si"
            base_room_url = f"{jitsi_server}/{call.jitsi_room_name}"

            # Moderator URL (for initiator) with special parameters
            moderator_params = (
                f"?userInfo.displayName={request.user.full_name}"
                f"&config.startWithAudioMuted=false"
                f"&config.startWithVideoMuted=false"
                f"&config.enableWelcomePage=false"
                f"&config.enableClosePage=false"
                f"&config.prejoinPageEnabled=false"
                f"&interfaceConfig.SHOW_JITSI_WATERMARK=false"
                f"&interfaceConfig.SHOW_WATERMARK_FOR_GUESTS=false"
                f"&config.enableInsecureRoomNameWarning=false"
            )

            # Participant URL (for recipient) without moderator privileges
            participant_params = (
                f"?userInfo.displayName={recipient.full_name}"
                f"&config.startWithAudioMuted=true"
                f"&config.startWithVideoMuted=true"
                f"&config.enableWelcomePage=false"
                f"&config.enableClosePage=false"
                f"&config.prejoinPageEnabled=false"
                f"&interfaceConfig.SHOW_JITSI_WATERMARK=false"
            )

            # Store the base URL and create specific URLs for each participant
            call.jitsi_room_url = base_room_url  # Base URL without parameters
            moderator_url = f"{base_room_url}{moderator_params}"
            participant_url = f"{base_room_url}{participant_params}"

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
        if (call.initiator.id != request.user.id and
            call.recipient.id != request.user.id):
            return HttpResponse("Not authorized to join this call", status=403)

        # Check if call is still active/joinable
        if call.state in ["ended", "declined", "cancelled"]:
            return HttpResponse("This call has ended", status=410)

        # Get Jitsi server URL
        jitsi_server = getattr(request.user.realm, "jitsi_server_url", None) or "https://meet.jit.si"

        # Determine other participant
        other_user = call.recipient if call.initiator.id == request.user.id else call.initiator

        context = {
            "call_id": str(call.call_id),
            "call_url": call.jitsi_room_url,
            "room_name": call.jitsi_room_name,
            "jitsi_server": jitsi_server,
            "is_video_call": call.call_type == "video",
            "call_type": call.call_type,
            "caller_name": call.initiator.full_name,
            "recipient_name": call.recipient.full_name,
            "current_user_name": request.user.full_name,
        }

        # Mark call as active if this is the first time someone joins
        if call.state == "initiated":
            call.state = "active"
            call.started_at = timezone.now()
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