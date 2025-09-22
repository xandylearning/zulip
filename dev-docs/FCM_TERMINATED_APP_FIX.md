# FCM Terminated App Notification Fix

## Problem Solved

When the Flutter app is terminated (killed/swiped away), data-only FCM messages won't wake the app or show notifications. This affects incoming call notifications and message notifications.

## Solution Implemented

The fix updates the FCM payload format to include both `data` and `notification` blocks, ensuring notifications show when the app is terminated while maintaining backward compatibility.

## Changes Made

### 1. Updated FCM Message Creation (`zerver/lib/push_notifications.py`)

**Before (Data-only):**
```python
messages = [
    firebase_messaging.Message(
        data=data, 
        token=token, 
        android=firebase_messaging.AndroidConfig(priority=priority)
    )
    for token in token_list
]
```

**After (Data + Notification):**
```python
messages = []
for token in token_list:
    # Determine notification content based on data type
    notification_content = _create_fcm_notification_content(data, options)
    
    # Create Android-specific notification configuration
    android_notification = None
    if notification_content:
        android_notification = firebase_messaging.AndroidNotification(
            title=notification_content.get("title"),
            body=notification_content.get("body"),
            channel_id=notification_content.get("channel_id", "messages-4"),
            sound="default",
            tag=notification_content.get("tag"),
            click_action="android.intent.action.VIEW"
        )
    
    # Create Android config with notification
    android_config = firebase_messaging.AndroidConfig(
        priority=priority,
        notification=android_notification
    )
    
    # Create the message with both data and notification
    message_kwargs = {
        "data": data,
        "token": token,
        "android": android_config
    }
    
    # Add notification block for cross-platform compatibility
    if notification_content:
        message_kwargs["notification"] = firebase_messaging.Notification(
            title=notification_content.get("title"),
            body=notification_content.get("body")
        )
    
    messages.append(firebase_messaging.Message(**message_kwargs))
```

### 2. Added Notification Content Generator

```python
def _create_fcm_notification_content(data: dict[str, Any], options: dict[str, Any]) -> dict[str, Any] | None:
    """Create notification content for FCM messages to support terminated app notifications."""
    event_type = data.get("event") or data.get("type")
    
    if event_type == "call":
        # Call notifications - use calls-1 channel (MAX importance)
        call_type = data.get("call_type", "call")
        sender_name = data.get("sender_full_name", "Someone")
        
        return {
            "title": f"Incoming {call_type} call",
            "body": f"From {sender_name}",
            "channel_id": "calls-1",
            "tag": f"call:{data.get('call_id', 'unknown')}"
        }
    
    elif event_type == "call_response":
        # Call response notifications - use calls-1 channel (MAX importance)
        response = data.get("response", "responded")
        receiver_name = data.get("receiver_name", "Someone")
        
        response_text = "accepted" if response == "accept" else "declined"
        
        return {
            "title": f"Call {response_text}",
            "body": f"{receiver_name} {response_text} your call",
            "channel_id": "calls-1",
            "tag": f"call_response:{data.get('call_id', 'unknown')}"
        }
    
    elif event_type == "message":
        # Message notifications - use messages-4 channel (HIGH importance)
        sender_name = data.get("sender_full_name", "Someone")
        content = data.get("content", "")
        
        # Truncate content for notification
        if len(content) > 100:
            content = content[:97] + "..."
        
        return {
            "title": sender_name,
            "body": content,
            "channel_id": "messages-4"
        }
    
    elif event_type == "remove":
        # Remove notifications don't need to show in terminated state
        return None
    
    else:
        # Default notification for other event types
        return {
            "title": "Zulip",
            "body": "New notification",
            "channel_id": "messages-4"
        }
```

### 3. Updated Call Notification Payloads (`zulip_calls_plugin/views/calls.py`)

**Enhanced call notification data:**
```python
payload_data_to_encrypt = {
    'event': 'call',  # Use 'event' for consistency with FCM notification detection
    'type': 'call',   # Keep 'type' for backward compatibility
    'call_id': call_data.get('call_id'),
    'sender_id': call_data.get('sender_id'),
    'sender_full_name': call_data.get('sender_name'),  # Use 'sender_full_name' for FCM notification
    'sender_name': call_data.get('sender_name'),       # Keep 'sender_name' for backward compatibility
    'sender_avatar_url': f"/avatar/{call_data.get('sender_id')}",
    'call_type': call_data.get('call_type'),
    'jitsi_url': call_data.get('jitsi_url'),
    'timeout_seconds': getattr(settings, 'CALL_NOTIFICATION_TIMEOUT', 120),
    'realm_uri': recipient.realm.url,
    'realm_name': recipient.realm.name,
    'realm_url': recipient.realm.url,
    'server': recipient.realm.host,  # Add server info for FCM
    'user_id': str(recipient.id),    # Add user ID for FCM
    'time': str(int(timezone.now().timestamp())),  # Add timestamp for FCM
}
```

### 4. Enhanced Message Notification Payloads

**Added additional fields for terminated app FCM support:**
```python
data.update(
    time=datetime_to_timestamp(message.date_sent),
    content=content,
    sender_full_name=sender_name,
    sender_avatar_url=sender_avatar_url,
    # Add additional fields for terminated app FCM support
    server=user_profile.realm.host,
    user_id=str(user_profile.id),
    realm_url=user_profile.realm.url,
)
```

## FCM Payload Format

### For Call Notifications

```json
{
  "to": "<device_fcm_token>",
  "priority": "high",
  "data": {
    "event": "call",
    "server": "your-org.example.com",
    "realm_url": "https://your-org.example.com",
    "user_id": "123",
    "call_id": "abc123",
    "sender_id": "456",
    "sender_full_name": "Alice",
    "call_type": "video",
    "time": "1726930000"
  },
  "android": {
    "priority": "high",
    "notification": {
      "channel_id": "calls-1",
      "tag": "call:abc123",
      "title": "Incoming video call",
      "body": "From Alice",
      "sound": "default",
      "click_action": "android.intent.action.VIEW"
    }
  },
  "notification": {
    "title": "Incoming video call",
    "body": "From Alice"
  }
}
```

### For Message Notifications

```json
{
  "to": "<device_fcm_token>",
  "priority": "high",
  "data": {
    "event": "message",
    "server": "your-org.example.com",
    "realm_url": "https://your-org.example.com",
    "user_id": "123",
    "zulip_message_id": "789",
    "sender_id": "456",
    "sender_full_name": "Alice",
    "content": "Hello there!",
    "time": "1726930000"
  },
  "android": {
    "priority": "high",
    "notification": {
      "channel_id": "messages-4",
      "title": "Alice",
      "body": "Hello there!",
      "sound": "default",
      "click_action": "android.intent.action.VIEW"
    }
  },
  "notification": {
    "title": "Alice",
    "body": "Hello there!"
  }
}
```

## Key Features

### 1. **Dual Block Support**
- **`data` block**: Contains all the app-specific data for processing when app is running
- **`notification` block**: Shows system notification when app is terminated
- **`android.notification` block**: Android-specific configuration with proper channel IDs

### 2. **Proper Channel Configuration**
- **`calls-1`**: For call notifications (MAX importance, full-screen intent)
- **`messages-4`**: For message notifications (HIGH importance)

### 3. **Notification Tags**
- **Call notifications**: `call:{call_id}` for proper notification management
- **Call response notifications**: `call_response:{call_id}` for response tracking

### 4. **High Priority Delivery**
- All notifications use `priority: "high"` for reliable delivery when app is terminated

## Behavior

### App Running
- Dart `onBackgroundMessage` handler processes the `data` payload
- Shows rich notifications with full context
- Maintains existing functionality

### App Terminated
- System shows the notification from the `notification` payload
- User can tap to launch the app
- For calls: System shows notification with full-screen intent, immediately launches call UI

### App Terminated + Call
- System shows notification with full-screen intent
- Immediately launches call UI for urgent call handling

## Android Channel Configuration

### calls-1 Channel (MAX Importance)
```json
{
  "name": "Calls",
  "description": "Incoming call notifications",
  "importance": "MAX",
  "sound": "default",
  "vibration": true,
  "lights": true,
  "bypass_dnd": true,
  "full_screen_intent": true
}
```

### messages-4 Channel (HIGH Importance)
```json
{
  "name": "Messages",
  "description": "New message notifications",
  "importance": "HIGH",
  "sound": "default",
  "vibration": true,
  "lights": true,
  "bypass_dnd": false,
  "full_screen_intent": false
}
```

## Testing

To test terminated app notifications:

1. **Kill the app completely** (swipe away from recent apps)
2. **Send FCM** with the payload format above
3. **Notification should appear** in system tray
4. **Tapping should launch** the app to the correct screen

## iOS Considerations

For iOS, you need:
- Standard APNs alert notifications (will show when app is terminated)
- For true "phone call" behavior when terminated, implement PushKit VoIP + CallKit (separate from FCM)

## Backward Compatibility

The fix maintains full backward compatibility:
- Existing data-only notifications continue to work
- New notification blocks are added without breaking existing functionality
- Both `event` and `type` fields are supported for different client versions

## Files Modified

1. **`zerver/lib/push_notifications.py`**
   - Updated `send_android_push_notification()` function
   - Added `_create_fcm_notification_content()` helper function
   - Enhanced message payload generation

2. **`zulip_calls_plugin/views/calls.py`**
   - Updated call notification payloads
   - Added FCM-specific fields for terminated app support

## Summary

This fix ensures that FCM notifications work reliably when the Flutter app is terminated, providing a seamless user experience for both call and message notifications while maintaining full backward compatibility with existing implementations.
