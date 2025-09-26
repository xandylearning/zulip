"""
AI Agent Core - LangGraph-based AI Messaging System

This module implements a sophisticated LangGraph agent architecture with Portkey
integration for AI mentor-student communication. It replaces the template-based
approach with a stateful, multi-agent workflow system.
"""

import json
import logging
import sqlite3
import time
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, TypedDict, Annotated

from django.conf import settings
from django.utils import timezone
from django.db import transaction

# LangGraph and LangChain imports
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig

# Portkey integration
try:
    from portkey_ai import Portkey, AsyncPortkey
    PORTKEY_AVAILABLE = True
except ImportError:
    PORTKEY_AVAILABLE = False

from zerver.models import UserProfile, Message, Realm
from zerver.actions.ai_mentor_events import (
    notify_ai_response_generated,
    notify_style_analysis_updated,
    notify_ai_error,
)

logger = logging.getLogger(__name__)


@dataclass
class PortkeyConfig:
    """Configuration for Portkey AI integration"""
    api_key: str
    base_url: str = "https://api.portkey.ai/v1"
    provider: str = "google"
    model: str = "@gemini/gemini-2.0-flash-001"
    max_retries: int = 3
    timeout: int = 30


class AgentState(TypedDict):
    """Shared state for the AI mentor agent workflow"""
    # Core message data
    messages: List[BaseMessage]
    student_id: int
    mentor_id: int
    realm_id: int

    # Context and analysis
    conversation_context: Dict[str, Any]
    mentor_style_profile: Dict[str, Any]
    student_profile: Dict[str, Any]
    urgency_assessment: Dict[str, Any]

    # Generated responses and suggestions
    response_candidates: List[Dict[str, Any]]
    intelligent_suggestions: List[Dict[str, Any]]
    final_response: str
    response_metadata: Dict[str, Any]

    # Decision and confidence tracking
    should_auto_respond: bool
    decision_reason: str
    confidence_score: float

    # Error handling
    errors: List[Dict[str, Any]]
    processing_status: str


class PortkeyLLMClient:
    """Robust Portkey client with error handling and retries"""

    def __init__(self, config: PortkeyConfig):
        if not PORTKEY_AVAILABLE:
            raise ImportError("Portkey AI not available. Install with: pip install portkey-ai")

        self.config = config
        self.client = Portkey(
            api_key=config.api_key,
            base_url=config.base_url
        )
        self.async_client = AsyncPortkey(
            api_key=config.api_key,
            base_url=config.base_url
        )

    def chat_completion(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """Synchronous chat completion with error handling"""
        for attempt in range(self.config.max_retries):
            try:
                response = self.client.chat.completions.create(
                    messages=messages,
                    model=kwargs.get('model', self.config.model),
                    temperature=kwargs.get('temperature', 0.7),
                    max_tokens=kwargs.get('max_tokens', 1000),
                    timeout=self.config.timeout
                )

                return {
                    "success": True,
                    "response": response,
                    "content": response.choices[0].message.content,
                    "usage": response.usage.dict() if response.usage else {},
                    "model": response.model,
                    "attempt": attempt + 1
                }

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "attempt": attempt + 1
                    }

                # Exponential backoff with jitter
                wait_time = (2 ** attempt) + (time.time() % 1)
                time.sleep(wait_time)

        return {"success": False, "error": "Max retries exceeded"}

    async def async_chat_completion(self, messages: List[Dict], **kwargs) -> Dict[str, Any]:
        """Asynchronous chat completion with error handling"""
        for attempt in range(self.config.max_retries):
            try:
                response = await self.async_client.chat.completions.create(
                    messages=messages,
                    model=kwargs.get('model', self.config.model),
                    temperature=kwargs.get('temperature', 0.7),
                    max_tokens=kwargs.get('max_tokens', 1000),
                    timeout=self.config.timeout
                )

                return {
                    "success": True,
                    "response": response,
                    "content": response.choices[0].message.content,
                    "usage": response.usage.dict() if response.usage else {},
                    "model": response.model,
                    "attempt": attempt + 1
                }

            except Exception as e:
                if attempt == self.config.max_retries - 1:
                    return {
                        "success": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "attempt": attempt + 1
                    }

                # Exponential backoff with jitter
                import asyncio
                wait_time = (2 ** attempt) + (time.time() % 1)
                await asyncio.sleep(wait_time)

        return {"success": False, "error": "Max retries exceeded"}


class MentorStyleAgent:
    """Agent specialized in analyzing mentor communication styles"""

    def __init__(self, llm_client: PortkeyLLMClient):
        self.llm_client = llm_client

    def analyze_mentor_style(self, state: AgentState) -> Dict[str, Any]:
        """Analyze mentor's communication style using AI"""
        try:
            mentor = UserProfile.objects.get(id=state["mentor_id"])

            # Get mentor's recent messages
            recent_messages = self._get_mentor_messages(mentor, limit=50)

            if len(recent_messages) < 5:
                return {
                    "mentor_style_profile": {
                        "confidence_score": 0.0,
                        "analysis_status": "insufficient_data",
                        "message_count": len(recent_messages)
                    }
                }

            # Create AI prompt for style analysis
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert communication style analyzer. Analyze the mentor's communication patterns from their message history and provide a detailed style profile.

Focus on:
1. Tone patterns (supportive, direct, encouraging, questioning)
2. Teaching approach (explanatory, resource-sharing, socratic, motivational)
3. Message structure and length preferences
4. Vocabulary and phrase patterns
5. Response timing characteristics

Return a JSON object with detailed analysis."""
                },
                {
                    "role": "user",
                    "content": f"""Analyze this mentor's communication style:

Mentor Messages:
{self._format_messages_for_analysis(recent_messages)}

Provide a comprehensive style analysis as JSON."""
                }
            ]

            response = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.3,  # Lower temperature for consistent analysis
                max_tokens=1500
            )

            if response["success"]:
                try:
                    style_analysis = json.loads(response["content"])
                    style_analysis["confidence_score"] = self._calculate_confidence(recent_messages)
                    style_analysis["message_count"] = len(recent_messages)
                    style_analysis["last_updated"] = timezone.now().isoformat()

                    return {"mentor_style_profile": style_analysis}
                except json.JSONDecodeError:
                    # Fallback to simple analysis
                    return self._fallback_style_analysis(recent_messages)
            else:
                return {
                    "mentor_style_profile": {
                        "confidence_score": 0.0,
                        "analysis_status": "llm_error",
                        "error": response.get("error")
                    }
                }

        except Exception as e:
            logger.error(f"Style analysis failed: {e}")
            return {
                "mentor_style_profile": {
                    "confidence_score": 0.0,
                    "analysis_status": "error",
                    "error": str(e)
                }
            }

    def _get_mentor_messages(self, mentor: UserProfile, limit: int = 50) -> List[Message]:
        """Get recent messages from mentor"""
        return Message.objects.filter(
            sender=mentor,
            realm=mentor.realm,
            date_sent__gte=timezone.now() - timedelta(days=90)
        ).order_by("-date_sent")[:limit]

    def _format_messages_for_analysis(self, messages: List[Message]) -> str:
        """Format messages for AI analysis"""
        formatted = []
        for i, msg in enumerate(messages[:20]):  # Limit to 20 most recent
            formatted.append(f"Message {i+1}: {msg.content[:200]}...")
        return "\n\n".join(formatted)

    def _calculate_confidence(self, messages: List[Message]) -> float:
        """Calculate confidence score based on data quality"""
        message_count = len(messages)
        count_confidence = min(1.0, message_count / 30)

        # Check date diversity
        unique_dates = len({msg.date_sent.date() for msg in messages})
        date_diversity = min(1.0, unique_dates / 10)

        # Check content diversity
        total_chars = sum(len(msg.content) for msg in messages)
        content_diversity = min(1.0, total_chars / 5000)

        return (count_confidence + date_diversity + content_diversity) / 3

    def _fallback_style_analysis(self, messages: List[Message]) -> Dict[str, Any]:
        """Fallback style analysis without AI"""
        # Simple keyword-based analysis
        all_content = " ".join([msg.content for msg in messages]).lower()

        tone_patterns = {
            "supportive": len([w for w in ["help", "support", "understand"] if w in all_content]) / len(messages),
            "encouraging": len([w for w in ["great", "excellent", "well done"] if w in all_content]) / len(messages),
            "questioning": all_content.count("?") / len(messages)
        }

        return {
            "mentor_style_profile": {
                "tone_patterns": tone_patterns,
                "confidence_score": 0.3,  # Low confidence for fallback
                "analysis_status": "fallback",
                "message_count": len(messages)
            }
        }


class ContextAnalysisAgent:
    """Agent specialized in analyzing conversation context and urgency"""

    def __init__(self, llm_client: PortkeyLLMClient):
        self.llm_client = llm_client

    def analyze_conversation_context(self, state: AgentState) -> Dict[str, Any]:
        """Analyze conversation context and assess urgency"""
        try:
            latest_message = state["messages"][-1] if state["messages"] else None
            if not latest_message:
                return {"conversation_context": {"urgency_level": 0.0}}

            # Get conversation history
            conversation_history = self._get_conversation_history(
                state["student_id"],
                state["mentor_id"],
                limit=10
            )

            # Create AI prompt for context analysis
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert conversation analyzer specializing in educational mentor-student interactions. Analyze the conversation context and assess urgency levels.

Evaluate:
1. Message urgency (0.0-1.0 scale)
2. Emotional tone and sentiment
3. Academic context and subject matter
4. Time sensitivity indicators
5. Student's learning needs

Return detailed analysis as JSON."""
                },
                {
                    "role": "user",
                    "content": f"""Analyze this mentor-student conversation:

Latest Student Message: {latest_message.content}

Recent Conversation History:
{self._format_conversation_history(conversation_history)}

Provide comprehensive context analysis as JSON with urgency assessment."""
                }
            ]

            response = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.4,
                max_tokens=1000
            )

            if response["success"]:
                try:
                    context_analysis = json.loads(response["content"])
                    context_analysis["analysis_timestamp"] = timezone.now().isoformat()
                    context_analysis["message_count_analyzed"] = len(conversation_history)

                    return {"conversation_context": context_analysis}
                except json.JSONDecodeError:
                    return self._fallback_context_analysis(latest_message.content)
            else:
                return self._fallback_context_analysis(latest_message.content)

        except Exception as e:
            logger.error(f"Context analysis failed: {e}")
            return {
                "conversation_context": {
                    "urgency_level": 0.5,  # Default medium urgency
                    "analysis_status": "error",
                    "error": str(e)
                }
            }

    def _get_conversation_history(self, student_id: int, mentor_id: int, limit: int = 10) -> List[Dict]:
        """Get recent conversation history between student and mentor"""
        # Simplified implementation - in production would get actual conversation thread
        try:
            recent_messages = Message.objects.filter(
                realm_id=UserProfile.objects.get(id=student_id).realm_id,
                sender_id__in=[student_id, mentor_id]
            ).order_by("-date_sent")[:limit]

            return [{
                "sender_id": msg.sender_id,
                "content": msg.content,
                "timestamp": msg.date_sent.isoformat(),
                "role": "student" if msg.sender_id == student_id else "mentor"
            } for msg in recent_messages]
        except Exception:
            return []

    def _format_conversation_history(self, history: List[Dict]) -> str:
        """Format conversation history for AI analysis"""
        formatted = []
        for msg in history:
            role = msg["role"].capitalize()
            content = msg["content"][:150] + "..." if len(msg["content"]) > 150 else msg["content"]
            formatted.append(f"{role}: {content}")
        return "\n".join(formatted)

    def _fallback_context_analysis(self, message_content: str) -> Dict[str, Any]:
        """Fallback context analysis without AI"""
        message_lower = message_content.lower()

        # Simple urgency indicators
        high_urgency_words = ["urgent", "asap", "emergency", "help", "stuck", "deadline"]
        medium_urgency_words = ["question", "clarify", "understand", "explain"]

        high_count = sum(1 for word in high_urgency_words if word in message_lower)
        medium_count = sum(1 for word in medium_urgency_words if word in message_lower)

        urgency_level = min(1.0, (high_count * 0.8 + medium_count * 0.4))

        return {
            "conversation_context": {
                "urgency_level": urgency_level,
                "sentiment": "neutral",
                "analysis_status": "fallback",
                "keywords_detected": {
                    "high_urgency": high_count,
                    "medium_urgency": medium_count
                }
            }
        }


class ResponseGenerationAgent:
    """Agent specialized in generating mentor-style responses"""

    def __init__(self, llm_client: PortkeyLLMClient):
        self.llm_client = llm_client

    def generate_response_candidates(self, state: AgentState) -> Dict[str, Any]:
        """Generate multiple response candidates using mentor's style"""
        try:
            mentor_style = state.get("mentor_style_profile", {})
            conversation_context = state.get("conversation_context", {})
            latest_message = state["messages"][-1] if state["messages"] else None

            if not latest_message or mentor_style.get("confidence_score", 0) < 0.3:
                return {"response_candidates": []}

            # Generate multiple response variants
            response_variants = []

            for i, tone in enumerate(["supportive", "questioning", "informative"]):
                messages = [
                    {
                        "role": "system",
                        "content": f"""You are an AI assistant that generates mentor responses mimicking a specific mentor's communication style.

Mentor Style Profile:
{json.dumps(mentor_style, indent=2)}

Conversation Context:
{json.dumps(conversation_context, indent=2)}

Generate a response that:
1. Matches the mentor's communication style exactly
2. Uses their typical tone: {tone}
3. Follows their teaching approach
4. Maintains their typical message length and structure
5. Uses vocabulary patterns they prefer

The response should feel authentic and indistinguishable from the actual mentor."""
                    },
                    {
                        "role": "user",
                        "content": f"""Student Message: {latest_message.content}

Generate a mentor response in the {tone} style that perfectly mimics this mentor's communication patterns."""
                    }
                ]

                response = self.llm_client.chat_completion(
                    messages=messages,
                    temperature=0.7 + (i * 0.1),  # Vary temperature for diversity
                    max_tokens=800
                )

                if response["success"]:
                    variant = {
                        "response_text": response["content"],
                        "style_variant": tone,
                        "generation_confidence": self._assess_response_quality(
                            response["content"],
                            mentor_style,
                            conversation_context
                        ),
                        "token_usage": response.get("usage", {}),
                        "model_used": response.get("model")
                    }
                    response_variants.append(variant)

            return {"response_candidates": response_variants}

        except Exception as e:
            logger.error(f"Response generation failed: {e}")
            return {
                "response_candidates": [],
                "errors": [{"type": "generation_error", "message": str(e)}]
            }

    def _assess_response_quality(self, response_text: str, mentor_style: Dict, context: Dict) -> float:
        """Assess the quality of generated response"""
        base_confidence = 0.7

        # Check length appropriateness
        expected_length = mentor_style.get("message_structure", {}).get("avg_length", 100)
        length_ratio = len(response_text) / max(expected_length, 50)
        length_score = 1.0 - abs(1.0 - length_ratio) * 0.5

        # Check for mentor's common phrases
        common_phrases = mentor_style.get("vocabulary_frequency", {}).get("phrases", {})
        phrase_score = 0.8  # Default if no phrase data

        if common_phrases:
            response_lower = response_text.lower()
            phrase_matches = sum(1 for phrase in common_phrases.keys() if phrase.lower() in response_lower)
            phrase_score = min(1.0, phrase_matches / 3)  # Normalize to 3 phrases

        # Combine scores
        return (base_confidence + length_score + phrase_score) / 3


class IntelligentSuggestionAgent:
    """Agent specialized in generating intelligent suggestions for mentors"""

    def __init__(self, llm_client: PortkeyLLMClient):
        self.llm_client = llm_client

    def generate_intelligent_suggestions(self, state: AgentState) -> Dict[str, Any]:
        """Generate intelligent suggestions for mentor response"""
        try:
            conversation_context = state.get("conversation_context", {})
            mentor_style = state.get("mentor_style_profile", {})
            student_profile = state.get("student_profile", {})
            latest_message = state["messages"][-1] if state["messages"] else None

            if not latest_message:
                return {"intelligent_suggestions": []}

            # Create AI prompt for suggestion generation
            messages = [
                {
                    "role": "system",
                    "content": """You are an expert educational mentor advisor. Generate intelligent suggestions to help mentors craft better responses to their students.

Provide 3-5 specific, actionable suggestions that include:
1. Content recommendations (what to address)
2. Tone adjustments (how to communicate)
3. Resource suggestions (materials to share)
4. Follow-up actions (next steps)
5. Teaching strategies (how to guide learning)

Each suggestion should be practical and immediately usable."""
                },
                {
                    "role": "user",
                    "content": f"""Student Message: {latest_message.content}

Mentor Style: {json.dumps(mentor_style, indent=2)}
Conversation Context: {json.dumps(conversation_context, indent=2)}
Student Profile: {json.dumps(student_profile, indent=2)}

Generate intelligent suggestions to help the mentor respond effectively."""
                }
            ]

            response = self.llm_client.chat_completion(
                messages=messages,
                temperature=0.6,
                max_tokens=1200
            )

            if response["success"]:
                try:
                    suggestions_data = json.loads(response["content"])
                    suggestions = suggestions_data if isinstance(suggestions_data, list) else [suggestions_data]

                    # Enhance suggestions with metadata
                    enhanced_suggestions = []
                    for i, suggestion in enumerate(suggestions):
                        if isinstance(suggestion, str):
                            suggestion = {"text": suggestion, "type": "general"}

                        suggestion.update({
                            "priority": self._calculate_suggestion_priority(suggestion, conversation_context),
                            "category": self._categorize_suggestion(suggestion),
                            "confidence": 0.8,
                            "suggestion_id": f"sug_{int(time.time())}_{i}"
                        })
                        enhanced_suggestions.append(suggestion)

                    return {"intelligent_suggestions": enhanced_suggestions}

                except json.JSONDecodeError:
                    # Parse as plain text and convert to suggestions
                    return self._parse_text_suggestions(response["content"])
            else:
                return self._fallback_suggestions(latest_message.content, conversation_context)

        except Exception as e:
            logger.error(f"Suggestion generation failed: {e}")
            return {
                "intelligent_suggestions": [],
                "errors": [{"type": "suggestion_error", "message": str(e)}]
            }

    def _calculate_suggestion_priority(self, suggestion: Dict, context: Dict) -> str:
        """Calculate priority level for suggestion"""
        urgency = context.get("urgency_level", 0.5)

        if urgency > 0.8:
            return "high"
        elif urgency > 0.5:
            return "medium"
        else:
            return "low"

    def _categorize_suggestion(self, suggestion: Dict) -> str:
        """Categorize suggestion type"""
        text = suggestion.get("text", "").lower()

        if any(word in text for word in ["resource", "material", "link", "reference"]):
            return "resource_sharing"
        elif any(word in text for word in ["question", "ask", "inquiry"]):
            return "questioning"
        elif any(word in text for word in ["encourage", "support", "motivate"]):
            return "encouragement"
        elif any(word in text for word in ["explain", "clarify", "elaborate"]):
            return "explanation"
        else:
            return "general"

    def _parse_text_suggestions(self, text_content: str) -> Dict[str, Any]:
        """Parse plain text into structured suggestions"""
        lines = [line.strip() for line in text_content.split('\n') if line.strip()]
        suggestions = []

        for i, line in enumerate(lines[:5]):  # Limit to 5 suggestions
            suggestions.append({
                "text": line,
                "type": "general",
                "priority": "medium",
                "category": "general",
                "confidence": 0.6,
                "suggestion_id": f"parsed_{int(time.time())}_{i}"
            })

        return {"intelligent_suggestions": suggestions}

    def _fallback_suggestions(self, message_content: str, context: Dict) -> Dict[str, Any]:
        """Generate fallback suggestions without AI"""
        message_lower = message_content.lower()
        suggestions = []

        if "?" in message_content:
            suggestions.append({
                "text": "Address the student's question directly and provide clear explanation",
                "type": "response_guidance",
                "priority": "high",
                "category": "explanation"
            })

        if any(word in message_lower for word in ["help", "stuck", "confused"]):
            suggestions.append({
                "text": "Offer specific guidance and break down complex concepts",
                "type": "teaching_strategy",
                "priority": "high",
                "category": "support"
            })

        urgency = context.get("urgency_level", 0.5)
        if urgency > 0.7:
            suggestions.append({
                "text": "Respond promptly due to high urgency indicators",
                "type": "timing_guidance",
                "priority": "high",
                "category": "urgency"
            })

        return {"intelligent_suggestions": suggestions}


class DecisionAgent:
    """Agent that makes decisions about auto-response triggering"""

    def __init__(self):
        self.min_mentor_absence_minutes = getattr(settings, 'AI_MENTOR_MIN_ABSENCE_MINUTES', 240)  # Default 4 hours
        self.max_auto_responses_per_day = getattr(settings, 'AI_MENTOR_MAX_DAILY_RESPONSES', 3)
        self.urgency_threshold = getattr(settings, 'AI_MENTOR_URGENCY_THRESHOLD', 0.7)
        self.confidence_threshold = getattr(settings, 'AI_MENTOR_CONFIDENCE_THRESHOLD', 0.6)

    def make_auto_response_decision(self, state: AgentState) -> Dict[str, Any]:
        """Decide whether to auto-respond and select best response"""
        try:
            mentor_style = state.get("mentor_style_profile", {})
            conversation_context = state.get("conversation_context", {})
            response_candidates = state.get("response_candidates", [])

            # Check decision criteria
            decision_factors = self._evaluate_decision_factors(
                state["mentor_id"],
                state["student_id"],
                mentor_style,
                conversation_context
            )

            should_respond = all([
                decision_factors["mentor_absence_sufficient"],
                decision_factors["daily_limit_ok"],
                decision_factors["urgency_sufficient"],
                decision_factors["style_confidence_sufficient"],
                decision_factors["no_human_request"]
            ])

            # Select best response if we should respond
            final_response = ""
            response_metadata = {}

            if should_respond and response_candidates:
                best_candidate = max(
                    response_candidates,
                    key=lambda x: x.get("generation_confidence", 0.0)
                )

                final_response = best_candidate["response_text"]
                response_metadata = {
                    "selected_variant": best_candidate["style_variant"],
                    "confidence": best_candidate["generation_confidence"],
                    "token_usage": best_candidate.get("token_usage", {}),
                    "model_used": best_candidate.get("model_used"),
                    "candidates_count": len(response_candidates)
                }

                # Add AI disclaimer
                final_response = self._add_ai_disclaimer(final_response)

            decision_reason = self._get_decision_reason(decision_factors, should_respond)

            return {
                "should_auto_respond": should_respond,
                "decision_reason": decision_reason,
                "final_response": final_response,
                "response_metadata": response_metadata,
                "decision_factors": decision_factors,
                "confidence_score": mentor_style.get("confidence_score", 0.0)
            }

        except Exception as e:
            logger.error(f"Decision making failed: {e}")
            return {
                "should_auto_respond": False,
                "decision_reason": "decision_error",
                "final_response": "",
                "response_metadata": {},
                "errors": [{"type": "decision_error", "message": str(e)}]
            }

    def _evaluate_decision_factors(self, mentor_id: int, student_id: int,
                                 mentor_style: Dict, conversation_context: Dict) -> Dict[str, bool]:
        """Evaluate all decision factors"""
        # Check mentor absence
        time_since_response = self._get_time_since_last_mentor_response(mentor_id, student_id)
        mentor_absence_sufficient = time_since_response.total_seconds() >= (self.min_mentor_absence_minutes * 60)

        # Check daily limit
        daily_count = self._get_daily_auto_response_count(mentor_id)
        daily_limit_ok = daily_count < self.max_auto_responses_per_day

        # Check urgency
        urgency_level = conversation_context.get("urgency_level", 0.0)
        urgency_sufficient = urgency_level >= self.urgency_threshold

        # Check style confidence
        style_confidence = mentor_style.get("confidence_score", 0.0)
        style_confidence_sufficient = style_confidence >= self.confidence_threshold

        # Check for human request (simplified check)
        latest_message = conversation_context.get("latest_message", "")
        no_human_request = not self._contains_human_request(latest_message)

        return {
            "mentor_absence_sufficient": mentor_absence_sufficient,
            "daily_limit_ok": daily_limit_ok,
            "urgency_sufficient": urgency_sufficient,
            "style_confidence_sufficient": style_confidence_sufficient,
            "no_human_request": no_human_request,
            "time_since_response_minutes": time_since_response.total_seconds() / 60,
            "daily_count": daily_count,
            "urgency_level": urgency_level,
            "style_confidence": style_confidence
        }

    def _get_time_since_last_mentor_response(self, mentor_id: int, student_id: int) -> timedelta:
        """Get time since mentor's last response to this student"""
        try:
            last_message = Message.objects.filter(
                sender_id=mentor_id,
                realm_id=UserProfile.objects.get(id=mentor_id).realm_id
            ).order_by("-date_sent").first()

            if last_message:
                return timezone.now() - last_message.date_sent
            else:
                return timedelta(days=1)  # Default to 1 day if no messages
        except Exception:
            return timedelta(days=1)

    def _get_daily_auto_response_count(self, mentor_id: int) -> int:
        """Get count of auto-responses sent today by this mentor"""
        try:
            today = timezone.now().date()
            return Message.objects.filter(
                sender_id=mentor_id,
                date_sent__date=today,
                content__contains="[AI Assistant Response]"
            ).count()
        except Exception:
            return 0

    def _contains_human_request(self, message: str) -> bool:
        """Check if student explicitly requested human interaction"""
        human_requests = [
            "talk to you personally",
            "speak with you directly",
            "need to talk to the real",
            "actual mentor",
            "human response",
            "not ai"
        ]

        message_lower = message.lower()
        return any(request in message_lower for request in human_requests)

    def _get_decision_reason(self, factors: Dict[str, bool], should_respond: bool) -> str:
        """Get human-readable decision reason"""
        if not should_respond:
            if not factors["mentor_absence_sufficient"]:
                return "mentor_recently_active"
            elif not factors["daily_limit_ok"]:
                return "daily_limit_reached"
            elif not factors["urgency_sufficient"]:
                return "low_urgency"
            elif not factors["style_confidence_sufficient"]:
                return "insufficient_style_data"
            elif not factors["no_human_request"]:
                return "human_interaction_requested"
            else:
                return "conditions_not_met"
        else:
            return "auto_response_generated"

    def _add_ai_disclaimer(self, response: str) -> str:
        """Add AI disclaimer to response"""
        disclaimer = ("\n\n*[This is an AI-generated response based on your mentor's communication style. "
                     "Your mentor will respond personally when available.]*")
        return f"[AI Assistant Response] {response}{disclaimer}"


class AIAgentOrchestrator:
    """Main orchestrator for the AI mentor agent system"""

    def __init__(self, portkey_config: PortkeyConfig):
        self.portkey_config = portkey_config
        self.llm_client = PortkeyLLMClient(portkey_config)

        # Initialize specialized agents
        self.style_agent = MentorStyleAgent(self.llm_client)
        self.context_agent = ContextAnalysisAgent(self.llm_client)
        self.response_agent = ResponseGenerationAgent(self.llm_client)
        self.suggestion_agent = IntelligentSuggestionAgent(self.llm_client)
        self.decision_agent = DecisionAgent()

        # Initialize state persistence
        self.checkpointer = self._initialize_checkpointer()
        self.workflow = self._build_workflow()

    def _initialize_checkpointer(self) -> SqliteSaver:
        """Initialize SQLite checkpointer for state persistence"""
        db_path = getattr(settings, 'AI_AGENT_STATE_DB_PATH', '/tmp/ai_agent_state.db')
        conn = sqlite3.connect(db_path, check_same_thread=False)
        return SqliteSaver(conn)

    def _build_workflow(self) -> StateGraph:
        """Build the complete LangGraph workflow"""
        workflow = StateGraph(AgentState)

        # Add agent nodes
        workflow.add_node("style_analysis", self._style_analysis_node)
        workflow.add_node("context_analysis", self._context_analysis_node)
        workflow.add_node("response_generation", self._response_generation_node)
        workflow.add_node("intelligent_suggestions", self._suggestion_generation_node)
        workflow.add_node("decision_making", self._decision_making_node)
        workflow.add_node("finalization", self._finalization_node)
        workflow.add_node("error_handling", self._error_handling_node)

        # Define workflow edges
        workflow.add_edge(START, "style_analysis")
        workflow.add_edge("style_analysis", "context_analysis")
        workflow.add_edge("context_analysis", "response_generation")
        workflow.add_edge("response_generation", "intelligent_suggestions")
        workflow.add_edge("intelligent_suggestions", "decision_making")
        workflow.add_edge("decision_making", "finalization")
        workflow.add_edge("finalization", END)

        # Add conditional error handling edges
        workflow.add_conditional_edges(
            "style_analysis",
            self._should_handle_error,
            {
                "error": "error_handling",
                "continue": "context_analysis"
            }
        )

        workflow.add_conditional_edges(
            "error_handling",
            lambda state: "end",
            {"end": END}
        )

        return workflow.compile(checkpointer=self.checkpointer)

    def _style_analysis_node(self, state: AgentState) -> AgentState:
        """Node for mentor style analysis"""
        try:
            result = self.style_agent.analyze_mentor_style(state)
            state.update(result)
            state["processing_status"] = "style_analysis_complete"
            return state
        except Exception as e:
            state["errors"] = state.get("errors", []) + [{"node": "style_analysis", "error": str(e)}]
            state["processing_status"] = "style_analysis_error"
            return state

    def _context_analysis_node(self, state: AgentState) -> AgentState:
        """Node for conversation context analysis"""
        try:
            result = self.context_agent.analyze_conversation_context(state)
            state.update(result)
            state["processing_status"] = "context_analysis_complete"
            return state
        except Exception as e:
            state["errors"] = state.get("errors", []) + [{"node": "context_analysis", "error": str(e)}]
            state["processing_status"] = "context_analysis_error"
            return state

    def _response_generation_node(self, state: AgentState) -> AgentState:
        """Node for response generation"""
        try:
            result = self.response_agent.generate_response_candidates(state)
            state.update(result)
            state["processing_status"] = "response_generation_complete"
            return state
        except Exception as e:
            state["errors"] = state.get("errors", []) + [{"node": "response_generation", "error": str(e)}]
            state["processing_status"] = "response_generation_error"
            return state

    def _suggestion_generation_node(self, state: AgentState) -> AgentState:
        """Node for intelligent suggestion generation"""
        try:
            result = self.suggestion_agent.generate_intelligent_suggestions(state)
            state.update(result)
            state["processing_status"] = "suggestions_complete"
            return state
        except Exception as e:
            state["errors"] = state.get("errors", []) + [{"node": "suggestions", "error": str(e)}]
            state["processing_status"] = "suggestions_error"
            return state

    def _decision_making_node(self, state: AgentState) -> AgentState:
        """Node for auto-response decision making"""
        try:
            result = self.decision_agent.make_auto_response_decision(state)
            state.update(result)
            state["processing_status"] = "decision_complete"
            return state
        except Exception as e:
            state["errors"] = state.get("errors", []) + [{"node": "decision", "error": str(e)}]
            state["processing_status"] = "decision_error"
            return state

    def _finalization_node(self, state: AgentState) -> AgentState:
        """Node for finalizing results and triggering events"""
        try:
            # Trigger events if auto-response was generated
            if state.get("should_auto_respond") and state.get("final_response"):
                self._trigger_success_events(state)

            # Log the interaction
            self._log_interaction(state)

            state["processing_status"] = "complete"
            return state
        except Exception as e:
            state["errors"] = state.get("errors", []) + [{"node": "finalization", "error": str(e)}]
            state["processing_status"] = "finalization_error"
            return state

    def _error_handling_node(self, state: AgentState) -> AgentState:
        """Node for handling errors"""
        try:
            errors = state.get("errors", [])
            if errors:
                # Trigger error events
                self._trigger_error_events(state, errors)

            state["processing_status"] = "error_handled"
            return state
        except Exception as e:
            logger.error(f"Error in error handling node: {e}")
            state["processing_status"] = "critical_error"
            return state

    def _should_handle_error(self, state: AgentState) -> str:
        """Determine if we should route to error handling"""
        errors = state.get("errors", [])
        if errors:
            return "error"
        return "continue"

    def _trigger_success_events(self, state: AgentState) -> None:
        """Trigger events for successful AI response generation"""
        try:
            mentor = UserProfile.objects.get(id=state["mentor_id"])
            student = UserProfile.objects.get(id=state["student_id"])

            notify_ai_response_generated(
                mentor=mentor,
                student=student,
                original_message=state["messages"][-1].content if state["messages"] else "",
                ai_response=state["final_response"],
                style_confidence=state.get("confidence_score", 0.0),
                decision_reason=state.get("decision_reason", "unknown"),
                message_id=0  # Would be actual message ID in production
            )

            # Trigger style analysis update event if analysis was performed
            mentor_style = state.get("mentor_style_profile", {})
            if mentor_style and mentor_style.get("confidence_score", 0) > 0:
                notify_style_analysis_updated(
                    mentor=mentor,
                    style_profile=mentor_style,
                    analysis_type="agent_analysis"
                )

        except Exception as e:
            logger.error(f"Failed to trigger success events: {e}")

    def _trigger_error_events(self, state: AgentState, errors: List[Dict]) -> None:
        """Trigger events for error conditions"""
        try:
            mentor = UserProfile.objects.get(id=state["mentor_id"])
            student = UserProfile.objects.get(id=state["student_id"])

            for error in errors:
                notify_ai_error(
                    mentor=mentor,
                    student=student,
                    error_type=f"agent_{error.get('node', 'unknown')}_error",
                    error_message=error.get('error', 'Unknown error'),
                    context={
                        "processing_status": state.get("processing_status"),
                        "node": error.get("node"),
                        "state_keys": list(state.keys())
                    }
                )

        except Exception as e:
            logger.error(f"Failed to trigger error events: {e}")

    def _log_interaction(self, state: AgentState) -> None:
        """Log the complete interaction for analytics"""
        try:
            interaction_data = {
                "mentor_id": state["mentor_id"],
                "student_id": state["student_id"],
                "realm_id": state["realm_id"],
                "processing_status": state.get("processing_status"),
                "auto_response_generated": bool(state.get("should_auto_respond")),
                "decision_reason": state.get("decision_reason"),
                "confidence_score": state.get("confidence_score", 0.0),
                "response_length": len(state.get("final_response", "")),
                "candidates_generated": len(state.get("response_candidates", [])),
                "suggestions_generated": len(state.get("intelligent_suggestions", [])),
                "errors_count": len(state.get("errors", [])),
                "timestamp": timezone.now().isoformat()
            }

            logger.info(f"AI agent interaction completed: {json.dumps(interaction_data)}")

        except Exception as e:
            logger.warning(f"Failed to log interaction: {e}")

    def process_student_message(self, student_id: int, mentor_id: int,
                              message_content: str) -> Dict[str, Any]:
        """Main entry point for processing student messages"""
        try:
            # Create initial state
            initial_state = {
                "messages": [HumanMessage(content=message_content)],
                "student_id": student_id,
                "mentor_id": mentor_id,
                "realm_id": UserProfile.objects.get(id=student_id).realm_id,
                "conversation_context": {},
                "mentor_style_profile": {},
                "student_profile": {},
                "urgency_assessment": {},
                "response_candidates": [],
                "intelligent_suggestions": [],
                "final_response": "",
                "response_metadata": {},
                "should_auto_respond": False,
                "decision_reason": "",
                "confidence_score": 0.0,
                "errors": [],
                "processing_status": "initialized"
            }

            # Configure workflow execution
            config = RunnableConfig(
                configurable={
                    "thread_id": f"mentor_{mentor_id}_student_{student_id}",
                    "checkpoint_ns": "ai_mentor_agent"
                }
            )

            # Execute the workflow
            final_state = self.workflow.invoke(initial_state, config=config)

            # Return results
            return {
                "success": True,
                "should_auto_respond": final_state.get("should_auto_respond", False),
                "decision_reason": final_state.get("decision_reason", "unknown"),
                "final_response": final_state.get("final_response", ""),
                "intelligent_suggestions": final_state.get("intelligent_suggestions", []),
                "confidence_score": final_state.get("confidence_score", 0.0),
                "response_metadata": final_state.get("response_metadata", {}),
                "processing_status": final_state.get("processing_status", "unknown"),
                "errors": final_state.get("errors", [])
            }

        except Exception as e:
            logger.error(f"Agent workflow execution failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "should_auto_respond": False,
                "final_response": "",
                "intelligent_suggestions": [],
                "confidence_score": 0.0
            }


# Factory function to create the orchestrator with proper configuration
def create_ai_agent_orchestrator() -> AIAgentOrchestrator:
    """Create and configure the AI agent orchestrator"""
    portkey_config = PortkeyConfig(
        api_key=getattr(settings, 'PORTKEY_API_KEY', ''),
        model=getattr(settings, 'AI_MENTOR_MODEL', '@gemini/gemini-2.0-flash-001'),
        max_retries=getattr(settings, 'AI_MENTOR_MAX_RETRIES', 3),
        timeout=getattr(settings, 'AI_MENTOR_TIMEOUT', 30)
    )

    return AIAgentOrchestrator(portkey_config)