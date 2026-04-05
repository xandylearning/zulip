---
name: zulip-dev
description: >
  Comprehensive development skill for this custom Zulip fork. Use for any
  Zulip development task: feature implementation, bug fixing, testing,
  plugin creation, push notifications, media messages, voice recording,
  LMS integration, calls plugin, event listeners, broadcast notifications,
  or API work. Covers all 9+ custom modules beyond base Zulip.
user-invocable: true
---

# Zulip Custom Fork — Development Guide

This project is a heavily customized Zulip fork focused on education/LMS with AI mentoring, rich media messaging, voice recording, Jitsi calling, broadcast notifications, and a pluggable event listener framework.

## Project Architecture Map

### Custom Modules

| Module | Location | Key Files | Tests | Migrations |
|--------|----------|-----------|-------|------------|
| **LMS Integration** | `lms_integration/` | `auth_backend.py`, `models.py`, `views.py`, `user_sync.py`, `jwt_validator.py`, `permission_utils.py`, `db_router.py` | `lms_integration/tests/` | — |
| **Calls Plugin** | `zulip_calls_plugin/` | `actions.py`, `models/calls.py`, `views/calls.py`, `middleware.py`, `worker.py` | `zulip_calls_plugin/tests/` | — |
| **Event Listeners** | `zerver/event_listeners/` | `base.py`, `registry.py`, `processor.py`, `integration.py`, `setup_plugin.py` | — | — |
| **Media Messages** | `zerver/models/messages.py` | `MessageType` enum (10 types), `media_metadata` JSONField, `primary_attachment`, `caption` | `zerver/tests/test_media_message_types.py` | `10009` |
| **Push Notifications** | `zerver/lib/push_notifications.py` | `make_fcm_app()`, `create_fcm_call_notification_message()`, `send_fcm_call_notifications()` | `zerver/tests/test_push_notifications.py` | — |
| **Voice Recording** | `zerver/views/voice_recording.py`, `zerver/actions/voice_recording.py` | `do_send_voice_recording_notification()`, `do_send_stream_voice_recording_notification()` | `zerver/tests/test_voice_recording.py` | — |
| **AI Mentor** | `zerver/actions/ai_mentor_events.py`, `zerver/worker/ai_mentor_worker.py` | `ai_mentor.py` listener, `ai_message_monitor.py`, queue: `ai_mentor_responses` | — | `10003` |
| **Broadcast Notifications** | `zerver/models/messages.py` | `broadcast_template_data` JSONField, `BroadcastButtonClick` model | — | `10004`-`10007` |
| **Media Detection** | `zerver/lib/media_type_detection.py` | Media type classification logic | — | — |

### Frontend Components (web/src/)

- `media_message_card.ts` — Rendering for all 10 media message types
- `voice_recorder.ts` — Voice recording UI
- `location_picker.ts` — Location selection
- `contact_picker.ts` — Contact selection
- `sticker_picker.ts` — Sticker selection
- `voice_typing_events.ts` / `voice_recording_events.ts` — Real-time event dispatch

### Message Type Enum

```python
class MessageType(models.IntegerChoices):
    NORMAL = 1
    RESOLVE_TOPIC_NOTIFICATION = 2
    IMAGE = 3
    VIDEO = 4
    AUDIO = 5
    DOCUMENT = 6
    LOCATION = 7
    CONTACT = 8
    STICKER = 9
    VOICE_MESSAGE = 10
```

### media_metadata JSON Schemas

- **Image**: `{width, height, mime_type}`
- **Video**: `{width, height, duration_secs, mime_type}`
- **Audio**: `{duration_secs, mime_type}`
- **Voice**: `{duration_secs, mime_type, waveform}`
- **Document**: `{mime_type, page_count}`
- **Location**: `{latitude, longitude, name}`
- **Contact**: `{name, phone, email}`
- **Sticker**: `{pack_id, sticker_id}`

---

## Feature Development Patterns

### Adding a New Message Type

1. Add to `MessageType` enum in `zerver/models/messages.py`
2. Define `media_metadata` schema for the type
3. Update `zerver/lib/media_type_detection.py` with classification logic
4. Create migration (`10000+` series numbering)
5. Update `zerver/actions/message_send.py` to handle the new type
6. Add frontend card rendering in `web/src/media_message_card.ts`
7. Update push notification formatting in `zerver/lib/push_notifications.py`
8. Write tests in `zerver/tests/test_media_message_types.py`

### Adding a New Event Listener

1. Create handler class extending `BaseEventHandler` in `zerver/event_listeners/`
2. Register event type in `zerver/lib/event_types.py`
3. Register handler in `zerver/event_listeners/registry.py`
4. Add frontend event dispatch in `web/src/<event>_events.ts`
5. Write tests

### Adding a New API Endpoint

1. Create view function in `zerver/views/`
2. Add URL pattern in `zproject/urls.py`
3. Update OpenAPI schema
4. Write backend tests
5. Update frontend API calls if applicable

### Adding a New Push Notification Type

1. Define FCM message format function in `zerver/lib/push_notifications.py`
2. Create send function with batch processing via `firebase_messaging.send_each()`
3. Handle device token types (FCM vs APNS)
4. Test with `./tools/test-backend zerver.tests.test_push_notifications`

### Adding a Calls Plugin Feature

1. Add model in `zulip_calls_plugin/models/`
2. Create action in `zulip_calls_plugin/actions.py`
3. Add view/endpoint in `zulip_calls_plugin/views/calls.py`
4. Create WebSocket event for real-time updates
5. Update Flutter integration guide if mobile-facing

### Creating a New Plugin (Event Listeners Framework)

1. Create handler in `zerver/event_listeners/` extending `BaseEventHandler`
2. Register via `zerver/event_listeners/setup_plugin.py`
3. Add management command if needed (see `run_event_listeners.py`, `list_event_listeners.py`)
4. Document in `docs/development/`

### Creating a Webhook Integration

- **Incoming** (external service -> Zulip): Use `@webhook_view` decorator + `check_send_webhook_message()`. See 89+ examples in `zerver/webhooks/`.
- **Outgoing** (Zulip -> external): HTTP endpoint returning `{"content": "markdown response"}`. Processed by `OutgoingWebhookWorker` via RabbitMQ queue `outgoing_webhooks`.

### Creating an Embedded Bot

1. Implement `BotHandler` class with `handle_message(self, message, bot_handler)` method
2. Use `bot_handler.send_reply()`, `bot_handler.storage.get/put` for state
3. Rate limit: 20 messages per 5-second window
4. Register in `zerver/lib/integrations.py`
5. See examples: converter, encrypt, helloworld, virtual_fs in same file

---

## Testing Cheatsheet

```bash
# Full suites
./tools/test-backend               # All backend tests
./tools/test-js-with-node          # All frontend tests
./tools/lint                       # All linters

# Module-specific backend tests
./tools/test-backend zerver.tests.test_push_notifications
./tools/test-backend zerver.tests.test_media_message_types
./tools/test-backend zerver.tests.test_voice_recording
./tools/test-backend zerver.tests.test_message_send
./tools/test-backend zerver.tests.test_message_fetch
./tools/test-backend lms_integration.tests
./tools/test-backend zulip_calls_plugin.tests

# Code quality
ruff check                         # Python linting
ruff format --check                # Python formatting check
mypy                               # Type checking (100% coverage enforced)
npm run lint                       # JS/TS linting
npm run prettier --check           # JS/TS formatting check

# Migrations
./tools/test-migrations            # Test all migrations
python manage.py makemigrations --check  # Verify no missing migrations
```

---

## Cross-Module Dependencies

```
Push Notifications ─── uses ──→ Media Type Detection ─── reads ──→ Message Types (MessageType enum)
         │
         └── FCM call format ──→ Calls Plugin (call_type field)

AI Mentor ─── uses ──→ Event Listeners Framework ─── queues via ──→ RabbitMQ (ai_mentor_responses)
    │
    └── flags messages via ──→ is_ai_generated + ai_metadata fields

LMS Integration ─── authenticates via ──→ JWT Validator ─── syncs via ──→ User Sync
       │
       └── controls ──→ DM Permission Matrix ──→ Channel Subscriptions

Calls Plugin ─── notifies via ──→ FCM Push (call notifications)
       │
       └── real-time via ──→ WebSocket Events ──→ Tornado Event System

Broadcast Notifications ─── stores in ──→ broadcast_template_data (Message model)
       │
       └── tracks via ──→ BroadcastButtonClick model
```

When making cross-module changes, trace these dependency chains and test all affected modules.

---

## Migration Numbering Convention

- **Standard Zulip**: `0001`-`0999` range
- **Custom features**: `10000+` series
  - `10003`: AI message fields (`is_ai_generated`, `ai_metadata`)
  - `10004`-`10007`: Broadcast notifications
  - `10009`: Rich media message types
- Always use `10000+` for new custom migrations to avoid conflicts with upstream Zulip

---

## Agent Team

| Agent | Role | When to use |
|-------|------|-------------|
| **xian** | Architecture & planning | Feature design, scoping, architectural decisions |
| **neom-ai-architect** | AI/LLM design | AI features, LangGraph, Google ADK integration |
| **zulip-dev** | Full-stack implementation | Code writing, bug fixing, testing, plugin creation |
| **flitz** | Flutter mobile dev | Flutter/Dart mobile app work |

---

## Key Technical Standards

- **Python**: PEP 8, 100-char line length, Ruff for lint+format, type hints required (mypy 100%)
- **TypeScript**: ESLint + Prettier, jQuery-based frontend
- **Django**: Models in `models.py`, views in `views/`, business logic in `lib/`, high-level operations in `actions/`
- **Migrations**: Test forward and backward, use 10000+ numbering for custom features
- **API**: RESTful JSON, update OpenAPI schema, maintain backward compatibility
- **Security**: OWASP top 10 awareness, no command injection, XSS, or SQL injection
