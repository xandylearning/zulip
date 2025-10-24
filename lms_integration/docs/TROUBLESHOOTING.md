# Troubleshooting Guide

This guide helps you diagnose and resolve common issues with the LMS Activity Event Listener and Notification System.

## Table of Contents

1. [Common Issues](#common-issues)
2. [Database Issues](#database-issues)
3. [Notification Issues](#notification-issues)
4. [Performance Issues](#performance-issues)
5. [Configuration Issues](#configuration-issues)
6. [Debugging Tools](#debugging-tools)
7. [Log Analysis](#log-analysis)
8. [Recovery Procedures](#recovery-procedures)

## Common Issues

### System Not Starting

#### Symptoms
- Management command fails to start
- Error messages about missing modules
- Database connection errors

#### Solutions

1. **Check Dependencies**
   ```bash
   # Verify all required packages are installed
   pip list | grep -E "(django|psycopg2|zulip)"
   ```

2. **Check Database Configuration**
   ```python
   # Verify database settings
   python manage.py dbshell
   ```

3. **Check LMS Integration**
   ```bash
   # Verify LMS integration is enabled
   python manage.py shell
   >>> from django.conf import settings
   >>> print(settings.LMS_ACTIVITY_MONITOR_ENABLED)
   ```

#### Debug Steps
```bash
# Run with verbose logging
python manage.py monitor_lms_activities --once --verbose

# Check system status
python manage.py monitor_lms_activities --stats
```

### No Events Being Detected

#### Symptoms
- System runs but no events are created
- Statistics show 0 total events
- No activity in logs

#### Solutions

1. **Check LMS Database Connection**
   ```python
   # Test LMS database connection
   python manage.py shell
   >>> from lms_integration.models import Students
   >>> Students.objects.using('lms_db').count()
   ```

2. **Verify Polling Configuration**
   ```python
   # Check polling settings
   from django.conf import settings
   print(f"Monitor enabled: {settings.LMS_ACTIVITY_MONITOR_ENABLED}")
   print(f"Poll interval: {settings.LMS_ACTIVITY_POLL_INTERVAL}")
   ```

3. **Check Event Types**
   ```python
   # Verify event types are configured
   print(settings.LMS_EVENT_TYPES_TO_MONITOR)
   ```

#### Debug Steps
```bash
# Run with debug logging
python manage.py monitor_lms_activities --once --verbose

# Check LMS database directly
python manage.py shell
>>> from lms_integration.models import Attempts
>>> Attempts.objects.using('lms_db').filter(date__gte=timezone.now() - timedelta(hours=1)).count()
```

### Notifications Not Being Sent

#### Symptoms
- Events are created but no notifications sent
- Statistics show 0 notifications sent
- No error messages in logs

#### Solutions

1. **Check Notification Settings**
   ```python
   # Verify notification settings
   from django.conf import settings
   print(f"Notifications enabled: {settings.LMS_NOTIFY_MENTORS_ENABLED}")
   ```

2. **Verify Mentor-Student Relationships**
   ```python
   # Check mentor-student relationships
   from lms_integration.models import Mentortostudent
   Mentortostudent.objects.using('lms_db').count()
   ```

3. **Check Zulip User Mapping**
   ```python
   # Test user mapping
   from lms_integration.lib.user_mapping import UserMapper
   mapper = UserMapper()
   user = mapper.get_zulip_user_for_mentor(mentor_id)
   print(f"Mentor user found: {user is not None}")
   ```

#### Debug Steps
```bash
# Process pending events manually
python manage.py monitor_lms_activities --process-pending --verbose

# Check notification status
python manage.py shell
>>> from lms_integration.models import LMSEventLog
>>> LMSEventLog.objects.filter(notification_sent=True).count()
```

## Database Issues

### LMS Database Connection Failed

#### Symptoms
- Error: "connection to server at 'localhost' failed"
- Error: "password authentication failed"
- Error: "database does not exist"

#### Solutions

1. **Check Database Credentials**
   ```python
   # Verify database configuration
   from django.conf import settings
   db_config = settings.DATABASES['lms_db']
   print(f"Host: {db_config['HOST']}")
   print(f"Port: {db_config['PORT']}")
   print(f"Name: {db_config['NAME']}")
   print(f"User: {db_config['USER']}")
   ```

2. **Test Database Connection**
   ```bash
   # Test connection manually
   psql -h lms.example.com -p 5432 -U lms_readonly -d lms_production
   ```

3. **Check Network Connectivity**
   ```bash
   # Test network connectivity
   ping lms.example.com
   telnet lms.example.com 5432
   ```

#### Debug Steps
```python
# Test database connection in Django
python manage.py shell
>>> from django.db import connections
>>> conn = connections['lms_db']
>>> conn.ensure_connection()
```

### Migration Issues

#### Symptoms
- Error: "table does not exist"
- Error: "column does not exist"
- Error: "migration failed"

#### Solutions

1. **Check Migration Status**
   ```bash
   # Check migration status
   python manage.py showmigrations lms_integration
   ```

2. **Run Migrations**
   ```bash
   # Run pending migrations
   python manage.py migrate lms_integration
   ```

3. **Reset Migrations (if needed)**
   ```bash
   # Reset migrations (CAUTION: This will delete data)
   python manage.py migrate lms_integration zero
   python manage.py migrate lms_integration
   ```

#### Debug Steps
```bash
# Check database schema
python manage.py dbshell
\dt lms_activity_events
\dt lms_event_logs
```

### Data Integrity Issues

#### Symptoms
- Error: "foreign key constraint failed"
- Error: "unique constraint failed"
- Data corruption

#### Solutions

1. **Check Data Integrity**
   ```python
   # Check for orphaned records
   from lms_integration.models import LMSActivityEvent, LMSEventLog
   orphaned_events = LMSActivityEvent.objects.filter(
       event_id__in=LMSEventLog.objects.values_list('event_id', flat=True)
   )
   ```

2. **Clean Up Data**
   ```python
   # Remove orphaned records
   orphaned_logs = LMSEventLog.objects.filter(
       event__isnull=True
   )
   orphaned_logs.delete()
   ```

#### Debug Steps
```python
# Check data integrity
python manage.py shell
>>> from lms_integration.models import LMSActivityEvent
>>> LMSActivityEvent.objects.filter(student_id__isnull=True).count()
```

## Notification Issues

### No Recipients Found

#### Symptoms
- Warning: "No notification recipients found"
- Events created but no notifications sent
- Error in event logs

#### Solutions

1. **Check Mentor-Student Relationships**
   ```python
   # Verify relationships exist
   from lms_integration.models import Mentortostudent
   relationships = Mentortostudent.objects.using('lms_db').count()
   print(f"Mentor-student relationships: {relationships}")
   ```

2. **Check Zulip User Accounts**
   ```python
   # Check if mentors have Zulip accounts
   from lms_integration.lib.user_mapping import UserMapper
   mapper = UserMapper()
   for mentor in Mentors.objects.using('lms_db')[:5]:
       user = mapper.get_zulip_user_for_mentor(mentor.user_id)
       print(f"Mentor {mentor.username}: {user is not None}")
   ```

3. **Verify Email Matching**
   ```python
   # Check email matching
   from lms_integration.models import Mentors
   from zerver.models import UserProfile
   mentor = Mentors.objects.using('lms_db').first()
   if mentor.email:
       zulip_user = UserProfile.objects.filter(email=mentor.email).first()
       print(f"Email match: {zulip_user is not None}")
   ```

#### Debug Steps
```python
# Debug user mapping
python manage.py shell
>>> from lms_integration.lib.user_mapping import UserMapper
>>> mapper = UserMapper()
>>> recipients = mapper.get_notification_recipients(student_id=123)
>>> print(f"Recipients: {len(recipients)}")
```

### Notification Delivery Failed

#### Symptoms
- Error: "Failed to send notification"
- Error in event logs
- Notifications not received

#### Solutions

1. **Check Zulip Configuration**
   ```python
   # Verify Zulip settings
   from django.conf import settings
   print(f"Zulip configured: {hasattr(settings, 'EXTERNAL_HOST')}")
   ```

2. **Test Message Sending**
   ```python
   # Test message sending
   from zerver.actions.message_send import internal_send_private_message
   from zerver.models import UserProfile
   
   user = UserProfile.objects.first()
   try:
       message_id = internal_send_private_message(
           sender=user,
           recipient=user,
           content="Test message",
           realm=user.realm
       )
       print(f"Message sent: {message_id}")
   except Exception as e:
       print(f"Error: {e}")
   ```

3. **Check User Permissions**
   ```python
   # Check user permissions
   user = UserProfile.objects.first()
   print(f"User active: {user.is_active}")
   print(f"User realm: {user.realm}")
   ```

#### Debug Steps
```bash
# Test notification system
python manage.py shell
>>> from lms_integration.event_listeners import LMSActivityEventHandler
>>> handler = LMSActivityEventHandler()
>>> stats = handler.get_event_stats()
>>> print(f"Notifications sent: {stats['events_with_notifications']}")
```

### Message Formatting Issues

#### Symptoms
- Malformed notification messages
- Missing information in messages
- Encoding errors

#### Solutions

1. **Check Message Formatter**
   ```python
   # Test message formatting
   from lms_integration.lib.message_formatter import MessageFormatter
   from lms_integration.models import LMSActivityEvent
   
   formatter = MessageFormatter()
   event = LMSActivityEvent.objects.first()
   if event:
       message = formatter.format_notification_message(event)
       print(f"Message: {message}")
   ```

2. **Check Data Quality**
   ```python
   # Check event data quality
   from lms_integration.models import LMSActivityEvent
   event = LMSActivityEvent.objects.first()
   print(f"Event type: {event.event_type}")
   print(f"Student: {event.student_username}")
   print(f"Activity: {event.activity_title}")
   print(f"Metadata: {event.activity_metadata}")
   ```

#### Debug Steps
```python
# Debug message formatting
python manage.py shell
>>> from lms_integration.lib.message_formatter import MessageFormatter
>>> formatter = MessageFormatter()
>>> # Test with sample data
>>> sample_event = LMSActivityEvent(
...     event_type='exam_passed',
...     student_username='test_user',
...     activity_title='Test Exam',
...     activity_metadata={'score': 85, 'percentage': 85}
... )
>>> message = formatter.format_notification_message(sample_event)
>>> print(message)
```

## Performance Issues

### Slow Database Queries

#### Symptoms
- Long response times
- Database timeouts
- High CPU usage

#### Solutions

1. **Check Database Indexes**
   ```sql
   -- Check indexes on LMS tables
   \d lms_activity_events
   \d lms_event_logs
   ```

2. **Optimize Queries**
   ```python
   # Use select_related for foreign keys
   events = LMSActivityEvent.objects.select_related('event').filter(
       processed_for_ai=False
   )
   ```

3. **Check Query Performance**
   ```python
   # Enable query logging
   from django.db import connection
   from django.conf import settings
   
   settings.DEBUG = True
   # Run your queries
   print(connection.queries)
   ```

#### Debug Steps
```bash
# Check database performance
python manage.py shell
>>> from django.db import connection
>>> from lms_integration.models import LMSActivityEvent
>>> LMSActivityEvent.objects.filter(processed_for_ai=False).count()
>>> print(f"Queries: {len(connection.queries)}")
```

### Memory Usage Issues

#### Symptoms
- High memory usage
- Out of memory errors
- Slow performance

#### Solutions

1. **Check Memory Usage**
   ```python
   # Monitor memory usage
   import psutil
   import os
   
   process = psutil.Process(os.getpid())
   print(f"Memory usage: {process.memory_info().rss / 1024 / 1024:.2f} MB")
   ```

2. **Optimize Data Processing**
   ```python
   # Process events in batches
   batch_size = 100
   events = LMSActivityEvent.objects.filter(processed_for_ai=False)[:batch_size]
   ```

3. **Clear Caches**
   ```python
   # Clear user mapping cache
   from lms_integration.lib.user_mapping import UserMapper
   mapper = UserMapper()
   mapper.clear_cache()
   ```

#### Debug Steps
```python
# Monitor memory usage
python manage.py shell
>>> import psutil
>>> import os
>>> process = psutil.Process(os.getpid())
>>> print(f"Memory: {process.memory_info().rss / 1024 / 1024:.2f} MB")
```

### High CPU Usage

#### Symptoms
- High CPU usage
- Slow response times
- System lag

#### Solutions

1. **Check Polling Frequency**
   ```python
   # Reduce polling frequency
   LMS_ACTIVITY_POLL_INTERVAL = 120  # Increase from 60 to 120 seconds
   ```

2. **Optimize Event Processing**
   ```python
   # Process events in batches
   batch_size = 50
   events = LMSActivityEvent.objects.filter(processed_for_ai=False)[:batch_size]
   ```

3. **Check for Infinite Loops**
   ```python
   # Add logging to detect infinite loops
   import logging
   logger = logging.getLogger(__name__)
   logger.info(f"Processing {len(events)} events")
   ```

#### Debug Steps
```bash
# Monitor CPU usage
top -p $(pgrep -f "monitor_lms_activities")
```

## Configuration Issues

### Settings Not Applied

#### Symptoms
- Settings changes not taking effect
- Default values being used
- Configuration errors

#### Solutions

1. **Check Settings File**
   ```python
   # Verify settings are loaded
   from django.conf import settings
   print(f"Monitor enabled: {getattr(settings, 'LMS_ACTIVITY_MONITOR_ENABLED', 'Not set')}")
   ```

2. **Reload Settings**
   ```bash
   # Restart the monitoring process
   pkill -f "monitor_lms_activities"
   python manage.py monitor_lms_activities --daemon
   ```

3. **Check Environment Variables**
   ```bash
   # Check environment variables
   env | grep LMS
   ```

#### Debug Steps
```python
# Check all LMS settings
python manage.py shell
>>> from django.conf import settings
>>> lms_settings = [attr for attr in dir(settings) if attr.startswith('LMS_')]
>>> for setting in lms_settings:
...     print(f"{setting}: {getattr(settings, setting)}")
```

### Database Router Issues

#### Symptoms
- Error: "database router failed"
- Wrong database being used
- Migration errors

#### Solutions

1. **Check Database Router**
   ```python
   # Verify router configuration
   from django.conf import settings
   print(f"Database routers: {settings.DATABASE_ROUTERS}")
   ```

2. **Test Router**
   ```python
   # Test router functionality
   from lms_integration.db_router import LMSRouter
   router = LMSRouter()
   print(f"LMS models: {router.lms_models}")
   print(f"Zulip models: {router.zulip_managed_models}")
   ```

3. **Check Model Routing**
   ```python
   # Test model routing
   from lms_integration.models import LMSActivityEvent
   from django.db import connections
   
   # Check which database is used
   print(f"Database: {LMSActivityEvent._meta.db_table}")
   ```

#### Debug Steps
```python
# Test database routing
python manage.py shell
>>> from lms_integration.models import LMSActivityEvent
>>> from django.db import connections
>>> print(f"Default DB: {connections['default'].alias}")
>>> print(f"LMS DB: {connections['lms_db'].alias}")
```

## Debugging Tools

### Log Analysis

#### Enable Debug Logging
```python
# Configure debug logging
import logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

#### Check Log Files
```bash
# Check system logs
tail -f /var/log/zulip/lms_activity.log
tail -f /var/log/zulip/error.log
```

#### Analyze Logs
```bash
# Search for errors
grep -i "error" /var/log/zulip/lms_activity.log
grep -i "failed" /var/log/zulip/lms_activity.log
```

### Statistics and Monitoring

#### Get System Statistics
```bash
# Get system statistics
python manage.py monitor_lms_activities --stats
```

#### Check Event Status
```python
# Check event status
from lms_integration.models import LMSActivityEvent, LMSEventLog

# Total events
total = LMSActivityEvent.objects.count()
print(f"Total events: {total}")

# Processed events
processed = LMSActivityEvent.objects.filter(processed_for_ai=True).count()
print(f"Processed events: {processed}")

# Pending events
pending = LMSActivityEvent.objects.filter(processed_for_ai=False).count()
print(f"Pending events: {pending}")

# Events with notifications
notifications = LMSEventLog.objects.filter(notification_sent=True).count()
print(f"Notifications sent: {notifications}")

# Events with errors
errors = LMSEventLog.objects.exclude(error_message__isnull=True).exclude(error_message='').count()
print(f"Events with errors: {errors}")
```

#### Monitor System Health
```python
# Monitor system health
def health_check():
    try:
        # Check database connectivity
        LMSActivityEvent.objects.count()
        
        # Check LMS database connectivity
        from lms_integration.models import Students
        Students.objects.using('lms_db').count()
        
        return True
    except Exception as e:
        print(f"Health check failed: {e}")
        return False

# Run health check
health_check()
```

### Performance Monitoring

#### Monitor Database Performance
```python
# Monitor database performance
from django.db import connection
from django.conf import settings

# Enable query logging
settings.DEBUG = True

# Run queries
from lms_integration.models import LMSActivityEvent
events = LMSActivityEvent.objects.filter(processed_for_ai=False)

# Check query count
print(f"Queries executed: {len(connection.queries)}")
for query in connection.queries:
    print(f"Query: {query['sql']}")
    print(f"Time: {query['time']}")
```

#### Monitor Memory Usage
```python
# Monitor memory usage
import psutil
import os

def monitor_memory():
    process = psutil.Process(os.getpid())
    memory_mb = process.memory_info().rss / 1024 / 1024
    print(f"Memory usage: {memory_mb:.2f} MB")
    
    # Check memory growth
    if memory_mb > 1000:  # 1GB threshold
        print("WARNING: High memory usage detected")

monitor_memory()
```

## Recovery Procedures

### Data Recovery

#### Recover from Database Corruption
```python
# Check for corrupted data
from lms_integration.models import LMSActivityEvent, LMSEventLog

# Find orphaned records
orphaned_logs = LMSEventLog.objects.filter(event__isnull=True)
print(f"Orphaned logs: {orphaned_logs.count()}")

# Clean up orphaned records
orphaned_logs.delete()
```

#### Recover from Migration Issues
```bash
# Reset migrations (CAUTION: This will delete data)
python manage.py migrate lms_integration zero
python manage.py migrate lms_integration
```

### System Recovery

#### Restart Monitoring System
```bash
# Stop monitoring
pkill -f "monitor_lms_activities"

# Clear caches
python manage.py shell
>>> from lms_integration.lib.user_mapping import UserMapper
>>> mapper = UserMapper()
>>> mapper.clear_cache()

# Restart monitoring
python manage.py monitor_lms_activities --daemon
```

#### Recover from Configuration Issues
```python
# Reset configuration
from django.conf import settings

# Check current settings
print(f"Monitor enabled: {getattr(settings, 'LMS_ACTIVITY_MONITOR_ENABLED', False)}")
print(f"Poll interval: {getattr(settings, 'LMS_ACTIVITY_POLL_INTERVAL', 60)}")
print(f"Notifications enabled: {getattr(settings, 'LMS_NOTIFY_MENTORS_ENABLED', True)}")

# Reset to defaults if needed
settings.LMS_ACTIVITY_MONITOR_ENABLED = True
settings.LMS_ACTIVITY_POLL_INTERVAL = 60
settings.LMS_NOTIFY_MENTORS_ENABLED = True
```

### Emergency Procedures

#### Stop All Monitoring
```bash
# Stop all monitoring processes
pkill -f "monitor_lms_activities"

# Verify no processes are running
ps aux | grep monitor_lms_activities
```

#### Clear All Data
```python
# Clear all event data (CAUTION: This will delete all data)
from lms_integration.models import LMSActivityEvent, LMSEventLog

# Delete all events
LMSActivityEvent.objects.all().delete()
LMSEventLog.objects.all().delete()
```

#### Reset System
```bash
# Reset the entire system
python manage.py migrate lms_integration zero
python manage.py migrate lms_integration
python manage.py monitor_lms_activities --daemon
```

## Getting Help

### Support Channels

1. **Check Logs**: Review system logs for error messages
2. **Run Diagnostics**: Use the debugging tools provided
3. **Check Documentation**: Review the API documentation
4. **Contact Support**: Reach out to the development team

### Useful Commands

```bash
# Check system status
python manage.py monitor_lms_activities --stats

# Run diagnostics
python manage.py monitor_lms_activities --once --verbose

# Check database
python manage.py dbshell

# Check migrations
python manage.py showmigrations lms_integration

# Run tests
python manage.py test lms_integration
```

### Reporting Issues

When reporting issues, include:

1. **Error Messages**: Full error messages and stack traces
2. **System Information**: OS, Python version, Django version
3. **Configuration**: Relevant settings and configuration
4. **Logs**: Relevant log entries
5. **Steps to Reproduce**: Detailed steps to reproduce the issue

### Common Solutions

1. **Restart the System**: Often resolves temporary issues
2. **Check Configuration**: Verify all settings are correct
3. **Clear Caches**: Clear user mapping and other caches
4. **Check Database**: Verify database connectivity and data integrity
5. **Review Logs**: Check logs for specific error messages
