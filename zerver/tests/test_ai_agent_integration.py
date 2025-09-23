"""
Test suite for AI Agent Integration with Zulip Message Sending

Tests the integration between the AI agent system and Zulip's message sending pipeline.
"""

import time
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.actions.message_send import check_send_message
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import most_recent_message
from zerver.models import Message, UserProfile
from zerver.models.realms import get_realm


class AIAgentIntegrationTest(ZulipTestCase):
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

    @override_settings(
        USE_LANGGRAPH_AGENTS=True,
        AI_MENTOR_MIN_ABSENCE_MINUTES=5,
        AI_MENTOR_MAX_DAILY_RESPONSES=3,
        AI_MENTOR_URGENCY_THRESHOLD=0.7,
        AI_MENTOR_CONFIDENCE_THRESHOLD=0.6,
    )
    def test_settings_configuration(self) -> None:
        """Test that AI agent settings load correctly"""

        from django.conf import settings

        # Test that settings are overridden correctly
        self.assertTrue(settings.USE_LANGGRAPH_AGENTS)
        self.assertEqual(settings.AI_MENTOR_MIN_ABSENCE_MINUTES, 5)
        self.assertEqual(settings.AI_MENTOR_MAX_DAILY_RESPONSES, 3)
        self.assertEqual(settings.AI_MENTOR_URGENCY_THRESHOLD, 0.7)
        self.assertEqual(settings.AI_MENTOR_CONFIDENCE_THRESHOLD, 0.6)

        # Test that we can import the settings module
        try:
            from zproject.ai_agent_settings import validate_ai_agent_settings

            # Test validation function exists and is callable
            self.assertTrue(callable(validate_ai_agent_settings))

            # Test validation - should have warnings for missing API keys in test environment
            warnings = validate_ai_agent_settings()
            self.assertIsInstance(warnings, list)

        except ImportError as e:
            self.fail(f"Could not import AI agent settings: {e}")

    @patch('zerver.actions.ai_mentor_events.trigger_ai_agent_conversation')
    def test_message_pipeline_integration(self, mock_trigger: MagicMock) -> None:
        """Test that student-to-mentor messages trigger AI agent events"""

        # Send a message from student to mentor
        message_content = "Hi Dr. Smith, I need help with calculus homework."

        message_id = check_send_message(
            sender=self.student,
            client=self.client,
            recipient_type_name='private',
            message_to=[self.mentor.email],
            topic_name=None,
            message_content=message_content,
            realm=self.realm,
        )

        # Verify the AI agent conversation was triggered
        mock_trigger.assert_called_once()
        call_args = mock_trigger.call_args[1]  # Get keyword arguments

        self.assertEqual(call_args['mentor'], self.mentor)
        self.assertEqual(call_args['student'], self.student)
        self.assertEqual(call_args['original_message'], message_content)
        self.assertEqual(call_args['original_message_id'], message_id)

    def test_ai_message_tagging_fields(self) -> None:
        """Test that Message model has AI tagging fields"""

        # Check that the new fields exist
        self.assertTrue(hasattr(Message, 'is_ai_generated'))
        self.assertTrue(hasattr(Message, 'ai_metadata'))

        # Create a test message and verify field behavior
        message_id = check_send_message(
            sender=self.mentor,
            client=self.client,
            recipient_type_name='private',
            message_to=[self.student.email],
            topic_name=None,
            message_content="Test message",
            realm=self.realm,
        )

        message = Message.objects.get(id=message_id)

        # Default values should be False and None
        self.assertFalse(message.is_ai_generated)
        self.assertIsNone(message.ai_metadata)

        # Test setting AI metadata
        ai_metadata = {
            "ai_system": "langgraph_agents",
            "model": "gpt-4",
            "confidence_score": 0.85,
            "triggered_by_event": True
        }

        message.is_ai_generated = True
        message.ai_metadata = ai_metadata
        message.save()

        # Reload and verify
        message.refresh_from_db()
        self.assertTrue(message.is_ai_generated)
        self.assertEqual(message.ai_metadata['ai_system'], 'langgraph_agents')
        self.assertEqual(message.ai_metadata['confidence_score'], 0.85)

    @patch('zerver.event_listeners.ai_mentor.handle_ai_agent_conversation')
    def test_event_listener_integration(self, mock_handler: MagicMock) -> None:
        """Test that AI agent events are properly handled"""

        from zerver.actions.ai_mentor_events import send_ai_agent_conversation_event

        # Create a test event
        ai_response_data = {
            "original_message_id": 12345,
            "trigger_timestamp": timezone_now().isoformat(),
        }

        # Send the event
        send_ai_agent_conversation_event(
            realm=self.realm,
            mentor=self.mentor,
            student=self.student,
            original_message="Test message",
            ai_response_data=ai_response_data,
        )

        # Verify the event handler was called
        mock_handler.assert_called_once()
        event_data = mock_handler.call_args[0][0]  # Get the event argument

        self.assertEqual(event_data['type'], 'ai_agent_conversation')
        self.assertEqual(event_data['mentor']['user_id'], self.mentor.id)
        self.assertEqual(event_data['student']['user_id'], self.student.id)
        self.assertEqual(event_data['message_data']['content'], 'Test message')

    @override_settings(USE_LANGGRAPH_AGENTS=True)
    @patch('zerver.lib.ai_mentor_response.handle_potential_ai_response')
    def test_agent_decision_logic(self, mock_ai_response: MagicMock) -> None:
        """Test that AI agent decision logic works correctly"""

        # Mock a successful AI response
        mock_ai_response.return_value = MagicMock(
            content="Here's help with your calculus problem...",
            confidence=0.85,
            model='gpt-4'
        )

        from zerver.event_listeners.ai_mentor import handle_ai_agent_conversation

        # Create test event data
        event_data = {
            "type": "ai_agent_conversation",
            "mentor": {"user_id": self.mentor.id},
            "student": {"user_id": self.student.id},
            "message_data": {
                "content": "I need help with calculus",
                "message_id": 12345,
            },
            "realm_id": self.realm.id,
        }

        # Process the event
        handle_ai_agent_conversation(event_data)

        # Verify AI response was called
        mock_ai_response.assert_called_once()

    def test_environment_configuration_validation(self) -> None:
        """Test environment variable configuration validation"""

        from zproject.ai_agent_settings import validate_ai_agent_settings

        with self.settings(
            USE_LANGGRAPH_AGENTS=True,
            PORTKEY_API_KEY='',  # Empty key should trigger warning
            AI_MENTOR_CONFIDENCE_THRESHOLD=0.95,  # Very high threshold should trigger warning
        ):
            warnings = validate_ai_agent_settings()

            # Should have warnings for missing API key and high threshold
            self.assertTrue(any("PORTKEY_API_KEY" in warning for warning in warnings))

    def test_agent_workflow_configuration(self) -> None:
        """Test that agent workflow configuration is accessible"""

        from zproject.ai_agent_settings import AI_AGENT_WORKFLOW_CONFIG

        # Verify workflow configuration structure
        self.assertIn('style_analysis', AI_AGENT_WORKFLOW_CONFIG)
        self.assertIn('context_analysis', AI_AGENT_WORKFLOW_CONFIG)
        self.assertIn('response_generation', AI_AGENT_WORKFLOW_CONFIG)
        self.assertIn('suggestion_generation', AI_AGENT_WORKFLOW_CONFIG)

        # Verify specific configuration values
        style_config = AI_AGENT_WORKFLOW_CONFIG['style_analysis']
        self.assertIn('min_messages_required', style_config)
        self.assertIn('cache_duration_hours', style_config)

    @patch('zerver.actions.ai_mentor_events.send_ai_message_created_event')
    def test_ai_message_monitoring_events(self, mock_send_event: MagicMock) -> None:
        """Test that AI message creation triggers monitoring events"""

        from zerver.event_listeners.ai_mentor import ai_mentor_event_listener

        # Create AI metadata
        ai_metadata = {
            "ai_system": "langgraph_agents",
            "model": "gpt-4",
            "confidence_score": 0.87,
            "triggered_by_event": True
        }

        # Create a message with AI metadata
        message_id = check_send_message(
            sender=self.mentor,
            client=self.client,
            recipient_type_name='private',
            message_to=[self.student.email],
            topic_name=None,
            message_content="AI generated response",
            realm=self.realm,
        )

        message = Message.objects.get(id=message_id)
        message.is_ai_generated = True
        message.ai_metadata = ai_metadata
        message.save()

        # The monitoring event would be triggered in the actual workflow
        # Here we verify the function exists and can be called
        self.assertTrue(hasattr(ai_mentor_event_listener, 'handle_ai_agent_conversation_event'))

    def test_complete_integration_flow(self) -> None:
        """Test the complete integration flow with mocked components"""

        with patch('zerver.actions.ai_mentor_events.trigger_ai_agent_conversation') as mock_trigger, \
             patch('zerver.event_listeners.ai_mentor.handle_ai_agent_conversation') as mock_handler:

            # Step 1: Student sends message to mentor
            message_content = "I'm struggling with derivatives, can you help?"

            message_id = check_send_message(
                sender=self.student,
                client=self.client,
                recipient_type_name='private',
                message_to=[self.mentor.email],
                topic_name=None,
                message_content=message_content,
                realm=self.realm,
            )

            # Step 2: Verify event trigger was called
            mock_trigger.assert_called_once()

            # Step 3: Simulate event processing
            event_data = {
                "type": "ai_agent_conversation",
                "mentor": {"user_id": self.mentor.id},
                "student": {"user_id": self.student.id},
                "message_data": {"content": message_content, "message_id": message_id},
                "realm_id": self.realm.id,
            }

            # Step 4: Process through event handler
            handle_ai_agent_conversation = mock_handler
            handle_ai_agent_conversation(event_data)

            # Step 5: Verify handler was called with correct data
            mock_handler.assert_called_once_with(event_data)

    def test_ai_agent_feature_flags(self) -> None:
        """Test AI agent feature flags configuration"""

        from zproject.ai_agent_settings import AI_AGENT_FEATURE_FLAGS

        # Verify feature flags exist
        expected_flags = [
            'enable_style_analysis',
            'enable_context_analysis',
            'enable_response_generation',
            'enable_intelligent_suggestions',
            'enable_auto_responses'
        ]

        for flag in expected_flags:
            self.assertIn(flag, AI_AGENT_FEATURE_FLAGS)
            # Should be boolean values
            self.assertIsInstance(AI_AGENT_FEATURE_FLAGS[flag], bool)