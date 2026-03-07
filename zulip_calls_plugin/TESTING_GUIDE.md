# 🧪 Zulip Calls Plugin - Testing Guide

This guide helps you test embedded and API call functionality in a development environment. For recent behavior changes, see [CHANGELOG.md](./CHANGELOG.md).

## 🚀 Quick Start Testing

### 1. Install the Plugin

```bash
# Install the plugin
python manage.py install_calls_plugin

# Start your development server
./tools/run-dev
```

### 2. Enable JavaScript Loading

Add this to any Zulip template (e.g., `templates/zerver/app.html`) before the closing `</body>` tag:

```html
<!-- Load embedded calls functionality -->
<script>
fetch('/calls/script')
    .then(response => response.text())
    .then(html => {
        document.head.insertAdjacentHTML('beforeend', html);
    })
    .catch(err => console.log('Embedded calls not available'));
</script>
```

### 3. Test in Web Browser

1. **Open Zulip** in your browser: `http://localhost:9991`
2. **Login** with your development account
3. **Start a direct message** with another user
4. **Click the video call button** (📹) or **audio call button** (🎤)
5. **Watch the embedded call window open!** 🎉

## 🔧 Detailed Testing Steps

### Test 1: Basic Call Creation

The API expects `user_id` (recipient's Zulip user ID). In the web UI, the compose context supplies this when you start a DM and click call.

```bash
# Replace OTHELLO_USER_ID with the recipient's user ID (e.g. from /api/v1/users)
curl -X POST "http://localhost:9991/api/v1/calls/create-embedded" \
  -u "hamlet@zulip.com:your-api-key" \
  -d "user_id=OTHELLO_USER_ID" \
  -d "is_video_call=true"
```

**Expected Response:**
```json
{
  "result": "success",
  "call_id": "uuid-here",
  "embedded_url": "/calls/embed/uuid-here",
  "call_type": "video",
  "room_name": "zulip-call-abc123",
  "recipient": { "user_id": 123, "full_name": "Othello", "email": "othello@zulip.com" }
}
```

To test the standard create endpoint (e.g. for mobile): `POST /api/v1/calls/create` with `user_id` and `is_video_call`. If the recipient is in another call, you get **409 Conflict** (no queue).

### Test 2: Embedded Call Interface

1. **Copy the `embedded_url`** from the response above
2. **Open in browser**: `http://localhost:9991/calls/embed/uuid-here`
3. **You should see**: A full Jitsi Meet interface with call controls

### Test 3: Web Button Integration

#### Prerequisites:
- Two Zulip accounts (hamlet and othello)
- Both accounts logged in (use different browsers/incognito)

#### Steps:
1. **User A (hamlet)**:
   - Go to direct messages
   - Select User B (othello) as recipient
   - Click video call button 📹
   - **Call window should open in popup**
   - **Call link should be inserted in compose box**

2. **User B (othello)**:
   - Should receive push notification (if configured)
   - Can click the call link in the message
   - **Should join the same call**

## 🔍 Debugging

### Check JavaScript Console

Open browser dev tools and look for:
```
Embedded calls: Plugin initialized
Embedded calls: Overrode call button handlers
```

### Check Network Requests

When clicking call buttons, you should see:
- `POST /api/v1/calls/create-embedded`
- Response with `embedded_url`

### Check Database

```bash
# Check if calls are being created
python manage.py shell

>>> from zulip_calls_plugin.models import Call
>>> Call.objects.all()
>>> # Should show your test calls
```

### Common Issues

#### "Module not found" errors:
```bash
# Make sure plugin is in INSTALLED_APPS
python manage.py shell
>>> from django.conf import settings
>>> 'zulip_calls_plugin' in settings.INSTALLED_APPS
```

#### Call buttons not overridden:
- Check browser console for JavaScript errors
- Verify `/calls/script` endpoint is accessible
- Make sure JavaScript is loaded after page load

#### Call window not opening:
- Check popup blocker settings
- Verify `/calls/embed/` endpoint works
- Check that call was created successfully

## 📊 Expected Flow

### Successful Call Flow:

1. **Button Click** → JavaScript intercepts
2. **API Call** → `POST /api/v1/calls/create-embedded`
3. **Database Record** → Call and CallEvent created
4. **Window Opens** → Embedded call interface loads
5. **Jitsi Loads** → Video/audio call interface ready
6. **Message Inserted** → Call link added to compose box
7. **Notification** → Success notification shown

### Database Changes:

```sql
-- Check what was created
SELECT * FROM zulip_calls_plugin_call ORDER BY created_at DESC LIMIT 5;
SELECT * FROM zulip_calls_plugin_callevent ORDER BY timestamp DESC LIMIT 10;
```

## 🎯 Success Criteria

✅ **Plugin Installation**: No errors during install
✅ **JavaScript Loading**: Console shows plugin initialized
✅ **Button Override**: Clicking video/audio button opens embedded window
✅ **Call Creation**: API creates call record in database
✅ **Embedded Interface**: Call window loads with Jitsi Meet
✅ **Message Integration**: Call link inserted in compose box
✅ **Multi-user**: Other users can join the same call

## 🛠️ Development notes

- **Feature flags**: `JITSI_JWT_ENABLED` and `CALL_RECORDING_ENABLED` default to `False`. Leave them off in dev unless you have Jitsi/Jibri configured. See [docs/JITSI_SECURITY_AND_RECORDING.md](./docs/JITSI_SECURITY_AND_RECORDING.md).
- **1:1 behavior**: Either party ending the call ends it for both. Use `POST /api/v1/calls/<call_id>/end`.
- **Changelog**: [CHANGELOG.md](./CHANGELOG.md). Doc index: [DOCUMENTATION_INDEX.md](./DOCUMENTATION_INDEX.md).

## 🚀 Next steps

Once basic testing works:

1. **Test with your Jitsi server** (see plugin config `JITSI_SERVER_URL`).
2. **Configure push notifications** for mobile (FCM).
3. **Test call history**: `GET /api/v1/calls/history`.
4. **Test on multiple devices/browsers**.

---

**If you hit issues:** check server logs (`tail -f var/log/zulip.log`), browser console, and the Network tab for failed API calls.