# Design: `zulip-dev` Skill and Agent

**Date:** 2026-04-05
**Status:** Approved
**Author:** Claude (brainstormed with user)

## Overview

Create a comprehensive Claude Code **skill** and **agent** for this custom Zulip fork. The skill serves as the "project brain" (knowledge base + patterns + testing cheatsheet), while the agent is a hands-on full-stack implementer that works alongside existing agents (xian for architecture, neom-ai-architect for AI design).

## Context

This Zulip fork has 9+ major custom modules beyond base Zulip:

| Module | Location | Purpose |
|--------|----------|---------|
| LMS Integration | `lms_integration/` | Educational LMS sync, auth, permissions |
| Calls Plugin | `zulip_calls_plugin/` | Jitsi 1:1 + group calling |
| Event Listeners | `zerver/event_listeners/` | Pluggable event framework |
| Media Messages | `zerver/models/messages.py` | 10 message types (image, video, audio, etc.) |
| Push Notifications | `zerver/lib/push_notifications.py` | Direct FCM + call notifications |
| Voice Recording | `zerver/views/voice_recording.py` | Real-time voice recording API |
| AI Mentor | `zerver/actions/ai_mentor_events.py` | LangGraph-based AI mentoring |
| Broadcast Notifications | migrations 10004-10007 | Rich media notification templates |
| Media Detection | `zerver/lib/media_type_detection.py` | Media type classification |

Existing agents:
- **xian** (purple, sonnet): Senior architect for feature planning and design
- **neom-ai-architect** (green, sonnet): AI/LLM feature design and LangGraph architecture

**Gap:** No agent for hands-on full-stack implementation. No skill for project-wide knowledge.

---

## Part 1: Skill Design

### File

`.claude/skills/zulip-dev/SKILL.md`

### Frontmatter

```yaml
name: zulip-dev
description: >
  Comprehensive development skill for this custom Zulip fork. Use for any
  Zulip development task: feature implementation, bug fixing, testing,
  plugin creation, push notifications, media messages, voice recording,
  LMS integration, calls plugin, event listeners, broadcast notifications,
  or API work. Covers all 9+ custom modules beyond base Zulip.
user-invocable: true
```

### Content Sections

#### 1. Project Architecture Map

Quick-reference table of all custom modules with:
- Directory/file paths
- Key classes and functions
- Migration number ranges
- Related test files
- Frontend component locations (web/src/)

Modules covered:
- LMS Integration (`lms_integration/`) — 30+ files, auth backend, models, views, user sync, permissions, multi-DB routing
- Calls Plugin (`zulip_calls_plugin/`) — actions, models, views, middleware, worker, Jitsi JWT
- Event Listeners (`zerver/event_listeners/`) — BaseEventHandler, registry, processor, setup_plugin
- Media Messages — `MessageType` enum (10 types), `media_metadata` JSONField schema, `primary_attachment`, `caption`, frontend cards (`media_message_card.ts`, `voice_recorder.ts`, `location_picker.ts`, `contact_picker.ts`, `sticker_picker.ts`)
- Push Notifications — `make_fcm_app()`, `create_fcm_call_notification_message()`, `send_fcm_call_notifications()`, direct FCM via firebase_admin
- Voice Recording — `do_send_voice_recording_notification()`, `do_send_stream_voice_recording_notification()`, event type `voice_recording`
- AI Mentor — `ai_mentor_worker.py` (queue: `ai_mentor_responses`), `ai_mentor.py` event listener, `ai_message_monitor.py`
- Broadcast Notifications — `broadcast_template_data` JSONField, `BroadcastButtonClick` model
- Media Detection — `media_type_detection.py`

#### 2. Feature Development Patterns

Step-by-step guides for common development tasks:

**Adding a new message type:**
1. Add to `MessageType` enum in `zerver/models/messages.py`
2. Define `media_metadata` schema for the type
3. Update `media_type_detection.py` with classification logic
4. Create migration (10000+ series numbering)
5. Update `message_send.py` to handle the new type
6. Add frontend card rendering in `media_message_card.ts`
7. Update push notification formatting in `push_notifications.py`
8. Write tests in `test_media_message_types.py`

**Adding a new event listener:**
1. Create handler class extending `BaseEventHandler` in `zerver/event_listeners/`
2. Register event type in `zerver/lib/event_types.py`
3. Register handler in `registry.py`
4. Add frontend event dispatch in `web/src/<event>_events.ts`
5. Write tests

**Adding a new API endpoint:**
1. Create view function in `zerver/views/`
2. Add URL pattern in `zproject/urls.py`
3. Update OpenAPI schema
4. Write backend tests
5. Update frontend API calls if applicable

**Adding a new push notification type:**
1. Define FCM message format function in `push_notifications.py`
2. Create send function with batch processing
3. Handle device token types (FCM vs APNS)
4. Test with `test_push_notifications`

**Adding a calls plugin feature:**
1. Add model in `zulip_calls_plugin/models/`
2. Create action in `actions.py`
3. Add view/endpoint in `views/calls.py`
4. Create WebSocket event for real-time updates
5. Update Flutter integration guide if mobile-facing

**Creating a new plugin (using event listeners framework):**
1. Create handler in `zerver/event_listeners/`
2. Extend `BaseEventHandler`
3. Register via `setup_plugin.py`
4. Add management command if needed
5. Document in `docs/development/`

#### 3. Testing Cheatsheet

```
# Full suites
./tools/test-backend               # All backend tests
./tools/test-js-with-node          # All frontend tests
./tools/lint                       # All linters

# Module-specific
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
mypy                               # Type checking
npm run lint                       # JS/TS linting
npm run prettier --check           # JS/TS formatting check

# Migrations
./tools/test-migrations            # Test all migrations
python manage.py makemigrations --check  # Verify no missing migrations
```

#### 4. Cross-Module Dependencies

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

#### 5. Plugin/Extension Development Guide

Three patterns for extending this Zulip fork:

1. **Event Listener Plugin** (server-side, real-time):
   - Best for: reacting to Zulip events (messages, user actions, state changes)
   - Pattern: `BaseEventHandler` subclass in `zerver/event_listeners/`
   - Example: `ai_mentor.py`, `ai_message_monitor.py`

2. **Webhook Integration** (external service):
   - Incoming: `@webhook_view` decorator, `check_send_webhook_message()`
   - Outgoing: HTTP endpoint returning `{"content": "..."}`
   - 89+ existing webhook integrations as templates in `zerver/webhooks/`

3. **Embedded Bot** (in-server automation):
   - Pattern: `BotHandler` class with `handle_message()` method
   - Built-in storage: `bot_handler.storage.get/put`
   - Rate limited: 20 messages per 5 seconds
   - Examples: `zerver/lib/integrations.py` (converter, encrypt, helloworld, etc.)

#### 6. Migration Numbering Convention

- Standard Zulip: `0001` - `0999` range
- Custom features: `10000+` series
  - `10003`: AI message fields
  - `10004-10007`: Broadcast notifications
  - `10009`: Rich media message types
- Always use `10000+` for new custom migrations to avoid conflicts with upstream Zulip

---

## Part 2: Agent Design

### File

`.claude/agents/zulip-dev.md`

### Frontmatter

```yaml
name: zulip-dev
model: sonnet
color: blue
description: >
  Use this agent when the user needs hands-on full-stack implementation
  across any Zulip custom module — writing code, fixing bugs, running tests,
  creating plugins, or modifying push notifications, media messages, voice
  recording, LMS integration, calls plugin, event listeners, broadcast
  notifications, or API endpoints. Use when the work is implementation-focused
  rather than architectural planning (use xian) or AI/LLM design (use
  neom-ai-architect).
```

### System Prompt Structure

#### Identity

A senior full-stack developer with deep expertise in this custom Zulip fork. Knows Django, TypeScript/jQuery, PostgreSQL, Redis, RabbitMQ, FCM, Jitsi, and all 9+ custom modules. Implementation-focused — writes code, runs tests, fixes bugs.

#### Core Workflow

1. **Read before writing** — Always read relevant code before making changes
2. **Follow patterns** — Check similar implementations in the same module first
3. **Test alongside** — Write tests as part of implementation, not after
4. **Lint before done** — Run ruff, mypy, ESLint before declaring work complete
5. **Migrate properly** — Create migrations for model changes, use 10000+ numbering

#### Module-Specific Expertise

For each of the 9 modules, the agent knows:
- Key files and entry points
- Common patterns and conventions
- Testing approaches
- Integration points with other modules

#### Collaboration Protocol

| Situation | Action |
|-----------|--------|
| Architecture/design decision needed | Defer to **xian** |
| AI/LLM feature design needed | Defer to **neom-ai-architect** |
| Implementation task from xian/neom | Accept and execute |
| Bug in custom module | Handle directly |
| New feature implementation | Handle directly (after design is approved) |
| Cross-module change | Trace dependencies, test all affected modules |

#### Quality Gates

Before declaring work complete:
- [ ] All relevant tests pass
- [ ] Code passes ruff check + ruff format
- [ ] Code passes mypy (100% type coverage)
- [ ] Frontend passes ESLint + Prettier
- [ ] Migrations work forward (and backward if destructive)
- [ ] API changes reflected in OpenAPI schema
- [ ] No security vulnerabilities (OWASP top 10 awareness)
- [ ] Changes follow existing module patterns

---

## Agent Team Summary

After this implementation, the agent team will be:

| Agent | Color | Role | Triggers |
|-------|-------|------|----------|
| **xian** | Purple | Architecture & planning | Feature design, scoping, architectural decisions |
| **neom-ai-architect** | Green | AI/LLM design | AI features, LangGraph, Google ADK |
| **zulip-dev** | Blue | Full-stack implementation | Code writing, bug fixing, testing, plugin creation |
| **flitz** | — | Flutter mobile dev | Flutter/Dart mobile app work |

---

## Files to Create

1. `.claude/skills/zulip-dev/SKILL.md` — Comprehensive development skill
2. `.claude/agents/zulip-dev.md` — Full-stack implementation agent
