# LMS Activity Event Listener API Documentation

This document provides comprehensive API documentation for the LMS Activity Event Listener and Notification System.

## Table of Contents

1. [Models API](#models-api)
2. [Activity Monitor API](#activity-monitor-api)
3. [Event Listener API](#event-listener-api)
4. [Message Formatter API](#message-formatter-api)
5. [User Mapper API](#user-mapper-api)
6. [Management Command API](#management-command-api)
7. [Database Queries](#database-queries)
8. [Configuration API](#configuration-api)

## Models API

### LMSActivityEvent

Core event storage model for LMS activities.

#### Fields

```python
class LMSActivityEvent(models.Model):
    event_id = models.AutoField(primary_key=True)
    event_type = models.CharField(max_length=50, choices=[...])
    student_id = models.IntegerField(help_text="Student ID from LMS database")
    student_username = models.CharField(max_length=255, blank=True, null=True)
    mentor_id = models.IntegerField(blank=True, null=True, help_text="Mentor ID from LMS database")
    mentor_username = models.CharField(max_length=255, blank=True, null=True)
    activity_id = models.IntegerField(help_text="Exam or content ID from LMS")
    activity_title = models.CharField(max_length=500, blank=True, null=True)
    activity_metadata = models.JSONField(blank=True, null=True, help_text="Additional data like scores, percentage, duration, etc.")
    timestamp = models.DateTimeField(help_text="When the activity occurred in LMS")
    created_at = models.DateTimeField(auto_now_add=True)
    processed_for_ai = models.BooleanField(default=False, help_text="Whether this event has been processed for AI analysis")
    zulip_user_id = models.IntegerField(blank=True, null=True, help_text="Zulip UserProfile ID if student has Zulip account")
```

#### Event Types

```python
EVENT_TYPE_CHOICES = [
    ('exam_started', 'Exam Started'),
    ('exam_completed', 'Exam Completed'),
    ('exam_failed', 'Exam Failed'),
    ('exam_passed', 'Exam Passed'),
    ('content_started', 'Content Started'),
    ('content_completed', 'Content Completed'),
    ('content_watched', 'Content Watched'),
]
```

#### Activity Metadata Structure

```python
# Exam events metadata
{
    "score": 85,
    "percentage": 85,
    "result": "pass",
    "time_taken": "45 minutes",
    "correct_answers": 17,
    "incorrect_answers": 3,
    "unanswered": 0,
    "percentile": 78.5,
    "speed": 1.2
}

# Content events metadata
{
    "content_type": "video",
    "state": "completed",
    "course_title": "Programming 101",
    "chapter_name": "Introduction to Python",
    "correct_answers": 5,
    "incorrect_answers": 1,
    "completed_on": "2024-01-15T14:30:00Z"
}
```

### LMSEventLog

Event processing audit trail model.

#### Fields

```python
class LMSEventLog(models.Model):
    event = models.OneToOneField(LMSActivityEvent, on_delete=models.CASCADE, primary_key=True)
    notification_sent = models.BooleanField(default=False)
    notification_message_id = models.IntegerField(blank=True, null=True, help_text="Zulip message ID of the notification sent to mentor")
    error_message = models.TextField(blank=True, null=True, help_text="Error details if processing failed")
    processed_at = models.DateTimeField(auto_now=True)
```

## Activity Monitor API

### ActivityMonitor Class

Main class for monitoring LMS activities.

#### Constructor

```python
def __init__(self, poll_interval: int = 60):
    """
    Initialize the activity monitor.
    
    Args:
        poll_interval: Polling interval in seconds
    """
```

#### Methods

##### poll_for_new_activities()

```python
def poll_for_new_activities(self) -> List[Dict]:
    """
    Poll LMS database for new activities since last poll.
    
    Returns:
        List of detected activity events
    """
```

##### process_activities()

```python
def process_activities(self) -> int:
    """
    Main processing method that polls for activities and creates events.
    
    Returns:
        Number of events created
    """
```

##### create_activity_event()

```python
def create_activity_event(self, event_data: Dict) -> Optional[LMSActivityEvent]:
    """
    Create LMSActivityEvent record in Zulip database.
    
    Args:
        event_data: Dictionary containing event data
        
    Returns:
        LMSActivityEvent instance or None if creation failed
    """
```

#### Event Data Structure

```python
event_data = {
    'event_type': 'exam_started',
    'student_id': 123,
    'student_username': 'john_doe',
    'mentor_id': 456,
    'mentor_username': 'mentor_smith',
    'activity_id': 789,
    'activity_title': 'Mathematics Final Exam',
    'activity_metadata': {
        'score': 85,
        'percentage': 85,
        'result': 'pass',
        'time_taken': '45 minutes'
    },
    'timestamp': datetime.now()
}
```

## Event Listener API

### LMSActivityEventHandler Class

Event handler for processing LMS activity events.

#### Constructor

```python
def __init__(self):
    """
    Initialize the event handler.
    """
```

#### Methods

##### handle_event()

```python
def handle_event(self, event_data: dict) -> None:
    """
    Handle LMS activity event.
    
    Args:
        event_data: Event data dictionary containing event_id
    """
```

##### process_pending_events()

```python
def process_pending_events(self) -> int:
    """
    Process all pending LMS activity events.
    
    Returns:
        Number of events processed
    """
```

##### get_event_stats()

```python
def get_event_stats(self) -> dict:
    """
    Get statistics about LMS activity events.
    
    Returns:
        Dictionary with event statistics
    """
```

#### Statistics Structure

```python
stats = {
    'total_events': 1234,
    'processed_events': 1200,
    'pending_events': 34,
    'events_with_notifications': 1180,
    'events_with_errors': 20
}
```

## Message Formatter API

### MessageFormatter Class

Formats notification messages for LMS activity events.

#### Constructor

```python
def __init__(self):
    """
    Initialize the message formatter.
    """
```

#### Methods

##### format_notification_message()

```python
def format_notification_message(self, event: LMSActivityEvent) -> str:
    """
    Format a notification message for an LMS activity event.
    
    Args:
        event: LMSActivityEvent instance
        
    Returns:
        Formatted message string
    """
```

##### format_summary_message()

```python
def format_summary_message(self, events: list, time_period: str = "recent") -> str:
    """
    Format a summary message for multiple events.
    
    Args:
        events: List of LMSActivityEvent instances
        time_period: Description of time period (e.g., "last hour", "today")
        
    Returns:
        Formatted summary message
    """
```

#### Message Examples

##### Exam Passed Message
```
🎉 **Exam Passed!**

**john_doe** has passed: **Mathematics Final Exam**
📊 **Score:** 85 | **Percentage:** 85% | **Result:** pass | **Time Taken:** 45 minutes
🎉 Congratulations to the student!
```

##### Content Completed Message
```
📚 **Content Completed**

**jane_smith** has completed: **Python Programming Tutorial**
📚 **Course:** Programming 101 | **Chapter:** Introduction to Python | **Type:** video
📅 Completed at: 2024-01-15 14:30:00
```

## User Mapper API

### UserMapper Class

Maps LMS users to Zulip UserProfiles for notifications.

#### Constructor

```python
def __init__(self):
    """
    Initialize the user mapper.
    """
```

#### Methods

##### get_zulip_user_for_student()

```python
def get_zulip_user_for_student(self, student_id: int) -> Optional[User]:
    """
    Get Zulip UserProfile for LMS student.
    
    Args:
        student_id: LMS student ID
        
    Returns:
        Zulip User instance or None if not found
    """
```

##### get_zulip_user_for_mentor()

```python
def get_zulip_user_for_mentor(self, mentor_id: int) -> Optional[User]:
    """
    Get Zulip UserProfile for LMS mentor.
    
    Args:
        mentor_id: LMS mentor ID
        
    Returns:
        Zulip User instance or None if not found
    """
```

##### get_mentor_for_student()

```python
def get_mentor_for_student(self, student_id: int) -> Optional[Tuple[int, str]]:
    """
    Get mentor information for a student.
    
    Args:
        student_id: LMS student ID
        
    Returns:
        Tuple of (mentor_id, mentor_username) or None if not found
    """
```

##### get_notification_recipients()

```python
def get_notification_recipients(self, student_id: int) -> list:
    """
    Get list of Zulip users who should receive notifications for a student.
    
    Args:
        student_id: LMS student ID
        
    Returns:
        List of Zulip User instances
    """
```

##### clear_cache()

```python
def clear_cache(self, student_id: Optional[int] = None, mentor_id: Optional[int] = None):
    """
    Clear user mapping cache.
    
    Args:
        student_id: Clear cache for specific student (optional)
        mentor_id: Clear cache for specific mentor (optional)
    """
```

##### get_mapping_stats()

```python
def get_mapping_stats(self) -> Dict[str, int]:
    """
    Get statistics about user mappings.
    
    Returns:
        Dictionary with mapping statistics
    """
```

## Management Command API

### monitor_lms_activities Command

Django management command for monitoring LMS activities.

#### Command Options

```bash
python manage.py monitor_lms_activities [OPTIONS]
```

##### Options

- `--interval INTERVAL`: Polling interval in seconds (default: 60)
- `--daemon`: Run as daemon (continuous monitoring)
- `--once`: Run once and exit
- `--process-pending`: Process pending events and exit
- `--stats`: Show event statistics and exit
- `--verbose`: Enable verbose logging

#### Usage Examples

```bash
# Run once to check for new activities
python manage.py monitor_lms_activities --once

# Run as daemon for continuous monitoring
python manage.py monitor_lms_activities --daemon --interval 30

# Process pending events
python manage.py monitor_lms_activities --process-pending

# Show statistics
python manage.py monitor_lms_activities --stats

# Enable verbose logging
python manage.py monitor_lms_activities --daemon --verbose
```

## Database Queries

### Common Queries

#### Get Unprocessed Events

```python
# Get events ready for AI processing
events = LMSActivityEvent.objects.filter(processed_for_ai=False)

# Get specific event types
exam_events = LMSActivityEvent.objects.filter(
    processed_for_ai=False,
    event_type__in=['exam_failed', 'exam_passed']
)
```

#### Get Student Activity History

```python
# Get student activity history
student_events = LMSActivityEvent.objects.filter(
    student_id=123,
    timestamp__gte=timezone.now() - timedelta(days=30)
).order_by('-timestamp')
```

#### Get Events by Time Range

```python
# Get events from last week
last_week = timezone.now() - timedelta(days=7)
events = LMSActivityEvent.objects.filter(
    timestamp__gte=last_week
).order_by('-timestamp')
```

#### Get Events with Errors

```python
# Get events that had processing errors
error_events = LMSEventLog.objects.exclude(
    error_message__isnull=True
).exclude(error_message='').select_related('event')
```

#### Batch Processing

```python
# Mark events as processed for AI
LMSActivityEvent.objects.filter(
    processed_for_ai=False,
    event_type__in=['exam_failed', 'content_started']
).update(processed_for_ai=True)
```

### Aggregation Queries

#### Event Counts by Type

```python
from django.db.models import Count

# Count events by type
event_counts = LMSActivityEvent.objects.values('event_type').annotate(
    count=Count('event_id')
).order_by('-count')
```

#### Student Activity Summary

```python
# Get student activity summary
student_summary = LMSActivityEvent.objects.filter(
    student_id=123
).aggregate(
    total_events=Count('event_id'),
    exam_events=Count('event_id', filter=Q(event_type__startswith='exam')),
    content_events=Count('event_id', filter=Q(event_type__startswith='content'))
)
```

## Configuration API

### Settings

#### Required Settings

```python
# Enable LMS activity monitoring
LMS_ACTIVITY_MONITOR_ENABLED = True

# Configure polling interval (seconds)
LMS_ACTIVITY_POLL_INTERVAL = 60

# Enable mentor notifications
LMS_NOTIFY_MENTORS_ENABLED = True

# Configure event types to monitor
LMS_EVENT_TYPES_TO_MONITOR = [
    'exam_started', 'exam_completed', 'exam_failed', 'exam_passed',
    'content_started', 'content_completed', 'content_watched'
]
```

#### Database Configuration

```python
# LMS database configuration (read-only)
DATABASES = {
    'lms_db': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'lms_production',
        'USER': 'lms_readonly',
        'PASSWORD': 'your_password',
        'HOST': 'lms.example.com',
        'PORT': '5432',
    }
}

# Database router for LMS integration
DATABASE_ROUTERS = ['lms_integration.db_router.LMSRouter']
```

### Environment Variables

```bash
# LMS Database Configuration
LMS_DB_NAME=lms_production
LMS_DB_USER=lms_readonly
LMS_DB_PASSWORD=your_password
LMS_DB_HOST=lms.example.com
LMS_DB_PORT=5432

# LMS Activity Monitoring
LMS_ACTIVITY_MONITOR_ENABLED=true
LMS_ACTIVITY_POLL_INTERVAL=60
LMS_NOTIFY_MENTORS_ENABLED=true
```

## Error Handling

### Common Exceptions

#### DatabaseConnectionError

```python
try:
    events = LMSActivityEvent.objects.filter(processed_for_ai=False)
except DatabaseError as e:
    logger.error(f"Database connection failed: {e}")
    # Handle database connection error
```

#### EventProcessingError

```python
try:
    event_handler.process_pending_events()
except Exception as e:
    logger.error(f"Event processing failed: {e}")
    # Handle event processing error
```

### Error Recovery

#### Automatic Retry

```python
# The system automatically retries failed operations
# with exponential backoff
```

#### Manual Recovery

```python
# Process failed events manually
failed_events = LMSEventLog.objects.exclude(
    error_message__isnull=True
).exclude(error_message='')

for event_log in failed_events:
    # Retry processing
    event_handler._process_event(event_log.event)
```

## Performance Optimization

### Database Indexes

The system includes optimized database indexes:

```python
# LMSActivityEvent indexes
indexes = [
    models.Index(fields=['student_id']),
    models.Index(fields=['event_type']),
    models.Index(fields=['timestamp']),
    models.Index(fields=['processed_for_ai']),
]
```

### Caching

```python
# User mapping is cached for performance
cache_key = f"lms_user_mapping_student_{student_id}"
cached_user = cache.get(cache_key)
```

### Batch Processing

```python
# Process events in batches for better performance
batch_size = 100
events = LMSActivityEvent.objects.filter(processed_for_ai=False)[:batch_size]
```

## Security Considerations

### Data Privacy

- Student data is handled according to privacy policies
- Personal information is not logged in plain text
- Access controls are enforced at the database level

### Authentication

- Uses Zulip's existing authentication system
- LMS database access is read-only
- Mentor notifications require valid Zulip accounts

### Rate Limiting

- Built-in rate limiting for database queries
- Configurable polling intervals
- Automatic backoff on errors

## Monitoring and Logging

### Logging Levels

```python
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

### Statistics

```python
# Get system statistics
stats = event_handler.get_event_stats()
print(f"Total events: {stats['total_events']}")
print(f"Processed events: {stats['processed_events']}")
print(f"Pending events: {stats['pending_events']}")
```

### Health Checks

```python
# Check system health
def health_check():
    try:
        # Check database connectivity
        LMSActivityEvent.objects.count()
        
        # Check LMS database connectivity
        Students.objects.using('lms_db').count()
        
        return True
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return False
```

## Integration Examples

### Custom Event Handler

```python
class CustomLMSActivityEventHandler(LMSActivityEventHandler):
    def handle_event(self, event_data: dict) -> None:
        # Custom event handling logic
        super().handle_event(event_data)
        
        # Additional custom processing
        self.send_custom_notification(event_data)
```

### Custom Message Formatter

```python
class CustomMessageFormatter(MessageFormatter):
    def format_exam_passed_message(self, event, emoji, student_name):
        # Custom formatting logic
        return f"🎓 {student_name} aced {event.activity_title}!"
```

### Custom User Mapper

```python
class CustomUserMapper(UserMapper):
    def get_notification_recipients(self, student_id: int) -> list:
        # Custom recipient logic
        recipients = super().get_notification_recipients(student_id)
        
        # Add additional recipients
        recipients.extend(self.get_additional_recipients(student_id))
        
        return recipients
```

## Troubleshooting

### Common Issues

1. **LMS Database Connection Failed**
   - Check database credentials
   - Verify network connectivity
   - Ensure LMS database is accessible

2. **No Notifications Sent**
   - Check if `LMS_NOTIFY_MENTORS_ENABLED` is True
   - Verify mentor-student relationships
   - Check if mentors have Zulip accounts

3. **Events Not Being Detected**
   - Verify `LMS_ACTIVITY_MONITOR_ENABLED` is True
   - Check polling interval configuration
   - Review activity monitor logs

### Debug Mode

```bash
# Enable verbose logging
python manage.py monitor_lms_activities --daemon --verbose
```

### Log Analysis

```python
# Analyze error logs
error_events = LMSEventLog.objects.exclude(
    error_message__isnull=True
).exclude(error_message='')

for event_log in error_events:
    print(f"Event {event_log.event.event_id}: {event_log.error_message}")
```
