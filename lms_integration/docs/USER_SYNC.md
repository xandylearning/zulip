# LMS User Sync Documentation

This document explains how to sync users from the LMS database to Zulip.

## Overview

The LMS integration provides three methods to sync users:

1. **Admin Interface**: Web-based administration panel for interactive sync management
2. **Daily Morning Sync**: A management command that syncs all users from LMS to Zulip
3. **Webhook Endpoint**: An API endpoint that LMS can call when a new user is created 

## Batch and Channel Architecture

When batch synchronization is enabled, the system creates a structured communication environment:

### Realm-Wide Groups (Created Once)

The system creates **6 realm-wide user groups** that contain all users across all batches:

1. **Students** - All students from all batches
2. **Chief Mentors** - All chief mentors from all batches  
3. **Class Heads** - All class heads from all batches
4. **Head Mentors** - All head mentors from all batches
5. **Mentors** - All regular mentors from all batches
6. **All Mentors** - Parent group containing all mentor hierarchy subgroups

These groups are created once when batch sync first runs, and users are added/removed as batches are synced.

### Batch-Specific Channels (Created Per Batch)

Each batch gets its own **private channel** where:
- **Channel Name**: Matches the batch name (truncated to 60 characters if needed)
- **Privacy**: Private channel (`invite_only=True`)
- **Permissions**: 
  - Mentors can send messages (via `can_send_message_group` set to "All Mentors")
  - Students can only read messages (cannot send)
- **Subscriptions**: All students and mentors in the batch are automatically subscribed

### How It Works

1. **First Sync**: Creates the 6 realm-wide groups
2. **Per Batch**: 
   - Creates a private channel for the batch
   - Adds students to the realm-wide "Students" group
   - Adds mentors to their appropriate realm-wide hierarchy group
   - Subscribes all batch members to the batch channel
3. **Subsequent Syncs**: Updates memberships and subscriptions as batches change

### Individual User Sync with Batch Channels

When syncing individual students or mentors (not through batch sync), the system automatically:
- Finds all batches the user belongs to
- Creates batch channels if they don't exist
- Subscribes the user to their batch channels
- Ensures proper channel permissions are set

This means that even when syncing users individually, they will automatically be subscribed to their batch channels, ensuring they have access to batch communication channels. 

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
- **Enable**: Check "Include Batches" to synchronize batch channels and realm-wide user groups
- **Realm-Wide Groups**: Creates 6 realm-wide user groups (once for entire realm):
  - **Students**: All students from all batches
  - **Chief Mentors**: All chief mentors from all batches
  - **Class Heads**: All class heads from all batches
  - **Head Mentors**: All head mentors from all batches
  - **Mentors**: All regular mentors from all batches
  - **All Mentors**: Parent group containing all mentor hierarchy subgroups
- **Batch Channels**: Creates a private channel for each batch where:
  - Only mentors can send messages (students are read-only)
  - All batch students and mentors are automatically subscribed
  - Channel permissions are configured automatically
- **Membership**: Automatically adds students and mentors to appropriate realm-wide groups based on their hierarchy level

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

### Individual Batch Sync

The admin interface provides the ability to sync individual batches, which is useful for:
- Syncing a newly created batch
- Updating a specific batch after changes
- Troubleshooting batch-specific issues
- Selective batch synchronization

#### Syncing a Single Batch

1. **Navigate to Batch Groups**: Go to the "Batch Groups" tab in the admin interface
2. **Find Your Batch**: Locate the batch you want to sync in the batch groups table
3. **Click Sync**: Click the "Sync" button next to the batch
4. **Confirm**: Confirm the sync operation in the dialog
5. **Monitor Progress**: Watch the button state change to "Syncing..." during the operation

#### What Happens During Individual Batch Sync

When you sync a single batch, the system:

1. **Syncs Mentors First**: 
   - Finds all mentors associated with the batch (through their students)
   - Syncs each mentor (creates or updates their Zulip account)
   - Tracks mentor emails to prevent duplicate student creation
   - Adds mentors to appropriate realm-wide hierarchy groups

2. **Syncs Students**:
   - Finds all students in the batch
   - **Skips students whose email matches a mentor email** (already synced as mentor)
   - Syncs remaining students (creates or updates their Zulip accounts)
   - Adds students to the realm-wide "Students" group

3. **Creates/Updates Batch Channel**:
   - Creates the batch channel if it doesn't exist
   - Configures channel permissions (only mentors can send messages)
   - Uses existing channel if already present

4. **Subscribes Users**:
   - Subscribes all synced students to the batch channel
   - Subscribes all synced mentors to the batch channel
   - Skips users who are already subscribed

#### Batch Sync Results

After syncing a batch, you'll see:
- **students_created**: Number of new student accounts created
- **students_updated**: Number of existing student accounts updated
- **students_subscribed**: Number of students subscribed to the batch channel
- **mentors_created**: Number of new mentor accounts created
- **mentors_updated**: Number of existing mentor accounts updated
- **mentors_subscribed**: Number of mentors subscribed to the batch channel
- **channel_created**: Whether a new channel was created (true) or existing channel was used (false)
- **users_synced**: Total number of users synced (created + updated)
- **groups_updated**: Total number of channel subscriptions made

#### Individual User Sync with Batch Channels

When syncing individual students or mentors (not through batch sync), the system automatically:
- Finds all batches the user belongs to
- Creates batch channels if they don't exist
- Subscribes the user to their batch channels
- Ensures proper channel permissions are set

This means that even when syncing users individually, they will automatically be subscribed to their batch channels.

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
- **Automatic Batch Channel Subscription**: When a student is synced, they are automatically subscribed to all batch channels they belong to

### Mentors

- **Role**: Moderator (`ROLE_MODERATOR`)
- **Active Status**: Always active
- **Full Name**: Uses `display_name` if available, otherwise `first_name last_name`
- **Priority Sync**: Mentors are always synced from the Mentors table, even if they also appear in the Students table. This ensures mentors receive the correct role and prevents duplicate user creation.
- **Automatic Batch Channel Subscription**: When a mentor is synced, they are automatically subscribed to all batch channels for batches containing their students

## Sync Behavior

### User Sync

- **New Users**: Creates a new Zulip user account
- **Existing Users**: Updates the user's full name and active status if changed
- **Missing Email**: Users without email addresses are skipped
- **Duplicate Emails**: If a user with the same email already exists, the user is updated instead of created
- **Mentors in Students Table**: Students who exist in the Mentors table are skipped during student sync to prevent duplicate user creation. These users are only synced from the Mentors table, ensuring mentors are created with the correct role and avoiding duplicate accounts.

### Batch and Channel Sync (with `--sync-batches`)

The batch synchronization feature creates a comprehensive communication structure. There are two ways to sync batches:

1. **Sync All Batches**: Syncs all batches at once (via admin UI "Sync All Batches" button or `--sync-batches` flag)
2. **Sync Individual Batch**: Syncs a single batch including all its students and mentors (via admin UI "Sync" button on each batch)

#### Sync All Batches

When syncing all batches (via `sync_batches_and_groups()` method):

#### Realm-Wide User Groups

**Created Once for Entire Realm:**
- **Students Group**: Contains all students from all batches
- **Mentor Hierarchy Groups**: 
  - **Chief Mentors**: All chief mentors across all batches
  - **Class Heads**: All class heads across all batches
  - **Head Mentors**: All head mentors across all batches
  - **Mentors**: All regular mentors across all batches
- **All Mentors Group**: Parent group containing all mentor hierarchy subgroups

**Group Membership:**
- Students are automatically added to the realm-wide "Students" group
- Mentors are automatically added to their appropriate hierarchy group based on their `hierarchy` field in the LMS database
- Inactive users are automatically removed from groups

#### Batch-Specific Channels

**Created Per Batch:**
- Each batch gets its own **private channel** (named after the batch)
- Channel permissions:
  - **Mentors**: Can send messages (configured via `can_send_message_group` set to "All Mentors")
  - **Students**: Can only read messages (cannot send)
- Automatic subscriptions:
  - All students in the batch are subscribed to their batch channel
  - All mentors of students in the batch are subscribed to their batch channel

#### Mentor Hierarchy

Mentors are organized into hierarchy groups based on their `hierarchy` field in the LMS `Mentors` table:
- **Chief Mentors**: Highest level mentors
- **Class Heads**: Class-level mentors
- **Head Mentors**: Head mentors
- **Mentors**: Regular mentors (default if hierarchy not specified)

The system normalizes hierarchy values from the LMS database to match these standard levels.

#### Sync Individual Batch

When syncing a single batch (via `sync_batch()` method):

1. **Mentors are synced first** to ensure correct role assignment
2. **Students are synced second**, with automatic skipping of any students whose email matches a mentor email
3. **Batch channel is created or retrieved**
4. **All users are subscribed** to the batch channel

This ensures that:
- Mentors always get the correct role (ROLE_MENTOR)
- No duplicate users are created
- Users who are both mentors and students are handled correctly
- Batch channels are automatically set up

#### Sync Statistics

When batch sync completes, you'll see:
- `channels_created`: Number of new batch channels created
- `channels_updated`: Number of existing channels updated
- `mentor_groups_created`: Number of new realm-wide mentor groups created (typically 0 after first sync)
- `student_groups_created`: Number of new realm-wide student groups created (typically 0 after first sync)
- `students_added`: Students added to realm-wide groups
- `students_subscribed`: Students subscribed to batch channels
- `mentors_added`: Mentors added to realm-wide hierarchy groups
- `mentors_subscribed`: Mentors subscribed to batch channels

For individual batch sync, you'll also see:
- `students_created`: Number of new student accounts created
- `students_updated`: Number of existing student accounts updated
- `mentors_created`: Number of new mentor accounts created
- `mentors_updated`: Number of existing mentor accounts updated
- `channel_created`: Whether a new channel was created (true/false)

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


