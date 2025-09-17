# Zulip Calls Plugin - Error Fixes Documentation

## Overview

This document describes the fixes implemented to resolve the errors found in the Zulip calls plugin error logs:

## ✅ FIXED: Realm.uri AttributeError (2025-09-17)

### Problem
The Zulip Calls plugin was experiencing runtime errors due to accessing a non-existent `uri` attribute on the `Realm` model:

```
2025-09-17 12:46:06.621 ERR [zulip_calls_plugin.views.calls] Failed to send call push notification: 'Realm' object has no attribute 'uri'
```

### Root Cause
The code was using `recipient.realm.uri` and `user_profile.realm.uri`, but the Zulip `Realm` model does not have a `uri` attribute. The correct attribute is `url`.

### Solution
**Fixed in:** `zulip_calls_plugin/views/calls.py`

**Changed from:**
```python
'realm_uri': recipient.realm.uri,
'realm_url': recipient.realm.uri,
```

**Changed to:**
```python
'realm_uri': recipient.realm.url,
'realm_url': recipient.realm.url,
```

### Technical Details

**Realm Model Properties:**
- ✅ `realm.url` - Returns the full URL (e.g., "https://example.zulipchat.com")
- ❌ `realm.uri` - Does not exist (deprecated)
- ✅ `realm.host` - Returns the host part (e.g., "example.zulipchat.com")
- ✅ `realm.subdomain` - Returns the subdomain (e.g., "example")

**Prevention Note:**
When working with Realm URLs in Zulip plugins, always use `realm.url` for the complete URL.

---

1. **Push Notification Errors**: Fixed incorrect API usage
2. **"You are currently in another call" Errors**: Implemented automatic cleanup
3. **Call Timeout Issues**: Added timeout mechanisms
4. **Manual Call Management**: Added endpoints for manual intervention

## Fixed Issues

### 1. Push Notification API Errors

**Problem**: 
```
Failed to send call push notification: send_android_push_notification() missing 2 required positional arguments: 'data' and 'options'
```

**Root Cause**: The plugin was calling `send_android_push_notification()` with incorrect arguments.

**Solution**: 
- Updated to use Zulip's proper `send_push_notifications()` API
- Fixed function signatures in `send_call_push_notification()` and `send_call_response_notification()`
- Added proper realm information to notification payloads

**Files Modified**:
- `zulip_calls_plugin/views/calls.py` (lines 44-91)

### 2. Stale Call State Management

**Problem**: 
```
Error starting call: You are currently in another call
```

**Root Cause**: Calls stuck in active states (`calling`, `ringing`, `accepted`) without automatic cleanup.

**Solution**: 
- Added `cleanup_stale_calls()` function to automatically timeout old calls
- Added `check_and_cleanup_user_calls()` to clean up before new call attempts
- Integrated cleanup into the `start_call()` function
- Added configurable timeout via `CALL_TIMEOUT_MINUTES` setting (default: 30 minutes)

**Files Modified**:
- `zulip_calls_plugin/views/calls.py` (lines 101-187, 1400-1402)

### 3. Call Timeout Mechanism

**Problem**: No automatic timeout for unanswered calls.

**Solution**:
- Implemented automatic timeout after configurable period
- Calls in `calling`, `ringing`, or `accepted` states are marked as `timeout` after 30 minutes
- Added `CallEvent` records for timeout tracking
- Enhanced management command for cleanup

**Files Modified**:
- `zulip_calls_plugin/views/calls.py` (lines 101-137)
- `zulip_calls_plugin/management/commands/cleanup_calls.py`

### 4. Manual Call Management

**Problem**: No way to manually end stuck calls.

**Solution**: Added new API endpoints:

#### New API Endpoints

1. **End Specific Call**: `POST /api/v1/calls/end`
   - Parameters: `call_id`
   - Ends a specific call by ID

2. **End All User Calls**: `POST /api/v1/calls/end-all`
   - Ends all active calls for the current user

3. **Get Active Calls**: `GET /api/v1/calls/active`
   - Returns all active calls for the current user

4. **Cleanup Stale Calls**: `POST /api/v1/calls/cleanup`
   - Admin-only endpoint to manually trigger cleanup
   - Requires realm admin privileges

**Files Modified**:
- `zulip_calls_plugin/views/calls.py` (lines 1604-1741)
- `zulip_calls_plugin/urls/calls.py` (lines 53-56)

## Configuration Settings

Add these settings to your Django settings for customization:

```python
# Call timeout in minutes (default: 30)
CALL_TIMEOUT_MINUTES = 30

# Enable/disable push notifications (default: True)
CALL_PUSH_NOTIFICATION_ENABLED = True

# Call notification timeout in seconds (default: 120)
CALL_NOTIFICATION_TIMEOUT = 120
```

## Usage Examples

### 1. Manual Call Cleanup

```bash
# Run the management command
python manage.py cleanup_calls

# With custom timeout
python manage.py cleanup_calls --timeout-minutes 15

# Also cleanup old ended calls
python manage.py cleanup_calls --cleanup-old-calls --old-calls-days 7
```

### 2. API Usage

```bash
# End a specific call
curl -X POST /api/v1/calls/end \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d "call_id=123e4567-e89b-12d3-a456-426614174000"

# End all user calls
curl -X POST /api/v1/calls/end-all \
  -H "Authorization: Bearer YOUR_API_KEY"

# Get active calls
curl -X GET /api/v1/calls/active \
  -H "Authorization: Bearer YOUR_API_KEY"

# Cleanup stale calls (admin only)
curl -X POST /api/v1/calls/cleanup \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 3. Automatic Cleanup

The system now automatically:
- Cleans up stale calls before starting new calls
- Times out calls after 30 minutes of inactivity
- Creates proper event logs for all call state changes

## Testing

Run the test script to verify fixes:

```bash
cd /path/to/zulip
python zulip_calls_plugin/test_fixes.py
```

## Monitoring

Monitor the following logs for call-related activity:

```bash
# Check for call errors
grep -i "calls\|plugin" /var/log/zulip/errors.log | tail -20

# Check for successful call operations
grep -i "call.*success\|call.*started\|call.*ended" /var/log/zulip/errors.log
```

## Migration Notes

- No database migrations required
- Existing call records will be automatically cleaned up
- New API endpoints are backward compatible
- Push notification format has been updated but is backward compatible

## Troubleshooting

### If you still see "You are currently in another call" errors:

1. Check for very recent calls that might not be stale yet:
   ```sql
   SELECT * FROM zulip_calls_plugin_call 
   WHERE state IN ('calling', 'ringing', 'accepted') 
   ORDER BY created_at DESC;
   ```

2. Manually end stuck calls:
   ```bash
   curl -X POST /api/v1/calls/end-all \
     -H "Authorization: Bearer YOUR_API_KEY"
   ```

3. Run cleanup command:
   ```bash
   python manage.py cleanup_calls --timeout-minutes 1
   ```

### If push notifications still fail:

1. Verify the Zulip push notification system is working
2. Check that `CALL_PUSH_NOTIFICATION_ENABLED = True` in settings
3. Ensure proper FCM/APNS credentials are configured

## Future Improvements

1. **Real-time Event Integration**: Integrate with Zulip's real-time event system
2. **Call Analytics**: Add call duration and quality metrics
3. **Advanced Timeout Logic**: Different timeouts for different call states
4. **Call Recording**: Optional call recording functionality
5. **Multi-party Calls**: Support for group calls

## Support

For issues or questions:
1. Check the error logs first
2. Run the test script to verify functionality
3. Use the new API endpoints for manual intervention
4. Review this documentation for configuration options
