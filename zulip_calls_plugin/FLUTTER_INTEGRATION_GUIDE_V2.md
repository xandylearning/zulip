# Flutter Integration Guide for Zulip Calls Plugin v2.0

**Last Updated**: January 28, 2026  
**Plugin Version**: 2.0  
**Zulip Version**: Latest

## Overview

Complete integration guide for implementing the Zulip Calls Plugin in Flutter mobile applications. This guide covers both **WebSocket** and **Event Polling** integration approaches, supporting 1-to-1 calls, group calls, push notifications, and offline handling.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Architecture Overview](#architecture-overview)
3. [Setup & Dependencies](#setup--dependencies)
4. [Authentication](#authentication)
5. [Integration Approaches](#integration-approaches)
   - [Option A: WebSocket Integration](#option-a-websocket-integration)
   - [Option B: Event Polling Integration](#option-b-event-polling-integration)
6. [API Service Implementation](#api-service-implementation)
7. [Call State Management](#call-state-management)
8. [UI Components](#ui-components)
9. [Group Calls](#group-calls)
10. [Push Notifications](#push-notifications)
11. [Offline Handling](#offline-handling)
12. [Permissions](#permissions)
13. [Testing](#testing)
14. [Troubleshooting](#troubleshooting)

## Quick Start

```dart
// 1. Add dependencies to pubspec.yaml
dependencies:
  http: ^1.1.0
  web_socket_channel: ^2.4.0
  provider: ^6.1.1
  jitsi_meet_flutter_sdk: ^10.0.0
  permission_handler: ^11.1.0
  flutter_callkit_incoming: ^2.0.0
  firebase_messaging: ^14.7.0

// 2. Initialize services
void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await ZulipAuth.initialize();
  runApp(MyApp());
}

// 3. Make a call
final callApi = CallApiService(baseUrl: 'https://your-zulip.com');
final response = await callApi.initiateCall(
  recipientEmail: 'user@example.com',
  callType: 'video',
);
```

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    Flutter App                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌──────────────┐      ┌──────────────┐               │
│  │   UI Layer   │◄─────│ Call State   │               │
│  │              │      │   Manager    │               │
│  └──────┬───────┘      └──────┬───────┘               │
│         │                     │                        │
│         │              ┌───────▼───────┐               │
│         │              │  API Service  │               │
│         │              └───────┬───────┘               │
│         │                     │                        │
│  ┌──────▼───────┐    ┌────────▼────────┐             │
│  │   WebSocket  │    │  Event Poller   │             │
│  │   Service    │    │    Service      │             │
│  └──────┬───────┘    └────────┬────────┘             │
│         │                     │                        │
└─────────┼─────────────────────┼────────────────────────┘
          │                     │
          ▼                     ▼
┌─────────────────────────────────────────────────────────┐
│              Zulip Server                               │
│  ┌──────────────┐      ┌──────────────┐               │
│  │  WebSocket   │      │ Event Queue  │               │
│  │   Endpoint   │      │     API      │               │
│  └──────────────┘      └──────────────┘               │
│         │                     │                        │
│         └─────────┬───────────┘                       │
│                   ▼                                    │
│         ┌──────────────────┐                          │
│         │  Calls Plugin    │                          │
│         │  API Endpoints   │                          │
│         └──────────────────┘                          │
└─────────────────────────────────────────────────────────┘
```

## Setup & Dependencies

### pubspec.yaml

```yaml
name: zulip_mobile
description: Zulip mobile app with calls support

environment:
  sdk: '>=3.0.0 <4.0.0'

dependencies:
  flutter:
    sdk: flutter

  # HTTP & Networking
  http: ^1.1.0
  web_socket_channel: ^2.4.0

  # State Management
  provider: ^6.1.1

  # Video Calling
  jitsi_meet_flutter_sdk: ^10.0.0

  # Permissions
  permission_handler: ^11.1.0

  # Push Notifications
  firebase_messaging: ^14.7.0
  firebase_core: ^2.24.0
  flutter_local_notifications: ^16.3.0

  # CallKit (iOS) & ConnectionService (Android)
  flutter_callkit_incoming: ^2.0.0

  # Storage
  shared_preferences: ^2.2.2

  # Utilities
  intl: ^0.19.0
  uuid: ^4.0.0

dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^3.0.0
```

### Platform Configuration

#### Android (android/app/src/main/AndroidManifest.xml)

```xml
<manifest>
  <!-- Permissions -->
  <uses-permission android:name="android.permission.INTERNET"/>
  <uses-permission android:name="android.permission.CAMERA"/>
  <uses-permission android:name="android.permission.RECORD_AUDIO"/>
  <uses-permission android:name="android.permission.MODIFY_AUDIO_SETTINGS"/>
  <uses-permission android:name="android.permission.WAKE_LOCK"/>
  <uses-permission android:name="android.permission.VIBRATE"/>
  <uses-permission android:name="android.permission.USE_FULL_SCREEN_INTENT"/>

  <application>
    <!-- Firebase & Notifications -->
    <meta-data
      android:name="com.google.firebase.messaging.default_notification_channel_id"
      android:value="zulip_calls" />
  </application>
</manifest>
```

#### iOS (ios/Runner/Info.plist)

```xml
<key>NSCameraUsageDescription</key>
<string>We need camera access for video calls</string>
<key>NSMicrophoneUsageDescription</key>
<string>We need microphone access for audio and video calls</string>
<key>UIBackgroundModes</key>
<array>
  <string>audio</string>
  <string>voip</string>
  <string>remote-notification</string>
</array>
```

## Authentication

### ZulipAuth Service

```dart
// lib/services/zulip_auth.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ZulipAuth {
  static const String _baseUrlKey = 'zulip_base_url';
  static const String _apiKeyKey = 'zulip_api_key';
  static const String _userIdKey = 'zulip_user_id';
  static const String _emailKey = 'zulip_email';

  static String? _baseUrl;
  static String? _apiKey;
  static int? _userId;
  static String? _email;

  /// Initialize auth from stored credentials
  static Future<bool> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    _baseUrl = prefs.getString(_baseUrlKey);
    _apiKey = prefs.getString(_apiKeyKey);
    _userId = prefs.getInt(_userIdKey);
    _email = prefs.getString(_emailKey);
    return isAuthenticated;
  }

  static bool get isAuthenticated =>
      _baseUrl != null &&
      _apiKey != null &&
      _userId != null &&
      _email != null;

  /// Login with email and API key
  static Future<bool> login({
    required String baseUrl,
    required String email,
    required String apiKey,
  }) async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/v1/users/me'),
        headers: _getAuthHeaders(email, apiKey),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _baseUrl = baseUrl;
        _apiKey = apiKey;
        _userId = data['user_id'];
        _email = email;

        // Store credentials
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_baseUrlKey, baseUrl);
        await prefs.setString(_apiKeyKey, apiKey);
        await prefs.setInt(_userIdKey, _userId!);
        await prefs.setString(_emailKey, email);

        return true;
      }
    } catch (e) {
      print('Login error: $e');
    }
    return false;
  }

  /// Logout
  static Future<void> logout() async {
    _baseUrl = null;
    _apiKey = null;
    _userId = null;
    _email = null;

    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_baseUrlKey);
    await prefs.remove(_apiKeyKey);
    await prefs.remove(_userIdKey);
    await prefs.remove(_emailKey);
  }

  /// Get auth headers for API requests
  static Map<String, String> get authHeaders {
    if (!isAuthenticated) {
      throw Exception('Not authenticated');
    }
    return _getAuthHeaders(_email!, _apiKey!);
  }

  static Map<String, String> _getAuthHeaders(String email, String apiKey) {
    final credentials = base64Encode(utf8.encode('$email:$apiKey'));
    return {
      'Authorization': 'Basic $credentials',
      'Content-Type': 'application/json',
    };
  }

  static String get baseUrl => _baseUrl!;
  static int get userId => _userId!;
  static String get email => _email!;
}
```

## Integration Approaches

Choose one of two approaches for real-time call events:

### Option A: WebSocket Integration

**Best for**: Low latency, persistent connections, real-time updates

```dart
// lib/services/zulip_websocket_service.dart
import 'dart:async';
import 'dart:convert';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:zulip_auth.dart';

class ZulipWebSocketService {
  WebSocketChannel? _channel;
  StreamController<CallEvent>? _eventController;
  Timer? _heartbeatTimer;
  bool _isConnected = false;

  Stream<CallEvent> get events => _eventController?.stream ?? const Stream.empty();

  /// Connect to Zulip WebSocket
  Future<void> connect() async {
    if (_isConnected) return;

    try {
      final wsUrl = _buildWebSocketUrl();
      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _eventController = StreamController<CallEvent>.broadcast();
      _isConnected = true;

      // Listen for messages
      _channel!.stream.listen(
        (message) => _handleMessage(message),
        onError: (error) => _handleError(error),
        onDone: () => _handleDisconnect(),
      );

      // Start heartbeat
      _startHeartbeat();
    } catch (e) {
      print('WebSocket connection error: $e');
      rethrow;
    }
  }

  String _buildWebSocketUrl() {
    final baseUrl = ZulipAuth.baseUrl;
    final wsUrl = baseUrl.replaceFirst('https://', 'wss://').replaceFirst('http://', 'ws://');
    final email = ZulipAuth.email;
    final apiKey = ZulipAuth.authHeaders['Authorization']!.split(' ')[1];
    return '$wsUrl/api/v1/events?api_key=$apiKey&email=$email';
  }

  void _handleMessage(dynamic message) {
    try {
      final data = json.decode(message);
      if (data['type'] == 'call_event' || data['type'] == 'group_call_event') {
        _eventController?.add(CallEvent.fromJson(data));
      }
    } catch (e) {
      print('Error parsing WebSocket message: $e');
    }
  }

  void _handleError(dynamic error) {
    print('WebSocket error: $error');
    _isConnected = false;
    // Reconnect after delay
    Future.delayed(const Duration(seconds: 5), () => connect());
  }

  void _handleDisconnect() {
    _isConnected = false;
    _heartbeatTimer?.cancel();
    // Reconnect
    Future.delayed(const Duration(seconds: 2), () => connect());
  }

  void _startHeartbeat() {
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      _channel?.sink.add(json.encode({'type': 'ping'}));
    });
  }

  void disconnect() {
    _heartbeatTimer?.cancel();
    _channel?.sink.close();
    _eventController?.close();
    _isConnected = false;
  }
}
```

### Option B: Event Polling Integration

**Best for**: Reliability, offline support, simpler implementation

```dart
// lib/services/zulip_event_service.dart
import 'dart:async';
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:zulip_auth.dart';

class ZulipEventService {
  String? _queueId;
  int _lastEventId = -1;
  Timer? _pollTimer;
  bool _isPolling = false;
  final StreamController<CallEvent> _eventController =
      StreamController<CallEvent>.broadcast();

  Stream<CallEvent> get events => _eventController.stream;

  /// Register for call events
  Future<void> register() async {
    final response = await http.post(
      Uri.parse('${ZulipAuth.baseUrl}/api/v1/register'),
      headers: ZulipAuth.authHeaders,
      body: jsonEncode({
        'event_types': ['call', 'group_call'],
        'client_capabilities': {
          'notification_settings_null': false,
        },
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to register: ${response.body}');
    }

    final data = jsonDecode(response.body);
    _queueId = data['queue_id'];
    _lastEventId = data['last_event_id'] ?? -1;
  }

  /// Start polling for events
  Future<void> startPolling() async {
    if (_isPolling) return;

    if (_queueId == null) {
      await register();
    }

    _isPolling = true;
    _poll();
  }

  Future<void> _poll() async {
    if (!_isPolling || _queueId == null) return;

    try {
      final response = await http.get(
        Uri.parse(
          '${ZulipAuth.baseUrl}/api/v1/events'
          '?queue_id=$_queueId'
          '&last_event_id=$_lastEventId'
          '&dont_block=false',
        ),
        headers: ZulipAuth.authHeaders,
      ).timeout(const Duration(seconds: 90));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
        final events = (data['events'] as List? ?? []);

        for (final event in events) {
          _lastEventId = event['id'];
          if (event['type'] == 'call' || event['type'] == 'group_call') {
            _eventController.add(CallEvent.fromJson(event));
          }
        }
      }

      // Continue polling
      _poll();
    } on TimeoutException {
      // Normal timeout, continue polling
      _poll();
    } catch (e) {
      print('Event poll error: $e');
      await Future.delayed(const Duration(seconds: 5));
      _isPolling = false;
      await startPolling();
    }
  }

  void stopPolling() {
    _isPolling = false;
    _pollTimer?.cancel();
  }

  void dispose() {
    stopPolling();
    _eventController.close();
  }
}
```

## API Service Implementation

```dart
// lib/services/call_api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:zulip_auth.dart';

class CallApiService {
  final String baseUrl;

  CallApiService({required this.baseUrl});

  Map<String, String> get _headers => ZulipAuth.authHeaders;

  /// Initiate a 1-to-1 call
  Future<CallResponse> initiateCall({
    required String recipientEmail,
    required String callType, // 'audio' or 'video'
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/initiate'),
      headers: _headers,
      body: jsonEncode({
        'recipient_email': recipientEmail,
        'call_type': callType,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to initiate call: ${response.body}');
    }

    return CallResponse.fromJson(jsonDecode(response.body));
  }

  /// Acknowledge incoming call
  Future<void> acknowledgeCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/acknowledge'),
      headers: _headers,
      body: jsonEncode({'call_id': callId}),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to acknowledge call: ${response.body}');
    }
  }

  /// Respond to call (accept/decline)
  Future<void> respondToCall({
    required String callId,
    required bool accept,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/respond'),
      headers: _headers,
      body: jsonEncode({
        'call_id': callId,
        'response': accept ? 'accept' : 'decline',
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to respond: ${response.body}');
    }
  }

  /// Update call status
  Future<void> updateCallStatus({
    required String callId,
    required String status,
  }) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/status'),
      headers: _headers,
      body: jsonEncode({
        'call_id': callId,
        'status': status,
      }),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to update status: ${response.body}');
    }
  }

  /// End call
  Future<void> endCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/end'),
      headers: _headers,
      body: jsonEncode({'call_id': callId}),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to end call: ${response.body}');
    }
  }

  /// Send heartbeat for active call
  Future<void> sendHeartbeat(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/heartbeat'),
      headers: _headers,
      body: jsonEncode({'call_id': callId}),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to send heartbeat: ${response.body}');
    }
  }

  // ========== Group Call APIs ==========

  /// Create group call
  Future<GroupCallResponse> createGroupCall({
    required String callType,
    String? title,
    int? streamId,
    String? topic,
    List<int>? userIds,
  }) async {
    final body = <String, dynamic>{
      'call_type': callType,
      if (title != null) 'title': title,
      if (streamId != null) 'stream_id': streamId,
      if (topic != null) 'topic': topic,
      if (userIds != null && userIds.isNotEmpty)
        'user_ids': userIds.join(','),
    };

    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/create'),
      headers: _headers,
      body: jsonEncode(body),
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to create group call: ${response.body}');
    }

    return GroupCallResponse.fromJson(jsonDecode(response.body));
  }

  /// Join group call
  Future<GroupCallJoinResponse> joinGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/join'),
      headers: _headers,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to join group call: ${response.body}');
    }

    return GroupCallJoinResponse.fromJson(jsonDecode(response.body));
  }

  /// Leave group call
  Future<void> leaveGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/leave'),
      headers: _headers,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to leave group call: ${response.body}');
    }
  }

  /// Decline group call invitation
  Future<void> declineGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/decline'),
      headers: _headers,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to decline group call: ${response.body}');
    }
  }

  /// End group call (host only)
  Future<void> endGroupCall(String callId) async {
    final response = await http.post(
      Uri.parse('$baseUrl/api/v1/calls/group/$callId/end'),
      headers: _headers,
    );

    if (response.statusCode != 200) {
      throw Exception('Failed to end group call: ${response.body}');
    }
  }

  /// Get call history
  Future<CallHistoryResponse> getCallHistory({
    int? limit,
    String? anchor,
    bool? includeEnded,
  }) async {
    final queryParams = <String, String>{};
    if (limit != null) queryParams['limit'] = limit.toString();
    if (anchor != null) queryParams['anchor'] = anchor;
    if (includeEnded != null) queryParams['include_ended'] = includeEnded.toString();

    final uri = Uri.parse('$baseUrl/api/v1/calls/history').replace(
      queryParameters: queryParams,
    );

    final response = await http.get(uri, headers: _headers);

    if (response.statusCode != 200) {
      throw Exception('Failed to get call history: ${response.body}');
    }

    return CallHistoryResponse.fromJson(jsonDecode(response.body));
  }
}

// Response Models
class CallResponse {
  final String callId;
  final String callUrl;
  final String callType;
  final String roomName;
  final CallParticipant recipient;
  final bool receiverOnline;

  CallResponse({
    required this.callId,
    required this.callUrl,
    required this.callType,
    required this.roomName,
    required this.recipient,
    required this.receiverOnline,
  });

  factory CallResponse.fromJson(Map<String, dynamic> json) {
    return CallResponse(
      callId: json['call_id'],
      callUrl: json['call_url'],
      callType: json['call_type'],
      roomName: json['room_name'],
      recipient: CallParticipant.fromJson(json['recipient']),
      receiverOnline: json['receiver_online'] ?? true,
    );
  }
}

class CallParticipant {
  final int userId;
  final String fullName;
  final String email;

  CallParticipant({
    required this.userId,
    required this.fullName,
    required this.email,
  });

  factory CallParticipant.fromJson(Map<String, dynamic> json) {
    return CallParticipant(
      userId: json['user_id'],
      fullName: json['full_name'],
      email: json['email'],
    );
  }
}

class GroupCallResponse {
  final String callId;
  final String callUrl;
  final String callType;
  final String? title;
  final int invitedCount;

  GroupCallResponse({
    required this.callId,
    required this.callUrl,
    required this.callType,
    this.title,
    required this.invitedCount,
  });

  factory GroupCallResponse.fromJson(Map<String, dynamic> json) {
    return GroupCallResponse(
      callId: json['call_id'],
      callUrl: json['call_url'],
      callType: json['call_type'],
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

  factory GroupCallJoinResponse.fromJson(Map<String, dynamic> json) {
    return GroupCallJoinResponse(
      callUrl: json['call_url'],
      callType: json['call_type'],
      title: json['title'],
      participantCount: json['participant_count'],
    );
  }
}

class CallHistoryResponse {
  final List<CallHistoryItem> calls;
  final String? nextAnchor;

  CallHistoryResponse({
    required this.calls,
    this.nextAnchor,
  });

  factory CallHistoryResponse.fromJson(Map<String, dynamic> json) {
    return CallHistoryResponse(
      calls: (json['calls'] as List)
          .map((c) => CallHistoryItem.fromJson(c))
          .toList(),
      nextAnchor: json['next_anchor'],
    );
  }
}

class CallHistoryItem {
  final String callId;
  final String callType;
  final String state;
  final String createdAt;
  final String? endedAt;
  final CallParticipant? otherParticipant;

  CallHistoryItem({
    required this.callId,
    required this.callType,
    required this.state,
    required this.createdAt,
    this.endedAt,
    this.otherParticipant,
  });

  factory CallHistoryItem.fromJson(Map<String, dynamic> json) {
    return CallHistoryItem(
      callId: json['call_id'],
      callType: json['call_type'],
      state: json['state'],
      createdAt: json['created_at'],
      endedAt: json['ended_at'],
      otherParticipant: json['other_participant'] != null
          ? CallParticipant.fromJson(json['other_participant'])
          : null,
    );
  }
}
```

## Call State Management

```dart
// lib/models/call_event.dart
class CallEvent {
  final String type; // 'call' or 'group_call'
  final String op; // 'initiated', 'incoming_call', 'accepted', etc.
  final String callId;
  final String callType; // 'audio' or 'video'
  final CallParticipant sender;
  final CallParticipant? receiver;
  final CallParticipant? host;
  final List<GroupCallParticipant>? participants;
  final String? jitsiUrl;
  final String state;
  final String timestamp;
  final String? title;
  final int? streamId;
  final String? topic;

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
    this.title,
    this.streamId,
    this.topic,
  });

  factory CallEvent.fromJson(Map<String, dynamic> json) {
    return CallEvent(
      type: json['type'] ?? json['event_type'],
      op: json['op'] ?? json['operation'],
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
      jitsiUrl: json['jitsi_url'] ?? json['call_url'],
      state: json['state'],
      timestamp: json['timestamp'] ?? json['created_at'],
      title: json['title'],
      streamId: json['stream_id'],
      topic: json['topic'],
    );
  }

  bool get isGroupCall => type == 'group_call';
}

class GroupCallParticipant {
  final int userId;
  final String fullName;
  final String state; // 'invited', 'joined', 'left', 'declined'
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
      isHost: json['is_host'] ?? false,
    );
  }
}
```

```dart
// lib/providers/call_state_manager.dart
import 'package:flutter/foundation.dart';

enum CallStatus {
  idle,
  outgoing,
  incoming,
  ringing,
  active,
}

class Call {
  final String callId;
  final String callType;
  final CallParticipant sender;
  final CallParticipant? receiver;
  final String? jitsiUrl;
  final String state;

  Call({
    required this.callId,
    required this.callType,
    required this.sender,
    this.receiver,
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
      jitsiUrl: jitsiUrl ?? this.jitsiUrl,
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

  /// Handle call event
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
        _activeCall = Call(
          callId: event.callId,
          callType: event.callType,
          sender: event.sender,
          receiver: event.receiver,
          jitsiUrl: event.jitsiUrl,
          state: 'calling',
        );
        _status = CallStatus.outgoing;
        break;

      case 'incoming_call':
        _activeCall = Call(
          callId: event.callId,
          callType: event.callType,
          sender: event.sender,
          receiver: event.receiver,
          jitsiUrl: event.jitsiUrl,
          state: 'incoming',
        );
        _status = CallStatus.incoming;
        break;

      case 'ringing':
        if (_activeCall?.callId == event.callId) {
          _activeCall = _activeCall!.copyWith(state: 'ringing');
          _status = CallStatus.ringing;
        }
        break;

      case 'accepted':
        if (_activeCall?.callId == event.callId) {
          _activeCall = _activeCall!.copyWith(
            state: 'accepted',
            jitsiUrl: event.jitsiUrl,
          );
          _status = CallStatus.active;
        }
        break;

      case 'declined':
      case 'ended':
      case 'cancelled':
        if (_activeCall?.callId == event.callId) {
          _activeCall = null;
          _status = CallStatus.idle;
        }
        break;

      case 'missed':
        _missedCalls.add(event);
        _activeCall = null;
        _status = CallStatus.idle;
        break;
    }
  }

  void _handleGroupCallEvent(CallEvent event) {
    switch (event.op) {
      case 'created':
        _activeGroupCall = GroupCall(
          callId: event.callId,
          callType: event.callType,
          host: event.host!,
          participants: event.participants ?? [],
          jitsiUrl: event.jitsiUrl!,
          title: event.title,
        );
        _status = CallStatus.active;
        break;

      case 'participant_invited':
        if (_activeGroupCall?.callId == event.callId) {
          _status = CallStatus.incoming;
        }
        break;

      case 'participant_joined':
      case 'participant_left':
      case 'participant_declined':
        if (_activeGroupCall?.callId == event.callId) {
          _activeGroupCall = _activeGroupCall!.copyWith(
            participants: event.participants ?? [],
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

  void clearMissedCalls() {
    _missedCalls.clear();
    notifyListeners();
  }

  void reset() {
    _activeCall = null;
    _activeGroupCall = null;
    _status = CallStatus.idle;
    notifyListeners();
  }
}
```

## UI Components

### Incoming Call Screen

```dart
// lib/screens/incoming_call_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:call_state_manager.dart';
import 'package:call_api_service.dart';

class IncomingCallScreen extends StatelessWidget {
  final String callId;
  final String callerName;
  final String callType;

  const IncomingCallScreen({
    Key? key,
    required this.callId,
    required this.callerName,
    required this.callType,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    final callApi = Provider.of<CallApiService>(context);

    return Scaffold(
      backgroundColor: Colors.black87,
      body: SafeArea(
        child: Column(
          children: [
            const Spacer(),
            // Avatar
            CircleAvatar(
              radius: 60,
              backgroundColor: Colors.grey[800],
              child: Text(
                callerName[0].toUpperCase(),
                style: const TextStyle(fontSize: 48, color: Colors.white),
              ),
            ),
            const SizedBox(height: 24),
            // Name
            Text(
              callerName,
              style: const TextStyle(
                fontSize: 28,
                color: Colors.white,
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            // Call type
            Text(
              callType == 'video' ? 'Video Call' : 'Audio Call',
              style: TextStyle(fontSize: 16, color: Colors.grey[400]),
            ),
            const Spacer(),
            // Action buttons
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceEvenly,
              children: [
                // Decline
                FloatingActionButton(
                  onPressed: () async {
                    await callApi.respondToCall(callId: callId, accept: false);
                    Navigator.pop(context);
                  },
                  backgroundColor: Colors.red,
                  child: const Icon(Icons.call_end),
                ),
                // Accept
                FloatingActionButton(
                  onPressed: () async {
                    await callApi.respondToCall(callId: callId, accept: true);
                    // Navigate to active call screen
                    Navigator.pushReplacementNamed(
                      context,
                      '/active-call',
                      arguments: {'callId': callId},
                    );
                  },
                  backgroundColor: Colors.green,
                  child: const Icon(Icons.call),
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
```

### Active Call Screen with Jitsi

```dart
// lib/screens/active_call_screen.dart
import 'package:flutter/material.dart';
import 'package:jitsi_meet_flutter_sdk/jitsi_meet_flutter_sdk.dart';
import 'package:provider/provider.dart';
import 'package:call_api_service.dart';
import 'package:call_state_manager.dart';

class ActiveCallScreen extends StatefulWidget {
  final String callId;
  final String jitsiUrl;

  const ActiveCallScreen({
    Key? key,
    required this.callId,
    required this.jitsiUrl,
  }) : super(key: key);

  @override
  State<ActiveCallScreen> createState() => _ActiveCallScreenState();
}

class _ActiveCallScreenState extends State<ActiveCallScreen> {
  JitsiMeetController? _jitsiController;
  Timer? _heartbeatTimer;

  @override
  void initState() {
    super.initState();
    _startJitsiCall();
    _startHeartbeat();
  }

  void _startJitsiCall() {
    final jitsiMeet = JitsiMeet();
    final options = JitsiMeetConferenceOptions(
      roomUrlOrName: widget.jitsiUrl,
      serverUrl: 'https://meet.jit.si',
      config: JitsiMeetConferenceConfig(
        startWithAudioMuted: false,
        startWithVideoMuted: false,
      ),
    );

    _jitsiController = jitsiMeet.join(
      options: options,
      listener: JitsiMeetEventListener(
        onConferenceJoined: () {
          print('Joined conference');
        },
        onConferenceTerminated: (message) {
          print('Conference terminated: $message');
          _endCall();
        },
        onError: (error) {
          print('Error: $error');
        },
      ),
    );
  }

  void _startHeartbeat() {
    final callApi = Provider.of<CallApiService>(context, listen: false);
    _heartbeatTimer = Timer.periodic(const Duration(seconds: 30), (_) {
      callApi.sendHeartbeat(widget.callId);
    });
  }

  Future<void> _endCall() async {
    _heartbeatTimer?.cancel();
    final callApi = Provider.of<CallApiService>(context, listen: false);
    await callApi.endCall(widget.callId);
    _jitsiController?.hangUp();
    if (mounted) {
      Navigator.pop(context);
    }
  }

  @override
  void dispose() {
    _heartbeatTimer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Stack(
        children: [
          // Jitsi view will be shown here
          Center(
            child: Text(
              'Call Active: ${widget.callId}',
              style: const TextStyle(color: Colors.white),
            ),
          ),
          // End call button
          Positioned(
            bottom: 32,
            left: 0,
            right: 0,
            child: Center(
              child: FloatingActionButton(
                onPressed: _endCall,
                backgroundColor: Colors.red,
                child: const Icon(Icons.call_end),
              ),
            ),
          ),
        ],
      ),
    );
  }
}
```

## Group Calls

### Creating a Group Call

```dart
Future<void> createGroupCall({
  required BuildContext context,
  required String title,
  required List<int> participantIds,
  required bool isVideo,
}) async {
  final callApi = Provider.of<CallApiService>(context, listen: false);

  try {
    final response = await callApi.createGroupCall(
      callType: isVideo ? 'video' : 'audio',
      title: title,
      userIds: participantIds,
    );

    // Navigate to group call screen
    Navigator.pushNamed(
      context,
      '/group-call',
      arguments: {
        'callId': response.callId,
        'jitsiUrl': response.callUrl,
        'title': response.title ?? title,
      },
    );
  } catch (e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Failed to create group call: $e')),
    );
  }
}
```

### Joining a Group Call

```dart
Future<void> joinGroupCall({
  required BuildContext context,
  required String callId,
}) async {
  final callApi = Provider.of<CallApiService>(context, listen: false);

  try {
    final response = await callApi.joinGroupCall(callId);

    Navigator.pushNamed(
      context,
      '/active-call',
      arguments: {
        'callId': callId,
        'jitsiUrl': response.callUrl,
      },
    );
  } catch (e) {
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Failed to join group call: $e')),
    );
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
      criticalAlert: true,
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
      // Show incoming call UI
      _showIncomingCallNotification(data);
    } else if (data['event'] == 'missed_call') {
      _showMissedCallNotification(data);
    }
  }

  @pragma('vm:entry-point')
  static Future<void> _handleBackgroundMessage(RemoteMessage message) async {
    final data = message.data;

    if (data['event'] == 'call') {
      await _showCallKitIncoming(data);
    }
  }

  static Future<void> _showCallKitIncoming(Map<String, dynamic> data) async {
    await FlutterCallkitIncoming.showCallkitIncoming(
      CallKitParams(
        id: data['call_id'],
        nameCaller: data['sender_name'] ?? data['sender_full_name'],
        appName: 'Zulip',
        handle: data['sender_email'],
        type: data['call_type'] == 'video' ? 1 : 0,
        duration: 90000,
        textAccept: 'Accept',
        textDecline: 'Decline',
        extra: data,
        headers: {},
        android: const AndroidParams(
          isCustomNotification: true,
          ringtonePath: 'system_ringtone_default',
          backgroundColor: '#0a0a0a',
          actionColor: '#4CAF50',
        ),
        ios: IOSParams(
          handleType: 'generic',
          supportsVideo: data['call_type'] == 'video',
        ),
      ),
    );
  }

  static Future<void> _handleCallKitAction(CallKitEvent event) async {
    final callId = event.body['id'];

    switch (event.event) {
      case Event.actionCallAccept:
        // Accept call via API
        break;
      case Event.actionCallDecline:
        // Decline call via API
        break;
      case Event.actionCallEnd:
        // End call via API
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
        ),
        iOS: DarwinNotificationDetails(),
      ),
    );
  }

  static void _showIncomingCallNotification(Map<String, dynamic> data) {
    // Navigate to incoming call screen
    // Implementation depends on your navigation setup
  }
}
```

## Offline Handling

```dart
// Handle offline receiver
final response = await callApi.initiateCall(
  recipientEmail: 'user@example.com',
  callType: 'video',
);

if (!response.receiverOnline) {
  showDialog(
    context: context,
    builder: (context) => AlertDialog(
      title: const Text('User Offline'),
      content: Text(
        '${response.recipient.fullName} appears to be offline. '
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
}
```

## Permissions

```dart
// lib/services/permission_service.dart
import 'package:permission_handler/permission_handler.dart';

class PermissionService {
  /// Request camera and microphone permissions
  static Future<bool> requestCallPermissions() async {
    final cameraStatus = await Permission.camera.request();
    final microphoneStatus = await Permission.microphone.request();

    return cameraStatus.isGranted && microphoneStatus.isGranted;
  }

  /// Check if permissions are granted
  static Future<bool> hasCallPermissions() async {
    final cameraStatus = await Permission.camera.status;
    final microphoneStatus = await Permission.microphone.status;

    return cameraStatus.isGranted && microphoneStatus.isGranted;
  }

  /// Open app settings if permissions denied
  static Future<void> openSettings() async {
    await openAppSettings();
  }
}
```

## Testing

### Unit Tests

```dart
// test/call_state_manager_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:call_state_manager.dart';

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
        sender: CallParticipant(
          userId: 1,
          fullName: 'Alice',
          email: 'alice@example.com',
        ),
        receiver: CallParticipant(
          userId: 2,
          fullName: 'Bob',
          email: 'bob@example.com',
        ),
        state: 'incoming',
        timestamp: DateTime.now().toIso8601String(),
      );

      manager.handleCallEvent(event);

      expect(manager.status, CallStatus.incoming);
      expect(manager.activeCall?.callId, 'test-123');
    });
  });
}
```

## Troubleshooting

### Common Issues

1. **Events not received**
   - Check event registration includes `'call'` and `'group_call'` types
   - Verify queue_id is valid (for polling)
   - Check WebSocket connection status
   - Review backend logs

2. **Push notifications not working**
   - Verify Firebase configuration
   - Check FCM token registration
   - Test with Firebase Console
   - Review notification permissions

3. **CallKit not showing (iOS)**
   - Check Info.plist includes required permissions
   - Verify `flutter_callkit_incoming` setup
   - Test on real device (not simulator)

4. **Jitsi not loading**
   - Verify Jitsi URL format
   - Check Jitsi server configuration
   - Review CORS settings
   - Test URL in browser first

5. **Calls immediately ending**
   - Verify heartbeat is being sent every 30s
   - Check network stability
   - Review backend cleanup worker logs

### Debug Logging

```dart
void main() {
  // Enable debug logging
  debugPrint = (String? message, {int? wrapWidth}) {
    print('[${DateTime.now()}] $message');
  };

  runApp(MyApp());
}
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
10. **Follow platform guidelines** for call UI (Material Design / HIG)

## Additional Resources

- [Zulip API Documentation](https://zulip.com/api/)
- [Jitsi Meet Flutter SDK](https://pub.dev/packages/jitsi_meet_flutter_sdk)
- [Flutter CallKit Incoming](https://pub.dev/packages/flutter_callkit_incoming)
- [Firebase Cloud Messaging](https://firebase.google.com/docs/cloud-messaging/flutter/client)

---

**Last Updated**: January 28, 2026  
**Plugin Version**: 2.0  
**Zulip Version**: Latest
