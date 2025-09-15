# 🧪 Zulip Calls Plugin - Testing Guide

This guide will help you test the embedded call functionality in your development environment.

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

```bash
# Test the embedded call API directly
curl -X POST "http://localhost:9991/api/v1/calls/create-embedded" \
  -u "hamlet@zulip.com:your-api-key" \
  -d "recipient_email=othello@zulip.com" \
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
  "recipient": {
    "user_id": 123,
    "full_name": "Othello",
    "email": "othello@zulip.com"
  }
}
```

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

## 🚀 Next Steps

Once basic testing works:

1. **Test with real Jitsi server** (not meet.jit.si)
2. **Configure push notifications** for mobile alerts
3. **Test call history** functionality
4. **Test on multiple devices/browsers**
5. **Performance testing** with multiple concurrent calls

---

**Happy Testing! 🎉📞**

If you encounter issues, check:
- Server logs: `tail -f var/log/zulip.log`
- Browser console for JavaScript errors
- Network tab in dev tools for API call failures