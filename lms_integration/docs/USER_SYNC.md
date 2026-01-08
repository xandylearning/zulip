# LMS User Sync Documentation

This document explains how to sync users from the LMS database to Zulip.

## Overview

The LMS integration provides three methods to sync users:

1. **Admin Interface**: Web-based administration panel for interactive sync management
2. **Daily Morning Sync**: A management command that syncs all users from LMS to Zulip
3. **Webhook Endpoint**: An API endpoint that LMS can call when a new user is created 

## Admin Interface Sync

The admin interface provides an intuitive web-based method for managing user synchronization with real-time progress monitoring and detailed control options.

### Accessing the Admin Interface

1. **Login as Administrator**: Access your Zulip server with administrator credentials
2. **Navigate to Settings**: Click the gear icon (⚙️) and select "Organization settings"
3. **LMS Integration Tab**: Click the "LMS Integration" tab in the settings panel
4. **User Sync Section**: Navigate to the "User Sync" tab within the admin interface

### Sync Types

The admin interface supports three sync types:

#### Incremental Sync (Recommended)
- **Description**: Syncs only new or modified users since the last sync
- **Use Case**: Regular daily operations
- **Performance**: Fast execution, minimal resource usage
- **Safety**: Low risk, preserves existing data

#### Full Sync
- **Description**: Complete resynchronization of all users
- **Use Case**: Initial setup, major data corrections, periodic comprehensive updates
- **Performance**: Slower execution, higher resource usage
- **Safety**: Medium risk, may update all existing users

#### Selective Sync
- **Description**: Sync specific users or groups based on custom criteria
- **Use Case**: Targeted updates, troubleshooting specific user issues
- **Performance**: Variable, depends on selection criteria
- **Safety**: High control, minimal impact

### Sync Options

#### Batch Synchronization
- **Enable**: Check "Include Batches" to synchronize batch group information
- **Function**: Creates Zulip user groups corresponding to LMS batch groups
- **Membership**: Automatically adds students and mentors to appropriate groups
- **Naming**: Groups named using batch naming convention

#### Update Preferences
- **Update Existing**: Refresh information for already synchronized users
- **Create Missing**: Create new Zulip accounts for users not yet synced
- **Preserve Custom**: Maintain user customizations in Zulip

### Using the Admin Interface Sync

#### Step 1: Configure Sync Options
1. Select your preferred sync type (Incremental recommended for regular use)
2. Choose whether to include batch synchronization
3. Configure update preferences as needed

#### Step 2: Initiate Synchronization
1. Click the "Start Sync" button
2. Monitor the real-time progress bar
3. Watch live statistics updates:
   - **Created**: New users added to Zulip
   - **Updated**: Existing users refreshed
   - **Skipped**: Users that didn't need changes
   - **Errors**: Users that failed to sync

#### Step 3: Review Results
1. Check the completion summary for statistics
2. Review any error messages if present
3. Verify user counts in the dashboard
4. Test user access and permissions

### Real-Time Monitoring

The admin interface provides live feedback during synchronization:

- **Progress Bar**: Visual indicator showing completion percentage
- **Status Text**: Current operation description
- **Live Statistics**: Real-time counts of sync operations
- **Error Tracking**: Immediate notification of any issues

### Sync History

The admin interface maintains a complete audit trail:

- **Sync Records**: All synchronization operations are logged
- **Duration Tracking**: Time taken for each sync operation
- **Result Analysis**: Success rates and error patterns
- **User Impact**: Detailed statistics for each sync

### Individual User Management

#### User Table Features
- **Searchable**: Find users by name, email, or LMS ID
- **Filterable**: Filter by user type (student/mentor) or sync status
- **Sortable**: Sort by any column for easy management
- **Paginated**: Navigate through large user lists efficiently

#### Individual User Actions
- **Resync User**: Manually resynchronize specific user data
- **View Details**: Access detailed user information and sync history
- **Update Status**: Modify user sync status or preferences

### Troubleshooting Sync Issues

#### Common Admin Interface Issues

**Sync Button Disabled**
- Verify administrator permissions
- Check LMS database connectivity
- Ensure no other sync operations are running

**Progress Not Updating**
- Check browser console for JavaScript errors
- Verify API endpoint connectivity
- Refresh the page and retry

**Incomplete Sync Results**
- Review error messages in the interface
- Check LMS database for data issues
- Verify Zulip user creation permissions

#### Using Logs for Debugging
1. Navigate to the "Logs" tab in the admin interface
2. Filter logs by source="sync" and level="ERROR"
3. Review detailed error messages and stack traces
4. Use log search functionality to find specific issues

### Best Practices for Admin Interface Sync

#### Regular Operations
1. **Use Incremental Sync**: For daily operations to minimize resource usage
2. **Schedule Full Sync**: Run comprehensive sync weekly or monthly
3. **Monitor Progress**: Always monitor sync operations for issues
4. **Review Logs**: Regularly check logs for warning signs

#### Data Management
1. **Backup Before Major Sync**: Create backups before full synchronization
2. **Test Configuration**: Use database test tools before syncing
3. **Validate Results**: Always verify sync results in the dashboard
4. **Document Changes**: Keep records of major sync operations

#### Performance Optimization
1. **Off-Peak Timing**: Run large sync operations during low-usage periods
2. **Batch Size**: Configure appropriate batch sizes for your system
3. **Resource Monitoring**: Monitor system resources during sync operations
4. **Network Bandwidth**: Consider network impact for large synchronizations

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
- **Mentor Exclusion**: Students who exist in the Mentors table are automatically skipped during student sync and will only be synced from the Mentors table

### Mentors

- **Role**: Moderator (`ROLE_MODERATOR`)
- **Active Status**: Always active
- **Full Name**: Uses `display_name` if available, otherwise `first_name last_name`
- **Priority Sync**: Mentors are always synced from the Mentors table, even if they also appear in the Students table. This ensures mentors receive the correct role and prevents duplicate user creation.

## Sync Behavior

### User Sync

- **New Users**: Creates a new Zulip user account
- **Existing Users**: Updates the user's full name and active status if changed
- **Missing Email**: Users without email addresses are skipped
- **Duplicate Emails**: If a user with the same email already exists, the user is updated instead of created
- **Mentors in Students Table**: Students who exist in the Mentors table are skipped during student sync to prevent duplicate user creation. These users are only synced from the Mentors table, ensuring mentors are created with the correct role and avoiding duplicate accounts.

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
4. **Mentors in Students Table**: If a user appears in both Students and Mentors tables, they will only be synced from the Mentors table. Check the sync statistics for "skipped" counts - users skipped because they're mentors will be logged with a debug message indicating they'll be synced from the Mentors table.

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


