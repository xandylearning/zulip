"""
AI Message Monitor Event Listener

This module monitors message-related events for AI agent integration,
tracking message flows, response patterns, and system performance.
"""

import logging
from typing import Any, Dict, Optional

from django.conf import settings
from django.utils import timezone

from zerver.event_listeners.base import BaseEventHandler
from zerver.event_listeners.registry import register_event_listener

logger = logging.getLogger(__name__)


@register_event_listener
class AIMessageMonitorEventHandler(BaseEventHandler):
    """
    Event handler for monitoring AI message-related events
    """

    name = "ai_message_monitor"
    description = "Monitors message events for AI agent integration analytics"
    supported_events = [
        "ai_mentor_response",
        "ai_style_analysis",
        "ai_error",
        "ai_feedback",
        "message"
    ]

    def handle_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle AI message monitoring events

        Args:
            event: Event data containing message information

        Returns:
            bool: True if event was processed successfully
        """
        try:
            event_type = event.get("type")

            if event_type == "ai_mentor_response":
                return self._handle_ai_response_event(event)
            elif event_type == "ai_style_analysis":
                return self._handle_style_analysis_event(event)
            elif event_type == "ai_error":
                return self._handle_ai_error_event(event)
            elif event_type == "ai_feedback":
                return self._handle_ai_feedback_event(event)
            elif event_type == "message":
                return self._handle_message_event(event)
            else:
                logger.debug(f"Unsupported event type for AI monitoring: {event_type}")
                return False

        except Exception as e:
            logger.error(f"Error handling AI message monitor event: {e}", exc_info=True)
            return False

    def _handle_ai_response_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle AI mentor response events

        Args:
            event: AI response event data

        Returns:
            bool: True if handled successfully
        """
        try:
            mentor_id = event.get("mentor_id")
            student_id = event.get("student_id")
            response_confidence = event.get("response_confidence", 0.0)
            decision_reason = event.get("decision_reason", "unknown")

            logger.info(
                f"AI response generated: mentor={mentor_id}, student={student_id}, "
                f"confidence={response_confidence:.2f}, reason={decision_reason}"
            )

            # Track response analytics
            self._track_response_analytics(event)

            return True

        except Exception as e:
            logger.error(f"Error handling AI response event: {e}")
            return False

    def _handle_style_analysis_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle AI style analysis events

        Args:
            event: Style analysis event data

        Returns:
            bool: True if handled successfully
        """
        try:
            mentor_id = event.get("mentor_id")
            analysis_type = event.get("analysis_type", "unknown")
            confidence_score = event.get("confidence_score", 0.0)

            logger.info(
                f"AI style analysis updated: mentor={mentor_id}, "
                f"type={analysis_type}, confidence={confidence_score:.2f}"
            )

            # Track style analysis performance
            self._track_style_analytics(event)

            return True

        except Exception as e:
            logger.error(f"Error handling AI style analysis event: {e}")
            return False

    def _handle_ai_error_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle AI error events

        Args:
            event: AI error event data

        Returns:
            bool: True if handled successfully
        """
        try:
            error_type = event.get("error_type", "unknown")
            error_message = event.get("error_message", "")
            mentor_id = event.get("mentor_id")
            student_id = event.get("student_id")

            logger.warning(
                f"AI error occurred: type={error_type}, mentor={mentor_id}, "
                f"student={student_id}, message={error_message}"
            )

            # Track error patterns for debugging
            self._track_error_analytics(event)

            return True

        except Exception as e:
            logger.error(f"Error handling AI error event: {e}")
            return False

    def _handle_ai_feedback_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle AI feedback events

        Args:
            event: AI feedback event data

        Returns:
            bool: True if handled successfully
        """
        try:
            feedback_type = event.get("feedback_type", "unknown")
            feedback_score = event.get("feedback_score")
            mentor_id = event.get("mentor_id")

            logger.info(
                f"AI feedback received: type={feedback_type}, mentor={mentor_id}, "
                f"score={feedback_score}"
            )

            # Track feedback for system improvement
            self._track_feedback_analytics(event)

            return True

        except Exception as e:
            logger.error(f"Error handling AI feedback event: {e}")
            return False

    def _handle_message_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle general message events for AI monitoring

        Args:
            event: Message event data

        Returns:
            bool: True if handled successfully
        """
        try:
            # Only monitor if AI system is enabled
            if not getattr(settings, 'USE_LANGGRAPH_AGENTS', False):
                return True

            message_type = event.get("message", {}).get("type")
            if message_type == "private":
                # Monitor private messages for potential AI processing
                return self._monitor_private_message(event)

            return True

        except Exception as e:
            logger.error(f"Error handling message event for AI monitoring: {e}")
            return False

    def _monitor_private_message(self, event: Dict[str, Any]) -> bool:
        """
        Monitor private messages for AI processing opportunities

        Args:
            event: Private message event data

        Returns:
            bool: True if monitoring was successful
        """
        try:
            message_data = event.get("message", {})
            sender_id = message_data.get("sender_id")
            recipient_id = message_data.get("recipient_id")

            # Log private message for AI monitoring (without content for privacy)
            logger.debug(
                f"Private message monitored: sender={sender_id}, recipient={recipient_id}"
            )

            return True

        except Exception as e:
            logger.error(f"Error monitoring private message: {e}")
            return False

    def _track_response_analytics(self, event: Dict[str, Any]) -> None:
        """
        Track AI response analytics

        Args:
            event: Response event data
        """
        try:
            # In a production system, this would write to analytics database
            # For now, we log key metrics
            logger.debug(f"AI response analytics: {event.get('mentor_id')}")

        except Exception as e:
            logger.error(f"Error tracking response analytics: {e}")

    def _track_style_analytics(self, event: Dict[str, Any]) -> None:
        """
        Track AI style analysis analytics

        Args:
            event: Style analysis event data
        """
        try:
            # Track style analysis patterns
            logger.debug(f"AI style analytics: {event.get('mentor_id')}")

        except Exception as e:
            logger.error(f"Error tracking style analytics: {e}")

    def _track_error_analytics(self, event: Dict[str, Any]) -> None:
        """
        Track AI error analytics

        Args:
            event: Error event data
        """
        try:
            # Track error patterns for system improvement
            logger.debug(f"AI error analytics: {event.get('error_type')}")

        except Exception as e:
            logger.error(f"Error tracking error analytics: {e}")

    def _track_feedback_analytics(self, event: Dict[str, Any]) -> None:
        """
        Track AI feedback analytics

        Args:
            event: Feedback event data
        """
        try:
            # Track feedback patterns for quality improvement
            logger.debug(f"AI feedback analytics: {event.get('feedback_type')}")

        except Exception as e:
            logger.error(f"Error tracking feedback analytics: {e}")


def handle_ai_mentor_response(event: Dict[str, Any]) -> bool:
    """
    Handle AI mentor response events

    Args:
        event: AI mentor response event data

    Returns:
        bool: True if handled successfully
    """
    try:
        handler = AIMessageMonitorEventHandler()
        return handler._handle_ai_response_event(event)
    except Exception as e:
        logger.error(f"Failed to handle AI mentor response event: {e}", exc_info=True)
        return False


def handle_ai_style_analysis(event: Dict[str, Any]) -> bool:
    """
    Handle AI style analysis events

    Args:
        event: AI style analysis event data

    Returns:
        bool: True if handled successfully
    """
    try:
        handler = AIMessageMonitorEventHandler()
        return handler._handle_style_analysis_event(event)
    except Exception as e:
        logger.error(f"Failed to handle AI style analysis event: {e}", exc_info=True)
        return False


def handle_ai_error(event: Dict[str, Any]) -> bool:
    """
    Handle AI error events

    Args:
        event: AI error event data

    Returns:
        bool: True if handled successfully
    """
    try:
        handler = AIMessageMonitorEventHandler()
        return handler._handle_ai_error_event(event)
    except Exception as e:
        logger.error(f"Failed to handle AI error event: {e}", exc_info=True)
        return False


def handle_ai_message_created(event: Dict[str, Any]) -> bool:
    """
    Handle AI message created events

    Args:
        event: AI message created event data

    Returns:
        bool: True if handled successfully
    """
    try:
        handler = AIMessageMonitorEventHandler()
        # Process as a custom AI monitoring event
        monitor_event = {
            "type": "ai_message_created",
            "message_id": event.get("message_id"),
            "mentor_id": event.get("mentor_id"),
            "student_id": event.get("student_id"),
            "ai_metadata": event.get("ai_metadata", {}),
            "timestamp": event.get("timestamp")
        }
        return handler._track_response_analytics(monitor_event)
    except Exception as e:
        logger.error(f"Failed to handle AI message created event: {e}", exc_info=True)
        return False


def handle_ai_agent_performance(event: Dict[str, Any]) -> bool:
    """
    Handle AI agent performance events

    Args:
        event: AI agent performance event data

    Returns:
        bool: True if handled successfully
    """
    try:
        agent_type = event.get("agent_type", "unknown")
        processing_time = event.get("processing_time_ms", 0)
        success = event.get("success", False)
        confidence = event.get("confidence_score")

        logger.info(
            f"AI agent performance: type={agent_type}, time={processing_time}ms, "
            f"success={success}, confidence={confidence}"
        )

        handler = AIMessageMonitorEventHandler()
        # Track performance metrics
        handler._track_response_analytics(event)

        return True
    except Exception as e:
        logger.error(f"Failed to handle AI agent performance event: {e}", exc_info=True)
        return False


# Register the event handler
def get_event_handler():
    """
    Factory function to create AI message monitor event handler instance

    Returns:
        AIMessageMonitorEventHandler: Configured event handler instance
    """
    return AIMessageMonitorEventHandler()