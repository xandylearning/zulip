"""
Django settings for LangGraph AI Agents system

This file contains settings specific to the LangGraph-based AI messaging system
with Portkey integration.
"""

import os
from typing import Dict, Any

# Core agent system settings
USE_LANGGRAPH_AGENTS = os.environ.get('USE_LANGGRAPH_AGENTS', 'False').lower() == 'true'

# Portkey AI configuration
PORTKEY_API_KEY = os.environ.get('PORTKEY_API_KEY', '')
PORTKEY_BASE_URL = os.environ.get('PORTKEY_BASE_URL', 'https://api.portkey.ai/v1')

# AI model configuration
AI_MENTOR_MODEL = os.environ.get('AI_MENTOR_MODEL', 'gpt-4')
AI_MENTOR_TEMPERATURE = float(os.environ.get('AI_MENTOR_TEMPERATURE', '0.7'))
AI_MENTOR_MAX_TOKENS = int(os.environ.get('AI_MENTOR_MAX_TOKENS', '1000'))

# Agent system timeouts and retries
AI_MENTOR_MAX_RETRIES = int(os.environ.get('AI_MENTOR_MAX_RETRIES', '3'))
AI_MENTOR_TIMEOUT = int(os.environ.get('AI_MENTOR_TIMEOUT', '30'))

# Decision thresholds
AI_MENTOR_MIN_ABSENCE_MINUTES = int(os.environ.get('AI_MENTOR_MIN_ABSENCE_MINUTES', '240'))  # Default 4 hours = 240 minutes
AI_MENTOR_MAX_DAILY_RESPONSES = int(os.environ.get('AI_MENTOR_MAX_DAILY_RESPONSES', '3'))
AI_MENTOR_URGENCY_THRESHOLD = float(os.environ.get('AI_MENTOR_URGENCY_THRESHOLD', '0.7'))
AI_MENTOR_CONFIDENCE_THRESHOLD = float(os.environ.get('AI_MENTOR_CONFIDENCE_THRESHOLD', '0.6'))

# State persistence
AI_AGENT_STATE_DB_PATH = os.environ.get('AI_AGENT_STATE_DB_PATH', '/tmp/ai_agent_state.db')

# Agent workflow configuration
AI_AGENT_WORKFLOW_CONFIG: Dict[str, Any] = {
    'style_analysis': {
        'min_messages_required': int(os.environ.get('AI_STYLE_MIN_MESSAGES', '5')),
        'max_messages_analyzed': int(os.environ.get('AI_STYLE_MAX_MESSAGES', '50')),
        'cache_duration_hours': int(os.environ.get('AI_STYLE_CACHE_HOURS', '24')),
    },
    'context_analysis': {
        'conversation_history_limit': int(os.environ.get('AI_CONTEXT_HISTORY_LIMIT', '10')),
        'urgency_keywords_weight': float(os.environ.get('AI_URGENCY_KEYWORDS_WEIGHT', '0.8')),
    },
    'response_generation': {
        'candidate_variants': int(os.environ.get('AI_RESPONSE_VARIANTS', '3')),
        'quality_threshold': float(os.environ.get('AI_RESPONSE_QUALITY_THRESHOLD', '0.7')),
    },
    'suggestion_generation': {
        'max_suggestions': int(os.environ.get('AI_MAX_SUGGESTIONS', '5')),
        'suggestion_categories': [
            'content_recommendations',
            'tone_adjustments',
            'resource_suggestions',
            'follow_up_actions',
            'teaching_strategies'
        ],
    }
}

# Logging configuration for AI agents
AI_AGENT_LOGGING_CONFIG = {
    'log_interactions': os.environ.get('AI_LOG_INTERACTIONS', 'True').lower() == 'true',
    'log_level': os.environ.get('AI_LOG_LEVEL', 'INFO'),
    'log_performance_metrics': os.environ.get('AI_LOG_PERFORMANCE', 'True').lower() == 'true',
    'log_agent_decisions': os.environ.get('AI_LOG_DECISIONS', 'True').lower() == 'true',
}

# Security and privacy settings
AI_AGENT_SECURITY_CONFIG = {
    'enforce_realm_isolation': True,
    'require_explicit_consent': os.environ.get('AI_REQUIRE_CONSENT', 'True').lower() == 'true',
    'anonymize_logs': os.environ.get('AI_ANONYMIZE_LOGS', 'True').lower() == 'true',
    'max_context_retention_days': int(os.environ.get('AI_MAX_CONTEXT_DAYS', '30')),
}

# Performance monitoring
AI_AGENT_PERFORMANCE_CONFIG = {
    'track_response_times': True,
    'track_token_usage': True,
    'track_success_rates': True,
    'alert_on_high_error_rate': True,
    'error_rate_threshold': float(os.environ.get('AI_ERROR_RATE_THRESHOLD', '0.1')),
}

# Feature flags for gradual rollout
AI_AGENT_FEATURE_FLAGS = {
    'enable_style_analysis': os.environ.get('AI_ENABLE_STYLE_ANALYSIS', 'True').lower() == 'true',
    'enable_context_analysis': os.environ.get('AI_ENABLE_CONTEXT_ANALYSIS', 'True').lower() == 'true',
    'enable_response_generation': os.environ.get('AI_ENABLE_RESPONSE_GEN', 'True').lower() == 'true',
    'enable_intelligent_suggestions': os.environ.get('AI_ENABLE_SUGGESTIONS', 'True').lower() == 'true',
    'enable_auto_responses': os.environ.get('AI_ENABLE_AUTO_RESPONSES', 'True').lower() == 'true',
}

# Development and testing settings
if os.environ.get('DJANGO_ENVIRONMENT') == 'development':
    # Use shorter timeouts and lower thresholds for development
    AI_MENTOR_MIN_ABSENCE_MINUTES = 5  # 5 minutes instead of 240 for testing
    AI_MENTOR_MAX_DAILY_RESPONSES = 10  # More responses for testing
    AI_MENTOR_URGENCY_THRESHOLD = 0.3  # Lower threshold for testing
    AI_MENTOR_CONFIDENCE_THRESHOLD = 0.3  # Lower threshold for testing

    # Enable all features for development
    AI_AGENT_FEATURE_FLAGS.update({key: True for key in AI_AGENT_FEATURE_FLAGS})

    # Use mock responses if no API keys provided
    if not PORTKEY_API_KEY:
        USE_LANGGRAPH_AGENTS = False

# Validation
def validate_ai_agent_settings():
    """Validate AI agent settings and warn about misconfigurations"""
    warnings = []

    if USE_LANGGRAPH_AGENTS:
        if not PORTKEY_API_KEY:
            warnings.append("PORTKEY_API_KEY not set - AI agents will not function")


        if AI_MENTOR_CONFIDENCE_THRESHOLD > 0.9:
            warnings.append("AI_MENTOR_CONFIDENCE_THRESHOLD very high - may prevent responses")

        if AI_MENTOR_MIN_ABSENCE_MINUTES > 1440:  # 24 hours = 1440 minutes
            warnings.append("AI_MENTOR_MIN_ABSENCE_MINUTES very high - auto-responses rarely triggered")

    return warnings

# Export all settings for import in main settings
__all__ = [
    'USE_LANGGRAPH_AGENTS',
    'PORTKEY_API_KEY',
    'PORTKEY_BASE_URL',
    'AI_MENTOR_MODEL',
    'AI_MENTOR_TEMPERATURE',
    'AI_MENTOR_MAX_TOKENS',
    'AI_MENTOR_MAX_RETRIES',
    'AI_MENTOR_TIMEOUT',
    'AI_MENTOR_MIN_ABSENCE_MINUTES',
    'AI_MENTOR_MAX_DAILY_RESPONSES',
    'AI_MENTOR_URGENCY_THRESHOLD',
    'AI_MENTOR_CONFIDENCE_THRESHOLD',
    'AI_AGENT_STATE_DB_PATH',
    'AI_AGENT_WORKFLOW_CONFIG',
    'AI_AGENT_LOGGING_CONFIG',
    'AI_AGENT_SECURITY_CONFIG',
    'AI_AGENT_PERFORMANCE_CONFIG',
    'AI_AGENT_FEATURE_FLAGS',
    'validate_ai_agent_settings',
]