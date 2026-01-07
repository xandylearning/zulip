# LMS Integration Settings
"""
Configuration settings for LMS Integration module.
These settings control how users without email addresses are handled.
"""

# Domain to use for generating placeholder emails for users without email addresses
# Example: If set to "noemail.yourschool.edu", a user with username "john_doe"
# would get the placeholder email "john_doe@noemail.yourschool.edu"
LMS_NO_EMAIL_DOMAIN = "noemail.local"

# Whether to automatically update user emails when real emails become available in LMS
# If True, users with placeholder emails will be updated to real emails during sync
# If False, placeholder emails will remain unchanged
LMS_AUTO_UPDATE_EMAILS = True

# Configuration for email notifications to users with placeholder emails
LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS = {
    # Whether to attempt email delivery to placeholder addresses
    'email_delivery': False,

    # Whether to show in-app notifications for users with placeholder emails
    'in_app_notifications': True,

    # Whether to log attempts to send emails to placeholder addresses
    'log_attempts': True,

    # Whether to track metrics for placeholder email notification attempts
    'track_metrics': True,
}

# Prefix for placeholder emails to make them easily identifiable
# Will be used as: {prefix}{username}@{domain}
LMS_PLACEHOLDER_EMAIL_PREFIX = ""

# Suffix to add before the domain for placeholder emails
# Will be used as: {username}{suffix}@{domain}
LMS_PLACEHOLDER_EMAIL_SUFFIX = ""

# Whether to allow users with placeholder emails to change their email through Zulip settings
# If True, users can update their email address in Zulip settings
# If False, email changes are only allowed through LMS sync or admin action
LMS_ALLOW_PLACEHOLDER_EMAIL_CHANGES = False

# Whether to include placeholder email users in email-based operations
# (like email invitations, password resets, etc.)
LMS_INCLUDE_PLACEHOLDER_USERS_IN_EMAIL_OPERATIONS = False

# Sync Configuration
# Progress update interval - how often to update sync progress (in number of records processed)
# Lower values provide more frequent updates but may impact performance
LMS_SYNC_PROGRESS_INTERVAL = 25  # Update every 25 users instead of default 100

# Batch size for database operations during sync
# Higher values improve performance but use more memory
LMS_SYNC_BATCH_SIZE = 500

# Whether to use bulk database operations for better performance
LMS_SYNC_USE_BULK_OPERATIONS = True