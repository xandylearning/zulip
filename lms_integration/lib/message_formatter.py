"""
Message Formatter for LMS Activity Notifications

Formats notification messages for mentors based on student LMS activities.
"""

from typing import Dict, Optional
from lms_integration.models import LMSActivityEvent


class MessageFormatter:
    """
    Formats notification messages for LMS activity events.
    """
    
    # Event type emojis
    EVENT_EMOJIS = {
        'exam_started': '📝',
        'exam_completed': '✅',
        'exam_failed': '❌',
        'exam_passed': '🎉',
        'content_started': '📖',
        'content_completed': '📚',
        'content_watched': '👀',
    }
    
    def format_notification_message(self, event: LMSActivityEvent) -> str:
        """
        Format a notification message for an LMS activity event.
        
        Args:
            event: LMSActivityEvent instance
            
        Returns:
            Formatted message string
        """
        emoji = self.EVENT_EMOJIS.get(event.event_type, '📋')
        student_name = self._get_student_display_name(event)
        
        if event.event_type.startswith('exam_'):
            return self._format_exam_message(event, emoji, student_name)
        elif event.event_type.startswith('content_'):
            return self._format_content_message(event, emoji, student_name)
        else:
            return self._format_generic_message(event, emoji, student_name)
    
    def _format_exam_message(self, event: LMSActivityEvent, emoji: str, student_name: str) -> str:
        """Format exam-related notification messages."""
        metadata = event.activity_metadata or {}
        
        if event.event_type == 'exam_started':
            return f"{emoji} **Student Activity Alert**\n\n" \
                   f"**{student_name}** has started the exam: **{event.activity_title}**\n" \
                   f"📅 Started at: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        elif event.event_type == 'exam_completed':
            score_info = self._format_score_info(metadata)
            return f"{emoji} **Exam Completed**\n\n" \
                   f"**{student_name}** has completed: **{event.activity_title}**\n" \
                   f"{score_info}\n" \
                   f"📅 Completed at: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        elif event.event_type == 'exam_passed':
            score_info = self._format_score_info(metadata)
            return f"{emoji} **Exam Passed!**\n\n" \
                   f"**{student_name}** has passed: **{event.activity_title}**\n" \
                   f"{score_info}\n" \
                   f"🎉 Congratulations to the student!"
        
        elif event.event_type == 'exam_failed':
            score_info = self._format_score_info(metadata)
            return f"{emoji} **Exam Failed**\n\n" \
                   f"**{student_name}** did not pass: **{event.activity_title}**\n" \
                   f"{score_info}\n" \
                   f"💡 Consider providing additional support."
        
        return self._format_generic_message(event, emoji, student_name)
    
    def _format_content_message(self, event: LMSActivityEvent, emoji: str, student_name: str) -> str:
        """Format content-related notification messages."""
        metadata = event.activity_metadata or {}
        course_info = self._format_course_info(metadata)
        
        if event.event_type == 'content_started':
            return f"{emoji} **Content Started**\n\n" \
                   f"**{student_name}** has started: **{event.activity_title}**\n" \
                   f"{course_info}\n" \
                   f"📅 Started at: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        elif event.event_type == 'content_completed':
            return f"{emoji} **Content Completed**\n\n" \
                   f"**{student_name}** has completed: **{event.activity_title}**\n" \
                   f"{course_info}\n" \
                   f"📅 Completed at: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        elif event.event_type == 'content_watched':
            return f"{emoji} **Content Viewed**\n\n" \
                   f"**{student_name}** has watched: **{event.activity_title}**\n" \
                   f"{course_info}\n" \
                   f"📅 Viewed at: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
        
        return self._format_generic_message(event, emoji, student_name)
    
    def _format_generic_message(self, event: LMSActivityEvent, emoji: str, student_name: str) -> str:
        """Format generic notification messages."""
        return f"{emoji} **Student Activity**\n\n" \
               f"**{student_name}** - {event.event_type.replace('_', ' ').title()}\n" \
               f"Activity: **{event.activity_title}**\n" \
               f"📅 Time: {event.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"
    
    def _get_student_display_name(self, event: LMSActivityEvent) -> str:
        """Get display name for student."""
        if event.student_username:
            return event.student_username
        return f"Student ID: {event.student_id}"
    
    def _format_score_info(self, metadata: Dict) -> str:
        """Format score information for exam events."""
        score_parts = []
        
        if metadata.get('score') is not None:
            score_parts.append(f"**Score:** {metadata['score']}")
        
        if metadata.get('percentage') is not None:
            score_parts.append(f"**Percentage:** {metadata['percentage']}%")
        
        if metadata.get('result'):
            score_parts.append(f"**Result:** {metadata['result']}")
        
        if metadata.get('time_taken'):
            score_parts.append(f"**Time Taken:** {metadata['time_taken']}")
        
        if metadata.get('correct_answers') is not None:
            score_parts.append(f"**Correct:** {metadata['correct_answers']}")
        
        if metadata.get('incorrect_answers') is not None:
            score_parts.append(f"**Incorrect:** {metadata['incorrect_answers']}")
        
        if metadata.get('unanswered') is not None:
            score_parts.append(f"**Unanswered:** {metadata['unanswered']}")
        
        if score_parts:
            return "📊 " + " | ".join(score_parts)
        
        return ""
    
    def _format_course_info(self, metadata: Dict) -> str:
        """Format course information for content events."""
        course_parts = []
        
        if metadata.get('course_title'):
            course_parts.append(f"**Course:** {metadata['course_title']}")
        
        if metadata.get('chapter_name'):
            course_parts.append(f"**Chapter:** {metadata['chapter_name']}")
        
        if metadata.get('content_type'):
            course_parts.append(f"**Type:** {metadata['content_type']}")
        
        if course_parts:
            return "📚 " + " | ".join(course_parts)
        
        return ""
    
    def format_summary_message(self, events: list, time_period: str = "recent") -> str:
        """
        Format a summary message for multiple events.
        
        Args:
            events: List of LMSActivityEvent instances
            time_period: Description of time period (e.g., "last hour", "today")
            
        Returns:
            Formatted summary message
        """
        if not events:
            return f"📊 **LMS Activity Summary - {time_period.title()}**\n\nNo new activities detected."
        
        # Group events by type
        event_counts = {}
        for event in events:
            event_counts[event.event_type] = event_counts.get(event.event_type, 0) + 1
        
        # Create summary
        summary_parts = [f"📊 **LMS Activity Summary - {time_period.title()}**\n"]
        summary_parts.append(f"**Total Activities:** {len(events)}\n")
        
        # Add breakdown by event type
        for event_type, count in event_counts.items():
            emoji = self.EVENT_EMOJIS.get(event_type, '📋')
            display_name = event_type.replace('_', ' ').title()
            summary_parts.append(f"{emoji} {display_name}: {count}")
        
        return "\n".join(summary_parts)
