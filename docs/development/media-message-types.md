# Media Message Types - Developer Guide

This guide explains how to extend and work with Zulip's rich media message types system.

## Adding a New Media Type

### 1. Database Schema

Add the new enum value to `MessageType` in `zerver/models/messages.py`:

```python
class MessageType(models.IntegerChoices):
    # ... existing types ...
    NEW_TYPE = 11
```

Update migration to include the new enum value.

### 2. Media Type Detection

Add MIME type mapping in `zerver/lib/media_type_detection.py`:

```python
def detect_media_type(mime_type: str | None) -> MessageType | None:
    if mime_type is None:
        return None
    mime_lower = mime_type.lower()
    # ... existing mappings ...
    if mime_lower.startswith("application/x-new-type"):
        return Message.MessageType.NEW_TYPE
    return None
```

Add string conversion functions:

```python
def media_type_to_string(message_type: MessageType) -> str | None:
    # ... existing mappings ...
    if message_type == Message.MessageType.NEW_TYPE:
        return "new_type"
    return None

def string_to_media_type(media_type: str) -> MessageType | None:
    # ... existing mappings ...
    if media_type == "new_type":
        return Message.MessageType.NEW_TYPE
    return None
```

### 3. API Schema

Update `zerver/openapi/zulip.yaml`:

- Add `"new_type"` to `media_type` enum in `POST /api/v1/messages` request
- Document expected `media_metadata` structure for the new type
- Add example in OpenAPI spec

### 4. Frontend TypeScript Types

Update `web/src/server_message.ts`:

```typescript
const server_message_schema = z.object({
    // ... existing fields ...
    media_type: z.enum([
        // ... existing types ...
        "new_type",
    ]).optional(),
});
```

### 5. Frontend Rendering

Add renderer in `web/src/media_message_card.ts`:

```typescript
export function renderNewTypeCard(message: Message): string {
    const metadata = message.media_metadata;
    // Build HTML for new type
    return `
        <div class="media-new-type-card">
            <!-- Render UI -->
        </div>
        ${getCaptionHtml(message.caption)}
    `;
}

export function renderMediaCard(message: Message): string {
    switch (message.media_type) {
        // ... existing cases ...
        case "new_type":
            return renderNewTypeCard(message);
        default:
            return "";
    }
}
```

Add CSS in `web/styles/media_message_card.css`:

```css
.media-new-type-card {
    /* Styles for new type */
}
```

### 6. Backend Tests

Add tests in `zerver/tests/test_media_message_types.py`:

```python
def test_send_new_type_message(self) -> None:
    """Test sending a new type message."""
    user = self.example_user("hamlet")
    self.login_user(user)
    
    result = self.api_post(
        user,
        "/api/v1/messages",
        {
            "type": "stream",
            "to": "Verona",
            "topic": "test",
            "content": "",
            "media_type": "new_type",
            "media_metadata": {
                # Type-specific metadata
            },
        },
    )
    
    self.assert_json_success(result)
    message = Message.objects.get(id=result.json()["id"])
    self.assertEqual(message.type, Message.MessageType.NEW_TYPE)
```

### 7. Frontend Tests

Add tests in `web/tests/media_message_card.test.cjs`:

```javascript
test("render_new_type_card", () => {
    const message = {
        id: 1,
        media_type: "new_type",
        media_metadata: {
            // Test metadata
        },
    };
    
    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-new-type-card"));
});
```

## Media Metadata Best Practices

### Required vs Optional Fields

- **Required**: Fields essential for rendering (e.g., `latitude`/`longitude` for location)
- **Optional**: Fields that enhance UX but aren't critical (e.g., `address` for location)

### Naming Conventions

- Use snake_case for JSON keys
- Use descriptive names (e.g., `duration_secs` not `dur`)
- Include units in names when ambiguous (e.g., `duration_secs` not `duration`)

### Type-Specific Guidelines

#### Images/Videos
- Always include `width` and `height` in pixels
- Include `mime_type` for proper rendering
- Optional: `thumbnail_url` for previews

#### Audio/Voice
- Always include `duration_secs`
- Voice messages: Include `waveform` array (normalized 0-1 values)
- Include `mime_type` for codec information

#### Location
- Always include `latitude` and `longitude` (decimal degrees)
- Optional: `name` (human-readable location name)
- Optional: `address` (street address)

#### Contact
- Always include `name`
- At least one of `phone` or `email` required
- Optional: `avatar_url`

#### Sticker
- Always include `pack_id` and `sticker_id`
- Attachment provides the image file

## Backend Processing Patterns

### Auto-Detection

When `media_type` is not provided but `primary_attachment_path_id` is:

```python
if message.type == Message.MessageType.NORMAL and primary_attachment:
    detected_type = detect_media_type(primary_attachment.content_type)
    if detected_type:
        message.type = detected_type
```

### Backward-Compatible Content Generation

Always generate Markdown `content` for old clients:

```python
if not content and media_type and primary_attachment_path_id:
    if media_type == Message.MessageType.IMAGE:
        content = f"![{caption or ''}](/user_uploads/{primary_attachment_path_id})"
    elif media_type == Message.MessageType.VIDEO:
        content = f"[{caption or 'Video'}](/user_uploads/{primary_attachment_path_id})"
    # ... other types
```

### Metadata Validation

Validate required fields per type:

```python
if media_type == Message.MessageType.LOCATION:
    if "latitude" not in media_metadata or "longitude" not in media_metadata:
        raise JsonableError("Location messages require latitude and longitude")
```

## Frontend Integration Patterns

### Compose Box Integration

Update `web/src/upload.ts` to detect and set media type:

```typescript
function guess_media_type_from_mime(mime_type: string): string | null {
    if (mime_type.startsWith("image/")) return "image";
    if (mime_type.startsWith("video/")) return "video";
    // ... other types
    return null;
}

// In upload-success handler
const media_type = guess_media_type_from_mime(file.type);
if (media_type) {
    compose_media_state.primary_attachment_path_id = path_id;
    compose_media_state.media_type = media_type;
    compose_media_state.media_metadata = {};
}
```

### Message Rendering

In `web/src/message_list_view.ts`:

```typescript
if (message.media_type) {
    const media_html = media_message_card.renderMediaCard(message);
    // Insert media_html into message DOM
} else {
    // Render standard Markdown content
}
```

### Local Echo

Update `web/src/echo.ts` to include media fields:

```typescript
interface LocalMessage {
    // ... existing fields ...
    media_type?: string;
    caption?: string | null;
    media_metadata?: Record<string, unknown>;
    primary_attachment_path_id?: string;
}
```

## Performance Considerations

### Database Indexes

The migration creates an index on `type` for efficient filtering:

```python
migrations.AddIndex(
    model_name="message",
    index=models.Index(fields=["type"], name="zerver_message_type_idx"),
)
```

### Caching

`MessageDict` caching includes media fields, so repeated fetches are fast.

### Bandwidth Optimization

Mobile clients can:

1. Check `media_metadata` before downloading attachments
2. Use thumbnail URLs if available
3. Lazy-load media on scroll

## Security Considerations

### Attachment Validation

- Verify `primary_attachment_path_id` belongs to the user's realm
- Check file size limits per media type
- Validate MIME types match declared `media_type`

### Metadata Sanitization

- Sanitize user-provided metadata (e.g., location names, contact info)
- Limit JSON size to prevent DoS
- Validate numeric ranges (e.g., latitude: -90 to 90)

### Privacy

- Location messages: Consider privacy implications
- Contact messages: Respect user privacy preferences
- Voice messages: Consider transcription/privacy policies

## Debugging

### Common Issues

1. **Media type not detected**: Check MIME type mapping in `media_type_detection.py`
2. **Missing attachment**: Verify `primary_attachment_path_id` is claimed before setting ForeignKey
3. **Old clients break**: Ensure `content` field is always populated
4. **Rendering fails**: Check `media_message_card.ts` handles all enum values

### Logging

Add debug logging in `check_message()`:

```python
if media_type:
    logger.debug(
        "Processing media message",
        extra={
            "media_type": media_type,
            "has_attachment": bool(primary_attachment_path_id),
            "has_metadata": bool(media_metadata),
        },
    )
```

## References

- [Subsystem Documentation](../subsystems/media-message-types.md)
- [Future Enhancements](media-message-types-future-enhancements.md) - Planned extensions (map UI, contact picker, sticker system)
- [API Documentation](../../zerver/openapi/zulip.yaml)
- [Backend Tests](../../zerver/tests/test_media_message_types.py)
- [Frontend Tests](../../web/tests/media_message_card.test.cjs)
