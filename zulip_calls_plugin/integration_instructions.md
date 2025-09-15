# Zulip Calls Plugin Integration Instructions

## Problem Fixed
The Zulip calls plugin now creates meetings in the background and redirects users directly to the meeting instead of just generating links in the compose box.

## How it Works

### Backend Changes
1. **Enhanced API endpoint**: `/api/v1/calls/create-embedded` now supports `redirect_to_meeting=true` parameter
2. **Direct meeting creation**: Creates Jitsi meeting rooms in background with proper database tracking
3. **Immediate redirect**: Returns Jitsi URL for immediate redirect to meeting

### Frontend Integration
The plugin provides JavaScript that overrides Zulip's default call button behavior:

1. **Call Override Script**: `/calls/override.js` - Serves JavaScript that replaces default call functionality
2. **Enhanced recipient detection**: Smart detection of recipients from compose context
3. **Direct meeting launch**: Opens Jitsi meeting in new window/tab immediately

## Integration Options

### Option 1: Manual Script Loading (Quick Test)
Add this script tag to Zulip's main template or run in browser console:

```html
<script src="/calls/override.js"></script>
```

### Option 2: Browser Console Testing
1. Open Zulip in browser
2. Open Developer Console
3. Paste and run:

```javascript
// Load the calls override script
fetch('/calls/override.js')
  .then(response => response.text())
  .then(script => {
    eval(script);
    console.log('Zulip Calls Plugin loaded successfully');
  })
  .catch(err => console.error('Failed to load calls plugin:', err));
```

### Option 3: Template Integration (Permanent)
Add to Zulip's base template (templates/zerver/app/index.html):

```html
<!-- Before closing </body> tag -->
<script>
// Load Zulip Calls Plugin
(function() {
    if (typeof $ !== 'undefined') {
        $.getScript('/calls/override.js');
    } else {
        setTimeout(arguments.callee, 100);
    }
})();
</script>
```

## How to Test

### Prerequisites
1. Start Zulip development server: `./tools/run-dev`
2. Navigate to a direct message conversation
3. Load the calls plugin script (using one of the options above)

### Testing Steps
1. **Start a direct message** with another user
2. **Click the video call or audio call button** in the compose box
3. **Expected behavior**:
   - Meeting is created in background
   - Jitsi meeting opens in new window/tab immediately
   - Compose box gets a "Join [video/audio] call" link
   - Success notification appears

### Previous vs New Behavior

**Before (Issue):**
- Click call button → Just inserts link in compose box
- User must send message and click link to join
- No meeting tracking

**After (Fixed):**
- Click call button → Meeting created immediately
- Jitsi opens in new window automatically
- Call tracked in database
- Link still inserted for sharing

## API Endpoints

### Create Embedded Call
```
POST /api/v1/calls/create-embedded
Content-Type: application/x-www-form-urlencoded

recipient_email=user@example.com
is_video_call=true
redirect_to_meeting=true
```

**Response:**
```json
{
  "result": "success",
  "call_id": "12345",
  "action": "redirect",
  "redirect_url": "https://meet.jit.si/zulip-call-abc123",
  "recipient": {
    "full_name": "John Doe",
    "email": "user@example.com"
  }
}
```

## Troubleshooting

### Script Not Loading
- Check `/calls/override.js` endpoint is accessible
- Verify CSRF token is available
- Check browser console for errors

### Recipient Not Found
- Ensure you're in a direct message conversation
- Plugin only works for DM calls, not channel calls
- Check that recipient email detection is working

### Meeting Not Opening
- Check popup blocker settings
- Verify Jitsi server URL is accessible
- Check network connectivity

## Files Modified

### Backend
- `zulip_calls_plugin/views/calls.py` - Enhanced create_embedded_call endpoint
- `zulip_calls_plugin/urls/calls.py` - Added override.js endpoint
- `zulip_calls_plugin/static/js/calls_override.js` - Main integration script

### Frontend Integration
- JavaScript that overrides `compose_call_ui.generate_and_insert_audio_or_video_call_link`
- Smart recipient detection from multiple sources
- Direct API calls to create meetings