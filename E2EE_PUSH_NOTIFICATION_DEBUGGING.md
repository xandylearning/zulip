# E2EE Push Notification Debugging Guide

## Problem Description

The server was showing "Skipping E2EE push notifications for user 8 because there are no registered devices" even though the Flutter app logs showed successful E2EE device registration. This indicated a disconnect between client registration and server recognition of E2EE devices.

## Root Cause Analysis

### Initial Issue: Missing Encryption Keys
- **Problem**: `PUSH_REGISTRATION_ENCRYPTION_KEYS` was not configured
- **Impact**: Queue worker couldn't decrypt client registration data
- **Result**: PushDevice records stuck with `bouncer_device_id=None` (status: "pending")

### Secondary Issue: Bouncer Service 500 Errors
- **Problem**: Push notification bouncer service returning 500 errors
- **Impact**: E2EE device registration failing at bouncer level
- **Result**: Devices remain in "pending" state indefinitely

## Debugging Steps Performed

### 1. Server Configuration Check
```bash
python3 manage.py shell -c "
from django.conf import settings
print(f'PUSH_REGISTRATION_ENCRYPTION_KEYS configured: {bool(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS)}')
print(f'ZULIP_SERVICE_PUSH_NOTIFICATIONS: {settings.ZULIP_SERVICE_PUSH_NOTIFICATIONS}')
print(f'ZULIP_SERVICES_URL: {settings.ZULIP_SERVICES_URL}')
"
```

**Result**: `PUSH_REGISTRATION_ENCRYPTION_KEYS` was `False`

### 2. Database State Analysis
```bash
python3 manage.py shell -c "
from zerver.models import PushDevice, PushDeviceToken
from zerver.models.users import UserProfile

user = UserProfile.objects.get(id=8)
push_devices = PushDevice.objects.filter(user=user)
push_tokens = PushDeviceToken.objects.filter(user=user)

print(f'PushDevice records: {push_devices.count()}')
for device in push_devices:
    print(f'  - ID: {device.id}, bouncer_device_id: {device.bouncer_device_id}, status: {device.status}')
"
```

**Result**: 
- 2 PushDevice records with `bouncer_device_id=None`
- 3 PushDeviceToken records (legacy tokens)
- Status: "pending"

### 3. Server Version and Feature Level Verification
- **Server Version**: Zulip 12.0-dev (supports E2EE - feature level 425 > 413)
- **E2EE Support**: ✅ Available since Zulip 11.0 (feature level 413)

### 4. Queue Worker Status Check
```bash
ps aux | grep "missedmessage_mobile_notifications"
```

**Result**: Queue worker running (process 2740419)

### 5. Error Log Analysis
```bash
tail -50 /var/log/zulip/errors.log | grep -i "push\|e2ee\|bouncer"
```

**Result**: 
```
zerver.lib.remote_server.PushNotificationBouncerRetryLaterError: Received 500 from push notification bouncer
```

## Solutions Implemented

### 1. Generate and Configure Encryption Keys

**Generate Keys**:
```bash
python3 -c "
import secrets
import base64

public_key = base64.b64encode(secrets.token_bytes(32)).decode('ascii')
private_key = base64.b64encode(secrets.token_bytes(32)).decode('ascii')

print('Generated encryption keys:')
print(f'Public key: {public_key}')
print(f'Private key: {private_key}')
print()
print('Add this line to /etc/zulip/zulip-secrets.conf:')
print(f'push_registration_encryption_keys = {{\"{public_key}\": \"{private_key}\"}}')
"
```

**Add to Secrets File**:
```bash
sudo bash -c 'echo "push_registration_encryption_keys = {\"b0CPSEBkJyS+yaS5wqaEICJTKk3pxNqCCoRfsP1cTcg=\": \"tnqT8vsHisKX1Fo/Td0JkcEavoJljlc1tm/ILrqjlv8=\"}" >> /etc/zulip/zulip-secrets.conf'
```

### 2. Restart Server
```bash
./scripts/restart-server
```

### 3. Re-register Server with Bouncer
```bash
python3 manage.py register_server --agree-to-terms-of-service
```

### 4. Clear Pending Registrations
```bash
python3 manage.py shell -c "
from zerver.models import PushDevice
from zerver.models.users import UserProfile

user = UserProfile.objects.get(id=8)
pending_devices = PushDevice.objects.filter(user=user, bouncer_device_id__isnull=True)
count = pending_devices.count()
pending_devices.delete()
print(f'Cleared {count} pending E2EE device registrations')
"
```

## Current Status

### ✅ Resolved Issues
1. **Encryption Keys**: Properly configured
2. **Server Registration**: Successfully re-registered with bouncer
3. **Queue Workers**: Running and processing events

### ❌ Remaining Issues
1. **Bouncer 500 Errors**: Push notification bouncer service returning 500 errors
2. **E2EE Registration**: Still failing at bouncer level
3. **Device Status**: Remains "pending" indefinitely

## Verification Commands

### Check Encryption Keys
```bash
python3 manage.py shell -c "
from django.conf import settings
print(f'PUSH_REGISTRATION_ENCRYPTION_KEYS configured: {bool(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS)}')
if settings.PUSH_REGISTRATION_ENCRYPTION_KEYS:
    print(f'Number of keys: {len(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS)}')
"
```

### Check Device Status
```bash
python3 manage.py shell -c "
from zerver.models import PushDevice
from zerver.models.users import UserProfile

user = UserProfile.objects.get(id=8)
devices = PushDevice.objects.filter(user=user)
for device in devices:
    status = '✅ ACTIVE' if device.bouncer_device_id else '⏳ PENDING'
    print(f'Device {device.id}: bouncer_device_id={device.bouncer_device_id}, status={status}')
"
```

### Test Manual Registration
```bash
python3 manage.py shell -c "
from zerver.models import PushDevice
from zerver.models.users import UserProfile
from zerver.lib.push_registration import handle_register_push_device_to_bouncer
from django.conf import settings

user = UserProfile.objects.get(id=8)
device = PushDevice.objects.filter(user=user).first()

if device:
    public_key = list(settings.PUSH_REGISTRATION_ENCRYPTION_KEYS.keys())[0]
    queue_item = {
        'user_profile_id': user.id,
        'bouncer_public_key': public_key,
        'encrypted_push_registration': 'test_data',
        'push_account_id': device.push_account_id
    }
    
    try:
        handle_register_push_device_to_bouncer(queue_item)
        print('✅ Manual registration succeeded!')
    except Exception as e:
        print(f'❌ Manual registration failed: {e}')
"
```

## Troubleshooting Guide

### If E2EE Registration Still Fails

1. **Check Bouncer Service Status**
   - The 500 errors might be temporary
   - Contact Zulip support if persistent

2. **Verify Flutter App Implementation**
   - Ensure E2EE encryption format matches server expectations
   - Check for any client-side encryption errors

3. **Fallback to Legacy Push Notifications**
   - E2EE is optional; legacy notifications should still work
   - Server will automatically fall back if E2EE fails

### Common Error Messages

- `"Skipping E2EE push notifications for user X because there are no registered devices"`
  - **Cause**: No devices with `bouncer_device_id` populated
  - **Solution**: Ensure E2EE registration completes successfully

- `"Received 500 from push notification bouncer"`
  - **Cause**: Bouncer service error
  - **Solution**: Check bouncer service status, re-register server

- `"PUSH_REGISTRATION_ENCRYPTION_KEYS configured: False"`
  - **Cause**: Missing encryption keys
  - **Solution**: Generate and configure encryption keys

## Key Files and Locations

- **Secrets File**: `/etc/zulip/zulip-secrets.conf`
- **Error Logs**: `/var/log/zulip/errors.log`
- **Worker Logs**: `/var/log/zulip/worker.log` (if exists)
- **Push Device Model**: `zerver.models.PushDevice`
- **Registration Handler**: `zerver.lib.push_registration.handle_register_push_device_to_bouncer`

## Related Documentation

- [Mobile Push Notifications](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html)
- [E2EE Push Notifications API](https://zulip.com/api/mobile-notifications)
- [Server Registration](https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html#signing-up)

## Next Steps

1. **Monitor bouncer service** for resolution of 500 errors
2. **Test legacy push notifications** to ensure basic functionality works
3. **Contact Zulip support** if bouncer issues persist
4. **Verify Flutter app** E2EE implementation if needed

---

**Date**: September 17, 2025  
**Server**: dev.zulip.xandylearning.in  
**Zulip Version**: 12.0-dev  
**Issue**: E2EE push notification registration failing due to bouncer 500 errors

