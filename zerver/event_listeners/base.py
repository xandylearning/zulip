"""
Base classes for event listeners
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from django.utils import timezone


logger = logging.getLogger(__name__)


class BaseEventHandler(ABC):
    """
    Base class for all event handlers
    """
    
    # Handler metadata
    name: str = ""
    description: str = ""
    supported_events: List[str] = []
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"{self.__class__.__module__}.{self.__class__.__name__}")
    
    @abstractmethod
    def handle_event(self, event: Dict[str, Any]) -> bool:
        """
        Handle an event. Return True if processed successfully, False otherwise.
        
        Args:
            event: The event dictionary containing event data
            
        Returns:
            bool: True if event was processed successfully
        """
        pass
    
    def can_handle_event(self, event: Dict[str, Any]) -> bool:
        """
        Check if this handler can process the given event
        
        Args:
            event: The event dictionary
            
        Returns:
            bool: True if this handler can process the event
        """
        event_type = event.get('type')
        return event_type in self.supported_events
    
    def pre_process(self, event: Dict[str, Any]) -> bool:
        """
        Pre-processing hook. Called before handle_event.
        
        Args:
            event: The event dictionary
            
        Returns:
            bool: True to continue processing, False to skip
        """
        return True
    
    def post_process(self, event: Dict[str, Any], success: bool) -> None:
        """
        Post-processing hook. Called after handle_event.
        
        Args:
            event: The event dictionary
            success: Whether the event was processed successfully
        """
        pass
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def log_event(self, event: Dict[str, Any], message: str, level: str = 'info') -> None:
        """Log event processing with context"""
        event_type = event.get('type', 'unknown')
        event_id = event.get('id', 'unknown')
        
        log_message = f"[{event_type}:{event_id}] {message}"
        
        getattr(self.logger, level)(log_message)


class MessageEventHandler(BaseEventHandler):
    """
    Base class specifically for message event handlers
    """
    
    supported_events = ['message', 'update_message', 'delete_message']
    
    def handle_event(self, event: Dict[str, Any]) -> bool:
        """Route message events to specific handlers"""
        event_type = event.get('type')
        
        if event_type == 'message':
            return self.handle_message(event)
        elif event_type == 'update_message':
            return self.handle_message_update(event)
        elif event_type == 'delete_message':
            return self.handle_message_delete(event)
        
        return False
    
    @abstractmethod
    def handle_message(self, event: Dict[str, Any]) -> bool:
        """Handle new message events"""
        pass
    
    def handle_message_update(self, event: Dict[str, Any]) -> bool:
        """Handle message update events (default: no-op)"""
        return True
    
    def handle_message_delete(self, event: Dict[str, Any]) -> bool:
        """Handle message delete events (default: no-op)"""
        return True
    
    def get_message_data(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract message data from event"""
        return event.get('message', {})
    
    def is_private_message(self, event: Dict[str, Any]) -> bool:
        """Check if the message is a private message"""
        message = self.get_message_data(event)
        return message.get('type') == 'private'
    
    def is_stream_message(self, event: Dict[str, Any]) -> bool:
        """Check if the message is a stream message"""
        message = self.get_message_data(event)
        return message.get('type') == 'stream'
    
    def get_sender_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Get sender ID from message event"""
        message = self.get_message_data(event)
        return message.get('sender_id')
    
    def get_message_content(self, event: Dict[str, Any]) -> str:
        """Get message content"""
        message = self.get_message_data(event)
        return message.get('content', '')


class UserEventHandler(BaseEventHandler):
    """
    Base class for user-related event handlers
    """
    
    supported_events = ['presence', 'user_status', 'typing', 'realm_user']
    
    def handle_event(self, event: Dict[str, Any]) -> bool:
        """Route user events to specific handlers"""
        event_type = event.get('type')
        
        if event_type == 'presence':
            return self.handle_presence(event)
        elif event_type == 'user_status':
            return self.handle_user_status(event)
        elif event_type == 'typing':
            return self.handle_typing(event)
        elif event_type == 'realm_user':
            return self.handle_realm_user(event)
        
        return False
    
    def handle_presence(self, event: Dict[str, Any]) -> bool:
        """Handle presence events (default: no-op)"""
        return True
    
    def handle_user_status(self, event: Dict[str, Any]) -> bool:
        """Handle user status events (default: no-op)"""
        return True
    
    def handle_typing(self, event: Dict[str, Any]) -> bool:
        """Handle typing events (default: no-op)"""
        return True
    
    def handle_realm_user(self, event: Dict[str, Any]) -> bool:
        """Handle realm user events (default: no-op)"""
        return True


class StreamEventHandler(BaseEventHandler):
    """
    Base class for stream/channel event handlers
    """
    
    supported_events = ['stream', 'subscription']
    
    def handle_event(self, event: Dict[str, Any]) -> bool:
        """Route stream events to specific handlers"""
        event_type = event.get('type')
        
        if event_type == 'stream':
            return self.handle_stream(event)
        elif event_type == 'subscription':
            return self.handle_subscription(event)
        
        return False
    
    def handle_stream(self, event: Dict[str, Any]) -> bool:
        """Handle stream events (default: no-op)"""
        return True
    
    def handle_subscription(self, event: Dict[str, Any]) -> bool:
        """Handle subscription events (default: no-op)"""
        return True


class CompositeEventHandler(BaseEventHandler):
    """
    Handler that can compose multiple handlers together
    """
    
    def __init__(self, handlers: List[BaseEventHandler], config: Dict[str, Any] = None):
        super().__init__(config)
        self.handlers = handlers
        
        # Combine supported events from all handlers
        self.supported_events = []
        for handler in handlers:
            self.supported_events.extend(handler.supported_events)
        self.supported_events = list(set(self.supported_events))  # Remove duplicates
    
    def handle_event(self, event: Dict[str, Any]) -> bool:
        """Process event with all applicable handlers"""
        results = []
        
        for handler in self.handlers:
            if handler.can_handle_event(event):
                try:
                    result = handler.handle_event(event)
                    results.append(result)
                except Exception as e:
                    self.logger.error(f"Handler {handler.__class__.__name__} failed: {e}")
                    results.append(False)
        
        # Return True if at least one handler succeeded
        return any(results) if results else False


class FilteredEventHandler(BaseEventHandler):
    """
    Handler wrapper that adds filtering capabilities
    """
    
    def __init__(self, base_handler: BaseEventHandler, filters: Dict[str, Any] = None):
        super().__init__()
        self.base_handler = base_handler
        self.filters = filters or {}
        self.supported_events = base_handler.supported_events
    
    def handle_event(self, event: Dict[str, Any]) -> bool:
        """Handle event only if it passes filters"""
        if not self.passes_filters(event):
            return True  # Consider filtered events as "handled"
        
        return self.base_handler.handle_event(event)
    
    def passes_filters(self, event: Dict[str, Any]) -> bool:
        """Check if event passes all configured filters"""
        
        # Event type filter
        if 'event_types' in self.filters:
            if event.get('type') not in self.filters['event_types']:
                return False
        
        # User ID filter
        if 'user_ids' in self.filters:
            user_id = self.extract_user_id(event)
            if user_id and user_id not in self.filters['user_ids']:
                return False
        
        # Realm filter
        if 'realm_ids' in self.filters:
            realm_id = self.extract_realm_id(event)
            if realm_id and realm_id not in self.filters['realm_ids']:
                return False
        
        # Stream filter (for stream messages)
        if 'stream_ids' in self.filters:
            stream_id = self.extract_stream_id(event)
            if stream_id and stream_id not in self.filters['stream_ids']:
                return False
        
        # Custom filter function
        if 'custom_filter' in self.filters:
            filter_func = self.filters['custom_filter']
            if callable(filter_func) and not filter_func(event):
                return False
        
        return True
    
    def extract_user_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Extract user ID from event"""
        if event.get('type') == 'message':
            return event.get('message', {}).get('sender_id')
        elif event.get('type') in ['presence', 'user_status']:
            return event.get('user_id')
        elif event.get('type') == 'typing':
            return event.get('sender', {}).get('user_id')
        return None
    
    def extract_realm_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Extract realm ID from event"""
        # This would need to be implemented based on how realm info is stored in events
        return None
    
    def extract_stream_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Extract stream ID from event"""
        if event.get('type') == 'message':
            message = event.get('message', {})
            if message.get('type') == 'stream':
                return message.get('stream_id')
        return None