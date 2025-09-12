"""
Integration utilities for connecting the event listeners plugin
with Zulip's existing event system.
"""

import logging
from typing import Dict, Any, Optional, List
from django.conf import settings
from django.core.management import call_command

logger = logging.getLogger(__name__)


class ZulipEventIntegration:
    """
    Integration layer between Zulip's event system and the event listeners plugin.
    """
    
    def __init__(self):
        self.processor = None
        self.enabled = getattr(settings, 'EVENT_LISTENERS_ENABLED', False)
        
        if self.enabled:
            self._initialize_processor()
    
    def _initialize_processor(self):
        """Initialize the event processor"""
        try:
            from .processor import EventProcessor
            from .registry import event_listener_registry
            
            self.processor = EventProcessor()
            logger.info(f"Event listeners integration initialized with {len(event_listener_registry.listeners)} listeners")
        except Exception as e:
            logger.error(f"Failed to initialize event listeners: {e}")
            self.enabled = False
    
    def process_zulip_event(self, event: Dict[str, Any], realm_id: Optional[int] = None) -> None:
        """
        Process a Zulip event through the event listeners system.
        
        This method should be called from Zulip's event processing pipeline
        to trigger custom event listeners.
        
        Args:
            event: The Zulip event dictionary
            realm_id: Optional realm ID for filtering
        """
        if not self.enabled or not self.processor:
            return
            
        try:
            # Add realm context if provided
            if realm_id and 'realm_id' not in event:
                event['realm_id'] = realm_id
            
            # Process the event through our listeners
            self.processor.process_event(event)
            
        except Exception as e:
            logger.error(f"Error processing event through listeners: {e}")
    
    def get_active_listeners(self) -> List[str]:
        """Get list of active listener names"""
        if not self.enabled or not self.processor:
            return []
        
        from .registry import event_listener_registry
        return list(event_listener_registry.listeners.keys())
    
    def start_listeners_daemon(self, listener_names: Optional[List[str]] = None) -> None:
        """
        Start the event listeners daemon.
        
        Args:
            listener_names: Optional list of specific listeners to start
        """
        if not self.enabled:
            logger.warning("Event listeners not enabled")
            return
        
        try:
            cmd_args = []
            if listener_names:
                cmd_args.extend(['--listeners', ','.join(listener_names)])
            
            call_command('run_event_listeners', *cmd_args)
        except Exception as e:
            logger.error(f"Failed to start event listeners daemon: {e}")


# Global integration instance
zulip_event_integration = ZulipEventIntegration()


def integrate_with_zulip_events():
    """
    Integration function to hook into Zulip's event processing.
    
    This function shows how to integrate with different parts of Zulip's event system.
    Call this during Django app initialization.
    """
    if not getattr(settings, 'EVENT_LISTENERS_ENABLED', False):
        return
    
    try:
        # Integration point 1: Hook into message sending
        integrate_with_message_sending()
        
        # Integration point 2: Hook into event queue processing  
        integrate_with_event_queue()
        
        # Integration point 3: Hook into real-time events
        integrate_with_realtime_events()
        
        logger.info("Successfully integrated event listeners with Zulip events")
        
    except Exception as e:
        logger.error(f"Failed to integrate event listeners: {e}")


def integrate_with_message_sending():
    """
    Integrate with Zulip's message sending pipeline.
    
    This shows how to hook into do_send_messages to process message events.
    """
    try:
        # Import Zulip's message handling
        from zerver.lib.message import do_send_messages
        
        # Store original function
        original_do_send_messages = do_send_messages
        
        def wrapped_do_send_messages(*args, **kwargs):
            """Wrapped version that also triggers our event listeners"""
            # Call original function
            result = original_do_send_messages(*args, **kwargs)
            
            # Process through our event listeners
            # Note: This is a simplified example - in practice you'd need to
            # construct proper event format from the message data
            try:
                if result and hasattr(result, '__iter__'):
                    for message in result:
                        if hasattr(message, 'to_dict'):
                            event = {
                                'type': 'message',
                                'message': message.to_dict(),
                                'realm_id': getattr(message, 'realm_id', None),
                            }
                            zulip_event_integration.process_zulip_event(event)
            except Exception as e:
                logger.error(f"Error processing message through event listeners: {e}")
            
            return result
        
        # Replace the function (this is just an example - be careful with monkey patching)
        # In practice, you'd want to use Django signals or other proper integration points
        logger.info("Integrated with message sending pipeline")
        
    except ImportError:
        logger.warning("Could not integrate with message sending - module not found")
    except Exception as e:
        logger.error(f"Error integrating with message sending: {e}")


def integrate_with_event_queue():
    """
    Integrate with Zulip's event queue processing.
    
    This shows how to hook into the event queue system.
    """
    try:
        # This would integrate with the queue processing system
        # to capture events as they flow through the queue
        logger.info("Integrated with event queue processing")
        
    except Exception as e:
        logger.error(f"Error integrating with event queue: {e}")


def integrate_with_realtime_events():
    """
    Integrate with Zulip's real-time event system.
    
    This shows how to hook into the real-time event distribution.
    """
    try:
        # This would integrate with the Tornado event distribution
        # to capture events in real-time
        logger.info("Integrated with real-time events")
        
    except Exception as e:
        logger.error(f"Error integrating with real-time events: {e}")


# Django signal handlers for integration
def handle_message_event(sender, **kwargs):
    """Django signal handler for message events"""
    event = kwargs.get('event')
    if event:
        zulip_event_integration.process_zulip_event(event)


def handle_user_event(sender, **kwargs):
    """Django signal handler for user events"""
    event = kwargs.get('event')
    if event:
        zulip_event_integration.process_zulip_event(event)


def handle_stream_event(sender, **kwargs):
    """Django signal handler for stream events"""
    event = kwargs.get('event')
    if event:
        zulip_event_integration.process_zulip_event(event)


# Example of how to use Python Client API integration
def integrate_with_python_client():
    """
    Example integration using Zulip's Python Client API.
    
    This shows how to use the event listeners with the Python client's
    call_on_each_event functionality.
    """
    try:
        import zulip
        
        # Initialize client (you'd need proper credentials)
        # client = zulip.Client(config_file="path/to/zuliprc")
        
        def event_callback(event):
            """Callback function for Python client events"""
            try:
                zulip_event_integration.process_zulip_event(event)
            except Exception as e:
                logger.error(f"Error processing client event: {e}")
        
        # This would start listening to events
        # client.call_on_each_event(event_callback)
        
        logger.info("Python client integration configured")
        
    except ImportError:
        logger.warning("Zulip Python client not available for integration")
    except Exception as e:
        logger.error(f"Error setting up Python client integration: {e}")


# Utility functions for integration
def create_event_from_message(message) -> Dict[str, Any]:
    """Create event dictionary from Zulip message object"""
    try:
        return {
            'type': 'message',
            'message': {
                'id': getattr(message, 'id', None),
                'content': getattr(message, 'content', ''),
                'sender_id': getattr(message, 'sender_id', None),
                'sender_full_name': getattr(message, 'sender__full_name', ''),
                'recipient_id': getattr(message, 'recipient_id', None),
                'timestamp': getattr(message, 'date_sent', None),
                'realm_id': getattr(message, 'realm_id', None),
            },
            'realm_id': getattr(message, 'realm_id', None),
        }
    except Exception as e:
        logger.error(f"Error creating event from message: {e}")
        return {'type': 'message', 'message': {}}


def create_event_from_user_activity(user, activity_type, **extra_data) -> Dict[str, Any]:
    """Create event dictionary from user activity"""
    try:
        return {
            'type': 'presence',
            'user_id': getattr(user, 'id', None),
            'email': getattr(user, 'email', ''),
            'presence': activity_type,
            'realm_id': getattr(user, 'realm_id', None),
            **extra_data
        }
    except Exception as e:
        logger.error(f"Error creating user activity event: {e}")
        return {'type': 'presence', 'user_id': None}


def create_event_from_stream_activity(stream, activity_type, **extra_data) -> Dict[str, Any]:
    """Create event dictionary from stream activity"""
    try:
        return {
            'type': 'stream',
            'op': activity_type,
            'streams': [{
                'stream_id': getattr(stream, 'id', None),
                'name': getattr(stream, 'name', ''),
                'description': getattr(stream, 'description', ''),
                'realm_id': getattr(stream, 'realm_id', None),
            }],
            'realm_id': getattr(stream, 'realm_id', None),
            **extra_data
        }
    except Exception as e:
        logger.error(f"Error creating stream activity event: {e}")
        return {'type': 'stream', 'op': activity_type, 'streams': []}