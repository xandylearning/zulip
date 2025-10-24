<!-- 86ab6088-7c56-4c45-9a50-884b359e0253 0fff97a7-23e1-40ce-a462-dd556653d4b7 -->
# LMS Activity Event Listener and Notification System

## Overview

Implement a polling-based event system that monitors the LMS database for student activities (exam attempts and content interactions), stores these events for future AI processing, and sends real-time Zulip notifications to assigned mentors.

## Architecture

The system will poll the external LMS database periodically to detect new student activities, emit internal events through Zulip's event system, and trigger mentor notifications. Events will be stored in Zulip's main database for future AI-driven behavior analysis.

## Implementation Steps

### 1. Create LMS Event Models (`lms_integration/models.py`)

Add new managed models to track LMS activity events in Zulip's database:

- **LMSActivityEvent**: Core event storage table
- Fields: event_id, event_type (exam_started, exam_completed, exam_failed, exam_passed, content_started, content_completed, content_watched), student_id (FK to Students via lms_db), student_username, mentor_id (FK to Mentors via lms_db), mentor_username, activity_id (exam/content ID), activity_title, activity_metadata (JSON for scores, percentage, duration, etc.), timestamp, processed_for_ai (boolean flag), created_at, zulip_user_id (nullable FK to UserProfile for future linking)

- **LMSEventLog**: Event processing audit trail
- Fields: event_id (FK to LMSActivityEvent), notification_sent (boolean), notification_message_id (nullable), error_message (text), processed_at

### 2. Create Event Detection Service (`lms_integration/lib/activity_monitor.py`)

Implement polling service to detect new LMS activities:

- **ActivityMonitor class**: 
- Poll `Attempts` table for new exam activities (compare against last processed timestamp)
- Poll `ContentAttempts` table for content interaction activities
- Emit standardized events when new records detected
- Track last poll timestamp to avoid duplicates
- Handle different event types based on attempt state (started, completed, passed/failed)

### 3. Create Event Listener (`lms_integration/event_listeners.py`)

Build event listener using Zulip's existing event listener framework:

- **LMSActivityEventHandler** (extends BaseEventHandler):
- Subscribe to LMS activity events
- Create LMSActivityEvent records in database
- Determine student's assigned mentor(s) from `Mentortostudent` relationship
- Format notification messages based on event type
- Send Zulip DMs to mentors using `internal_send_private_message()`
- Log notification status in LMSEventLog

### 4. Create Message Formatting (`lms_integration/lib/message_formatter.py`)

Implement notification message templates:

- **MessageFormatter class**:
- Format exam event messages: "🎓 Student [Name] just completed [Exam Title] - Score: X%, Result: Pass/Fail"
- Format content event messages: "📚 Student [Name] started/completed [Content Title]"
- Include relevant metrics (time taken, score, completion percentage)
- Support markdown formatting for better readability
- Add contextual information (course, chapter if available)

### 5. Create Management Command (`lms_integration/management/commands/monitor_lms_activities.py`)

Build Django management command to run the polling service:

- **Command implementation**:
- Accept poll interval parameter (default 60 seconds)
- Run ActivityMonitor in loop
- Handle graceful shutdown on SIGTERM/SIGINT
- Log monitoring activity and errors
- Support daemon mode for production deployment

### 6. Database Migration

Create migration for new models:

- Add LMSActivityEvent table
- Add LMSEventLog table
- Create indexes on student_id, event_type, timestamp for query performance
- Create index on processed_for_ai for AI batch processing

### 7. Update Database Router (`lms_integration/db_router.py`)

Ensure new managed models use default database:

- Exclude LMSActivityEvent and LMSEventLog from lms_models set
- Allow migrations for these models on default database

### 8. Configuration (`settings.py` or environment variables)

Add configuration settings:

- LMS_ACTIVITY_MONITOR_ENABLED (boolean, default False)
- LMS_ACTIVITY_POLL_INTERVAL (seconds, default 60)
- LMS_NOTIFY_MENTORS_ENABLED (boolean, default True)
- LMS_EVENT_TYPES_TO_MONITOR (list of event types to track)

### 9. Integration with Zulip Users

Create helper utilities (`lms_integration/lib/user_mapping.py`):

- **UserMapper class**:
- Match LMS students/mentors to Zulip UserProfile by email
- Cache mappings for performance
- Handle cases where LMS users don't have Zulip accounts yet
- Provide fallback notification mechanisms

## Key Files to Create/Modify

**New Files:**

- `lms_integration/lib/__init__.py`
- `lms_integration/lib/activity_monitor.py`
- `lms_integration/lib/message_formatter.py`
- `lms_integration/lib/user_mapping.py`
- `lms_integration/event_listeners.py`
- `lms_integration/management/commands/monitor_lms_activities.py`
- `lms_integration/migrations/000X_add_lms_event_models.py`

**Modified Files:**

- `lms_integration/models.py` (add new event models)
- `lms_integration/db_router.py` (update routing logic)
- `zproject/settings.py` (add configuration)

## Event Flow

1. **Detection**: Management command polls LMS database every 60 seconds
2. **Processing**: ActivityMonitor detects new Attempts/ContentAttempts records
3. **Event Creation**: LMSActivityEvent record created in Zulip database
4. **Listener Activation**: LMSActivityEventHandler processes the event
5. **Mentor Lookup**: Find assigned mentor(s) from Mentortostudent table
6. **Notification**: Send formatted Zulip DM to mentor(s)
7. **Logging**: Record notification status in LMSEventLog
8. **AI Queue**: Events marked with processed_for_ai=False for future batch processing

## Testing Approach

- Unit tests for ActivityMonitor detection logic
- Unit tests for MessageFormatter output
- Integration tests for event creation and notification flow
- Mock LMS database records for testing
- Test mentor notification message delivery

## Future AI Integration Points

Events stored in LMSActivityEvent table will support:

- Batch export for AI behavior analysis
- Pattern detection (declining performance, engagement drops)
- Predictive nudging based on historical patterns
- Query API for AI agent to fetch student activity history

### To-dos

- [ ] Create LMSActivityEvent and LMSEventLog models in lms_integration/models.py
- [ ] Generate and configure database migration for new event models
- [ ] Update db_router.py to properly route new managed models
- [ ] Implement ActivityMonitor class to poll LMS database for new activities
- [ ] Create MessageFormatter class for notification message templates
- [ ] Implement UserMapper utility to link LMS users to Zulip UserProfiles
- [ ] Build LMSActivityEventHandler using Zulip's event listener framework
- [ ] Create monitor_lms_activities management command for polling service
- [ ] Add LMS monitoring configuration to settings
- [ ] Create unit and integration tests for the event system