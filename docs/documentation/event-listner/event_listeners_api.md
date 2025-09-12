# Event Listeners Plugin - API Reference

## 🎯 Core APIs

### Registration Decorator

#### @register_event_listener

Automatically registers an event listener class using its `name` attribute.

```python
@register_event_listener
class MyListener(MessageEventHandler):
    name = "my_listener"  # Required
    description = "My custom listener"  # Optional
    
    def handle_message(self, event):
        return True
```

## 🏗️ Base Classes

### BaseEventHandler

Abstract base class for all event handlers.

```python
class BaseEventHandler(ABC):
    # Required class attributes
    name: str = ""                    # Unique identifier
    description: str = ""             # Human-readable description
    supported_events: List[str] = []  # Event types this handler supports
    
    def __init__(self, config: Dict[str, Any] = None):
        pass
    
    # Abstract method - must implement
    @abstractmethod
    def handle_event(self, event: Dict[str, Any]) -> bool:
        """Handle an event. Return True if successful."""
        pass
    
    # Optional hooks
    def pre_process(self, event: Dict[str, Any]) -> bool:
        """Called before handle_event. Return False to skip."""
        return True
    
    def post_process(self, event: Dict[str, Any], success: bool) -> None:
        """Called after handle_event."""
        pass
    
    # Utility methods
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value."""
        pass
    
    def log_event(self, event: Dict[str, Any], message: str, level: str = 'info') -> None:
        """Log with event context."""
        pass
```

### MessageEventHandler

Specialized handler for message events.

```python
class MessageEventHandler(BaseEventHandler):
    supported_events = ['message', 'update_message', 'delete_message']
    
    # Abstract method - must implement
    @abstractmethod
    def handle_message(self, event: Dict[str, Any]) -> bool:
        """Handle new message events."""
        pass
    
    # Optional methods
    def handle_message_update(self, event: Dict[str, Any]) -> bool:
        """Handle message edit events."""
        return True
    
    def handle_message_delete(self, event: Dict[str, Any]) -> bool:
        """Handle message deletion events."""
        return True
    
    # Utility methods
    def get_message_data(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Extract message data from event."""
        return event.get('message', {})
    
    def is_private_message(self, event: Dict[str, Any]) -> bool:
        """Check if message is private."""
        pass
    
    def is_stream_message(self, event: Dict[str, Any]) -> bool:
        """Check if message is to a stream."""
        pass
    
    def get_sender_id(self, event: Dict[str, Any]) -> Optional[int]:
        """Get sender user ID."""
        pass
    
    def get_message_content(self, event: Dict[str, Any]) -> str:
        """Get message content text."""
        pass
```

### UserEventHandler

Specialized handler for user activity events.

```python
class UserEventHandler(BaseEventHandler):
    supported_events = ['presence', 'user_status', 'typing', 'realm_user']
    
    # Optional methods - implement as needed
    def handle_presence(self, event: Dict[str, Any]) -> bool:
        """Handle user presence changes (online/offline)."""
        return True
    
    def handle_user_status(self, event: Dict[str, Any]) -> bool:
        """Handle user status updates."""
        return True
    
    def handle_typing(self, event: Dict[str, Any]) -> bool:
        """Handle typing indicators."""
        return True
    
    def handle_realm_user(self, event: Dict[str, Any]) -> bool:
        """Handle user account changes."""
        return True
```

### StreamEventHandler

Specialized handler for stream/channel events.

```python
class StreamEventHandler(BaseEventHandler):
    supported_events = ['stream', 'subscription']
    
    # Optional methods - implement as needed
    def handle_stream(self, event: Dict[str, Any]) -> bool:
        """Handle stream creation/updates."""
        return True
    
    def handle_subscription(self, event: Dict[str, Any]) -> bool:
        """Handle subscription changes."""
        return True
```

## 🎛️ Registry API

### EventListenerRegistry

Main registry for managing event listeners.

```python
# Global instance
from zerver.event_listeners.registry import event_listener_registry

# Registration
event_listener_registry.register(name: str, handler_class: Type[BaseEventHandler])
event_listener_registry.unregister(name: str)

# Retrieval
event_listener_registry.get_handler_class(name: str) -> Type[BaseEventHandler]
event_listener_registry.get_handler_instance(name: str, config: Dict = None) -> BaseEventHandler
event_listener_registry.list_listeners() -> List[str]

# Discovery
event_listener_registry.autodiscover_listeners()
event_listener_registry.discover_app_listeners(app_name: str)
```

## ⚙️ Event Processor API

### EventProcessor

Core event processing engine.

```python
from zerver.event_listeners.processor import event_processor

# Processing
result = event_processor.process_event(event: Dict[str, Any]) -> Dict[str, Any]
results = event_processor.process_events(events: List[Dict]) -> List[Dict]

# Statistics
stats = event_processor.get_stats() -> Dict[str, Any]
event_processor.reset_stats()

# Configuration
event_processor.add_filter(filter_func: Callable)
event_processor.remove_filter(filter_name: str)
event_processor.set_config(config: Dict[str, Any])
```

### Process Result Format

```python
{
    'success': bool,                    # Overall success
    'event_type': str,                  # Type of event processed
    'processed_listeners': List[str],   # Successfully processed listeners
    'failed_listeners': Dict[str, str], # Failed listeners with error messages
    'processing_time_ms': float,        # Total processing time in milliseconds
    'filtered_out': bool,               # Whether event was filtered out
    'error_message': str                # Error message if failed
}
```

## 🗃️ Database Models API

### EventListener Model

```python
from zerver.event_listeners.models import EventListener

# Fields
name: CharField(max_length=100, unique=True)
handler_class: CharField(max_length=255)
description: TextField(blank=True)
event_types: JSONField(default=list)
is_enabled: BooleanField(default=True)
config: JSONField(default=dict)
created_at: DateTimeField(auto_now_add=True)
updated_at: DateTimeField(auto_now=True)

# Methods
def get_handler_instance() -> BaseEventHandler
def update_stats(success: bool, processing_time: float)
def is_handler_available() -> bool
```

### EventLog Model

```python
from zerver.event_listeners.models import EventLog

# Fields
listener_name: CharField(max_length=100)
event_type: CharField(max_length=50)
event_data: JSONField()
processing_time: FloatField()
success: BooleanField()
error_message: TextField(blank=True)
timestamp: DateTimeField(auto_now_add=True)

# Class methods
@classmethod
def log_event(cls, listener_name: str, event: Dict, success: bool, 
              processing_time: float, error_message: str = "")
```

### ListenerStats Model

```python
from zerver.event_listeners.models import ListenerStats

# Fields
listener_name: CharField(max_length=100, unique=True)
events_processed: IntegerField(default=0)
events_failed: IntegerField(default=0)
avg_processing_time: FloatField(default=0.0)
last_event_at: DateTimeField(null=True)

# Methods
def update_stats(success: bool, processing_time: float)
def get_success_rate() -> float
def get_events_per_hour() -> float
```

## 🔧 Integration API

### ZulipEventIntegration

Integration with Zulip's event system.

```python
from zerver.event_listeners.integration import zulip_event_integration

# Processing
zulip_event_integration.process_zulip_event(event: Dict, realm_id: int = None)

# Management
zulip_event_integration.get_active_listeners() -> List[str]
zulip_event_integration.start_listeners_daemon(listener_names: List[str] = None)

# Status
zulip_event_integration.enabled -> bool
```

## 📊 Event Format Reference

### Message Event

```python
{
    'type': 'message',
    'message': {
        'id': int,                    # Message ID
        'sender_id': int,             # Sender user ID
        'sender_full_name': str,      # Sender display name
        'sender_email': str,          # Sender email
        'content': str,               # Message content
        'timestamp': int,             # Unix timestamp
        'client': str,                # Client app name
        'recipient_id': int,          # Recipient ID
        'type': str,                  # 'stream' or 'private'
        'stream_id': int,             # Stream ID (if stream message)
        'subject': str,               # Topic name (if stream message)
        'display_recipient': [...],   # Recipient info
    },
    'realm_id': int                   # Realm ID
}
```

### Presence Event

```python
{
    'type': 'presence',
    'user_id': int,                   # User ID
    'email': str,                     # User email
    'presence': {
        'website': {
            'client': str,            # Client name
            'status': str,            # 'active' or 'idle'
            'timestamp': int,         # Unix timestamp
        }
    },
    'realm_id': int
}
```

### Stream Event

```python
{
    'type': 'stream',
    'op': str,                        # 'create', 'delete', 'update'
    'streams': [{
        'stream_id': int,             # Stream ID
        'name': str,                  # Stream name
        'description': str,           # Stream description
        'invite_only': bool,          # Private stream flag
        'is_web_public': bool,        # Web public flag
    }],
    'realm_id': int
}
```

## 🛠️ Management Commands API

### run_event_listeners

```bash
./manage.py run_event_listeners [options]

Options:
  --config-file PATH     Zulip config file (default: ~/.zuliprc)
  --listeners NAMES      Comma-separated listener names
  --event-types TYPES    Comma-separated event types to listen for
  --demo-mode           Run in demo mode (no Zulip client needed)
  --dry-run             Show configuration without processing
  --stats-interval N     Statistics reporting interval (seconds)
```

### list_event_listeners

```bash
./manage.py list_event_listeners [options]

Options:
  --show-stats          Include processing statistics
  --show-config         Include configuration details
  --status STATUS       Filter by status (enabled/disabled)
  --event-type TYPE     Filter by supported event type
  --format FORMAT       Output format (table/json/yaml)
```

## 🔍 Utility Functions

### Configuration Helpers

```python
from zerver.event_listeners.models import ListenerConfig

# Get configuration value
def get_listener_config(listener_name: str, key: str, default: Any = None) -> Any:
    pass

# Set configuration value
def set_listener_config(listener_name: str, key: str, value: Any) -> None:
    pass

# Get all configuration for a listener
def get_listener_configs(listener_name: str) -> Dict[str, Any]:
    pass
```

### Statistics Helpers

```python
from zerver.event_listeners.models import ListenerStats

# Get listener statistics
def get_listener_stats(listener_name: str) -> Dict[str, Any]:
    pass

# Get global statistics
def get_global_stats() -> Dict[str, Any]:
    pass
```

## 🚨 Error Handling

### Custom Exceptions

```python
from zerver.event_listeners.exceptions import (
    EventListenerError,       # Base exception
    HandlerNotFoundError,     # Handler not registered
    ConfigurationError,       # Invalid configuration
    ProcessingError,          # Event processing failed
    ValidationError,          # Event validation failed
)
```

### Error Response Format

```python
{
    'success': False,
    'error_type': str,        # Error classification
    'error_message': str,     # Human-readable message
    'error_details': dict,    # Additional error context
    'timestamp': str,         # ISO timestamp
    'listener_name': str,     # Listener that failed
    'event_type': str         # Event type being processed
}
```

This API reference provides the essential interfaces for building custom event listeners and integrating with the plugin system.