"""Media type detection utilities for rich media message types.

This module provides functions to detect and map media types from MIME types
to Zulip's MessageType enum values.
"""

from zerver.models.messages import Message


# MIME type sets for different media categories
IMAGE_MIME_TYPES = {
    "image/apng",
    "image/avif",
    "image/gif",
    "image/heic",
    "image/heif",
    "image/jpeg",
    "image/png",
    "image/tiff",
    "image/webp",
}

VIDEO_MIME_TYPES = {
    "video/mp4",
    "video/webm",
    "video/quicktime",  # .mov files
    "video/x-msvideo",  # .avi files
}

AUDIO_MIME_TYPES = {
    "audio/aac",
    "audio/flac",
    "audio/mp4",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
    "audio/x-m4a",
}


def detect_media_type(content_type: str | None) -> int | None:
    """Map MIME content_type to MessageType enum value.

    Args:
        content_type: MIME type string (e.g., "image/jpeg", "video/mp4")

    Returns:
        MessageType enum value (e.g., Message.MessageType.IMAGE) or None
        if the content type doesn't match any known media type.
    """
    if not content_type:
        return None

    # Normalize content_type (remove charset, etc.)
    normalized_type = content_type.split(";")[0].strip().lower()

    if normalized_type in IMAGE_MIME_TYPES:
        return Message.MessageType.IMAGE
    elif normalized_type in VIDEO_MIME_TYPES:
        return Message.MessageType.VIDEO
    elif normalized_type in AUDIO_MIME_TYPES:
        return Message.MessageType.AUDIO
    else:
        # Everything else is treated as a document
        # This includes PDFs, Office docs, text files, etc.
        return Message.MessageType.DOCUMENT


def media_type_to_string(media_type: int) -> str | None:
    """Convert MessageType enum value to string representation for API.

    Args:
        media_type: MessageType enum value

    Returns:
        String representation (e.g., "image", "video") or None for NORMAL type
    """
    mapping = {
        Message.MessageType.NORMAL: None,
        Message.MessageType.RESOLVE_TOPIC_NOTIFICATION: None,
        Message.MessageType.IMAGE: "image",
        Message.MessageType.VIDEO: "video",
        Message.MessageType.AUDIO: "audio",
        Message.MessageType.DOCUMENT: "document",
        Message.MessageType.LOCATION: "location",
        Message.MessageType.CONTACT: "contact",
        Message.MessageType.STICKER: "sticker",
        Message.MessageType.VOICE_MESSAGE: "voice_message",
    }
    return mapping.get(media_type)


def string_to_media_type(media_type_str: str) -> int | None:
    """Convert string representation to MessageType enum value.

    Args:
        media_type_str: String representation (e.g., "image", "video")

    Returns:
        MessageType enum value or None if invalid
    """
    mapping = {
        "text": Message.MessageType.NORMAL,
        "image": Message.MessageType.IMAGE,
        "video": Message.MessageType.VIDEO,
        "audio": Message.MessageType.AUDIO,
        "document": Message.MessageType.DOCUMENT,
        "location": Message.MessageType.LOCATION,
        "contact": Message.MessageType.CONTACT,
        "sticker": Message.MessageType.STICKER,
        "voice_message": Message.MessageType.VOICE_MESSAGE,
    }
    return mapping.get(media_type_str)
