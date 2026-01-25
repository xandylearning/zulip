# Flutter Call Events Integration Guide

Complete guide for integrating Zulip call events with a Flutter mobile application.

## Table of Contents

- [Overview](#overview)
- [Event Types](#event-types)
- [Setup](#setup)
- [Event Models](#event-models)
- [State Management](#state-management)
- [Push Notifications](#push-notifications)
- [API Integration](#api-integration)
- [Offline Handling](#offline-handling)
- [Missed Calls](#missed-calls)
- [Complete Examples](#complete-examples)
- [Testing](#testing)

## Overview

This guide covers:
1. Real-time call events via Zulip's event system
2. 1-to-1 calls and group calls
3. Offline handling and missed calls
4. Push notification integration
5. CallKit/ConnectionService integration

### Architecture

```
Flutter App
    │
    ├─→ Event Polling ───→ Zulip Event Queue API
    │                         │
    ├─→ Call State Manager ←──┤ (call/group_call events)
    │        │                │
    │        └─→ UI Updates   │
    │                          │
    └─→ Push Notifications ←──┘ (offline/background)
```

## Event Types

### 1-to-1 Call Events

| Event Type | Op | Recipient | Description |
|------------|-----|-----------|-------------|
| `call` | `initiated` | Caller | Call created (sent to caller) |
| `call` | `incoming_call` | Receiver | Incoming call (sent to receiver) |
| `call` | `ringing` | Caller | Receiver acknowledged (sent to caller) |
| `call` | `accepted` | Both | Call accepted (sent to both) |
| `call` | `declined` | Both | Call declined (sent to both) |
| `call` | `ended` | Both | Call ended (sent to both) |
| `call` | `cancelled` | Both | Caller cancelled (sent to both) |
| `call` | `missed` | Caller | Call missed/timed out (sent to caller) |

### Group Call Events

| Event Type | Op | Recipient | Description |
|------------|-----|-----------|-------------|
| `group_call` | `created` | Host | Group call created |
| `group_call` | `participant_invited` | Invitee | User invited to call |
| `group_call` | `participant_joined` | All active | User joined call |
| `group_call` | `participant_left` | Remaining | User left call |
| `group_call` | `participant_declined` | Host & joined | User declined invitation |
| `group_call` | `participant_missed` | - | User missed invitation (state update) |
| `group_call` | `ended` | All participants | Call ended by host |

## Setup

### 1. Dependencies

Add to `pubspec.yaml`:

```yaml
dependencies:
  flutter:
    sdk: flutter

  # HTTP & WebSocket
  http: ^1.1.0
  web_socket_channel: ^2.4.0

  # State Management
  provider: ^6.1.0

  # Video Calling
  jitsi_meet_flutter_sdk: ^10.0.0

  # Push Notifications
  firebase_messaging: ^14.7.0
  firebase_core: ^2.24.0

  # CallKit (iOS) & ConnectionService (Android)
  flutter_callkit_incoming: ^2.0.0

  # Local Notifications
  flutter_local_notifications: ^16.3.0

  # Permissions
  permission_handler: ^11.1.0
```

### 2. Initialize Services

```dart
// main.dart
void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize Firebase
  await Firebase.initializeApp();

  // Setup push notifications
  await CallPushHandler.initialize();

  // Setup CallKit
  await FlutterCallkitIncoming.setup();

  runApp(
    MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => CallStateManager()),
        Provider(create: (_) => ZulipEventService()),
      ],
      child: MyApp(),
    ),
  );
}
```

### 3. Register for Events

```dart
// lib/services/zulip_event_service.dart
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;

class ZulipEventService {
  static const String baseUrl = 'https://your-zulip-domain.com';
  final String apiKey;
  final String email;

  ZulipEventService({
    required this.apiKey,
    required this.email,
  });

  Map<String, String> get _authHeaders => {
    'Authorization': 'Basic ${base64Encode(utf8.encode('$email:$apiKey'))}',
    'Content-Type': 'application/json',
  };

  /// Register for call events and get queue_id
  Future<EventRegistration> registerForEvents() async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/register'),
      headers: _authHeaders,
      body: jsonEncode({
        'event_types': ['call', 'group_call', 'message'],
        'client_capabilities': {
          'notification_settings_null': false,
        },
        'apply_markdown': false,
        'include_subscribers': false,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to register for events: ${response.body}');
    }

    final data = jsonDecode(response.body);
    return EventRegistration(
      queueId: data['queue_id'],
      lastEventId: data['last_event_id'],
    );
  }

  /// Poll for events (long-polling with 90s timeout)
  Future<EventPollResponse> pollEvents({
    required String queueId,
    required int lastEventId,
  }) async {
    final response = await http.get(
      Uri.parse(
        '$baseUrl/api/v1/events'
        '?queue_id=$queueId'
        '&last_event_id=$lastEventId'
        '&dont_block=false',
      ),
      headers: _authHeaders,
    ).timeout(
      const Duration(seconds: 90),
      onTimeout: () => throw TimeoutException('Event poll timeout'),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to poll events: ${response.body}');
    }

    final data = jsonDecode(response.body);
    return EventPollResponse(
      events: (data['events'] as List)
          .map((e) => ZulipEvent.fromJson(e))
          .toList(),
    );
  }
}

class EventRegistration {
  final String queueId;
  final int lastEventId;

  EventRegistration({required this.queueId, required this.lastEventId});
}

class EventPollResponse {
  final List<ZulipEvent> events;

  EventPollResponse({required this.events});
}
```

### 4. Event Polling Loop

```dart
// lib/services/call_event_poller.dart
import 'dart:async';
import 'package:flutter/foundation.dart';

class CallEventPoller {
  final ZulipEventService _eventService;
  Timer? _pollTimer;
  String? _queueId;
  int _lastEventId = -1;
  bool _isPolling = false;

  final StreamController<ZulipEvent> _eventController =
      StreamController<ZulipEvent>.broadcast();

  Stream<ZulipEvent> get events => _eventController.stream;

  CallEventPoller(this._eventService);

  /// Start event polling
  Future<void> startPolling() async {
    if (_isPolling) return;

    try {
      // Register for events
      final registration = await _eventService.registerForEvents();
      _queueId = registration.queueId;
      _lastEventId = registration.lastEventId;

      _isPolling = true;
      _poll();

      debugPrint('Event polling started: queue_id=$_queueId');
    } catch (e) {
      debugPrint('Failed to start event polling: $e');
      // Retry after 5 seconds
      await Future.delayed(const Duration(seconds: 5));
      startPolling();
    }
  }

  /// Stop event polling
  void stopPolling() {
    _isPolling = false;
    _pollTimer?.cancel();
    debugPrint('Event polling stopped');
  }

  /// Internal polling loop
  Future<void> _poll() async {
    if (!_isPolling || _queueId == null) return;

    try {
      final response = await _eventService.pollEvents(
        queueId: _queueId!,
        lastEventId: _lastEventId,
      );

      for (final event in response.events) {
        _lastEventId = event.id;

        // Filter for call events
        if (event.type == 'call' || event.type == 'group_call') {
          _eventController.add(event);
          debugPrint('Received ${event.type} event: ${event.op}');
        }
      }

      // Continue polling immediately
      _poll();
    } on TimeoutException {
      // Normal timeout, continue polling
      _poll();
    } catch (e) {
      debugPrint('Event poll error: $e');

      // Wait before retrying
      await Future.delayed(const Duration(seconds: 5));

      // Restart polling (will re-register if needed)
      _isPolling = false;
      startPolling();
    }
  }

  void dispose() {
    stopPolling();
    _eventController.close();
  }
}
```

## Event Models

```dart
// lib/models/call_event.dart
class ZulipEvent {
  final int id;
  final String type;
  final String op;
  final Map<String, dynamic> data;

  ZulipEvent({
    required this.id,
    required this.type,
    required this.op,
    required this.data,
  });

  factory ZulipEvent.fromJson(Map<String, dynamic> json) {
    return ZulipEvent(
      id: json['id'],
      type: json['type'],
      op: json['op'],
      data: json,
    );
  }

  /// Convert to CallEvent for call events
  CallEvent toCallEvent() {
    assert(type == 'call' || type == 'group_call');
    return CallEvent.fromJson(data);
  }
}

class CallEvent {
  final String type;              // 'call' or 'group_call'
  final String op;                // 'initiated', 'incoming_call', etc.
  final String callId;
  final String callType;          // 'audio' or 'video'
  final CallParticipant sender;
  final CallParticipant? receiver;
  final CallParticipant? host;
  final List<GroupCallParticipant>? participants;
  final String? jitsiUrl;
  final String state;
  final String timestamp;
  final bool? receiverWasOffline;
  final String? reason;
  final int? timeoutSeconds;
  final String? title;
  final int? streamId;
  final String? topic;
  final int? inviterId;
  final bool? wasOffline;

  CallEvent({
    required this.type,
    required this.op,
    required this.callId,
    required this.callType,
    required this.sender,
    this.receiver,
    this.host,
    this.participants,
    this.jitsiUrl,
    required this.state,
    required this.timestamp,
    this.receiverWasOffline,
    this.reason,
    this.timeoutSeconds,
    this.title,
    this.streamId,
    this.topic,
    this.inviterId,
    this.wasOffline,
  });

  factory CallEvent.fromJson(Map<String, dynamic> json) {
    return CallEvent(
      type: json['type'],
      op: json['op'],
      callId: json['call_id'],
      callType: json['call_type'],
      sender: CallParticipant.fromJson(json['sender']),
      receiver: json['receiver'] != null
          ? CallParticipant.fromJson(json['receiver'])
          : null,
      host: json['host'] != null
          ? CallParticipant.fromJson(json['host'])
          : null,
      participants: json['participants'] != null
          ? (json['participants'] as List)
              .map((p) => GroupCallParticipant.fromJson(p))
              .toList()
          : null,
      jitsiUrl: json['jitsi_url'],
      state: json['state'],
      timestamp: json['timestamp'],
      receiverWasOffline: json['receiver_was_offline'],
      reason: json['reason'],
      timeoutSeconds: json['timeout_seconds'],
      title: json['title'],
      streamId: json['stream_id'],
      topic: json['topic'],
      inviterId: json['inviter_id'],
      wasOffline: json['was_offline'],
    );
  }

  bool get isGroupCall => type == 'group_call';
}

class CallParticipant {
  final int userId;
  final String fullName;

  CallParticipant({
    required this.userId,
    required this.fullName,
  });

  factory CallParticipant.fromJson(Map<String, dynamic> json) {
    return CallParticipant(
      userId: json['user_id'],
      fullName: json['full_name'],
    );
  }

  Map<String, dynamic> toJson() => {
    'user_id': userId,
    'full_name': fullName,
  };
}

class GroupCallParticipant {
  final int userId;
  final String fullName;
  final String state;  // 'invited', 'joined', 'left', 'declined', 'missed'
  final bool isHost;

  GroupCallParticipant({
    required this.userId,
    required this.fullName,
    required this.state,
    required this.isHost,
  });

  factory GroupCallParticipant.fromJson(Map<String, dynamic> json) {
    return GroupCallParticipant(
      userId: json['user_id'],
      fullName: json['full_name'],
      state: json['state'],
      isHost: json['is_host'],
    );
  }
}
```

## State Management

```dart
// lib/providers/call_state_manager.dart
import 'package:flutter/foundation.dart';

enum CallStatus {
  idle,
  outgoing,     // Calling someone
  incoming,     // Receiving a call
  ringing,      // Other party acknowledged
  active,       // Call in progress
}

class Call {
  final String callId;
  final String callType;
  final CallParticipant sender;
  final CallParticipant receiver;
  final String? jitsiUrl;
  final String state;

  Call({
    required this.callId,
    required this.callType,
    required this.sender,
    required this.receiver,
    this.jitsiUrl,
    required this.state,
  });

  Call copyWith({
    String? state,
    String? jitsiUrl,
  }) {
    return Call(
      callId: callId,
      callType: callType,
      sender: sender,
      receiver: receiver,
      jitsi Url: jitsiUrl ?? this.jitsiUrl,
      state: state ?? this.state,
    );
  }
}

class GroupCall {
  final String callId;
  final String callType;
  final CallParticipant host;
  final List<GroupCallParticipant> participants;
  final String jitsiUrl;
  final String? title;

  GroupCall({
    required this.callId,
    required this.callType,
    required this.host,
    required this.participants,
    required this.jitsiUrl,
    this.title,
  });

  GroupCall copyWith({
    List<GroupCallParticipant>? participants,
  }) {
    return GroupCall(
      callId: callId,
      callType: callType,
      host: host,
      participants: participants ?? this.participants,
      jitsiUrl: jitsiUrl,
      title: title,
    );
  }
}

class CallStateManager extends ChangeNotifier {
  Call? _activeCall;
  GroupCall? _activeGroupCall;
  CallStatus _status = CallStatus.idle;
  final List<CallEvent> _missedCalls = [];

  Call? get activeCall => _activeCall;
  GroupCall? get activeGroupCall => _activeGroupCall;
  CallStatus get status => _status;
  List<CallEvent> get missedCalls => List.unmodifiable(_missedCalls);

  bool get hasActiveCall => _activeCall != null || _activeGroupCall != null;

  /// Handle incoming call event
  void handleCallEvent(CallEvent event) {
    debugPrint('Handling ${event.type} event: ${event.op}');

    if (event.isGroupCall) {
      _handleGroupCallEvent(event);
    } else {
      _handleCallEvent(event);
    }

    notifyListeners();
  }

  void _handleCallEvent(CallEvent event) {
    switch (event.op) {
      case 'initiated':
        _handleCallInitiated(event);
        break;
      case 'incoming_call':
        _handleIncomingCall(event);
        break;
      case 'ringing':
        _handleCallRinging(event);
        break;
      case 'accepted':
        _handleCallAccepted(event);
        break;
      case 'declined':
      case 'ended':
      case 'cancelled':
        _handleCallEnded(event);
        break;
      case 'missed':
        _handleCallMissed(event);
        break;
    }
  }

  void _handleCallInitiated(CallEvent event) {
    _activeCall = Call(
      callId: event.callId,
      callType: event.callType,
      sender: event.sender,
      receiver: event.receiver!,
      jitsiUrl: event.jitsiUrl,
      state: 'calling',
    );
    _status = CallStatus.outgoing;
  }

  void _handleIncomingCall(CallEvent event) {
    _activeCall = Call(
      callId: event.callId,
      callType: event.callType,
      sender: event.sender,
      receiver: event.receiver!,
      jitsiUrl: event.jitsiUrl,
      state: 'incoming',
    );
    _status = CallStatus.incoming;

    // Trigger UI to show incoming call screen
  }

  void _handleCallRinging(CallEvent event) {
    if (_activeCall?.callId == event.callId) {
      _activeCall = _activeCall!.copyWith(state: 'ringing');
      _status = CallStatus.ringing;
    }
  }

  void _handleCallAccepted(CallEvent event) {
    if (_activeCall?.callId == event.callId) {
      _activeCall = _activeCall!.copyWith(
        state: 'accepted',
        jitsiUrl: event.jitsiUrl,
      );
      _status = CallStatus.active;

      // Trigger Jitsi join
    }
  }

  void _handleCallEnded(CallEvent event) {
    if (_activeCall?.callId == event.callId) {
      _activeCall = null;
      _status = CallStatus.idle;
    }
  }

  void _handleCallMissed(CallEvent event) {
    _missedCalls.add(event);
    _activeCall = null;
    _status = CallStatus.idle;
  }

  void _handleGroupCallEvent(CallEvent event) {
    switch (event.op) {
      case 'created':
        _activeGroupCall = GroupCall(
          callId: event.callId,
          callType: event.callType,
          host: event.host!,
          participants: event.participants!,
          jitsiUrl: event.jitsiUrl!,
          title: event.title,
        );
        _status = CallStatus.active;
        break;
      case 'participant_invited':
        _activeGroupCall = GroupCall(
          callId: event.callId,
          callType: event.callType,
          host: event.host!,
          participants: event.participants!,
          jitsiUrl: event.jitsiUrl!,
          title: event.title,
        );
        _status = CallStatus.incoming;
        break;
      case 'participant_joined':
      case 'participant_left':
      case 'participant_declined':
        if (_activeGroupCall?.callId == event.callId) {
          _activeGroupCall = _activeGroupCall!.copyWith(
            participants: event.participants,
          );
        }
        break;
      case 'ended':
        if (_activeGroupCall?.callId == event.callId) {
          _activeGroupCall = null;
          _status = CallStatus.idle;
        }
        break;
    }
  }

  /// Clear missed calls
  void clearMissedCalls() {
    _missedCalls.clear();
    notifyListeners();
  }
}
```

## Push Notifications

```dart
// lib/services/call_push_handler.dart
import 'package:firebase_messaging/firebase_messaging.dart';
import 'package:flutter_callkit_incoming/flutter_callkit_incoming.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class CallPushHandler {
  static final FlutterLocalNotificationsPlugin _localNotifications =
      FlutterLocalNotificationsPlugin();

  static Future<void> initialize() async {
    // Initialize local notifications
    await _localNotifications.initialize(
      const InitializationSettings(
        android: AndroidInitializationSettings('@mipmap/ic_launcher'),
        iOS: DarwinInitializationSettings(),
      ),
    );

    // Request permissions
    await FirebaseMessaging.instance.requestPermission(
      alert: true,
      badge: true,
      sound: true,
      criticalAlert: true, // For call notifications
    );

    // Setup message handlers
    FirebaseMessaging.onMessage.listen(_handleForegroundMessage);
    FirebaseMessaging.onBackgroundMessage(_handleBackgroundMessage);

    // Setup CallKit action listener
    FlutterCallkitIncoming.onEvent.listen(_handleCallKitAction);
  }

  static Future<void> _handleForegroundMessage(RemoteMessage message) async {
    final data = message.data;

    if (data['event'] == 'call') {
      // Show incoming call UI directly (app is in foreground)
      _showIncomingCallScreen(data);
    } else if (data['event'] == 'missed_call') {
      _showMissedCallNotification(data);
    } else if (data['event'] == 'group_call') {
      _showGroupCallInvitation(data);
    }
  }

  @pragma('vm:entry-point')
  static Future<void> _handleBackgroundMessage(RemoteMessage message) async {
    final data = message.data;

    if (data['event'] == 'call') {
      // Show CallKit (iOS) or Heads-up notification (Android)
      await _showCallKitIncoming(data);
    } else if (data['event'] == 'missed_call') {
      await _showMissedCallNotification(data);
    }
  }

  static Future<void> _showCallKitIncoming(Map<String, dynamic> data) async {
    await FlutterCallkitIncoming.showCallkitIncoming(
      CallKitParams(
        id: data['call_id'],
        nameCaller: data['sender_name'] ?? data['sender_full_name'],
        appName: 'Zulip',
        avatar: data['sender_avatar_url'],
        handle: data['sender_email'],
        type: data['call_type'] == 'video' ? 1 : 0,
        duration: 90000, // 90 second timeout
        textAccept: 'Accept',
        textDecline: 'Decline',
        textMissedCall: 'Missed call',
        textCallback: 'Call back',
        extra: data,
        headers: {},
        android: const AndroidParams(
          isCustomNotification: true,
          isShowLogo: false,
          ringtonePath: 'system_ringtone_default',
          backgroundColor: '#0a0a0a',
          backgroundUrl: 'assets/images/call_background.png',
          actionColor: '#4CAF50',
          incomingCallNotificationChannelName: 'Incoming Call',
        ),
        ios: IOSParams(
          iconName: 'CallKitLogo',
          handleType: 'generic',
          supportsVideo: data['call_type'] == 'video',
          maximumCallGroups: 1,
          maximumCallsPerCallGroup: 1,
          audioSessionMode: 'default',
          audioSessionActive: true,
          audioSessionPreferredSampleRate: 44100.0,
          audioSessionPreferredIOBufferDuration: 0.005,
          supportsDTMF: false,
          supportsHolding: false,
          supportsGrouping: false,
          supportsUngrouping: false,
          ringtonePath: 'system_ringtone_default',
        ),
      ),
    );
  }

  static Future<void> _handleCallKitAction(CallKitEvent event) async {
    final callId = event.body['id'];

    switch (event.event) {
      case Event.actionCallAccept:
        // Accept call via API
        await _acceptCall(callId);
        break;
      case Event.actionCallDecline:
        // Decline call via API
        await _declineCall(callId);
        break;
      case Event.actionCallEnd:
        // End call via API
        await _endCall(callId);
        break;
    }
  }

  static Future<void> _showMissedCallNotification(Map<String, dynamic> data) async {
    await _localNotifications.show(
      data['call_id'].hashCode,
      'Missed ${data['call_type']} call',
      'From ${data['sender_name'] ?? data['sender_full_name']}',
      const NotificationDetails(
        android: AndroidNotificationDetails(
          'missed_calls',
          'Missed Calls',
          channelDescription: 'Notifications for missed calls',
          importance: Importance.high,
          priority: Priority.high,
          icon: '@mipmap/ic_launcher',
        ),
        iOS: DarwinNotificationDetails(),
      ),
    );
  }

  static void _showIncomingCallScreen(Map<String, dynamic> data) {
    // Navigate to incoming call screen
    // Implementation depends on your navigation setup
  }

  static void _showGroupCallInvitation(Map<String, dynamic> data) {
    // Show group call invitation dialog
  }

  static Future<void> _acceptCall(String callId) async {
    // Implement API call to accept
  }

  static Future<void> _declineCall(String callId) async {
    // Implement API call to decline
  }

  static Future<void> _endCall(String callId) async {
    // Implement API call to end
  }
}
```

## API Integration

```dart
// lib/services/call_api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class CallApiService {
  final String baseUrl;
  final String apiKey;
  final String email;

  CallApiService({
    required this.baseUrl,
    required this.apiKey,
    required this.email,
  });

  Map<String, String> get _authHeaders => {
    'Authorization': 'Basic ${base64Encode(utf8.encode('$email:$apiKey'))}',
    'Content-Type': 'application/x-www-form-urlencoded',
  };

  /// Create a 1-to-1 call
  Future<CallResponse> createCall({
    required String recipientEmail,
    required bool isVideo,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/create'),
      headers: _authHeaders,
      body: {
        'recipient_email': recipientEmail,
        'call_type': isVideo ? 'video' : 'audio',
      },
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to create call: ${response.body}');
    }

    final data = jsonDecode(response.body);
    return CallResponse(
      callId: data['call_id'],
      jitsiUrl: data['call_url'],
      callType: data['call_type'],
      roomName: data['room_name'],
      receiverOnline: data['receiver_online'] ?? true,
      recipient: Recipient(
        userId: data['recipient']['user_id'],
        fullName: data['recipient']['full_name'],
        email: data['recipient']['email'],
      ),
    );
  }

  /// Respond to a call (accept or decline)
  Future<void> respondToCall(String callId, bool accept) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/$callId/respond'),
      headers: _authHeaders,
      body: {'response': accept ? 'accept' : 'decline'},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to respond to call: ${response.body}');
    }
  }

  /// End a call
  Future<void> endCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/$callId/end'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to end call: ${response.body}');
    }
  }

  /// Cancel a call (before receiver answers)
  Future<void> cancelCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/$callId/cancel'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to cancel call: ${response.body}');
    }
  }

  /// Send heartbeat for active call
  Future<void> sendHeartbeat(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/heartbeat'),
      headers: _authHeaders,
      body: {'call_id': callId},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to send heartbeat: ${response.body}');
    }
  }

  /// Acknowledge incoming call (set to ringing state)
  Future<void> acknowledgeCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/acknowledge'),
      headers: _authHeaders,
      body: {'call_id': callId},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to acknowledge call: ${response.body}');
    }
  }

  // ========== Group Call APIs ==========

  /// Create a group call
  Future<GroupCallResponse> createGroupCall({
    required String callType,
    String? title,
    int? streamId,
    String? topic,
    List<int>? userIds,
  }) async {
    final body = {
      'call_type': callType,
      if (title != null) 'title': title,
      if (streamId != null) 'stream_id': streamId.toString(),
      if (topic != null) 'topic': topic,
      if (userIds != null && userIds.isNotEmpty)
        'user_ids': userIds.join(','),
    };

    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/create'),
      headers: _authHeaders,
      body: body,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to create group call: ${response.body}');
    }

    final data = jsonDecode(response.body);
    return GroupCallResponse.fromJson(data);
  }

  /// Invite users to a group call
  Future<void> inviteToGroupCall(String callId, List<int> userIds) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/invite'),
      headers: _authHeaders,
      body: {'user_ids': userIds.join(',')},
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to invite to group call: ${response.body}');
    }
  }

  /// Join a group call
  Future<GroupCallJoinResponse> joinGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/join'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to join group call: ${response.body}');
    }

    final data = jsonDecode(response.body);
    return GroupCallJoinResponse(
      callUrl: data['call_url'],
      callType: data['call_type'],
      title: data['title'],
      participantCount: data['participant_count'],
    );
  }

  /// Leave a group call
  Future<void> leaveGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/leave'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to leave group call: ${response.body}');
    }
  }

  /// Decline a group call invitation
  Future<void> declineGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/decline'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to decline group call: ${response.body}');
    }
  }

  /// End a group call (host only)
  Future<void> endGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/end'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to end group call: ${response.body}');
    }
  }

  /// Get group call status
  Future<GroupCallStatus> getGroupCallStatus(String callId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/status'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to get group call status: ${response.body}');
    }

    final data = jsonDecode(response.body);
    return GroupCallStatus.fromJson(data['call']);
  }

  /// Get group call participants
  Future<List<GroupCallParticipantInfo>> getGroupCallParticipants(String callId) async {
    final response = await http.get(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/participants'),
      headers: _authHeaders,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to get participants: ${response.body}');
    }

    final data = jsonDecode(response.body);
    return (data['participants'] as List)
        .map((p) => GroupCallParticipantInfo.fromJson(p))
        .toList();
  }
}

// Response models
class CallResponse {
  final String callId;
  final String jitsiUrl;
  final String callType;
  final String roomName;
  final bool receiverOnline;
  final Recipient recipient;

  CallResponse({
    required this.callId,
    required this.jitsiUrl,
    required this.callType,
    required this.roomName,
    required this.receiverOnline,
    required this.recipient,
  });
}

class Recipient {
  final int userId;
  final String fullName;
  final String email;

  Recipient({
    required this.userId,
    required this.fullName,
    required this.email,
  });
}

class GroupCallResponse {
  final String callId;
  final String callUrl;
  final String callType;
  final String roomName;
  final String? title;
  final int invitedCount;

  GroupCallResponse({
    required this.callId,
    required this.callUrl,
    required this.callType,
    required this.roomName,
    this.title,
    required this.invitedCount,
  });

  factory GroupCallResponse.fromJson(Map<String, dynamic> json) {
    return GroupCallResponse(
      callId: json['call_id'],
      callUrl: json['call_url'],
      callType: json['call_type'],
      roomName: json['room_name'],
      title: json['title'],
      invitedCount: json['invited_count'],
    );
  }
}

class GroupCallJoinResponse {
  final String callUrl;
  final String callType;
  final String? title;
  final int participantCount;

  GroupCallJoinResponse({
    required this.callUrl,
    required this.callType,
    this.title,
    required this.participantCount,
  });
}

class GroupCallStatus {
  final String callId;
  final String callType;
  final String state;
  final String? title;
  final String jitsiUrl;
  final int participantCount;
  final int maxParticipants;

  GroupCallStatus({
    required this.callId,
    required this.callType,
    required this.state,
    this.title,
    required this.jitsiUrl,
    required this.participantCount,
    required this.maxParticipants,
  });

  factory GroupCallStatus.fromJson(Map<String, dynamic> json) {
    return GroupCallStatus(
      callId: json['call_id'],
      callType: json['call_type'],
      state: json['state'],
      title: json['title'],
      jitsiUrl: json['jitsi_url'],
      participantCount: json['participant_count'],
      maxParticipants: json['max_participants'],
    );
  }
}

class GroupCallParticipantInfo {
  final int userId;
  final String fullName;
  final String email;
  final String state;
  final bool isHost;
  final String invitedAt;
  final String? joinedAt;
  final String? leftAt;

  GroupCallParticipantInfo({
    required this.userId,
    required this.fullName,
    required this.email,
    required this.state,
    required this.isHost,
    required this.invitedAt,
    this.joinedAt,
    this.leftAt,
  });

  factory GroupCallParticipantInfo.fromJson(Map<String, dynamic> json) {
    return GroupCallParticipantInfo(
      userId: json['user_id'],
      fullName: json['full_name'],
      email: json['email'],
      state: json['state'],
      isHost: json['is_host'],
      invitedAt: json['invited_at'],
      joinedAt: json['joined_at'],
      leftAt: json['left_at'],
    );
  }
}
```

## Offline Handling

When creating a call, the API returns a `receiver_online` flag indicating if the receiver is currently online:

```dart
final callResponse = await callApiService.createCall(
  recipientEmail: 'user@example.com',
  isVideo: true,
);

if (!callResponse.receiverOnline) {
  // User is offline - show appropriate UI
  showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('User may be offline'),
      content: Text(
        '${callResponse.recipient.fullName} appears to be offline. '
        'They will receive a notification about your call.',
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('OK'),
        ),
      ],
    ),
  );
} else {
  // User is online - show normal calling UI
  showCallingScreen(callResponse);
}
```

The backend uses Zulip's presence system (`receiver_is_off_zulip()`) to determine if a user has any active event queues. If not, they're considered offline and the event will be queued for delivery when they come online, plus a push notification is sent.

## Missed Calls

### Handling Missed Call Events

```dart
void handleMissedCall(CallEvent event) {
  // Add to missed calls list
  final callStateManager = context.read<CallStateManager>();
  callStateManager.handleCallEvent(event);

  // Show notification
  showNotification(
    title: 'Missed ${event.callType} call',
    body: event.receiver?.fullName ?? 'Unknown caller',
    payload: jsonEncode({
      'type': 'missed_call',
      'call_id': event.callId,
      'sender_id': event.sender.userId,
    }),
  );

  // Optionally show in-app banner
  ScaffoldMessenger.of(context).showSnackBar(
    SnackBar(
      content: Text('Missed call from ${event.receiver?.fullName}'),
      action: SnackBarAction(
        label: 'Call Back',
        onPressed: () => _callBack(event),
      ),
      duration: const Duration(seconds: 10),
    ),
  );
}

Future<void> _callBack(CallEvent missedCallEvent) async {
  // Create a new call to the person who called
  final callApiService = context.read<CallApiService>();

  try {
    final response = await callApiService.createCall(
      recipientEmail: missedCallEvent.sender.email,  // Would need to get email
      isVideo: missedCallEvent.callType == 'video',
    );

    // Navigate to calling screen
    Navigator.pushNamed(
      context,
      '/calling',
      arguments: response,
    );
  } catch (e) {
    showError('Failed to call back: $e');
  }
}
```

### Missed Call UI

```dart
// lib/widgets/missed_calls_list.dart
class MissedCallsList extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    final callStateManager = context.watch<CallStateManager>();
    final missedCalls = callStateManager.missedCalls;

    if (missedCalls.isEmpty) {
      return const Center(
        child: Text('No missed calls'),
      );
    }

    return ListView.builder(
      itemCount: missedCalls.length,
      itemBuilder: (context, index) {
        final call = missedCalls[index];
        return ListTile(
          leading: Icon(
            call.callType == 'video'
                ? Icons.videocam
                : Icons.phone,
            color: Colors.red,
          ),
          title: Text(call.sender.fullName),
          subtitle: Text(_formatTimestamp(call.timestamp)),
          trailing: IconButton(
            icon: const Icon(Icons.phone_callback),
            onPressed: () => _callBack(context, call),
          ),
        );
      },
    );
  }

  String _formatTimestamp(String timestamp) {
    final dateTime = DateTime.parse(timestamp);
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (difference.inDays > 0) {
      return '${difference.inDays}d ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours}h ago';
    } else if (difference.inMinutes > 0) {
      return '${difference.inMinutes}m ago';
    } else {
      return 'Just now';
    }
  }
}
```

## Complete Examples

### Example 1: Making a Call

```dart
Future<void> makeCall({
  required BuildContext context,
  required String recipientEmail,
  required bool isVideo,
}) async {
  final callApiService = context.read<CallApiService>();
  final callStateManager = context.read<CallStateManager>();

  try {
    // Show loading
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(
        child: CircularProgressIndicator(),
      ),
    );

    // Create call
    final response = await callApiService.createCall(
      recipientEmail: recipientEmail,
      isVideo: isVideo,
    );

    // Close loading
    Navigator.pop(context);

    // Check if receiver is offline
    if (!response.receiverOnline) {
      showOfflineWarning(context, response.recipient.fullName);
    }

    // Navigate to calling screen
    Navigator.pushNamed(
      context,
      '/calling',
      arguments: CallScreenArguments(
        callId: response.callId,
        callType: response.callType,
        jitsiUrl: response.jitsiUrl,
        otherUser: response.recipient.fullName,
        isOutgoing: true,
      ),
    );
  } catch (e) {
    Navigator.pop(context); // Close loading
    showErrorDialog(context, 'Failed to start call: $e');
  }
}
```

### Example 2: Handling Incoming Call

```dart
// This would be triggered by the event poller or push notification
Future<void> handleIncomingCall(
  BuildContext context,
  CallEvent event,
) async {
  // Show incoming call screen
  final result = await Navigator.pushNamed(
    context,
    '/incoming-call',
    arguments: IncomingCallArguments(
      callId: event.callId,
      callType: event.callType,
      callerName: event.sender.fullName,
      callerId: event.sender.userId,
    ),
  );

  if (result == 'accept') {
    // User accepted - respond to call
    final callApiService = context.read<CallApiService>();
    await callApiService.respondToCall(event.callId, true);

    // Navigate to active call screen
    Navigator.pushNamed(
      context,
      '/active-call',
      arguments: ActiveCallArguments(
        callId: event.callId,
        jitsiUrl: event.jitsiUrl!,
      ),
    );
  } else if (result == 'decline') {
    // User declined
    final callApiService = context.read<CallApiService>();
    await callApiService.respondToCall(event.callId, false);
  }
}
```

### Example 3: Group Call Creation

```dart
Future<void> createGroupCall({
  required BuildContext context,
  required String title,
  required List<int> participants,
  required bool isVideo,
}) async {
  final callApiService = context.read<CallApiService>();

  try {
    // Create group call
    final response = await callApiService.createGroupCall(
      callType: isVideo ? 'video' : 'audio',
      title: title,
      userIds: participants,
    );

    // Navigate to group call screen
    Navigator.pushNamed(
      context,
      '/group-call',
      arguments: GroupCallArguments(
        callId: response.callId,
        jitsiUrl: response.callUrl,
        title: response.title ?? 'Group Call',
      ),
    );
  } catch (e) {
    showErrorDialog(context, 'Failed to create group call: $e');
  }
}
```

## Testing

### Unit Tests

```dart
// test/call_state_manager_test.dart
import 'package:flutter_test/flutter_test.dart';

void main() {
  group('CallStateManager', () {
    late CallStateManager manager;

    setUp(() {
      manager = CallStateManager();
    });

    test('initial state is idle', () {
      expect(manager.status, CallStatus.idle);
      expect(manager.activeCall, isNull);
    });

    test('handles incoming call event', () {
      final event = CallEvent(
        type: 'call',
        op: 'incoming_call',
        callId: 'test-123',
        callType: 'video',
        sender: CallParticipant(userId: 1, fullName: 'Alice'),
        receiver: CallParticipant(userId: 2, fullName: 'Bob'),
        state: 'ringing',
        timestamp: DateTime.now().toIso8601String(),
      );

      manager.handleCallEvent(event);

      expect(manager.status, CallStatus.incoming);
      expect(manager.activeCall?.callId, 'test-123');
    });

    test('handles call ended event', () {
      // Setup: create active call
      final incomingEvent = CallEvent(/* ... */);
      manager.handleCallEvent(incomingEvent);

      // End call
      final endEvent = CallEvent(
        type: 'call',
        op: 'ended',
        callId: 'test-123',
        /* ... */
      );
      manager.handleCallEvent(endEvent);

      expect(manager.status, CallStatus.idle);
      expect(manager.activeCall, isNull);
    });
  });
}
```

### Integration Tests

```dart
// integration_test/call_flow_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:integration_test/integration_test.dart';

void main() {
  IntegrationTestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('complete call flow', (tester) async {
    // 1. Launch app
    await tester.pumpWidget(MyApp());

    // 2. Navigate to user list
    await tester.tap(find.text('Contacts'));
    await tester.pumpAndSettle();

    // 3. Select user and start call
    await tester.tap(find.text('Alice'));
    await tester.pumpAndSettle();
    await tester.tap(find.byIcon(Icons.videocam));
    await tester.pumpAndSettle();

    // 4. Verify calling screen shown
    expect(find.text('Calling Alice...'), findsOneWidget);

    // 5. Simulate call accepted event (would come from backend)
    // ...

    // 6. Verify active call screen
    expect(find.text('Connected'), findsOneWidget);

    // 7. End call
    await tester.tap(find.byIcon(Icons.call_end));
    await tester.pumpAndSettle();

    // 8. Verify returned to previous screen
    expect(find.text('Alice'), findsOneWidget);
  });
}
```

## Troubleshooting

### Common Issues

**1. Events not received**
- Check event registration includes `'call'` and `'group_call'` types
- Verify queue_id is valid
- Check network connectivity
- Review backend logs for event dispatch

**2. Push notifications not working**
- Verify Firebase configuration
- Check FCM token registration
- Test with Firebase Console
- Review notification permissions

**3. CallKit not showing (iOS)**
- Check Info.plist includes required permissions
- Verify `flutter_callkit_incoming` setup
- Test with device (not simulator)
- Check iOS notification permissions

**4. Calls immediately ending**
- Verify heartbeat is being sent every 30s
- Check network stability
- Review backend cleanup worker logs

**5. Jitsi not loading**
- Verify Jitsi URL format
- Check Jitsi server configuration
- Review CORS settings
- Test URL in browser first

### Debug Logging

Enable debug logging:

```dart
// In main.dart
void main() {
  // Enable debug logging
  debugPrint = (String? message, {int? wrapWidth}) {
    print('[${DateTime.now()}] $message');
  };

  // ... rest of setup
}
```

### Backend Event Verification

Check backend logs to verify events are being sent:

```bash
# SSH into Zulip server
cd /home/zulip/deployments/current

# Check call event logs
tail -f /var/log/zulip/zulip_calls_plugin.log

# Check event queue logs
tail -f /var/log/zulip/events.log
```

## Best Practices

1. **Always send heartbeat** every 30 seconds during active calls
2. **Handle network failures** gracefully with reconnection logic
3. **Show offline indicators** when `receiver_online` is false
4. **Clean up state** when app goes to background
5. **Test on real devices** - simulators don't support CallKit fully
6. **Use background isolates** for event polling to avoid UI jank
7. **Implement proper error handling** for all API calls
8. **Cache missed calls** locally for offline viewing
9. **Request permissions** early (camera, microphone, notifications)
10. **Follow platform guidelines** for call UI (Material Design / Human Interface Guidelines)

## Additional Resources

- [Zulip Event System Documentation](https://zulip.readthedocs.io/en/latest/subsystems/events-system.html)
- [Jitsi Meet Flutter SDK](https://pub.dev/packages/jitsi_meet_flutter_sdk)
- [Flutter CallKit Incoming](https://pub.dev/packages/flutter_callkit_incoming)
- [Firebase Cloud Messaging](https://firebase.google.com/docs/cloud-messaging/flutter/client)

## Support

For issues and questions:
- Check existing issues on GitHub
- Review server logs at `/var/log/zulip/zulip_calls_plugin.log`
- Test API endpoints with curl/Postman
- Enable debug logging in Flutter app

---

**Last Updated**: 2026-01-25
**Plugin Version**: 1.0.0
**Zulip Version**: Latest
