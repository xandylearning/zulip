"""
Event Listener Registry
Manages registration and discovery of event listeners
"""

import importlib
import logging
from typing import Dict, List, Type, Any, Optional
from django.conf import settings
from django.apps import apps
from .base import BaseEventHandler

logger = logging.getLogger(__name__)


class EventListenerRegistry:
    """
    Registry for event listeners
    """
    
    def __init__(self):
        self.listeners: Dict[str, Type[BaseEventHandler]] = {}
        self.instances: Dict[str, BaseEventHandler] = {}
    
    def register(self, name: str, handler_class: Type[BaseEventHandler]) -> None:
        """
        Register an event handler class
        
        Args:
            name: Unique name for the handler
            handler_class: The handler class
        """
        if not issubclass(handler_class, BaseEventHandler):
            raise ValueError(f"Handler {handler_class} must inherit from BaseEventHandler")
        
        if name in self.listeners:
            logger.warning(f"Overriding existing listener '{name}'")
        
        self.listeners[name] = handler_class
        logger.debug(f"Registered event listener: {name}")
    
    def unregister(self, name: str) -> None:
        """Unregister an event handler"""
        if name in self.listeners:
            del self.listeners[name]
            if name in self.instances:
                del self.instances[name]
            logger.debug(f"Unregistered event listener: {name}")
    
    def get_handler_class(self, name: str) -> Optional[Type[BaseEventHandler]]:
        """Get handler class by name"""
        return self.listeners.get(name)
    
    def get_handler_instance(self, name: str, config: Dict[str, Any] = None) -> Optional[BaseEventHandler]:
        """
        Get or create handler instance
        
        Args:
            name: Handler name
            config: Configuration for the handler
            
        Returns:
            Handler instance or None if not found
        """
        # Check if we already have an instance with the same config
        cache_key = f"{name}_{hash(str(sorted((config or {}).items())))}"
        
        if cache_key in self.instances:
            return self.instances[cache_key]
        
        handler_class = self.get_handler_class(name)
        if handler_class:
            try:
                instance = handler_class(config)
                self.instances[cache_key] = instance
                return instance
            except Exception as e:
                logger.error(f"Failed to create handler instance '{name}': {e}")
        
        return None
    
    def list_listeners(self) -> List[str]:
        """Get list of registered listener names"""
        return list(self.listeners.keys())
    
    def get_listeners_for_event_type(self, event_type: str) -> List[str]:
        """Get list of listeners that can handle a specific event type"""
        matching_listeners = []
        
        for name, handler_class in self.listeners.items():
            if hasattr(handler_class, 'supported_events') and event_type in handler_class.supported_events:
                matching_listeners.append(name)
        
        return matching_listeners
    
    def autodiscover_listeners(self) -> None:
        """
        Auto-discover event listeners in installed apps
        Looks for 'event_listeners' modules in each Django app
        """
        for app_config in apps.get_app_configs():
            self.discover_app_listeners(app_config.name)
    
    def discover_app_listeners(self, app_name: str) -> None:
        """
        Discover event listeners in a specific app
        
        Args:
            app_name: Django app name
        """
        try:
            # Try to import app_name.event_listeners
            listeners_module_name = f"{app_name}.event_listeners"
            listeners_module = importlib.import_module(listeners_module_name)
            
            # Look for classes that inherit from BaseEventHandler
            for attr_name in dir(listeners_module):
                attr = getattr(listeners_module, attr_name)
                
                if (isinstance(attr, type) and 
                    issubclass(attr, BaseEventHandler) and 
                    attr != BaseEventHandler):
                    
                    # Register the handler
                    handler_name = getattr(attr, 'name', attr.__name__)
                    self.register(handler_name, attr)
                    
        except ImportError:
            # No event_listeners module in this app, skip
            pass
        except Exception as e:
            logger.error(f"Error discovering listeners in {app_name}: {e}")
    
    def load_from_settings(self) -> None:
        """Load listeners from Django settings"""
        listeners_config = getattr(settings, 'EVENT_LISTENERS', {})
        
        for name, config in listeners_config.items():
            handler_module = config.get('handler_module')
            handler_class = config.get('handler_class')
            
            if handler_module and handler_class:
                try:
                    module = importlib.import_module(handler_module)
                    cls = getattr(module, handler_class)
                    self.register(name, cls)
                except (ImportError, AttributeError) as e:
                    logger.error(f"Failed to load listener '{name}': {e}")
    
    def clear(self) -> None:
        """Clear all registered listeners"""
        self.listeners.clear()
        self.instances.clear()


# Global registry instance
event_listener_registry = EventListenerRegistry()


def register_listener(name: str):
    """
    Decorator to register an event listener class with a specific name
    
    Usage:
        @register_listener('my_listener')
        class MyEventListener(BaseEventHandler):
            ...
    """
    def decorator(handler_class: Type[BaseEventHandler]):
        event_listener_registry.register(name, handler_class)
        return handler_class
    return decorator


def register_event_listener(handler_class: Type[BaseEventHandler]):
    """
    Decorator to register an event listener class using its 'name' attribute
    
    Usage:
        @register_event_listener
        class MyEventListener(BaseEventHandler):
            name = 'my_listener'
            ...
    """
    # Get the name from the class, either from 'name' attribute or class name
    listener_name = getattr(handler_class, 'name', handler_class.__name__.lower())
    event_listener_registry.register(listener_name, handler_class)
    return handler_class


def get_listener(name: str, config: Dict[str, Any] = None) -> Optional[BaseEventHandler]:
    """
    Convenience function to get a listener instance
    
    Args:
        name: Listener name
        config: Configuration for the listener
        
    Returns:
        Listener instance or None
    """
    return event_listener_registry.get_handler_instance(name, config)


def list_available_listeners() -> List[str]:
    """Get list of all available listeners"""
    return event_listener_registry.list_listeners()


def get_listeners_for_event(event_type: str) -> List[str]:
    """Get listeners that can handle a specific event type"""
    return event_listener_registry.get_listeners_for_event_type(event_type)