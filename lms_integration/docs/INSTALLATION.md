# Installation Guide

This guide provides step-by-step instructions for installing and configuring the LMS Activity Event Listener and Notification System.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation Steps](#installation-steps)
3. [Configuration](#configuration)
4. [Database Setup](#database-setup)
5. [Testing](#testing)
6. [Production Deployment](#production-deployment)
7. [Troubleshooting](#troubleshooting)

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
