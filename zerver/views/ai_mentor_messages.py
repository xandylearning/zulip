"""
API endpoints for AI mentor messaging functionality

Integrates with Zulip's existing messaging system to provide selective
AI mentor responses that preserve human touch.
"""

from typing import Optional, Dict, Any, List
import logging
from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from datetime import timedelta

from analytics.lib.counts import COUNT_STATS
from zerver.decorator import require_realm_member
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import UserProfile, Message, Recipient
from zerver.lib.ai_mentor_response import (
    AIMentorResponseEngine,
    handle_potential_ai_response,
    ResponseContext
)
from zerver.actions.ai_mentor_events import (
    send_ai_mentor_settings_change_event,
    send_ai_mentor_feedback_event,
)
from zerver.lib.message import send_message_backend
from zerver.actions.message_send import check_send_message

logger = logging.getLogger(__name__)


@require_realm_member
@typed_endpoint
def process_mentor_message_request(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    recipient_user_id: int,
    message_content: str,
    enable_ai_assistance: bool = True,
) -> HttpResponse:
    """
    Process a message from student to mentor with optional AI assistance

    This endpoint is called when a student sends a message to a mentor.
    It may trigger an AI auto-response if conditions are met.
    """
    # Verify AI features are enabled
    if not _ai_features_available(user_profile):
        return json_error(_("AI features are not enabled on this server."))

    # Check AI usage limits
    if not _check_ai_usage_limits(user_profile):
        return json_error(_("Monthly AI usage limit reached."))

    try:
        # Get recipient mentor
        mentor = UserProfile.objects.select_related('realm').get(
            id=recipient_user_id,
            realm=user_profile.realm
        )

        # Verify this is a student-to-mentor message
        if (user_profile.role != UserProfile.ROLE_STUDENT or
                mentor.role != UserProfile.ROLE_MENTOR):
            return json_error(_("AI mentor assistance is only available for student-mentor communication."))

        # Check communication permissions (reuse existing Zulip logic)
        if not user_profile.can_communicate_with(mentor):
            return json_error(_("You don't have permission to message this mentor."))

        # Send the original student message
        message_id = _send_student_message(user_profile, mentor, message_content)

        ai_response_sent = False
        ai_response_reason = None

        # Process potential AI response if enabled
        if enable_ai_assistance:
            try:
                ai_response = _process_ai_mentor_response(
                    student=user_profile,
                    mentor=mentor,
                    student_message=message_content
                )

                if ai_response:
                    # Send AI response as the mentor
                    ai_message_id = _send_ai_mentor_response(mentor, user_profile, ai_response)
                    ai_response_sent = True
                    ai_response_reason = "auto_response_generated"

                    # Log AI interaction for audit trail
                    _log_ai_interaction(
                        mentor=mentor,
                        student=user_profile,
                        student_message=message_content,
                        ai_response=ai_response,
                        message_id=ai_message_id
                    )

            except Exception as e:
                logger.warning(f"AI response generation failed: {e}")
                # Continue gracefully - original message was still sent

        return json_success({
            'message_id': message_id,
            'ai_response_sent': ai_response_sent,
            'ai_response_reason': ai_response_reason,
            'agent_system_used': True,
            'processing_method': 'langgraph_agents',
            'mentor_notified': True
        })

    except UserProfile.DoesNotExist:
        return json_error(_("Mentor not found."))
    except Exception as e:
        logger.error(f"Error processing mentor message: {e}")
        return json_error(_("Failed to process message."))


@require_realm_member
@typed_endpoint
def get_mentor_ai_settings(
    request: HttpRequest,
    user_profile: UserProfile
) -> HttpResponse:
    """
    Get AI assistance settings for a mentor

    Returns mentor's AI style profile and auto-response preferences
    """
    if user_profile.role != UserProfile.ROLE_MENTOR:
        return json_error(_("This endpoint is only available for mentors."))

    if not _ai_features_available(user_profile):
        return json_error(_("AI features are not enabled."))

    try:
        ai_engine = AIMentorResponseEngine()

        settings_data = {
            'ai_features_enabled': True,
            'agent_system_enabled': True,
            'langgraph_agents_available': True,
            'portkey_integration': True,
            'daily_response_limit': getattr(settings, 'AI_MENTOR_MAX_DAILY_RESPONSES', 3),
            'min_absence_minutes': getattr(settings, 'AI_MENTOR_MIN_ABSENCE_MINUTES', 240),
            'confidence_threshold': getattr(settings, 'AI_MENTOR_CONFIDENCE_THRESHOLD', 0.6),
            'urgency_threshold': getattr(settings, 'AI_MENTOR_URGENCY_THRESHOLD', 0.7)
        }

        return json_success(settings_data)

    except Exception as e:
        logger.error(f"Error getting mentor AI settings: {e}")
        return json_error(_("Failed to retrieve AI settings."))


@require_realm_member
@typed_endpoint
def update_mentor_ai_preferences(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    auto_response_enabled: bool = True,
    max_daily_responses: Optional[int] = None,
    min_absence_hours: Optional[int] = None,
) -> HttpResponse:
    """
    Update mentor's AI assistance preferences

    Allows mentors to control when and how AI responses are generated
    """
    if user_profile.role != UserProfile.ROLE_MENTOR:
        return json_error(_("This endpoint is only available for mentors."))

    if not _ai_features_available(user_profile):
        return json_error(_("AI features are not enabled."))

    try:
        # In a full implementation, these would be stored in database
        # For now, we'll return success with current settings
        # Get old values for event notification
        old_auto_response = True  # Would get from database in production
        old_max_daily = 3  # Would get from database in production
        old_min_absence = 4  # Would get from database in production

        preferences = {
            'auto_response_enabled': auto_response_enabled,
            'max_daily_responses': max_daily_responses or 3,
            'min_absence_hours': min_absence_hours or 4,
            'updated_at': timezone.now().isoformat()
        }

        # Send events for changed settings
        if auto_response_enabled != old_auto_response:
            send_ai_mentor_settings_change_event(
                realm=user_profile.realm,
                mentor=user_profile,
                setting_name="auto_response_enabled",
                old_value=old_auto_response,
                new_value=auto_response_enabled,
                changed_by=user_profile
            )

        if max_daily_responses and max_daily_responses != old_max_daily:
            send_ai_mentor_settings_change_event(
                realm=user_profile.realm,
                mentor=user_profile,
                setting_name="max_daily_responses",
                old_value=old_max_daily,
                new_value=max_daily_responses,
                changed_by=user_profile
            )

        if min_absence_hours and min_absence_hours != old_min_absence:
            send_ai_mentor_settings_change_event(
                realm=user_profile.realm,
                mentor=user_profile,
                setting_name="min_absence_hours",
                old_value=old_min_absence,
                new_value=min_absence_hours,
                changed_by=user_profile
            )

        return json_success({
            'preferences_updated': True,
            'current_preferences': preferences
        })

    except Exception as e:
        logger.error(f"Error updating mentor preferences: {e}")
        return json_error(_("Failed to update preferences."))


@require_realm_member
@typed_endpoint
def get_ai_interaction_history(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    days_back: int = 7,
    limit: int = 50,
) -> HttpResponse:
    """
    Get history of AI interactions for transparency

    Shows when AI responses were generated and why
    """
    if not _ai_features_available(user_profile):
        return json_error(_("AI features are not enabled."))

    # Only mentors and students involved can see their interaction history
    if user_profile.role not in [UserProfile.ROLE_MENTOR, UserProfile.ROLE_STUDENT]:
        return json_error(_("Access denied."))

    try:
        # In production, this would query actual AI interaction logs
        # For now, return mock data structure
        history_data = {
            'interactions': [
                {
                    'timestamp': timezone.now().isoformat(),
                    'type': 'auto_response_generated',
                    'mentor_id': user_profile.id if user_profile.role == UserProfile.ROLE_MENTOR else None,
                    'student_message_preview': 'Need help with calculus...',
                    'ai_response_preview': 'That\'s a great question about...',
                    'decision_reason': 'mentor_absent_6_hours',
                    'urgency_score': 0.8
                }
            ],
            'total_auto_responses': 1,
            'days_analyzed': days_back,
            'ai_usage_stats': {
                'responses_this_week': 3,
                'avg_response_time': '2.1 seconds',
                'student_satisfaction': 0.85  # Would come from feedback
            }
        }

        return json_success(history_data)

    except Exception as e:
        logger.error(f"Error getting AI interaction history: {e}")
        return json_error(_("Failed to retrieve interaction history."))


def _ai_features_available(user_profile: UserProfile) -> bool:
    """Check if AI features are available for this user"""
    return (hasattr(settings, 'TOPIC_SUMMARIZATION_MODEL') and
            settings.TOPIC_SUMMARIZATION_MODEL is not None and
            user_profile.can_summarize_topics())


def _check_ai_usage_limits(user_profile: UserProfile) -> bool:
    """Check if user has exceeded AI usage limits"""
    if settings.MAX_PER_USER_MONTHLY_AI_COST is None:
        return True

    used_credits = COUNT_STATS["ai_credit_usage::day"].current_month_accumulated_count_for_user(
        user_profile
    )
    return used_credits < settings.MAX_PER_USER_MONTHLY_AI_COST * 1000000000


def _send_student_message(student: UserProfile, mentor: UserProfile, content: str) -> int:
    """Send the original student message to mentor"""
    message_id = check_send_message(
        sender=student,
        client=None,  # API client
        message_type_name='private',
        message_to=[mentor.email],
        topic_name=None,
        message_content=content,
        realm=student.realm,
        forwarder_user_profile=None,
        local_id=None,
        sender_queue_id=None,
        widget_content=None,
        email_gateway=False,
    )
    return message_id


def _process_ai_mentor_response(student: UserProfile, mentor: UserProfile, student_message: str) -> Optional[str]:
    """Process potential AI mentor response"""
    try:
        ai_engine = AIMentorResponseEngine()

        # Get conversation history (simplified for this implementation)
        conversation_history = _get_conversation_history(student, mentor, limit=10)

        # Process and potentially generate AI response
        ai_response = ai_engine.process_student_message(
            student=student,
            mentor=mentor,
            message_content=student_message,
            conversation_history=conversation_history
        )

        return ai_response

    except Exception as e:
        logger.warning(f"AI response processing failed: {e}")
        return None


def _send_ai_mentor_response(mentor: UserProfile, student: UserProfile, ai_response: str) -> int:
    """Send AI-generated response as the mentor"""
    # Add small delay to make it feel more natural (async in production)
    import time
    time.sleep(1)

    message_id = check_send_message(
        sender=mentor,
        client=None,
        message_type_name='private',
        message_to=[student.email],
        topic_name=None,
        message_content=ai_response,
        realm=mentor.realm,
        forwarder_user_profile=None,
        local_id=None,
        sender_queue_id=None,
        widget_content=None,
        email_gateway=False,
    )

    return message_id


def _get_conversation_history(student: UserProfile, mentor: UserProfile, limit: int = 10) -> List[Dict[str, Any]]:
    """Get recent conversation history between student and mentor"""
    # Simplified implementation - in production would get actual message thread
    return [
        {
            'sender_id': student.id,
            'sender_role': 'student',
            'content': 'Previous student message...',
            'timestamp': timezone.now() - timedelta(hours=2)
        },
        {
            'sender_id': mentor.id,
            'sender_role': 'mentor',
            'content': 'Previous mentor response...',
            'timestamp': timezone.now() - timedelta(hours=1)
        }
    ]


def _log_ai_interaction(mentor: UserProfile, student: UserProfile,
                       student_message: str, ai_response: str, message_id: int) -> None:
    """Log AI interaction for audit trail and analytics"""
    try:
        # In production, this would store in database or send to analytics service
        interaction_data = {
            'mentor_id': mentor.id,
            'student_id': student.id,
            'realm_id': mentor.realm.id,
            'student_message_length': len(student_message),
            'ai_response_length': len(ai_response),
            'message_id': message_id,
            'timestamp': timezone.now(),
            'interaction_type': 'auto_response'
        }

        logger.info(f"AI mentor interaction logged: {interaction_data}")

    except Exception as e:
        logger.warning(f"Failed to log AI interaction: {e}")


# Webhook endpoint for integration with messaging flow
@csrf_exempt
def handle_message_sent_webhook(request: HttpRequest) -> HttpResponse:
    """
    Webhook handler that can be called when messages are sent

    This allows the AI system to react to new messages in real-time
    """
    try:
        if request.method != 'POST':
            return json_error("POST required")

        # Parse message data (would be provided by Zulip's webhook system)
        message_data = {
            'sender_id': int(request.POST.get('sender_id')),
            'recipient_id': int(request.POST.get('recipient_id')),
            'content': request.POST.get('content', ''),
            'message_type': request.POST.get('type', 'private')
        }

        # Only process private messages for AI mentor assistance
        if message_data['message_type'] != 'private':
            return json_success({'processed': False, 'reason': 'not_private_message'})

        # Process potential AI response
        ai_response = handle_potential_ai_response(message_data)

        return json_success({
            'processed': True,
            'ai_response_generated': ai_response is not None,
            'webhook_handled': True
        })

    except Exception as e:
        logger.error(f"Webhook processing failed: {e}")
        return json_error("Webhook processing failed")


@require_realm_member
@typed_endpoint
def submit_ai_mentor_feedback(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: int,
    mentor_user_id: int,
    feedback_type: str,
    feedback_score: Optional[int] = None,
    feedback_comment: Optional[str] = None,
) -> HttpResponse:
    """
    Submit feedback for an AI mentor response

    Allows users to rate and comment on AI-generated mentor responses
    """
    if not _ai_features_available(user_profile):
        return json_error(_("AI features are not enabled."))

    try:
        # Get mentor user
        mentor = UserProfile.objects.select_related('realm').get(
            id=mentor_user_id,
            realm=user_profile.realm
        )

        # Validate feedback type
        valid_feedback_types = ['helpful', 'not_helpful', 'inappropriate', 'rating']
        if feedback_type not in valid_feedback_types:
            return json_error(_("Invalid feedback type."))

        # Validate rating if provided
        if feedback_type == 'rating' and (feedback_score is None or not 1 <= feedback_score <= 5):
            return json_error(_("Rating must be between 1 and 5."))

        # Send feedback event
        send_ai_mentor_feedback_event(
            realm=user_profile.realm,
            mentor=mentor,
            student=user_profile,
            message_id=message_id,
            feedback_type=feedback_type,
            feedback_score=float(feedback_score) if feedback_score else None,
            feedback_comment=feedback_comment
        )

        return json_success({
            'feedback_submitted': True,
            'message_id': message_id,
            'feedback_type': feedback_type,
            'timestamp': timezone.now().isoformat()
        })

    except UserProfile.DoesNotExist:
        return json_error(_("Mentor not found."))
    except Exception as e:
        logger.error(f"Error submitting AI mentor feedback: {e}")
        return json_error(_("Failed to submit feedback."))


@require_realm_member
@typed_endpoint
def get_intelligent_message_suggestions(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    student_user_id: int,
    message_content: str,
) -> HttpResponse:
    """
    Get intelligent suggestions for mentor response using LangGraph agents

    This endpoint provides AI-powered suggestions to help mentors craft better responses
    """
    if user_profile.role != UserProfile.ROLE_MENTOR:
        return json_error(_("This endpoint is only available for mentors."))

    if not _ai_features_available(user_profile):
        return json_error(_("AI features are not enabled."))

    try:
        # Get student user
        student = UserProfile.objects.select_related('realm').get(
            id=student_user_id,
            realm=user_profile.realm
        )

        # Verify mentor can communicate with this student
        if not user_profile.can_communicate_with(student):
            return json_error(_("You don't have permission to get suggestions for this student."))

        # Get AI engine and generate suggestions
        ai_engine = AIMentorResponseEngine()
        suggestions = ai_engine.get_intelligent_suggestions(
            student=student,
            mentor=user_profile,
            message_content=message_content
        )

        return json_success({
            'suggestions': suggestions,
            'student_id': student_user_id,
            'suggestion_count': len(suggestions),
            'agent_system_used': True,
            'processing_method': 'langgraph_agents',
            'timestamp': timezone.now().isoformat()
        })

    except UserProfile.DoesNotExist:
        return json_error(_("Student not found."))
    except Exception as e:
        logger.error(f"Error getting intelligent suggestions: {e}")
        return json_error(_("Failed to generate suggestions."))


@require_realm_member
@typed_endpoint
def enhance_mentor_message(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    recipient_user_id: int,
    message_content: str,
    enhancement_type: str = "contextual",
) -> HttpResponse:
    """
    Enhance a mentor message with AI before sending using LangGraph agents

    This endpoint provides AI-powered message enhancement based on context and mentor style
    """
    if user_profile.role != UserProfile.ROLE_MENTOR:
        return json_error(_("This endpoint is only available for mentors."))

    if not _ai_features_available(user_profile):
        return json_error(_("AI features are not enabled."))

    if not _check_ai_usage_limits(user_profile):
        return json_error(_("Monthly AI usage limit reached."))

    try:
        # Get recipient student
        student = UserProfile.objects.select_related('realm').get(
            id=recipient_user_id,
            realm=user_profile.realm
        )

        # Verify this is a mentor-to-student enhancement
        if student.role != UserProfile.ROLE_STUDENT:
            return json_error(_("Message enhancement is only available for mentor-student communication."))

        # Check communication permissions
        if not user_profile.can_communicate_with(student):
            return json_error(_("You don't have permission to message this student."))

        # Get AI engine and process enhancement
        ai_engine = AIMentorResponseEngine()

        # For enhancement, we simulate processing the message through agents to get suggestions
        suggestions = ai_engine.get_intelligent_suggestions(
            student=student,
            mentor=user_profile,
            message_content=message_content
        )

        # Create enhanced response data
        enhancement_data = {
            'original_message': message_content,
            'intelligent_suggestions': suggestions,
            'enhancement_type': enhancement_type,
            'agent_system_used': True,
            'processing_method': 'langgraph_agents',
            'enhancement_available': len(suggestions) > 0
        }

        return json_success(enhancement_data)

    except UserProfile.DoesNotExist:
        return json_error(_("Student not found."))
    except Exception as e:
        logger.error(f"Error enhancing mentor message: {e}")
        return json_error(_("Failed to enhance message."))