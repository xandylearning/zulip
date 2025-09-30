# Flutter Integration Guide for Zulip Calls Plugin

## Overview
Complete integration guide for implementing the Zulip Calls Plugin with WebSocket support in a Flutter mobile application. This guide covers the entire call flow from initiation to termination with real-time events.

## Table of Contents
1. [Setup & Dependencies](#setup--dependencies)
2. [Authentication Setup](#authentication-setup)
3. [WebSocket Integration](#websocket-integration)
4. [API Service Implementation](#api-service-implementation)
5. [Call State Management](#call-state-management)
6. [UI Components](#ui-components)
7. [Permission Handling](#permission-handling)
8. [Complete Example](#complete-example)

## Setup & Dependencies

### pubspec.yaml
```yaml
dependencies:
  flutter:
    sdk: flutter
  http: ^1.1.0
  web_socket_channel: ^2.4.0
  permission_handler: ^11.0.1
  jitsi_meet_flutter_sdk: ^10.0.0
  provider: ^6.1.1
  shared_preferences: ^2.2.2
  flutter_local_notifications: ^16.3.0

dev_dependencies:
  flutter_test:
    sdk: flutter
```

## Authentication Setup

### ZulipAuth Service
```dart
// lib/services/zulip_auth.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class ZulipAuth {
  static const String _baseUrl = 'https://your-zulip-domain.com';
  static const String _apiKeyPref = 'zulip_api_key';
  static const String _userIdPref = 'zulip_user_id';
  static const String _emailPref = 'zulip_email';

  static String? _apiKey;
  static int? _userId;
  static String? _email;

  // Initialize auth from stored credentials
  static Future<bool> initialize() async {
    final prefs = await SharedPreferences.getInstance();
    _apiKey = prefs.getString(_apiKeyPref);
    _userId = prefs.getInt(_userIdPref);
    _email = prefs.getString(_emailPref);
    return isAuthenticated;
  }

  static bool get isAuthenticated =>
      _apiKey != null && _userId != null && _email != null;

  // Login with email and API key
  static Future<bool> login(String email, String apiKey) async {
    try {
      final response = await http.get(
        Uri.parse('$_baseUrl/api/v1/users/me'),
        headers: _getAuthHeaders(email, apiKey),
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        _apiKey = apiKey;
        _userId = data['user_id'];
        _email = email;

        // Store credentials
        final prefs = await SharedPreferences.getInstance();
        await prefs.setString(_apiKeyPref, apiKey);
        await prefs.setInt(_userIdPref, _userId!);
        await prefs.setString(_emailPref, email);

        return true;
      }
    } catch (e) {
      print('Login error: $e');
    }
    return false;
  }

  // Get auth headers for API requests
  static Map<String, String> get authHeaders => _getAuthHeaders(_email!, _apiKey!);

  static Map<String, String> _getAuthHeaders(String email, String apiKey) {
    final credentials = base64Encode(utf8.encode('$email:$apiKey'));
    return {
      'Authorization': 'Basic $credentials',
      'Content-Type': 'application/json',
    };
  }

  static String get baseUrl => _baseUrl;
  static int? get userId => _userId;
  static String? get email => _email;
}
```

## WebSocket Integration

### WebSocket Service
```dart
// lib/services/websocket_service.dart
import 'dart:convert';
import 'dart:async';
import 'package:web_socket_channel/web_socket_channel.dart';
import 'package:web_socket_channel/status.dart' as status;
import 'zulip_auth.dart';

class WebSocketService {
  WebSocketChannel? _channel;
  StreamController<Map<String, dynamic>>? _eventController;
  Timer? _heartbeatTimer;
  bool _isConnected = false;

  Stream<Map<String, dynamic>> get eventStream =>
      _eventController?.stream ?? const Stream.empty();

  bool get isConnected => _isConnected;

  Future<void> connect() async {
    try {
      await disconnect(); // Clean up existing connection

      // Register for events first
      final queueResponse = await _registerEventQueue();
      if (queueResponse == null) return;

      final queueId = queueResponse['queue_id'];
      final lastEventId = queueResponse['last_event_id'];

      // Connect WebSocket
      final wsUrl = '${ZulipAuth.baseUrl.replaceFirst('https://', 'wss://')}/api/v1/events'
          '?queue_id=$queueId&last_event_id=$lastEventId';

      _channel = WebSocketChannel.connect(Uri.parse(wsUrl));
      _eventController = StreamController<Map<String, dynamic>>.broadcast();

      // Listen to WebSocket messages
      _channel!.stream.listen(
        (data) {
          try {
            final eventData = json.decode(data);
            _handleEvent(eventData);
          } catch (e) {
            print('WebSocket message parse error: $e');
          }
        },
        onError: (error) {
          print('WebSocket error: $error');
          _isConnected = false;
          _reconnect();
        },
        onDone: () {
          print('WebSocket connection closed');
          _isConnected = false;
          _reconnect();
        },
      );

      _isConnected = true;
      _startHeartbeat();
      print('WebSocket connected successfully');

    } catch (e) {
      print('WebSocket connection error: $e');
      _reconnect();
    }
  }

  Future<Map<String, dynamic>?> _registerEventQueue() async {
    try {
      final response = await http.post(
        Uri.parse('${ZulipAuth.baseUrl}/api/v1/register'),
        headers: ZulipAuth.authHeaders,
        body: json.encode({
          'event_types': ['call_event'], // Register for call events
          'client_capabilities': {
            'notification_settings_null': false,
            'bulk_message_deletion': true,
            'user_avatar_url_field_optional': true,
          }
        }),
      );

      if (response.statusCode == 200) {
        return json.decode(response.body);
      }
    } catch (e) {
      print('Event queue registration error: $e');
    }
    return null;
  }

  void _handleEvent(Map<String, dynamic> eventData) {
    final eventType = eventData['type'];

    if (eventType == 'call_event') {
      // Handle call-specific events
      _eventController?.add(eventData);
      print('Call event received: ${eventData['event_type']}');
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(Duration(seconds: 30), (timer) {
      if (_isConnected && _channel != null) {
        _channel!.sink.add(json.encode({'type': 'heartbeat'}));
      }
    });
  }

  void _reconnect() {
    Timer(Duration(seconds: 5), () {
      if (!_isConnected) {
        print('Attempting WebSocket reconnection...');
        connect();
      }
    });
  }

  Future<void> disconnect() async {
    _heartbeatTimer?.cancel();
    _isConnected = false;
    await _channel?.sink.close(status.goingAway);
    await _eventController?.close();
    _channel = null;
    _eventController = null;
  }
}
```

## API Service Implementation

### Calls API Service
```dart
// lib/services/calls_api_service.dart
import 'dart:convert';
import 'package:http/http.dart' as http;
import 'zulip_auth.dart';

class CallsApiService {
  static Future<ApiResponse<CallData>> initiateCall({
    required String recipientEmail,
    required bool isVideoCall,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ZulipAuth.baseUrl}/api/v1/calls/initiate'),
        headers: ZulipAuth.authHeaders,
        body: json.encode({
          'recipient_email': recipientEmail,
          'is_video_call': isVideoCall.toString(),
        }),
      );

      final data = json.decode(response.body);

      if (response.statusCode == 200 && data['result'] == 'success') {
        return ApiResponse.success(CallData.fromJson(data));
      } else {
        return ApiResponse.error(data['message'] ?? 'Failed to initiate call');
      }
    } catch (e) {
      return ApiResponse.error('Network error: $e');
    }
  }

  static Future<ApiResponse<void>> acknowledgeCall({
    required String callId,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ZulipAuth.baseUrl}/api/v1/calls/acknowledge'),
        headers: ZulipAuth.authHeaders,
        body: json.encode({
          'call_id': callId,
          'status': 'ringing',
        }),
      );

      final data = json.decode(response.body);

      if (response.statusCode == 200 && data['result'] == 'success') {
        return ApiResponse.success(null);
      } else {
        return ApiResponse.error(data['message'] ?? 'Failed to acknowledge call');
      }
    } catch (e) {
      return ApiResponse.error('Network error: $e');
    }
  }

  static Future<ApiResponse<void>> respondToCall({
    required String callId,
    required CallResponse response,
  }) async {
    try {
      final httpResponse = await http.post(
        Uri.parse('${ZulipAuth.baseUrl}/api/v1/calls/respond'),
        headers: ZulipAuth.authHeaders,
        body: json.encode({
          'call_id': callId,
          'response': response.value,
        }),
      );

      final data = json.decode(httpResponse.body);

      if (httpResponse.statusCode == 200 && data['result'] == 'success') {
        return ApiResponse.success(null);
      } else {
        return ApiResponse.error(data['message'] ?? 'Failed to respond to call');
      }
    } catch (e) {
      return ApiResponse.error('Network error: $e');
    }
  }

  static Future<ApiResponse<void>> updateCallStatus({
    required String callId,
    required CallStatus status,
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ZulipAuth.baseUrl}/api/v1/calls/status'),
        headers: ZulipAuth.authHeaders,
        body: json.encode({
          'call_id': callId,
          'status': status.value,
        }),
      );

      final data = json.decode(response.body);

      if (response.statusCode == 200 && data['result'] == 'success') {
        return ApiResponse.success(null);
      } else {
        return ApiResponse.error(data['message'] ?? 'Failed to update call status');
      }
    } catch (e) {
      return ApiResponse.error('Network error: $e');
    }
  }

  static Future<ApiResponse<void>> endCall({
    required String callId,
    String reason = 'user_hangup',
  }) async {
    try {
      final response = await http.post(
        Uri.parse('${ZulipAuth.baseUrl}/api/v1/calls/end'),
        headers: ZulipAuth.authHeaders,
        body: json.encode({
          'call_id': callId,
          'reason': reason,
        }),
      );

      final data = json.decode(response.body);

      if (response.statusCode == 200 && data['result'] == 'success') {
        return ApiResponse.success(null);
      } else {
        return ApiResponse.error(data['message'] ?? 'Failed to end call');
      }
    } catch (e) {
      return ApiResponse.error('Network error: $e');
    }
  }
}

// Helper classes
class ApiResponse<T> {
  final bool isSuccess;
  final T? data;
  final String? error;

  ApiResponse.success(this.data) : isSuccess = true, error = null;
  ApiResponse.error(this.error) : isSuccess = false, data = null;
}

class CallData {
  final String callId;
  final String callUrl;
  final String callType;
  final String roomId;

  CallData({
    required this.callId,
    required this.callUrl,
    required this.callType,
    required this.roomId,
  });

  factory CallData.fromJson(Map<String, dynamic> json) {
    return CallData(
      callId: json['call_id'] ?? '',
      callUrl: json['call_url'] ?? '',
      callType: json['call_type'] ?? 'audio',
      roomId: json['room_id'] ?? '',
    );
  }
}

enum CallResponse {
  accept('accept'),
  reject('reject');

  const CallResponse(this.value);
  final String value;
}

enum CallStatus {
  connected('connected'),
  onHold('on_hold'),
  muted('muted'),
  videoDisabled('video_disabled'),
  screenSharing('screen_sharing');

  const CallStatus(this.value);
  final String value;
}
```

## Call State Management

### Call State Provider
```dart
// lib/providers/call_provider.dart
import 'package:flutter/foundation.dart';
import '../services/calls_api_service.dart';
import '../services/websocket_service.dart';

class CallProvider extends ChangeNotifier {
  final WebSocketService _webSocketService = WebSocketService();
  final CallsApiService _apiService = CallsApiService();

  CallState _currentCallState = CallState.idle;
  CallData? _currentCall;
  String? _currentCallId;
  bool _isIncomingCall = false;
  String? _callerName;
  String? _receiverName;

  // Getters
  CallState get currentCallState => _currentCallState;
  CallData? get currentCall => _currentCall;
  String? get currentCallId => _currentCallId;
  bool get isIncomingCall => _isIncomingCall;
  String? get callerName => _callerName;
  String? get receiverName => _receiverName;

  CallProvider() {
    _initializeWebSocket();
  }

  void _initializeWebSocket() {
    _webSocketService.eventStream.listen((event) {
      _handleWebSocketEvent(event);
    });
    _webSocketService.connect();
  }

  void _handleWebSocketEvent(Map<String, dynamic> event) {
    final eventType = event['event_type'];
    final callId = event['call_id'];

    switch (eventType) {
      case 'participant_ringing':
        _handleParticipantRinging(event);
        break;
      case 'call_accepted':
        _handleCallAccepted(event);
        break;
      case 'call_rejected':
        _handleCallRejected(event);
        break;
      case 'call_ended':
        _handleCallEnded(event);
        break;
      case 'call_status_update':
        _handleCallStatusUpdate(event);
        break;
    }
  }

  void _handleParticipantRinging(Map<String, dynamic> event) {
    if (_currentCallId == event['call_id']) {
      _currentCallState = CallState.ringing;
      notifyListeners();
    }
  }

  void _handleCallAccepted(Map<String, dynamic> event) {
    if (_currentCallId == event['call_id']) {
      _currentCallState = CallState.connected;
      notifyListeners();
    }
  }

  void _handleCallRejected(Map<String, dynamic> event) {
    if (_currentCallId == event['call_id']) {
      _currentCallState = CallState.rejected;
      _resetCallState();
      notifyListeners();
    }
  }

  void _handleCallEnded(Map<String, dynamic> event) {
    if (_currentCallId == event['call_id']) {
      _currentCallState = CallState.ended;
      _resetCallState();
      notifyListeners();
    }
  }

  void _handleCallStatusUpdate(Map<String, dynamic> event) {
    // Handle status updates (muted, video disabled, etc.)
    notifyListeners();
  }

  // Public methods
  Future<bool> initiateCall({
    required String recipientEmail,
    required bool isVideoCall,
  }) async {
    try {
      _currentCallState = CallState.calling;
      notifyListeners();

      final response = await CallsApiService.initiateCall(
        recipientEmail: recipientEmail,
        isVideoCall: isVideoCall,
      );

      if (response.isSuccess && response.data != null) {
        _currentCall = response.data;
        _currentCallId = response.data!.callId;
        _currentCallState = CallState.calling;
        notifyListeners();
        return true;
      } else {
        _currentCallState = CallState.error;
        notifyListeners();
        return false;
      }
    } catch (e) {
      _currentCallState = CallState.error;
      notifyListeners();
      return false;
    }
  }

  Future<bool> acknowledgeCall(String callId) async {
    final response = await CallsApiService.acknowledgeCall(callId: callId);
    return response.isSuccess;
  }

  Future<bool> acceptCall() async {
    if (_currentCallId == null) return false;

    final response = await CallsApiService.respondToCall(
      callId: _currentCallId!,
      response: CallResponse.accept,
    );

    if (response.isSuccess) {
      _currentCallState = CallState.connected;
      _isIncomingCall = false;
      notifyListeners();
      return true;
    }
    return false;
  }

  Future<bool> rejectCall() async {
    if (_currentCallId == null) return false;

    final response = await CallsApiService.respondToCall(
      callId: _currentCallId!,
      response: CallResponse.reject,
    );

    if (response.isSuccess) {
      _resetCallState();
      notifyListeners();
      return true;
    }
    return false;
  }

  Future<bool> endCall() async {
    if (_currentCallId == null) return false;

    final response = await CallsApiService.endCall(callId: _currentCallId!);

    if (response.isSuccess) {
      _resetCallState();
      notifyListeners();
      return true;
    }
    return false;
  }

  Future<bool> updateCallStatus(CallStatus status) async {
    if (_currentCallId == null) return false;

    final response = await CallsApiService.updateCallStatus(
      callId: _currentCallId!,
      status: status,
    );

    return response.isSuccess;
  }

  void _resetCallState() {
    _currentCallState = CallState.idle;
    _currentCall = null;
    _currentCallId = null;
    _isIncomingCall = false;
    _callerName = null;
    _receiverName = null;
  }

  @override
  void dispose() {
    _webSocketService.disconnect();
    super.dispose();
  }
}

enum CallState {
  idle,
  calling,
  ringing,
  connected,
  ended,
  rejected,
  error,
}
```

## UI Components

### Incoming Call Screen
```dart
// lib/screens/incoming_call_screen.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../providers/call_provider.dart';

class IncomingCallScreen extends StatefulWidget {
  final String callId;
  final String callerName;
  final bool isVideoCall;

  const IncomingCallScreen({
    Key? key,
    required this.callId,
    required this.callerName,
    required this.isVideoCall,
  }) : super(key: key);

  @override
  _IncomingCallScreenState createState() => _IncomingCallScreenState();
}

class _IncomingCallScreenState extends State<IncomingCallScreen> {
  @override
  void initState() {
    super.initState();
    // Acknowledge call receipt
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CallProvider>().acknowledgeCall(widget.callId);
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black87,
      body: Consumer<CallProvider>(
        builder: (context, callProvider, child) {
          return SafeArea(
            child: Column(
              children: [
                Expanded(
                  flex: 2,
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        CircleAvatar(
                          radius: 80,
                          backgroundImage: NetworkImage(
                            'https://your-zulip-domain.com/avatar/${widget.callerName}',
                          ),
                        ),
                        SizedBox(height: 24),
                        Text(
                          widget.callerName,
                          style: TextStyle(
                            color: Colors.white,
                            fontSize: 28,
                            fontWeight: FontWeight.bold,
                          ),
                        ),
                        SizedBox(height: 8),
                        Text(
                          'Incoming ${widget.isVideoCall ? 'video' : 'audio'} call',
                          style: TextStyle(
                            color: Colors.white70,
                            fontSize: 18,
                          ),
                        ),
                        if (callProvider.currentCallState == CallState.ringing)
                          Padding(
                            padding: const EdgeInsets.only(top: 16),
                            child: Text(
                              'Ringing...',
                              style: TextStyle(
                                color: Colors.white70,
                                fontSize: 16,
                              ),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
                Expanded(
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                    children: [
                      // Reject button
                      FloatingActionButton(
                        onPressed: () async {
                          await callProvider.rejectCall();
                          Navigator.of(context).pop();
                        },
                        backgroundColor: Colors.red,
                        child: Icon(Icons.call_end, color: Colors.white),
                      ),
                      // Accept button
                      FloatingActionButton(
                        onPressed: () async {
                          final success = await callProvider.acceptCall();
                          if (success && callProvider.currentCall != null) {
                            Navigator.of(context).pushReplacement(
                              MaterialPageRoute(
                                builder: (_) => JitsiCallScreen(
                                  callData: callProvider.currentCall!,
                                ),
                              ),
                            );
                          }
                        },
                        backgroundColor: Colors.green,
                        child: Icon(Icons.call, color: Colors.white),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
```

### Jitsi Call Screen
```dart
// lib/screens/jitsi_call_screen.dart
import 'package:flutter/material.dart';
import 'package:jitsi_meet_flutter_sdk/jitsi_meet_flutter_sdk.dart';
import 'package:provider/provider.dart';
import '../providers/call_provider.dart';
import '../services/calls_api_service.dart';

class JitsiCallScreen extends StatefulWidget {
  final CallData callData;

  const JitsiCallScreen({
    Key? key,
    required this.callData,
  }) : super(key: key);

  @override
  _JitsiCallScreenState createState() => _JitsiCallScreenState();
}

class _JitsiCallScreenState extends State<JitsiCallScreen> {
  late JitsiMeet _jitsiMeet;
  bool _isCallActive = false;

  @override
  void initState() {
    super.initState();
    _initializeJitsi();
  }

  void _initializeJitsi() async {
    _jitsiMeet = JitsiMeet();

    // Configure Jitsi options
    final options = JitsiMeetConferenceOptions(
      room: widget.callData.roomId,
      configOverrides: {
        'startWithAudioMuted': false,
        'startWithVideoMuted': widget.callData.callType == 'audio',
        'enableWelcomePage': false,
        'enableClosePage': false,
        'prejoinPageEnabled': false,
      },
      featureFlags: {
        'unsaferoomwarning.enabled': false,
        'resolution': 720,
      },
      userInfo: JitsiMeetUserInfo(
        displayName: 'User', // Get from auth
        email: 'user@example.com', // Get from auth
      ),
    );

    // Set up event listeners
    _jitsiMeet.eventListeners.add(JitsiMeetEventListener(
      conferenceJoined: (url) {
        _handleConferenceJoined();
      },
      conferenceTerminated: (url, error) {
        _handleConferenceEnded();
      },
      conferenceWillJoin: (url) {
        setState(() {
          _isCallActive = true;
        });
      },
      participantJoined: (email, name, role, participantId) {
        _updateCallStatus(CallStatus.connected);
      },
      audioMutedChanged: (muted) {
        if (muted) {
          _updateCallStatus(CallStatus.muted);
        }
      },
      videoMutedChanged: (muted) {
        if (muted) {
          _updateCallStatus(CallStatus.videoDisabled);
        }
      },
    ));

    // Join the conference
    await _jitsiMeet.join(options);
  }

  void _handleConferenceJoined() {
    _updateCallStatus(CallStatus.connected);
  }

  void _handleConferenceEnded() {
    final callProvider = context.read<CallProvider>();
    callProvider.endCall();
    Navigator.of(context).popUntil((route) => route.isFirst);
  }

  void _updateCallStatus(CallStatus status) {
    final callProvider = context.read<CallProvider>();
    callProvider.updateCallStatus(status);
  }

  @override
  Widget build(BuildContext context) {
    return WillPopScope(
      onWillPop: () async {
        await _jitsiMeet.hangUp();
        return true;
      },
      child: Scaffold(
        body: Consumer<CallProvider>(
          builder: (context, callProvider, child) {
            if (callProvider.currentCallState == CallState.ended) {
              WidgetsBinding.instance.addPostFrameCallback((_) {
                Navigator.of(context).popUntil((route) => route.isFirst);
              });
            }

            return Container(
              child: _isCallActive
                  ? Container() // Jitsi will handle the UI
                  : Center(
                      child: CircularProgressIndicator(),
                    ),
            );
          },
        ),
        floatingActionButton: _isCallActive
            ? FloatingActionButton(
                onPressed: () async {
                  await _jitsiMeet.hangUp();
                },
                backgroundColor: Colors.red,
                child: Icon(Icons.call_end),
              )
            : null,
      ),
    );
  }

  @override
  void dispose() {
    _jitsiMeet.hangUp();
    super.dispose();
  }
}
```

## Permission Handling

### Permissions Service
```dart
// lib/services/permissions_service.dart
import 'package:permission_handler/permission_handler.dart';

class PermissionsService {
  static Future<bool> requestCallPermissions() async {
    Map<Permission, PermissionStatus> permissions = await [
      Permission.camera,
      Permission.microphone,
      Permission.notification,
    ].request();

    bool allGranted = permissions.values
        .every((status) => status == PermissionStatus.granted);

    return allGranted;
  }

  static Future<bool> checkCallPermissions() async {
    final camera = await Permission.camera.status;
    final microphone = await Permission.microphone.status;
    final notification = await Permission.notification.status;

    return camera == PermissionStatus.granted &&
           microphone == PermissionStatus.granted &&
           notification == PermissionStatus.granted;
  }
}
```

## Complete Example

### Main App Integration
```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'providers/call_provider.dart';
import 'services/zulip_auth.dart';
import 'services/permissions_service.dart';
import 'screens/login_screen.dart';
import 'screens/home_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // Initialize auth
  await ZulipAuth.initialize();

  // Request permissions
  await PermissionsService.requestCallPermissions();

  runApp(MyApp());
}

class MyApp extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => CallProvider()),
      ],
      child: MaterialApp(
        title: 'Zulip Calls',
        theme: ThemeData(
          primarySwatch: Colors.blue,
          visualDensity: VisualDensity.adaptivePlatformDensity,
        ),
        home: ZulipAuth.isAuthenticated ? HomeScreen() : LoginScreen(),
      ),
    );
  }
}
```

### Usage Example
```dart
// Making a call
final callProvider = context.read<CallProvider>();
final success = await callProvider.initiateCall(
  recipientEmail: 'user@example.com',
  isVideoCall: true,
);

if (success) {
  Navigator.push(
    context,
    MaterialPageRoute(
      builder: (_) => JitsiCallScreen(
        callData: callProvider.currentCall!,
      ),
    ),
  );
}
```

## Push Notifications Integration

For handling incoming calls when the app is in background, integrate with your FCM setup to show incoming call notifications and launch the IncomingCallScreen.

## Testing

Test the complete flow:
1. Authentication
2. WebSocket connection
3. Call initiation
4. Call acknowledgment
5. Call acceptance/rejection
6. Real-time status updates
7. Call termination

This guide provides a complete implementation for integrating the Zulip Calls Plugin with your Flutter app, including WebSocket support for real-time events and proper state management.