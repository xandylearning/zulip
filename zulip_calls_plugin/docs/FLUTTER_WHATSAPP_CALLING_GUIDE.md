# Flutter WhatsApp-Like Calling Guide

> **Canonical reference** for building a production-quality calling experience on
> top of the Zulip Calls Plugin.  This document supersedes the older
> `FLUTTER_CALL_EVENTS_INTEGRATION.md` and any earlier V1/V2 guides.

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Dependencies](#2-dependencies)
3. [API Reference](#3-api-reference)
4. [Event System](#4-event-system)
5. [Push Notification Handling](#5-push-notification-handling)
6. [Call State Machine](#6-call-state-machine)
7. [WhatsApp-Like UX Patterns](#7-whatsapp-like-ux-patterns)
8. [Edge Cases](#8-edge-cases)
9. [Group Call Specifics](#9-group-call-specifics)
10. [Jitsi Configuration](#10-jitsi-configuration)
11. [Code Examples](#11-code-examples)

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Flutter App                              │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │ CallService  │  │  CallState   │  │    UI Screens         │  │
│  │  (API calls) │──│  Notifier    │──│  Incoming / Active /  │  │
│  │              │  │  (Riverpod)  │  │  Ended / History      │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────────────────┘  │
│         │                 │                                      │
│  ┌──────▼───────┐  ┌──────▼───────┐  ┌───────────────────────┐  │
│  │ Zulip Event  │  │ FCM / APNS   │  │ CallKit /             │  │
│  │ Long-poll    │  │ Push Handler │  │ ConnectionService     │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
└─────────┼─────────────────┼──────────────────────┼──────────────┘
          │                 │                      │
          ▼                 ▼                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Zulip Server                                │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────────┐  │
│  │ REST API       │  │ Tornado      │  │ Push Notification   │  │
│  │ /api/v1/calls  │  │ Event Queue  │  │ Service             │  │
│  └────────┬───────┘  └──────┬───────┘  └─────────────────────┘  │
│           │                 │                                    │
│           ▼                 ▼                                    │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │              Jitsi Meet Server (self-hosted)                │ │
│  │         Audio / Video / JWT auth / Recording               │ │
│  └─────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

**Data flow for an incoming 1:1 call:**

1. Server creates `Call` record, sends **event** via Tornado to receiver.
2. If receiver is offline, server also sends a **high-priority FCM data message**.
3. Flutter receives FCM → shows full-screen incoming-call UI via CallKit/ConnectionService.
4. User taps *Accept* → app calls `POST /api/v1/calls/<id>/respond` with `response=accept`.
5. Server transitions call to `accepted`, sends event to both participants.
6. Flutter immediately joins Jitsi with the returned `call_url`.

---

## 2. Dependencies

Add these to `pubspec.yaml`:

```yaml
dependencies:
  jitsi_meet_flutter_sdk: ^10.3.0    # Jitsi Meet SDK wrapper
  flutter_callkit_incoming: ^2.0.4    # Native call UI (iOS CallKit / Android ConnectionService)
  firebase_messaging: ^15.1.6         # FCM push notifications
  firebase_core: ^3.8.1
  just_audio: ^0.9.40                 # Ringtone & call sounds
  riverpod: ^2.6.1                    # State management (or provider/bloc)
  uuid: ^4.5.1                        # Generate unique IDs
  http: ^1.2.2                        # HTTP client (or dio)
  connectivity_plus: ^6.1.1           # Network state monitoring
```

### Platform setup

| Platform | Requirement |
|----------|-------------|
| **iOS** | Enable *Push Notifications*, *Background Modes → Voice over IP*, *Background Modes → Remote notifications* in Xcode capabilities. Add CallKit usage descriptions to `Info.plist`. |
| **Android** | Add `<uses-permission android:name="android.permission.USE_FULL_SCREEN_INTENT"/>` and the `ConnectionService` declarations in `AndroidManifest.xml`. |

---

## 3. API Reference

All endpoints require Zulip authentication (`Authorization: Basic <api_key>`).
Base URL: `https://<your-zulip>/`

### 3.1 One-to-One Call Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/calls/create` | Create a new 1:1 call |
| `POST` | `/api/v1/calls/<call_id>/respond` | Accept or decline |
| `POST` | `/api/v1/calls/<call_id>/end` | End the call (either party) |
| `POST` | `/api/v1/calls/<call_id>/cancel` | Caller cancels before answer |
| `GET`  | `/api/v1/calls/<call_id>/status` | Get current call state |
| `GET`  | `/api/v1/calls/history` | Call history for current user |
| `POST` | `/api/v1/calls/acknowledge` | Receiver acknowledges ringing |
| `POST` | `/api/v1/calls/heartbeat` | Keep-alive during active call |

### 3.2 Create Call — Request & Response

```http
POST /api/v1/calls/create
Content-Type: application/x-www-form-urlencoded

recipient_user_id=42&is_video_call=true
```

**Success (201):**
```json
{
  "result": "success",
  "call_id": "a1b2c3d4-...",
  "call_url": "https://dev.meet.xandylearning.in/zulip-call-abc123?jwt=...",
  "call_type": "video",
  "receiver_online": true
}
```

**Receiver busy (409):**
```json
{
  "result": "error",
  "message": "Jane Doe is currently in another call"
}
```

### 3.3 Respond to Call

```http
POST /api/v1/calls/<call_id>/respond
Content-Type: application/x-www-form-urlencoded

response=accept
```

**Success:**
```json
{
  "result": "success",
  "action": "accept",
  "call_url": "https://dev.meet.xandylearning.in/zulip-call-abc123?jwt=...",
  "message": "Call accepted successfully"
}
```

When `response=decline`, the server also sends a **push notification** to the
caller so their phone shows "Call declined" even if backgrounded.

### 3.4 End Call

```http
POST /api/v1/calls/<call_id>/end
```

Either participant can call this. For 1:1 calls the call ends for **both**
(WhatsApp-style). The endpoint is **idempotent** — calling it on an already-ended
call returns success.

### 3.5 Acknowledge (Ringing)

```http
POST /api/v1/calls/acknowledge
Content-Type: application/x-www-form-urlencoded

call_id=<call_id>
```

Call this as soon as the receiver's phone starts ringing. This transitions the
call from `calling` → `ringing` and lets the caller see a "Ringing…" indicator.

### 3.6 Heartbeat

```http
POST /api/v1/calls/heartbeat
Content-Type: application/x-www-form-urlencoded

call_id=<call_id>
```

Send every 30 seconds during an active call. If heartbeats stop for 90 seconds
the server's cleanup worker marks the call as ended/network_failure.

If the call has already ended, the server returns:
```json
{ "result": "success", "call_state": "ended" }
```

### 3.7 Group Call Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/calls/group/create` | Create group call |
| `POST` | `/api/v1/calls/group/<call_id>/invite` | Invite users |
| `POST` | `/api/v1/calls/group/<call_id>/join` | Join the call |
| `POST` | `/api/v1/calls/group/<call_id>/leave` | Leave (doesn't end for others) |
| `POST` | `/api/v1/calls/group/<call_id>/decline` | Decline invitation |
| `POST` | `/api/v1/calls/group/<call_id>/end` | End for all (host only) |
| `GET`  | `/api/v1/calls/group/<call_id>/status` | Get call + participant info |
| `GET`  | `/api/v1/calls/group/<call_id>/participants` | List participants |

---

## 4. Event System

Events arrive through Zulip's long-polling event queue (`/api/v1/events`).
Register with `event_types=["call", "group_call"]`.

### 4.1 One-to-One Call Events

| `type` | `op` | Recipients | Description |
|--------|------|-----------|-------------|
| `call` | `initiated` | Caller | Call created |
| `call` | `incoming_call` | Receiver | Incoming call (includes `receiver_was_offline`) |
| `call` | `ringing` | Caller | Receiver acknowledged / phone ringing |
| `call` | `accepted` | Both | Call accepted, join Jitsi now |
| `call` | `declined` | Both | Call declined by receiver |
| `call` | `ended` | Both | Call ended (includes optional `reason`) |
| `call` | `cancelled` | Both | Caller cancelled before answer |
| `call` | `missed` | **Both** | Call timed out with no answer |

### 4.2 Event Payload Shape (1:1)

```json
{
  "type": "call",
  "op": "incoming_call",
  "call_id": "a1b2c3d4-...",
  "call_type": "video",
  "sender": {
    "user_id": 7,
    "full_name": "Alice",
    "avatar_url": "/avatar/7"
  },
  "receiver": {
    "user_id": 42,
    "full_name": "Bob",
    "avatar_url": "/avatar/42"
  },
  "state": "calling",
  "jitsi_url": "https://dev.meet.xandylearning.in/zulip-call-abc123",
  "timestamp": "2026-03-07T12:00:00.000000+00:00"
}
```

### 4.3 Group Call Events

| `type` | `op` | Recipients |
|--------|------|-----------|
| `group_call` | `created` | Host |
| `group_call` | `participant_invited` | Invited user |
| `group_call` | `participants_invited` | Existing joined members |
| `group_call` | `participant_joined` | All active participants |
| `group_call` | `participant_left` | All active participants |
| `group_call` | `participant_declined` | Host + joined |
| `group_call` | `ended` | All participants |

### 4.4 Group Call Event Payload

```json
{
  "type": "group_call",
  "op": "participant_joined",
  "call_id": "g1h2i3j4-...",
  "call_type": "video",
  "host": {
    "user_id": 7,
    "full_name": "Alice",
    "avatar_url": "/avatar/7"
  },
  "participants": [
    {
      "user_id": 7,
      "full_name": "Alice",
      "avatar_url": "/avatar/7",
      "state": "joined",
      "is_host": true
    },
    {
      "user_id": 42,
      "full_name": "Bob",
      "avatar_url": "/avatar/42",
      "state": "joined",
      "is_host": false
    }
  ],
  "jitsi_url": "https://dev.meet.xandylearning.in/zulip-group-xyz",
  "title": "Sprint Planning",
  "stream_id": 15,
  "topic": "standup",
  "timestamp": "2026-03-07T12:05:00.000000+00:00"
}
```

---

## 5. Push Notification Handling

### 5.1 FCM Payload Structure

When the receiver is offline (or for high-priority call signals), the server
sends an FCM **data-only** message:

```json
{
  "data": {
    "event": "call",
    "call_id": "a1b2c3d4-...",
    "sender_id": "7",
    "sender_name": "Alice",
    "sender_full_name": "Alice",
    "sender_avatar_url": "/avatar/7",
    "receiver_id": "42",
    "receiver_name": "Bob",
    "receiver_avatar_url": "/avatar/42",
    "call_type": "video",
    "jitsi_url": "https://dev.meet.xandylearning.in/zulip-call-abc123?jwt=..."
  },
  "android": { "priority": "high" },
  "apns": {
    "headers": { "apns-priority": "10" },
    "payload": { "aps": { "content-available": 1 } }
  }
}
```

### 5.2 Call Response Push

When the receiver declines, the server pushes to the **caller**:

```json
{
  "data": {
    "event": "call_response",
    "type": "call_response",
    "call_id": "a1b2c3d4-...",
    "response": "decline",
    "receiver_id": 42,
    "receiver_name": "Bob",
    "receiver_avatar_url": "/avatar/42",
    "sender_id": 7,
    "sender_full_name": "Alice",
    "sender_avatar_url": "/avatar/7",
    "call_type": "video"
  }
}
```

### 5.3 Foreground / Background / Terminated Handling

| App State | Handler | Action |
|-----------|---------|--------|
| **Foreground** | `FirebaseMessaging.onMessage` | Route to `CallStateNotifier` directly |
| **Background** | `FirebaseMessaging.onBackgroundMessage` | Show CallKit/ConnectionService incoming-call screen |
| **Terminated** | Background message handler + `flutter_callkit_incoming` | Wake app, show native call UI, hold state until user taps accept |

### 5.4 CallKit / ConnectionService Setup

```dart
Future<void> showIncomingCallScreen(Map<String, dynamic> data) async {
  final params = CallKitParams(
    id: data['call_id'],
    nameCaller: data['sender_name'],
    avatar: '${baseUrl}${data['sender_avatar_url']}',
    handle: data['sender_name'],
    type: data['call_type'] == 'video' ? 1 : 0,
    textAccept: 'Accept',
    textDecline: 'Decline',
    duration: 90000,
    extra: data,
    android: const AndroidParams(
      isShowLogo: false,
      isCustomNotification: true,
      ringtonePath: 'system_ringtone_default',
      backgroundColor: '#1a1a2e',
      actionColor: '#4CAF50',
      isShowFullLockedScreen: true,
    ),
    ios: const IOSParams(
      supportsVideo: true,
      maximumCallsPerCallGroup: 1,
      audioSessionMode: 'default',
      audioSessionActive: true,
      audioSessionPreferredSampleRate: 44100.0,
      audioSessionPreferredIOBufferDuration: 0.005,
      ringtonePath: 'system_ringtone_default',
    ),
  );
  await FlutterCallkitIncoming.showCallkitIncoming(params);
}
```

Listen for user actions:

```dart
FlutterCallkitIncoming.onEvent.listen((CallEvent? event) {
  switch (event?.event) {
    case Event.actionCallAccept:
      _handleAccept(event!.body);
      break;
    case Event.actionCallDecline:
      _handleDecline(event!.body);
      break;
    case Event.actionCallEnded:
      _handleEnd(event!.body);
      break;
    case Event.actionCallTimeout:
      _handleTimeout(event!.body);
      break;
    default:
      break;
  }
});
```

---

## 6. Call State Machine

### 6.1 One-to-One Call States

```
                  ┌─────────┐
                  │  idle    │
                  └────┬────┘
                       │  POST /create
                       ▼
                  ┌─────────┐    cancel()    ┌───────────┐
           ┌──────│ calling  │──────────────▶│ cancelled  │
           │      └────┬────┘               └───────────┘
           │           │  acknowledge()
           │           ▼
           │      ┌─────────┐
           │      │ ringing  │
           │      └────┬────┘
           │           │
           │     ┌─────┴──────┐
           │     │            │
           │     ▼            ▼
           │ ┌─────────┐  ┌──────────┐
           │ │ accepted │  │ rejected │
           │ └────┬────┘  └──────────┘
           │      │
           │      │  end() (either party)
           │      ▼
           │ ┌─────────┐
           │ │  ended   │
           │ └─────────┘
           │
           │  90s timeout (no answer)
           ▼
      ┌─────────┐
      │ missed   │
      └─────────┘
```

**Terminal states:** `ended`, `cancelled`, `missed`, `rejected`, `timeout`, `network_failure`

### 6.2 State Transition Rules

| From | To | Trigger |
|------|----|---------|
| `idle` | `calling` | Caller creates call |
| `calling` | `ringing` | Receiver acknowledges |
| `calling` | `cancelled` | Caller cancels |
| `calling` | `missed` | 90s timeout |
| `ringing` | `accepted` | Receiver accepts |
| `ringing` | `rejected` | Receiver declines |
| `ringing` | `cancelled` | Caller cancels |
| `ringing` | `missed` | 90s timeout |
| `accepted` | `ended` | Either party ends |
| `accepted` | `network_failure` | Heartbeat timeout |

### 6.3 Client-side state enum

```dart
enum CallStatus {
  idle,
  calling,
  ringing,
  accepted,
  ended,
  cancelled,
  missed,
  rejected,
  networkFailure,
}
```

---

## 7. WhatsApp-Like UX Patterns

### 7.1 Pre-warm Jitsi on Accept

Immediately join Jitsi the moment the user accepts — don't wait for a
confirmation round-trip.

```dart
Future<void> acceptCall(String callId) async {
  // Optimistically start joining Jitsi while the API call happens
  final jitsiJoinFuture = _joinJitsi(pendingJitsiUrl!);

  final response = await _api.respondToCall(callId, 'accept');
  if (response.result == 'success' && response.callUrl != null) {
    // Use server-provided URL (has fresh JWT)
    await jitsiJoinFuture;
  }
}
```

### 7.2 Full-screen Incoming Call Overlay

Show a full-screen overlay when a call comes in, even over the lock screen:

```
┌─────────────────────────────┐
│                             │
│      ┌────────────────┐     │
│      │                │     │
│      │   Avatar (lg)  │     │
│      │                │     │
│      └────────────────┘     │
│                             │
│        Alice is calling     │
│        Video Call           │
│                             │
│                             │
│    ┌────────┐  ┌────────┐   │
│    │ Decline│  │ Accept │   │
│    │   🔴   │  │   🟢   │   │
│    └────────┘  └────────┘   │
│                             │
└─────────────────────────────┘
```

- Use `flutter_callkit_incoming` for native integration (lock screen, heads-up).
- Load the avatar from `${baseUrl}${sender.avatar_url}`.
- Play a ringtone via `just_audio` for in-app overlay (CallKit handles native).

### 7.3 In-Call UI

```
┌─────────────────────────────┐
│  Alice              00:42   │
│                             │
│   ┌───────────────────────┐ │
│   │                       │ │
│   │    Jitsi Video View   │ │
│   │                       │ │
│   │                       │ │
│   └───────────────────────┘ │
│                             │
│  ┌──────┬──────┬──────────┐ │
│  │ Mute │ Cam  │ Speaker  │ │
│  └──────┴──────┴──────────┘ │
│                             │
│       ┌──────────┐          │
│       │  End 🔴  │          │
│       └──────────┘          │
└─────────────────────────────┘
```

- **Timer**: Start a `Stopwatch` when `accepted` event arrives.
- **Mute / Camera / Speaker**: Use `JitsiMeet` API methods.
- **End button**: Calls `POST /api/v1/calls/<id>/end`, then navigates to ended screen.

### 7.4 Picture-in-Picture (PiP) / Minimized Call Bubble

When the user navigates away during an active call:

```dart
// Android: enable PiP mode
await JitsiMeet.enterPictureInPicture();

// iOS: use a floating overlay widget
// (CallKit shows the green banner automatically)
```

### 7.5 Call Ended Screen

Show briefly (2-3 seconds) after the call ends:

```
┌─────────────────────────────┐
│                             │
│        Call Ended           │
│        Duration: 04:23      │
│                             │
│       ┌────────────┐        │
│       │  Call Back  │        │
│       └────────────┘        │
│                             │
└─────────────────────────────┘
```

### 7.6 Missed Call Notification

When a `missed` event arrives or a missed-call push is received:

- Show a system notification: "Missed video call from Alice".
- Include a **"Call Back"** action button.
- Update the call history screen.

```dart
void handleMissedCall(Map<String, dynamic> event) {
  final senderName = event['sender']['full_name'];
  final callType = event['call_type'];
  final callId = event['call_id'];
  final senderId = event['sender']['user_id'];

  showNotification(
    title: 'Missed $callType call',
    body: '$senderName tried to call you',
    actions: [
      NotificationAction(
        id: 'call_back',
        title: 'Call Back',
        payload: {'user_id': senderId, 'call_type': callType},
      ),
    ],
  );
}
```

### 7.7 Busy Handling (409)

When `POST /create` returns `409`:

```dart
if (response.statusCode == 409) {
  showSnackBar('${recipientName} is on another call. Try again later.');
  callState.reset();
}
```

---

## 8. Edge Cases

### 8.1 Double-end Idempotency

Both participants may tap "End" at the same time. The server returns success for
both — no error on the second call. Handle it:

```dart
Future<void> endCall(String callId) async {
  if (_state == CallStatus.ended) return;
  _state = CallStatus.ended;
  notifyListeners();
  await _api.endCall(callId);
  // Even if the server says "already ended", we're fine
}
```

### 8.2 Heartbeat After Ended

If the heartbeat response says `call_state: "ended"`, the other party already
hung up. Transition to ended immediately:

```dart
void _onHeartbeatResponse(Map<String, dynamic> data) {
  if (data['call_state'] == 'ended') {
    _transitionTo(CallStatus.ended);
    _leaveJitsi();
  }
}
```

### 8.3 Decline-After-Cancel Race

The receiver taps "Decline" at the exact moment the caller cancels. The server
handles this gracefully (returns success with `action: "noop"` if the call is
already in a terminal state). The client should check for `noop`:

```dart
final response = await _api.respondToCall(callId, 'decline');
if (response.action == 'noop') {
  // Call was already cancelled/ended — just dismiss UI
}
```

### 8.4 App Killed During Active Call

- The heartbeat stops → after 90 seconds the cleanup worker sets the call to
  `ended` or `network_failure`.
- On next app launch, check for any active calls via `/api/v1/calls/history`
  and reconcile state.

### 8.5 Network Loss and Reconnection

```dart
final subscription = Connectivity().onConnectivityChanged.listen((result) {
  if (result == ConnectivityResult.none) {
    _showReconnectingBanner();
    _heartbeatTimer?.cancel();
  } else {
    _hideReconnectingBanner();
    _startHeartbeat();
    _refetchCallStatus();
  }
});
```

When reconnected:
1. Re-fetch call status via `GET /api/v1/calls/<id>/status`.
2. If the call is still `accepted`, resume Jitsi and restart heartbeat.
3. If the call has ended, show the ended screen.

### 8.6 Bluetooth / Headset Switching

Jitsi handles audio routing natively. For call sounds (ringtone) before Jitsi
joins, configure `just_audio` to respect audio route changes:

```dart
final player = AudioPlayer();
await player.setAudioSource(AudioSource.asset('assets/ringtone.mp3'));
await player.setLoopMode(LoopMode.one);
await player.play();

// Stop when call is accepted or cancelled
player.stop();
player.dispose();
```

### 8.7 Multiple Incoming Calls

If a second call arrives while one is already active, the server returns `409`
to the new caller. The receiver doesn't need to handle this — the server blocks
it.

If a second call arrives while one is *ringing* (not yet accepted), show the
most recent one and auto-decline the older one:

```dart
void onIncomingCall(CallEvent event) {
  if (_currentRingingCallId != null) {
    _api.respondToCall(_currentRingingCallId!, 'decline');
  }
  _currentRingingCallId = event.callId;
  _showIncomingCallUI(event);
}
```

### 8.8 Call During Active Call

If the user tries to make an outgoing call while already in one, block it
client-side:

```dart
Future<void> createCall(int recipientId, bool isVideo) async {
  if (_state != CallStatus.idle) {
    showSnackBar('You are already in a call.');
    return;
  }
  // proceed with API call...
}
```

---

## 9. Group Call Specifics

### 9.1 Lifecycle

1. Host creates: `POST /api/v1/calls/group/create`
2. Host invites: `POST /api/v1/calls/group/<id>/invite`
3. Each invitee joins independently: `POST /api/v1/calls/group/<id>/join`
4. Any participant can leave without affecting others: `POST /api/v1/calls/group/<id>/leave`
5. Only the host can end for everyone: `POST /api/v1/calls/group/<id>/end`

### 9.2 Key Differences from 1:1

| Aspect | 1:1 Call | Group Call |
|--------|----------|------------|
| End behavior | Either party → ends for both | Only host can end for all; participants leave individually |
| Moderator | None (equal peers) | Host has moderator privileges |
| Join | Automatic on accept | Explicit join required |
| Leave | = End call | Just removes participant |
| Decline | Rejects the call | Declines invitation, others unaffected |

### 9.3 Displaying Participants

Use the `participants` array from group call events to build a grid:

```dart
Widget buildParticipantGrid(List<Participant> participants) {
  final joined = participants.where((p) => p.state == 'joined').toList();
  return GridView.builder(
    gridDelegate: SliverGridDelegateWithFixedCrossAxisCount(
      crossAxisCount: joined.length <= 4 ? 2 : 3,
    ),
    itemCount: joined.length,
    itemBuilder: (ctx, i) => ParticipantTile(
      name: joined[i].fullName,
      avatarUrl: '${baseUrl}${joined[i].avatarUrl}',
      isHost: joined[i].isHost,
    ),
  );
}
```

---

## 10. Jitsi Configuration

### 10.1 Joining with JWT

When `JITSI_JWT_ENABLED` is `true` on the server, the `call_url` returned by
the API already contains the `?jwt=<token>` query parameter. Pass it directly:

```dart
Future<void> joinJitsi(String jitsiUrl, String displayName) async {
  final uri = Uri.parse(jitsiUrl);
  final roomName = uri.pathSegments.last;
  final jwt = uri.queryParameters['jwt'];
  final serverUrl = '${uri.scheme}://${uri.host}';

  var options = JitsiMeetConferenceOptions(
    serverURL: serverUrl,
    room: roomName,
    token: jwt,
    userInfo: JitsiMeetUserInfo(
      displayName: displayName,
      email: '',
    ),
    configOverrides: {
      'prejoinConfig.enabled': false,
      'startWithAudioMuted': false,
      'startWithVideoMuted': false,
      'disableModeratorIndicator': true,
      'enableInsecureRoomNameWarning': false,
      'notifications': [],
    },
    featureFlags: {
      'unsaferoomwarning.enabled': false,
      'prejoinpage.enabled': false,
      'lobby-mode.enabled': false,
      'pip.enabled': true,
      'call-integration.enabled': true,
    },
  );

  await JitsiMeet().join(options);
}
```

### 10.2 Handling Jitsi Events

```dart
JitsiMeet().addListener(
  JitsiMeetEventListener(
    conferenceJoined: (url) {
      _callState.setConnected();
    },
    conferenceTerminated: (url, error) {
      _callState.endCall(reason: error ?? 'normal');
    },
    participantJoined: (email, name, role, participantId) {
      _callState.addRemoteParticipant(participantId, name);
    },
    participantLeft: (participantId) {
      _callState.removeRemoteParticipant(participantId);
    },
    audioMutedChanged: (muted) {
      _callState.setAudioMuted(muted);
    },
    videoMutedChanged: (muted) {
      _callState.setVideoMuted(muted);
    },
  ),
);
```

### 10.3 Self-hosted vs Public Jitsi

| Setting | Self-hosted (recommended) | Public (`meet.jit.si`) |
|---------|--------------------------|------------------------|
| `JITSI_SERVER_URL` | `https://meet.yourcompany.com` | `https://meet.jit.si` |
| JWT auth | Supported (Prosody module) | Not available |
| Recording | Supported (Jibri) | Not available |
| Privacy | Full control | Third-party servers |

### 10.4 Audio / Video Defaults

For a WhatsApp-like experience:
- **Audio calls**: `startWithVideoMuted: true`, `startWithAudioMuted: false`
- **Video calls**: `startWithVideoMuted: false`, `startWithAudioMuted: false`
- **Pre-join**: Always disabled (`prejoinConfig.enabled: false`) — auto-join immediately

---

## 11. Code Examples

### 11.1 CallService — API Layer

```dart
class CallService {
  final String baseUrl;
  final String apiKey;

  CallService({required this.baseUrl, required this.apiKey});

  Map<String, String> get _headers => {
    'Authorization': 'Basic $apiKey',
    'Content-Type': 'application/x-www-form-urlencoded',
  };

  Future<CreateCallResponse> createCall(int recipientId, bool isVideo) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/create'),
      headers: _headers,
      body: {
        'recipient_user_id': recipientId.toString(),
        'is_video_call': isVideo.toString(),
      },
    );
    return CreateCallResponse.fromJson(jsonDecode(response.body), response.statusCode);
  }

  Future<RespondResponse> respondToCall(String callId, String action) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/$callId/respond'),
      headers: _headers,
      body: {'response': action},
    );
    return RespondResponse.fromJson(jsonDecode(response.body));
  }

  Future<void> endCall(String callId) async {
    await http.post(
      Uri.parse('$baseUrl/api/v1/calls/$callId/end'),
      headers: _headers,
    );
  }

  Future<void> cancelCall(String callId) async {
    await http.post(
      Uri.parse('$baseUrl/api/v1/calls/$callId/cancel'),
      headers: _headers,
    );
  }

  Future<void> acknowledge(String callId) async {
    await http.post(
      Uri.parse('$baseUrl/api/v1/calls/acknowledge'),
      headers: _headers,
      body: {'call_id': callId},
    );
  }

  Future<HeartbeatResponse> heartbeat(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/heartbeat'),
      headers: _headers,
      body: {'call_id': callId},
    );
    return HeartbeatResponse.fromJson(jsonDecode(response.body));
  }

  Future<CallStatusResponse> getStatus(String callId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/v1/calls/$callId/status'),
      headers: _headers,
    );
    return CallStatusResponse.fromJson(jsonDecode(response.body));
  }

  Future<List<CallHistoryItem>> getHistory() async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/v1/calls/history'),
      headers: _headers,
    );
    final data = jsonDecode(response.body);
    return (data['calls'] as List)
        .map((c) => CallHistoryItem.fromJson(c))
        .toList();
  }
}
```

### 11.2 CallStateNotifier — State Management

```dart
class CallStateNotifier extends ChangeNotifier {
  CallStatus _status = CallStatus.idle;
  String? _callId;
  String? _jitsiUrl;
  String? _remoteName;
  String? _remoteAvatarUrl;
  String? _callType;
  DateTime? _callStartTime;
  Timer? _heartbeatTimer;
  Timer? _callDurationTimer;
  Duration _duration = Duration.zero;

  CallStatus get status => _status;
  String? get callId => _callId;
  String? get remoteName => _remoteName;
  String? get remoteAvatarUrl => _remoteAvatarUrl;
  String? get callType => _callType;
  Duration get duration => _duration;

  final CallService _api;

  CallStateNotifier(this._api);

  // ---- Outgoing call flow ----

  Future<bool> startCall(int recipientId, String recipientName,
      String recipientAvatar, bool isVideo) async {
    if (_status != CallStatus.idle) return false;

    _remoteName = recipientName;
    _remoteAvatarUrl = recipientAvatar;
    _callType = isVideo ? 'video' : 'audio';
    _transitionTo(CallStatus.calling);

    try {
      final result = await _api.createCall(recipientId, isVideo);
      if (result.statusCode == 409) {
        _transitionTo(CallStatus.idle);
        return false;
      }
      _callId = result.callId;
      _jitsiUrl = result.callUrl;
      return true;
    } catch (e) {
      _transitionTo(CallStatus.idle);
      return false;
    }
  }

  Future<void> cancelOutgoing() async {
    if (_callId == null) return;
    _transitionTo(CallStatus.cancelled);
    await _api.cancelCall(_callId!);
    _cleanup();
  }

  // ---- Incoming call flow ----

  void onIncomingCall(Map<String, dynamic> event) {
    _callId = event['call_id'];
    _callType = event['call_type'];
    _remoteName = event['sender']['full_name'];
    _remoteAvatarUrl = event['sender']['avatar_url'];
    _jitsiUrl = event['jitsi_url'];
    _transitionTo(CallStatus.ringing);
    _api.acknowledge(_callId!);
  }

  Future<void> acceptIncoming() async {
    if (_callId == null) return;
    _transitionTo(CallStatus.accepted);
    _startHeartbeat();
    _startDurationTimer();

    // Pre-warm: join Jitsi immediately
    _joinJitsi();

    await _api.respondToCall(_callId!, 'accept');
  }

  Future<void> declineIncoming() async {
    if (_callId == null) return;
    _transitionTo(CallStatus.rejected);
    await _api.respondToCall(_callId!, 'decline');
    _cleanup();
  }

  // ---- Active call ----

  Future<void> endCall() async {
    if (_callId == null || _status == CallStatus.ended) return;
    _transitionTo(CallStatus.ended);
    _heartbeatTimer?.cancel();
    _callDurationTimer?.cancel();
    await _api.endCall(_callId!);
  }

  // ---- Event handlers ----

  void onCallEvent(Map<String, dynamic> event) {
    final op = event['op'] as String;
    switch (op) {
      case 'ringing':
        _transitionTo(CallStatus.ringing);
        break;
      case 'accepted':
        _transitionTo(CallStatus.accepted);
        _startHeartbeat();
        _startDurationTimer();
        _joinJitsi();
        break;
      case 'declined':
        _transitionTo(CallStatus.rejected);
        _cleanup();
        break;
      case 'ended':
        _transitionTo(CallStatus.ended);
        _leaveJitsi();
        _cleanup();
        break;
      case 'cancelled':
        _transitionTo(CallStatus.cancelled);
        _cleanup();
        break;
      case 'missed':
        _transitionTo(CallStatus.missed);
        _cleanup();
        break;
    }
  }

  // ---- Internals ----

  void _transitionTo(CallStatus newStatus) {
    _status = newStatus;
    notifyListeners();
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(
      const Duration(seconds: 30),
      (_) async {
        if (_callId == null) return;
        try {
          final hb = await _api.heartbeat(_callId!);
          if (hb.callState == 'ended') {
            _transitionTo(CallStatus.ended);
            _leaveJitsi();
            _cleanup();
          }
        } catch (_) {
          // Network error — will retry next tick
        }
      },
    );
  }

  void _startDurationTimer() {
    _callStartTime = DateTime.now();
    _callDurationTimer?.cancel();
    _callDurationTimer = Timer.periodic(
      const Duration(seconds: 1),
      (_) {
        _duration = DateTime.now().difference(_callStartTime!);
        notifyListeners();
      },
    );
  }

  void _joinJitsi() {
    if (_jitsiUrl == null) return;
    // See Section 10.1 for full Jitsi join implementation
    joinJitsi(_jitsiUrl!, _remoteName ?? 'User');
  }

  void _leaveJitsi() {
    JitsiMeet().hangUp();
  }

  void _cleanup() {
    _heartbeatTimer?.cancel();
    _callDurationTimer?.cancel();
    Future.delayed(const Duration(seconds: 3), () {
      _callId = null;
      _jitsiUrl = null;
      _remoteName = null;
      _remoteAvatarUrl = null;
      _callType = null;
      _duration = Duration.zero;
      _transitionTo(CallStatus.idle);
    });
  }

  @override
  void dispose() {
    _heartbeatTimer?.cancel();
    _callDurationTimer?.cancel();
    super.dispose();
  }
}
```

### 11.3 IncomingCallScreen

```dart
class IncomingCallScreen extends StatelessWidget {
  final String callerName;
  final String callerAvatarUrl;
  final String callType;
  final VoidCallback onAccept;
  final VoidCallback onDecline;

  const IncomingCallScreen({
    super.key,
    required this.callerName,
    required this.callerAvatarUrl,
    required this.callType,
    required this.onAccept,
    required this.onDecline,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1a1a2e),
      body: SafeArea(
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Spacer(flex: 2),
            CircleAvatar(
              radius: 60,
              backgroundImage: NetworkImage(callerAvatarUrl),
            ),
            const SizedBox(height: 24),
            Text(
              callerName,
              style: const TextStyle(
                color: Colors.white, fontSize: 28, fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Incoming ${callType} call...',
              style: TextStyle(color: Colors.white.withOpacity(0.7), fontSize: 16),
            ),
            const Spacer(flex: 3),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                _CallActionButton(
                  icon: Icons.call_end,
                  color: Colors.red,
                  label: 'Decline',
                  onTap: onDecline,
                ),
                _CallActionButton(
                  icon: Icons.call,
                  color: Colors.green,
                  label: 'Accept',
                  onTap: onAccept,
                ),
              ],
            ),
            const SizedBox(height: 48),
          ],
        ),
      ),
    );
  }
}

class _CallActionButton extends StatelessWidget {
  final IconData icon;
  final Color color;
  final String label;
  final VoidCallback onTap;

  const _CallActionButton({
    required this.icon,
    required this.color,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        GestureDetector(
          onTap: onTap,
          child: Container(
            width: 64,
            height: 64,
            decoration: BoxDecoration(shape: BoxShape.circle, color: color),
            child: Icon(icon, color: Colors.white, size: 32),
          ),
        ),
        const SizedBox(height: 8),
        Text(label, style: const TextStyle(color: Colors.white, fontSize: 14)),
      ],
    );
  }
}
```

### 11.4 ActiveCallScreen

```dart
class ActiveCallScreen extends StatelessWidget {
  final CallStateNotifier callState;

  const ActiveCallScreen({super.key, required this.callState});

  String _formatDuration(Duration d) {
    final minutes = d.inMinutes.remainder(60).toString().padLeft(2, '0');
    final seconds = d.inSeconds.remainder(60).toString().padLeft(2, '0');
    if (d.inHours > 0) {
      return '${d.inHours}:$minutes:$seconds';
    }
    return '$minutes:$seconds';
  }

  @override
  Widget build(BuildContext context) {
    return ListenableBuilder(
      listenable: callState,
      builder: (context, _) {
        if (callState.status == CallStatus.ended) {
          return _CallEndedView(
            remoteName: callState.remoteName ?? '',
            duration: callState.duration,
          );
        }

        return Scaffold(
          backgroundColor: const Color(0xFF1a1a2e),
          body: SafeArea(
            child: Column(
              children: [
                // Header
                Padding(
                  padding: const EdgeInsets.all(16),
                  child: Row(
                    children: [
                      CircleAvatar(
                        radius: 20,
                        backgroundImage: callState.remoteAvatarUrl != null
                            ? NetworkImage(callState.remoteAvatarUrl!)
                            : null,
                      ),
                      const SizedBox(width: 12),
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            callState.remoteName ?? '',
                            style: const TextStyle(
                                color: Colors.white, fontSize: 18),
                          ),
                          Text(
                            callState.status == CallStatus.accepted
                                ? _formatDuration(callState.duration)
                                : callState.status == CallStatus.ringing
                                    ? 'Ringing...'
                                    : 'Calling...',
                            style: TextStyle(
                                color: Colors.white.withOpacity(0.7)),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                // Jitsi video area (rendered by JitsiMeet SDK natively)
                const Expanded(child: SizedBox()),

                // Controls
                Padding(
                  padding: const EdgeInsets.only(bottom: 48),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      _ToggleButton(
                        icon: Icons.mic_off,
                        activeIcon: Icons.mic,
                        label: 'Mute',
                        onTap: () => JitsiMeet().setAudioMuted(true),
                      ),
                      _ToggleButton(
                        icon: Icons.videocam_off,
                        activeIcon: Icons.videocam,
                        label: 'Camera',
                        onTap: () => JitsiMeet().setVideoMuted(true),
                      ),
                      _ToggleButton(
                        icon: Icons.volume_up,
                        activeIcon: Icons.volume_off,
                        label: 'Speaker',
                        onTap: () => JitsiMeet().toggleScreenShare(true),
                      ),
                      _CallActionButton(
                        icon: Icons.call_end,
                        color: Colors.red,
                        label: 'End',
                        onTap: () => callState.endCall(),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        );
      },
    );
  }
}

class _CallEndedView extends StatelessWidget {
  final String remoteName;
  final Duration duration;

  const _CallEndedView({required this.remoteName, required this.duration});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF1a1a2e),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.call_end, color: Colors.white54, size: 48),
            const SizedBox(height: 16),
            const Text('Call Ended',
                style: TextStyle(color: Colors.white, fontSize: 24)),
            const SizedBox(height: 8),
            Text(
              'Duration: ${duration.inMinutes}m ${duration.inSeconds.remainder(60)}s',
              style: const TextStyle(color: Colors.white54, fontSize: 16),
            ),
          ],
        ),
      ),
    );
  }
}
```

### 11.5 CallHistoryScreen

```dart
class CallHistoryScreen extends StatelessWidget {
  final CallService api;

  const CallHistoryScreen({super.key, required this.api});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Call History')),
      body: FutureBuilder<List<CallHistoryItem>>(
        future: api.getHistory(),
        builder: (context, snapshot) {
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final calls = snapshot.data!;
          if (calls.isEmpty) {
            return const Center(child: Text('No call history'));
          }
          return ListView.builder(
            itemCount: calls.length,
            itemBuilder: (context, index) {
              final call = calls[index];
              return ListTile(
                leading: CircleAvatar(
                  backgroundImage: NetworkImage(call.remoteAvatarUrl),
                ),
                title: Text(call.remoteName),
                subtitle: Text(
                  '${call.callType} - ${call.state} - ${call.formattedTime}',
                ),
                trailing: IconButton(
                  icon: Icon(
                    call.callType == 'video' ? Icons.videocam : Icons.call,
                  ),
                  onPressed: () {
                    // Initiate new call to same person
                  },
                ),
              );
            },
          );
        },
      ),
    );
  }
}
```

### 11.6 FirebaseMessaging Background Handler

```dart
@pragma('vm:entry-point')
Future<void> _firebaseBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();

  final data = message.data;
  final event = data['event'];

  if (event == 'call') {
    await showIncomingCallScreen(data);
  } else if (event == 'call_response' && data['response'] == 'decline') {
    await FlutterCallkitIncoming.endCall(data['call_id']);
  }
}

void setupFCM() {
  FirebaseMessaging.onBackgroundMessage(_firebaseBackgroundHandler);

  FirebaseMessaging.onMessage.listen((RemoteMessage message) {
    final data = message.data;
    final event = data['event'];

    if (event == 'call') {
      callStateNotifier.onIncomingCall(data);
      showIncomingCallScreen(data);
    } else if (event == 'call_response') {
      if (data['response'] == 'decline') {
        callStateNotifier.onCallEvent({'op': 'declined'});
      }
    }
  });
}
```

---

## Key Corrections vs Older Documentation

| Aspect | Old docs | Correct (this guide) |
|--------|----------|---------------------|
| Create endpoint | `/api/v1/calls/initiate` | `/api/v1/calls/create` |
| Ringing event op | `participant_ringing` | `ringing` |
| Call queue endpoints | Existed | **Removed** — server returns 409 if busy |
| Moderator for 1:1 | Sender was moderator | No moderator — equal peers |
| Avatar in events | Not included | `avatar_url` in sender, receiver, host, participants |
| Missed-call event | Sent to caller only | Sent to **both** participants |
| `leave_call` for 1:1 | Existed | **Removed** — use `end_call` (ends for both) |
| Decline push to caller | Not sent | Server sends push to caller on decline |
