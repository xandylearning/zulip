"""
Tests for placeholder email functionality in LMS integration.

These tests cover:
- Email utility functions
- User sync with placeholder emails
- Authentication with placeholder emails
- Notification handling for placeholder emails
"""

import unittest
from unittest.mock import patch, MagicMock, Mock
from django.test import TestCase, override_settings
from django.core.exceptions import ValidationError
from django.contrib.auth.models import AnonymousUser

from zerver.models import UserProfile, Realm, Message, Recipient
from zerver.lib.test_classes import ZulipTestCase

from lms_integration.lib.email_utils import (
    generate_placeholder_email,
    clean_username_for_email,
    is_placeholder_email,
    validate_and_prepare_email,
    update_email_if_changed,
    should_send_email_notification,
    should_show_inapp_notifications,
    should_log_notification_attempts,
    get_placeholder_email_stats,
    log_placeholder_email_attempt,
)

from lms_integration.lib.notifications import LMSNotificationHandler
from lms_integration.auth_backend import TestPressJWTAuthBackend
from lms_integration.lib.user_sync import UserSync
from lms_integration.models import Students, Mentors


class EmailUtilsTest(TestCase):
    """Test email utility functions."""

    def setUp(self):
        self.realm = Realm.objects.create(
            string_id="testlms",
            name="Test LMS Realm",
        )

    def test_generate_placeholder_email(self):
        """Test placeholder email generation."""
        # Basic generation
        email = generate_placeholder_email("john_doe")
        self.assertEqual(email, "john_doe@noemail.local")

        # With custom domain
        email = generate_placeholder_email("jane_smith", "students.school.edu")
        self.assertEqual(email, "jane_smith@students.school.edu")

        # With prefix/suffix settings
        with override_settings(
            LMS_PLACEHOLDER_EMAIL_PREFIX="student_",
            LMS_PLACEHOLDER_EMAIL_SUFFIX="_lms"
        ):
            email = generate_placeholder_email("bob_wilson")
            self.assertEqual(email, "student_bob_wilson_lms@noemail.local")

    def test_clean_username_for_email(self):
        """Test username cleaning for email compatibility."""
        # Normal username
        self.assertEqual(clean_username_for_email("john_doe"), "john_doe")

        # Username with special characters
        self.assertEqual(clean_username_for_email("user@#$%"), "user____")

        # Username with dots at start/end
        self.assertEqual(clean_username_for_email(".user."), "user")

        # Long username
        long_username = "a" * 70
        cleaned = clean_username_for_email(long_username)
        self.assertLessEqual(len(cleaned), 64)

        # Empty username
        self.assertEqual(clean_username_for_email(""), "user")

    def test_is_placeholder_email(self):
        """Test placeholder email detection."""
        # Placeholder emails
        self.assertTrue(is_placeholder_email("john@noemail.local"))
        self.assertTrue(is_placeholder_email("jane@students.school.edu", "students.school.edu"))

        # Real emails
        self.assertFalse(is_placeholder_email("john@school.edu"))
        self.assertFalse(is_placeholder_email("jane@gmail.com"))

    @patch('lms_integration.lib.email_utils.settings')
    def test_validate_and_prepare_email(self, mock_settings):
        """Test email validation and preparation."""
        mock_settings.LMS_NO_EMAIL_DOMAIN = "test.local"

        # Valid email
        email, is_placeholder = validate_and_prepare_email("user@school.edu", "username", self.realm)
        self.assertEqual(email, "user@school.edu")
        self.assertFalse(is_placeholder)

        # No email provided
        email, is_placeholder = validate_and_prepare_email(None, "username", self.realm)
        self.assertEqual(email, "username@test.local")
        self.assertTrue(is_placeholder)

        # Empty email
        email, is_placeholder = validate_and_prepare_email("", "username", self.realm)
        self.assertEqual(email, "username@test.local")
        self.assertTrue(is_placeholder)

        # Invalid email format
        email, is_placeholder = validate_and_prepare_email("invalid-email", "username", self.realm)
        self.assertEqual(email, "username@test.local")
        self.assertTrue(is_placeholder)

    @patch('lms_integration.lib.email_utils.settings')
    def test_validate_and_prepare_email_disposable_uses_placeholder(self, mock_settings):
        """Disposable or disallowed emails should be replaced with placeholders, not raise errors."""
        mock_settings.LMS_NO_EMAIL_DOMAIN = "test.local"

        # Configure realm to disallow disposable email addresses
        self.realm.disallow_disposable_email_addresses = True
        self.realm.save(update_fields=["disallow_disposable_email_addresses"])

        # Use a well-known disposable email domain; validation should fall back to placeholder
        disposable_email = "user@mailinator.com"

        email, is_placeholder = validate_and_prepare_email(disposable_email, "username", self.realm)

        self.assertTrue(is_placeholder)
        self.assertNotEqual(email, disposable_email)
        self.assertTrue(email.endswith("@test.local"))

    def test_get_placeholder_email_stats(self):
        """Test placeholder email statistics."""
        # Create test users
        user1 = UserProfile.objects.create(
            realm=self.realm,
            email="real@school.edu",
            delivery_email="real@school.edu",
            full_name="Real User",
        )

        user2 = UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Placeholder User",
        )

        stats = get_placeholder_email_stats(self.realm)

        self.assertEqual(stats['total_users'], 2)
        self.assertEqual(stats['placeholder_users'], 1)
        self.assertEqual(stats['real_email_users'], 1)
        self.assertEqual(stats['placeholder_percentage'], 50.0)

    def test_should_send_email_notification(self):
        """Test email notification decision logic."""
        # User with real email
        real_user = UserProfile.objects.create(
            realm=self.realm,
            email="real@school.edu",
            delivery_email="real@school.edu",
            full_name="Real User",
        )

        # User with placeholder email
        placeholder_user = UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Placeholder User",
        )

        # Should send to real email user
        self.assertTrue(should_send_email_notification(real_user))

        # Should not send to placeholder email user by default
        self.assertFalse(should_send_email_notification(placeholder_user))

    def test_should_show_inapp_notifications(self):
        """Test in-app notification decision logic."""
        # User with placeholder email
        placeholder_user = UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Placeholder User",
        )

        # Should show in-app notifications by default
        self.assertTrue(should_show_inapp_notifications(placeholder_user))

    def test_update_email_if_changed(self):
        """Test email update functionality."""
        user = UserProfile.objects.create(
            realm=self.realm,
            email="old@noemail.local",
            delivery_email="old@noemail.local",
            full_name="Test User",
        )

        # Update to real email
        updated = update_email_if_changed(user, "new@school.edu", "username")
        self.assertTrue(updated)
        user.refresh_from_db()
        self.assertEqual(user.delivery_email, "new@school.edu")
        self.assertEqual(user.email, "new@school.edu")

        # No change needed
        updated = update_email_if_changed(user, "new@school.edu", "username")
        self.assertFalse(updated)

    def test_log_placeholder_email_attempt(self):
        """Test placeholder email attempt logging."""
        user = UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Test User",
        )

        # Should not raise any exceptions
        with patch('lms_integration.lib.email_utils.logger') as mock_logger:
            log_placeholder_email_attempt(user, "test_operation", "test details")
            mock_logger.info.assert_called_once()


class AuthenticationBackendTest(ZulipTestCase):
    """Test authentication backend with placeholder emails."""

    def setUp(self):
        super().setUp()
        self.realm = self.example_realm("testlms")
        self.backend = TestPressJWTAuthBackend()

    @patch('lms_integration.auth_backend.testpress_jwt_validator.validate_token')
    def test_authenticate_with_email(self, mock_validate):
        """Test authentication with real email."""
        mock_validate.return_value = {
            'email': 'user@school.edu',
            'username': 'test_user',
            'first_name': 'Test',
            'last_name': 'User',
            'is_active': True,
            'id': 123
        }

        user = self.backend.authenticate(
            request=None,
            testpress_jwt_token="valid_token",
            realm=self.realm
        )

        self.assertIsNotNone(user)
        self.assertEqual(user.delivery_email, 'user@school.edu')

    @patch('lms_integration.auth_backend.testpress_jwt_validator.validate_token')
    def test_authenticate_without_email(self, mock_validate):
        """Test authentication without email (should generate placeholder)."""
        mock_validate.return_value = {
            'email': None,
            'username': 'test_user',
            'first_name': 'Test',
            'last_name': 'User',
            'is_active': True,
            'id': 123
        }

        user = self.backend.authenticate(
            request=None,
            testpress_jwt_token="valid_token",
            realm=self.realm
        )

        self.assertIsNotNone(user)
        self.assertTrue(is_placeholder_email(user.delivery_email))
        self.assertTrue(user.delivery_email.startswith('test_user@'))

    @patch('lms_integration.auth_backend.testpress_jwt_validator.validate_token')
    def test_authenticate_username_only(self, mock_validate):
        """Test authentication with only username."""
        mock_validate.return_value = {
            'username': 'student123',
            'first_name': 'Student',
            'last_name': 'Test',
            'is_active': True,
            'id': 456
        }

        user = self.backend.authenticate(
            request=None,
            testpress_jwt_token="valid_token",
            realm=self.realm
        )

        self.assertIsNotNone(user)
        self.assertTrue(is_placeholder_email(user.delivery_email))
        self.assertIn('student123', user.delivery_email)

    @patch('lms_integration.auth_backend.testpress_jwt_validator.validate_token')
    def test_authenticate_no_email_no_username(self, mock_validate):
        """Test authentication without email or username (should fail)."""
        mock_validate.return_value = {
            'first_name': 'Test',
            'last_name': 'User',
            'is_active': True,
            'id': 789
        }

        user = self.backend.authenticate(
            request=None,
            testpress_jwt_token="valid_token",
            realm=self.realm,
            return_data={}
        )

        self.assertIsNone(user)


class UserSyncTest(ZulipTestCase):
    """Test user sync with placeholder emails."""

    def setUp(self):
        super().setUp()
        self.realm = self.example_realm("testlms")

    @patch('lms_integration.lib.user_sync.Students.objects')
    def test_sync_student_without_email(self, mock_students):
        """Test syncing student without email."""
        mock_student = Mock()
        mock_student.id = 1
        mock_student.username = "student1"
        mock_student.email = None
        mock_student.first_name = "Test"
        mock_student.last_name = "Student"
        mock_student.display_name = None
        mock_student.is_active = True

        user_sync = UserSync(realm=self.realm)

        # Mock the database lookup to return no existing user
        with patch('lms_integration.lib.user_sync.UserProfile.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None

            # Mock user creation
            with patch('lms_integration.lib.user_sync.do_create_user') as mock_create:
                mock_user = Mock()
                mock_user.email = "student1@noemail.local"
                mock_create.return_value = mock_user

                created, user, message = user_sync.sync_student(mock_student)

                self.assertTrue(created)
                self.assertIsNotNone(user)
                # Check that do_create_user was called with placeholder email
                args, kwargs = mock_create.call_args
                self.assertTrue(is_placeholder_email(kwargs['email']))

    @patch('lms_integration.lib.user_sync.Mentors.objects')
    def test_sync_mentor_without_email(self, mock_mentors):
        """Test syncing mentor without email."""
        mock_mentor = Mock()
        mock_mentor.user_id = 1
        mock_mentor.username = "mentor1"
        mock_mentor.email = None
        mock_mentor.first_name = "Test"
        mock_mentor.last_name = "Mentor"
        mock_mentor.display_name = None

        user_sync = UserSync(realm=self.realm)

        # Mock the database lookup to return no existing user
        with patch('lms_integration.lib.user_sync.UserProfile.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = None

            # Mock user creation
            with patch('lms_integration.lib.user_sync.do_create_user') as mock_create:
                mock_user = Mock()
                mock_user.email = "mentor1@noemail.local"
                mock_create.return_value = mock_user

                created, user, message = user_sync.sync_mentor(mock_mentor)

                self.assertTrue(created)
                self.assertIsNotNone(user)
                # Check that do_create_user was called with placeholder email
                args, kwargs = mock_create.call_args
                self.assertTrue(is_placeholder_email(kwargs['email']))

    def test_sync_student_email_update(self):
        """Test updating student from placeholder to real email."""
        # Create user with placeholder email
        placeholder_user = UserProfile.objects.create(
            realm=self.realm,
            email="student1@noemail.local",
            delivery_email="student1@noemail.local",
            full_name="Test Student",
        )

        mock_student = Mock()
        mock_student.id = 1
        mock_student.username = "student1"
        mock_student.email = "student1@school.edu"  # Now has real email
        mock_student.first_name = "Test"
        mock_student.last_name = "Student"
        mock_student.display_name = None
        mock_student.is_active = True

        user_sync = UserSync(realm=self.realm)

        # Mock the database lookup to return existing user
        with patch('lms_integration.lib.user_sync.UserProfile.objects.filter') as mock_filter:
            mock_filter.return_value.first.return_value = placeholder_user

            # Enable auto-update
            with override_settings(LMS_AUTO_UPDATE_EMAILS=True):
                created, user, message = user_sync.sync_student(mock_student)

                self.assertFalse(created)  # Existing user
                self.assertIsNotNone(user)

                # Check that email was updated
                placeholder_user.refresh_from_db()
                self.assertEqual(placeholder_user.delivery_email, "student1@school.edu")


class NotificationHandlerTest(ZulipTestCase):
    """Test notification handling for placeholder emails."""

    def setUp(self):
        super().setUp()
        self.realm = self.example_realm("testlms")

    def test_send_email_notification_real_email(self):
        """Test sending email notification to user with real email."""
        user = UserProfile.objects.create(
            realm=self.realm,
            email="real@school.edu",
            delivery_email="real@school.edu",
            full_name="Real User",
        )

        # Mock the actual email sending
        with patch('lms_integration.lib.notifications.queue_json_publish') as mock_queue:
            result = LMSNotificationHandler.send_email_notification(
                user, "test", {"message": "test"}
            )

            self.assertTrue(result)
            mock_queue.assert_called_once()

    def test_send_email_notification_placeholder_email(self):
        """Test blocking email notification to user with placeholder email."""
        user = UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Placeholder User",
        )

        # Should be blocked
        with patch('lms_integration.lib.notifications.queue_json_publish') as mock_queue:
            result = LMSNotificationHandler.send_email_notification(
                user, "test", {"message": "test"}
            )

            self.assertFalse(result)
            mock_queue.assert_not_called()

    def test_send_message_notification(self):
        """Test message notification handling."""
        placeholder_user = UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Placeholder User",
        )

        # Create a mock message
        mock_message = Mock()
        mock_message.id = 1

        with patch('lms_integration.lib.notifications.send_email_notifications_to_user') as mock_send:
            result = LMSNotificationHandler.send_message_notification(
                placeholder_user, mock_message
            )

            # Email should be blocked, but in-app should work
            self.assertFalse(result["email_sent"])
            self.assertTrue(result["in_app_shown"])
            self.assertTrue(result["push_sent"])
            mock_send.assert_not_called()

    def test_bulk_send_notifications(self):
        """Test bulk notification sending with mixed user types."""
        real_user = UserProfile.objects.create(
            realm=self.realm,
            email="real@school.edu",
            delivery_email="real@school.edu",
            full_name="Real User",
        )

        placeholder_user = UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Placeholder User",
        )

        users = [real_user, placeholder_user]

        with patch('lms_integration.lib.notifications.LMSNotificationHandler.send_email_notification') as mock_send:
            mock_send.side_effect = [True, False]  # Real user succeeds, placeholder blocked

            stats = LMSNotificationHandler.bulk_send_notifications(
                users, "test", {"message": "test"}
            )

            self.assertEqual(stats["sent"], 1)
            self.assertEqual(stats["blocked"], 1)
            self.assertEqual(stats["failed"], 0)

    def test_get_notification_stats(self):
        """Test notification statistics."""
        # Create mixed users
        UserProfile.objects.create(
            realm=self.realm,
            email="real1@school.edu",
            delivery_email="real1@school.edu",
            full_name="Real User 1",
        )

        UserProfile.objects.create(
            realm=self.realm,
            email="real2@school.edu",
            delivery_email="real2@school.edu",
            full_name="Real User 2",
        )

        UserProfile.objects.create(
            realm=self.realm,
            email="placeholder@noemail.local",
            delivery_email="placeholder@noemail.local",
            full_name="Placeholder User",
        )

        stats = LMSNotificationHandler.get_notification_stats(self.realm)

        self.assertEqual(stats["total_users"], 3)
        self.assertEqual(stats["users_with_email_notifications"], 2)
        self.assertEqual(stats["users_without_email_notifications"], 1)
        self.assertAlmostEqual(stats["email_notification_coverage"], 66.7, places=1)


class ManagementCommandTest(TestCase):
    """Test management command functionality."""

    def setUp(self):
        self.realm = Realm.objects.create(
            string_id="testlms",
            name="Test LMS Realm",
        )

    def test_command_import(self):
        """Test that management command can be imported."""
        from lms_integration.management.commands.manage_placeholder_emails import Command
        self.assertIsNotNone(Command)

    @patch('lms_integration.management.commands.manage_placeholder_emails.get_placeholder_email_stats')
    def test_report_action(self, mock_stats):
        """Test report generation."""
        from lms_integration.management.commands.manage_placeholder_emails import Command

        mock_stats.return_value = {
            'total_users': 10,
            'placeholder_users': 3,
            'real_email_users': 7,
            'placeholder_percentage': 30.0
        }

        command = Command()
        command.realm = self.realm

        # Test text format (shouldn't raise exceptions)
        try:
            command.handle_report({'format': 'text'})
        except SystemExit:
            pass  # Management commands often call sys.exit

        # Test JSON format
        try:
            command.handle_report({'format': 'json'})
        except SystemExit:
            pass

        mock_stats.assert_called_with(self.realm)


if __name__ == '__main__':
    unittest.main()