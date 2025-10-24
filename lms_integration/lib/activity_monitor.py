"""
LMS Activity Monitor

Polls the external LMS database for new student activities and emits events
for processing by the event listener system.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from django.conf import settings
from django.db import transaction
from django.utils import timezone

from lms_integration.models import Attempts, ContentAttempts, Students, Mentors, Mentortostudent
from lms_integration.models import LMSActivityEvent

logger = logging.getLogger(__name__)


class ActivityMonitor:
    """
    Monitors LMS database for new student activities and creates events.
    """
    
    def __init__(self, poll_interval: int = 60):
        self.poll_interval = poll_interval
        self.last_poll_time = None
        self.processed_attempts = set()
        self.processed_content_attempts = set()
        
    def poll_for_new_activities(self) -> List[Dict]:
        """
        Poll LMS database for new activities since last poll.
        Returns list of detected activity events.
        """
        events = []
        current_time = timezone.now()
        
        # Set initial poll time if not set
        if self.last_poll_time is None:
            self.last_poll_time = current_time - timedelta(minutes=5)  # Look back 5 minutes initially
        
        try:
            # Poll for new exam attempts
            exam_events = self._detect_exam_activities()
            events.extend(exam_events)
            
            # Poll for new content attempts
            content_events = self._detect_content_activities()
            events.extend(content_events)
            
            # Update last poll time
            self.last_poll_time = current_time
            
            logger.info(f"Detected {len(events)} new activities since {self.last_poll_time}")
            
        except Exception as e:
            logger.error(f"Error polling LMS activities: {e}")
            
        return events
    
    def _detect_exam_activities(self) -> List[Dict]:
        """Detect new exam activities from Attempts table."""
        events = []
        
        try:
            # Query for new attempts since last poll
            new_attempts = Attempts.objects.filter(
                date__gte=self.last_poll_time
            ).select_related('user', 'exam')
            
            for attempt in new_attempts:
                # Skip if already processed
                if attempt.id in self.processed_attempts:
                    continue
                
                # Determine event type based on attempt state
                event_type = self._determine_exam_event_type(attempt)
                if not event_type:
                    continue
                
                # Get mentor information
                mentor_info = self._get_student_mentor(attempt.user_id)
                
                # Create event data
                event_data = {
                    'event_type': event_type,
                    'student_id': attempt.user_id,
                    'student_username': attempt.username or attempt.user.username if attempt.user else None,
                    'mentor_id': mentor_info.get('mentor_id'),
                    'mentor_username': mentor_info.get('mentor_username'),
                    'activity_id': attempt.exam_id,
                    'activity_title': attempt.exam.title if attempt.exam else None,
                    'activity_metadata': {
                        'score': attempt.score,
                        'percentage': attempt.percentage,
                        'result': attempt.result,
                        'time_taken': attempt.time_taken,
                        'correct_answers': attempt.correct_answers_count,
                        'incorrect_answers': attempt.incorrect_answers_count,
                        'unanswered': attempt.unanswered_count,
                        'percentile': attempt.percentile,
                        'speed': attempt.speed,
                    },
                    'timestamp': attempt.date or attempt.last_started_time or timezone.now(),
                }
                
                events.append(event_data)
                self.processed_attempts.add(attempt.id)
                
        except Exception as e:
            logger.error(f"Error detecting exam activities: {e}")
            
        return events
    
    def _detect_content_activities(self) -> List[Dict]:
        """Detect new content activities from ContentAttempts table."""
        events = []
        
        try:
            # Query for new content attempts since last poll
            new_content_attempts = ContentAttempts.objects.filter(
                created__gte=self.last_poll_time
            ).select_related('user', 'chapter_content', 'course', 'chapter')
            
            for content_attempt in new_content_attempts:
                # Skip if already processed
                if content_attempt.id in self.processed_content_attempts:
                    continue
                
                # Determine event type based on content attempt state
                event_type = self._determine_content_event_type(content_attempt)
                if not event_type:
                    continue
                
                # Get mentor information
                mentor_info = self._get_student_mentor(content_attempt.user_id)
                
                # Create event data
                event_data = {
                    'event_type': event_type,
                    'student_id': content_attempt.user_id,
                    'student_username': content_attempt.user.username if content_attempt.user else None,
                    'mentor_id': mentor_info.get('mentor_id'),
                    'mentor_username': mentor_info.get('mentor_username'),
                    'activity_id': content_attempt.chapter_content_id,
                    'activity_title': content_attempt.chapter_content.title if content_attempt.chapter_content else None,
                    'activity_metadata': {
                        'content_type': content_attempt.content_type,
                        'state': content_attempt.state,
                        'course_title': content_attempt.course.title if content_attempt.course else None,
                        'chapter_name': content_attempt.chapter.name if content_attempt.chapter else None,
                        'correct_answers': content_attempt.correct_answers_count,
                        'incorrect_answers': content_attempt.incorrect_answers_count,
                        'completed_on': content_attempt.completed_on.isoformat() if content_attempt.completed_on else None,
                    },
                    'timestamp': content_attempt.created,
                }
                
                events.append(event_data)
                self.processed_content_attempts.add(content_attempt.id)
                
        except Exception as e:
            logger.error(f"Error detecting content activities: {e}")
            
        return events
    
    def _determine_exam_event_type(self, attempt: Attempts) -> Optional[str]:
        """Determine event type based on exam attempt state."""
        if not attempt.state:
            return None
            
        state = attempt.state.lower()
        
        if state in ['started', 'in_progress']:
            return 'exam_started'
        elif state in ['completed', 'finished']:
            if attempt.result:
                result = attempt.result.lower()
                if result in ['pass', 'passed']:
                    return 'exam_passed'
                elif result in ['fail', 'failed']:
                    return 'exam_failed'
                else:
                    return 'exam_completed'
            return 'exam_completed'
        
        return None
    
    def _determine_content_event_type(self, content_attempt: ContentAttempts) -> Optional[str]:
        """Determine event type based on content attempt state."""
        if not content_attempt.state:
            return None
            
        state = content_attempt.state.lower()
        
        if state in ['started', 'in_progress']:
            return 'content_started'
        elif state in ['completed', 'finished']:
            return 'content_completed'
        elif state in ['watched', 'viewed']:
            return 'content_watched'
        
        return None
    
    def _get_student_mentor(self, student_id: int) -> Dict[str, Optional[str]]:
        """Get mentor information for a student."""
        try:
            # Find mentor-student relationship
            mentor_student = Mentortostudent.objects.filter(
                b_id=student_id  # b is the student in the relationship
            ).select_related('a').first()  # a is the mentor
            
            if mentor_student and mentor_student.a:
                mentor = mentor_student.a
                return {
                    'mentor_id': mentor.user_id,
                    'mentor_username': mentor.username,
                }
        except Exception as e:
            logger.warning(f"Could not find mentor for student {student_id}: {e}")
            
        return {'mentor_id': None, 'mentor_username': None}
    
    def create_activity_event(self, event_data: Dict) -> Optional[LMSActivityEvent]:
        """Create LMSActivityEvent record in Zulip database."""
        try:
            with transaction.atomic():
                event = LMSActivityEvent.objects.create(
                    event_type=event_data['event_type'],
                    student_id=event_data['student_id'],
                    student_username=event_data.get('student_username'),
                    mentor_id=event_data.get('mentor_id'),
                    mentor_username=event_data.get('mentor_username'),
                    activity_id=event_data['activity_id'],
                    activity_title=event_data.get('activity_title'),
                    activity_metadata=event_data.get('activity_metadata'),
                    timestamp=event_data['timestamp'],
                    processed_for_ai=False,
                )
                
                logger.info(f"Created LMS activity event: {event.event_id} - {event.event_type}")
                return event
                
        except Exception as e:
            logger.error(f"Error creating LMS activity event: {e}")
            return None
    
    def process_activities(self) -> int:
        """
        Main processing method that polls for activities and creates events.
        Returns number of events created.
        """
        events_created = 0
        
        try:
            # Poll for new activities
            activities = self.poll_for_new_activities()
            
            # Create events for each activity
            for activity_data in activities:
                event = self.create_activity_event(activity_data)
                if event:
                    events_created += 1
                    
        except Exception as e:
            logger.error(f"Error processing activities: {e}")
            
        return events_created
