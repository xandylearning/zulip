import uuid
import logging
from django.http import JsonResponse, HttpResponse
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
            user_profile=recipient,
            data=call_data,
            priority="high"
        )
    except Exception as e:
        logger.error(f"Failed to send call push notification: {e}")


@require_http_methods(["POST"])
@authenticated_rest_api_view(webhook_client_name="Zulip")
def initiate_quick_call(request, user_profile: UserProfile) -> JsonResponse:
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
        call_url = f"{jitsi_server}/zulip-call-{room_id}"

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
def create_call(request, user_profile: UserProfile) -> JsonResponse:
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

            # Generate Jitsi URL
            jitsi_server = getattr(user_profile.realm, "jitsi_server_url", None) or "https://meet.jit.si"
            call.jitsi_room_url = f"{jitsi_server}/{call.jitsi_room_name}"
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

            # Send push notification
            push_data = {
                "type": "call_invitation",
                "call_id": str(call.call_id),
                "call_url": call.jitsi_room_url,
                "call_type": call.call_type,
                "caller_name": user_profile.full_name,
                "caller_id": user_profile.id,
                "room_name": call.jitsi_room_name,
            }

            send_call_push_notification(recipient, push_data)

            return JsonResponse({
                "result": "success",
                "call_id": str(call.call_id),
                "call_url": call.jitsi_room_url,
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
def respond_to_call(request, user_profile: UserProfile, call_id: str) -> JsonResponse:
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
def end_call(request, user_profile: UserProfile, call_id: str) -> JsonResponse:
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
def get_call_status(request, user_profile: UserProfile, call_id: str) -> JsonResponse:
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
def get_call_history(request, user_profile: UserProfile) -> JsonResponse:
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
@authenticated_rest_api_view(webhook_client_name="Zulip")
def create_embedded_call(request, user_profile: UserProfile) -> JsonResponse:
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

            # Create call record
            call = Call.objects.create(
                call_type="video" if is_video_call else "audio",
                initiator=user_profile,
                recipient=recipient,
                jitsi_room_name=f"zulip-call-{uuid.uuid4().hex[:12]}",
                realm=user_profile.realm
            )

            # Generate Jitsi URL
            jitsi_server = getattr(user_profile.realm, "jitsi_server_url", None) or "https://meet.jit.si"
            call.jitsi_room_url = f"{jitsi_server}/{call.jitsi_room_name}"
            call.save()

            # Create initial call event
            CallEvent.objects.create(
                call=call,
                event_type="initiated",
                user=user_profile,
                metadata={
                    "recipient_email": recipient_email,
                    "is_video_call": is_video_call,
                    "embedded": True
                }
            )

            # Send push notification to recipient
            push_data = {
                "type": "call_invitation_embedded",
                "call_id": str(call.call_id),
                "call_url": call.jitsi_room_url,
                "call_type": call.call_type,
                "caller_name": user_profile.full_name,
                "caller_id": user_profile.id,
                "room_name": call.jitsi_room_name,
                "embedded_url": f"/calls/embed/{call.call_id}",
            }

            send_call_push_notification(recipient, push_data)

            # Return response with both redirect and embed URLs
            response_data = {
                "result": "success",
                "call_id": str(call.call_id),
                "call_url": call.jitsi_room_url,  # Direct Jitsi URL
                "embedded_url": f"/calls/embed/{call.call_id}",  # Embedded interface URL
                "call_type": call.call_type,
                "room_name": call.jitsi_room_name,
                "recipient": {
                    "user_id": recipient.id,
                    "full_name": recipient.full_name,
                    "email": recipient.delivery_email,
                }
            }

            # If redirect_to_meeting is requested, return the Jitsi URL for immediate redirect
            if redirect_to_meeting:
                response_data["action"] = "redirect"
                response_data["redirect_url"] = call.jitsi_room_url

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
 * Zulip Calls Plugin - Direct Integration
 */
(function() {
    'use strict';

    console.log('Zulip Calls Plugin: Starting integration...');

    // Wait for Zulip to be ready
    function waitForZulip() {
        if (typeof window.compose_call_ui === 'undefined' || typeof $ === 'undefined') {
            setTimeout(waitForZulip, 100);
            return;
        }
        overrideZulipCallFunctionality();
    }

    function overrideZulipCallFunctionality() {
        const originalFunction = window.compose_call_ui.generate_and_insert_audio_or_video_call_link;

        if (originalFunction) {
            window.compose_call_ui.generate_and_insert_audio_or_video_call_link = function($target_element, is_audio_call) {
                console.log('Zulip Calls Plugin: Intercepted call creation, is_audio_call:', is_audio_call);
                createEmbeddedCall($target_element, !is_audio_call);
            };
            console.log('Zulip Calls Plugin: Successfully overrode call functionality');
        }
    }

    function createEmbeddedCall($button, isVideoCall) {
        const recipientEmail = getRecipientEmail();

        if (!recipientEmail) {
            alert('Please select a recipient for the call');
            return;
        }

        $button.prop('disabled', true);

        $.ajax({
            url: '/api/v1/calls/create-embedded',
            method: 'POST',
            headers: {
                'X-CSRFToken': $('input[name="csrfmiddlewaretoken"]').val() || $('[name="csrfmiddlewaretoken"]').val()
            },
            data: {
                recipient_email: recipientEmail,
                is_video_call: isVideoCall,
                redirect_to_meeting: true
            },
            success: function(response) {
                if (response.result === 'success' && response.redirect_url) {
                    window.open(response.redirect_url, '_blank', 'width=1200,height=800,resizable=yes');

                    const $textarea = $('textarea#compose-textarea');
                    const callType = isVideoCall ? 'video' : 'audio';
                    const link = `[Join ${callType} call](${response.redirect_url})`;
                    const currentValue = $textarea.val();
                    $textarea.val(currentValue + (currentValue ? '\\n\\n' : '') + link).trigger('input');

                    if (window.ui_report && window.ui_report.success) {
                        ui_report.success(`${callType} call started successfully`);
                    }
                }
            },
            error: function() {
                alert('Failed to create call');
            },
            complete: function() {
                $button.prop('disabled', false);
            }
        });
    }

    function getRecipientEmail() {
        const dmInput = $('#private_message_recipient');
        if (dmInput.length && dmInput.val()) {
            return dmInput.val().trim().split(',')[0].trim();
        }

        if (window.compose_state && window.compose_state.private_message_recipient) {
            const recipients = compose_state.private_message_recipient();
            if (recipients) {
                return recipients.split(',')[0].trim();
            }
        }

        return null;
    }

    waitForZulip();

    window.zulipCallsPlugin = { createEmbeddedCall, getRecipientEmail };
})();
'''

    return HttpResponse(js_content, content_type='application/javascript')