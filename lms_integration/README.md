# LMS Activity Event Listener and Notification System

A comprehensive system for monitoring student activities in an external LMS database and sending real-time notifications to mentors in Zulip.

## Overview

This system provides real-time monitoring of student activities (exam attempts, content interactions) from an external LMS database and automatically notifies assigned mentors through Zulip. All event data is stored in Zulip's database for future AI-driven behavior analysis and nudging.

## Features

- **Real-time Activity Monitoring**: Polls LMS database for new student activities
- **Smart Event Detection**: Automatically classifies events (exam_started, exam_passed, content_completed, etc.)
- **Rich Notifications**: Formatted messages with emojis, scores, and contextual information
- **Mentor Mapping**: Automatically finds and notifies assigned mentors
- **AI-Ready Data**: Events stored with metadata for future AI analysis
- **Production Ready**: Daemon mode, graceful shutdown, and comprehensive error handling

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   LMS Database  │───▶│  Activity Monitor │───▶│  Zulip Database │
│   (Read-only)   │    │                  │    │  (Event Storage)│
└─────────────────┘    └────────┬─────────┘    └─────────────────┘
                                │
                                ▼
                        ┌──────────────────┐
                        │  Event Listener  │
                        │                  │
                        └────────┬─────────┘
                                 │
                                 ▼
                        ┌──────────────────┐
                        │  Mentor Notify   │
                        │  (Zulip DMs)     │
                        └──────────────────┘
```

## Installation

### Prerequisites

- Zulip server with LMS integration enabled
- External LMS database access (read-only)
- Python 3.8+

### Setup

1. **Enable LMS Integration**:
   ```python
   # In your Zulip settings
   LMS_ACTIVITY_MONITOR_ENABLED = True
   LMS_ACTIVITY_POLL_INTERVAL = 60  # seconds
   LMS_NOTIFY_MENTORS_ENABLED = True
   ```

2. **Configure Database Access**:
   ```python
   # LMS database configuration
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
   ```

3. **Run Migrations**:
   ```bash
   python manage.py migrate lms_integration
   ```

## Usage

### Management Command

The system is controlled through a Django management command:

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

### Command Options

- `--interval N`: Polling interval in seconds (default: 60)
- `--daemon`: Run as daemon (continuous monitoring)
- `--once`: Run once and exit
- `--process-pending`: Process pending events and exit
- `--stats`: Show event statistics and exit
- `--verbose`: Enable verbose logging

## Configuration

### Settings

Configure the system through Zulip's settings:

```python
# LMS Activity Monitoring Settings
LMS_ACTIVITY_MONITOR_ENABLED = True
LMS_ACTIVITY_POLL_INTERVAL = 60  # seconds
LMS_NOTIFY_MENTORS_ENABLED = True
LMS_EVENT_TYPES_TO_MONITOR = [
    'exam_started', 'exam_completed', 'exam_failed', 'exam_passed',
    'content_started', 'content_completed', 'content_watched'
]
```

### Database Router

The system uses a database router to separate LMS data from Zulip data:

- **External LMS Database**: Read-only access for polling activities
- **Zulip Database**: All new tables (LMSActivityEvent, LMSEventLog) stored here
- **No migrations to LMS**: External LMS database remains untouched

## Event Types

The system monitors and processes the following event types:

### Exam Events
- `exam_started`: Student begins an exam
- `exam_completed`: Student completes an exam
- `exam_passed`: Student passes an exam
- `exam_failed`: Student fails an exam

### Content Events
- `content_started`: Student starts content (video, assignment, etc.)
- `content_completed`: Student completes content
- `content_watched`: Student watches content (for videos)

## Data Models

### LMSActivityEvent

Core event storage table:

```python
class LMSActivityEvent(models.Model):
    event_id = models.AutoField(primary_key=True)
    event_type = models.CharField(max_length=50, choices=[...])
    student_id = models.IntegerField()
    student_username = models.CharField(max_length=255)
    mentor_id = models.IntegerField()
    mentor_username = models.CharField(max_length=255)
    activity_id = models.IntegerField()
    activity_title = models.CharField(max_length=500)
    activity_metadata = models.JSONField()
    timestamp = models.DateTimeField()
    processed_for_ai = models.BooleanField(default=False)
    zulip_user_id = models.IntegerField(null=True)
```

### LMSEventLog

Event processing audit trail:

```python
class LMSEventLog(models.Model):
    event = models.OneToOneField(LMSActivityEvent)
    notification_sent = models.BooleanField(default=False)
    notification_message_id = models.IntegerField(null=True)
    error_message = models.TextField(null=True)
    processed_at = models.DateTimeField(auto_now=True)
```

## Notification Examples

### Exam Passed Notification
```
🎉 **Exam Passed!**

**john_doe** has passed: **Mathematics Final Exam**
📊 **Score:** 85 | **Percentage:** 85% | **Result:** pass | **Time Taken:** 45 minutes
🎉 Congratulations to the student!
```

### Content Completed Notification
```
📚 **Content Completed**

**jane_smith** has completed: **Python Programming Tutorial**
📚 **Course:** Programming 101 | **Chapter:** Introduction to Python | **Type:** video
📅 Completed at: 2024-01-15 14:30:00
```

## API for AI Integration

The system provides data for AI-driven behavior analysis:

### Query Unprocessed Events
```python
# Get events ready for AI processing
events = LMSActivityEvent.objects.filter(processed_for_ai=False)
```

### Batch Processing
```python
# Mark events as processed for AI
LMSActivityEvent.objects.filter(
    processed_for_ai=False,
    event_type__in=['exam_failed', 'content_started']
).update(processed_for_ai=True)
```

### Student Activity History
```python
# Get student activity history
student_events = LMSActivityEvent.objects.filter(
    student_id=123,
    timestamp__gte=timezone.now() - timedelta(days=30)
).order_by('-timestamp')
```

## Monitoring and Logging

### Statistics
```bash
python manage.py monitor_lms_activities --stats
```

Output:
```
==================================================
LMS Activity Event Statistics
==================================================
Total Events: 1,234
Processed Events: 1,200
Pending Events: 34
Events with Notifications: 1,180
Events with Errors: 20
==================================================
```

### Logging

The system provides comprehensive logging:

- **Activity Detection**: New activities found during polling
- **Event Processing**: Event creation and processing status
- **Notifications**: Mentor notification delivery
- **Errors**: Detailed error information for debugging

## Troubleshooting

### Common Issues

1. **LMS Database Connection Failed**
   - Check database credentials in settings
   - Verify network connectivity to LMS database
   - Ensure LMS database is accessible

2. **No Notifications Sent**
   - Check if `LMS_NOTIFY_MENTORS_ENABLED` is True
   - Verify mentor-student relationships in LMS
   - Check if mentors have Zulip accounts

3. **Events Not Being Detected**
   - Verify `LMS_ACTIVITY_MONITOR_ENABLED` is True
   - Check polling interval configuration
   - Review activity monitor logs

### Debug Mode

Enable verbose logging for debugging:

```bash
python manage.py monitor_lms_activities --daemon --verbose
```

## Development

### Running Tests

```bash
# Run all tests
python manage.py test lms_integration

# Run specific test modules
python manage.py test lms_integration.tests.test_message_formatter
python manage.py test lms_integration.tests.test_activity_monitor
python manage.py test lms_integration.tests.test_event_listener
```

### Adding New Event Types

1. Add new event type to `LMSActivityEvent.event_type` choices
2. Update `ActivityMonitor` to detect new event types
3. Add message formatting in `MessageFormatter`
4. Update tests

### Custom Message Templates

Override message formatting by extending `MessageFormatter`:

```python
class CustomMessageFormatter(MessageFormatter):
    def format_exam_passed_message(self, event, emoji, student_name):
        # Custom formatting logic
        return f"🎓 {student_name} aced {event.activity_title}!"
```

## Security Considerations

- **Database Access**: LMS database access is read-only
- **Data Privacy**: Student data is handled according to privacy policies
- **Authentication**: Uses Zulip's existing authentication system
- **Rate Limiting**: Built-in rate limiting for database queries

## Performance

- **Polling Interval**: Configurable (default: 60 seconds)
- **Database Indexes**: Optimized for query performance
- **Caching**: User mapping cached for performance
- **Batch Processing**: Efficient batch processing for AI integration

## Future Enhancements

- **Webhook Support**: Real-time webhook integration with LMS
- **Advanced Analytics**: Built-in analytics dashboard
- **Custom Rules**: Configurable notification rules
- **Integration APIs**: REST APIs for external integrations

## Support

For issues and questions:

1. Check the troubleshooting section
2. Review logs with `--verbose` flag
3. Check system statistics with `--stats`
4. Contact the development team

## License

This system is part of the Zulip LMS integration and follows the same license terms.
