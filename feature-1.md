# 🚀 Backend Implementation Guide for Zulip Flutter Call Integration

## 📋 Overview

This document provides complete backend implementation instructions for integrating video/voice calling functionality with the Zulip Flutter app. The Flutter client is already implemented and ready to work with these endpoints.

## 🎯 Current Status

### ✅ Flutter App (Complete)
- Jitsi Meet package integrated
- Call buttons in DM interface
- Push notification handling
- Permissions management
- Error handling

### 🔨 Backend Required
- Call invitation API endpoints
- Push notification service
- Call state management
- User availability checking

## 🛠️ Implementation Options

Choose based on your requirements:

### Option A: Quick Start (30 minutes)
- Single endpoint for immediate calls
- Basic push notifications
- No call state tracking
- Perfect for MVP/testing

### Option B: Standard Implementation (2-4 hours)
- Full call management API
- Call state tracking
- Accept/decline functionality
- Call history

### Option C: Advanced Implementation (1-2 days)
- Complete call management system
- Database models for call tracking
- Advanced features (busy status, call queuing)
- Analytics and monitoring

---

## 🚀 Option A: Quick Start Implementation

### 1. Create Basic Call Endpoint

**File:** `zerver/views/calls.py`

```python
import uuid
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from zerver.decorator import api_key_only_webhook_view
from zerver.models import UserProfile, get_user_by_delivery_email
from zerver.lib.push_notifications import send_android_push_notification

@require_http_methods(["POST"])
@api_key_only_webhook_view('Zulip')
def initiate_quick_call(request, user_profile):
    """
    Quick call implementation - generates Jitsi room and sends notification
    """
    try:
        # Get request parameters
        recipient_email = request.POST.get('recipient_email')
        is_video_call = request.POST.get('is_video_call', 'true').lower() == 'true'

        if not recipient_email:
            return JsonResponse({
                "result": "error",
                "message": "recipient_email is required"
            }, status=400)

        # Generate unique room ID
        room_id = str(uuid.uuid4())[:12]  # Short ID for easier joining

        # Get Jitsi server URL (use realm setting or fallback)
        jitsi_server = getattr(user_profile.realm, 'jitsi_server_url', None) or "https://meet.jit.si"
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
        return JsonResponse({
            "result": "error",
            "message": f"Failed to initiate call: {str(e)}"
        }, status=500)

def send_call_push_notification(recipient, call_data):
    """
    Send FCM push notification for incoming call
    """
    try:
        # Use Zulip's existing push notification system
        send_android_push_notification(
            user_profile=recipient,
            data=call_data,
            priority="high"
        )
    except Exception as e:
        # Log error but don't fail the call creation
        print(f"Failed to send push notification: {e}")
```

### 2. Add URL Configuration

**File:** `zerver/urls.py`

```python
# Add this import at the top
from zerver.views import calls

# Add this to your urlpatterns list
urlpatterns = [
    # ... existing patterns ...
    path('api/v1/calls/initiate', calls.initiate_quick_call),
]
```

### 3. Configure Jitsi Server (Optional)

**In your Django admin or management command:**

```python
from zerver.models import Realm

# Set Jitsi server for your organization
realm = Realm.objects.get(string_id="your-organization-name")
realm.jitsi_server_url = "https://meet.jit.si"  # or your custom Jitsi server
realm.save()
```

### 4. Test the Implementation

```bash
# Test call initiation
curl -X POST "https://your-zulip-server.com/api/v1/calls/initiate" \
  -u "your-email@domain.com:your-api-key" \
  -d "recipient_email=recipient@domain.com" \
  -d "is_video_call=true"
```

**Expected Response:**
```json
{
  "result": "success",
  "call_url": "https://meet.jit.si/zulip-call-abc123def456",
  "room_id": "abc123def456",
  "message": "Call initiated successfully"
}
```

---

## 🔧 Option B: Standard Implementation

### 1. Enhanced Call Management

**File:** `zerver/views/calls.py`

```python
import uuid
import time
import json
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from zerver.decorator import api_key_only_webhook_view
from zerver.models import UserProfile, get_user_by_delivery_email
from zerver.lib.push_notifications import send_android_push_notification

# In-memory call storage (use Redis or database for production)
active_calls = {}

@require_http_methods(["POST"])
@api_key_only_webhook_view('Zulip')
def create_call(request, user_profile):
    """
    Create a new call with state tracking
    """
    try:
        # Get request parameters
        recipient_email = request.POST.get('recipient_email')
        is_video_call = request.POST.get('is_video_call', 'true').lower() == 'true'

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

        # Generate call details
        call_id = str(uuid.uuid4())
        room_name = f"zulip-call-{call_id[:12]}"
        jitsi_server = getattr(user_profile.realm, 'jitsi_server_url', None) or "https://meet.jit.si"
        call_url = f"{jitsi_server}/{room_name}"

        # Store call state
        call_data = {
            "call_id": call_id,
            "room_name": room_name,
            "call_url": call_url,
            "is_video_call": is_video_call,
            "state": "initiated",
            "initiator": {
                "user_id": user_profile.id,
                "full_name": user_profile.full_name,
                "email": user_profile.delivery_email,
            },
            "recipient": {
                "user_id": recipient.id,
                "full_name": recipient.full_name,
                "email": recipient.delivery_email,
            },
            "created_at": int(time.time()),
            "expires_at": int(time.time()) + 60,  # 60 seconds to answer
        }

        active_calls[call_id] = call_data

        # Send push notification
        push_data = {
            "type": "call_invitation",
            "call_id": call_id,
            "call_url": call_url,
            "is_video_call": is_video_call,
            "caller_name": user_profile.full_name,
            "caller_id": user_profile.id,
            "room_name": room_name,
        }

        send_call_push_notification(recipient, push_data)

        return JsonResponse({
            "result": "success",
            "call_id": call_id,
            "call_url": call_url,
            "room_name": room_name,
            "expires_in": 60
        })

    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": f"Failed to create call: {str(e)}"
        }, status=500)

@require_http_methods(["POST"])
@api_key_only_webhook_view('Zulip')
def respond_to_call(request, user_profile, call_id):
    """
    Accept or decline a call invitation
    """
    try:
        if call_id not in active_calls:
            return JsonResponse({
                "result": "error",
                "message": "Call not found or expired"
            }, status=404)

        call_data = active_calls[call_id]
        response = request.POST.get('response')  # 'accept' or 'decline'

        if response not in ['accept', 'decline']:
            return JsonResponse({
                "result": "error",
                "message": "Response must be 'accept' or 'decline'"
            }, status=400)

        # Check if user is the recipient
        if call_data["recipient"]["user_id"] != user_profile.id:
            return JsonResponse({
                "result": "error",
                "message": "Not authorized to respond to this call"
            }, status=403)

        # Update call state
        call_data["state"] = "accepted" if response == "accept" else "declined"
        call_data["responded_at"] = int(time.time())

        if response == "accept":
            # Notify caller that call was accepted
            try:
                caller = UserProfile.objects.get(id=call_data["initiator"]["user_id"])
                notification_data = {
                    "type": "call_accepted",
                    "call_id": call_id,
                    "call_url": call_data["call_url"],
                    "accepter_name": user_profile.full_name,
                }
                send_call_push_notification(caller, notification_data)
            except UserProfile.DoesNotExist:
                pass

            return JsonResponse({
                "result": "success",
                "action": "accepted",
                "call_url": call_data["call_url"],
                "message": "Call accepted"
            })
        else:
            # Clean up declined call
            del active_calls[call_id]

            return JsonResponse({
                "result": "success",
                "action": "declined",
                "message": "Call declined"
            })

    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": f"Failed to respond to call: {str(e)}"
        }, status=500)

@require_http_methods(["POST"])
@api_key_only_webhook_view('Zulip')
def end_call(request, user_profile, call_id):
    """
    End an ongoing call
    """
    try:
        if call_id not in active_calls:
            return JsonResponse({
                "result": "error",
                "message": "Call not found"
            }, status=404)

        call_data = active_calls[call_id]

        # Check authorization
        if (call_data["initiator"]["user_id"] != user_profile.id and
            call_data["recipient"]["user_id"] != user_profile.id):
            return JsonResponse({
                "result": "error",
                "message": "Not authorized to end this call"
            }, status=403)

        # Mark call as ended
        call_data["state"] = "ended"
        call_data["ended_at"] = int(time.time())

        # Clean up after 5 minutes
        # In production, use a proper cleanup mechanism

        return JsonResponse({
            "result": "success",
            "message": "Call ended successfully"
        })

    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": f"Failed to end call: {str(e)}"
        }, status=500)

@require_http_methods(["GET"])
@api_key_only_webhook_view('Zulip')
def get_call_status(request, user_profile, call_id):
    """
    Get current status of a call
    """
    try:
        if call_id not in active_calls:
            return JsonResponse({
                "result": "error",
                "message": "Call not found"
            }, status=404)

        call_data = active_calls[call_id]

        # Check authorization
        if (call_data["initiator"]["user_id"] != user_profile.id and
            call_data["recipient"]["user_id"] != user_profile.id):
            return JsonResponse({
                "result": "error",
                "message": "Not authorized to view this call"
            }, status=403)

        return JsonResponse({
            "result": "success",
            "call": {
                "call_id": call_data["call_id"],
                "state": call_data["state"],
                "call_url": call_data["call_url"],
                "is_video_call": call_data["is_video_call"],
                "created_at": call_data["created_at"],
                "initiator": call_data["initiator"],
                "recipient": call_data["recipient"],
            }
        })

    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get call status: {str(e)}"
        }, status=500)

def send_call_push_notification(recipient, call_data):
    """
    Send FCM push notification for call events
    """
    try:
        send_android_push_notification(
            user_profile=recipient,
            data=call_data,
            priority="high"
        )
    except Exception as e:
        print(f"Failed to send push notification: {e}")
```

### 2. Update URL Configuration

**File:** `zerver/urls.py`

```python
# Add these URL patterns
urlpatterns = [
    # ... existing patterns ...
    path('api/v1/calls/create', calls.create_call),
    path('api/v1/calls/<str:call_id>/respond', calls.respond_to_call),
    path('api/v1/calls/<str:call_id>/end', calls.end_call),
    path('api/v1/calls/<str:call_id>/status', calls.get_call_status),
]
```

---

## 🔧 Option C: Advanced Implementation with Database

### 1. Database Models

**File:** `zerver/models.py` (add to existing models)

```python
import uuid
from django.db import models
from django.utils import timezone

class Call(models.Model):
    """Model for managing video/voice calls"""

    CALL_TYPES = [
        ('video', 'Video Call'),
        ('audio', 'Audio Call'),
    ]

    CALL_STATES = [
        ('initiated', 'Initiated'),
        ('ringing', 'Ringing'),
        ('active', 'Active'),
        ('ended', 'Ended'),
        ('declined', 'Declined'),
        ('missed', 'Missed'),
        ('cancelled', 'Cancelled'),
    ]

    call_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    call_type = models.CharField(max_length=10, choices=CALL_TYPES)
    state = models.CharField(max_length=20, choices=CALL_STATES, default='initiated')

    # Participants
    initiator = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='initiated_calls')
    recipient = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='received_calls')

    # Call details
    jitsi_room_name = models.CharField(max_length=255)
    jitsi_room_url = models.URLField()

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['state', 'created_at']),
            models.Index(fields=['initiator', 'created_at']),
            models.Index(fields=['recipient', 'created_at']),
        ]

class CallEvent(models.Model):
    """Model for tracking call events and history"""

    EVENT_TYPES = [
        ('initiated', 'Call Initiated'),
        ('ringing', 'Call Ringing'),
        ('accepted', 'Call Accepted'),
        ('declined', 'Call Declined'),
        ('missed', 'Call Missed'),
        ('ended', 'Call Ended'),
        ('cancelled', 'Call Cancelled'),
    ]

    call = models.ForeignKey(Call, on_delete=models.CASCADE, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ['-timestamp']
```

### 2. Database Migration

Create and run migration:

```bash
python manage.py makemigrations
python manage.py migrate
```

### 3. Advanced Call Management Views

**File:** `zerver/views/advanced_calls.py`

```python
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db import transaction
from zerver.decorator import api_key_only_webhook_view
from zerver.models import UserProfile, get_user_by_delivery_email, Call, CallEvent
from zerver.lib.push_notifications import send_android_push_notification

@require_http_methods(["POST"])
@api_key_only_webhook_view('Zulip')
def create_advanced_call(request, user_profile):
    """
    Create a new call with full database tracking
    """
    try:
        with transaction.atomic():
            # Get request parameters
            recipient_email = request.POST.get('recipient_email')
            is_video_call = request.POST.get('is_video_call', 'true').lower() == 'true'

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
                state__in=['initiated', 'ringing', 'active']
            ).first()

            if existing_call:
                return JsonResponse({
                    "result": "error",
                    "message": "Call already in progress with this user",
                    "existing_call_id": str(existing_call.call_id)
                }, status=409)

            # Create call record
            call = Call.objects.create(
                call_type='video' if is_video_call else 'audio',
                initiator=user_profile,
                recipient=recipient,
                jitsi_room_name=f"zulip-call-{uuid.uuid4().hex[:12]}",
                realm=user_profile.realm
            )

            # Generate Jitsi URL
            jitsi_server = getattr(user_profile.realm, 'jitsi_server_url', None) or "https://meet.jit.si"
            call.jitsi_room_url = f"{jitsi_server}/{call.jitsi_room_name}"
            call.save()

            # Create initial call event
            CallEvent.objects.create(
                call=call,
                event_type='initiated',
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
        return JsonResponse({
            "result": "error",
            "message": f"Failed to create call: {str(e)}"
        }, status=500)

@require_http_methods(["POST"])
@api_key_only_webhook_view('Zulip')
def respond_to_advanced_call(request, user_profile, call_id):
    """
    Accept or decline a call invitation with full tracking
    """
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
            if call.state not in ['initiated', 'ringing']:
                return JsonResponse({
                    "result": "error",
                    "message": f"Cannot respond to call in state: {call.state}"
                }, status=400)

            response = request.POST.get('response')
            if response not in ['accept', 'decline']:
                return JsonResponse({
                    "result": "error",
                    "message": "Response must be 'accept' or 'decline'"
                }, status=400)

            if response == 'accept':
                call.state = 'active'
                call.started_at = timezone.now()
                event_type = 'accepted'

                # Notify caller
                notification_data = {
                    "type": "call_accepted",
                    "call_id": str(call.call_id),
                    "call_url": call.jitsi_room_url,
                    "accepter_name": user_profile.full_name,
                }
                send_call_push_notification(call.initiator, notification_data)

            else:
                call.state = 'declined'
                call.ended_at = timezone.now()
                event_type = 'declined'

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
                "call_url": call.jitsi_room_url if response == 'accept' else None,
                "message": f"Call {response}ed successfully"
            })

    except Exception as e:
        return JsonResponse({
            "result": "error",
            "message": f"Failed to respond to call: {str(e)}"
        }, status=500)

@require_http_methods(["GET"])
@api_key_only_webhook_view('Zulip')
def get_call_history(request, user_profile):
    """
    Get call history for the user
    """
    try:
        # Get query parameters
        limit = min(int(request.GET.get('limit', 50)), 100)
        offset = int(request.GET.get('offset', 0))

        # Get calls where user was initiator or recipient
        calls = Call.objects.filter(
            models.Q(initiator=user_profile) | models.Q(recipient=user_profile),
            realm=user_profile.realm
        ).order_by('-created_at')[offset:offset + limit]

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
        return JsonResponse({
            "result": "error",
            "message": f"Failed to get call history: {str(e)}"
        }, status=500)

def send_call_push_notification(recipient, call_data):
    """
    Enhanced FCM push notification for calls
    """
    try:
        send_android_push_notification(
            user_profile=recipient,
            data=call_data,
            priority="high"
        )
    except Exception as e:
        # Log error but don't fail the call
        import logging
        logging.error(f"Failed to send call push notification: {e}")
```

---

## 📱 Push Notification Configuration

### Firebase Cloud Messaging Setup

**File:** `zerver/lib/push_notifications.py` (enhance existing)

```python
# Add call-specific notification handling
def send_call_notification(user_profile, call_data):
    """
    Send high-priority call notification
    """
    # Prepare notification data
    notification_data = {
        "priority": "high",
        "data": call_data,
        "android": {
            "priority": "high",
            "ttl": "60s",  # Expire after 60 seconds
            "notification": {
                "channel_id": "calls",
                "priority": "high",
                "sound": "call_ringtone",
            }
        }
    }

    # Use existing Zulip FCM infrastructure
    return send_android_push_notification(
        user_profile=user_profile,
        data=call_data,
        priority="high"
    )
```

---

## 🧪 Testing Your Implementation

### 1. Test Call Creation

```bash
# Test basic call creation
curl -X POST "https://your-zulip-server.com/api/v1/calls/create" \
  -u "caller@domain.com:api-key" \
  -d "recipient_email=recipient@domain.com" \
  -d "is_video_call=true"
```

### 2. Test Call Response

```bash
# Test call acceptance
curl -X POST "https://your-zulip-server.com/api/v1/calls/CALL_ID/respond" \
  -u "recipient@domain.com:api-key" \
  -d "response=accept"
```

### 3. Test Call History

```bash
# Get call history
curl -X GET "https://your-zulip-server.com/api/v1/calls/history?limit=10" \
  -u "user@domain.com:api-key"
```

---

## 📋 Implementation Checklist

### Quick Start (Option A)
- [ ] Add `initiate_quick_call` endpoint
- [ ] Update URL configuration
- [ ] Test with Flutter app
- [ ] Verify push notifications work

### Standard Implementation (Option B)
- [ ] Implement all call management endpoints
- [ ] Add in-memory call state tracking
- [ ] Test accept/decline functionality
- [ ] Verify call status endpoint

### Advanced Implementation (Option C)
- [ ] Create database models and run migrations
- [ ] Implement advanced call endpoints
- [ ] Add call history functionality
- [ ] Set up proper error handling and logging
- [ ] Add monitoring and analytics

### Production Readiness
- [ ] Add rate limiting for call endpoints
- [ ] Implement proper error logging
- [ ] Set up monitoring and alerts
- [ ] Add database cleanup for old calls
- [ ] Configure FCM properly
- [ ] Add security headers
- [ ] Performance testing

---

## 🚀 Getting Started

1. **Choose your implementation option** based on requirements
2. **Copy the relevant code** into your Zulip server
3. **Update URL configuration** to expose endpoints
4. **Test with curl** to verify functionality
5. **Test with Flutter app** for end-to-end validation
6. **Configure push notifications** for full experience

## 📞 API Endpoints Summary

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/calls/initiate` | POST | Quick call creation (Option A) |
| `/api/v1/calls/create` | POST | Full call creation (Option B/C) |
| `/api/v1/calls/{id}/respond` | POST | Accept/decline call |
| `/api/v1/calls/{id}/end` | POST | End ongoing call |
| `/api/v1/calls/{id}/status` | GET | Get call status |
| `/api/v1/calls/history` | GET | Get call history (Option C) |

## 🔧 Required Request Parameters

### Call Creation
- `recipient_email` (required): Email of user to call
- `is_video_call` (optional): true/false for video/audio call

### Call Response
- `response` (required): "accept" or "decline"

The Flutter app is ready and waiting for your backend implementation! 🎉