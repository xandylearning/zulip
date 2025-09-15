# 📦 Zulip Calls Plugin Installation Guide

## 🎯 Overview
This guide provides step-by-step instructions for installing the Zulip Calls Plugin on your Zulip server.

## 📋 Prerequisites

- Zulip server running (version 8.0+)
- Root/sudo access to the server
- Basic knowledge of Django and Python

---

## 🚀 Installation Steps

### 1. Create Plugin Directory Structure

```bash
# Navigate to Zulip installation
cd /srv/zulip

# Create plugin directories
sudo mkdir -p zulip_calls_plugin/{views,urls,templates,migrations,static/{js,css}}
sudo mkdir -p zulip_calls_plugin/management/commands

# Set ownership
sudo chown -R zulip:zulip zulip_calls_plugin/
```

### 2. Create Core Plugin Files

#### `/srv/zulip/zulip_calls_plugin/__init__.py`
```python
"""Zulip Calls Plugin - Video and Audio Calling Integration"""

default_app_config = 'zulip_calls_plugin.apps.ZulipCallsPluginConfig'
```

#### `/srv/zulip/zulip_calls_plugin/apps.py`
```python
from django.apps import AppConfig

class ZulipCallsPluginConfig(AppConfig):
    name = 'zulip_calls_plugin'
    verbose_name = 'Zulip Calls Plugin'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Import signal handlers if needed
        pass
```

#### `/srv/zulip/zulip_calls_plugin/models.py`
```python
import uuid
from django.db import models
from django.utils import timezone
from zerver.models import UserProfile, Realm

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

    def __str__(self):
        return f"{self.call_type.title()} call from {self.initiator.full_name} to {self.recipient.full_name}"

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

    def __str__(self):
        return f"{self.event_type} by {self.user.full_name} at {self.timestamp}"
```

#### `/srv/zulip/zulip_calls_plugin/views/__init__.py`
```python
"""Zulip Calls Plugin Views"""

from .calls import (
    initiate_quick_call,
    create_call,
    respond_to_call,
    end_call,
    get_call_status,
    get_call_history,
    create_embedded_call,
    embedded_call_view,
    get_embedded_calls_script,
    get_calls_override_script,
)

__all__ = [
    'initiate_quick_call',
    'create_call',
    'respond_to_call',
    'end_call',
    'get_call_status',
    'get_call_history',
    'create_embedded_call',
    'embedded_call_view',
    'get_embedded_calls_script',
    'get_calls_override_script',
]
```

#### `/srv/zulip/zulip_calls_plugin/urls/__init__.py`
```python
"""Zulip Calls Plugin URL Configuration"""

from typing import Any

from .calls import urlpatterns

# Empty i18n_urlpatterns since this plugin doesn't have internationalized URLs
i18n_urlpatterns: Any = []

__all__ = ["urlpatterns", "i18n_urlpatterns"]
```

#### `/srv/zulip/zulip_calls_plugin/urls/calls.py`
```python
from django.urls import path

from ..views import (
    create_call,
    respond_to_call,
    end_call,
    get_call_status,
    get_call_history,
    initiate_quick_call,
    create_embedded_call,
    embedded_call_view,
    get_embedded_calls_script,
    get_calls_override_script,
)

# Plugin URL patterns for call functionality
urlpatterns = [
    # Quick call endpoint (Option A from feature spec)
    path("api/v1/calls/initiate", initiate_quick_call, name="initiate_quick_call"),

    # Full call management endpoints (Option B/C from feature spec)
    path("api/v1/calls/create", create_call, name="create_call"),
    path("api/v1/calls/<str:call_id>/respond", respond_to_call, name="respond_to_call"),
    path("api/v1/calls/<str:call_id>/end", end_call, name="end_call"),
    path("api/v1/calls/<str:call_id>/status", get_call_status, name="get_call_status"),

    # Embedded call endpoints
    path("api/v1/calls/create-embedded", create_embedded_call, name="create_embedded_call"),
    path("calls/embed/<str:call_id>", embedded_call_view, name="embedded_call_view"),
    path("calls/script", get_embedded_calls_script, name="get_embedded_calls_script"),
    path("calls/override.js", get_calls_override_script, name="get_calls_override_script"),

    # Call history endpoint
    path("api/v1/calls/history", get_call_history, name="get_call_history"),
]
```

### 3. Copy the Views File

```bash
# Copy the complete views file from your development environment
sudo cp /path/to/your/zulip_calls_plugin/views/calls.py /srv/zulip/zulip_calls_plugin/views/calls.py
sudo chown zulip:zulip /srv/zulip/zulip_calls_plugin/views/calls.py
```

### 4. Update Django Settings

#### Edit `/etc/zulip/settings.py`:
```python
# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... existing apps ...
    'zulip_calls_plugin',
]
```

#### Edit `/srv/zulip/zproject/urls.py`:
```python
# Add this import near the top
from zulip_calls_plugin.urls import urlpatterns as calls_urls

# Add this line in the urls list (around line 500+)
urls += calls_urls
```

### 5. Create and Run Migrations

```bash
# Navigate to Zulip directory
cd /srv/zulip

# Create migrations
sudo -u zulip python manage.py makemigrations zulip_calls_plugin

# Apply migrations
sudo -u zulip python manage.py migrate
```

### 6. Update Web Assets

#### Add JavaScript Integration to `/srv/zulip/web/src/compose_setup.js`:

Add this function around line 650:
```javascript
// Zulip Calls Plugin - Function to create embedded calls instead of links
function create_embedded_call_instead_of_link($button, isVideoCall) {
    console.log('🚀 Zulip Calls Plugin: Creating embedded call, isVideo:', isVideoCall);

    // Get recipient email
    function getRecipientEmail() {
        console.log('🔍 [compose_setup.js] Starting recipient search...');

        // Check if we're in a private message context
        const messageType = compose_state.get_message_type();
        console.log('🔍 [compose_setup.js] Message type:', messageType);

        if (messageType === "private") {
            // First try to get from the compose state
            const recipients = compose_state.private_message_recipient_emails();
            console.log('🔍 [compose_setup.js] Recipients from compose state:', recipients);
            if (recipients) {
                const firstRecipient = recipients.split(',')[0].trim();
                console.log('📧 [compose_setup.js] Found recipient via compose_state:', firstRecipient);
                return firstRecipient;
            }

            // Fallback: check the DM input field
            const dmInput = $("#private_message_recipient");
            console.log('🔍 [compose_setup.js] DM input:', dmInput.val());
            if (dmInput.length && dmInput.val()) {
                const inputRecipient = dmInput.val().trim().split(',')[0].trim();
                console.log('📧 [compose_setup.js] Found recipient via input:', inputRecipient);
                return inputRecipient;
            }
        }

        // If not composing but viewing a DM conversation, get recipient from narrow
        const currentFilter = narrow_state.filter();
        console.log('🔍 [compose_setup.js] Current filter:', currentFilter);

        if (currentFilter && currentFilter.is_conversation_view()) {
            console.log('🔍 [compose_setup.js] Is conversation view');
            const termTypes = currentFilter.sorted_term_types();
            console.log('🔍 [compose_setup.js] Term types:', termTypes);

            if (termTypes.includes("dm")) {
                console.log('🔍 [compose_setup.js] Has DM terms');
                // Get the recipient IDs from the narrow
                const recipientIds = currentFilter.operands("dm");
                console.log('🔍 [compose_setup.js] Recipient IDs:', recipientIds);

                if (recipientIds && recipientIds.length > 0) {
                    // Get the first recipient's email
                    const firstRecipientId = recipientIds[0];
                    console.log('🔍 [compose_setup.js] First recipient ID:', firstRecipientId);
                    const user = people.get_by_user_id(firstRecipientId);
                    console.log('🔍 [compose_setup.js] User from people API:', user);

                    if (user) {
                        console.log('📧 [compose_setup.js] Found recipient via narrow:', user.email);
                        return user.email;
                    }
                }
            }
        }

        return null;
    }

    const recipientEmail = getRecipientEmail();

    if (!recipientEmail) {
        compose_banner.show_error_message(
            "Please select a recipient for the call",
            compose_banner.CLASSNAMES.generic_compose_error,
            $("#compose_banners"),
            $("textarea#compose-textarea"),
        );
        return;
    }

    // Show loading state
    $button.prop('disabled', true).addClass('creating-call');

    // Create the embedded call
    $.ajax({
        url: '/api/v1/calls/create-embedded',
        method: 'POST',
        headers: {
            'X-CSRFToken': $('meta[name="csrf-token"]').attr('content') || $('input[name="csrfmiddlewaretoken"]').val()
        },
        data: {
            recipient_email: recipientEmail,
            is_video_call: isVideoCall,
            redirect_to_meeting: true
        },
        success: function(response) {
            console.log('📞 Call creation response:', response);

            if (response.result === 'success' && response.redirect_url) {
                // Open meeting immediately
                window.open(response.redirect_url, '_blank', 'width=1200,height=800,resizable=yes,menubar=no,toolbar=no');

                // Insert call link in compose box
                const $textarea = $('textarea#compose-textarea');
                const callType = isVideoCall ? 'video' : 'audio';
                const link = `[Join ${callType} call](${response.redirect_url})`;
                const currentValue = $textarea.val();
                const newValue = currentValue + (currentValue ? '\n\n' : '') + link;

                $textarea.val(newValue).trigger('input').focus();

                compose_banner.show_success_message(
                    `${callType.charAt(0).toUpperCase() + callType.slice(1)} call started!`,
                    $("#compose_banners"),
                );
            } else {
                throw new Error(response.message || 'Failed to create call');
            }
        },
        error: function(xhr) {
            console.error('❌ Call creation failed:', xhr);
            const errorData = xhr.responseJSON;
            const msg = errorData?.message || 'Failed to create call';

            compose_banner.show_error_message(
                msg,
                compose_banner.CLASSNAMES.generic_compose_error,
                $("#compose_banners"),
                $("textarea#compose-textarea"),
            );

            console.log('🔄 Falling back to original Zulip call functionality');
            // Fallback to original functionality
            if (typeof original_generate_and_insert_audio_or_video_call_link !== 'undefined') {
                original_generate_and_insert_audio_or_video_call_link($button, !isVideoCall);
            }
        },
        complete: function() {
            $button.removeClass('creating-call').prop('disabled', false);
        }
    });
}
```

Then replace the existing call button handlers around line 620:
```javascript
// Replace the video call button handler
$("body").on("click", ".video_link", (e) => {
    e.preventDefault();
    e.stopPropagation();
    create_embedded_call_instead_of_link($(e.target), true);
});

// Replace the audio call button handler
$("body").on("click", ".audio_link", (e) => {
    e.preventDefault();
    e.stopPropagation();
    create_embedded_call_instead_of_link($(e.target), false);
});
```

### 7. Set File Permissions

```bash
# Set proper ownership for all plugin files
sudo chown -R zulip:zulip /srv/zulip/zulip_calls_plugin/

# Set executable permissions for management commands (if any)
sudo chmod +x /srv/zulip/zulip_calls_plugin/management/commands/*.py
```

### 8. Restart Services

```bash
# Restart Zulip services
sudo supervisorctl restart zulip-django
sudo supervisorctl restart zulip-tornado

# If you have memcached
sudo service memcached restart

# Restart nginx
sudo service nginx restart

# Rebuild and restart webpack if needed
cd /srv/zulip
sudo -u zulip ./tools/webpack --quiet
```

---

## 🎛️ Event Listeners Installation

### 1. Enable Event Listeners App

Add to `/etc/zulip/settings.py`:
```python
# Add to INSTALLED_APPS if not already present
INSTALLED_APPS = [
    # ... existing apps ...
    'zerver.event_listeners',  # Enable event listeners
    'zulip_calls_plugin',
]
```

### 2. Create Call Event Listeners

#### Create `/srv/zulip/zulip_calls_plugin/event_listeners.py`:
```python
import logging
from typing import Any, Dict
from zerver.event_listeners.base import EventListener
from zerver.models import UserProfile
from .models import Call, CallEvent

logger = logging.getLogger(__name__)

class CallEventListener(EventListener):
    """Event listener for call-related events"""

    def __init__(self):
        super().__init__()
        self.event_types = ['call_created', 'call_ended', 'call_accepted', 'call_declined']

    def handle_event(self, event_type: str, event_data: Dict[str, Any]) -> None:
        """Handle call events"""
        try:
            if event_type == 'call_created':
                self._handle_call_created(event_data)
            elif event_type == 'call_ended':
                self._handle_call_ended(event_data)
            elif event_type == 'call_accepted':
                self._handle_call_accepted(event_data)
            elif event_type == 'call_declined':
                self._handle_call_declined(event_data)
        except Exception as e:
            logger.error(f"Error handling call event {event_type}: {e}")

    def _handle_call_created(self, event_data: Dict[str, Any]) -> None:
        """Handle call creation events"""
        call_id = event_data.get('call_id')
        logger.info(f"Call created event received for call {call_id}")

        # Add any custom logic for call creation
        # e.g., analytics, notifications, etc.

    def _handle_call_ended(self, event_data: Dict[str, Any]) -> None:
        """Handle call end events"""
        call_id = event_data.get('call_id')
        duration = event_data.get('duration_seconds')
        logger.info(f"Call {call_id} ended after {duration} seconds")

        # Add any custom logic for call ending
        # e.g., cleanup, analytics, billing, etc.

    def _handle_call_accepted(self, event_data: Dict[str, Any]) -> None:
        """Handle call acceptance events"""
        call_id = event_data.get('call_id')
        accepter_id = event_data.get('accepter_id')
        logger.info(f"Call {call_id} accepted by user {accepter_id}")

    def _handle_call_declined(self, event_data: Dict[str, Any]) -> None:
        """Handle call decline events"""
        call_id = event_data.get('call_id')
        decliner_id = event_data.get('decliner_id')
        logger.info(f"Call {call_id} declined by user {decliner_id}")

# Register the event listener
call_event_listener = CallEventListener()
```

### 3. Register Event Listeners

#### Update `/srv/zulip/zulip_calls_plugin/apps.py`:
```python
from django.apps import AppConfig

class ZulipCallsPluginConfig(AppConfig):
    name = 'zulip_calls_plugin'
    verbose_name = 'Zulip Calls Plugin'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # Register event listeners
        try:
            from .event_listeners import call_event_listener
            from zerver.event_listeners.registry import register_event_listener

            register_event_listener(call_event_listener)
            print("✅ Zulip Calls Plugin event listeners registered")
        except ImportError:
            # Event listeners not available in this Zulip version
            print("⚠️ Event listeners not available, skipping registration")
        except Exception as e:
            print(f"❌ Failed to register call event listeners: {e}")
```

---

## 🧪 Testing Installation

### 1. Test Database Migration

```bash
cd /srv/zulip
sudo -u zulip python manage.py shell

# In Python shell:
from zulip_calls_plugin.models import Call, CallEvent
print("✅ Models imported successfully")

# Test creating a call (replace with real user IDs)
from zerver.models import UserProfile
users = UserProfile.objects.all()[:2]
if len(users) >= 2:
    call = Call.objects.create(
        call_type='video',
        initiator=users[0],
        recipient=users[1],
        jitsi_room_name='test-room',
        jitsi_room_url='https://meet.jit.si/test-room',
        realm=users[0].realm
    )
    print(f"✅ Test call created: {call.call_id}")
```

### 2. Test API Endpoints

```bash
# Test the embedded call endpoint
curl -X POST "http://localhost:9991/api/v1/calls/create-embedded" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "recipient_email=testuser@yourdomain.com&is_video_call=true" \
  --cookie "sessionid=your-session-id" \
  -H "X-CSRFToken: your-csrf-token"

# Test call history
curl -X GET "http://localhost:9991/api/v1/calls/history" \
  -u "your-email@domain.com:your-api-key"
```

### 3. Test Web Integration

1. Log into your Zulip web interface
2. Navigate to a DM conversation
3. Click the video or audio call button
4. Check browser console for logs
5. Verify call creation and Jitsi opening

---

## 🚨 Troubleshooting

### Common Issues

#### Plugin Not Loading
```bash
# Check if plugin is in INSTALLED_APPS
grep -n "zulip_calls_plugin" /etc/zulip/settings.py

# Check for import errors
sudo -u zulip python manage.py shell -c "import zulip_calls_plugin; print('Plugin imported successfully')"
```

#### Migration Issues
```bash
# Reset migrations if needed
sudo rm -f /srv/zulip/zulip_calls_plugin/migrations/000*.py
sudo -u zulip python manage.py makemigrations zulip_calls_plugin
sudo -u zulip python manage.py migrate
```

#### JavaScript Errors
- Check browser console for errors
- Verify CSRF token handling
- Check network requests in DevTools
- Ensure proper jQuery syntax

#### 404 Errors on API Endpoints
- Verify URL patterns are included in main urls.py
- Check that views are imported correctly
- Restart Django server after URL changes

### Debug Commands

```bash
# Check Django logs
sudo tail -f /var/log/zulip/django.log

# Check error logs
sudo tail -f /var/log/zulip/errors.log

# Test URL resolution
sudo -u zulip python manage.py shell -c "
from django.urls import reverse
print(reverse('create_embedded_call'))
"

# Check database tables
sudo -u zulip python manage.py dbshell
# Then: \dt zulip_calls_plugin_*
```

---

## ✅ Installation Checklist

### Prerequisites
- [ ] Zulip server running
- [ ] Root/sudo access
- [ ] Django knowledge

### Plugin Installation
- [ ] Created plugin directory structure
- [ ] Created all Python files (models, views, urls, apps)
- [ ] Added to INSTALLED_APPS in settings.py
- [ ] Updated main urls.py to include plugin URLs
- [ ] Created and ran migrations
- [ ] Updated JavaScript files
- [ ] Set proper file permissions

### Event Listeners
- [ ] Created event_listeners.py
- [ ] Updated apps.py to register listeners
- [ ] Added zerver.event_listeners to INSTALLED_APPS

### Testing
- [ ] Database models work
- [ ] API endpoints respond
- [ ] Web integration works
- [ ] Event listeners register

### Production
- [ ] Restarted all services
- [ ] Tested with real users
- [ ] Checked logs for errors
- [ ] Configured monitoring

The Zulip Calls Plugin should now be fully installed and operational! 🎉

---

## 📞 Support

If you encounter issues:

1. Check the troubleshooting section
2. Review Django and error logs
3. Test individual components
4. Verify file permissions and ownership
5. Ensure all services are restarted

The plugin provides comprehensive logging to help diagnose issues.