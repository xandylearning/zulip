# Placeholder Email Support for LMS Integration

This guide documents the placeholder email feature that allows LMS users without email addresses to use Zulip.

## Overview

Many LMS systems (especially educational institutions) have students who don't have email addresses. Previously, these users could not be synced to Zulip because Zulip requires email addresses for all users. The placeholder email feature solves this by:

1. **Generating placeholder emails** for users without real email addresses
2. **Automatically updating** placeholder emails to real emails when they become available
3. **Smart notification handling** to prevent email delivery to non-existent addresses
4. **Maintaining full Zulip functionality** except email notifications

## How It Works

### Placeholder Email Generation

When a user without an email address is synced from the LMS:

1. The system generates a placeholder email using their username
2. Default format: `{username}@noemail.local`
3. Can be configured to use your institution's domain: `{username}@students.school.edu`

### Example Flow

```
LMS User:
- Username: john_doe
- Email: (empty)

Generated Zulip User:
- Username: john_doe
- Email: john_doe@noemail.local (placeholder)
- Can authenticate, use Zulip normally
- No email notifications sent
- In-app notifications work normally
```

## Configuration

### Settings

Configure placeholder emails in the admin interface or by adding these settings:

```python
# Domain for generating placeholder emails
LMS_NO_EMAIL_DOMAIN = "students.yourschool.edu"

# Auto-update placeholder emails to real emails when available
LMS_AUTO_UPDATE_EMAILS = True

# Notification behavior for placeholder email users
LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS = {
    'email_delivery': False,        # Don't send emails to placeholder addresses
    'in_app_notifications': True,   # Show in-app notifications
    'log_attempts': True,          # Log blocked email attempts
}
```

### Admin Interface Configuration

1. Go to **Organization settings** → **LMS Integration** → **Configuration**
2. Find the **Placeholder Email Configuration** section
3. Set your preferred domain and notification settings
4. Save configuration

## User Sync Behavior

### Students Without Email

```python
# Before (would be skipped):
if not student.email:
    return False, None, f"Student {student.id} has no email address"

# After (creates placeholder):
email, is_placeholder = validate_and_prepare_email(
    student.email,    # None or empty
    student.username, # "john_doe"
    self.realm
)
# email = "john_doe@noemail.local", is_placeholder = True
```

### Auto-Update to Real Email

When a student gets a real email in the LMS:

```python
# During next sync:
if LMS_AUTO_UPDATE_EMAILS and student.email:
    # Updates john_doe@noemail.local → john.doe@school.edu
    update_email_if_changed(user_profile, student.email, student.username)
```

## Authentication

### JWT Authentication

The JWT authentication backend handles both scenarios:

```python
# JWT payload with email:
{
    "username": "john_doe",
    "email": "john.doe@school.edu"
}
# → Uses real email

# JWT payload without email:
{
    "username": "john_doe",
    "email": null
}
# → Generates john_doe@noemail.local
```

### Username-Based Matching

The system can find existing users by placeholder email patterns:

```python
# Finds user even if domain changed from noemail.local to students.school.edu
find_user_by_placeholder_patterns("john_doe")
```

## Notification Handling

### Email Notifications

- **Real email users**: Receive all email notifications normally
- **Placeholder email users**: Email notifications are blocked
- **Logging**: Blocked attempts are logged for monitoring

### In-App & Push Notifications

- **All users**: Receive in-app and push notifications normally
- **No impact**: Placeholder emails don't affect non-email notifications

### Notification Flow

```python
def send_notification(user, message):
    if should_send_email_notification(user):
        send_email(user, message)  # Only for real emails
    else:
        log_placeholder_email_attempt(user, "notification_blocked")

    # These always work:
    send_push_notification(user, message)
    show_in_app_notification(user, message)
```

## Management Commands

### Report Statistics

```bash
# Generate placeholder email usage report
python manage.py manage_placeholder_emails --realm your-realm report

# JSON format for integration
python manage.py manage_placeholder_emails --realm your-realm report --format json

# CSV format for spreadsheets
python manage.py manage_placeholder_emails --realm your-realm report --format csv
```

### Update Emails

```bash
# Check for real emails in LMS and update placeholder emails
python manage.py manage_placeholder_emails --realm your-realm update

# Dry run to see what would be updated
python manage.py manage_placeholder_emails --realm your-realm update --dry-run
```

### Bulk Email Updates

```bash
# Update emails from CSV file (username,email format)
python manage.py manage_placeholder_emails --realm your-realm bulk-update emails.csv

# Validate CSV without making changes
python manage.py manage_placeholder_emails --realm your-realm bulk-update emails.csv --dry-run
```

#### CSV Format Example

```csv
john_doe,john.doe@school.edu
jane_smith,jane.smith@school.edu
bob_wilson,bob.wilson@school.edu
```

## Monitoring & Administration

### Admin Dashboard

The LMS Integration admin panel shows:

1. **Statistics**:
   - Total users vs. placeholder email users
   - Email notification coverage percentage
   - Recent placeholder email activity

2. **Placeholder Email Management**:
   - List of users with placeholder emails
   - Bulk update tools
   - Export functionality

3. **Configuration**:
   - Domain settings
   - Auto-update preferences
   - Notification behavior

### Monitoring Queries

```sql
-- Count users with placeholder emails
SELECT COUNT(*) FROM zerver_userprofile
WHERE delivery_email LIKE '%@noemail.local';

-- Find users who could be updated
SELECT u.delivery_email, s.email as lms_email
FROM zerver_userprofile u
JOIN lms_students s ON u.delivery_email LIKE CONCAT(s.username, '@%')
WHERE s.email IS NOT NULL
AND s.email != ''
AND u.delivery_email LIKE '%@noemail.local';
```

## Troubleshooting

### Common Issues

#### Users Not Syncing
- **Check**: Username uniqueness in LMS
- **Verify**: LMS connection is working
- **Solution**: Ensure usernames are valid email local parts

#### Email Updates Not Working
- **Check**: `LMS_AUTO_UPDATE_EMAILS = True` setting
- **Verify**: LMS has real email addresses
- **Solution**: Run manual update command

#### Notifications Not Reaching Users
- **Expected**: Email notifications blocked for placeholder users
- **Verify**: In-app notifications still work
- **Solution**: Update to real emails or use in-app messaging

### Debug Commands

```bash
# Check specific user's email status
python manage.py shell -c "
from zerver.models import UserProfile
from lms_integration.lib.email_utils import is_placeholder_email
user = UserProfile.objects.get(delivery_email='john_doe@noemail.local')
print(f'Is placeholder: {is_placeholder_email(user.delivery_email)}')
"

# Test email generation
python manage.py shell -c "
from lms_integration.lib.email_utils import generate_placeholder_email
print(generate_placeholder_email('test_user'))
"
```

### Logs to Monitor

```bash
# Placeholder email generation
grep "Generated placeholder email" /var/log/zulip/lms_integration.log

# Blocked email notifications
grep "Blocked email notification" /var/log/zulip/lms_integration.log

# Email updates
grep "Updated user email" /var/log/zulip/lms_integration.log
```

## Migration Guide

### For Existing Installations

1. **Update Code**: Deploy the placeholder email feature
2. **Run Migration**: `python manage.py migrate lms_integration`
3. **Configure Settings**: Set domain and preferences
4. **Test Sync**: Run a test sync with a user without email
5. **Monitor**: Check logs and admin dashboard

### Data Migration

For existing users who were previously skipped:

```bash
# Report what would be synced now
python manage.py manage_placeholder_emails --realm your-realm convert --dry-run

# Run full sync to create users with placeholder emails
python manage.py lms_sync --realm your-realm --sync-type all
```

## Best Practices

### Domain Selection

- **Internal domain**: Use `students.yourschool.edu` for clarity
- **Fake domain**: Use `noemail.local` to avoid confusion
- **Avoid real domains**: Don't use domains that receive email

### Email Management

- **Regular updates**: Run periodic checks for real emails
- **Monitor statistics**: Track placeholder email percentage
- **Plan migration**: Have strategy for transitioning users to real emails

### Communication

- **Inform users**: Tell students they won't receive email notifications
- **Alternative channels**: Use in-app messaging or announcements
- **Support process**: Have plan for users who need email updates

## Security Considerations

### Authentication

- **JWT validation**: Same security as regular users
- **Username requirements**: Ensure usernames are secure identifiers
- **Domain spoofing**: Use clearly fake domains to prevent confusion

### Email Delivery

- **No sensitive data**: Placeholder emails never receive emails
- **Audit logging**: All blocked attempts are logged
- **Privacy**: No risk of email leakage to wrong addresses

## API Reference

### Email Utilities

```python
from lms_integration.lib.email_utils import (
    generate_placeholder_email,
    is_placeholder_email,
    validate_and_prepare_email,
    update_email_if_changed,
    should_send_email_notification,
    get_placeholder_email_stats
)

# Generate placeholder email
email = generate_placeholder_email("username", "domain.com")

# Check if email is placeholder
is_fake = is_placeholder_email("user@noemail.local")

# Prepare email (real or placeholder)
email, is_placeholder = validate_and_prepare_email(
    raw_email, username, realm
)

# Update email if changed
updated = update_email_if_changed(user_profile, new_email, username)

# Check notification permissions
can_email = should_send_email_notification(user_profile)

# Get statistics
stats = get_placeholder_email_stats(realm)
```

### Notification Handling

```python
from lms_integration.lib.notifications import LMSNotificationHandler

# Send single notification
sent = LMSNotificationHandler.send_email_notification(
    user_profile, "message", {"content": "..."}
)

# Send bulk notifications
stats = LMSNotificationHandler.bulk_send_notifications(
    user_list, "announcement", {"subject": "...", "message": "..."}
)

# Get notification statistics
notification_stats = LMSNotificationHandler.get_notification_stats(realm)
```

## Support

For questions or issues with placeholder email functionality:

1. Check the admin dashboard statistics
2. Review the logs for error messages
3. Test with the management commands
4. Consult this guide for configuration options

The placeholder email feature ensures that all LMS users can access Zulip regardless of whether they have email addresses, while maintaining security and preventing email delivery issues.