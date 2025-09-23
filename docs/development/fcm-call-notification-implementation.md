# FCM Call Notification Implementation - Fix Documentation

## Overview

This document describes the implementation of FCM (Firebase Cloud Messaging) call notifications in the exact format specified for optimal call notification delivery on Android devices. The implementation ensures that call notifications are delivered reliably to both foreground and background/terminated applications.

## Problem Statement

The original call notification system was using a generic FCM format that may not have been optimized for call notifications. A specific FCM format was required to ensure:

1. **High Priority Delivery**: Call notifications need maximum priority for real-time delivery
2. **Proper Channel Configuration**: Using the correct notification channel (`calls-1`) for call importance
3. **Structured Data Payload**: Consistent data structure for client-side call handling
4. **Cross-platform Compatibility**: Working on both active and terminated Android applications

## Solution

### 1. New FCM Call Notification Functions

#### `create_fcm_call_notification_message()`
**Location**: `zerver/lib/push_notifications.py`

Creates FCM messages in the exact specified format:

```python
def create_fcm_call_notification_message(
    token: str,
    call_data: dict[str, Any],
    realm_host: str,
    realm_url: str,
) -> firebase_messaging.Message:
    """
    Create FCM call notification message in the exact format specified.

    Returns Firebase messaging Message object with:
    - High priority delivery
    - Structured data payload with all required fields
    - Android-specific notification configuration
    - Cross-platform notification block
    """
```

#### `send_fcm_call_notifications()`
**Location**: `zerver/lib/push_notifications.py`

Handles batch sending of FCM call notifications with:

```python
def send_fcm_call_notifications(
    devices: Sequence[DeviceToken],
    call_data: dict[str, Any],
    realm_host: str,
    realm_url: str,
    remote: Optional["RemoteZulipServer"] = None,
) -> int:
    """
    Send FCM call notifications using the specialized call notification format.

    Features:
    - Batch processing for multiple devices
    - Error handling and token cleanup
    - Comprehensive logging
    - Unregistered token removal
    """
```

#### `send_fcm_call_notification()`
**Location**: `zulip_calls_plugin/views/calls.py`

High-level integration function:

```python
def send_fcm_call_notification(recipient: UserProfile, call_data: dict) -> None:
    """
    Send FCM call notification using the specialized call notification format.

    Integrates with the calls plugin to send notifications in the exact format:
    - Extracts FCM devices for the recipient
    - Prepares call data with all required fields
    - Calls the specialized FCM sending function
    """
```

### 2. Exact Format Implementation

The implementation generates FCM notifications in the exact format specified:

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

### 3. Key Format Elements

#### Data Payload
- **`event: "call"`** - Identifies this as a call notification
- **`server`** - Realm hostname for client routing
- **`realm_url`** - Full realm URL for authentication
- **`user_id`** - Recipient user ID
- **`call_id`** - Unique call identifier
- **`sender_id`** - Caller's user ID
- **`sender_full_name`** - Caller's display name
- **`call_type`** - "video" or "audio"
- **`time`** - Unix timestamp of call initiation

#### Android Configuration
- **`priority: "high"`** - Ensures immediate delivery
- **`channel_id: "calls-1"`** - Uses maximum importance notification channel
- **`tag: "call:{call_id}"`** - Unique tag for notification management
- **`sound: "default"`** - Default ringtone
- **`click_action: "android.intent.action.VIEW"`** - Opens app when tapped

#### Cross-platform Notification
- **`title`** - Dynamic title based on call type
- **`body`** - Caller identification

### 4. Integration Points

#### Call Creation Endpoint
**Location**: `zulip_calls_plugin/views/calls.py:create_call()`

```python
# Send legacy push notification (for compatibility)
send_call_push_notification(recipient, push_data)

# Send specialized FCM call notification in exact format specified
fcm_call_data = {
    "call_id": str(call.call_id),
    "sender_id": str(user_profile.id),
    "sender_name": user_profile.full_name,
    "call_type": call.call_type,
    "jitsi_url": participant_url,
}
send_fcm_call_notification(recipient, fcm_call_data)
```

#### Start Call Endpoint
**Location**: `zulip_calls_plugin/views/calls.py:start_call()`

Similar integration ensures both endpoints use the new FCM format.

## Implementation Details

### 1. Backwards Compatibility

The implementation maintains backwards compatibility by:

- **Dual Notifications**: Sending both legacy and new FCM formats
- **Fallback Support**: Legacy system continues to work for older clients
- **Gradual Migration**: New format is additive, not replacing existing functionality

### 2. Error Handling

```python
# Automatic token cleanup for unregistered devices
if isinstance(error, FCMUnregisteredError):
    logger.info(f"FCM Call: Removing unregistered token {token}")
    device = DeviceTokenClass.objects.filter(
        user_id=call_data.get("user_id"), token=token
    ).first()
    if device:
        device.delete()
```

### 3. Logging and Monitoring

Comprehensive logging for debugging and monitoring:

```python
logger.info(f"FCM Call: Sent notification with ID {response.message_id} to {token}")
logger.warning(f"FCM Call: Failed to send to {token}: {error}")
logger.info(f"FCM Call: Successfully sent {successfully_sent_count}/{len(messages)} call notifications")
```

### 4. Device Filtering

Only sends to FCM devices:

```python
fcm_devices = PushDeviceToken.objects.filter(
    user=recipient,
    kind=PushDeviceToken.FCM
)
```

## Testing

### 1. Test Implementation

**Location**: `test_fcm_call_notifications.py`

Comprehensive test suite that verifies:

- **Format Compliance**: All required fields present with correct values
- **Android Configuration**: Proper channel, priority, and notification settings
- **Data Payload**: Correct event type and call information
- **Cross-platform Support**: Both Android and general notification blocks
- **Multiple Call Types**: Video and audio call format verification

### 2. Test Results

```
🎉 ALL TESTS PASSED!
FCM call notifications are working correctly and match the specified format.
```

The test validates:
- ✅ Data payload contains all required fields
- ✅ Android notification configuration is correct
- ✅ Cross-platform notification format is proper
- ✅ Call type variations work (video/audio)
- ✅ All values match expected format

### 3. Running Tests

```bash
# In Vagrant development environment
vagrant ssh
python test_fcm_call_notifications.py
```

## Configuration

### 1. Required Settings

No additional configuration required. The implementation uses existing FCM settings:

- **`PUSH_NOTIFICATION_BOUNCER_URL`** - For remote notifications
- **FCM Service Account** - For Firebase authentication
- **`CALL_PUSH_NOTIFICATION_ENABLED`** - Feature flag (default: True)

### 2. Channel Configuration

The implementation uses the existing `calls-1` notification channel which should be configured in the Android client with:

- **Importance**: Maximum
- **Sound**: Custom ringtone
- **Vibration**: Enabled
- **Lock Screen**: Show all content

## Troubleshooting

### 1. Common Issues

#### Notifications Not Received
**Symptoms**: FCM call notifications not appearing on Android devices

**Possible Causes**:
- FCM service account not configured
- Device token not registered
- Notification channel not properly configured in client
- Device in power saving mode

**Solutions**:
1. Verify FCM configuration in Zulip settings
2. Check device registration: `PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.FCM)`
3. Ensure client app has proper notification channel setup
4. Check Android device settings for app notification permissions

#### Wrong Notification Format
**Symptoms**: Notifications received but in wrong format

**Possible Causes**:
- Client app not handling new FCM format
- Legacy notification system being used instead
- Incorrect data field mapping

**Solutions**:
1. Verify client app processes the `event: "call"` data field
2. Check client handles `calls-1` notification channel
3. Ensure client uses `call_id` from data payload for call management

### 2. Debugging

#### Enable Debug Logging

```python
# In settings.py
LOGGING = {
    'loggers': {
        'zerver.lib.push_notifications': {
            'level': 'DEBUG',
        },
        'zulip_calls_plugin.views.calls': {
            'level': 'DEBUG',
        },
    }
}
```

#### Check FCM Messages

```bash
# Monitor FCM call notification logs
tail -f /var/log/zulip/django.log | grep "FCM Call"

# Check for FCM errors
tail -f /var/log/zulip/errors.log | grep FCM
```

#### Verify Device Registration

```bash
# In Django shell
./manage.py shell

from zerver.models import UserProfile, PushDeviceToken
user = UserProfile.objects.get(email="user@example.com")
fcm_devices = PushDeviceToken.objects.filter(user=user, kind=PushDeviceToken.FCM)
print(f"FCM devices: {fcm_devices.count()}")
for device in fcm_devices:
    print(f"Token: {device.token[:20]}...")
```

### 3. Performance Monitoring

#### Key Metrics to Monitor

- **Success Rate**: Percentage of successfully sent FCM call notifications
- **Response Time**: Time to send batch FCM notifications
- **Token Cleanup**: Rate of unregistered token removal
- **Error Rate**: FCM API errors and failures

#### Log Analysis

```bash
# Count successful FCM call notifications
grep "FCM Call: Sent notification" /var/log/zulip/django.log | wc -l

# Check for FCM errors
grep "FCM Call: Failed" /var/log/zulip/django.log

# Monitor token cleanup
grep "FCM Call: Removing unregistered token" /var/log/zulip/django.log
```

## Security Considerations

### 1. Data Privacy

The FCM call notification includes minimal data:
- **No sensitive content**: Only call metadata and participant information
- **Realm isolation**: Server and realm URL properly scoped to user's realm
- **User consent**: Only sent to users with registered FCM tokens

### 2. Token Management

- **Automatic cleanup**: Unregistered tokens automatically removed
- **Secure storage**: FCM tokens stored securely in database
- **Realm scoping**: Tokens only used within appropriate realm context

## Future Enhancements

### 1. Potential Improvements

- **Rich Notifications**: Add caller avatar and additional call context
- **Action Buttons**: Accept/Decline buttons directly in notification
- **Call Quality**: Include network quality hints for call routing
- **Time-to-Live**: Dynamic TTL based on call urgency

### 2. Client-Side Integration

Clients should be updated to:
- Handle the new `event: "call"` data structure
- Use `call_id` for call state management
- Process `sender_full_name` for caller identification
- Implement proper `calls-1` notification channel

## Conclusion

The FCM call notification implementation successfully delivers call notifications in the exact specified format, ensuring reliable delivery to Android devices in all application states. The implementation maintains backwards compatibility while providing enhanced functionality for modern FCM-capable clients.

**Key Benefits:**
- ✅ Exact format compliance with specification
- ✅ High priority delivery for real-time call notifications
- ✅ Proper notification channel usage
- ✅ Comprehensive error handling and monitoring
- ✅ Backwards compatibility with existing systems
- ✅ Thorough testing and validation

The implementation is production-ready and will improve call notification reliability across the Zulip platform.