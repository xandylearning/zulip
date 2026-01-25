# Flutter Integration: Reminders API

This document provides REST API request/response examples for integrating message reminders in a Flutter application.

## Table of Contents
1. [Create Reminder](#create-reminder)
2. [Get Reminders](#get-reminders)
3. [Delete Reminder](#delete-reminder)
4. [Complete Flutter Example](#complete-flutter-example)

---

## Create Reminder

Create a reminder for a message. The reminder will be sent as a direct message to yourself at the specified time.

**Endpoint:** `POST /api/v1/reminders`

**Request Headers:**
```
Authorization: Basic {base64(email:api_key)}
Content-Type: application/json
```

**Request Body:**
```json
{
  "message_id": 123,
  "scheduled_delivery_timestamp": 1640995200,
  "note": "Optional reminder note"
}
```

**Request Parameters:**
- `message_id` (required, integer): The ID of the message to create a reminder for
- `scheduled_delivery_timestamp` (required, integer): Unix timestamp (seconds since epoch) for when the reminder should be delivered. Must be in the future.
- `note` (optional, string): Optional note to include with the reminder. Maximum length is 500 characters.

**Example Request (cURL):**
```bash
curl -X POST https://your-zulip-server.com/api/v1/reminders \
  -u user@example.com:your_api_key \
  -H "Content-Type: application/json" \
  -d '{
    "message_id": 123,
    "scheduled_delivery_timestamp": 1640995200,
    "note": "Follow up on this"
  }'
```

**Example Request (Flutter/Dart):**
```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

Future<int> createReminder({
  required String baseUrl,
  required String email,
  required String apiKey,
  required int messageId,
  required int scheduledDeliveryTimestamp,
  String? note,
}) async {
  final url = Uri.parse('$baseUrl/api/v1/reminders');
  final credentials = base64Encode(utf8.encode('$email:$apiKey'));
  
  final response = await http.post(
    url,
    headers: {
      'Authorization': 'Basic $credentials',
      'Content-Type': 'application/json',
    },
    body: jsonEncode({
      'message_id': messageId,
      'scheduled_delivery_timestamp': scheduledDeliveryTimestamp,
      if (note != null) 'note': note,
    }),
  );
  
  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    return data['reminder_id'] as int;
  } else {
    throw Exception('Failed to create reminder: ${response.body}');
  }
}

// Usage example
void example() async {
  // Create a reminder for 24 hours from now
  final now = DateTime.now();
  final tomorrow = now.add(Duration(hours: 24));
  final timestamp = tomorrow.millisecondsSinceEpoch ~/ 1000;
  
  final reminderId = await createReminder(
    baseUrl: 'https://your-zulip-server.com',
    email: 'user@example.com',
    apiKey: 'your_api_key',
    messageId: 123,
    scheduledDeliveryTimestamp: timestamp,
    note: 'Don\'t forget to follow up',
  );
  
  print('Reminder created with ID: $reminderId');
}
```

**Success Response (200 OK):**
```json
{
  "result": "success",
  "msg": "",
  "reminder_id": 42
}
```

**Response Fields:**
- `reminder_id` (integer): The ID of the created reminder, which can be used to delete it later

**Error Response (400 Bad Request):**
```json
{
  "result": "error",
  "msg": "Scheduled delivery time must be in the future.",
  "code": "DELIVERY_TIME_NOT_IN_FUTURE"
}
```

**Error Response (400 Bad Request) - Invalid Message:**
```json
{
  "result": "error",
  "msg": "Invalid message(s)",
  "code": "BAD_REQUEST"
}
```

**Error Response (400 Bad Request) - Note Too Long:**
```json
{
  "result": "error",
  "msg": "Maximum reminder note length: 500 characters",
  "code": "BAD_REQUEST"
}
```

---

## Get Reminders

Get all undelivered reminders for the current user.

**Endpoint:** `GET /api/v1/reminders`

**Request Headers:**
```
Authorization: Basic {base64(email:api_key)}
```

**Example Request (cURL):**
```bash
curl -X GET https://your-zulip-server.com/api/v1/reminders \
  -u user@example.com:your_api_key
```

**Example Request (Flutter/Dart):**
```dart
Future<List<Map<String, dynamic>>> getReminders({
  required String baseUrl,
  required String email,
  required String apiKey,
}) async {
  final url = Uri.parse('$baseUrl/api/v1/reminders');
  final credentials = base64Encode(utf8.encode('$email:$apiKey'));
  
  final response = await http.get(
    url,
    headers: {
      'Authorization': 'Basic $credentials',
    },
  );
  
  if (response.statusCode == 200) {
    final data = jsonDecode(response.body);
    return List<Map<String, dynamic>>.from(data['reminders'] ?? []);
  } else {
    throw Exception('Failed to get reminders: ${response.body}');
  }
}
```

**Success Response (200 OK):**
```json
{
  "result": "success",
  "msg": "",
  "reminders": [
    {
      "reminder_id": 42,
      "to": [10],
      "type": "private",
      "content": "You requested a reminder for #**general>Hello@123**.\n\n@_**John Doe|5** [said](https://zulip.example.com/#narrow/channel/1-general/topic/Hello/near/123):\n```quote\nThis is the message content\n```",
      "rendered_content": "<p>You requested a reminder for <a href=\"#narrow/channel/1-general/topic/Hello/near/123\">#<strong>general</strong>&gt;Hello@123</a>.</p>\n<p><span class=\"user-mention\" data-user-id=\"5\">@John Doe</span> <a href=\"https://zulip.example.com/#narrow/channel/1-general/topic/Hello/near/123\">said</a>:</p>\n<div class=\"codehilite\"><pre><span></span>This is the message content\n</pre></div>",
      "scheduled_delivery_timestamp": 1640995200,
      "failed": false,
      "reminder_target_message_id": 123
    },
    {
      "reminder_id": 43,
      "to": [10],
      "type": "private",
      "content": "You requested a reminder for the following direct message. Note:\n > Follow up on this\n\n@_**Jane Smith|6** [said](https://zulip.example.com/#narrow/dm/6,10/near/124):\n```quote\nDirect message content\n```",
      "rendered_content": "<p>You requested a reminder for the following direct message. Note:</p>\n<blockquote>\n<p>Follow up on this</p>\n</blockquote>\n<p><span class=\"user-mention\" data-user-id=\"6\">@Jane Smith</span> <a href=\"https://zulip.example.com/#narrow/dm/6,10/near/124\">said</a>:</p>\n<div class=\"codehilite\"><pre><span></span>Direct message content\n</pre></div>",
      "scheduled_delivery_timestamp": 1641081600,
      "failed": false,
      "reminder_target_message_id": 124
    }
  ]
}
```

**Response Fields:**
- `reminders` (array): List of reminder objects, ordered by scheduled delivery time (earliest first)

**Reminder Object Fields:**
- `reminder_id` (integer): Unique identifier for the reminder
- `to` (array of integers): List of user IDs who will receive the reminder (always includes yourself)
- `type` (string): Always `"private"` for reminders (they are sent as direct messages)
- `content` (string): Plain text content of the reminder message
- `rendered_content` (string): HTML-rendered content of the reminder message
- `scheduled_delivery_timestamp` (integer): Unix timestamp (seconds) when the reminder will be delivered
- `failed` (boolean): Whether the reminder delivery has failed
- `reminder_target_message_id` (integer): The ID of the message this reminder is for

**Empty Response (200 OK):**
```json
{
  "result": "success",
  "msg": "",
  "reminders": []
}
```

---

## Delete Reminder

Delete a reminder before it is delivered.

**Endpoint:** `DELETE /api/v1/reminders/{reminder_id}`

**Request Headers:**
```
Authorization: Basic {base64(email:api_key)}
```

**Example Request (cURL):**
```bash
curl -X DELETE https://your-zulip-server.com/api/v1/reminders/42 \
  -u user@example.com:your_api_key
```

**Example Request (Flutter/Dart):**
```dart
Future<void> deleteReminder({
  required String baseUrl,
  required String email,
  required String apiKey,
  required int reminderId,
}) async {
  final url = Uri.parse('$baseUrl/api/v1/reminders/$reminderId');
  final credentials = base64Encode(utf8.encode('$email:$apiKey'));
  
  final response = await http.delete(
    url,
    headers: {
      'Authorization': 'Basic $credentials',
    },
  );
  
  if (response.statusCode != 200) {
    throw Exception('Failed to delete reminder: ${response.body}');
  }
}
```

**Success Response (200 OK):**
```json
{
  "result": "success",
  "msg": ""
}
```

**Error Response (404 Not Found):**
```json
{
  "result": "error",
  "msg": "Reminder does not exist",
  "code": "RESOURCE_NOT_FOUND"
}
```

---

## Complete Flutter Example

Here's a complete example class for managing reminders:

```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

class Reminder {
  final int reminderId;
  final List<int> to;
  final String type;
  final String content;
  final String renderedContent;
  final int scheduledDeliveryTimestamp;
  final bool failed;
  final int reminderTargetMessageId;

  Reminder({
    required this.reminderId,
    required this.to,
    required this.type,
    required this.content,
    required this.renderedContent,
    required this.scheduledDeliveryTimestamp,
    required this.failed,
    required this.reminderTargetMessageId,
  });

  factory Reminder.fromJson(Map<String, dynamic> json) {
    return Reminder(
      reminderId: json['reminder_id'] as int,
      to: List<int>.from(json['to'] as List),
      type: json['type'] as String,
      content: json['content'] as String,
      renderedContent: json['rendered_content'] as String,
      scheduledDeliveryTimestamp: json['scheduled_delivery_timestamp'] as int,
      failed: json['failed'] as bool,
      reminderTargetMessageId: json['reminder_target_message_id'] as int,
    );
  }

  DateTime get scheduledDeliveryTime {
    return DateTime.fromMillisecondsSinceEpoch(
      scheduledDeliveryTimestamp * 1000,
    );
  }
}

class ZulipReminders {
  final String baseUrl;
  final String email;
  final String apiKey;
  
  ZulipReminders({
    required this.baseUrl,
    required this.email,
    required this.apiKey,
  });
  
  String get _authHeader {
    final credentials = base64Encode(utf8.encode('$email:$apiKey'));
    return 'Basic $credentials';
  }
  
  /// Create a reminder for a message
  /// 
  /// [messageId] - The ID of the message to create a reminder for
  /// [scheduledDeliveryTime] - When the reminder should be delivered
  /// [note] - Optional note to include with the reminder
  Future<int> createReminder({
    required int messageId,
    required DateTime scheduledDeliveryTime,
    String? note,
  }) async {
    final url = Uri.parse('$baseUrl/api/v1/reminders');
    final timestamp = scheduledDeliveryTime.millisecondsSinceEpoch ~/ 1000;
    
    final response = await http.post(
      url,
      headers: {
        'Authorization': _authHeader,
        'Content-Type': 'application/json',
      },
      body: jsonEncode({
        'message_id': messageId,
        'scheduled_delivery_timestamp': timestamp,
        if (note != null) 'note': note,
      }),
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data['reminder_id'] as int;
    } else {
      final error = jsonDecode(response.body);
      throw Exception('Failed to create reminder: ${error['msg']}');
    }
  }
  
  /// Get all undelivered reminders
  Future<List<Reminder>> getReminders() async {
    final url = Uri.parse('$baseUrl/api/v1/reminders');
    
    final response = await http.get(
      url,
      headers: {
        'Authorization': _authHeader,
      },
    );
    
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      final remindersList = data['reminders'] as List;
      return remindersList
          .map((json) => Reminder.fromJson(json as Map<String, dynamic>))
          .toList();
    } else {
      throw Exception('Failed to get reminders: ${response.body}');
    }
  }
  
  /// Delete a reminder
  Future<void> deleteReminder(int reminderId) async {
    final url = Uri.parse('$baseUrl/api/v1/reminders/$reminderId');
    
    final response = await http.delete(
      url,
      headers: {
        'Authorization': _authHeader,
      },
    );
    
    if (response.statusCode != 200) {
      final error = jsonDecode(response.body);
      throw Exception('Failed to delete reminder: ${error['msg']}');
    }
  }
  
  /// Create a reminder for 1 hour from now
  Future<int> createReminderInOneHour({
    required int messageId,
    String? note,
  }) async {
    final oneHourLater = DateTime.now().add(Duration(hours: 1));
    return createReminder(
      messageId: messageId,
      scheduledDeliveryTime: oneHourLater,
      note: note,
    );
  }
  
  /// Create a reminder for 24 hours from now
  Future<int> createReminderTomorrow({
    required int messageId,
    String? note,
  }) async {
    final tomorrow = DateTime.now().add(Duration(days: 1));
    return createReminder(
      messageId: messageId,
      scheduledDeliveryTime: tomorrow,
      note: note,
    );
  }
}

// Usage example
void example() async {
  final reminders = ZulipReminders(
    baseUrl: 'https://your-zulip-server.com',
    email: 'user@example.com',
    apiKey: 'your_api_key',
  );
  
  // Create a reminder for 1 hour from now
  final reminderId = await reminders.createReminderInOneHour(
    messageId: 123,
    note: 'Follow up on this message',
  );
  print('Reminder created: $reminderId');
  
  // Get all reminders
  final allReminders = await reminders.getReminders();
  print('You have ${allReminders.length} reminders');
  
  for (final reminder in allReminders) {
    print('Reminder ${reminder.reminderId} scheduled for ${reminder.scheduledDeliveryTime}');
  }
  
  // Delete a reminder
  await reminders.deleteReminder(reminderId);
  print('Reminder deleted');
}
```

---

## Notes

1. **Reminder Delivery**: Reminders are delivered as direct messages to yourself at the scheduled time. The reminder message includes:
   - A link to the original message
   - The original message content (quoted)
   - Your optional note (if provided)

2. **Timestamp Format**: All timestamps are Unix timestamps in seconds (not milliseconds).

3. **Future Timestamps Only**: The `scheduled_delivery_timestamp` must be in the future. Attempting to create a reminder with a past timestamp will result in an error.

4. **Reminder Content**: The reminder content is automatically formatted by the server and includes:
   - For channel messages: A link to the channel message
   - For direct messages: The direct message content
   - Your optional note (if provided)
   - The original message content as a quote

5. **Failed Reminders**: Reminders that fail to deliver will still appear in the list with `failed: true`. You can delete them manually.

6. **Reminder Limits**: There's no explicit limit on the number of reminders you can create, but be mindful of server resources.

7. **Real-time Updates**: When you create or delete a reminder, you'll receive a real-time event through the events API (`/api/v1/events`) with type `"reminder"` or `"scheduled_message"`.

---

## Error Codes

Common error codes you may encounter:

- `DELIVERY_TIME_NOT_IN_FUTURE`: The scheduled delivery timestamp is in the past
- `BAD_REQUEST`: Invalid message ID or other validation error
- `RESOURCE_NOT_FOUND`: Reminder does not exist (when deleting)
- `UNAUTHORIZED`: Invalid authentication credentials

---

## Integration with Real-time Events

Reminders are also available through the real-time events API. When you register an event queue, you can request `"reminders"` in the `event_types`:

```dart
// Register event queue with reminders
final registerResponse = await http.post(
  Uri.parse('$baseUrl/api/v1/register'),
  headers: {
    'Authorization': _authHeader,
    'Content-Type': 'application/json',
  },
  body: jsonEncode({
    'event_types': ['reminder', 'message'],
    'fetch_event_types': ['reminder', 'message'],
  }),
);
```

You'll receive events when reminders are created, updated, or deleted.
