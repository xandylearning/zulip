#!/usr/bin/env python3
"""
Script to enable enhanced debug logging for AI agent system
Run this to temporarily increase AI logging verbosity
"""

import os
import sys
import django

# Add the zulip directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set up Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'zproject.dev_settings')
django.setup()

import logging

def enable_ai_debug_logging():
    """Enable debug-level logging for all AI components"""

    # Set up AI-specific loggers
    ai_loggers = [
        'zerver.actions.message_send',
        'zerver.actions.ai_mentor_events',
        'zerver.event_listeners.ai_mentor',
        'zerver.event_listeners.ai_message_monitor',
        'zerver.lib.ai_agent_core',
        'zerver.lib.ai_mentor_response',
    ]

    print("🔧 Enabling enhanced AI debug logging...")

    for logger_name in ai_loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)

        # Add console handler if not exists
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s [%(name)s] %(levelname)s: %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        print(f"  ✅ {logger_name} set to DEBUG level")

    print("\n📊 AI Debug logging enabled!")
    print("Monitor logs with: tail -f /var/log/zulip/django.log | grep -E '(AI|ai_agent|ai_mentor)'")

if __name__ == "__main__":
    enable_ai_debug_logging()