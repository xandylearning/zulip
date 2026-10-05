# Changelog

All notable changes to the LMS Activity Event Listener and Notification System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2026-10-05

### Fixed

#### JWT Authentication
- **First JWT login failed for every new full-member faculty user** — Logins
  failed with `Could not find or create user … after IntegrityError: duplicate
  key value violates unique constraint
  "zerver_usergroupmembersh_user_group_id_user_profi_5b32ea4b_uniq"`. The root
  cause was not a race (see 1.0.1): in realms with
  `waiting_period_threshold = 0`, `do_create_user`
  (`zerver/actions/create_user.py`) added new faculty users to `role:faculty`
  twice — once as their role group and again in the "full members" branch,
  which had been changed from `role:full_members` to `role:faculty`.
  - The full-members branch adds `role:full_members` again, and skips it for
    realms that only have the legacy `role:fullmembers` group instead of
    failing user creation.
  - Fixed the `NameError` on the undefined `full_members_system_group` that the
    same branch would have hit next.

### Added
- Regression tests that exercise the real `do_create_user`:
  `zerver/tests/test_users.py` (`CreateUserSystemGroupMembershipTest`) and
  `tests/test_jwt_user_creation.py`.

## [1.0.1] - 2026-05-31

### Fixed

#### JWT Authentication
- **Concurrent first-time login race condition** — Two near-simultaneous JWT
  logins for the same brand-new user could both reach `do_create_user`, causing
  the second to fail with `duplicate key value violates unique constraint
  "zerver_usergroupmembersh_user_group_id_user_profi_5b32ea4b_uniq"` and the
  login to fail with `Could not find or create user … after error`.
  - `TestPressJWTAuthBackend._get_or_create_user` now wraps `do_create_user` in
    `transaction.atomic(savepoint=True)` so a failed creation rolls back cleanly
    instead of poisoning the surrounding transaction (which had made the recovery
    queries fail with "current transaction is aborted").
  - `IntegrityError` is now caught explicitly and treated as "a concurrent
    request created this user first": the backend re-queries and returns the
    existing user, making creation idempotent under concurrency.
  - Recovery logic extracted into `_recover_existing_user()` /
    `_finalize_recovered_user()`, which run only after the savepoint rollback.
  - `_add_username_mapping()` is now idempotent (`get_or_create` inside its own
    savepoint), fixing the same latent "swallow error, poison transaction" bug
    for the `ExternalAuthID` mapping insert.

### Added
- Regression tests in `tests/test_placeholder_emails.py`
  (`test_concurrent_creation_recovers_existing_user`,
  `test_creation_failure_with_no_existing_user_returns_none`).
- `docs/POSTMORTEM_2026-05-12_jwt_user_creation_race.md` documenting the incident.
- Updated `docs/JWT_AUTHENTICATION.md`, `docs/SIMPLIFIED_AUTH_BACKEND.md`, and
  `docs/TROUBLESHOOTING.md` with concurrency/transaction-safety guidance.

## [1.0.0] - 2024-10-24

### Added

#### Core System
- **LMS Activity Event Listener and Notification System** - Complete implementation
- **Real-time Activity Monitoring** - Polls LMS database for new student activities
- **Smart Event Detection** - Automatically classifies events based on activity state
- **Rich Notifications** - Formatted messages with emojis, scores, and contextual information
- **Mentor Mapping** - Automatically finds and notifies assigned mentors
- **AI-Ready Data Storage** - Events stored with metadata for future AI analysis

#### Database Models
- **LMSActivityEvent** - Core event storage table with comprehensive metadata
  - Event types: exam_started, exam_completed, exam_failed, exam_passed, content_started, content_completed, content_watched
  - Student and mentor information linking
  - Activity metadata (scores, percentages, timestamps)
  - AI processing flags
  - Zulip user linking for future integration
- **LMSEventLog** - Event processing audit trail
  - Notification tracking
  - Error logging
  - Processing timestamps

#### Activity Monitoring
- **ActivityMonitor** - Polls LMS database for new activities
  - Exam attempt detection from `Attempts` table
  - Content interaction detection from `ContentAttempts` table
  - Duplicate prevention with timestamp tracking
  - Event type determination based on activity state
- **Event Processing Pipeline** - Complete event lifecycle management
  - Event creation and storage
  - Mentor lookup and notification
  - Error handling and logging

#### Message System
- **MessageFormatter** - Rich notification message formatting
  - Exam event messages with scores and results
  - Content event messages with course information
  - Emoji support for visual appeal
  - Markdown formatting for readability
  - Summary messages for multiple events
- **Notification Delivery** - Zulip DM integration
  - Automatic mentor notification
  - Message ID tracking
  - Error handling and retry logic

#### User Management
- **UserMapper** - LMS to Zulip user mapping
  - Email-based user matching
  - Caching for performance
  - Fallback mechanisms for missing users
  - Mentor-student relationship lookup

#### Management Interface
- **monitor_lms_activities** - Comprehensive management command
  - Daemon mode for continuous monitoring
  - One-time execution mode
  - Pending event processing
  - Statistics and reporting
  - Graceful shutdown handling
  - Verbose logging support

#### Database Integration
- **Database Router** - Proper database separation
  - External LMS database (read-only)
  - Zulip database (event storage)
  - Migration management
- **Database Migrations** - Complete migration system
  - New model creation
  - Index optimization
  - Data integrity constraints

#### Configuration System
- **Settings Integration** - Zulip settings integration
  - `LMS_ACTIVITY_MONITOR_ENABLED` - Enable/disable monitoring
  - `LMS_ACTIVITY_POLL_INTERVAL` - Configurable polling frequency
  - `LMS_NOTIFY_MENTORS_ENABLED` - Notification control
  - `LMS_EVENT_TYPES_TO_MONITOR` - Event type filtering

#### Testing Framework
- **Comprehensive Test Suite** - Complete testing coverage
  - Unit tests for ActivityMonitor
  - Unit tests for MessageFormatter
  - Unit tests for EventListener
  - Mock-based testing for external dependencies
  - Integration test framework

#### Documentation
- **README.md** - Comprehensive documentation
  - Installation and setup instructions
  - Usage examples and command reference
  - Configuration options
  - API documentation for AI integration
  - Troubleshooting guide
- **CHANGELOG.md** - Version history and changes
- **Inline Documentation** - Code documentation and comments

### Technical Details

#### Event Types Supported
- **Exam Events**: exam_started, exam_completed, exam_passed, exam_failed
- **Content Events**: content_started, content_completed, content_watched

#### Database Schema
- **LMSActivityEvent Table**: 
  - Primary key: event_id (AutoField)
  - Event classification: event_type (CharField with choices)
  - Student information: student_id, student_username
  - Mentor information: mentor_id, mentor_username
  - Activity details: activity_id, activity_title, activity_metadata (JSON)
  - Timestamps: timestamp, created_at
  - AI processing: processed_for_ai (BooleanField)
  - Zulip integration: zulip_user_id (IntegerField, nullable)
  - Indexes: student_id, event_type, timestamp, processed_for_ai

- **LMSEventLog Table**:
  - Primary key: event (OneToOneField to LMSActivityEvent)
  - Notification tracking: notification_sent, notification_message_id
  - Error handling: error_message
  - Processing: processed_at

#### Performance Optimizations
- **Database Indexes** - Optimized for query performance
- **Caching** - User mapping cached for performance
- **Batch Processing** - Efficient event processing
- **Rate Limiting** - Built-in rate limiting for database queries

#### Security Features
- **Read-only LMS Access** - External database remains read-only
- **Data Privacy** - Student data handled according to privacy policies
- **Authentication** - Uses Zulip's existing authentication system
- **Error Handling** - Comprehensive error handling and logging

#### Production Features
- **Daemon Mode** - Continuous monitoring with graceful shutdown
- **Logging** - Comprehensive logging system
- **Statistics** - Built-in statistics and monitoring
- **Error Recovery** - Automatic error recovery and retry logic

### Configuration

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

### Usage Examples

#### Basic Usage
```bash
# Run once to check for new activities
python manage.py monitor_lms_activities --once

# Run as daemon for continuous monitoring
python manage.py monitor_lms_activities --daemon --interval 30

# Process pending events
python manage.py monitor_lms_activities --process-pending

# Show statistics
python manage.py monitor_lms_activities --stats
```

#### Advanced Usage
```bash
# Enable verbose logging
python manage.py monitor_lms_activities --daemon --verbose

# Custom polling interval
python manage.py monitor_lms_activities --daemon --interval 120

# Process specific event types
python manage.py monitor_lms_activities --process-pending --event-types exam_started,exam_completed
```

### API for AI Integration

#### Query Unprocessed Events
```python
# Get events ready for AI processing
events = LMSActivityEvent.objects.filter(processed_for_ai=False)

# Get specific event types
exam_events = LMSActivityEvent.objects.filter(
    processed_for_ai=False,
    event_type__in=['exam_failed', 'exam_passed']
)
```

#### Batch Processing
```python
# Mark events as processed for AI
LMSActivityEvent.objects.filter(
    processed_for_ai=False,
    event_type__in=['exam_failed', 'content_started']
).update(processed_for_ai=True)
```

#### Student Activity History
```python
# Get student activity history
student_events = LMSActivityEvent.objects.filter(
    student_id=123,
    timestamp__gte=timezone.now() - timedelta(days=30)
).order_by('-timestamp')
```

### Future Roadmap

#### Planned Features
- **Webhook Support** - Real-time webhook integration with LMS
- **Advanced Analytics** - Built-in analytics dashboard
- **Custom Rules** - Configurable notification rules
- **Integration APIs** - REST APIs for external integrations
- **AI Integration** - Built-in AI analysis and nudging
- **Mobile Support** - Mobile app integration
- **Multi-tenant Support** - Support for multiple LMS instances

#### Performance Improvements
- **Caching Layer** - Redis-based caching for better performance
- **Async Processing** - Asynchronous event processing
- **Database Optimization** - Further database query optimization
- **Load Balancing** - Support for multiple monitoring instances

### Breaking Changes

None in this initial release.

### Deprecations

None in this initial release.

### Security

- **Database Access** - LMS database access is read-only
- **Data Privacy** - Student data is handled according to privacy policies
- **Authentication** - Uses Zulip's existing authentication system
- **Rate Limiting** - Built-in rate limiting for database queries

### Dependencies

- Django 3.2+
- PostgreSQL 12+
- Zulip server
- Python 3.8+

### Installation

1. Ensure LMS integration is enabled in Zulip
2. Configure database access to external LMS
3. Run migrations: `python manage.py migrate lms_integration`
4. Configure settings for LMS activity monitoring
5. Start monitoring: `python manage.py monitor_lms_activities --daemon`

### Support

For issues and questions:
1. Check the troubleshooting section in README.md
2. Review logs with `--verbose` flag
3. Check system statistics with `--stats`
4. Contact the development team

---

## Version History

- **1.0.0** (2024-10-24): Initial release with complete LMS activity monitoring system

