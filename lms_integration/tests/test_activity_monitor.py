"""
Tests for LMS Activity Monitor
"""

from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from django.test import TestCase
from django.utils import timezone

from lms_integration.lib.activity_monitor import ActivityMonitor
from lms_integration.models import LMSActivityEvent, Attempts, ContentAttempts


class ActivityMonitorTestCase(TestCase):
    """Test cases for ActivityMonitor class."""
    
    def setUp(self):
        """Set up test data."""
        self.monitor = ActivityMonitor(poll_interval=60)
        self.monitor.last_poll_time = timezone.now() - timedelta(minutes=10)
    
    def test_determine_exam_event_type_started(self):
        """Test exam event type determination for started exams."""
        # Mock attempt with started state
        attempt = Mock()
        attempt.state = 'started'
        attempt.result = None
        
        event_type = self.monitor._determine_exam_event_type(attempt)
        self.assertEqual(event_type, 'exam_started')
    
    def test_determine_exam_event_type_completed_passed(self):
        """Test exam event type determination for completed passed exams."""
        # Mock attempt with completed state and pass result
        attempt = Mock()
        attempt.state = 'completed'
        attempt.result = 'pass'
        
        event_type = self.monitor._determine_exam_event_type(attempt)
        self.assertEqual(event_type, 'exam_passed')
    
    def test_determine_exam_event_type_completed_failed(self):
        """Test exam event type determination for completed failed exams."""
        # Mock attempt with completed state and fail result
        attempt = Mock()
        attempt.state = 'completed'
        attempt.result = 'fail'
        
        event_type = self.monitor._determine_exam_event_type(attempt)
        self.assertEqual(event_type, 'exam_failed')
    
    def test_determine_content_event_type_started(self):
        """Test content event type determination for started content."""
        # Mock content attempt with started state
        content_attempt = Mock()
        content_attempt.state = 'started'
        
        event_type = self.monitor._determine_content_event_type(content_attempt)
        self.assertEqual(event_type, 'content_started')
    
    def test_determine_content_event_type_completed(self):
        """Test content event type determination for completed content."""
        # Mock content attempt with completed state
        content_attempt = Mock()
        content_attempt.state = 'completed'
        
        event_type = self.monitor._determine_content_event_type(content_attempt)
        self.assertEqual(event_type, 'content_completed')
    
    def test_determine_content_event_type_watched(self):
        """Test content event type determination for watched content."""
        # Mock content attempt with watched state
        content_attempt = Mock()
        content_attempt.state = 'watched'
        
        event_type = self.monitor._determine_content_event_type(content_attempt)
        self.assertEqual(event_type, 'content_watched')
    
    def test_create_activity_event(self):
        """Test creating LMS activity event."""
        event_data = {
            'event_type': 'exam_started',
            'student_id': 123,
            'student_username': 'test_student',
            'mentor_id': 456,
            'mentor_username': 'test_mentor',
            'activity_id': 789,
            'activity_title': 'Test Exam',
            'activity_metadata': {'score': 85, 'percentage': 85},
            'timestamp': timezone.now(),
        }
        
        event = self.monitor.create_activity_event(event_data)
        
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, 'exam_started')
        self.assertEqual(event.student_id, 123)
        self.assertEqual(event.student_username, 'test_student')
        self.assertEqual(event.mentor_id, 456)
        self.assertEqual(event.mentor_username, 'test_mentor')
        self.assertEqual(event.activity_id, 789)
        self.assertEqual(event.activity_title, 'Test Exam')
        self.assertEqual(event.activity_metadata['score'], 85)
        self.assertFalse(event.processed_for_ai)
    
    def test_create_activity_event_with_error(self):
        """Test creating LMS activity event with invalid data."""
        # Invalid event data that should cause an error
        event_data = {
            'event_type': 'invalid_type',
            'student_id': 'invalid_id',  # Should be integer
            'activity_id': 'invalid_id',  # Should be integer
            'timestamp': 'invalid_timestamp',  # Should be datetime
        }
        
        event = self.monitor.create_activity_event(event_data)
        self.assertIsNone(event)
