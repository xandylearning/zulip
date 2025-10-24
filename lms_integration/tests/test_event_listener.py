"""
Tests for LMS Event Listener
"""

from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone

from lms_integration.models import LMSActivityEvent, LMSEventLog
from lms_integration.event_listeners import LMSActivityEventHandler


class LMSActivityEventHandlerTestCase(TestCase):
    """Test cases for LMSActivityEventHandler class."""
    
    def setUp(self):
        """Set up test data."""
        self.handler = LMSActivityEventHandler()
    
    def test_get_event_stats(self):
        """Test getting event statistics."""
        # Create some test events
        event1 = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            activity_id=1,
            timestamp=timezone.now(),
            processed_for_ai=True
        )
        
        event2 = LMSActivityEvent.objects.create(
            event_type='exam_completed',
            student_id=2,
            activity_id=2,
            timestamp=timezone.now(),
            processed_for_ai=False
        )
        
        # Create event logs
        LMSEventLog.objects.create(
            event=event1,
            notification_sent=True
        )
        
        LMSEventLog.objects.create(
            event=event2,
            notification_sent=False,
            error_message="Test error"
        )
        
        stats = self.handler.get_event_stats()
        
        self.assertEqual(stats['total_events'], 2)
        self.assertEqual(stats['processed_events'], 1)
        self.assertEqual(stats['pending_events'], 1)
        self.assertEqual(stats['events_with_notifications'], 1)
        self.assertEqual(stats['events_with_errors'], 1)
    
    def test_process_pending_events(self):
        """Test processing pending events."""
        # Create a pending event
        event = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            activity_id=1,
            timestamp=timezone.now(),
            processed_for_ai=False
        )
        
        # Mock the notification sending
        with patch.object(self.handler, '_send_notification'):
            processed_count = self.handler.process_pending_events()
            
            self.assertEqual(processed_count, 1)
            
            # Check that event was marked as processed
            event.refresh_from_db()
            self.assertTrue(event.processed_for_ai)
    
    def test_handle_event_with_valid_data(self):
        """Test handling event with valid data."""
        # Create an event
        event = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            activity_id=1,
            timestamp=timezone.now(),
            processed_for_ai=False
        )
        
        event_data = {'event_id': event.event_id}
        
        # Mock the processing
        with patch.object(self.handler, '_process_event'):
            self.handler.handle_event(event_data)
    
    def test_handle_event_with_invalid_data(self):
        """Test handling event with invalid data."""
        # Test with missing event_id
        event_data = {}
        
        # Should not raise an exception
        self.handler.handle_event(event_data)
        
        # Test with non-existent event_id
        event_data = {'event_id': 99999}
        
        # Should not raise an exception
        self.handler.handle_event(event_data)
    
    def test_get_notification_recipients_with_mentor(self):
        """Test getting notification recipients when mentor is available."""
        # Create an event with mentor information
        event = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            mentor_id=1,
            mentor_username='test_mentor',
            activity_id=1,
            timestamp=timezone.now()
        )
        
        # Mock the user mapper
        mock_user = Mock()
        mock_user.email = 'mentor@example.com'
        
        with patch.object(self.handler.user_mapper, 'get_zulip_user_for_mentor', return_value=mock_user):
            recipients = self.handler._get_notification_recipients(event)
            
            self.assertEqual(len(recipients), 1)
            self.assertEqual(recipients[0], mock_user)
    
    def test_get_notification_recipients_without_mentor(self):
        """Test getting notification recipients when no mentor is available."""
        # Create an event without mentor information
        event = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            mentor_id=None,
            mentor_username=None,
            activity_id=1,
            timestamp=timezone.now()
        )
        
        # Mock the user mapper to return no recipients
        with patch.object(self.handler.user_mapper, 'get_notification_recipients', return_value=[]):
            recipients = self.handler._get_notification_recipients(event)
            
            self.assertEqual(len(recipients), 0)
    
    def test_send_notification_success(self):
        """Test successful notification sending."""
        # Create an event
        event = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            activity_id=1,
            timestamp=timezone.now()
        )
        
        # Create event log
        event_log = LMSEventLog.objects.create(event=event)
        
        # Mock recipient
        mock_recipient = Mock()
        mock_recipient.email = 'mentor@example.com'
        mock_recipient.realm = Mock()
        
        # Mock the internal_send_private_message function
        with patch('lms_integration.event_listeners.internal_send_private_message', return_value=12345):
            with patch.object(self.handler, '_get_notification_recipients', return_value=[mock_recipient]):
                self.handler._send_notification(event, event_log)
                
                # Check that event log was updated
                event_log.refresh_from_db()
                self.assertTrue(event_log.notification_sent)
                self.assertEqual(event_log.notification_message_id, 12345)
    
    def test_send_notification_no_recipients(self):
        """Test notification sending when no recipients are available."""
        # Create an event
        event = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            activity_id=1,
            timestamp=timezone.now()
        )
        
        # Create event log
        event_log = LMSEventLog.objects.create(event=event)
        
        # Mock no recipients
        with patch.object(self.handler, '_get_notification_recipients', return_value=[]):
            self.handler._send_notification(event, event_log)
            
            # Check that error was logged
            event_log.refresh_from_db()
            self.assertFalse(event_log.notification_sent)
            self.assertIn('No notification recipients found', event_log.error_message)
    
    def test_send_notification_error(self):
        """Test notification sending with error."""
        # Create an event
        event = LMSActivityEvent.objects.create(
            event_type='exam_started',
            student_id=1,
            activity_id=1,
            timestamp=timezone.now()
        )
        
        # Create event log
        event_log = LMSEventLog.objects.create(event=event)
        
        # Mock recipient
        mock_recipient = Mock()
        mock_recipient.email = 'mentor@example.com'
        mock_recipient.realm = Mock()
        
        # Mock the internal_send_private_message function to raise an exception
        with patch('lms_integration.event_listeners.internal_send_private_message', side_effect=Exception("Test error")):
            with patch.object(self.handler, '_get_notification_recipients', return_value=[mock_recipient]):
                self.handler._send_notification(event, event_log)
                
                # Check that error was logged
                event_log.refresh_from_db()
                self.assertFalse(event_log.notification_sent)
                self.assertIn('Test error', event_log.error_message)
