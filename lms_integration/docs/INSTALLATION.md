# Installation Guide

This guide provides step-by-step instructions for installing and configuring the LMS Activity Event Listener and Notification System.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Admin Interface Setup](#admin-interface-setup)
6. [Testing](#testing)
7. [Production Deployment](#production-deployment)
8. [Troubleshooting](#troubleshooting)

## Prerequisites

### System Requirements

- **Zulip Server**: Version 8.0 or higher
- **Python**: Version 3.8 or higher
- **PostgreSQL**: Version 12 or higher
- **Django**: Version 3.2 or higher
- **Operating System**: Linux, macOS, or Windows

### Database Requirements

- **Zulip Database**: PostgreSQL database for Zulip
- **LMS Database**: External PostgreSQL database (read-only access)
- **Network Access**: Connection to LMS database

### Required Permissions

- **Database Access**: Read-only access to LMS database
- **Zulip Admin**: Administrative access to Zulip server
- **File System**: Write permissions for logs and temporary files

## Installation Steps

### Step 1: Verify Zulip Installation

Ensure Zulip is properly installed and running:

```bash
# Check Zulip status
sudo systemctl status zulip

# Check Zulip version
python manage.py --version
```

### Step 2: Enable LMS Integration

The LMS integration should already be enabled in your Zulip installation. Verify this:

```python
# Check if LMS integration is enabled
python manage.py shell
>>> from django.conf import settings
>>> print('lms_integration' in settings.INSTALLED_APPS)
```

### Step 3: Configure Database Access

Configure access to the external LMS database:

```python
# In your Zulip settings (e.g., /etc/zulip/settings.py)
DATABASES = {
    'default': {
        # Your existing Zulip database configuration
    },
    'lms_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'lms_production',
        'USER': 'lms_readonly',
        'PASSWORD': 'your_lms_password',
        'HOST': 'lms.example.com',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 2,
        },
    }
}

# Database router for LMS integration
DATABASE_ROUTERS = ['lms_integration.db_router.LMSRouter']
```

### Step 4: Run Database Migrations

Create the necessary database tables:

```bash
# Run migrations for LMS integration
python manage.py migrate lms_integration

# Verify migrations
python manage.py showmigrations lms_integration
```

### Step 5: Configure LMS Activity Monitoring

Enable and configure the LMS activity monitoring:

```python
# In your Zulip settings
LMS_ACTIVITY_MONITOR_ENABLED = True
LMS_ACTIVITY_POLL_INTERVAL = 60  # seconds
LMS_NOTIFY_MENTORS_ENABLED = True
LMS_EVENT_TYPES_TO_MONITOR = [
    'exam_started', 'exam_completed', 'exam_failed', 'exam_passed',
    'content_started', 'content_completed', 'content_watched'
]
```

### Step 6: Test the Installation

Verify the installation is working:

```bash
# Test the management command
python manage.py monitor_lms_activities --help

# Test database connectivity
python manage.py monitor_lms_activities --stats

# Test event processing
python manage.py monitor_lms_activities --once --verbose
```

## Configuration

### Basic Configuration

#### Enable Monitoring

```python
# Enable LMS activity monitoring
LMS_ACTIVITY_MONITOR_ENABLED = True
```

#### Configure Polling

```python
# Set polling interval (seconds)
LMS_ACTIVITY_POLL_INTERVAL = 60

# Minimum recommended: 30 seconds
# Maximum recommended: 300 seconds (5 minutes)
```

#### Configure Notifications

```python
# Enable mentor notifications
LMS_NOTIFY_MENTORS_ENABLED = True
```

#### Configure Event Types

```python
# Configure which event types to monitor
LMS_EVENT_TYPES_TO_MONITOR = [
    'exam_started',      # Student starts an exam
    'exam_completed',    # Student completes an exam
    'exam_failed',       # Student fails an exam
    'exam_passed',       # Student passes an exam
    'content_started',   # Student starts content
    'content_completed', # Student completes content
    'content_watched',   # Student watches content
]
```

### Advanced Configuration

#### Custom Polling Intervals

```python
# Different intervals for different environments
if PRODUCTION:
    LMS_ACTIVITY_POLL_INTERVAL = 60
else:
    LMS_ACTIVITY_POLL_INTERVAL = 30
```

#### Custom Event Types

```python
# Monitor only specific event types
LMS_EVENT_TYPES_TO_MONITOR = [
    'exam_passed',
    'exam_failed',
    'content_completed'
]
```

#### Database Connection Settings

```python
# Advanced database configuration
DATABASES = {
    'lms_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'lms_production',
        'USER': 'lms_readonly',
        'PASSWORD': 'your_lms_password',
        'HOST': 'lms.example.com',
        'PORT': '5432',
        'OPTIONS': {
            'connect_timeout': 2,
            'sslmode': 'require',
        },
        'CONN_MAX_AGE': 60,
    }
}
```

### Environment Variables

You can also configure the system using environment variables:

```bash
# Set environment variables
export LMS_ACTIVITY_MONITOR_ENABLED=true
export LMS_ACTIVITY_POLL_INTERVAL=60
export LMS_NOTIFY_MENTORS_ENABLED=true

# LMS Database configuration
export LMS_DB_NAME=lms_production
export LMS_DB_USER=lms_readonly
export LMS_DB_PASSWORD=your_lms_password
export LMS_DB_HOST=lms.example.com
export LMS_DB_PORT=5432
```

## Database Setup

### LMS Database Requirements

The external LMS database must have the following tables:

- `students` - Student information
- `mentors` - Mentor information
- `attempts` - Exam attempts
- `content_attempts` - Content interaction attempts
- `_MentorToStudent` - Mentor-student relationships

### Database Permissions

The LMS database user must have:

- **SELECT** permissions on all required tables
- **READ** access to the database
- **NO WRITE** permissions (read-only access)

### Test Database Connectivity

```python
# Test LMS database connectivity
python manage.py shell
>>> from lms_integration.models import Students
>>> student_count = Students.objects.using('lms_db').count()
>>> print(f"Students in LMS: {student_count}")

# Test mentor-student relationships
>>> from lms_integration.models import Mentortostudent
>>> relationship_count = Mentortostudent.objects.using('lms_db').count()
>>> print(f"Mentor-student relationships: {relationship_count}")
```

### Database Indexes

The system automatically creates optimized indexes:

```sql
-- Indexes created automatically
CREATE INDEX lms_activit_student_c7a329_idx ON lms_activity_events (student_id);
CREATE INDEX lms_activit_event_t_ff9bbf_idx ON lms_activity_events (event_type);
CREATE INDEX lms_activit_timesta_bcc866_idx ON lms_activity_events (timestamp);
CREATE INDEX lms_activit_process_19da29_idx ON lms_activity_events (processed_for_ai);
```

## Admin Interface Setup

The LMS Integration system includes a comprehensive admin interface that provides web-based management and monitoring capabilities.

### Frontend Dependencies

Install required frontend dependencies:

```bash
# Navigate to Zulip root directory
cd /srv/zulip

# Install TypeScript dependencies (if not already installed)
npm install

# Build frontend assets
npm run build:dev
```

### Template Integration

The admin interface is automatically integrated into Zulip's settings panel. Ensure the following files are properly installed:

#### Backend Templates
```bash
# Verify admin template exists
ls -la web/templates/settings/lms_integration_admin.hbs

# Verify main settings template includes LMS integration
grep -n "lms_integration" web/templates/settings_overlay.hbs
```

#### Frontend Assets
```bash
# Verify TypeScript module exists
ls -la web/src/settings_lms_integration.ts

# Verify integration in admin.ts
grep -n "lms_integration" web/src/admin.ts
```

### Access Configuration

#### Administrator Permissions

Ensure the admin interface is accessible to administrators:

```python
# In your Zulip settings (zproject/settings.py)
# Verify LMS integration is enabled in INSTALLED_APPS
INSTALLED_APPS = [
    # ... other apps
    'lms_integration',
    # ... rest of apps
]

# Admin interface settings
LMS_ADMIN_INTERFACE_ENABLED = True
```

#### URL Configuration

The admin interface routes are automatically included when LMS integration is enabled:

```python
# Verify in lms_integration/urls.py
urlpatterns = [
    # Admin API endpoints
    path('api/v1/lms/admin/', include('lms_integration.admin_urls')),
    # ... other patterns
]
```

### Initial Admin Setup

#### 1. Access the Admin Interface

1. Log into Zulip as an administrator
2. Click the gear icon (⚙️) in the top navigation
3. Select "Organization settings"
4. Click the "LMS Integration" tab

If the tab doesn't appear, verify:
- LMS integration is properly installed
- Your account has administrator privileges
- Frontend assets have been built

#### 2. Initial Configuration

Complete the initial setup through the admin interface:

##### Database Configuration
1. Navigate to the "Configuration" tab
2. Enter LMS database connection details:
   - **Host**: Your LMS database hostname
   - **Port**: Database port (usually 5432)
   - **Database Name**: LMS database name
   - **Username**: Read-only database user
   - **Password**: Database password

3. Click "Test Database Connection" to verify connectivity

##### System Settings
1. Enable LMS Integration: ✅ Checked
2. Set Poll Interval: 60 seconds (recommended)
3. Enable Activity Monitoring: ✅ Checked
4. Enable Mentor Notifications: ✅ Checked

#### 3. Verify Admin Interface Functionality

##### Dashboard Test
1. Navigate to the "Dashboard" tab
2. Verify status badge shows "Connected" (green)
3. Check that statistics load properly
4. Confirm last sync and activity times are displayed

##### User Sync Test
1. Navigate to the "User Sync" tab
2. Select "Incremental" sync type
3. Click "Start Sync" button
4. Monitor progress in real-time
5. Verify sync completion statistics

##### Activity Monitoring Test
1. Navigate to the "Activity Monitoring" tab
2. Click "Poll Activities" button
3. Verify events are detected and displayed
4. Test event details modal functionality

### Admin Interface Customization

#### Branding and Styling

Customize the admin interface appearance:

```css
/* Add to web/styles/admin.css */
.lms-integration-admin {
    /* Custom styling for LMS admin interface */
    --primary-color: #your-brand-color;
}

.lms-status-badge.connected {
    background-color: var(--success-color);
}

.lms-integration-tabs .nav-link.active {
    border-bottom: 2px solid var(--primary-color);
}
```

#### Feature Configuration

Control which admin features are available:

```python
# In your settings.py
LMS_ADMIN_FEATURES = {
    'dashboard': True,
    'user_sync': True,
    'activity_monitoring': True,
    'batch_management': True,
    'configuration': True,
    'logs': True,
}

# Disable specific features if needed
LMS_ADMIN_FEATURES['batch_management'] = False
```

### Security Configuration

#### Admin Access Control

Ensure proper access control for the admin interface:

```python
# In lms_integration/views.py (already implemented)
@require_http_methods(["GET"])
@admin_required
def admin_dashboard(request):
    # Admin interface views require administrator privileges
    pass
```

#### API Security

The admin REST API includes security measures:

- **Authentication Required**: All endpoints require valid administrator authentication
- **CSRF Protection**: POST requests include CSRF token validation
- **Rate Limiting**: API calls are rate-limited to prevent abuse
- **Input Validation**: All input parameters are validated and sanitized

#### Audit Logging

Admin actions are automatically logged:

```python
# Verify audit logging is enabled
LMS_ADMIN_AUDIT_LOGGING = True

# Check audit logs
python manage.py shell
>>> from lms_integration.models import LMSEventLog
>>> # View recent admin actions
>>> logs = LMSEventLog.objects.filter(source='admin').order_by('-created_at')[:10]
```

### Performance Optimization

#### Database Optimization

Ensure optimal database performance for the admin interface:

```sql
-- Add additional indexes for admin queries
CREATE INDEX lms_events_admin_dashboard_idx ON lms_activity_events (created_at, event_type);
CREATE INDEX lms_sync_history_idx ON lms_sync_history (started_at);
CREATE INDEX lms_logs_admin_idx ON lms_event_logs (processed_at, error_message);
```

#### Caching Configuration

Enable caching for improved admin interface performance:

```python
# In your settings.py
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}

# LMS admin interface caching
LMS_ADMIN_CACHE_TIMEOUT = 300  # 5 minutes
```

#### Frontend Optimization

Optimize frontend performance:

```javascript
// Ensure admin interface uses efficient loading
// Already implemented in settings_lms_integration.ts
const debounce = (func, delay) => {
    // Debounced search to reduce API calls
};
```

### Troubleshooting Admin Interface Issues

#### Common Setup Issues

**Admin Tab Not Visible**
```bash
# Check if LMS integration is properly installed
python manage.py shell -c "import lms_integration; print('LMS Integration installed')"

# Verify admin user permissions
python manage.py shell -c "
from django.contrib.auth.models import User
user = User.objects.get(email='your-admin@example.com')
print(f'Is superuser: {user.is_superuser}')
print(f'Is staff: {user.is_staff}')
"
```

**Frontend Assets Not Loading**
```bash
# Rebuild frontend assets
npm run build:dev

# Check for TypeScript compilation errors
npm run lint

# Verify admin.ts includes LMS integration
grep -n "lms_integration" web/src/admin.ts
```

**Database Connection Issues**
```bash
# Test database connection manually
python manage.py shell -c "
from django.db import connections
db = connections['lms_db']
cursor = db.cursor()
cursor.execute('SELECT 1')
print('LMS database connection successful')
"
```

## Testing

### Unit Tests

Run the test suite to verify everything is working:

```bash
# Run all tests
python manage.py test lms_integration

# Run specific test modules
python manage.py test lms_integration.tests.test_message_formatter
python manage.py test lms_integration.tests.test_activity_monitor
python manage.py test lms_integration.tests.test_event_listener
```

### Integration Tests

Test the complete system:

```bash
# Test management command
python manage.py monitor_lms_activities --once --verbose

# Test statistics
python manage.py monitor_lms_activities --stats

# Test event processing
python manage.py monitor_lms_activities --process-pending
```

### Manual Testing

#### Test Event Creation

```python
# Create a test event
python manage.py shell
>>> from lms_integration.models import LMSActivityEvent
>>> from django.utils import timezone
>>> 
>>> event = LMSActivityEvent.objects.create(
...     event_type='exam_started',
...     student_id=123,
...     student_username='test_student',
...     activity_id=456,
...     activity_title='Test Exam',
...     timestamp=timezone.now()
... )
>>> print(f"Event created: {event.event_id}")
```

#### Test Notification System

```python
# Test notification system
>>> from lms_integration.event_listeners import LMSActivityEventHandler
>>> handler = LMSActivityEventHandler()
>>> stats = handler.get_event_stats()
>>> print(f"Total events: {stats['total_events']}")
>>> print(f"Processed events: {stats['processed_events']}")
```

## Production Deployment

### Systemd Service

Create a systemd service for the monitoring system:

```ini
# /etc/systemd/system/zulip-lms-monitor.service
[Unit]
Description=Zulip LMS Activity Monitor
After=zulip.target
Requires=zulip.target

[Service]
Type=simple
User=zulip
Group=zulip
WorkingDirectory=/srv/zulip
ExecStart=/srv/zulip/.venv/bin/python manage.py monitor_lms_activities --daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
# Enable the service
sudo systemctl enable zulip-lms-monitor

# Start the service
sudo systemctl start zulip-lms-monitor

# Check status
sudo systemctl status zulip-lms-monitor
```

### Logging Configuration

Configure logging for production:

```python
# In your Zulip settings
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'lms_file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/zulip/lms_activity.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'lms_integration': {
            'handlers': ['lms_file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
}
```

### Monitoring and Alerting

Set up monitoring for the system:

```bash
# Check system status
python manage.py monitor_lms_activities --stats

# Monitor logs
tail -f /var/log/zulip/lms_activity.log

# Check service status
sudo systemctl status zulip-lms-monitor
```

### Backup and Recovery

#### Database Backup

```bash
# Backup Zulip database
pg_dump zulip_production > zulip_backup.sql

# Backup LMS activity events
pg_dump -t lms_activity_events -t lms_event_logs zulip_production > lms_events_backup.sql
```

#### Recovery Procedures

```bash
# Restore from backup
psql zulip_production < zulip_backup.sql

# Restore LMS events
psql zulip_production < lms_events_backup.sql
```

## Troubleshooting

### Common Installation Issues

#### Database Connection Failed

```bash
# Check database connectivity
psql -h lms.example.com -p 5432 -U lms_readonly -d lms_production

# Test from Django
python manage.py shell
>>> from django.db import connections
>>> conn = connections['lms_db']
>>> conn.ensure_connection()
```

#### Migration Issues

```bash
# Check migration status
python manage.py showmigrations lms_integration

# Run migrations
python manage.py migrate lms_integration

# Reset migrations if needed (CAUTION: This will delete data)
python manage.py migrate lms_integration zero
python manage.py migrate lms_integration
```

#### Permission Issues

```bash
# Check file permissions
ls -la /srv/zulip/lms_integration/

# Check database permissions
psql -h lms.example.com -U lms_readonly -d lms_production -c "\dt"
```

### Verification Checklist

- [ ] Zulip server is running
- [ ] LMS integration is enabled
- [ ] Database migrations completed
- [ ] LMS database connectivity works
- [ ] Management command runs without errors
- [ ] Statistics command shows data
- [ ] Test events can be created
- [ ] Notifications can be sent

### Getting Help

If you encounter issues:

1. **Check Logs**: Review system logs for error messages
2. **Run Diagnostics**: Use the troubleshooting guide
3. **Check Configuration**: Verify all settings are correct
4. **Contact Support**: Reach out to the development team

### Useful Commands

```bash
# Check system status
python manage.py monitor_lms_activities --stats

# Test connectivity
python manage.py monitor_lms_activities --once --verbose

# Check database
python manage.py dbshell

# Run tests
python manage.py test lms_integration

# Check migrations
python manage.py showmigrations lms_integration
```

## Next Steps

After successful installation:

1. **Configure Monitoring**: Set up monitoring and alerting
2. **Test Notifications**: Verify mentor notifications work
3. **Monitor Performance**: Check system performance
4. **Set Up Backups**: Configure backup procedures
5. **Document Configuration**: Document your specific configuration

## Support

For additional help:

- **Documentation**: Check the API documentation
- **Troubleshooting**: Use the troubleshooting guide
- **Logs**: Review system logs for errors
- **Community**: Reach out to the Zulip community
- **Support**: Contact the development team

