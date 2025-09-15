# 📞 Zulip Calls Plugin - Complete Documentation

## 📋 Overview

The Zulip Calls Plugin provides seamless video and audio calling functionality integrated directly into Zulip. It supports both web and mobile clients with advanced features like moderator privileges, call state management, and comprehensive API endpoints.

## 🎯 Features

### ✅ Core Features
- **Video & Audio Calls**: Support for both video and audio calling
- **Moderator Privileges**: Call initiators get full moderator control
- **Web Integration**: JavaScript override for Zulip web interface
- **Mobile API**: Complete REST API for mobile app integration
- **Push Notifications**: Real-time call notifications
- **Call History**: Complete call tracking and history
- **Call States**: Full state management (initiated, active, ended, etc.)
- **Database Integration**: Persistent call storage and tracking

### ✅ Advanced Features
- **Separate URLs**: Different URLs for moderators and participants
- **Call Events**: Detailed event tracking for analytics
- **User Authentication**: Integrated with Zulip's auth system
- **Error Handling**: Comprehensive error handling and logging
- **Domain Flexibility**: Handles multiple email domain formats
- **Real-time Updates**: Live call status updates

---

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Web Client    │    │  Mobile Client  │    │  Jitsi Server   │
│                 │    │                 │    │                 │
│ - JavaScript    │    │ - Flutter/RN    │    │ - meet.jit.si   │
│ - Call Buttons  │    │ - Push Notifs   │    │ - Custom Server │
│ - UI Override   │    │ - Native UI     │    │                 │
└─────────┬───────┘    └─────────┬───────┘    └─────────┬───────┘
          │                      │                      │
          └──────────────────────┼──────────────────────┘
                                 │
                    ┌─────────────▼───────────────┐
                    │     Zulip Backend          │
                    │                            │
                    │ - Django Views             │
                    │ - Database Models          │
                    │ - Push Notification System │
                    │ - Authentication           │
                    │ - URL Management           │
                    └────────────────────────────┘
```

---

## 🗄️ Database Schema

### Call Model
```python
class Call(models.Model):
    call_id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    call_type = models.CharField(max_length=10, choices=CALL_TYPES)  # 'video', 'audio'
    state = models.CharField(max_length=20, choices=CALL_STATES, default='initiated')

    # Participants
    initiator = models.ForeignKey(UserProfile, related_name='initiated_calls')
    recipient = models.ForeignKey(UserProfile, related_name='received_calls')

    # Jitsi Integration
    jitsi_room_name = models.CharField(max_length=255)
    jitsi_room_url = models.URLField()  # Base URL without parameters

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)

    # Realm
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
```

### CallEvent Model
```python
class CallEvent(models.Model):
    call = models.ForeignKey(Call, related_name='events')
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    user = models.ForeignKey(UserProfile)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)
```

### Call States
- `initiated` - Call created, waiting for response
- `ringing` - Recipient notified
- `active` - Call accepted and ongoing
- `ended` - Call completed normally
- `declined` - Call rejected by recipient
- `missed` - Call not answered in time
- `cancelled` - Call cancelled by initiator

---

## 🚀 API Endpoints

### Core Call Management

#### POST `/api/v1/calls/create-embedded`
**Purpose**: Create a call optimized for web interface with immediate redirect support

**Authentication**: Session-based (`@zulip_login_required`)

**Parameters**:
```
recipient_email: string (required) - Email of the user to call
is_video_call: boolean (optional, default: true) - Video or audio call
redirect_to_meeting: boolean (optional, default: false) - Auto-redirect to Jitsi
```

**Response**:
```json
{
  "result": "success",
  "call_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_url": "https://meet.jit.si/zulip-call-abc123?userInfo.displayName=John&config.startWithAudioMuted=false",
  "participant_url": "https://meet.jit.si/zulip-call-abc123?userInfo.displayName=Jane&config.startWithAudioMuted=true",
  "embedded_url": "/calls/embed/550e8400-e29b-41d4-a716-446655440000",
  "call_type": "video",
  "room_name": "zulip-call-abc123",
  "recipient": {
    "user_id": 456,
    "full_name": "Jane Doe",
    "email": "jane@example.com"
  }
}
```

#### POST `/api/v1/calls/create`
**Purpose**: Create a call with full database tracking for mobile/API clients

**Authentication**: API Key (`@authenticated_rest_api_view`)

**Parameters**: Same as create-embedded

**Response**: Similar to create-embedded but includes additional metadata

#### POST `/api/v1/calls/{call_id}/respond`
**Purpose**: Accept or decline a call invitation

**Authentication**: API Key (`@authenticated_rest_api_view`)

**Parameters**:
```
response: string (required) - "accept" or "decline"
```

**Response**:
```json
{
  "result": "success",
  "action": "accept",
  "call_url": "https://meet.jit.si/zulip-call-abc123?params",
  "message": "Call accepted successfully"
}
```

#### POST `/api/v1/calls/{call_id}/end`
**Purpose**: End an ongoing call

**Authentication**: API Key (`@authenticated_rest_api_view`)

**Response**:
```json
{
  "result": "success",
  "message": "Call ended successfully"
}
```

#### GET `/api/v1/calls/{call_id}/status`
**Purpose**: Get current status of a call

**Authentication**: API Key (`@authenticated_rest_api_view`)

**Response**:
```json
{
  "result": "success",
  "call": {
    "call_id": "550e8400-e29b-41d4-a716-446655440000",
    "state": "active",
    "call_url": "https://meet.jit.si/zulip-call-abc123",
    "call_type": "video",
    "created_at": "2025-09-15T14:30:00Z",
    "started_at": "2025-09-15T14:30:15Z",
    "ended_at": null,
    "initiator": {
      "user_id": 123,
      "full_name": "John Doe",
      "email": "john@example.com"
    },
    "recipient": {
      "user_id": 456,
      "full_name": "Jane Doe",
      "email": "jane@example.com"
    }
  }
}
```

#### GET `/api/v1/calls/history`
**Purpose**: Get call history for the authenticated user

**Authentication**: API Key (`@authenticated_rest_api_view`)

**Parameters**:
```
limit: int (optional, default: 50, max: 100) - Number of calls to return
offset: int (optional, default: 0) - Pagination offset
```

**Response**:
```json
{
  "result": "success",
  "calls": [
    {
      "call_id": "550e8400-e29b-41d4-a716-446655440000",
      "call_type": "video",
      "state": "ended",
      "was_initiator": true,
      "other_user": {
        "user_id": 456,
        "full_name": "Jane Doe",
        "email": "jane@example.com"
      },
      "created_at": "2025-09-15T14:30:00Z",
      "started_at": "2025-09-15T14:30:15Z",
      "ended_at": "2025-09-15T14:45:30Z",
      "duration_seconds": 915
    }
  ],
  "has_more": false
}
```

### Additional Endpoints

#### GET `/calls/embed/{call_id}`
**Purpose**: Serve embedded call interface for web

**Authentication**: Session-based (`@zulip_login_required`)

#### GET `/calls/override.js`
**Purpose**: Serve JavaScript override script for web integration

**Authentication**: None (public)

#### GET `/calls/script`
**Purpose**: Serve embedded calls script and CSS

**Authentication**: None (public)

---

## 🔧 Installation & Setup

### 1. Database Migration
```bash
# Create and apply migrations for the new models
python manage.py makemigrations
python manage.py migrate
```

### 2. URL Configuration
The plugin is automatically integrated into Zulip's URL configuration via:
```python
# In zproject/urls.py
from zulip_calls_plugin.urls import urlpatterns as calls_urls
urls += calls_urls
```

### 3. File Structure
```
zulip_calls_plugin/
├── __init__.py
├── models.py                 # Call and CallEvent models
├── views/
│   ├── __init__.py          # View exports
│   └── calls.py             # Main call management views
├── urls/
│   ├── __init__.py          # URL exports
│   └── calls.py             # URL patterns
└── templates/               # HTML templates for embedded views
    ├── embedded_call.html
    └── embedded_calls_script.html
```

### 4. Key Files Modified

#### `/Users/straxs/Work/zulip/zulip_calls_plugin/models.py`
Contains the Call and CallEvent Django models with proper indexes and relationships.

#### `/Users/straxs/Work/zulip/zulip_calls_plugin/views/calls.py`
Main implementation file containing:
- All API endpoint handlers
- Push notification system
- URL generation with moderator/participant distinction
- Error handling and logging
- Domain flexibility for user lookup

#### `/Users/straxs/Work/zulip/zulip_calls_plugin/urls/calls.py`
URL routing configuration mapping endpoints to views.

#### `/Users/straxs/Work/zulip/web/src/compose_setup.js`
JavaScript integration for web client call functionality.

---

## 🎮 Web Integration

### JavaScript Override System
The plugin includes a sophisticated JavaScript override system that:

1. **Intercepts Call Button Clicks**: Uses multiple strategies to override Zulip's default call buttons
2. **Extracts Recipients**: Intelligently finds recipient emails from compose state or narrow context
3. **Creates Calls**: Makes API calls to the backend to initiate calls
4. **Handles Responses**: Opens Jitsi meetings and inserts call links in chat

### Key JavaScript Functions
```javascript
// Main call creation function
function create_embedded_call_instead_of_link($button, isVideoCall)

// Recipient extraction with multiple fallback methods
function getRecipientEmail()

// CSRF token handling
function getCsrfToken()
```

### Override Strategies
1. **Function Override**: Replaces `compose_call_ui.generate_and_insert_audio_or_video_call_link`
2. **Click Handler Override**: Removes existing handlers and adds custom ones
3. **DOM Level Interception**: Captures clicks at the document level

---

## 📱 Mobile Integration

### Authentication
Mobile clients should use Zulip's API key authentication:
```
Authorization: Basic base64(email:api_key)
```

### Push Notifications
The system sends FCM push notifications with this data structure:
```json
{
  "type": "call_invitation",
  "call_id": "uuid",
  "call_url": "https://meet.jit.si/room?participant_params",
  "call_type": "video|audio",
  "caller_name": "John Doe",
  "caller_id": 123,
  "room_name": "zulip-call-abc123"
}
```

For detailed mobile integration, see `MOBILE_CALL_INTEGRATION.md`.

---

## 🔐 Security & Authentication

### Web Endpoints
- Use `@zulip_login_required` for session-based authentication
- CSRF protection included
- Domain validation for user lookups

### API Endpoints
- Use `@authenticated_rest_api_view` for API key authentication
- Rate limiting recommended for production
- Input validation on all parameters

### Authorization
- Users can only create calls within their realm
- Users can only respond to calls addressed to them
- Users can only view/end calls they participate in
- Moderator URLs are only provided to call initiators

---

## 🎯 Moderator System

### How It Works
1. **Call Initiator** receives a URL with moderator parameters:
   ```
   https://meet.jit.si/room?userInfo.displayName=Initiator&config.startWithAudioMuted=false&config.enableInsecureRoomNameWarning=false
   ```

2. **Call Recipient** receives a URL with participant parameters:
   ```
   https://meet.jit.si/room?userInfo.displayName=Participant&config.startWithAudioMuted=true
   ```

### Moderator Privileges
- Mute/unmute participants
- Remove participants from call
- End call for everyone
- Control meeting settings
- Start with audio/video enabled

### Participant Experience
- Join with audio/video muted by default
- Cannot control other participants
- Can only control own audio/video
- Streamlined joining experience

---

## 🚨 Error Handling

### Common Error Scenarios

#### User Not Found
```json
{
  "result": "error",
  "message": "Recipient not found. Tried: ['user@domain1.com', 'user@domain2.com']. Available: ['valid1@domain.com', 'valid2@domain.com']"
}
```

#### Call Already in Progress
```json
{
  "result": "error",
  "message": "Call already in progress with this user",
  "existing_call_id": "uuid"
}
```

#### Invalid Call State
```json
{
  "result": "error",
  "message": "Cannot respond to call in state: ended"
}
```

#### Unauthorized Access
```json
{
  "result": "error",
  "message": "Not authorized to respond to this call"
}
```

### Domain Flexibility
The system automatically tries multiple email domain formats:
- If `user@domain1.com` fails, tries `user@domain2.com`
- Supports `@zulipdev.com` ↔ `@zulip.com` conversion
- Logs attempted email formats for debugging

---

## 📊 Logging & Monitoring

### Key Log Messages
```python
# Call creation
logger.info(f"Attempting to create call: recipient_email='{recipient_email}', realm='{realm.string_id}'")

# User lookup failures
logger.error(f"User not found after trying: {tried_emails}, realm='{realm.string_id}'")

# Alternative domain success
logger.info(f"Found user with alternative email: '{alternative_email}' instead of '{original_email}'")

# Push notification failures
logger.error(f"Failed to send call push notification: {e}")
```

### Monitoring Recommendations
- Track call creation success/failure rates
- Monitor push notification delivery
- Alert on high error rates
- Track call duration and completion rates
- Monitor Jitsi server connectivity

---

## 🧪 Testing

### Manual Testing

#### Web Interface
1. Navigate to a DM conversation
2. Click video/audio call button
3. Verify call creation and Jitsi opening
4. Test with different users and call types

#### API Testing
```bash
# Create a call
curl -X POST "http://localhost:9991/api/v1/calls/create-embedded" \
  -H "X-CSRFToken: your-csrf-token" \
  -H "Cookie: sessionid=your-session-id" \
  -d "recipient_email=test@example.com&is_video_call=true"

# Accept a call
curl -X POST "http://localhost:9991/api/v1/calls/CALL_ID/respond" \
  -u "user@domain.com:api-key" \
  -d "response=accept"

# Get call history
curl -X GET "http://localhost:9991/api/v1/calls/history?limit=10" \
  -u "user@domain.com:api-key"
```

### Automated Testing
```bash
# Run Django tests
./tools/test-backend zulip_calls_plugin

# Run JavaScript tests
./tools/test-js-with-node web/tests/compose_setup.test.js

# Run linting
./tools/lint zulip_calls_plugin/
```

---

## 🚀 Production Deployment

### Performance Considerations
- Index database properly for call queries
- Use Redis for call state caching if needed
- Configure proper connection pooling for Jitsi
- Set up CDN for JavaScript files

### Security Hardening
- Add rate limiting to call creation endpoints
- Implement call time limits
- Monitor for abuse patterns
- Validate all user inputs
- Use HTTPS for all Jitsi URLs

### Monitoring & Alerts
- Track call success rates
- Monitor Jitsi server health
- Alert on high error rates
- Track user engagement metrics

### Scaling Considerations
- Database connection pooling
- Async task processing for push notifications
- Load balancing for Jitsi servers
- Cleanup jobs for old call records

---

## 🔧 Configuration Options

### Realm Settings
```python
# Set custom Jitsi server for a realm
realm = Realm.objects.get(string_id="your-org")
realm.jitsi_server_url = "https://your-jitsi-server.com"
realm.save()
```

### JavaScript Override Settings
The override script includes configurable behavior:
- Multiple fallback strategies for recipient detection
- Customizable UI messages and error handling
- Debug logging levels
- Retry logic for API calls

---

## 📚 Troubleshooting

### Common Issues

#### "Recipient not found" Error
- Check email format matches database
- Verify user exists in same realm
- Check debug logs for attempted emails
- Verify domain handling is correct

#### JavaScript Override Not Working
- Check browser console for errors
- Verify override script is loaded
- Check for conflicting JavaScript
- Ensure proper CSRF token handling

#### Push Notifications Not Delivered
- Verify FCM configuration
- Check user device tokens
- Verify push notification payload format
- Check server logs for delivery failures

#### Calls Not Starting
- Verify Jitsi server accessibility
- Check URL parameter formatting
- Verify user permissions (camera/microphone)
- Test with different browsers

### Debug Mode
Enable debug logging to see detailed information:
```python
import logging
logging.getLogger('zulip_calls_plugin').setLevel(logging.DEBUG)
```

---

## 🤝 Contributing

### Code Style
- Follow Zulip's Python and JavaScript style guides
- Use type hints for all Python functions
- Add comprehensive error handling
- Include logging for debugging

### Testing Requirements
- Add unit tests for all new functionality
- Include integration tests for API endpoints
- Test edge cases and error conditions
- Verify cross-browser compatibility for JavaScript

### Documentation
- Update API documentation for any changes
- Include examples for new features
- Document configuration options
- Provide troubleshooting guides

---

## 📄 License

This plugin is part of the Zulip project and follows the same Apache 2.0 license.

---

## 📞 Support

For issues and feature requests:
1. Check the troubleshooting section
2. Review the debug logs
3. Test with manual API calls
4. Create detailed issue reports with logs and reproduction steps

The Zulip Calls Plugin provides a complete, production-ready calling solution integrated seamlessly into the Zulip ecosystem! 🎉