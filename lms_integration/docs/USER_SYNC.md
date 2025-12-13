# LMS User Sync Documentation

This document explains how to sync users from the LMS database to Zulip.

## Overview

The LMS integration provides two methods to sync users:

1. **Daily Morning Sync**: A management command that syncs all users from LMS to Zulip
2. **Webhook Endpoint**: An API endpoint that LMS can call when a new user is created

## Daily Morning Sync

### Running the Sync Command

To sync all users from LMS to Zulip, run:

```bash
python manage.py sync_lms_users
```

This will sync both students and mentors.

### Command Options

- `--students-only`: Sync only students
- `--mentors-only`: Sync only mentors
- `--student-id <id>`: Sync a specific student by ID
- `--mentor-id <id>`: Sync a specific mentor by ID
- `--realm <string_id>`: Specify the realm to sync users to (default: first realm)
- `--sync-batches`: Also sync batches and group memberships (creates batch groups and adds users)
- `--verbose`: Enable verbose logging

### Examples

```bash
# Sync all users
python manage.py sync_lms_users

# Sync only students
python manage.py sync_lms_users --students-only

# Sync a specific student
python manage.py sync_lms_users --student-id 123

# Sync to a specific realm
python manage.py sync_lms_users --realm zulip

# Sync users and batches (creates batch groups and manages memberships)
python manage.py sync_lms_users --sync-batches
```

### Scheduling Daily Sync

To run the sync every morning, add a cron job:

```bash
# Edit crontab
crontab -e

# Add this line to run at 6 AM every day
0 6 * * * cd /path/to/zulip && /path/to/venv/bin/python manage.py sync_lms_users
```

Or use systemd timer (recommended for production):

```ini
# /etc/systemd/system/zulip-lms-sync.service
[Unit]
Description=Zulip LMS User Sync
After=network.target

[Service]
Type=oneshot
User=zulip
WorkingDirectory=/home/zulip/deployments/current
ExecStart=/home/zulip/deployments/current/venv/bin/python manage.py sync_lms_users
```

```ini
# /etc/systemd/system/zulip-lms-sync.timer
[Unit]
Description=Daily Zulip LMS User Sync
Requires=zulip-lms-sync.service

[Timer]
OnCalendar=daily
OnCalendar=06:00
Persistent=true

[Install]
WantedBy=timers.target
```

Then enable and start:

```bash
sudo systemctl enable zulip-lms-sync.timer
sudo systemctl start zulip-lms-sync.timer
```

## Webhook Endpoint

### Configuration

Configure the webhook secret and optional realm settings using Zulip's configuration files.

#### Production Configuration

Add to `/etc/zulip/zulip-secrets.conf`:
```ini
[secrets]
lms_webhook_secret = your-secret-token-here
```

Optionally, add to `/etc/zulip/zulip.conf`:
```ini
[lms_user_sync]
realm = zulip
```

#### Development Configuration

Add to `zproject/dev-secrets.conf`:
```ini
[secrets]
lms_webhook_secret = your-dev-secret-token-here
```

Optionally, add to `zproject/dev_settings.py`:
```python
LMS_USER_SYNC_REALM = "zulip"  # Optional
```

**Note**: After updating configuration files, restart the Zulip server:
```bash
su zulip -c /home/zulip/deployments/current/scripts/restart-server
```

### Endpoint URL

The webhook endpoint is available at:

```
POST /api/v1/lms/webhook/user-created
```

### Authentication

The webhook supports three authentication methods:

1. **Authorization Header** (recommended):
   ```
   Authorization: Bearer <secret>
   ```

2. **Custom Header**:
   ```
   X-LMS-Webhook-Secret: <secret>
   ```

3. **Request Body**:
   ```json
   {
     "secret": "<secret>",
     ...
   }
   ```

### Request Format

```json
{
  "event_type": "user_created",
  "user_type": "student",  // or "mentor"
  "user_id": 123,
  "secret": "your-secret-token"  // optional if provided in header
}
```

### Response Format

**Success (User Created)**:
```json
{
  "result": "success",
  "message": "User user@example.com created successfully",
  "user_id": 456,
  "email": "user@example.com",
  "created": true
}
```

**Success (User Updated)**:
```json
{
  "result": "success",
  "message": "User user@example.com already exists and was updated",
  "user_id": 456,
  "email": "user@example.com",
  "created": false
}
```

**Error**:
```json
{
  "result": "error",
  "message": "Error description"
}
```

### Example Webhook Call

Using curl:

```bash
curl -X POST https://your-zulip-server.com/api/v1/lms/webhook/user-created \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your-secret-token" \
  -d '{
    "event_type": "user_created",
    "user_type": "student",
    "user_id": 123
  }'
```

Using Python:

```python
import requests

url = "https://your-zulip-server.com/api/v1/lms/webhook/user-created"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer your-secret-token"
}
data = {
    "event_type": "user_created",
    "user_type": "student",
    "user_id": 123
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

## User Mapping

### Students

- **Role**: Member (`ROLE_MEMBER`)
- **Active Status**: Synced from LMS `is_active` field
- **Full Name**: Uses `display_name` if available, otherwise `first_name last_name`

### Mentors

- **Role**: Moderator (`ROLE_MODERATOR`)
- **Active Status**: Always active
- **Full Name**: Uses `display_name` if available, otherwise `first_name last_name`

## Sync Behavior

### User Sync

- **New Users**: Creates a new Zulip user account
- **Existing Users**: Updates the user's full name and active status if changed
- **Missing Email**: Users without email addresses are skipped
- **Duplicate Emails**: If a user with the same email already exists, the user is updated instead of created

### Batch and Group Sync (with `--sync-batches`)

- **Batch Groups**: Creates Zulip user groups for each LMS batch
- **Student Membership**: Adds active students to their batch groups
- **Mentor Membership**: Adds mentors to batch groups based on which students they mentor
- **Inactive Users**: Removes inactive users from batch groups automatically
- **Group Updates**: Updates existing batch groups if they already exist

## Troubleshooting

### Users Not Syncing

1. Check that the LMS database connection is configured correctly
2. Verify that users have email addresses in the LMS database
3. Check logs for errors: `tail -f /var/log/zulip/server.log`

### Webhook Not Working

1. Verify `lms_webhook_secret` is set in `/etc/zulip/zulip-secrets.conf` (production) or `zproject/dev-secrets.conf` (development)
2. Check that the secret matches between LMS and Zulip
3. Verify the endpoint URL is correct
4. Check webhook logs for authentication errors
5. Restart the Zulip server after updating configuration files

### Permission Errors

1. Ensure the Zulip user running the sync command has database access
2. Check that the LMS database user has read permissions
3. Verify realm permissions for user creation

## Configuration Reference

### Production Settings

**`/etc/zulip/zulip-secrets.conf`** (required for webhook):
```ini
[secrets]
lms_webhook_secret = your-secret-token-here
```

**`/etc/zulip/zulip.conf`** (optional):
```ini
[lms_user_sync]
realm = zulip
```

### Development Settings

**`zproject/dev-secrets.conf`** (required for webhook):
```ini
[secrets]
lms_webhook_secret = your-dev-secret-token-here
```

**`zproject/dev_settings.py`** (optional):
```python
LMS_USER_SYNC_REALM = "zulip"  # Optional, defaults to first realm
```

### Setting Descriptions

- **`lms_webhook_secret`**: Secret token used to authenticate webhook requests from LMS. Must match the token configured in your LMS system.
- **`realm`**: Realm string_id where users should be synced. If not specified, defaults to the first realm in the system.

**Important**: After updating configuration files, restart the Zulip server for changes to take effect.


