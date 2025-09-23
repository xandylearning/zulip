"""
AI Mentor Events System

This module defines events for the AI mentor response feature and provides
functions to trigger and handle these events within Zulip's event system.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from django.utils.timezone import now as timezone_now

from zerver.lib.event_types import UserGroupMembersDict
from zerver.lib.users import get_user_profile_by_id_in_realm
from zerver.models import Message, Realm, UserProfile
from zerver.tornado.django_api import send_event_on_commit

logger = logging.getLogger(__name__)


def send_ai_mentor_response_event(
    realm: Realm,
    mentor: UserProfile,
    student: UserProfile,
    original_message: str,
    ai_response: str,
    style_confidence: float,
    decision_reason: str,
    message_id: int,
) -> None:
    """
    Send event when AI generates a mentor response

    This event notifies relevant users that an AI response was generated
    on behalf of a mentor.
    """
    event = {
        "type": "ai_mentor_response",
        "id": message_id,
        "mentor": {
            "user_id": mentor.id,
            "full_name": mentor.full_name,
            "email": mentor.email,
        },
        "student": {
            "user_id": student.id,
            "full_name": student.full_name,
            "email": student.email,
        },
        "original_message_preview": original_message[:100] + "..." if len(original_message) > 100 else original_message,
        "ai_response_preview": ai_response[:100] + "..." if len(ai_response) > 100 else ai_response,
        "style_confidence": style_confidence,
        "decision_reason": decision_reason,
        "timestamp": timezone_now().isoformat(),
        "ai_generated": True,
        "requires_mentor_review": style_confidence < 0.8,  # Flag low-confidence responses
    }

    # Send to mentor (primary recipient)
    mentor_users = [mentor.id]

    # Send to realm admins for monitoring
    admin_users = [admin.id for admin in realm.get_human_admin_users()]

    # Send to student if they have AI notifications enabled
    recipient_users = mentor_users + admin_users
    if not student.hide_ai_features:
        recipient_users.append(student.id)

    send_event_on_commit(realm, event, recipient_users)

    # Log the event for audit purposes
    logger.info(
        f"AI mentor response event sent: mentor={mentor.id}, student={student.id}, "
        f"confidence={style_confidence}, reason={decision_reason}"
    )


def send_ai_mentor_style_analysis_event(
    realm: Realm,
    mentor: UserProfile,
    style_profile: Dict[str, Any],
    analysis_type: str = "periodic",
) -> None:
    """
    Send event when mentor style analysis is updated

    This event notifies mentors when their communication style
    has been analyzed or updated.
    """
    event = {
        "type": "ai_mentor_style_analysis",
        "mentor": {
            "user_id": mentor.id,
            "full_name": mentor.full_name,
            "email": mentor.email,
        },
        "style_profile": {
            "confidence_score": style_profile.get("confidence_score", 0.0),
            "dominant_tone": _get_dominant_pattern(style_profile.get("tone_patterns", {})),
            "teaching_approach": _get_dominant_pattern(style_profile.get("teaching_approach", {})),
            "message_count_analyzed": style_profile.get("message_count", 0),
            "last_updated": style_profile.get("last_updated", timezone_now().isoformat()),
        },
        "analysis_type": analysis_type,  # "initial", "periodic", "manual"
        "timestamp": timezone_now().isoformat(),
        "recommendations": _generate_style_recommendations(style_profile),
    }

    # Send only to the mentor and realm admins
    recipient_users = [mentor.id] + [admin.id for admin in realm.get_human_admin_users()]

    send_event_on_commit(realm, event, recipient_users)

    logger.info(
        f"AI mentor style analysis event sent: mentor={mentor.id}, "
        f"confidence={style_profile.get('confidence_score', 0.0)}, type={analysis_type}"
    )


def send_ai_mentor_settings_change_event(
    realm: Realm,
    mentor: UserProfile,
    setting_name: str,
    old_value: Any,
    new_value: Any,
    changed_by: UserProfile,
) -> None:
    """
    Send event when AI mentor settings are changed

    This event notifies when mentor AI preferences are updated.
    """
    event = {
        "type": "ai_mentor_settings_change",
        "mentor": {
            "user_id": mentor.id,
            "full_name": mentor.full_name,
            "email": mentor.email,
        },
        "changed_by": {
            "user_id": changed_by.id,
            "full_name": changed_by.full_name,
            "email": changed_by.email,
        },
        "setting": {
            "name": setting_name,
            "old_value": old_value,
            "new_value": new_value,
        },
        "timestamp": timezone_now().isoformat(),
    }

    # Send to mentor and the user who made the change (if different)
    recipient_users = [mentor.id]
    if changed_by.id != mentor.id:
        recipient_users.append(changed_by.id)

    # Send to realm admins
    recipient_users.extend([admin.id for admin in realm.get_human_admin_users()])

    send_event_on_commit(realm, event, recipient_users)

    logger.info(
        f"AI mentor settings change event sent: mentor={mentor.id}, "
        f"setting={setting_name}, changed_by={changed_by.id}"
    )


def send_ai_mentor_interaction_stats_event(
    realm: Realm,
    mentor: UserProfile,
    stats_period: str,
    stats_data: Dict[str, Any],
) -> None:
    """
    Send event with AI mentor interaction statistics

    This event provides periodic statistics about AI mentor activity.
    """
    event = {
        "type": "ai_mentor_interaction_stats",
        "mentor": {
            "user_id": mentor.id,
            "full_name": mentor.full_name,
            "email": mentor.email,
        },
        "period": stats_period,  # "daily", "weekly", "monthly"
        "stats": {
            "total_responses": stats_data.get("total_responses", 0),
            "auto_responses": stats_data.get("auto_responses", 0),
            "manual_responses": stats_data.get("manual_responses", 0),
            "avg_response_time": stats_data.get("avg_response_time", 0.0),
            "student_satisfaction": stats_data.get("student_satisfaction", 0.0),
            "style_confidence_avg": stats_data.get("style_confidence_avg", 0.0),
            "top_decision_reasons": stats_data.get("top_decision_reasons", []),
        },
        "timestamp": timezone_now().isoformat(),
        "period_start": stats_data.get("period_start"),
        "period_end": stats_data.get("period_end"),
    }

    # Send to mentor and realm admins
    recipient_users = [mentor.id] + [admin.id for admin in realm.get_human_admin_users()]

    send_event_on_commit(realm, event, recipient_users)

    logger.info(
        f"AI mentor stats event sent: mentor={mentor.id}, period={stats_period}, "
        f"responses={stats_data.get('total_responses', 0)}"
    )


def send_ai_mentor_error_event(
    realm: Realm,
    mentor: UserProfile,
    student: UserProfile,
    error_type: str,
    error_message: str,
    context: Dict[str, Any],
) -> None:
    """
    Send event when AI mentor system encounters an error

    This event notifies administrators of AI system errors.
    """
    event = {
        "type": "ai_mentor_error",
        "mentor": {
            "user_id": mentor.id,
            "full_name": mentor.full_name,
            "email": mentor.email,
        },
        "student": {
            "user_id": student.id,
            "full_name": student.full_name,
            "email": student.email,
        },
        "error": {
            "type": error_type,
            "message": error_message,
            "severity": _classify_error_severity(error_type),
        },
        "context": context,
        "timestamp": timezone_now().isoformat(),
        "requires_intervention": _requires_admin_intervention(error_type),
    }

    # Send to realm admins only for error monitoring
    recipient_users = [admin.id for admin in realm.get_human_admin_users()]

    send_event_on_commit(realm, event, recipient_users)

    logger.error(
        f"AI mentor error event sent: mentor={mentor.id}, student={student.id}, "
        f"error_type={error_type}, message={error_message}"
    )


def send_ai_agent_conversation_event(
    realm: Realm,
    mentor: UserProfile,
    student: UserProfile,
    original_message: str,
    ai_response_data: Dict[str, Any],
) -> None:
    """
    Send event to trigger AI agent conversation processing

    This event initiates the AI agent workflow for generating mentor responses.
    """
    event = {
        "type": "ai_agent_conversation",
        "mentor": {
            "user_id": mentor.id,
            "full_name": mentor.full_name,
            "email": mentor.email,
        },
        "student": {
            "user_id": student.id,
            "full_name": student.full_name,
            "email": student.email,
        },
        "message_data": {
            "content": original_message,
            "message_id": ai_response_data.get("original_message_id"),
            "sender_id": student.id,
            "recipient_id": mentor.id,
        },
        "processing_request": {
            "trigger_type": "student_message",
            "urgency_level": "normal",
            "require_response": True,
            "max_response_time_minutes": 30,
        },
        "timestamp": timezone_now().isoformat(),
        "realm_id": realm.id,
    }

    # Send to specialized AI agent event handler (not general users)
    # This will be processed by the AI agent event listener
    send_event_on_commit(realm, event, [])

    # Dispatch to AI agent event listener immediately for processing
    try:
        from zerver.event_listeners.ai_mentor import handle_ai_agent_conversation
        handle_ai_agent_conversation(event)
    except Exception as e:
        logger.error(f"Failed to dispatch AI agent conversation event: {e}", exc_info=True)

    # Log the conversation trigger
    logger.info(
        f"AI agent conversation event triggered: mentor={mentor.id}, student={student.id}, "
        f"message_id={ai_response_data.get('original_message_id')}"
    )


def send_ai_mentor_feedback_event(
    realm: Realm,
    mentor: UserProfile,
    student: UserProfile,
    message_id: int,
    feedback_type: str,
    feedback_score: Optional[float] = None,
    feedback_comment: Optional[str] = None,
) -> None:
    """
    Send event when users provide feedback on AI mentor responses

    This event captures user feedback for improving the AI system.
    """
    event = {
        "type": "ai_mentor_feedback",
        "message_id": message_id,
        "mentor": {
            "user_id": mentor.id,
            "full_name": mentor.full_name,
            "email": mentor.email,
        },
        "student": {
            "user_id": student.id,
            "full_name": student.full_name,
            "email": student.email,
        },
        "feedback": {
            "type": feedback_type,  # "helpful", "not_helpful", "inappropriate", "rating"
            "score": feedback_score,  # 1-5 rating if applicable
            "comment": feedback_comment,
        },
        "timestamp": timezone_now().isoformat(),
    }

    # Send to mentor and realm admins for feedback analysis
    recipient_users = [mentor.id] + [admin.id for admin in realm.get_human_admin_users()]

    send_event_on_commit(realm, event, recipient_users)

    logger.info(
        f"AI mentor feedback event sent: mentor={mentor.id}, student={student.id}, "
        f"type={feedback_type}, score={feedback_score}"
    )


# Helper functions

def _get_dominant_pattern(patterns: Dict[str, float]) -> str:
    """Get the most dominant pattern from a dictionary of pattern scores"""
    if not patterns:
        return "unknown"
    return max(patterns.items(), key=lambda x: x[1])[0]


def _generate_style_recommendations(style_profile: Dict[str, Any]) -> List[str]:
    """Generate recommendations based on style analysis"""
    recommendations = []

    confidence = style_profile.get("confidence_score", 0.0)
    if confidence < 0.6:
        recommendations.append("Consider sending more varied messages to improve AI style analysis")

    tone_patterns = style_profile.get("tone_patterns", {})
    if tone_patterns.get("questioning", 0) > 0.8:
        recommendations.append("Your questioning style promotes critical thinking")
    elif tone_patterns.get("supportive", 0) > 0.8:
        recommendations.append("Your supportive approach helps build student confidence")

    teaching_approach = style_profile.get("teaching_approach", {})
    if teaching_approach.get("resource_sharing", 0) > 0.7:
        recommendations.append("Consider balancing resource sharing with direct explanation")

    return recommendations


def _classify_error_severity(error_type: str) -> str:
    """Classify error severity level"""
    high_severity_errors = ["ai_api_failure", "style_analysis_corruption", "security_violation"]
    medium_severity_errors = ["rate_limit_exceeded", "invalid_context", "timeout"]

    if error_type in high_severity_errors:
        return "high"
    elif error_type in medium_severity_errors:
        return "medium"
    else:
        return "low"


def _requires_admin_intervention(error_type: str) -> bool:
    """Determine if error requires immediate admin intervention"""
    critical_errors = ["security_violation", "ai_api_failure", "data_corruption"]
    return error_type in critical_errors


# Convenience functions for common event triggers

def notify_ai_response_generated(
    mentor: UserProfile,
    student: UserProfile,
    original_message: str,
    ai_response: str,
    style_confidence: float,
    decision_reason: str,
    message_id: int,
) -> None:
    """Convenience function to notify when AI response is generated"""
    send_ai_mentor_response_event(
        realm=mentor.realm,
        mentor=mentor,
        student=student,
        original_message=original_message,
        ai_response=ai_response,
        style_confidence=style_confidence,
        decision_reason=decision_reason,
        message_id=message_id,
    )


def notify_style_analysis_updated(
    mentor: UserProfile,
    style_profile: Dict[str, Any],
    analysis_type: str = "periodic",
) -> None:
    """Convenience function to notify when style analysis is updated"""
    send_ai_mentor_style_analysis_event(
        realm=mentor.realm,
        mentor=mentor,
        style_profile=style_profile,
        analysis_type=analysis_type,
    )


def notify_ai_error(
    mentor: UserProfile,
    student: UserProfile,
    error_type: str,
    error_message: str,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Convenience function to notify of AI system errors"""
    send_ai_mentor_error_event(
        realm=mentor.realm,
        mentor=mentor,
        student=student,
        error_type=error_type,
        error_message=error_message,
        context=context or {},
    )


def trigger_ai_agent_conversation(
    mentor: UserProfile,
    student: UserProfile,
    original_message: str,
    original_message_id: int,
) -> None:
    """Convenience function to trigger AI agent conversation processing"""
    ai_response_data = {
        "original_message_id": original_message_id,
        "trigger_timestamp": timezone_now().isoformat(),
    }

    send_ai_agent_conversation_event(
        realm=mentor.realm,
        mentor=mentor,
        student=student,
        original_message=original_message,
        ai_response_data=ai_response_data,
    )


def send_ai_message_created_event(
    realm: Realm,
    message_id: int,
    ai_metadata: Dict[str, Any],
    mentor: UserProfile,
    student: UserProfile,
) -> None:
    """
    Send event when AI message is created for monitoring and analytics
    """
    event = {
        "type": "ai_message_created",
        "message_id": message_id,
        "ai_metadata": ai_metadata,
        "mentor_id": mentor.id,
        "student_id": student.id,
        "realm_id": realm.id,
        "timestamp": timezone_now().isoformat(),
    }

    # Send to event system
    send_event_on_commit(realm, event, [])

    # Dispatch to monitoring listeners
    try:
        from zerver.event_listeners.ai_message_monitor import handle_ai_message_created
        handle_ai_message_created(event)
    except Exception as e:
        logger.error(f"Failed to dispatch AI message created event: {e}", exc_info=True)

    logger.info(
        f"AI message created event sent: message_id={message_id}, "
        f"mentor={mentor.id}, student={student.id}"
    )


def send_ai_agent_performance_event(
    realm: Realm,
    agent_type: str,
    processing_time_ms: int,
    success: bool,
    error_message: str = None,
    token_usage: int = 0,
    confidence_score: float = None,
) -> None:
    """
    Send event for AI agent performance monitoring
    """
    event = {
        "type": "ai_agent_performance",
        "agent_type": agent_type,
        "processing_time_ms": processing_time_ms,
        "success": success,
        "error_message": error_message,
        "token_usage": token_usage,
        "confidence_score": confidence_score,
        "timestamp": timezone_now().isoformat(),
        "realm_id": realm.id,
    }

    # Send to event system
    send_event_on_commit(realm, event, [])

    # Dispatch to monitoring listeners
    try:
        from zerver.event_listeners.ai_message_monitor import handle_ai_agent_performance
        handle_ai_agent_performance(event)
    except Exception as e:
        logger.error(f"Failed to dispatch AI agent performance event: {e}", exc_info=True)