# Push Notification Diagnostics Guide

## Overview
This guide helps diagnose why push notifications are being queued but not processed or delivered. The diagnostic process covers three main areas:

1. **Worker Queue Processing** - Are workers running and consuming queued notifications?
2. **Bouncer Communication** - Is the push bouncer integration working?
3. **Platform Delivery** - Are notifications reaching APNs/FCM successfully?

## Current Status Analysis
From your logs, you can see:
- ✅ **Notification Triggering**: "User 43: Queuing push notification for message 421"
- ❌ **Worker Processing**: Missing "Push notification handler started" logs
- ❌ **Bouncer Communication**: No bouncer interaction logs
- ❌ **Platform Delivery**: No APNs/FCM delivery logs

## Phase 1: Worker Queue Diagnosis

### 1.1 Check Worker Status

**Development Environment:**
```bash
# Check if workers are running
ps aux | grep process_queue | grep -v grep
ps aux | grep missedmessage_mobile_notifications | grep -v grep

# Start workers manually for testing
./manage.py process_queue --queue_name=missedmessage_mobile_notifications
```

**Production Environment:**
```bash
# Check supervisord worker status
sudo supervisorctl status | grep missedmessage
sudo supervisorctl status | grep queue

# Check systemd services (if using systemd)
sudo systemctl status zulip-workers@missedmessage_mobile_notifications
sudo systemctl status zulip-workers@*
```

### 1.2 Check Message Broker Status

**RabbitMQ (default for Zulip):**
```bash
# Check RabbitMQ service
sudo systemctl status rabbitmq-server

# Check queue status (requires admin access)
sudo rabbitmqctl list_queues name messages consumers
sudo rabbitmqctl list_queues missedmessage_mobile_notifications

# Check for queue processing errors
ls -la /var/log/zulip/queue_error/
cat /var/log/zulip/queue_error/missedmessage_mobile_notifications.errors
```

### 1.3 Manual Queue Processing Test

```bash
# Force process the queue to trigger worker logs
sudo -u zulip /home/zulip/deployments/current/manage.py process_queue --queue_name=missedmessage_mobile_notifications

# Process all queues for comprehensive test
sudo -u zulip /home/zulip/deployments/current/manage.py process_queue --all

# Check for immediate log output
tail -f /var/log/zulip/django.log | grep "Push notification handler"
```

### 1.4 Worker Configuration Check

```bash
# Check Django queue settings
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from django.conf import settings
import pprint
print('TORNADO_PROCESSES:', settings.TORNADO_PROCESSES)
print('USING_RABBITMQ:', getattr(settings, 'USING_RABBITMQ', 'Not set'))
pprint.pprint({k: v for k, v in vars(settings).items() if 'QUEUE' in k or 'RABBIT' in k})
"
```

**Expected Success Indicators:**
```
INFO [zerver.lib.push_notifications] Push notification handler started: user_id=43, message_id=421, trigger=direct_message
```

## Phase 2: Bouncer Communication Verification

### 2.1 Check Bouncer Configuration

```bash
# Verify bouncer settings
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from django.conf import settings
print(f'Push notifications enabled: {settings.PUSH_NOTIFICATION_BOUNCER_URL is not None}')
print(f'Bouncer URL: {getattr(settings, \"PUSH_NOTIFICATION_BOUNCER_URL\", \"Not configured\")}')
print(f'Org ID configured: {bool(getattr(settings, \"ZULIP_ORG_ID\", None))}')
print(f'Org Key configured: {bool(getattr(settings, \"ZULIP_ORG_KEY\", None))}')
print(f'Uses bouncer: {getattr(settings, \"ZULIP_SERVICE_PUSH_NOTIFICATIONS\", False)}')
"
```

### 2.2 Test Bouncer Connectivity

```bash
# Get bouncer credentials
BOUNCER_URL=$(sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "from django.conf import settings; print(getattr(settings, 'PUSH_NOTIFICATION_BOUNCER_URL', 'https://push.zulipchat.com'))")
ORG_ID=$(sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "from django.conf import settings; print(getattr(settings, 'ZULIP_ORG_ID', ''))")
ORG_KEY=$(sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "from django.conf import settings; print(getattr(settings, 'ZULIP_ORG_KEY', ''))")

# Test bouncer connectivity
curl -v -u "$ORG_ID:$ORG_KEY" "$BOUNCER_URL/api/v1/remotes/server/analytics/status"
```

### 2.3 Check Device Registration

```bash
# Check registered devices for test user
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from zerver.models import PushDeviceToken, UserProfile
try:
    user = UserProfile.objects.get(id=43)  # Replace 43 with your test user ID
    devices = PushDeviceToken.objects.filter(user=user)
    print(f'User {user.id} ({user.email}) has {devices.count()} devices:')
    for device in devices:
        print(f'  Token: {device.token[:20]}... Kind: {device.get_kind_display()} Updated: {device.last_updated}')
except UserProfile.DoesNotExist:
    print('User 43 not found - replace with valid user ID')
"
```

### 2.4 Check Bouncer Registration Status

```bash
# Check if server is registered with bouncer
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from zerver.lib.remote_server import send_server_data_to_push_bouncer
from django.conf import settings
if hasattr(settings, 'ZULIP_ORG_ID') and settings.ZULIP_ORG_ID:
    print('Server appears to be registered with bouncer')
    print(f'Org ID: {settings.ZULIP_ORG_ID}')
else:
    print('Server may not be registered with bouncer - run: ./manage.py register_server')
"
```

**Expected Success Indicators:**
```
INFO [zerver.lib.push_notifications] Using notification bouncer for user 43 push notifications
INFO [zerver.lib.push_notifications] Sending legacy push notifications to bouncer for user 43: 0 Android devices, 1 Apple devices
```

## Phase 3: Platform Delivery Verification

### 3.1 Check Recent Push Success

```bash
# Check Redis for recent push notification success
redis-cli get "push_notifications_recently_working_ts"
redis-cli keys "*push*" | head -10
```

### 3.2 Look for Delivery Logs

```bash
# Check for successful bouncer communication
grep "Sent mobile push notifications.*through bouncer" /var/log/zulip/django.log | tail -10

# Check for bouncer errors
grep -E "(Bouncer refused|PushNotificationsDisallowedByBouncerError|INVALID_ZULIP_SERVER)" /var/log/zulip/django.log | tail -10
```

### 3.3 Verify Device Token Status

```bash
# Check for invalid/expired device tokens
grep -E "(Invalid device token|Token expired|APNs error|FCM error)" /var/log/zulip/django.log | tail -10
```

**Expected Success Indicators:**
```
INFO [zerver.lib.push_notifications] Sent mobile push notifications for user 43 through bouncer: 0 via FCM devices, 1 via APNs devices
```

## Common Issues and Solutions

### Issue 1: No Workers Running
**Symptoms:** No "Push notification handler started" logs after manual queue processing
**Solutions:**
```bash
# Restart workers
sudo supervisorctl restart zulip-workers:*
sudo systemctl restart zulip-workers@missedmessage_mobile_notifications

# Check for startup errors
sudo journalctl -u zulip-workers@missedmessage_mobile_notifications -f
```

### Issue 2: RabbitMQ Issues
**Symptoms:** Connection refused errors, no queue processing
**Solutions:**
```bash
# Restart RabbitMQ
sudo systemctl restart rabbitmq-server

# Check RabbitMQ logs
sudo journalctl -u rabbitmq-server -f

# Reset RabbitMQ if needed (CAUTION: Will lose queued messages)
sudo systemctl stop rabbitmq-server
sudo rm -rf /var/lib/rabbitmq/mnesia
sudo systemctl start rabbitmq-server
```

### Issue 3: Bouncer Not Configured
**Symptoms:** No bouncer logs, "PUSH_NOTIFICATIONS_DISALLOWED" errors
**Solutions:**
```bash
# Register server with bouncer
sudo -u zulip /home/zulip/deployments/current/manage.py register_server

# Check registration at https://selfhosting.zulip.com/
# Ensure your plan allows push notifications
```

### Issue 4: Invalid Device Tokens
**Symptoms:** Bouncer communication works but delivery fails
**Solutions:**
```bash
# Clear invalid tokens (they'll re-register)
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from zerver.models import PushDeviceToken
# Remove tokens older than 30 days that might be expired
import datetime
cutoff = datetime.datetime.now() - datetime.timedelta(days=30)
old_tokens = PushDeviceToken.objects.filter(last_updated__lt=cutoff)
print(f'Removing {old_tokens.count()} old device tokens')
old_tokens.delete()
"
```

## Complete Diagnostic Command Sequence

Run these commands in order to get a complete picture:

```bash
# 1. Check worker status
echo "=== WORKER STATUS ==="
sudo supervisorctl status | grep -E "(queue|worker)"
ps aux | grep process_queue | grep -v grep

# 2. Check message broker
echo "=== MESSAGE BROKER STATUS ==="
sudo systemctl status rabbitmq-server
sudo rabbitmqctl list_queues name messages | grep missedmessage

# 3. Check push notification configuration
echo "=== PUSH NOTIFICATION CONFIGURATION ==="
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from django.conf import settings
print(f'Bouncer enabled: {getattr(settings, \"PUSH_NOTIFICATION_BOUNCER_URL\", None) is not None}')
print(f'Org registered: {bool(getattr(settings, \"ZULIP_ORG_ID\", None))}')
"

# 4. Manual queue processing test
echo "=== MANUAL QUEUE TEST ==="
sudo -u zulip /home/zulip/deployments/current/manage.py process_queue --queue_name=missedmessage_mobile_notifications &
QUEUE_PID=$!
sleep 5
tail -f /var/log/zulip/django.log | grep -E "(Push notification handler|Using notification bouncer)" &
LOG_PID=$!
sleep 10
kill $QUEUE_PID $LOG_PID 2>/dev/null

# 5. Check recent logs for errors
echo "=== RECENT ERRORS ==="
grep -E "(ERROR|CRITICAL)" /var/log/zulip/django.log | grep -i push | tail -5
```

## Log File Locations

- **Main Django logs:** `/var/log/zulip/django.log`
- **Worker logs:** `/var/log/zulip/workers/`
- **Queue errors:** `/var/log/zulip/queue_error/`
- **Supervisor logs:** `/var/log/supervisor/`
- **System logs:** `journalctl -u zulip* -f`

## Next Steps After Diagnostics

1. **If no worker logs appear:** Focus on worker/queue configuration
2. **If worker logs appear but no bouncer logs:** Check bouncer configuration
3. **If bouncer logs appear but no delivery:** Check device tokens and platform setup
4. **If everything logs correctly:** Issue may be with mobile app notification settings

## Testing Push Notifications End-to-End

After fixing issues, test with:

```bash
# Send a test message that should trigger a push notification
sudo -u zulip /home/zulip/deployments/current/manage.py shell -c "
from zerver.models import UserProfile, get_realm
from zerver.lib.actions import do_send_messages, check_message
from zerver.lib.message import SendMessageRequest

# Replace with your test users
sender = UserProfile.objects.get(email='sender@yourdomain.com')
recipient = UserProfile.objects.get(email='recipient@yourdomain.com')

message = check_message(sender, sender.realm.get_admin_client(), 'private', [recipient.id], 'Test push notification', None)
do_send_messages([message])
print('Test message sent - check for push notification logs')
"
```

Monitor logs in real-time during testing:
```bash
tail -f /var/log/zulip/django.log | grep -E "(Push notification|bouncer|APNs|FCM)"
```