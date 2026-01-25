---
name: LMS Activity Event Listener and Notification System
overview: ""
todos:
  - id: 8c897ae8-9d14-4b2b-918d-eb74d91296d7
    content: Create LMSActivityEvent and LMSEventLog models in lms_integration/models.py
    status: pending
  - id: 8633d5e7-c70f-4386-92fd-c24e52c676dc
    content: Generate and configure database migration for new event models
    status: pending
  - id: daf20447-d2d0-4b10-a1e0-e4e39236984b
    content: Update db_router.py to properly route new managed models
    status: pending
  - id: 1ce71036-5a6b-482f-9daf-9af28140acfe
    content: Implement ActivityMonitor class to poll LMS database for new activities
    status: pending
  - id: 20ddb54a-8ae7-4d1c-9e43-f9899842ca1e
    content: Create MessageFormatter class for notification message templates
    status: pending
  - id: 46b3e373-7ebe-4d69-8b50-60b05b441923
    content: Implement UserMapper utility to link LMS users to Zulip UserProfiles
    status: pending
  - id: 42e5b260-6135-42e6-98fe-657b5657fa41
    content: Build LMSActivityEventHandler using Zulip's event listener framework
    status: pending
  - id: d324944a-9f9b-4091-83a6-fec803b03a5e
    content: Create monitor_lms_activities management command for polling service
    status: pending
  - id: f8eb4fc3-860e-473c-8c8a-b528ff345481
    content: Add LMS monitoring configuration to settings
    status: pending
  - id: ab6f1c86-6b1c-491e-a4fc-4220aa78d308
    content: Create unit and integration tests for the event system
    status: pending
---

# LMS Activity Event Listener and Notification System

## Overview

Implement a polling-based event system that monitors the LMS database for student activities (exam attempts and content interactions), stores these events in Zulip's database for future AI processing, and sends real-time Zulip notifications to assigned mentors.

## Architecture

The system will poll the external LMS database periodically to detect new student activities, emit internal events through Zulip's event system, and trigger mentor notifications. **All event data will be stored in Zulip's main database (not the external LMS database)** for future AI-driven behavior analysis.

## Implementation Steps

### 1. Create LMS Event Models in Zulip Database (`lms_integration/models.py`)

**IMPORTANT**: These models will be stored in **Zulip's default database**, not the external LMS database. They are managed=True Django models that will live alongside other Zulip data.

Add new managed models to track LMS activity events:

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
- Create LMSActivityEvent records in Zulip database
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

### 6. Database Migration for Zulip Database

**Create migration for new models in Zulip's database**:

- Add LMSActivityEvent table to Zulip's default database
- Add LMSEventLog table to Zulip's default database
- Create indexes on student_id, event_type, timestamp for query performance
- Create index on processed_for_ai for AI batch processing
- **No migrations to external LMS database - that remains read-only**

### 7. Update Database Router (`lms_integration/db_router.py`)

Ensure new managed models use Zulip's default database:

- Exclude LMSActivityEvent and LMSEventLog from lms_models set
- Allow migrations for these models on default database only
- Keep external LMS database read-only

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
- `lms_integration/migrations/000X_add_lms_event_models.py` (for Zulip DB only)

**Modified Files:**

- `lms_integration/models.py` (add new event models for Zulip database)
- `lms_integration/db_router.py` (update routing logic to keep new models in Zulip DB)
- `zproject/settings.py` (add configuration)

## Event Flow

1. **Detection**: Management command polls external LMS database every 60 seconds (read-only)
2. **Processing**: ActivityMonitor detects new Attempts/ContentAttempts records from LMS
3. **Event Storage**: LMSActivityEvent record created in **Zulip's database**
4. **Listener Activation**: LMSActivityEventHandler processes the event
5. **Mentor Lookup**: Find assigned mentor(s) from LMS Mentortostudent table (read-only)
6. **Notification**: Send formatted Zulip DM to mentor(s)
7. **Logging**: Record notification status in LMSEventLog (Zulip database)
8. **AI Queue**: Events marked with processed_for_ai=False for future batch processing

## Database Separation Strategy

- **External LMS Database**: Read-only access for polling student activities
- **Zulip Database**: All new tables (LMSActivityEvent, LMSEventLog) stored here
- **No migrations to LMS**: External LMS database remains untouched

## Testing Approach

- Unit tests for ActivityMonitor detection logic
- Unit tests for MessageFormatter output
- Integration tests for event creation and notification flow
- Mock LMS database records for testing
- Test mentor notification message delivery

## Future AI Integration Points

Events stored in LMSActivityEvent table (in Zulip database) will support:

- Batch export for AI behavior analysis
- Pattern detection (declining performance, engagement drops)
- Predictive nudging based on historical patterns
- Query API for AI agent to fetch student activity history