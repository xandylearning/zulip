"""
Tests for the Event Listeners Django app plugin.
"""

import unittest
from unittest.mock import Mock, patch, MagicMock
from django.test import TestCase, override_settings
from django.db import transaction

from zerver.event_listeners.base import (
    BaseEventHandler, 
    MessageEventHandler,
    UserEventHandler,
    StreamEventHandler,
)
from zerver.event_listeners.registry import EventListenerRegistry, register_event_listener
from zerver.event_listeners.processor import EventProcessor
from zerver.event_listeners.models import EventListener, EventLog, ListenerStats


class BaseEventHandlerTest(TestCase):
    """Tests for BaseEventHandler"""
    
    def setUp(self):
        self.handler = BaseEventHandler()
        self.handler.name = "test_handler"
    
    def test_can_handle_default(self):
        """Test default can_handle implementation"""
        event = {"type": "message"}
        self.assertTrue(self.handler.can_handle(event))
    
    def test_handle_event_not_implemented(self):
        """Test that handle_event raises NotImplementedError"""
        event = {"type": "message"}
        with self.assertRaises(NotImplementedError):
            self.handler.handle_event(event)
    
    def test_get_listener_config(self):
        """Test getting listener configuration"""
        with patch.object(self.handler, '_get_config_from_db') as mock_config:
            mock_config.return_value = {"test": "value"}
            config = self.handler.get_listener_config()
            self.assertEqual(config, {"test": "value"})


class MessageEventHandlerTest(TestCase):
    """Tests for MessageEventHandler"""
    
    def setUp(self):
        self.handler = MessageEventHandler()
        self.handler.name = "test_message_handler"
    
    def test_can_handle_message_events(self):
        """Test that it can handle message events"""
        message_event = {"type": "message", "message": {"content": "test"}}
        self.assertTrue(self.handler.can_handle(message_event))
        
        non_message_event = {"type": "presence", "user_id": 1}
        self.assertFalse(self.handler.can_handle(non_message_event))
    
    def test_handle_event_calls_handle_message_event(self):
        """Test that handle_event calls handle_message_event for message events"""
        with patch.object(self.handler, 'handle_message_event') as mock_handle:
            event = {"type": "message", "message": {"content": "test"}}
            self.handler.handle_event(event)
            mock_handle.assert_called_once_with(event)
    
    def test_handle_message_event_not_implemented(self):
        """Test that handle_message_event raises NotImplementedError"""
        event = {"type": "message", "message": {"content": "test"}}
        with self.assertRaises(NotImplementedError):
            self.handler.handle_message_event(event)


class EventListenerRegistryTest(TestCase):
    """Tests for EventListenerRegistry"""
    
    def setUp(self):
        self.registry = EventListenerRegistry()
    
    def test_register_listener(self):
        """Test registering a listener"""
        @register_event_listener
        class TestListener(BaseEventHandler):
            name = "test_listener"
            def handle_event(self, event):
                pass
        
        # Check that the listener was registered in the global registry
        from zerver.event_listeners.registry import event_listener_registry
        self.assertIn("test_listener", event_listener_registry.listeners)
    
    def test_get_listener_by_name(self):
        """Test getting listener by name"""
        class TestListener(BaseEventHandler):
            name = "test_listener_by_name"
            def handle_event(self, event):
                pass
        
        listener_instance = TestListener()
        self.registry.register("test_listener_by_name", TestListener)
        
        retrieved = self.registry.get_listener("test_listener_by_name")
        self.assertEqual(retrieved, TestListener)
    
    def test_list_listeners(self):
        """Test listing all listeners"""
        class TestListener1(BaseEventHandler):
            name = "test_listener_1"
            def handle_event(self, event):
                pass
        
        class TestListener2(BaseEventHandler):
            name = "test_listener_2"  
            def handle_event(self, event):
                pass
        
        self.registry.register("test_listener_1", TestListener1)
        self.registry.register("test_listener_2", TestListener2)
        
        listeners = self.registry.list_listeners()
        self.assertIn("test_listener_1", listeners)
        self.assertIn("test_listener_2", listeners)


class EventProcessorTest(TestCase):
    """Tests for EventProcessor"""
    
    def setUp(self):
        self.processor = EventProcessor()
    
    def test_process_event_with_mock_handler(self):
        """Test processing an event with a mock handler"""
        # Create a mock handler
        mock_handler = Mock(spec=BaseEventHandler)
        mock_handler.name = "mock_handler"
        mock_handler.can_handle.return_value = True
        
        # Mock the registry to return our handler
        with patch('zerver.event_listeners.processor.event_listener_registry') as mock_registry:
            mock_registry.get_enabled_listeners.return_value = [mock_handler]
            
            event = {"type": "message", "content": "test"}
            self.processor.process_event(event)
            
            mock_handler.can_handle.assert_called_once_with(event)
            mock_handler.handle_event.assert_called_once_with(event)
    
    def test_process_event_filters_by_type(self):
        """Test that events are filtered by type"""
        # Create handlers for different event types
        message_handler = Mock(spec=MessageEventHandler)
        message_handler.name = "message_handler"
        message_handler.can_handle.side_effect = lambda e: e.get("type") == "message"
        
        user_handler = Mock(spec=UserEventHandler)
        user_handler.name = "user_handler"
        user_handler.can_handle.side_effect = lambda e: e.get("type") == "presence"
        
        with patch('zerver.event_listeners.processor.event_listener_registry') as mock_registry:
            mock_registry.get_enabled_listeners.return_value = [message_handler, user_handler]
            
            # Process a message event
            message_event = {"type": "message", "content": "test"}
            self.processor.process_event(message_event)
            
            # Only message handler should be called
            message_handler.handle_event.assert_called_once_with(message_event)
            user_handler.handle_event.assert_not_called()


@override_settings(EVENT_LISTENERS_ENABLED=True)
class ModelTest(TestCase):
    """Tests for Event Listener models"""
    
    def test_event_listener_model(self):
        """Test EventListener model"""
        listener = EventListener.objects.create(
            name="test_listener",
            handler_class=f"{BaseEventHandler.__module__}.BaseEventHandler",
            description="Test listener",
            is_enabled=True
        )
        
        self.assertEqual(listener.name, "test_listener")
        self.assertTrue(listener.is_enabled)
        self.assertIsNotNone(listener.created_at)
    
    def test_event_log_model(self):
        """Test EventLog model"""
        log = EventLog.objects.create(
            listener_name="test_listener",
            event_type="message",
            event_data={"content": "test"},
            processing_time=0.1,
            success=True
        )
        
        self.assertEqual(log.listener_name, "test_listener")
        self.assertEqual(log.event_type, "message")
        self.assertTrue(log.success)
    
    def test_listener_stats_model(self):
        """Test ListenerStats model"""
        stats = ListenerStats.objects.create(
            listener_name="test_listener",
            events_processed=100,
            events_failed=5,
            avg_processing_time=0.5,
            last_event_at=timezone.now()
        )
        
        self.assertEqual(stats.listener_name, "test_listener")
        self.assertEqual(stats.events_processed, 100)
        self.assertEqual(stats.events_failed, 5)


class IntegrationTest(TestCase):
    """Integration tests for the complete plugin system"""
    
    @override_settings(EVENT_LISTENERS_ENABLED=True)
    def test_end_to_end_message_processing(self):
        """Test end-to-end message processing"""
        
        # Create a test handler
        class TestIntegrationHandler(MessageEventHandler):
            name = "integration_test_handler"
            description = "Test handler for integration test"
            
            def __init__(self):
                super().__init__()
                self.processed_events = []
            
            def handle_message_event(self, event):
                self.processed_events.append(event)
        
        # Register the handler
        from zerver.event_listeners.registry import event_listener_registry  
        handler_instance = TestIntegrationHandler()
        event_listener_registry.register("integration_test_handler", TestIntegrationHandler)
        
        # Create processor and process event
        processor = EventProcessor()
        test_event = {
            "type": "message",
            "message": {
                "content": "Integration test message",
                "sender_id": 1,
                "recipient_id": 2
            }
        }
        
        with patch('zerver.event_listeners.processor.event_listener_registry') as mock_registry:
            mock_registry.get_enabled_listeners.return_value = [handler_instance]
            processor.process_event(test_event)
        
        # Verify the event was processed
        self.assertEqual(len(handler_instance.processed_events), 1)
        self.assertEqual(handler_instance.processed_events[0], test_event)


class ExampleListenersTest(TestCase):
    """Tests for example listeners"""
    
    def test_message_logger_listener(self):
        """Test the message logger example"""
        from zerver.event_listeners.examples import MessageLoggerListener
        
        listener = MessageLoggerListener()
        event = {
            "type": "message",
            "message": {
                "sender_full_name": "Test User",
                "content": "Test message content"
            }
        }
        
        with patch('builtins.print') as mock_print:
            listener.handle_message_event(event)
            mock_print.assert_called_once_with("[MESSAGE] Test User: Test message content")
    
    def test_user_status_listener(self):
        """Test the user status tracker example"""
        from zerver.event_listeners.examples import UserStatusListener
        
        listener = UserStatusListener()
        event = {
            "type": "presence",
            "user_id": 123,
            "presence": {"active": True}
        }
        
        with patch('builtins.print') as mock_print:
            listener.handle_user_event(event)
            mock_print.assert_called_once_with("[USER STATUS] User 123: {'active': True}")


if __name__ == '__main__':
    # Import timezone here to avoid import issues
    from django.utils import timezone
    unittest.main()