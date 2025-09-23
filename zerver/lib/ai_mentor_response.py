"""
AI Mentor Response Engine

This module provides the main interface for AI mentor responses using
LangGraph agents and Portkey integration. It replaces the legacy template-based
system with a sophisticated multi-agent workflow.
"""

import logging
from typing import Any

from django.conf import settings
from django.utils import timezone

from zerver.models import UserProfile
from zerver.actions.ai_mentor_events import (
    notify_ai_response_generated,
    notify_ai_error,
)

# Import the new LangGraph agent system
try:
    from zerver.lib.ai_agent_core import create_ai_agent_orchestrator
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False

logger = logging.getLogger(__name__)




class AIMentorResponseEngine:
    """Main engine coordinating AI mentor responses using LangGraph agents"""

    def __init__(self) -> None:
        if not LANGGRAPH_AVAILABLE:
            raise ImportError(
                "LangGraph dependencies not available. Install with: pip install -e ."
            )

        # Initialize LangGraph agent system
        self.use_agents = getattr(settings, 'USE_LANGGRAPH_AGENTS', True)

        if not self.use_agents:
            raise ValueError(
                "LangGraph agents are disabled. Set USE_LANGGRAPH_AGENTS=True to use AI mentor features."
            )

        try:
            self.agent_orchestrator = create_ai_agent_orchestrator()
            logger.info("LangGraph AI agents initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize LangGraph agents: {e}")
            raise

    def process_student_message(self, student: UserProfile, mentor: UserProfile,
                              message_content: str) -> str | None:
        """
        Process student message and potentially generate AI mentor response using LangGraph agents

        Returns AI response if conditions are met, None otherwise
        """
        # Check if AI features are enabled and user has permission
        if not self._ai_features_enabled(mentor):
            return None

        try:
            logger.info(f"Processing with LangGraph agents: student={student.id}, mentor={mentor.id}")

            result = self.agent_orchestrator.process_student_message(
                student_id=student.id,
                mentor_id=mentor.id,
                message_content=message_content
            )

            if result["success"]:
                self._log_agent_interaction(student, mentor, result)

                if result["should_auto_respond"]:
                    return result["final_response"]
                else:
                    logger.info(f"Agent decided not to auto-respond: {result['decision_reason']}")
                    return None
            else:
                logger.error(f"Agent processing failed: {result.get('error')}")
                return None

        except Exception as e:
            logger.error(f"Agent processing error: {e}")

            # Trigger error event
            try:
                notify_ai_error(
                    mentor=mentor,
                    student=student,
                    error_type="agent_processing_error",
                    error_message=str(e),
                    context={"message_content_length": len(message_content)}
                )
            except Exception:
                pass

            return None

    def get_intelligent_suggestions(self, student: UserProfile, mentor: UserProfile,
                                  message_content: str) -> list[dict]:
        """Get intelligent suggestions for mentor response using LangGraph agents"""
        try:
            result = self.agent_orchestrator.process_student_message(
                student_id=student.id,
                mentor_id=mentor.id,
                message_content=message_content
            )

            if result["success"]:
                return result.get("intelligent_suggestions", [])

        except Exception as e:
            logger.warning(f"Failed to get agent suggestions: {e}")

        return []

    def _log_agent_interaction(self, student: UserProfile, mentor: UserProfile, result: dict) -> None:
        """Log interaction from agent system"""
        try:
            interaction_data = {
                'system': 'langgraph_agents',
                'mentor_id': mentor.id,
                'student_id': student.id,
                'success': result.get('success'),
                'auto_respond': result.get('should_auto_respond'),
                'decision_reason': result.get('decision_reason'),
                'confidence_score': result.get('confidence_score'),
                'response_length': len(result.get('final_response', '')),
                'suggestions_count': len(result.get('intelligent_suggestions', [])),
                'processing_status': result.get('processing_status'),
                'errors_count': len(result.get('errors', [])),
                'timestamp': timezone.now().isoformat()
            }

            logger.info(f"Agent interaction logged: {interaction_data}")

        except Exception as e:
            logger.warning(f"Failed to log agent interaction: {e}")

    def _ai_features_enabled(self, user: UserProfile) -> bool:
        """Check if AI features are enabled for this user"""
        return (hasattr(settings, "TOPIC_SUMMARIZATION_MODEL") and
                settings.TOPIC_SUMMARIZATION_MODEL is not None and
                user.can_summarize_topics())


# Main entry point for processing potential AI responses
def handle_potential_ai_response(student_message: dict[str, Any]) -> str | None:
    """
    Main entry point for processing potential AI responses using LangGraph agents

    Called when a student sends a message to a mentor
    """
    try:
        student = UserProfile.objects.get(id=student_message["sender_id"])
        mentor = UserProfile.objects.get(id=student_message["recipient_id"])

        # Verify this is a mentor-student interaction
        if mentor.role != UserProfile.ROLE_MENTOR or student.role != UserProfile.ROLE_STUDENT:
            return None

        # Check if they can communicate (existing Zulip permission system)
        if not student.can_communicate_with(mentor):
            return None

        # Initialize AI engine
        ai_engine = AIMentorResponseEngine()

        # Process message and potentially generate response
        ai_response = ai_engine.process_student_message(
            student=student,
            mentor=mentor,
            message_content=student_message["content"]
        )

        return ai_response

    except (UserProfile.DoesNotExist, KeyError, Exception) as e:
        # Log error and return None - fail gracefully
        logger.error(f"Error in handle_potential_ai_response: {e}")

        try:
            # Try to get user info for error notification
            if 'sender_id' in student_message and 'recipient_id' in student_message:
                try:
                    student = UserProfile.objects.get(id=student_message["sender_id"])
                    mentor = UserProfile.objects.get(id=student_message["recipient_id"])

                    notify_ai_error(
                        mentor=mentor,
                        student=student,
                        error_type="processing_error",
                        error_message=str(e),
                        context={"student_message_keys": list(student_message.keys())}
                    )
                except Exception:
                    # If we can't get user info, just pass
                    pass
        except Exception:
            # Don't fail on error notification failure
            pass

        return None
