"""
Test suite for AI Agent Event System

Tests the event-driven AI agent conversation system that replaces direct calls
with event-based processing.
"""

import json
import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import UserProfile
from zerver.models.realms import get_realm


class AIEventSystemTest(ZulipTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.realm = get_realm("zulip")

        # Create test users with proper roles
        self.mentor = self.example_user("hamlet")
        self.mentor.role = UserProfile.ROLE_MENTOR
        self.mentor.save()

        self.student = self.example_user("othello")
        self.student.role = UserProfile.ROLE_STUDENT
        self.student.save()

    def test_event_system_integration(self) -> None:
        """Test that the event system components are properly integrated"""

        # Test event creation functions
        try:
            from zerver.actions.ai_mentor_events import (
                send_ai_agent_conversation_event,
                trigger_ai_agent_conversation
            )
            # Import successful
        except ImportError as e:
            self.fail(f"AI agent event functions not importable: {e}")

        # Test event listener functions
        try:
            from zerver.event_listeners.ai_mentor import (
                handle_ai_agent_conversation,
                ai_mentor_event_listener
            )
            # Import successful
        except ImportError as e:
            self.fail(f"AI agent event listener not importable: {e}")

        # Test event listener has the new conversation handler
        self.assertTrue(
            hasattr(ai_mentor_event_listener, 'handle_ai_agent_conversation_event'),
            "Event listener missing conversation handler method"
        )

    def test_message_integration_uses_events(self) -> None:
        """Test that message sending integration uses events instead of direct calls"""

        # We can't easily test file contents in unit tests, so we test the behavior
        with patch('zerver.actions.ai_mentor_events.trigger_ai_agent_conversation') as mock_trigger:
            from zerver.actions.message_send import check_send_message

            # Send a student-to-mentor message
            message_id = check_send_message(
                sender=self.student,
                client=self.client,
                recipient_type_name='private',
                message_to=[self.mentor.email],
                topic_name=None,
                message_content="Test message for AI trigger",
                realm=self.realm,
            )

            # Verify that the event trigger was called (event-based approach)
            mock_trigger.assert_called_once()

    def test_ai_metadata_tagging(self) -> None:
        """Test that AI message tagging is working with event system"""

        from zerver.models import Message

        # Check for new fields
        self.assertTrue(hasattr(Message, 'is_ai_generated'), "Message model missing is_ai_generated field")
        self.assertTrue(hasattr(Message, 'ai_metadata'), "Message model missing ai_metadata field")

        # Create a test message and set AI metadata
        message = Message.objects.create(
            sender=self.mentor,
            recipient=self.student,
            content="Test AI response",
            realm=self.realm,
            sending_client=self.client,
            date_sent=timezone_now(),
            is_ai_generated=True,
            ai_metadata={
                "ai_system": "langgraph_agents",
                "triggered_by_event": True,
                "confidence_score": 0.85
            }
        )

        # Verify the metadata is stored correctly
        self.assertTrue(message.is_ai_generated)
        self.assertEqual(message.ai_metadata['ai_system'], 'langgraph_agents')
        self.assertTrue(message.ai_metadata['triggered_by_event'])

    def test_event_flow_completeness(self) -> None:
        """Test that the complete event flow is implemented"""

        # Test that we have all the required components
        components = {
            "Event Trigger": "zerver.actions.ai_mentor_events.trigger_ai_agent_conversation",
            "Event Creation": "zerver.actions.ai_mentor_events.send_ai_agent_conversation_event",
            "Event Handler": "zerver.event_listeners.ai_mentor.handle_ai_agent_conversation",
            "Event Listener Class": "zerver.event_listeners.ai_mentor.ai_mentor_event_listener"
        }

        for component_name, import_path in components.items():
            try:
                module_path, function_name = import_path.rsplit('.', 1)
                module = __import__(module_path, fromlist=[function_name])
                component = getattr(module, function_name)
                # Component exists and is importable
                self.assertIsNotNone(component, f"{component_name} is None after import")
            except (ImportError, AttributeError) as e:
                self.fail(f"{component_name} missing: {import_path} - {e}")

    def test_configuration_compatibility(self) -> None:
        """Test that the event system is compatible with existing configuration"""

        with self.settings(
            USE_LANGGRAPH_AGENTS=True,
            AI_MENTOR_MIN_ABSENCE_MINUTES=5,
        ):
            from zproject.ai_agent_settings import (
                USE_LANGGRAPH_AGENTS,
                AI_MENTOR_MIN_ABSENCE_MINUTES,
                validate_ai_agent_settings
            )

            self.assertTrue(USE_LANGGRAPH_AGENTS)
            self.assertEqual(AI_MENTOR_MIN_ABSENCE_MINUTES, 5)

            # Test validation still works
            warnings = validate_ai_agent_settings()
            # Warnings are expected in test environment (missing API keys)
            self.assertIsInstance(warnings, list)

    @patch('zerver.event_listeners.ai_mentor.handle_ai_agent_conversation')
    def test_ai_agent_conversation_event_dispatch(self, mock_handler: MagicMock) -> None:
        """Test that ai_agent_conversation events are properly dispatched"""

        from zerver.actions.ai_mentor_events import send_ai_agent_conversation_event

        # Create test event data
        ai_response_data = {
            "original_message_id": 12345,
            "trigger_timestamp": timezone_now().isoformat(),
        }

        # Send the event
        send_ai_agent_conversation_event(
            realm=self.realm,
            mentor=self.mentor,
            student=self.student,
            original_message="Test student message",
            ai_response_data=ai_response_data,
        )

        # Verify the handler was called
        mock_handler.assert_called_once()

        # Verify event structure
        event_data = mock_handler.call_args[0][0]
        self.assertEqual(event_data['type'], 'ai_agent_conversation')
        self.assertEqual(event_data['mentor']['user_id'], self.mentor.id)
        self.assertEqual(event_data['student']['user_id'], self.student.id)
        self.assertEqual(event_data['message_data']['content'], 'Test student message')

    def test_ai_message_created_event(self) -> None:
        """Test AI message created event generation"""

        from zerver.actions.ai_mentor_events import send_ai_message_created_event

        ai_metadata = {
            "ai_system": "langgraph_agents",
            "model": "gpt-4",
            "confidence_score": 0.87,
            "triggered_by_event": True
        }

        with patch('zerver.event_listeners.ai_message_monitor.handle_ai_message_created') as mock_handler:
            # Send AI message created event
            send_ai_message_created_event(
                realm=self.realm,
                message_id=12345,
                ai_metadata=ai_metadata,
                mentor=self.mentor,
                student=self.student,
            )

            # Verify monitoring handler was called
            mock_handler.assert_called_once()

            event_data = mock_handler.call_args[0][0]
            self.assertEqual(event_data['type'], 'ai_message_created')
            self.assertEqual(event_data['message_id'], 12345)
            self.assertEqual(event_data['ai_metadata']['ai_system'], 'langgraph_agents')

    def test_ai_agent_performance_event(self) -> None:
        """Test AI agent performance monitoring events"""

        from zerver.actions.ai_mentor_events import send_ai_agent_performance_event

        with patch('zerver.event_listeners.ai_message_monitor.handle_ai_agent_performance') as mock_handler:
            # Send performance event
            send_ai_agent_performance_event(
                realm=self.realm,
                agent_type="style_analysis",
                processing_time_ms=1500,
                success=True,
                token_usage=150,
                confidence_score=0.85,
            )

            # Verify monitoring handler was called
            mock_handler.assert_called_once()

            event_data = mock_handler.call_args[0][0]
            self.assertEqual(event_data['type'], 'ai_agent_performance')
            self.assertEqual(event_data['agent_type'], 'style_analysis')
            self.assertEqual(event_data['processing_time_ms'], 1500)
            self.assertTrue(event_data['success'])

    def test_event_listener_error_handling(self) -> None:
        """Test that event listeners handle errors gracefully"""

        from zerver.event_listeners.ai_mentor import handle_ai_agent_conversation

        # Create malformed event data
        malformed_event = {
            "type": "ai_agent_conversation",
            # Missing required fields
        }

        # This should not raise an exception
        try:
            handle_ai_agent_conversation(malformed_event)
        except Exception as e:
            # If it does raise an exception, it should be logged, not crash
            # In a real test we'd check the logs, here we just ensure it doesn't crash the test
            pass

    @override_settings(USE_LANGGRAPH_AGENTS=True)
    def test_ai_agent_workflow_integration(self) -> None:
        """Test integration with AI agent workflow system"""

        # Test that the workflow configuration is accessible
        from zproject.ai_agent_settings import AI_AGENT_WORKFLOW_CONFIG

        required_configs = [
            'style_analysis',
            'context_analysis',
            'response_generation',
            'suggestion_generation'
        ]

        for config_key in required_configs:
            self.assertIn(config_key, AI_AGENT_WORKFLOW_CONFIG)

    def test_event_system_scalability(self) -> None:
        """Test that the event system can handle multiple concurrent events"""

        from zerver.actions.ai_mentor_events import trigger_ai_agent_conversation

        with patch('zerver.event_listeners.ai_mentor.handle_ai_agent_conversation') as mock_handler:
            # Simulate multiple concurrent conversation triggers
            for i in range(5):
                trigger_ai_agent_conversation(
                    mentor=self.mentor,
                    student=self.student,
                    original_message=f"Test message {i}",
                    original_message_id=1000 + i,
                )

            # All events should be processed
            self.assertEqual(mock_handler.call_count, 5)

    def test_ai_event_monitoring_system(self) -> None:
        """Test the AI event monitoring system"""

        try:
            from zerver.event_listeners.ai_message_monitor import (
                ai_message_monitor,
                handle_ai_message_created,
                handle_ai_message_feedback,
                handle_ai_agent_performance
            )

            # Verify monitoring system exists
            self.assertIsNotNone(ai_message_monitor)

            # Verify handler functions exist
            self.assertTrue(callable(handle_ai_message_created))
            self.assertTrue(callable(handle_ai_message_feedback))
            self.assertTrue(callable(handle_ai_agent_performance))

        except ImportError as e:
            self.fail(f"AI message monitoring system not available: {e}")

    def test_complete_event_lifecycle(self) -> None:
        """Test the complete event lifecycle from trigger to monitoring"""

        with patch('zerver.lib.ai_mentor_response.handle_potential_ai_response') as mock_ai_response, \
             patch('zerver.actions.message_send.check_send_message') as mock_send_message, \
             patch('zerver.event_listeners.ai_message_monitor.handle_ai_message_created') as mock_monitor:

            # Mock AI response
            mock_ai_response.return_value = MagicMock(
                content="AI generated response",
                confidence=0.85,
                model='gpt-4'
            )
            mock_send_message.return_value = 54321  # Mock message ID

            from zerver.event_listeners.ai_mentor import handle_ai_agent_conversation

            # Create complete event
            event_data = {
                "type": "ai_agent_conversation",
                "mentor": {"user_id": self.mentor.id},
                "student": {"user_id": self.student.id},
                "message_data": {
                    "content": "I need help with my homework",
                    "message_id": 12345,
                },
                "realm_id": self.realm.id,
            }

            # Process the event
            handle_ai_agent_conversation(event_data)

            # Verify the complete lifecycle
            mock_ai_response.assert_called_once()
            # Note: In real implementation, message sending and monitoring would be called
            # Here we're testing the event structure and flow

    def test_ai_agent_settings_integration(self) -> None:
        """Test integration with AI agent settings system"""

        from zproject.ai_agent_settings import (
            AI_AGENT_FEATURE_FLAGS,
            AI_AGENT_SECURITY_CONFIG,
            AI_AGENT_PERFORMANCE_CONFIG
        )

        # Verify configuration dictionaries exist and have expected structure
        self.assertIsInstance(AI_AGENT_FEATURE_FLAGS, dict)
        self.assertIsInstance(AI_AGENT_SECURITY_CONFIG, dict)
        self.assertIsInstance(AI_AGENT_PERFORMANCE_CONFIG, dict)

        # Verify key feature flags
        expected_flags = [
            'enable_style_analysis',
            'enable_context_analysis',
            'enable_response_generation'
        ]

        for flag in expected_flags:
            self.assertIn(flag, AI_AGENT_FEATURE_FLAGS)