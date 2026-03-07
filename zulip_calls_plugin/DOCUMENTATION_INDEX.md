# Zulip Calls Plugin Documentation Index

## 📚 Documentation Suite

### 🎯 **Main documentation**
- **[README.md](./README.md)** — Overview, installation, configuration, API summary, testing
- **[CHANGELOG.md](./CHANGELOG.md)** — Version history and notable changes

### 📱 **Flutter / mobile (canonical)**
- **[docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md](./docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md)** — **Preferred** guide for mobile calling
  - Correct API paths and payloads (post queue-removal)
  - Event `op` names: `initiated`, `incoming_call`, `ringing`, `accepted`, `declined`, `ended`, `cancelled`, `missed`
  - Push notification structure and CallKit/ConnectionService
  - Call state machine, UX patterns, edge cases
  - Dart examples: CallService, CallStateNotifier, screens

### 🔒 **Jitsi security and recording**
- **[docs/JITSI_SECURITY_AND_RECORDING.md](./docs/JITSI_SECURITY_AND_RECORDING.md)** — JWT auth and GCP recording
  - Prosody JWT configuration
  - Plugin settings (`JITSI_JWT_ENABLED`, `CALL_RECORDING_ENABLED`, etc.)
  - GCP bucket and Jibri setup
  - Hardening checklist

### 🔧 **API and implementation**
- **[API_REFERENCE.md](./API_REFERENCE.md)** — Detailed API reference (see README and Flutter guide for current behavior)
- **[docs/FLUTTER_CALL_EVENTS_INTEGRATION.md](./docs/FLUTTER_CALL_EVENTS_INTEGRATION.md)** — Alternate Flutter/events reference (superseded by FLUTTER_WHATSAPP_CALLING_GUIDE for API correctness)

## 🚀 Quick start

- **Backend / DevOps**: [README.md](./README.md) → [docs/JITSI_SECURITY_AND_RECORDING.md](./docs/JITSI_SECURITY_AND_RECORDING.md) for JWT/recording.
- **Flutter / mobile**: [docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md](./docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md).
- **Development**: [DEVELOPMENT.md](./DEVELOPMENT.md) — run locally, feature flags, plugin layout.
- **Testing**: [TESTING_GUIDE.md](./TESTING_GUIDE.md) and README testing section.

## 📋 Core behavior

- **1:1 calls**: Create with `POST /api/v1/calls/create`; respond with `POST /api/v1/calls/<id>/respond`; end with `POST /api/v1/calls/<id>/end` (either party ends for both). No call queue; busy returns 409.
- **Events** (Zulip event queue): `initiated`, `incoming_call`, `ringing`, `accepted`, `declined`, `ended`, `cancelled`, `missed`. Payloads include `avatar_url`.
- **Optional**: Jitsi JWT and GCP recording are feature-flagged; see plugin config and JITSI_SECURITY_AND_RECORDING.md.