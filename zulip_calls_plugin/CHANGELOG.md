# Changelog

All notable changes to the Zulip Calls Plugin are documented in this file.

## [1.1.0] - 2026-03-07

### Added

- **Jitsi JWT authentication** (optional): Plugin can generate JWT tokens for Jitsi room access. Controlled by `JITSI_JWT_ENABLED` (default: `False`). See `docs/JITSI_SECURITY_AND_RECORDING.md`.
- **GCP call recording configuration**: Settings for Jibri/GCP recording (`CALL_RECORDING_ENABLED`, `CALL_RECORDING_GCP_BUCKET`, etc.). Default: disabled. See `docs/JITSI_SECURITY_AND_RECORDING.md`.
- **Richer notification payloads**: Event and push payloads now include `avatar_url` for sender/receiver; push payloads include `receiver_id`, `receiver_name`, `receiver_avatar_url` for outgoing-call UI.
- **Missed-call event to both participants**: `missed` event is sent to caller and receiver for call history and UI updates.
- **Call declined push to caller**: When the receiver declines, the caller receives a push notification so their device shows "Call declined" even when backgrounded.
- **Comprehensive Flutter guide**: `docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md` with correct APIs, events, state machine, UX patterns, edge cases, and Dart examples.

### Changed

- **1:1 call behavior (WhatsApp-style)**: Either participant ending the call terminates it for both. No moderator concept for 1:1 calls.
- **Busy handling**: If the recipient is in another call, the server returns `409 Conflict` with a message instead of queueing. Call queue feature removed.
- **Idempotent endpoints**: `end_call`, `heartbeat`, `acknowledge`, `respond_to_call`, and `cancel_call` handle terminal-state and duplicate requests gracefully (return success, no error).
- **Embedded call template**: Config passed via `data-call-config` on `<body>` to avoid linter issues; CSRF token included for end-call POST; call timer and accurate participant count; single endCall guard to prevent double-firing.
- **Event payloads**: `do_send_call_event` and `do_send_group_call_event` include `avatar_url` for sender, receiver, host, and participants.

### Removed

- **Call queue**: `CallQueue` model, queue APIs (`GET /api/v1/calls/queue`, `POST /api/v1/calls/queue/<id>/cancel`), and `leave_call` for 1:1 calls. Use `end_call` to end the call for both parties.
- **1:1 leave endpoint**: `POST /api/v1/calls/<call_id>/leave` removed; use `POST /api/v1/calls/<call_id>/end` instead.
- **Middleware JS injection**: Redundant call-button injection removed; `compose_setup.js` is the canonical handler.
- **Debug UI**: Test banner and duplicate calling-screen markup removed from embedded call template.

### Fixed

- **Embedded call UI**: Loading overlay element and safe access in JS; removed moderator display for 1:1; replaced `alert()` with `console.error()` in embedded_calls.js; cleaned verbose console logging in compose_setup.js.
- **Feature flags**: `JITSI_JWT_ENABLED` and `CALL_RECORDING_ENABLED` default to `False` for development; enable in production when Jitsi and Jibri are configured.

### Documentation

- **Jitsi security and recording**: `docs/JITSI_SECURITY_AND_RECORDING.md` — Prosody JWT, plugin settings, GCP bucket and Jibri setup, hardening checklist.
- **Flutter**: `docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md` supersedes older Flutter guides; use it for API paths, event `op` names, and mobile UX.

---

## [1.0.0] - Initial release

- Video and audio 1:1 and group calls via Jitsi Meet.
- Real-time events and push notifications.
- Call creation, respond, end, cancel, status, history.
- Acknowledge and heartbeat for mobile.
- Embedded call window for web.
- Call history and cleanup worker.
