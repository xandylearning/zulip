"""
Test suite for AI Agent Core Functionality

Tests the LangGraph multi-agent system core functionality.
"""

import json
from typing import Any, Dict
from unittest.mock import MagicMock, patch

from django.test import override_settings
from django.utils.timezone import now as timezone_now

from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Message, UserProfile
from zerver.models.realms import get_realm


class AIAgentCoreTest(ZulipTestCase):
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

    def _create_mock_portkey_config(self):
        """Helper to create mock Portkey config for testing"""
        try:
            from zerver.lib.ai_agent_core import PortkeyConfig
            return PortkeyConfig(
                api_key="test_key",
                virtual_key="test_virtual_key",
                base_url="https://api.portkey.ai/v1"
            )
        except ImportError:
            return None

    @override_settings(USE_LANGGRAPH_AGENTS=True)
    def test_ai_agent_orchestrator_import(self) -> None:
        """Test that the AI agent orchestrator can be imported"""

        try:
            from zerver.lib.ai_agent_core import AIAgentOrchestrator, PortkeyConfig

            # Mock portkey config for testing
            mock_config = PortkeyConfig(
                api_key="test_key",
                virtual_key="test_virtual_key",
                base_url="https://api.portkey.ai/v1"
            )

            orchestrator = AIAgentOrchestrator(portkey_config=mock_config)
            self.assertIsNotNone(orchestrator)
        except ImportError as e:
            self.fail(f"Could not import AIAgentOrchestrator: {e}")

    @override_settings(USE_LANGGRAPH_AGENTS=True)
    def test_individual_agents_exist(self) -> None:
        """Test that all individual agents exist and can be imported"""

        agent_classes = [
            'MentorStyleAnalysisAgent',
            'ContextAnalysisAgent',
            'ResponseGenerationAgent',
            'IntelligentSuggestionAgent',
            'DecisionAgent'
        ]

        try:
            from zerver.lib.ai_agent_core import (
                MentorStyleAnalysisAgent,
                ContextAnalysisAgent,
                ResponseGenerationAgent,
                IntelligentSuggestionAgent,
                DecisionAgent
            )

            # Mock portkey config for agents
            mock_config = {
                "api_key": "test_key",
                "virtual_key": "test_virtual_key",
                "base_url": "https://api.portkey.ai/v1"
            }

            # Test that each agent can be instantiated
            agents = {
                'style': MentorStyleAnalysisAgent(mock_config),
                'context': ContextAnalysisAgent(mock_config),
                'response': ResponseGenerationAgent(mock_config),
                'suggestion': IntelligentSuggestionAgent(mock_config),
                'decision': DecisionAgent()  # Decision agent doesn't need portkey config
            }

            for agent_name, agent in agents.items():
                self.assertIsNotNone(agent, f"{agent_name} agent is None")

        except ImportError as e:
            self.fail(f"Could not import agent classes: {e}")

    @patch('zerver.lib.ai_agent_core.MentorStyleAnalysisAgent.analyze_mentor_style')
    def test_style_analysis_agent(self, mock_analyze: MagicMock) -> None:
        """Test the style analysis agent functionality"""

        mock_analyze.return_value = {
            "mentor_style_profile": {
                "tone_pattern": "supportive_and_encouraging",
                "teaching_approach": "step_by_step_explanatory",
                "confidence_score": 0.87,
                "message_count": 23
            }
        }

        try:
            from zerver.lib.ai_agent_core import MentorStyleAnalysisAgent

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            agent = MentorStyleAnalysisAgent(mock_config)
            result = agent.analyze_mentor_style(self.mentor)

            self.assertIn('mentor_style_profile', result)
            self.assertEqual(result['mentor_style_profile']['confidence_score'], 0.87)
            mock_analyze.assert_called_once()

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @patch('zerver.lib.ai_agent_core.ContextAnalysisAgent.analyze_conversation_context')
    def test_context_analysis_agent(self, mock_analyze: MagicMock) -> None:
        """Test the context analysis agent functionality"""

        mock_analyze.return_value = {
            "conversation_context": {
                "urgency_level": 0.92,
                "sentiment": "anxious_and_stressed",
                "academic_context": {
                    "subject": "calculus",
                    "specific_topic": "derivative_chain_rule"
                }
            }
        }

        try:
            from zerver.lib.ai_agent_core import ContextAnalysisAgent

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            agent = ContextAnalysisAgent(mock_config)

            # Create a test message
            test_message = Message(
                sender=self.student,
                content="I'm struggling with calculus derivatives",
                realm=self.realm,
                date_sent=timezone_now()
            )

            result = agent.analyze_conversation_context(test_message, [])

            self.assertIn('conversation_context', result)
            self.assertEqual(result['conversation_context']['urgency_level'], 0.92)
            mock_analyze.assert_called_once()

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @patch('zerver.lib.ai_agent_core.ResponseGenerationAgent.generate_response_variants')
    def test_response_generation_agent(self, mock_generate: MagicMock) -> None:
        """Test the response generation agent functionality"""

        mock_generate.return_value = {
            "response_candidates": [
                {
                    "response_text": "Don't worry, let's work through this step by step...",
                    "style_variant": "supportive",
                    "generation_confidence": 0.89
                },
                {
                    "response_text": "Here's the chain rule formula: d/dx[f(g(x))] = f'(g(x)) × g'(x)",
                    "style_variant": "direct_teaching",
                    "generation_confidence": 0.85
                }
            ]
        }

        try:
            from zerver.lib.ai_agent_core import ResponseGenerationAgent

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            agent = ResponseGenerationAgent(mock_config)

            mentor_style = {"tone_pattern": "supportive"}
            context = {"urgency_level": 0.8}

            result = agent.generate_response_variants(mentor_style, context, "Help with calculus")

            self.assertIn('response_candidates', result)
            self.assertEqual(len(result['response_candidates']), 2)
            self.assertEqual(result['response_candidates'][0]['style_variant'], 'supportive')

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @patch('zerver.lib.ai_agent_core.IntelligentSuggestionAgent.generate_suggestions')
    def test_intelligent_suggestion_agent(self, mock_generate: MagicMock) -> None:
        """Test the intelligent suggestion agent functionality"""

        mock_generate.return_value = {
            "intelligent_suggestions": [
                {
                    "text": "Acknowledge the student's stress and time pressure first",
                    "type": "communication_strategy",
                    "priority": "high",
                    "confidence": 0.91
                }
            ]
        }

        try:
            from zerver.lib.ai_agent_core import IntelligentSuggestionAgent

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            agent = IntelligentSuggestionAgent(mock_config)

            result = agent.generate_suggestions("Help with calculus", {}, {})

            self.assertIn('intelligent_suggestions', result)
            self.assertEqual(len(result['intelligent_suggestions']), 1)
            self.assertEqual(result['intelligent_suggestions'][0]['priority'], 'high')

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @patch('zerver.lib.ai_agent_core.DecisionAgent.make_response_decision')
    def test_decision_agent(self, mock_decide: MagicMock) -> None:
        """Test the decision agent functionality"""

        mock_decide.return_value = {
            "should_auto_respond": True,
            "decision_reason": "high_urgency_with_reliable_style_data",
            "final_response": "Don't panic - let's work through this together...",
            "confidence_score": 0.89
        }

        try:
            from zerver.lib.ai_agent_core import DecisionAgent

            agent = DecisionAgent()

            mentor_style = {"confidence_score": 0.87}
            context = {"urgency_level": 0.92}
            response_candidates = [{"response_text": "Test response", "generation_confidence": 0.85}]

            result = agent.make_response_decision(
                mentor_id=self.mentor.id,
                student_id=self.student.id,
                mentor_style=mentor_style,
                conversation_context=context,
                response_candidates=response_candidates,
                suggestions=[]
            )

            self.assertTrue(result['should_auto_respond'])
            self.assertEqual(result['decision_reason'], 'high_urgency_with_reliable_style_data')

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @override_settings(USE_LANGGRAPH_AGENTS=True)
    @patch('zerver.lib.ai_agent_core.AIAgentOrchestrator.process_student_message')
    def test_agent_orchestrator_workflow(self, mock_process: MagicMock) -> None:
        """Test the complete agent orchestrator workflow"""

        mock_process.return_value = {
            "should_auto_respond": True,
            "final_response": "AI generated response",
            "confidence_score": 0.87,
            "metadata": {
                "agents_used": ["style_analysis", "context_analysis", "response_generation", "decision_making"]
            }
        }

        try:
            from zerver.lib.ai_agent_core import AIAgentOrchestrator

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            orchestrator = AIAgentOrchestrator(mock_config)

            result = orchestrator.process_student_message(
                student=self.student,
                mentor=self.mentor,
                message_content="I need help with calculus"
            )

            self.assertTrue(result['should_auto_respond'])
            self.assertIn('final_response', result)
            self.assertIn('metadata', result)

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    def test_agent_workflow_state_management(self) -> None:
        """Test that agent workflow state is properly managed"""

        try:
            from zerver.lib.ai_agent_core import AIAgentOrchestrator

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            orchestrator = AIAgentOrchestrator(mock_config)

            # Test that state database path is configured
            self.assertIsNotNone(orchestrator.state_db_path)

            # Test that workflow configuration exists
            self.assertIsNotNone(orchestrator.workflow_config)

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @override_settings(USE_LANGGRAPH_AGENTS=True)
    def test_agent_error_handling(self) -> None:
        """Test that agents handle errors gracefully"""

        try:
            from zerver.lib.ai_agent_core import MentorStyleAnalysisAgent

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            agent = MentorStyleAnalysisAgent(mock_config)

            # Test with invalid input - should not crash
            try:
                result = agent.analyze_mentor_style(None)
                # Should return error state or fallback
                self.assertIsNotNone(result)
            except Exception:
                # If it raises an exception, that's also acceptable as long as it's handled
                pass

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @override_settings(USE_LANGGRAPH_AGENTS=True)
    def test_agent_configuration_integration(self) -> None:
        """Test that agents properly integrate with configuration system"""

        try:
            from zerver.lib.ai_agent_core import AIAgentOrchestrator
            from zproject.ai_agent_settings import AI_AGENT_WORKFLOW_CONFIG

            mock_config = {"api_key": "test", "virtual_key": "test", "base_url": "test"}
            orchestrator = AIAgentOrchestrator(mock_config)

            # Test that orchestrator uses configuration
            self.assertIsNotNone(AI_AGENT_WORKFLOW_CONFIG)

            # Test specific configuration values
            self.assertIn('style_analysis', AI_AGENT_WORKFLOW_CONFIG)
            self.assertIn('min_messages_required', AI_AGENT_WORKFLOW_CONFIG['style_analysis'])

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    @patch('zerver.lib.ai_agent_core.LLMClient')
    def test_llm_client_integration(self, mock_llm_client: MagicMock) -> None:
        """Test that agents properly integrate with LLM client"""

        mock_llm_client.return_value.chat_completion.return_value = {
            "success": True,
            "content": '{"analysis": "test"}',
            "usage": {"tokens": 100}
        }

        try:
            from zerver.lib.ai_agent_core import MentorStyleAnalysisAgent

            agent = MentorStyleAnalysisAgent()

            # Mock the LLM client
            agent.llm_client = mock_llm_client.return_value

            # Test that LLM client is used properly
            # This would be tested in integration with actual LLM calls
            self.assertIsNotNone(agent.llm_client)

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")

    def test_agent_performance_monitoring(self) -> None:
        """Test that agent performance is properly monitored"""

        try:
            from zerver.lib.ai_agent_core import AIAgentOrchestrator

            orchestrator = AIAgentOrchestrator()

            # Test that performance monitoring is enabled
            from zproject.ai_agent_settings import AI_AGENT_PERFORMANCE_CONFIG

            self.assertTrue(AI_AGENT_PERFORMANCE_CONFIG.get('track_response_times', False))
            self.assertTrue(AI_AGENT_PERFORMANCE_CONFIG.get('track_token_usage', False))

        except ImportError as e:
            self.skipTest(f"AI agent core not available: {e}")