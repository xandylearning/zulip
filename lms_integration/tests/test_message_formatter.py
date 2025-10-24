"""
Tests for LMS Message Formatter
"""

from datetime import datetime
from django.test import TestCase
from django.utils import timezone

from lms_integration.models import LMSActivityEvent
from lms_integration.lib.message_formatter import MessageFormatter


class MessageFormatterTestCase(TestCase):
    """Test cases for MessageFormatter class."""
    
    def setUp(self):
        """Set up test data."""
        self.formatter = MessageFormatter()
        self.timestamp = timezone.now()
    
    def test_format_exam_started_message(self):
        """Test formatting exam started message."""
        event = LMSActivityEvent(
            event_type='exam_started',
            student_username='john_doe',
            activity_title='Math Exam',
            timestamp=self.timestamp
        )
        
        message = self.formatter.format_notification_message(event)
        
        self.assertIn('📝', message)
        self.assertIn('Student Activity Alert', message)
        self.assertIn('john_doe', message)
        self.assertIn('Math Exam', message)
        self.assertIn('started', message)
    
    def test_format_exam_passed_message(self):
        """Test formatting exam passed message."""
        event = LMSActivityEvent(
            event_type='exam_passed',
            student_username='jane_smith',
            activity_title='Science Quiz',
            timestamp=self.timestamp,
            activity_metadata={
                'score': 85,
                'percentage': 85,
                'result': 'pass',
                'time_taken': '45 minutes'
            }
        )
        
        message = self.formatter.format_notification_message(event)
        
        self.assertIn('🎉', message)
        self.assertIn('Exam Passed!', message)
        self.assertIn('jane_smith', message)
        self.assertIn('Science Quiz', message)
        self.assertIn('Score: 85', message)
        self.assertIn('Percentage: 85%', message)
        self.assertIn('Congratulations', message)
    
    def test_format_exam_failed_message(self):
        """Test formatting exam failed message."""
        event = LMSActivityEvent(
            event_type='exam_failed',
            student_username='bob_wilson',
            activity_title='History Test',
            timestamp=self.timestamp,
            activity_metadata={
                'score': 45,
                'percentage': 45,
                'result': 'fail',
                'time_taken': '30 minutes'
            }
        )
        
        message = self.formatter.format_notification_message(event)
        
        self.assertIn('❌', message)
        self.assertIn('Exam Failed', message)
        self.assertIn('bob_wilson', message)
        self.assertIn('History Test', message)
        self.assertIn('Score: 45', message)
        self.assertIn('Percentage: 45%', message)
        self.assertIn('additional support', message)
    
    def test_format_content_started_message(self):
        """Test formatting content started message."""
        event = LMSActivityEvent(
            event_type='content_started',
            student_username='alice_brown',
            activity_title='Python Tutorial',
            timestamp=self.timestamp,
            activity_metadata={
                'course_title': 'Programming 101',
                'chapter_name': 'Introduction to Python',
                'content_type': 'video'
            }
        )
        
        message = self.formatter.format_notification_message(event)
        
        self.assertIn('📖', message)
        self.assertIn('Content Started', message)
        self.assertIn('alice_brown', message)
        self.assertIn('Python Tutorial', message)
        self.assertIn('Programming 101', message)
        self.assertIn('Introduction to Python', message)
    
    def test_format_content_completed_message(self):
        """Test formatting content completed message."""
        event = LMSActivityEvent(
            event_type='content_completed',
            student_username='charlie_davis',
            activity_title='Database Design',
            timestamp=self.timestamp,
            activity_metadata={
                'course_title': 'Database Systems',
                'chapter_name': 'Advanced Queries',
                'content_type': 'assignment'
            }
        )
        
        message = self.formatter.format_notification_message(event)
        
        self.assertIn('📚', message)
        self.assertIn('Content Completed', message)
        self.assertIn('charlie_davis', message)
        self.assertIn('Database Design', message)
        self.assertIn('Database Systems', message)
        self.assertIn('Advanced Queries', message)
    
    def test_format_content_watched_message(self):
        """Test formatting content watched message."""
        event = LMSActivityEvent(
            event_type='content_watched',
            student_username='diana_lee',
            activity_title='Machine Learning Lecture',
            timestamp=self.timestamp,
            activity_metadata={
                'course_title': 'AI Fundamentals',
                'chapter_name': 'Neural Networks',
                'content_type': 'video'
            }
        )
        
        message = self.formatter.format_notification_message(event)
        
        self.assertIn('👀', message)
        self.assertIn('Content Viewed', message)
        self.assertIn('diana_lee', message)
        self.assertIn('Machine Learning Lecture', message)
        self.assertIn('AI Fundamentals', message)
        self.assertIn('Neural Networks', message)
    
    def test_format_summary_message(self):
        """Test formatting summary message for multiple events."""
        events = [
            LMSActivityEvent(event_type='exam_started'),
            LMSActivityEvent(event_type='exam_completed'),
            LMSActivityEvent(event_type='content_started'),
            LMSActivityEvent(event_type='content_completed'),
        ]
        
        message = self.formatter.format_summary_message(events, "last hour")
        
        self.assertIn('LMS Activity Summary', message)
        self.assertIn('Last Hour', message)
        self.assertIn('Total Activities: 4', message)
        self.assertIn('📝 Exam Started: 1', message)
        self.assertIn('✅ Exam Completed: 1', message)
        self.assertIn('📖 Content Started: 1', message)
        self.assertIn('📚 Content Completed: 1', message)
    
    def test_format_summary_message_empty(self):
        """Test formatting summary message for no events."""
        message = self.formatter.format_summary_message([], "today")
        
        self.assertIn('LMS Activity Summary', message)
        self.assertIn('Today', message)
        self.assertIn('No new activities detected', message)
    
    def test_get_student_display_name_with_username(self):
        """Test getting student display name with username."""
        event = LMSActivityEvent(
            student_username='test_user',
            student_id=123
        )
        
        display_name = self.formatter._get_student_display_name(event)
        self.assertEqual(display_name, 'test_user')
    
    def test_get_student_display_name_without_username(self):
        """Test getting student display name without username."""
        event = LMSActivityEvent(
            student_username=None,
            student_id=123
        )
        
        display_name = self.formatter._get_student_display_name(event)
        self.assertEqual(display_name, 'Student ID: 123')
