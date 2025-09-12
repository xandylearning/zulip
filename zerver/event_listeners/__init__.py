# Event Listeners Django App Plugin
# This app provides a modular event listening system for Zulip

default_app_config = 'zerver.event_listeners.apps.EventListenersConfig'

# Plugin metadata
__version__ = '1.0.0'
__author__ = 'Zulip Team'
__description__ = 'Flexible event listener plugin system for Zulip'

# Lazy imports to avoid circular import issues during Django startup
def _lazy_import_base():
    from .base import (
        BaseEventHandler,
        MessageEventHandler, 
        UserEventHandler,
        StreamEventHandler,
        FilteredEventHandler,
        CompositeEventHandler,
    )
    return {
        'BaseEventHandler': BaseEventHandler,
        'MessageEventHandler': MessageEventHandler,
        'UserEventHandler': UserEventHandler,
        'StreamEventHandler': StreamEventHandler,
        'FilteredEventHandler': FilteredEventHandler,
        'CompositeEventHandler': CompositeEventHandler,
    }

def _lazy_import_registry():
    from .registry import register_event_listener, event_listener_registry
    return {
        'register_event_listener': register_event_listener,
        'event_listener_registry': event_listener_registry,
    }

def _lazy_import_integration():
    from .integration import zulip_event_integration
    return {
        'zulip_event_integration': zulip_event_integration,
    }

# Make imports available at module level using __getattr__
def __getattr__(name):
    if name in ['BaseEventHandler', 'MessageEventHandler', 'UserEventHandler', 
                'StreamEventHandler', 'FilteredEventHandler', 'CompositeEventHandler']:
        return _lazy_import_base()[name]
    elif name in ['register_event_listener', 'event_listener_registry']:
        return _lazy_import_registry()[name]
    elif name == 'zulip_event_integration':
        return _lazy_import_integration()[name]
    else:
        raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Plugin API exports
__all__ = [
    'BaseEventHandler',
    'MessageEventHandler',
    'UserEventHandler', 
    'StreamEventHandler',
    'FilteredEventHandler',
    'CompositeEventHandler',
    'register_event_listener',
    'event_listener_registry',
    'zulip_event_integration',
]