"""Tests for rich media message types functionality."""

from zerver.actions.message_send import check_send_message
from zerver.lib.media_type_detection import (
    detect_media_type,
    media_type_to_string,
    string_to_media_type,
)
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Attachment, Message, UserProfile
from zerver.models.messages import AbstractMessage


class MediaTypeDetectionTest(ZulipTestCase):
    def test_detect_media_type_image(self) -> None:
        self.assertEqual(detect_media_type("image/jpeg"), Message.MessageType.IMAGE)
        self.assertEqual(detect_media_type("image/png"), Message.MessageType.IMAGE)
        self.assertEqual(detect_media_type("image/webp"), Message.MessageType.IMAGE)

    def test_detect_media_type_video(self) -> None:
        self.assertEqual(detect_media_type("video/mp4"), Message.MessageType.VIDEO)
        self.assertEqual(detect_media_type("video/webm"), Message.MessageType.VIDEO)

    def test_detect_media_type_audio(self) -> None:
        self.assertEqual(detect_media_type("audio/mpeg"), Message.MessageType.AUDIO)
        self.assertEqual(detect_media_type("audio/webm"), Message.MessageType.AUDIO)

    def test_detect_media_type_document(self) -> None:
        self.assertEqual(detect_media_type("application/pdf"), Message.MessageType.DOCUMENT)
        self.assertEqual(detect_media_type("text/plain"), Message.MessageType.DOCUMENT)

    def test_detect_media_type_none(self) -> None:
        self.assertIsNone(detect_media_type(None))
        self.assertIsNone(detect_media_type("unknown/type"))

    def test_media_type_to_string(self) -> None:
        self.assertEqual(media_type_to_string(Message.MessageType.IMAGE), "image")
        self.assertEqual(media_type_to_string(Message.MessageType.VIDEO), "video")
        self.assertEqual(media_type_to_string(Message.MessageType.AUDIO), "audio")
        self.assertEqual(media_type_to_string(Message.MessageType.VOICE_MESSAGE), "voice_message")
        self.assertIsNone(media_type_to_string(Message.MessageType.NORMAL))

    def test_string_to_media_type(self) -> None:
        self.assertEqual(string_to_media_type("image"), Message.MessageType.IMAGE)
        self.assertEqual(string_to_media_type("voice_message"), Message.MessageType.VOICE_MESSAGE)
        self.assertIsNone(string_to_media_type("invalid"))


class MediaMessageSendTest(ZulipTestCase):
    def test_send_image_message(self) -> None:
        """Test sending an image message with caption."""
        user = self.example_user("hamlet")
        self.login_user(user)

        # Create a test attachment
        attachment = Attachment.objects.create(
            file_name="test.jpg",
            path_id="1/ab/cdef/test.jpg",
            owner=user,
            realm=user.realm,
            size=1024,
            content_type="image/jpeg",
        )

        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": "Verona",
                "topic": "test",
                "content": "",
                "media_type": "image",
                "caption": "Test image caption",
                "primary_attachment_path_id": attachment.path_id,
                "media_metadata": {"width": 1920, "height": 1080, "mime_type": "image/jpeg"},
            },
        )

        self.assert_json_success(result)
        message_id = result.json()["id"]
        message = Message.objects.get(id=message_id)

        self.assertEqual(message.type, Message.MessageType.IMAGE)
        self.assertEqual(message.caption, "Test image caption")
        self.assertEqual(message.primary_attachment, attachment)
        self.assertIsNotNone(message.media_metadata)
        self.assertEqual(message.media_metadata["width"], 1920)
        # Content should still be populated for backward compatibility
        self.assertIn(attachment.path_id, message.content)

    def test_send_video_message(self) -> None:
        """Test sending a video message."""
        user = self.example_user("hamlet")
        self.login_user(user)

        attachment = Attachment.objects.create(
            file_name="test.mp4",
            path_id="1/ab/cdef/test.mp4",
            owner=user,
            realm=user.realm,
            size=2048,
            content_type="video/mp4",
        )

        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": "Verona",
                "topic": "test",
                "content": "",
                "media_type": "video",
                "caption": "Test video",
                "primary_attachment_path_id": attachment.path_id,
                "media_metadata": {
                    "width": 1920,
                    "height": 1080,
                    "duration_secs": 30,
                    "mime_type": "video/mp4",
                },
            },
        )

        self.assert_json_success(result)
        message = Message.objects.get(id=result.json()["id"])
        self.assertEqual(message.type, Message.MessageType.VIDEO)
        self.assertEqual(message.caption, "Test video")

    def test_send_voice_message(self) -> None:
        """Test sending a voice message with waveform data."""
        user = self.example_user("hamlet")
        self.login_user(user)

        attachment = Attachment.objects.create(
            file_name="voice.webm",
            path_id="1/ab/cdef/voice.webm",
            owner=user,
            realm=user.realm,
            size=512,
            content_type="audio/webm",
        )

        waveform = [0.1, 0.3, 0.7, 0.5, 0.2]
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": "Verona",
                "topic": "test",
                "content": "",
                "media_type": "voice_message",
                "primary_attachment_path_id": attachment.path_id,
                "media_metadata": {
                    "duration_secs": 15,
                    "mime_type": "audio/webm",
                    "waveform": waveform,
                },
            },
        )

        self.assert_json_success(result)
        message = Message.objects.get(id=result.json()["id"])
        self.assertEqual(message.type, Message.MessageType.VOICE_MESSAGE)
        self.assertEqual(message.media_metadata["waveform"], waveform)

    def test_send_location_message(self) -> None:
        """Test sending a location message (no attachment needed)."""
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
                "media_type": "location",
                "media_metadata": {
                    "latitude": 40.7128,
                    "longitude": -74.0060,
                    "name": "New York City",
                    "address": "Manhattan, NY",
                },
            },
        )

        self.assert_json_success(result)
        message = Message.objects.get(id=result.json()["id"])
        self.assertEqual(message.type, Message.MessageType.LOCATION)
        self.assertEqual(message.media_metadata["latitude"], 40.7128)
        self.assertIsNone(message.primary_attachment)

    def test_send_contact_message(self) -> None:
        """Test sending a contact message."""
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
                "media_type": "contact",
                "media_metadata": {
                    "name": "Jane Doe",
                    "phone": "+1234567890",
                    "email": "jane@example.com",
                },
            },
        )

        self.assert_json_success(result)
        message = Message.objects.get(id=result.json()["id"])
        self.assertEqual(message.type, Message.MessageType.CONTACT)
        self.assertEqual(message.media_metadata["name"], "Jane Doe")

    def test_auto_detect_media_type_from_attachment(self) -> None:
        """Test that media type is auto-detected from attachment content_type."""
        user = self.example_user("hamlet")
        self.login_user(user)

        attachment = Attachment.objects.create(
            file_name="photo.jpg",
            path_id="1/ab/cdef/photo.jpg",
            owner=user,
            realm=user.realm,
            size=1024,
            content_type="image/jpeg",
        )

        # Send without explicit media_type, but with primary_attachment_path_id
        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": "Verona",
                "topic": "test",
                "content": "",
                "primary_attachment_path_id": attachment.path_id,
            },
        )

        self.assert_json_success(result)
        message = Message.objects.get(id=result.json()["id"])
        # Should auto-detect as IMAGE from content_type
        self.assertEqual(message.type, Message.MessageType.IMAGE)

    def test_backward_compatibility_content_field(self) -> None:
        """Test that content field is always populated for backward compatibility."""
        user = self.example_user("hamlet")
        self.login_user(user)

        attachment = Attachment.objects.create(
            file_name="test.jpg",
            path_id="1/ab/cdef/test.jpg",
            owner=user,
            realm=user.realm,
            size=1024,
            content_type="image/jpeg",
        )

        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": "Verona",
                "topic": "test",
                "content": "",  # Empty content
                "media_type": "image",
                "primary_attachment_path_id": attachment.path_id,
            },
        )

        self.assert_json_success(result)
        message = Message.objects.get(id=result.json()["id"])
        # Content should be auto-generated markdown
        self.assertIn(attachment.path_id, message.content)
        self.assertIn("![", message.content)  # Image markdown syntax

    def test_message_fetch_includes_media_fields(self) -> None:
        """Test that GET /messages includes media_type, caption, media_metadata, primary_attachment."""
        user = self.example_user("hamlet")
        self.login_user(user)

        attachment = Attachment.objects.create(
            file_name="test.jpg",
            path_id="1/ab/cdef/test.jpg",
            owner=user,
            realm=user.realm,
            size=1024,
            content_type="image/jpeg",
        )

        result = self.api_post(
            user,
            "/api/v1/messages",
            {
                "type": "stream",
                "to": "Verona",
                "topic": "test",
                "content": "",
                "media_type": "image",
                "caption": "Test caption",
                "primary_attachment_path_id": attachment.path_id,
                "media_metadata": {"width": 1920, "height": 1080},
            },
        )

        message_id = result.json()["id"]

        # Fetch the message
        result = self.api_get(user, f"/api/v1/messages/{message_id}")
        self.assert_json_success(result)
        message_data = result.json()["message"]

        self.assertEqual(message_data["media_type"], "image")
        self.assertEqual(message_data["caption"], "Test caption")
        self.assertIsNotNone(message_data["media_metadata"])
        self.assertIsNotNone(message_data["primary_attachment"])
        self.assertEqual(message_data["primary_attachment"]["id"], attachment.id)
