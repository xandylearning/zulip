# 🚀 Zulip Calls Plugin

A modular plugin that adds video/voice calling functionality to Zulip using Jitsi Meet integration. This plugin is designed to be easily installed and removed without affecting core Zulip functionality.

## 📋 Features

- **Video & Audio Calls**: Full Jitsi Meet integration for high-quality calls
- **Push Notifications**: Real-time call invitations with FCM support
- **Call Management**: Accept, decline, and end calls with full state tracking
- **Call History**: Complete call history with duration tracking
- **Database Models**: Persistent storage of call data and events
- **Plugin Architecture**: Easy install/uninstall without core modifications

## 🛠️ Installation

### Quick Installation

```bash
# Install the plugin
python manage.py install_calls_plugin

# Restart your Zulip server
./scripts/restart-server
```

### Manual Installation

1. **Add to INSTALLED_APPS** in `zproject/computed_settings.py`:
```python
INSTALLED_APPS = [
    # ... existing apps ...
    "zulip_calls_plugin",
]
```

2. **Add URL patterns** in `zproject/urls.py`:
```python
from zulip_calls_plugin.plugin_config import CallsPluginConfig

urlpatterns = [
    # ... existing patterns ...
    path('', include(CallsPluginConfig.get_url_patterns())),
]
```

3. **Create and apply migrations**:
```bash
python manage.py makemigrations zulip_calls_plugin
python manage.py migrate zulip_calls_plugin
```

## 🔧 Configuration

### Jitsi Server Configuration

Set your Jitsi server URL (optional, defaults to meet.jit.si):

```python
# In Django shell or management command
from zerver.models import Realm

realm = Realm.objects.get(string_id="your-organization")
realm.jitsi_server_url = "https://your-jitsi-server.com"
realm.save()
```

### Push Notifications

Ensure your Zulip server has FCM configured for mobile push notifications. The plugin uses Zulip's existing push notification infrastructure.

## 📞 API Endpoints

| Endpoint | Method | Description | Implementation |
|----------|--------|-------------|----------------|
| `/api/v1/calls/initiate` | POST | Quick call creation (no DB) | Option A |
| `/api/v1/calls/create` | POST | Full call creation with tracking | Option B/C |
| `/api/v1/calls/create-embedded` | POST | Create embedded call for web UI | **NEW** |
| `/api/v1/calls/{id}/respond` | POST | Accept/decline call invitation | Option B/C |
| `/api/v1/calls/{id}/end` | POST | End ongoing call | Option B/C |
| `/api/v1/calls/{id}/status` | GET | Get current call status | Option B/C |
| `/api/v1/calls/history` | GET | Get user's call history | Option C |
| `/calls/embed/{id}` | GET | **Embedded call interface** | **NEW** |
| `/calls/script` | GET | **JavaScript for embedded calls** | **NEW** |

## 🧪 Testing

### Test Embedded Call Creation (NEW!)

```bash
curl -X POST "http://localhost:9991/api/v1/calls/create-embedded" \
  -u "caller@example.com:api-key" \
  -d "recipient_email=recipient@example.com" \
  -d "is_video_call=true"
```

**Response includes `embedded_url` for the call interface!**

### Test Web Interface

1. **Navigate to the Zulip web interface**
2. **Start a new direct message**
3. **Click the video or audio call button**
4. **Call window opens embedded in your domain! 🎉**

### Test Standard API

```bash
# Test standard call creation
curl -X POST "http://localhost:9991/api/v1/calls/create" \
  -u "caller@example.com:api-key" \
  -d "recipient_email=recipient@example.com" \
  -d "is_video_call=true"

# Test call response
curl -X POST "http://localhost:9991/api/v1/calls/CALL_ID/respond" \
  -u "recipient@example.com:api-key" \
  -d "response=accept"

# Test call history
curl -X GET "http://localhost:9991/api/v1/calls/history?limit=10" \
  -u "user@example.com:api-key"
```

## 🌐 Web Interface Integration (NEW!)

The plugin automatically overrides Zulip's existing video/audio call buttons to use embedded calls instead of opening new tabs.

### Features:
- **Embedded Jitsi Meet**: Calls open in a popup window within your domain
- **Call Management**: Accept, decline, end calls with real-time updates
- **Visual Notifications**: In-browser notifications for call status
- **Seamless Integration**: Works with existing Zulip call buttons
- **No External Redirects**: All calls stay within your Zulip domain

### How It Works:
1. **User clicks video/audio button** in Zulip compose area
2. **Plugin intercepts** the click and calls `/api/v1/calls/create-embedded`
3. **Embedded call window opens** showing Jitsi Meet interface
4. **Call URL is inserted** into the message compose box
5. **Real-time updates** between participants via push notifications

### Automatic Integration:
The plugin JavaScript automatically:
- Detects and overrides existing call buttons (`.video_link`, `.audio_link`)
- Manages call windows and prevents duplicates
- Handles call state updates and notifications
- Integrates with Zulip's compose system

## 📱 Flutter App Integration

This plugin is designed to work with the Zulip Flutter mobile app. The Flutter app should:

1. **Call Creation**: POST to `/api/v1/calls/create` when user taps call button
2. **Push Handling**: Listen for call invitation push notifications
3. **Call Response**: POST to `/api/v1/calls/{id}/respond` for accept/decline
4. **Jitsi Integration**: Open Jitsi Meet with the provided `call_url`

### Expected Push Notification Format

```json
{
  "type": "call_invitation",
  "call_id": "uuid-string",
  "call_url": "https://meet.jit.si/zulip-call-abc123",
  "call_type": "video",
  "caller_name": "John Doe",
  "caller_id": 123,
  "room_name": "zulip-call-abc123"
}
```

## 📊 Database Schema

### Call Model
- `call_id`: UUID primary key
- `call_type`: "video" or "audio"
- `state`: Current call state (initiated, active, ended, etc.)
- `initiator`: Foreign key to UserProfile
- `recipient`: Foreign key to UserProfile
- `jitsi_room_name`: Jitsi meeting room name
- `jitsi_room_url`: Full Jitsi meeting URL
- `created_at`, `started_at`, `ended_at`: Timestamps
- `realm`: Foreign key to Realm

### CallEvent Model
- `call`: Foreign key to Call
- `event_type`: Type of event (initiated, accepted, declined, etc.)
- `user`: UserProfile who triggered the event
- `timestamp`: When the event occurred
- `metadata`: Additional event data (JSON)

## 🚫 Uninstallation

### Quick Uninstall

```bash
# Remove plugin completely (including data)
python manage.py uninstall_calls_plugin

# Or keep call data
python manage.py uninstall_calls_plugin --keep-data
```

### Manual Uninstall

1. **Remove from INSTALLED_APPS** in `zproject/computed_settings.py`
2. **Remove URL patterns** from `zproject/urls.py`
3. **Remove database tables** (optional):
```bash
python manage.py migrate zulip_calls_plugin zero
```

## 🔍 Troubleshooting

### Plugin Not Loading
- Check that `zulip_calls_plugin` is in INSTALLED_APPS
- Verify URL patterns are included
- Restart the Zulip server

### Database Errors
- Ensure migrations are applied: `python manage.py migrate zulip_calls_plugin`
- Check database permissions

### Push Notifications Not Working
- Verify FCM is configured in Zulip
- Check that mobile apps have proper push tokens
- Review server logs for push notification errors

### Jitsi Calls Not Connecting
- Verify Jitsi server URL is accessible
- Check firewall settings for Jitsi ports
- Ensure HTTPS is properly configured

## 🏗️ Development

### Plugin Structure

```
zulip_calls_plugin/
├── __init__.py              # Plugin metadata
├── apps.py                  # Django app configuration
├── plugin_config.py         # Plugin configuration utilities
├── models/
│   ├── __init__.py
│   └── calls.py             # Call and CallEvent models
├── views/
│   ├── __init__.py
│   └── calls.py             # API view implementations
├── urls/
│   ├── __init__.py
│   └── calls.py             # URL routing
├── migrations/              # Database migrations (auto-generated)
├── management/
│   └── commands/
│       ├── install_calls_plugin.py    # Installation command
│       └── uninstall_calls_plugin.py  # Uninstallation command
└── README.md                # This file
```

### Adding New Features

1. **Models**: Add new models to `models/calls.py`
2. **Views**: Add new API endpoints to `views/calls.py`
3. **URLs**: Register new URLs in `urls/calls.py`
4. **Migrations**: Run `python manage.py makemigrations zulip_calls_plugin`

## 📄 License

This plugin is released under the same license as Zulip (Apache 2.0).

## 🤝 Contributing

Contributions are welcome! Please follow Zulip's contribution guidelines and ensure all changes are backward compatible.

## 📞 Support

For issues and questions:
- Check Zulip's main documentation
- Review the troubleshooting section above
- Open an issue in the Zulip repository

---

**Ready to make calls in Zulip! 🎉📞**