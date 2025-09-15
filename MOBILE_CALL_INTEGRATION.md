# 📱 Zulip Mobile Call Integration Guide

## 📋 Overview

This document provides complete integration instructions for implementing the Zulip Calls Plugin with mobile applications (Flutter/React Native). The backend is already implemented with full moderator support and call management features.

## 🎯 Current Backend Status

### ✅ Backend Implementation (Complete)
- ✅ Call creation with moderator privileges
- ✅ Push notification system
- ✅ Call state management
- ✅ User availability checking
- ✅ Database models for call tracking
- ✅ Accept/decline functionality
- ✅ Call history
- ✅ Separate moderator/participant URLs
- ✅ Full API endpoints

### 🔨 Mobile Integration Required
- Mobile API calls to backend endpoints
- Jitsi Meet SDK integration
- Push notification handling
- Call UI components
- Permissions management

---

## 🛠️ Backend API Endpoints

The backend provides these endpoints for mobile integration:

### Core Call Management
| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/v1/calls/create-embedded` | POST | Create call with moderator/participant URLs | Session/API Key |
| `/api/v1/calls/create` | POST | Full call creation with database tracking | API Key |
| `/api/v1/calls/{id}/respond` | POST | Accept/decline call invitation | API Key |
| `/api/v1/calls/{id}/end` | POST | End ongoing call | API Key |
| `/api/v1/calls/{id}/status` | GET | Get current call status | API Key |
| `/api/v1/calls/history` | GET | Get user's call history | API Key |

---

## 📱 Mobile Implementation Guide

### 1. API Integration

#### Call Creation
```dart
// Flutter example
Future<Map<String, dynamic>> createCall({
  required String recipientEmail,
  required bool isVideoCall,
}) async {
  final response = await http.post(
    Uri.parse('$baseUrl/api/v1/calls/create-embedded'),
    headers: {
      'Authorization': 'Basic ${base64Encode(utf8.encode('$email:$apiKey'))}',
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: {
      'recipient_email': recipientEmail,
      'is_video_call': isVideoCall.toString(),
      'redirect_to_meeting': 'false', // Mobile handles the Jitsi integration
    },
  );

  if (response.statusCode == 200) {
    return json.decode(response.body);
  } else {
    throw Exception('Failed to create call: ${response.body}');
  }
}
```

#### Response Handling
```dart
Future<void> respondToCall({
  required String callId,
  required String response, // 'accept' or 'decline'
}) async {
  final result = await http.post(
    Uri.parse('$baseUrl/api/v1/calls/$callId/respond'),
    headers: {
      'Authorization': 'Basic ${base64Encode(utf8.encode('$email:$apiKey'))}',
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body: {'response': response},
  );

  if (result.statusCode != 200) {
    throw Exception('Failed to respond to call: ${result.body}');
  }
}
```

### 2. Jitsi Meet SDK Integration

#### Flutter Implementation
```yaml
# pubspec.yaml
dependencies:
  jitsi_meet_flutter_sdk: ^10.0.0
  permission_handler: ^11.0.1
```

```dart
import 'package:jitsi_meet_flutter_sdk/jitsi_meet_flutter_sdk.dart';

class CallService {
  final _jitsiMeet = JitsiMeet();

  Future<void> joinCall({
    required String callUrl,
    required String displayName,
    required bool isVideoCall,
    required bool isModerator,
  }) async {
    // Extract room name from URL
    final uri = Uri.parse(callUrl);
    final roomName = uri.pathSegments.last.split('?').first;

    final options = JitsiMeetConferenceOptions(
      serverURL: '${uri.scheme}://${uri.host}',
      room: roomName,
      configOverrides: {
        'startWithAudioMuted': isModerator ? false : true,
        'startWithVideoMuted': isVideoCall ? false : true,
        'enableWelcomePage': false,
        'enableClosePage': false,
        'toolbarButtons': [
          'microphone',
          'camera',
          'closedcaptions',
          'desktop',
          'embedmeeting',
          'fullscreen',
          'fodeviceselection',
          'hangup',
          'profile',
          'chat',
          'recording',
          'livestreaming',
          'etherpad',
          'sharedvideo',
          'settings',
          'raisehand',
          'videoquality',
          'filmstrip',
          'invite',
          'feedback',
          'stats',
          'shortcuts',
          'tileview',
          'videobackgroundblur',
          'download',
          'help',
          'mute-everyone',
          'mute-video-everyone',
          'security'
        ],
      },
      featureFlags: {
        'unsaferoomwarning.enabled': false,
        'prejoinpage.enabled': false,
        'welcomepage.enabled': false,
      },
      userInfo: JitsiMeetUserInfo(
        displayName: displayName,
      ),
    );

    await _jitsiMeet.join(options);
  }

  void setupEventListeners() {
    _jitsiMeet.eventListeners.add(
      JitsiMeetEventListener(
        conferenceJoined: (url) => print('Conference joined: $url'),
        conferenceTerminated: (url, error) => print('Conference terminated'),
        conferenceWillJoin: (url) => print('Conference will join: $url'),
        participantJoined: (email, name, role, participantId) {
          print('Participant joined: $name ($role)');
        },
        participantLeft: (participantId) => print('Participant left'),
        audioMutedChanged: (muted) => print('Audio muted: $muted'),
        videoMutedChanged: (muted) => print('Video muted: $muted'),
        endpointTextMessageReceived: (senderId, message) {
          print('Message received: $message');
        },
        screenShareToggled: (participantId, sharing) {
          print('Screen share toggled: $sharing');
        },
        chatMessageReceived: (senderId, message, isPrivate, timestamp) {
          print('Chat message: $message');
        },
        chatToggled: (isOpen) => print('Chat toggled: $isOpen'),
        participantsInfoRetrieved: (participantsInfo, requestId) {
          print('Participants info: $participantsInfo');
        },
        readyToClose: () {
          print('Ready to close');
          // Navigate back or handle call end
        },
      ),
    );
  }
}
```

### 3. Push Notification Handling

#### Firebase Setup
```dart
// main.dart
import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_messaging/firebase_messaging.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  await Firebase.initializeApp();

  // Set up background message handler
  FirebaseMessaging.onBackgroundMessage(_firebaseMessagingBackgroundHandler);

  runApp(MyApp());
}

@pragma('vm:entry-point')
Future<void> _firebaseMessagingBackgroundHandler(RemoteMessage message) async {
  await Firebase.initializeApp();
  print("Handling a background message: ${message.messageId}");

  if (message.data['type'] == 'call_invitation') {
    // Show incoming call notification
    await _showIncomingCallNotification(message);
  }
}
```

#### Call Notification Handler
```dart
class CallNotificationService {
  static Future<void> handleCallNotification(RemoteMessage message) async {
    final data = message.data;

    if (data['type'] == 'call_invitation') {
      await _showIncomingCallDialog(
        callId: data['call_id'],
        callerName: data['caller_name'],
        callUrl: data['call_url'],
        isVideoCall: data['is_video_call'] == 'true',
      );
    } else if (data['type'] == 'call_accepted') {
      // Handle call accepted notification
      await _handleCallAccepted(data);
    }
  }

  static Future<void> _showIncomingCallDialog({
    required String callId,
    required String callerName,
    required String callUrl,
    required bool isVideoCall,
  }) async {
    // Show system call UI or custom dialog
    await showDialog(
      context: navigatorKey.currentContext!,
      barrierDismissible: false,
      builder: (context) => IncomingCallDialog(
        callId: callId,
        callerName: callerName,
        callUrl: callUrl,
        isVideoCall: isVideoCall,
        onAccept: () async {
          Navigator.pop(context);
          await _acceptCall(callId, callUrl, callerName, false); // Participant
        },
        onDecline: () async {
          Navigator.pop(context);
          await _declineCall(callId);
        },
      ),
    );
  }

  static Future<void> _acceptCall(
    String callId,
    String callUrl,
    String displayName,
    bool isModerator,
  ) async {
    try {
      // Respond to call via API
      await CallService.respondToCall(callId: callId, response: 'accept');

      // Join Jitsi meeting
      await CallService().joinCall(
        callUrl: callUrl,
        displayName: displayName,
        isVideoCall: true, // Get from call data
        isModerator: isModerator,
      );
    } catch (e) {
      print('Error accepting call: $e');
    }
  }

  static Future<void> _declineCall(String callId) async {
    try {
      await CallService.respondToCall(callId: callId, response: 'decline');
    } catch (e) {
      print('Error declining call: $e');
    }
  }
}
```

### 4. UI Components

#### Incoming Call Dialog
```dart
class IncomingCallDialog extends StatelessWidget {
  final String callId;
  final String callerName;
  final String callUrl;
  final bool isVideoCall;
  final VoidCallback onAccept;
  final VoidCallback onDecline;

  const IncomingCallDialog({
    Key? key,
    required this.callId,
    required this.callerName,
    required this.callUrl,
    required this.isVideoCall,
    required this.onAccept,
    required this.onDecline,
  }) : super(key: key);

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text('Incoming ${isVideoCall ? 'Video' : 'Audio'} Call'),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          CircleAvatar(
            radius: 40,
            child: Text(callerName.substring(0, 1).toUpperCase()),
          ),
          SizedBox(height: 16),
          Text(
            callerName,
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold),
          ),
          SizedBox(height: 8),
          Text('is calling you...'),
        ],
      ),
      actions: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            // Decline button
            ElevatedButton.icon(
              onPressed: onDecline,
              icon: Icon(Icons.call_end, color: Colors.white),
              label: Text('Decline'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.red,
                foregroundColor: Colors.white,
              ),
            ),
            // Accept button
            ElevatedButton.icon(
              onPressed: onAccept,
              icon: Icon(
                isVideoCall ? Icons.videocam : Icons.call,
                color: Colors.white,
              ),
              label: Text('Accept'),
              style: ElevatedButton.styleFrom(
                backgroundColor: Colors.green,
                foregroundColor: Colors.white,
              ),
            ),
          ],
        ),
      ],
    );
  }
}
```

#### Call History UI
```dart
class CallHistoryScreen extends StatefulWidget {
  @override
  _CallHistoryScreenState createState() => _CallHistoryScreenState();
}

class _CallHistoryScreenState extends State<CallHistoryScreen> {
  List<dynamic> calls = [];
  bool isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadCallHistory();
  }

  Future<void> _loadCallHistory() async {
    try {
      final response = await http.get(
        Uri.parse('$baseUrl/api/v1/calls/history?limit=50'),
        headers: {
          'Authorization': 'Basic ${base64Encode(utf8.encode('$email:$apiKey'))}',
        },
      );

      if (response.statusCode == 200) {
        final data = json.decode(response.body);
        setState(() {
          calls = data['calls'];
          isLoading = false;
        });
      }
    } catch (e) {
      setState(() => isLoading = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Failed to load call history: $e')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: Text('Call History')),
      body: isLoading
          ? Center(child: CircularProgressIndicator())
          : ListView.builder(
              itemCount: calls.length,
              itemBuilder: (context, index) {
                final call = calls[index];
                final otherUser = call['other_user'];
                final wasInitiator = call['was_initiator'];

                return ListTile(
                  leading: CircleAvatar(
                    child: Icon(
                      call['call_type'] == 'video'
                          ? Icons.videocam
                          : Icons.call,
                    ),
                  ),
                  title: Text(otherUser['full_name']),
                  subtitle: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        wasInitiator ? 'Outgoing call' : 'Incoming call',
                        style: TextStyle(fontSize: 12),
                      ),
                      Text(
                        _formatCallTime(call['created_at']),
                        style: TextStyle(fontSize: 10, color: Colors.grey),
                      ),
                    ],
                  ),
                  trailing: _getCallStatusIcon(call['state']),
                  onTap: () {
                    // Show call details or initiate new call
                  },
                );
              },
            ),
    );
  }

  Widget _getCallStatusIcon(String state) {
    IconData icon;
    Color color;

    switch (state) {
      case 'ended':
        icon = Icons.call_end;
        color = Colors.green;
        break;
      case 'declined':
        icon = Icons.call_end;
        color = Colors.red;
        break;
      case 'missed':
        icon = Icons.call_missed;
        color = Colors.orange;
        break;
      default:
        icon = Icons.call;
        color = Colors.grey;
    }

    return Icon(icon, color: color, size: 20);
  }

  String _formatCallTime(String timestamp) {
    final dateTime = DateTime.parse(timestamp);
    final now = DateTime.now();
    final difference = now.difference(dateTime);

    if (difference.inDays > 0) {
      return '${difference.inDays} days ago';
    } else if (difference.inHours > 0) {
      return '${difference.inHours} hours ago';
    } else {
      return '${difference.inMinutes} minutes ago';
    }
  }
}
```

### 5. Permissions Handling

```dart
class PermissionService {
  static Future<bool> requestCallPermissions() async {
    final permissions = [
      Permission.camera,
      Permission.microphone,
      Permission.notification,
    ];

    Map<Permission, PermissionStatus> statuses =
        await permissions.request();

    return statuses.values.every(
      (status) => status == PermissionStatus.granted,
    );
  }

  static Future<bool> checkCallPermissions() async {
    final camera = await Permission.camera.status;
    final microphone = await Permission.microphone.status;
    final notification = await Permission.notification.status;

    return camera.isGranted &&
           microphone.isGranted &&
           notification.isGranted;
  }
}
```

---

## 🔑 Key Implementation Details

### 1. Moderator vs Participant URLs
The backend creates separate URLs:
- **Initiator** gets moderator URL with full control
- **Recipient** gets participant URL with limited privileges

```dart
// When creating a call (initiator)
final callResponse = await createCall(
  recipientEmail: recipientEmail,
  isVideoCall: isVideoCall,
);

// Initiator joins with moderator URL
await CallService().joinCall(
  callUrl: callResponse['call_url'], // Moderator URL
  displayName: currentUserName,
  isVideoCall: isVideoCall,
  isModerator: true,
);

// When accepting a call (recipient)
// The push notification contains participant URL
await CallService().joinCall(
  callUrl: notificationData['call_url'], // Participant URL
  displayName: currentUserName,
  isVideoCall: isVideoCall,
  isModerator: false,
);
```

### 2. Call States
The backend manages these call states:
- `initiated` - Call created, waiting for response
- `ringing` - Recipient notified, no response yet
- `active` - Call accepted and ongoing
- `ended` - Call completed
- `declined` - Call rejected
- `missed` - Call not answered in time
- `cancelled` - Call cancelled by initiator

### 3. Push Notification Data Format
```json
{
  "type": "call_invitation",
  "call_id": "uuid-string",
  "call_url": "https://meet.jit.si/room?params",
  "call_type": "video|audio",
  "caller_name": "John Doe",
  "caller_id": 123,
  "room_name": "zulip-call-abc123"
}
```

---

## 🧪 Testing Your Implementation

### 1. Unit Tests
```dart
// test/call_service_test.dart
import 'package:flutter_test/flutter_test.dart';
import 'package:mockito/mockito.dart';

void main() {
  group('CallService', () {
    test('should create call successfully', () async {
      // Test call creation
      final result = await CallService.createCall(
        recipientEmail: 'test@example.com',
        isVideoCall: true,
      );

      expect(result['result'], 'success');
      expect(result['call_id'], isNotNull);
    });

    test('should handle call response', () async {
      // Test call acceptance/decline
      await CallService.respondToCall(
        callId: 'test-call-id',
        response: 'accept',
      );

      // Verify API was called correctly
    });
  });
}
```

### 2. Integration Testing
```bash
# Test with actual Zulip server
flutter test integration_test/call_flow_test.dart

# Test push notifications
flutter test integration_test/notification_test.dart
```

---

## 📋 Implementation Checklist

### Mobile Setup
- [ ] Add Jitsi Meet SDK dependency
- [ ] Add Firebase messaging for push notifications
- [ ] Add permission_handler for camera/mic permissions
- [ ] Implement call service with API integration
- [ ] Create incoming call dialog UI
- [ ] Set up push notification handlers
- [ ] Implement call history screen
- [ ] Add permission request flows

### Backend Integration
- [ ] Test `/api/v1/calls/create-embedded` endpoint
- [ ] Test `/api/v1/calls/{id}/respond` endpoint
- [ ] Test `/api/v1/calls/{id}/end` endpoint
- [ ] Test push notification delivery
- [ ] Verify moderator/participant URL handling
- [ ] Test call state management

### Production Readiness
- [ ] Add error handling for network failures
- [ ] Implement retry logic for API calls
- [ ] Add call quality monitoring
- [ ] Set up analytics and crash reporting
- [ ] Add call recording capabilities (if needed)
- [ ] Implement call waiting/busy status
- [ ] Add contact integration
- [ ] Test on different devices and OS versions

---

## 🚀 Quick Start Guide

1. **Add dependencies to pubspec.yaml**:
   ```yaml
   dependencies:
     jitsi_meet_flutter_sdk: ^10.0.0
     firebase_core: ^2.24.2
     firebase_messaging: ^14.7.10
     permission_handler: ^11.0.1
     http: ^1.1.0
   ```

2. **Set up Firebase**:
   - Add `google-services.json` (Android) and `GoogleService-Info.plist` (iOS)
   - Configure FCM in Firebase Console

3. **Initialize services**:
   ```dart
   await Firebase.initializeApp();
   await CallNotificationService.initialize();
   await PermissionService.requestCallPermissions();
   ```

4. **Test with backend**:
   ```dart
   final result = await CallService.createCall(
     recipientEmail: 'test@yourdomain.com',
     isVideoCall: true,
   );
   print('Call created: ${result['call_id']}');
   ```

5. **Handle incoming calls**:
   ```dart
   FirebaseMessaging.onMessage.listen((message) {
     if (message.data['type'] == 'call_invitation') {
       CallNotificationService.handleCallNotification(message);
     }
   });
   ```

The mobile app will now work seamlessly with your Zulip Calls Plugin backend! 🎉

---

## 📞 API Response Examples

### Call Creation Response
```json
{
  "result": "success",
  "call_id": "550e8400-e29b-41d4-a716-446655440000",
  "call_url": "https://meet.jit.si/zulip-call-abc123?userInfo.displayName=John%20Doe&config.startWithAudioMuted=false",
  "participant_url": "https://meet.jit.si/zulip-call-abc123?userInfo.displayName=Jane%20Doe&config.startWithAudioMuted=true",
  "call_type": "video",
  "room_name": "zulip-call-abc123",
  "recipient": {
    "user_id": 456,
    "full_name": "Jane Doe",
    "email": "jane@example.com"
  }
}
```

### Call History Response
```json
{
  "result": "success",
  "calls": [
    {
      "call_id": "550e8400-e29b-41d4-a716-446655440000",
      "call_type": "video",
      "state": "ended",
      "was_initiator": true,
      "other_user": {
        "user_id": 456,
        "full_name": "Jane Doe",
        "email": "jane@example.com"
      },
      "created_at": "2025-09-15T14:30:00Z",
      "started_at": "2025-09-15T14:30:15Z",
      "ended_at": "2025-09-15T14:45:30Z",
      "duration_seconds": 915
    }
  ],
  "has_more": false
}
```