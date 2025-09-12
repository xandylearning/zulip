"""
Example event listeners demonstrating the plugin system usage.

These examples show how to create custom event listeners using the
event_listeners Django app plugin system.
"""

import logging
from typing import Dict, Any
from .base import MessageEventHandler, UserEventHandler, StreamEventHandler
from .registry import register_event_listener

logger = logging.getLogger(__name__)


@register_event_listener
class MessageLoggerListener(MessageEventHandler):
    """Simple message logger that logs all messages to console"""
    
    name = "message_logger"
    description = "Logs all messages to the console"
    
    def handle_message_event(self, event: Dict[str, Any]) -> None:
        """Log message events"""
        message = event.get('message', {})
        sender_full_name = message.get('sender_full_name', 'Unknown')
        content = message.get('content', '')[:100]  # First 100 chars
        
        logger.info(f"Message from {sender_full_name}: {content}")
        print(f"[MESSAGE] {sender_full_name}: {content}")


@register_event_listener
class UserStatusListener(UserEventHandler):
    """Tracks user status changes"""
    
    name = "user_status_tracker"
    description = "Tracks user status changes (online/offline)"
    
    def handle_user_event(self, event: Dict[str, Any]) -> None:
        """Handle user status events"""
        if event.get('type') == 'presence':
            user_id = event.get('user_id')
            status = event.get('presence', {})
            
            logger.info(f"User {user_id} status changed: {status}")
            print(f"[USER STATUS] User {user_id}: {status}")


@register_event_listener
class StreamActivityListener(StreamEventHandler):
    """Monitors stream activity"""
    
    name = "stream_activity_monitor"
    description = "Monitors stream creation, updates, and activity"
    
    def handle_stream_event(self, event: Dict[str, Any]) -> None:
        """Handle stream-related events"""
        event_type = event.get('type')
        
        if event_type == 'stream':
            op = event.get('op')
            streams = event.get('streams', [])
            
            for stream in streams:
                stream_name = stream.get('name', 'Unknown')
                logger.info(f"Stream {op}: {stream_name}")
                print(f"[STREAM] {op}: {stream_name}")


@register_event_listener
class AIMentoringListener(MessageEventHandler):
    """
    Example AI mentoring listener that demonstrates the pattern
    for implementing AI mentoring functionality.
    
    This is a simplified version - for full implementation,
    refer to AI_MENTORING_SYSTEM_DOCS.md
    """
    
    name = "ai_mentoring_demo"
    description = "Demo AI mentoring system with pattern learning"
    
    def __init__(self):
        super().__init__()
        self.mentor_patterns = {}  # In production, use database
        self.student_interactions = {}  # Track student interactions
    
    def handle_message_event(self, event: Dict[str, Any]) -> None:
        """Handle messages for AI mentoring"""
        message = event.get('message', {})
        sender_id = message.get('sender_id')
        recipient_id = message.get('recipient_id')
        content = message.get('content', '')
        
        # Check if this is a student-mentor interaction
        if self.is_mentor_student_interaction(sender_id, recipient_id):
            self.learn_from_interaction(sender_id, recipient_id, content)
            self.potentially_respond_as_ai(sender_id, recipient_id, content)
    
    def is_mentor_student_interaction(self, sender_id: int, recipient_id: int) -> bool:
        """Check if this is a mentor-student interaction"""
        # This would check your mentor-student mapping
        # For demo purposes, return False to avoid actual responses
        return False
    
    def learn_from_interaction(self, sender_id: int, recipient_id: int, content: str) -> None:
        """Learn patterns from mentor-student interactions"""
        logger.info(f"Learning from interaction: {sender_id} -> {recipient_id}")
        # Implement pattern learning logic here
        
    def potentially_respond_as_ai(self, sender_id: int, recipient_id: int, content: str) -> None:
        """Potentially respond as AI with human-like delay"""
        logger.info(f"Considering AI response for: {sender_id} -> {recipient_id}")
        # Implement AI response logic with delays here


# Example of a composite listener that handles multiple event types
@register_event_listener
class ComprehensiveAnalyticsListener(MessageEventHandler, UserEventHandler, StreamEventHandler):
    """
    Example of a listener that handles multiple event types
    for comprehensive analytics
    """
    
    name = "comprehensive_analytics"
    description = "Comprehensive analytics across all event types"
    
    def __init__(self):
        super().__init__()
        self.analytics_data = {
            'messages': 0,
            'user_events': 0,
            'stream_events': 0
        }
    
    def handle_message_event(self, event: Dict[str, Any]) -> None:
        """Track message analytics"""
        self.analytics_data['messages'] += 1
        logger.info(f"Analytics: {self.analytics_data['messages']} messages processed")
    
    def handle_user_event(self, event: Dict[str, Any]) -> None:
        """Track user event analytics"""
        self.analytics_data['user_events'] += 1
        logger.info(f"Analytics: {self.analytics_data['user_events']} user events processed")
    
    def handle_stream_event(self, event: Dict[str, Any]) -> None:
        """Track stream event analytics"""
        self.analytics_data['stream_events'] += 1
        logger.info(f"Analytics: {self.analytics_data['stream_events']} stream events processed")
    
    def get_analytics_summary(self) -> Dict[str, int]:
        """Get analytics summary"""
        return self.analytics_data.copy()