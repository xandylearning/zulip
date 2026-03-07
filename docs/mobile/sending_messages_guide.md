# Mobile Message Sending Guide

This guide details how to send various types of messages from a mobile client to the Zulip server. It covers standard text messages as well as rich media messages including images, videos, audio, voice messages, documents, locations, and contacts.

## API Endpoint

**URL**: `POST /api/v1/messages`

**Content-Type**: `application/x-www-form-urlencoded`

## Common Parameters

All message requests must include the following parameters:

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `type` | string | The type of message: `"private"` (for DMs) or `"stream"` (for channels). |
| `to` | string/array | **For Stream**: The name or ID of the stream.<br>**For Private**: A list of user IDs or emails. |
| `content` | string | The message body. For normal text messages, this must be non-empty. For rich media messages that include `media_type` and `primary_attachment_path_id`, `content` may be empty; the server will generate a Markdown fallback based on the attachment so that older clients still display a link. |
| `topic` | string | **Required for Stream messages**. The topic of the message. |

---

## sending Rich Media Messages

Sending rich media (images, video, audio, etc.) is a **two-step process**:

1.  **Upload the file** to get a `uri`.
2.  **Send the message** referencing the file's path ID and including media metadata.

### Step 1: Upload File

**Endpoint**: `POST /api/v1/user_uploads`

**Body**: `multipart/form-data` with the file in the `file` field.

**Response**:
```json
{
  "result": "success",
  "uri": "/user_uploads/1/4e/m2w3k4/image.png",
  "msg": "",
  "id": 42
}
```

**Extract the Path ID**: Remove the leading `/user_uploads/` from the `uri`.
*   Example URI: `/user_uploads/1/4e/m2w3k4/image.png`
*   **Path ID**: `1/4e/m2w3k4/image.png`

### Step 2: Send Message

Include these additional parameters in your `POST /api/v1/messages` request:

| Parameter | Type | Description |
| :--- | :--- | :--- |
| `media_type` | string | The type of media: `image`, `video`, `audio`, `voice_message`, `document`. |
| `primary_attachment_path_id` | string | The **Path ID** obtained from Step 1. |
| `media_metadata` | JSON string | A JSON object containing metadata specific to the media type (e.g., dimensions, duration). |
| `caption` | string | (Optional) A caption for the media. |

For all of the examples below, `content` is intentionally left empty for media messages. When `media_type` and `primary_attachment_path_id` are provided, the server accepts an empty body and automatically generates a Markdown fallback using the uploaded file, so that older clients still see a sensible link.

---

## Message Type Examples

### 1. Normal Text Message

```http
POST /api/v1/messages
type=stream
to=general
topic=Greetings
content=Hello world!
```

### 2. Image Message

**Prerequisite**: Upload image, get path ID (e.g., `1/4e/img.jpg`).

```http
POST /api/v1/messages
type=private
to=[123]
content=
media_type=image
primary_attachment_path_id=1/4e/img.jpg
caption=Check out this view!
media_metadata={"width": 1920, "height": 1080, "mime_type": "image/jpeg"}
```

### 3. Video Message

**Prerequisite**: Upload video, get path ID (e.g., `1/4e/vid.mp4`).

```http
POST /api/v1/messages
type=stream
to=design
topic=Assets
content=
media_type=video
primary_attachment_path_id=1/4e/vid.mp4
caption=Demo walkthrough
media_metadata={"width": 1280, "height": 720, "duration_secs": 45, "mime_type": "video/mp4"}
```

### 4. Audio Message

**Prerequisite**: Upload audio file, get path ID (e.g., `1/4e/song.mp3`).

```http
POST /api/v1/messages
type=private
to=[456]
content=
media_type=audio
primary_attachment_path_id=1/4e/song.mp3
caption=Listen to this track
media_metadata={"duration_secs": 180, "mime_type": "audio/mpeg"}
```

### 5. Voice Message

**Prerequisite**: Record audio, upload it, get path ID (e.g., `1/4e/voice.webm`).
**Note**: `waveform` is an array of amplitude values (0.0 to 1.0) for visualization.

```http
POST /api/v1/messages
type=private
to=[123]
content=
media_type=voice_message
primary_attachment_path_id=1/4e/voice.webm
media_metadata={"duration_secs": 15, "mime_type": "audio/webm", "waveform": [0.1, 0.5, 0.8, 0.3, 0.1]}
```

### 6. Document Message

**Prerequisite**: Upload document, get path ID (e.g., `1/4e/report.pdf`).

```http
POST /api/v1/messages
type=stream
to=reports
topic=Q1
content=
media_type=document
primary_attachment_path_id=1/4e/report.pdf
caption=Q1 Financial Report
media_metadata={"mime_type": "application/pdf", "page_count": 12}
```

### 7. Location Message

**Note**: No file upload required.

```http
POST /api/v1/messages
type=private
to=[123]
content=
media_type=location
media_metadata={"latitude": 37.7749, "longitude": -122.4194, "name": "San Francisco", "address": "Market St, SF, CA"}
```

### 8. Contact Message

**Note**: No file upload required.

```http
POST /api/v1/messages
type=private
to=[123]
content=
media_type=contact
media_metadata={"name": "John Doe", "phone": "+15550199", "email": "john.doe@example.com"}
```
