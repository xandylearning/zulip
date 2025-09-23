# Fix: KeyError 'user_profile_id' in missedmessage_mobile_notifications queue

## Problem Description

The `missedmessage_mobile_notifications` queue worker was throwing a `KeyError: 'user_profile_id'` when processing `register_push_device_to_bouncer` events during retry failure handling.

### Error Details

```
KeyError: 'user_profile_id'
File "/zerver/worker/missedmessage_mobile_notifications.py", line 63, in failure_processor
    event["user_profile_id"],
```

### Root Cause

The `failure_processor` function in `zerver/worker/missedmessage_mobile_notifications.py` was attempting to access `user_profile_id` directly from the event object (`event["user_profile_id"]`), but for `register_push_device_to_bouncer` events, the `user_profile_id` is nested inside the `payload` object.

### Event Structure Analysis

The queue handles three types of events with different structures:

1. **Regular push notification events** (type: "add"):
   ```python
   {
       "user_profile_id": user_profile_id,
       "message_id": message_id,
       "trigger": "...",
       "type": "add",
       "mentioned_user_group_id": ...
   }
   ```

2. **Remove notification events** (type: "remove"):
   ```python
   {
       "type": "remove",
       "user_profile_id": user_profile_id,
       "message_ids": [...]
   }
   ```

3. **Register push device to bouncer events** (type: "register_push_device_to_bouncer"):
   ```python
   {
       "type": "register_push_device_to_bouncer",
       "payload": {
           "user_profile_id": user_profile_id,
           "bouncer_public_key": "...",
           "encrypted_push_registration": "...",
           "push_account_id": ...
       }
   }
   ```

## Solution

### Code Changes

**File**: `zerver/worker/missedmessage_mobile_notifications.py`

**Before**:
```python
def failure_processor(event: dict[str, Any]) -> None:
    logger.warning(
        "Maximum retries exceeded for trigger:%s event:push_notification",
        event["user_profile_id"],
    )
```

**After**:
```python
def failure_processor(event: dict[str, Any]) -> None:
    # For register_push_device_to_bouncer events, user_profile_id is in payload
    if event.get("type") == "register_push_device_to_bouncer":
        user_profile_id = event["payload"]["user_profile_id"]
    else:
        # For other events (like push notifications), user_profile_id is at top level
        user_profile_id = event["user_profile_id"]
    
    logger.warning(
        "Maximum retries exceeded for trigger:%s event:push_notification",
        user_profile_id,
    )
```

### Implementation Details

1. **Conditional Access**: Added a check for the event type to determine the correct location of `user_profile_id`
2. **Backward Compatibility**: Maintains support for existing event types ("add" and "remove")
3. **Error Prevention**: Prevents KeyError exceptions during retry failure logging

## Deployment Steps

1. **Deploy the fix** to the production environment
2. **Restart queue workers** to ensure they pick up the updated code:
   ```bash
   sudo supervisorctl restart zulip_events_missedmessage_mobile_notifications
   ```
3. **Monitor logs** to verify the fix is working:
   ```bash
   tail -f /var/log/zulip/workers.log | grep "missedmessage_mobile_notifications"
   ```

## Testing

### Manual Testing

1. **Trigger a push device registration** that will fail (e.g., with invalid bouncer credentials)
2. **Verify retry behavior** - the worker should retry the failed registration
3. **Check failure logging** - when retries are exhausted, the warning should log the correct `user_profile_id` without throwing a KeyError

### Test Cases

- [ ] `register_push_device_to_bouncer` events with retry failures
- [ ] Regular push notification events (`type: "add"`)
- [ ] Remove notification events (`type: "remove"`)
- [ ] Mixed event types in the same queue

## Related Issues

- **Underlying Issue**: The 500 error from the push notification bouncer should be investigated separately
- **Bouncer Configuration**: Verify push notification bouncer credentials and connectivity
- **Network Issues**: Check for network connectivity problems between the server and bouncer

## Prevention

To prevent similar issues in the future:

1. **Event Structure Documentation**: Document the structure of all event types handled by each queue
2. **Type Safety**: Consider using TypedDict or similar for better type checking
3. **Unit Tests**: Add comprehensive tests for all event types and failure scenarios
4. **Code Review**: Ensure reviewers understand the different event structures when modifying queue workers

## Files Modified

- `zerver/worker/missedmessage_mobile_notifications.py` - Fixed KeyError in failure_processor

## References

- [Zulip Queuing System Documentation](https://zulip.readthedocs.io/en/latest/subsystems/queuing.html)
- [Push Notifications Documentation](https://zulip.readthedocs.io/en/latest/subsystems/notifications.html)
