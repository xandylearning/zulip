# Media Message Types Subsystem

This document describes Zulip's rich media message types system, which extends the platform to support WhatsApp-style media messages including images, videos, audio files, documents, location sharing, contact cards, stickers, and voice messages.

## Overview

The media message types subsystem allows Zulip to treat various media types as first-class message types rather than just Markdown links. This provides:

1. **Structured Media Data**: Messages include structured metadata (dimensions, duration, location coordinates, etc.)
2. **Rich UI Rendering**: Specialized UI components for each media type
3. **Backward Compatibility**: Older clients continue to work with Markdown content fallback
4. **Mobile API Support**: Optimized data structures for mobile clients

## Architecture

### Database Schema

The system extends `AbstractMessage` (used by both `Message` and `ArchivedMessage`) with:

- **`type`**: IntegerChoices enum field with values:
  - `NORMAL` (1): Standard text messages
  - `RESOLVE_TOPIC_NOTIFICATION` (2): Topic resolution notifications
  - `IMAGE` (3): Image messages
  - `VIDEO` (4): Video messages
  - `AUDIO` (5): Audio file messages
  - `DOCUMENT` (6): Document/file messages
  - `LOCATION` (7): Location sharing messages
  - `CONTACT` (8): Contact card messages
  - `STICKER` (9): Sticker messages
  - `VOICE_MESSAGE` (10): In-app recorded voice messages

- **`caption`**: TextField for optional caption text accompanying media
- **`primary_attachment`**: ForeignKey to `Attachment` model for messages with file attachments
- **`media_metadata`**: JSONField for flexible, type-specific metadata

### Message Flow

#### Sending Media Messages

1. **Upload**: User uploads a file via `/api/v1/user_uploads` or uses in-app recording (voice messages)
2. **Compose**: Frontend detects media type and sets `media_type`, `caption`, `media_metadata`, `primary_attachment_path_id`
3. **API Request**: `POST /api/v1/messages` includes media fields
4. **Backend Processing**:
   - `check_message()` validates media parameters
   - Converts `media_type` string to `MessageType` enum
   - Auto-detects type from attachment `content_type` if not specified
   - Generates backward-compatible Markdown `content` if empty
   - Sets `primary_attachment` ForeignKey after claiming attachment
5. **Storage**: Message saved with `type`, `caption`, `primary_attachment`, `media_metadata`
6. **Event**: Message event sent to clients with structured media data

#### Receiving Media Messages

1. **Event Queue**: Client receives message event via `/api/v1/register` event queue
2. **Client Capabilities**: Newer clients opt-in via `rich_media_message_types: true` capability
3. **Serialization**: `MessageDict.post_process_dicts()` includes:
   - `media_type`: String representation (e.g., "image", "voice_message")
   - `caption`: Caption text if present
   - `media_metadata`: Type-specific metadata object
   - `primary_attachment`: Full attachment object with `id`, `name`, `path_id`, `size`, `content_type`
4. **Rendering**: Frontend `media_message_card.ts` renders appropriate UI component
5. **Fallback**: Older clients see Markdown `content` field

### Media Type Detection

The `zerver/lib/media_type_detection.py` module provides:

- **`detect_media_type(mime_type: str | None) -> MessageType | None`**: Maps MIME types to `MessageType` enum values
- **`media_type_to_string(message_type: MessageType) -> str | None`**: Converts enum to API string representation
- **`string_to_media_type(media_type: str) -> MessageType | None`**: Converts API string to enum

### Media Metadata Structure

Each media type has a specific `media_metadata` structure:

#### Image (`IMAGE`)
```json
{
  "width": 1920,
  "height": 1080,
  "mime_type": "image/jpeg"
}
```

#### Video (`VIDEO`)
```json
{
  "width": 1920,
  "height": 1080,
  "duration_secs": 30,
  "mime_type": "video/mp4"
}
```

#### Audio (`AUDIO`)
```json
{
  "duration_secs": 120,
  "mime_type": "audio/mpeg"
}
```

#### Voice Message (`VOICE_MESSAGE`)
```json
{
  "duration_secs": 15,
  "mime_type": "audio/webm",
  "waveform": [0.1, 0.3, 0.7, 0.5, 0.2]
}
```

#### Location (`LOCATION`)
```json
{
  "latitude": 40.7128,
  "longitude": -74.0060,
  "name": "New York City",
  "address": "Manhattan, NY"
}
```

#### Contact (`CONTACT`)
```json
{
  "name": "Jane Doe",
  "phone": "+1234567890",
  "email": "jane@example.com"
}
```

#### Sticker (`STICKER`)
```json
{
  "pack_id": "pack1",
  "sticker_id": "sticker1"
}
```

#### Document (`DOCUMENT`)
```json
{
  "mime_type": "application/pdf",
  "page_count": 10  // Optional
}
```

## API Endpoints

### Send Message

**Endpoint**: `POST /api/v1/messages`

**New Parameters** (all optional):
- `media_type`: String enum ("image", "video", "audio", "document", "location", "contact", "sticker", "voice_message")
- `caption`: String for optional caption text
- `media_metadata`: JSON object with type-specific metadata
- `primary_attachment_path_id`: String path_id from upload response

**Response**: Standard message object with additional fields:
- `media_type`: String representation
- `caption`: Caption text
- `media_metadata`: Metadata object
- `primary_attachment`: Attachment object

### Event Queue Registration

**Endpoint**: `POST /api/v1/register`

**New Capability**:
- `rich_media_message_types`: Boolean to opt-in to receiving structured media data

When `rich_media_message_types: true`, message events include full `media_type`, `caption`, `media_metadata`, and `primary_attachment` fields. When `false` (or omitted), clients receive only the `content` field with Markdown fallback.

## Frontend Components

### Media Message Card Renderer

`web/src/media_message_card.ts` provides type-specific rendering functions:

- `renderImageCard(message)`: Image with optional caption
- `renderVideoCard(message)`: Video player with controls
- `renderAudioCard(message)`: Audio player with controls
- `renderVoiceCard(message)`: Voice message with waveform visualization
- `renderDocumentCard(message)`: Document download link
- `renderLocationCard(message)`: Location map/coordinates
- `renderContactCard(message)`: Contact card with name/phone/email
- `renderStickerCard(message)`: Sticker image

### Voice Recorder

`web/src/voice_recorder.ts` provides in-app voice recording:

- Uses `MediaRecorder` API with `audio/webm;codecs=opus` codec
- Records audio chunks and creates Blob on stop
- Uploads via `upload.ts` and sends as `VOICE_MESSAGE` type
- Includes waveform visualization support

### Location Picker

`web/src/location_picker.ts` provides location sharing:

- Uses browser `Geolocation` API for current location
- Sends location as `LOCATION` message type
- Future: Map picker UI (e.g., Leaflet.js)

### Contact Picker

`web/src/contact_picker.ts` provides contact sharing:

- Simple prompt-based UI (future: Contacts API integration)
- Sends contact as `CONTACT` message type

### Sticker Picker

`web/src/sticker_picker.ts` provides sticker selection:

- Stub implementation (future: sticker pack management UI)
- Sends sticker as `STICKER` message type

## Backward Compatibility

The system maintains full backward compatibility:

1. **Content Field**: Always populated with Markdown representation (e.g., `![caption](/user_uploads/...)` for images)
2. **Old Clients**: Ignore new fields and render `content` as before
3. **New Clients**: Opt-in via `rich_media_message_types` capability to receive structured data
4. **API**: New fields are optional and additive

## Mobile API Considerations

Mobile clients should:

1. **Opt-in**: Set `rich_media_message_types: true` in `/api/v1/register`
2. **Handle Both**: Support both structured fields and Markdown `content` fallback
3. **Bandwidth**: Use `primary_attachment` to download media only when needed
4. **Metadata**: Use `media_metadata` for UI rendering (thumbnails, duration, etc.)

## Testing

- **Backend**: `zerver/tests/test_media_message_types.py` - Comprehensive Django tests
- **Frontend**: `web/tests/media_message_card.test.cjs` - Rendering tests

## Migration

Migration `10009_add_rich_media_message_types.py`:

- Adds new enum values to `type` field
- Adds `caption`, `primary_attachment`, `media_metadata` fields
- Creates index on `type` field for performance
- Applies to both `Message` and `ArchivedMessage` tables

## Future Enhancements

See [Future Enhancements Documentation](../development/media-message-types-future-enhancements.md) for detailed implementation plans for:

- **Map picker UI** for location messages (interactive map with Leaflet.js/Mapbox)
- **Enhanced contact picker** with Contacts API integration
- **Sticker pack management system** with database models and admin UI
- Enhanced waveform visualization for voice messages
- Media preview/thumbnail generation
- Media compression/optimization
