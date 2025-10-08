# Bug Fix: Database Field Name Mismatch

## Issue
```
CallApiException(500): Failed to create call: Cannot resolve keyword 'initiator' into field. 
Choices are: sender, receiver, ...
```

## Root Cause
The `Call` model uses `sender` and `receiver` as the actual database fields:

```python
# models/calls.py
class Call(models.Model):
    sender = models.ForeignKey(UserProfile, ...)   # Actual DB field
    receiver = models.ForeignKey(UserProfile, ...) # Actual DB field
    
    # Properties for backward compatibility (NOT queryable)
    @property
    def initiator(self):
        return self.sender
    
    @property
    def recipient(self):
        return self.receiver
```

**The Problem:** Django ORM queries **cannot use `@property` fields** - they require actual database field names.

## What Was Fixed

### ❌ Before (Incorrect - using properties in queries)
```python
# This FAILS because 'initiator' and 'recipient' are @property, not database fields
Call.objects.filter(
    models.Q(initiator=user_profile, recipient=recipient) |
    models.Q(initiator=recipient, recipient=user_profile)
)

Call.objects.create(
    initiator=user_profile,  # ❌ Wrong field name
    recipient=recipient,     # ❌ Wrong field name
)
```

### ✅ After (Correct - using actual database fields)
```python
# This WORKS because 'sender' and 'receiver' are actual database fields
Call.objects.filter(
    models.Q(sender=user_profile, receiver=recipient) |
    models.Q(sender=recipient, receiver=user_profile)
)

Call.objects.create(
    sender=user_profile,    # ✅ Correct field name
    receiver=recipient,     # ✅ Correct field name
)
```

## Files Changed

### `/Users/straxs/Work/zulip/zulip_calls_plugin/views/calls.py`

**Line 643-645:** Fixed existing call check in `create_call()`
```python
# Before
existing_call = Call.objects.filter(
    models.Q(initiator=user_profile, recipient=recipient) |
    models.Q(initiator=recipient, recipient=user_profile),
    state__in=["initiated", "ringing", "active"]
)

# After
existing_call = Call.objects.filter(
    models.Q(sender=user_profile, receiver=recipient) |
    models.Q(sender=recipient, receiver=user_profile),
    state__in=["initiated", "ringing", "active"]
)
```

**Line 656-660:** Fixed call creation in `create_call()`
```python
# Before
call = Call.objects.create(
    call_type="video" if is_video_call else "audio",
    initiator=user_profile,
    recipient=recipient,
    ...
)

# After
call = Call.objects.create(
    call_type="video" if is_video_call else "audio",
    sender=user_profile,
    receiver=recipient,
    ...
)
```

**Line 966-968:** Fixed call history query in `get_call_history()`
```python
# Before
calls = Call.objects.filter(
    models.Q(initiator=user_profile) | models.Q(recipient=user_profile),
    realm=user_profile.realm
)

# After
calls = Call.objects.filter(
    models.Q(sender=user_profile) | models.Q(receiver=user_profile),
    realm=user_profile.realm
)
```

**Line 973:** Fixed other_user lookup in `get_call_history()`
```python
# Before
other_user = call.recipient if call.initiator.id == user_profile.id else call.initiator

# After
other_user = call.receiver if call.sender.id == user_profile.id else call.sender
```

**Line 979:** Fixed was_initiator field
```python
# Before
"was_initiator": call.initiator.id == user_profile.id,

# After
"was_initiator": call.sender.id == user_profile.id,
```

## What Was NOT Changed

Property access (reading values) works fine and was left unchanged:

```python
# These are OK - reading properties works fine
if call.initiator.id != user_profile.id:  # ✅ OK
    ...

send_notification(call.recipient, data)    # ✅ OK

response = {
    "initiator": {                         # ✅ OK
        "user_id": call.initiator.id,     # ✅ OK
        "full_name": call.initiator.full_name,
    },
    "recipient": {                         # ✅ OK
        "user_id": call.recipient.id,     # ✅ OK
    }
}
```

## Testing

After this fix, the following should work:

```bash
# Create a call
curl -X POST "https://dev.zulip.xandylearning.in/api/v1/calls/create" \
  -u "user@example.com:api_key" \
  -d "recipient_email=recipient@example.com" \
  -d "is_video_call=true"

# Should return 200 with call_id and call_url
```

## Key Takeaway

**Django ORM Rule:** 
- ✅ Use actual database field names (`sender`, `receiver`) in queries
- ✅ Properties (`initiator`, `recipient`) can only be used for reading values
- ❌ Properties cannot be used in `.filter()`, `.create()`, `.update()`, etc.

## Status
🟢 **FIXED** - All database queries now use correct field names (`sender`/`receiver`)
