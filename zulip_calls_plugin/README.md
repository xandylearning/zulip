# 🚀 Zulip Calls Plugin

A modular plugin that adds video/voice calling functionality to Zulip using Jitsi Meet integration. This plugin is designed to be easily installed and removed without affecting core Zulip functionality.

## 📋 Features

- **Video & Audio Calls**: Full Jitsi Meet integration for high-quality calls
- **Real-time WebSocket Events**: Live call status updates with Zulip's event system
- **Push Notifications**: Real-time call invitations with FCM support
- **Call Management**: Accept, decline, and end calls with full state tracking
- **Call Acknowledgment**: Participants can acknowledge incoming calls (ringing status)
- **Status Updates**: Real-time status updates during active calls (connected, muted, etc.)
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

### Optional: Jitsi JWT and call recording

- **Jitsi JWT**: Set `JITSI_JWT_ENABLED = True` and configure `JITSI_JWT_SECRET` (and related settings) in production when your Jitsi server has Prosody JWT enabled. Default: `False` for development.
- **Call recording**: Set `CALL_RECORDING_ENABLED = True` and configure GCP bucket and Jibri when recording is required. Default: `False`.

See **[docs/JITSI_SECURITY_AND_RECORDING.md](./docs/JITSI_SECURITY_AND_RECORDING.md)** for setup.

## 📞 API Endpoints

### 1:1 calls

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/calls/create` | POST | Create call (body: `user_id`, `is_video_call`). Returns 409 if recipient is busy. |
| `/api/v1/calls/create-embedded` | POST | Create embedded call for web (session auth). |
| `/api/v1/calls/<call_id>/respond` | POST | Accept or decline (body: `response=accept` or `response=decline`). |
| `/api/v1/calls/<call_id>/end` | POST | End call (either party; ends for both in 1:1). Idempotent. |
| `/api/v1/calls/<call_id>/cancel` | POST | Caller cancels before answer. |
| `/api/v1/calls/<call_id>/status` | GET | Get current call state. |
| `/api/v1/calls/history` | GET | Get user's call history. |
| `/api/v1/calls/acknowledge` | POST | Receiver acknowledges (ringing). Body: `call_id`. |
| `/api/v1/calls/heartbeat` | POST | Keep-alive during active call. Body: `call_id`. |

### Group calls

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/calls/group/create` | POST | Create group call. |
| `/api/v1/calls/group/<call_id>/invite` | POST | Invite users. |
| `/api/v1/calls/group/<call_id>/join` | POST | Join call. |
| `/api/v1/calls/group/<call_id>/leave` | POST | Leave (does not end for others). |
| `/api/v1/calls/group/<call_id>/decline` | POST | Decline invitation. |
| `/api/v1/calls/group/<call_id>/end` | POST | End for all (host only). |
| `/api/v1/calls/group/<call_id>/status` | GET | Get call and participant info. |
| `/api/v1/calls/group/<call_id>/participants` | GET | List participants. |

### Web

| Path | Description |
|------|-------------|
| `/calls/embed/<call_id>` | Embedded Jitsi call interface (session auth). |
| `/calls/script` | JavaScript for embedded calls. |

## 🧪 Testing

### Test Embedded Call Creation

```bash
curl -X POST "http://localhost:9991/api/v1/calls/create-embedded" \
  -u "caller@example.com:api-key" \
  -d "user_id=RECIPIENT_USER_ID" \
  -d "is_video_call=true"
```

Response includes `embedded_url` for the call interface. The web UI resolves the recipient from the compose context and passes `user_id`.

### Test Web Interface

1. **Navigate to the Zulip web interface**
2. **Start a new direct message**
3. **Click the video or audio call button**
4. **Call window opens embedded in your domain**

### Test Complete Call Flow

```bash
# 1. Create call (recipient busy → 409)
curl -X POST "http://localhost:9991/api/v1/calls/create" \
  -u "caller@example.com:api-key" \
  -d "user_id=RECIPIENT_USER_ID" \
  -d "is_video_call=true"

# 2. Receiver acknowledges (ringing)
curl -X POST "http://localhost:9991/api/v1/calls/acknowledge" \
  -u "recipient@example.com:api-key" \
  -d "call_id=CALL_ID"

# 3. Accept or decline
curl -X POST "http://localhost:9991/api/v1/calls/CALL_ID/respond" \
  -u "recipient@example.com:api-key" \
  -d "response=accept"

# 4. End call (either participant)
curl -X POST "http://localhost:9991/api/v1/calls/CALL_ID/end" \
  -u "user@example.com:api-key"

# Call history
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

## 📱 Flutter / Mobile Integration

For a WhatsApp-like calling experience (full-screen incoming, Jitsi SDK, CallKit/ConnectionService, edge cases), use the canonical guide:

📖 **[docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md](./docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md)** — API reference, event `op` names, push payloads, state machine, UX patterns, and Dart examples.

Summary for mobile clients:

- **Create call**: `POST /api/v1/calls/create` (body: `user_id`, `is_video_call`). Busy → 409.
- **Respond**: `POST /api/v1/calls/<call_id>/respond` with `response=accept` or `response=decline`.
- **End**: `POST /api/v1/calls/<call_id>/end` (either party; 1:1 ends for both).
- **Acknowledge**: `POST /api/v1/calls/acknowledge` (body: `call_id`) when phone starts ringing.
- **Heartbeat**: `POST /api/v1/calls/heartbeat` (body: `call_id`) every ~30s during active call.

Real-time events (Zulip event queue, `type: "call"`): `initiated`, `incoming_call`, `ringing`, `accepted`, `declined`, `ended`, `cancelled`, `missed`. Payloads include `sender`, `receiver`, and `avatar_url`.

## 📊 Database Schema

### Call Model
- `call_id`: UUID primary key
- `call_type`: "video" or "audio"
- `state`: Current call state (`calling`, `ringing`, `accepted`, `rejected`, `missed`, `timeout`, `cancelled`, `ended`)
- `sender`: Foreign key to UserProfile
- `receiver`: Foreign key to UserProfile
- `jitsi_room_name`: Jitsi meeting room name
- `jitsi_room_url`: Full Jitsi meeting URL
- `created_at`, `answered_at`, `ended_at`: Timestamps
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

See **[DEVELOPMENT.md](./DEVELOPMENT.md)** for run instructions, feature flags, plugin layout, and doc index.

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

## 📋 Changelog

See **[CHANGELOG.md](./CHANGELOG.md)** for version history and notable changes.

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