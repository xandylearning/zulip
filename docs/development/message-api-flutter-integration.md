# Message API for Flutter Integration

This document describes the Zulip message API structure and rich media message types for integrating the Flutter mobile app. It covers the updated request/response shapes, client capabilities, and recommended Dart models.

## Overview

- **Base URL**: `{server}/api/v1` (e.g. `https://your-server.zulip.com/api/v1`)
- **Auth**: HTTP Basic (email + API key) or session cookie
- **Content type**: `application/x-www-form-urlencoded` for `POST /messages`; query params for GET

To receive and send **rich media messages** (image, video, audio, voice, document, location, contact, sticker), the Flutter app must:

1. Declare the `rich_media_message_types` client capability when registering the event queue.
2. Send optional `media_type`, `caption`, `media_metadata`, and `primary_attachment_path_id` when posting messages.
3. Parse the extended message object in both REST responses and real-time events.

---

## 1. Register event queue (required for rich media)

**Endpoint**: `POST /api/v1/register`

To receive message events that include `media_type`, `caption`, `media_metadata`, and `primary_attachment`, the client must opt in via `client_capabilities`.

### Request

Include in the request body (e.g. as JSON for the `client_capabilities` parameter if your client sends it as JSON):

```json
{
  "client_capabilities": {
    "notification_settings_null": true,
    "rich_media_message_types": true
  }
}
```

- **`rich_media_message_types`** (boolean): When `true`, message objects in the register response, in `GET /messages` responses, and in `message` events from `GET /events` will include:
  - `media_type`
  - `caption`
  - `media_metadata`
  - `primary_attachment`

When `false` or omitted, those fields are not sent; the app can still render messages using the `content` field (Markdown/HTML fallback).

### Flutter / Dart

When calling your register API client, set capabilities before registering:

```dart
// Example: ensure your register payload includes:
final response = await zulipApi.register(
  clientCapabilities: {
    'notification_settings_null': true,
    'rich_media_message_types': true,
    // ... other capabilities your app uses
  },
);
```

---

## 2. Get messages

**Endpoint**: `GET /api/v1/messages`

Query params: `anchor`, `num_before`, `num_after`, `narrow` (JSON array), optional `apply_markdown`, `client_gravatar`, etc.

### Response (with rich media)

When the client has registered with `rich_media_message_types: true`, each item in `messages` can include the rich media fields below. Standard fields (e.g. `id`, `content`, `sender_id`, `timestamp`, `type`, `subject`, `stream_id`, `display_recipient`, etc.) are unchanged.

**Extended message object (relevant fields for Flutter)**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Message ID |
| `content` | string | Body (HTML or Markdown). Always present; for media messages this is a fallback (e.g. image Markdown). |
| `type` | string | `"stream"` or `"private"` |
| `subject` | string | Topic (stream messages only) |
| `stream_id` | int? | Present for stream messages |
| `sender_id` | int | Sender user ID |
| `timestamp` | int | Unix time (seconds) |
| `media_type` | string? | One of: `image`, `video`, `audio`, `voice_message`, `document`, `location`, `contact`, `sticker`. `null` for normal text. |
| `caption` | string? | Caption for media messages |
| `media_metadata` | object? | Type-specific metadata (see below) |
| `primary_attachment` | object? | Present for file-based media (image, video, audio, voice_message, document) |

**`primary_attachment` shape**:

| Field | Type | Description |
|-------|------|-------------|
| `id` | int | Attachment ID |
| `name` | string | Original filename |
| `path_id` | string | Path segment for URL (see “Attachment URL” below) |
| `size` | int | Size in bytes |
| `content_type` | string? | MIME type |

### Attachment URL

To build the download/display URL for an attachment:

```text
{server_url}/user_uploads/{path_id}
```

Example: if `path_id` is `2/ab/cdef/photo.jpg` and server is `https://example.zulip.com`, the URL is:

```text
https://example.zulip.com/user_uploads/2/ab/cdef/photo.jpg
```

Requests must use the same auth (e.g. API key or session) as the rest of the API.

### Dart model suggestion

```dart
class PrimaryAttachment {
  final int id;
  final String name;
  final String pathId;
  final int size;
  final String? contentType;

  PrimaryAttachment({
    required this.id,
    required this.name,
    required this.pathId,
    required this.size,
    this.contentType,
  });

  factory PrimaryAttachment.fromJson(Map<String, dynamic> json) {
    return PrimaryAttachment(
      id: json['id'] as int,
      name: json['name'] as String,
      pathId: json['path_id'] as String,
      size: json['size'] as int,
      contentType: json['content_type'] as String?,
    );
  }

  String url(String serverUrl) =>
      '$serverUrl/user_uploads/$pathId';
}

class Message {
  final int id;
  final String content;
  final String type; // 'stream' | 'private'
  final String subject;
  final int? streamId;
  final int senderId;
  final int timestamp;
  final String? mediaType;
  final String? caption;
  final Map<String, dynamic>? mediaMetadata;
  final PrimaryAttachment? primaryAttachment;
  // ... other fields (reactions, display_recipient, etc.)

  Message({
    required this.id,
    required this.content,
    required this.type,
    required this.subject,
    this.streamId,
    required this.senderId,
    required this.timestamp,
    this.mediaType,
    this.caption,
    this.mediaMetadata,
    this.primaryAttachment,
  });

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] as int,
      content: json['content'] as String,
      type: json['type'] as String,
      subject: (json['subject'] ?? '') as String,
      streamId: json['stream_id'] as int?,
      senderId: json['sender_id'] as int,
      timestamp: json['timestamp'] as int,
      mediaType: json['media_type'] as String?,
      caption: json['caption'] as String?,
      mediaMetadata: json['media_metadata'] != null
          ? Map<String, dynamic>.from(json['media_metadata'] as Map)
          : null,
      primaryAttachment: json['primary_attachment'] != null
          ? PrimaryAttachment.fromJson(
              Map<String, dynamic>.from(json['primary_attachment'] as Map))
          : null,
    );
  }

  bool get isRichMedia => mediaType != null;
}
```

---

## 3. Send message

**Endpoint**: `POST /api/v1/messages`

Body: `application/x-www-form-urlencoded`.

### Required parameters

| Parameter | Type | Description |
|-----------|------|-------------|
| `type` | string | `"direct"` or `"private"` for DM; `"stream"` or `"channel"` for channel |
| `to` | string / int / array | Channel name or ID, or list of user IDs/emails for DM |
| `content` | string | Message body (can be empty for some media-only messages) |

For channel messages, `topic` is required.

### Optional parameters (rich media)

| Parameter | Type | Description |
|-----------|------|-------------|
| `media_type` | string | One of: `image`, `video`, `audio`, `voice_message`, `document`, `location`, `contact`, `sticker` |
| `caption` | string | Caption for the media message |
| `media_metadata` | JSON object | Type-specific metadata (see “Media metadata by type” below) |
| `primary_attachment_path_id` | string | Path ID from upload response; links the uploaded file as the primary attachment. If omitted but `media_type` is set, no file is attached (e.g. location/contact). |

If `primary_attachment_path_id` is set but `media_type` is not, the server will infer `media_type` from the attachment’s content type.

Other optional params: `queue_id`, `local_id` (local echo), `read_by_sender`, `topic` (for channel).

### Upload flow for file-based media

1. **Upload file**: `POST /api/v1/user_uploads` with the file. Response includes `uri` (e.g. `/user_uploads/1/4e/xxx/filename.jpg`). The path after `/user_uploads/` is the `path_id` to use as `primary_attachment_path_id` (e.g. `1/4e/xxx/filename.jpg`).
2. **Send message**: `POST /api/v1/messages` with `type`, `to`, `content` (can be empty), `media_type`, optional `caption`, optional `media_metadata`, and `primary_attachment_path_id` set to that path.

Example (conceptual) for an image:

```text
content=
&type=private
&to=[9,10]
&media_type=image
&caption=Sunset
&media_metadata={"width":1920,"height":1080,"mime_type":"image/jpeg"}
&primary_attachment_path_id=1/4e/abc123/photo.jpg
```

### Media metadata by type

Use these shapes when sending `media_metadata` (and when parsing them in Flutter).

| media_type | Suggested JSON shape (all optional where noted) |
|------------|--------------------------------------------------|
| `image` | `{"width": int, "height": int, "mime_type": string}` |
| `video` | `{"width": int, "height": int, "duration_secs": int, "mime_type": string}` |
| `audio` | `{"duration_secs": int, "mime_type": string}` |
| `voice_message` | `{"duration_secs": int, "mime_type": string, "waveform": [float, ...]}` |
| `document` | `{"mime_type": string, "page_count": int}` |
| `location` | `{"latitude": float, "longitude": float, "name": string, "address": string}` |
| `contact` | `{"name": string, "phone": string, "email": string}` |
| `sticker` | `{"pack_id": string, "sticker_id": string}` |

Example Dart helper for type-safe metadata:

```dart
abstract class MediaMetadata {
  Map<String, dynamic> toJson();
}

class ImageMetadata implements MediaMetadata {
  final int? width;
  final int? height;
  final String? mimeType;
  ImageMetadata({this.width, this.height, this.mimeType});
  @override
  Map<String, dynamic> toJson() => {
    if (width != null) 'width': width,
    if (height != null) 'height': height,
    if (mimeType != null) 'mime_type': mimeType,
  };
}

class LocationMetadata implements MediaMetadata {
  final double latitude;
  final double longitude;
  final String? name;
  final String? address;
  LocationMetadata({
    required this.latitude,
    required this.longitude,
    this.name,
    this.address,
  });
  @override
  Map<String, dynamic> toJson() => {
    'latitude': latitude,
    'longitude': longitude,
    if (name != null) 'name': name,
    if (address != null) 'address': address,
  };
}

class VoiceMessageMetadata implements MediaMetadata {
  final int durationSecs;
  final String? mimeType;
  final List<double>? waveform;
  VoiceMessageMetadata({
    required this.durationSecs,
    this.mimeType,
    this.waveform,
  });
  @override
  Map<String, dynamic> toJson() => {
    'duration_secs': durationSecs,
    if (mimeType != null) 'mime_type': mimeType,
    if (waveform != null) 'waveform': waveform,
  };
}
// Similarly for video, audio, document, contact, sticker.
```

---

## 4. Real-time events

**Endpoint**: `GET /api/v1/events?queue_id=...&last_event_id=...`

When a new message is created, the server sends a `message` event. The payload structure matches the message object returned by `GET /messages` and by `POST /messages` (including `media_type`, `caption`, `media_metadata`, `primary_attachment` when the client registered with `rich_media_message_types: true`).

Flutter should use the same `Message.fromJson` (and `PrimaryAttachment.fromJson`) for:

- Initial load: `GET /messages`
- Send response: `POST /messages` returns `id` (and optionally full message in some flows)
- Live updates: `GET /events` → `type: "message"` → `message` object

---

## 5. Summary checklist for Flutter

- [ ] Call `POST /register` with `client_capabilities.rich_media_message_types: true`.
- [ ] Use the same message model for GET messages, POST response, and event `message` payloads.
- [ ] Build attachment URLs as `{server_url}/user_uploads/{path_id}`.
- [ ] For sending: upload file first, then send message with `primary_attachment_path_id`, `media_type`, and optional `caption` and `media_metadata`.
- [ ] Handle `media_type == null` as normal text; use `content` as fallback for any message.
- [ ] Optionally use typed `media_metadata` classes per `media_type` for UI (duration, dimensions, location, etc.).

For full OpenAPI details (all parameters and response codes), see the server’s OpenAPI spec at `zerver/openapi/zulip.yaml` (paths `/messages`, `/register`, `/events`, `/user_uploads`). The authoritative message and attachment schemas are in the `MessagesBase` / `MessagesEvent` and related components there.
