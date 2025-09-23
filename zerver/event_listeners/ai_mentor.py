"""
AI Mentor Event Listener

This module handles AI agent conversation events for the mentor-student
interaction system. It processes events triggered when students send messages
to mentors and determines if AI mentor responses should be generated.
"""

import logging
from typing import Any, Dict

from django.conf import settings

from zerver.event_listeners.base import BaseEventHandler
from zerver.event_listeners.registry import register_event_listener

logger = logging.getLogger(__name__)


@register_event_listener
class AIMentorEventHandler(BaseEventHandler):
    """
    Event handler for AI mentor conversation events
    """

    name = "ai_mentor"
    description = "Handles AI mentor conversation events for student-mentor interactions"
    supported_events = ["ai_agent_conversation"]

    def handle_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle AI agent conversation event

        Args:
            event: Event data containing conversation details

        Returns:
            bool: True if event was processed successfully
        """
        try:
            event_type = event.get("type")
            if event_type != "ai_agent_conversation":
                return False

            # Extract event data
            mentor_data = event.get("mentor", {})
            student_data = event.get("student", {})
            original_message = event.get("original_message", "")

            mentor_id = mentor_data.get("id")
            student_id = student_data.get("id")

            if not mentor_id or not student_id:
                logger.warning("AI mentor event missing mentor or student ID")
                return False

            logger.info(
                f"Processing AI mentor event: mentor={mentor_id}, student={student_id}, "
                f"message_length={len(original_message)}"
            )

            # Check if AI agent system is enabled
            if not getattr(settings, 'USE_LANGGRAPH_AGENTS', False):
                logger.debug("AI agent system disabled, skipping processing")
                return True

            # Process the AI mentor conversation
            return self._process_ai_conversation(event)

        except Exception as e:
            logger.error(f"Error handling AI mentor event: {e}", exc_info=True)
            return False

    def _process_ai_conversation(self, event: Dict[str, Any]) -> bool:
        """
        Process the AI conversation event using the AI agent core system

        Args:
            event: Complete event data

        Returns:
            bool: True if processing was successful
        """
        try:
            # Import AI agent core when needed to avoid circular imports
            from zerver.lib.ai_agent_core import create_ai_agent_orchestrator

            # Extract data from event
            mentor_data = event.get("mentor", {})
            student_data = event.get("student", {})
            original_message = event.get("original_message", "")
            original_message_id = event.get("original_message_id", 0)

            # Get user profiles
            from zerver.models import UserProfile

            try:
                mentor = UserProfile.objects.get(id=mentor_data.get("id"))
                student = UserProfile.objects.get(id=student_data.get("id"))
            except UserProfile.DoesNotExist as e:
                logger.error(f"User not found for AI conversation: {e}")
                return False

            # Create AI agent orchestrator and process
            try:
                orchestrator = create_ai_agent_orchestrator()

                # Process the student message through the AI agent system
                result = orchestrator.process_student_message(
                    student_id=student.id,
                    mentor_id=mentor.id,
                    message_content=original_message
                )

                if result.get("success"):
                    logger.info(
                        f"AI agent processing completed: mentor={mentor.id}, student={student.id}, "
                        f"auto_response={result.get('should_auto_respond', False)}, "
                        f"decision={result.get('decision_reason', 'unknown')}"
                    )
                    return True
                else:
                    logger.warning(
                        f"AI agent processing failed: {result.get('error', 'Unknown error')}"
                    )
                    return False

            except Exception as orchestrator_error:
                logger.error(
                    f"AI orchestrator error for mentor={mentor.id}, student={student.id}: {orchestrator_error}",
                    exc_info=True
                )
                return False

        except ImportError as import_error:
            logger.error(f"AI agent core not available: {import_error}")
            return False
        except Exception as e:
            logger.error(f"Error processing AI conversation: {e}", exc_info=True)
            return False


def handle_ai_agent_conversation(event: Dict[str, Any]) -> bool:
    """
    Standalone function to handle AI agent conversation events

    This function is called directly by the AI mentor events system
    for immediate processing of conversation events.

    Args:
        event: Event data containing conversation details

    Returns:
        bool: True if event was handled successfully
    """
    try:
        handler = AIMentorEventHandler()
        return handler.handle_event(event)
    except Exception as e:
        logger.error(f"Failed to handle AI agent conversation event: {e}", exc_info=True)
        return False


def handle_ai_message_created(event: Dict[str, Any]) -> bool:
    """
    Handle AI message created events (forwarded to monitor)

    Args:
        event: AI message created event data

    Returns:
        bool: True if handled successfully
    """
    try:
        from zerver.event_listeners.ai_message_monitor import handle_ai_message_created as monitor_handler
        return monitor_handler(event)
    except ImportError:
        logger.warning("AI message monitor not available")
        return True
    except Exception as e:
        logger.error(f"Failed to handle AI message created event: {e}", exc_info=True)
        return False


# Register the event handler
def get_event_handler():
    """
    Factory function to create AI mentor event handler instance

    Returns:
        AIMentorEventHandler: Configured event handler instance
    """
    return AIMentorEventHandler()