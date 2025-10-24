# Event Listener Implementation Guide

This guide explains how the **Event Listeners** system is implemented in Zulip and how to add it as a Django app plugin. The Event Listeners system provides a flexible framework for handling real-time events like messages, user activities, stream changes, and custom events.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [How Event Listeners Work](#how-event-listeners-work)
3. [Installation and Setup](#installation-and-setup)
4. [Creating Event Listeners](#creating-event-listeners)
5. [Registration System](#registration-system)
6. [Event Processing Pipeline](#event-processing-pipeline)
7. [Integration with Zulip Events](#integration-with-zulip-events)
8. [Database Models](#database-models)
9. [Management Commands](#management-commands)
10. [Examples](#examples)

---

## Architecture Overview

### Core Components

The Event Listeners system consists of several key components:

```
zerver/event_listeners/
├── apps.py              # Django app configuration and initialization
├── base.py              # Base classes for event handlers
├── registry.py          # Registration and discovery system
├── processor.py         # Event processing engine
├── models.py            # Database models for configuration and logging
├── signals.py           # Django signal handlers
├── integration.py       # Integration with Zulip's event system
├── examples.py          # Example implementations
└── management/
    └── commands/
        ├── run_event_listeners.py    # Start event listeners daemon
        └── list_event_listeners.py   # List available listeners
```

### Event Flow Diagram

```
┌─────────────────┐
│  Zulip Events   │ (Messages, User Status, Stream Changes)
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────┐
│    Event Integration Layer          │
│  (integration.py)                   │
│  - Captures Zulip events            │
│  - Converts to standard format      │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│     Event Processor                 │
│  (processor.py)                     │
│  - Routes events to handlers        │
│  - Manages execution                │
│  - Tracks statistics                │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Event Listener Registry           │
│  (registry.py)                      │
│  - Stores registered handlers       │
│  - Creates handler instances        │
└────────┬────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────┐
│   Event Handlers                    │
│  (base.py + custom implementations) │
│  - MessageEventHandler              │
│  - UserEventHandler                 │
│  - StreamEventHandler               │
│  - Custom handlers                  │
└─────────────────────────────────────┘
```

---

## How Event Listeners Work

### 1. Registration Phase

Event listeners are registered using a decorator pattern:

```python
from zerver.event_listeners.base import MessageEventHandler
from zerver.event_listeners.registry import register_event_listener

@register_event_listener
class MyMessageListener(MessageEventHandler):
    name = "my_message_listener"
    description = "Handles incoming messages"

    def handle_message(self, event):
        # Your logic here
        pass
```

**What happens during registration:**

1. The `@register_event_listener` decorator is called when the class is defined
2. The registry extracts the `name` attribute (or uses class name)
3. The handler class is stored in the global `event_listener_registry`
4. The class reference is kept for later instantiation

**Registry code (zerver/event_listeners/registry.py:175-188):**

```python
def register_event_listener(handler_class: Type[BaseEventHandler]):
    """
    Decorator to register an event listener class using its 'name' attribute
    """
    listener_name = getattr(handler_class, 'name', handler_class.__name__.lower())
    event_listener_registry.register(listener_name, handler_class)
    return handler_class
```

### 2. Initialization Phase

When Django starts, the app configuration initializes the event system:

**From zerver/event_listeners/apps.py:15-36:**

```python
class EventListenersConfig(AppConfig):
    name = 'zerver.event_listeners'

    def ready(self):
        """Called when Django app is ready"""
        if getattr(settings, 'EVENT_LISTENERS_ENABLED', False):
            self.register_event_listeners()
            logger.info("Event Listeners app initialized")

    def register_event_listeners(self):
        """Register default event listeners"""
        from . import signals  # Import signals to register them
        from .registry import event_listener_registry

        # Import examples to register the decorators
        from . import examples

        # Register built-in listeners
        event_listener_registry.autodiscover_listeners()

        logger.info(f"Registered {len(event_listener_registry.listeners)} event listeners")
```

**What happens:**

1. Django calls `ready()` when the app is loaded
2. If `EVENT_LISTENERS_ENABLED` is True, initialization starts
3. Signal handlers are imported and connected
4. Example listeners are imported (triggers decorator registration)
5. `autodiscover_listeners()` scans all installed apps for event listeners
6. All discovered listeners are registered in the global registry

### 3. Event Processing Phase

When an event occurs in Zulip:

**From zerver/event_listeners/processor.py:32-93:**

```python
class EventProcessor:
    def process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single event with all applicable listeners
        """
        event_type = event.get('type', 'unknown')
        event_id = event.get('id', 0)

        results = {
            'event_type': event_type,
            'processed_listeners': [],
            'failed_listeners': [],
            'success': False
        }

        # Get active listeners for this event type
        active_listeners = self.get_active_listeners_for_event(event)

        # Process with each listener
        for listener_config in active_listeners:
            listener_result = self.process_with_listener(event, listener_config)

            if listener_result['success']:
                results['processed_listeners'].append(listener_result)
            else:
                results['failed_listeners'].append(listener_result)

        return results
```

**Processing steps:**

1. **Event arrives**: From Zulip's event system (message sent, user status changed, etc.)
2. **Filter listeners**: Processor queries database for active listeners matching event type
3. **Instantiate handlers**: For each matching listener, create or retrieve handler instance
4. **Pre-processing**: Handler's `pre_process()` method is called (can filter events)
5. **Main processing**: Handler's `handle_event()` method is called with event data
6. **Post-processing**: Handler's `post_process()` method is called
7. **Statistics tracking**: Processing time and success/failure are recorded
8. **Logging**: Event processing is logged if enabled

### 4. Handler Execution

Inside a handler, the base class routes events to specialized methods:

**From zerver/event_listeners/base.py:91-146:**

```python
class MessageEventHandler(BaseEventHandler):
    """Base class specifically for message event handlers"""

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
```

**Handler hierarchy:**

```
BaseEventHandler (abstract base)
├── MessageEventHandler (routes message events)
│   ├── handle_message()
│   ├── handle_message_update()
│   └── handle_message_delete()
├── UserEventHandler (routes user events)
│   ├── handle_presence()
│   ├── handle_user_status()
│   ├── handle_typing()
│   └── handle_realm_user()
├── StreamEventHandler (routes stream events)
│   ├── handle_stream()
│   └── handle_subscription()
└── Custom handlers (your implementations)
```

---

## Installation and Setup

### Step 1: Add to INSTALLED_APPS

The Event Listeners app is located at `zerver/event_listeners/`, which makes it `zerver.event_listeners` in Python module notation.

**Option A: Add to Development Settings**

Edit `zproject/dev_settings.py`:

```python
# Around line 89
if "zerver.event_listeners" not in EXTRA_INSTALLED_APPS:
    EXTRA_INSTALLED_APPS.append("zerver.event_listeners")
```

**Option B: Add to Production Settings**

Edit `/etc/zulip/settings.py` (production) or `zproject/computed_settings.py`:

```python
EXTRA_INSTALLED_APPS = getattr(globals(), 'EXTRA_INSTALLED_APPS', []) + ['zerver.event_listeners']
```

### Step 2: Enable Event Listeners

Add to your settings:

```python
# Enable event listeners plugin
EVENT_LISTENERS_ENABLED = True
```

### Step 3: Run Migrations

```bash
python manage.py migrate zerver.event_listeners
```

This creates the following database tables:

- `event_listeners_eventlistener`: Stores listener configurations
- `event_listeners_eventlog`: Logs processed events
- `event_listeners_listenerstats`: Tracks performance statistics
- `event_listeners_listenerconfig`: Stores dynamic configuration

### Step 4: Verify Installation

```bash
# List available listeners
python manage.py list_event_listeners

# Expected output:
# Registered Event Listeners:
# ──────────────────────────────────────────
# 1. message_logger
#    Description: Logs all messages to the console
#    Event types: message, update_message, delete_message
#
# 2. user_status_tracker
#    Description: Tracks user status changes
#    Event types: presence, user_status, typing, realm_user
# ...
```

---

## Creating Event Listeners

### Basic Message Listener

```python
# my_app/event_listeners.py

from typing import Dict, Any
from zerver.event_listeners.base import MessageEventHandler
from zerver.event_listeners.registry import register_event_listener


@register_event_listener
class CustomMessageHandler(MessageEventHandler):
    """Custom handler for message events"""

    name = "custom_message_handler"
    description = "Processes messages for custom logic"

    def handle_message(self, event: Dict[str, Any]) -> bool:
        """
        Handle new message events

        Args:
            event: Event dictionary containing message data

        Returns:
            True if processed successfully
        """
        message = self.get_message_data(event)

        # Extract message information
        sender_id = message.get('sender_id')
        content = message.get('content', '')
        is_private = self.is_private_message(event)

        # Your custom logic here
        self.logger.info(f"Processing message from user {sender_id}: {content[:50]}...")

        # Example: Check for keywords
        if 'urgent' in content.lower():
            self.handle_urgent_message(message)

        return True

    def handle_urgent_message(self, message: Dict[str, Any]) -> None:
        """Handle urgent messages"""
        self.logger.warning(f"Urgent message detected: {message.get('id')}")
        # Send notification, alert admins, etc.
```

### Multi-Event Listener

Handle multiple event types in a single listener:

```python
@register_event_listener
class ComprehensiveListener(MessageEventHandler, UserEventHandler, StreamEventHandler):
    """Listener that handles multiple event types"""

    name = "comprehensive_listener"
    description = "Handles messages, users, and streams"

    def handle_message(self, event: Dict[str, Any]) -> bool:
        """Handle message events"""
        self.log_event(event, "Processing message event")
        # Your message logic
        return True

    def handle_presence(self, event: Dict[str, Any]) -> bool:
        """Handle user presence events"""
        user_id = event.get('user_id')
        status = event.get('presence', {})
        self.logger.info(f"User {user_id} presence: {status}")
        return True

    def handle_stream(self, event: Dict[str, Any]) -> bool:
        """Handle stream events"""
        op = event.get('op')  # create, update, delete
        streams = event.get('streams', [])
        for stream in streams:
            self.logger.info(f"Stream {op}: {stream.get('name')}")
        return True
```

### Filtered Event Listener

Use pre-processing to filter events:

```python
@register_event_listener
class FilteredMessageListener(MessageEventHandler):
    """Listener with custom filtering"""

    name = "filtered_listener"
    description = "Only processes messages from specific users"

    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        # List of user IDs to monitor
        self.monitored_users = self.get_config('monitored_users', [])

    def pre_process(self, event: Dict[str, Any]) -> bool:
        """Filter events before processing"""
        sender_id = self.get_sender_id(event)

        # Only process if sender is in monitored list
        if self.monitored_users and sender_id not in self.monitored_users:
            return False  # Skip this event

        return True  # Continue processing

    def handle_message(self, event: Dict[str, Any]) -> bool:
        """This only runs for filtered events"""
        message = self.get_message_data(event)
        self.logger.info(f"Processing monitored message: {message.get('id')}")
        return True
```

---

## Registration System

### How Registration Works

The registration system uses three main mechanisms:

#### 1. Decorator Registration

```python
@register_event_listener
class MyListener(BaseEventHandler):
    name = "my_listener"
```

**Registry implementation (zerver/event_listeners/registry.py:16-54):**

```python
class EventListenerRegistry:
    def __init__(self):
        self.listeners: Dict[str, Type[BaseEventHandler]] = {}
        self.instances: Dict[str, BaseEventHandler] = {}

    def register(self, name: str, handler_class: Type[BaseEventHandler]) -> None:
        """Register an event handler class"""
        if not issubclass(handler_class, BaseEventHandler):
            raise ValueError(f"Handler {handler_class} must inherit from BaseEventHandler")

        if name in self.listeners:
            logger.warning(f"Overriding existing listener '{name}'")

        self.listeners[name] = handler_class
        logger.debug(f"Registered event listener: {name}")
```

#### 2. Auto-Discovery

The registry can automatically discover listeners in installed apps:

```python
def autodiscover_listeners(self) -> None:
    """
    Auto-discover event listeners in installed apps
    Looks for 'event_listeners' modules in each Django app
    """
    for app_config in apps.get_app_configs():
        self.discover_app_listeners(app_config.name)

def discover_app_listeners(self, app_name: str) -> None:
    """Discover event listeners in a specific app"""
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
```

**To use auto-discovery:**

Create `your_app/event_listeners.py`:

```python
from zerver.event_listeners.base import MessageEventHandler

class MyAutoDiscoveredListener(MessageEventHandler):
    name = "auto_discovered"
    # No decorator needed!
```

#### 3. Settings-Based Registration

Define listeners in Django settings:

```python
# settings.py
EVENT_LISTENERS = {
    'my_listener': {
        'handler_module': 'my_app.handlers',
        'handler_class': 'MyEventHandler',
        'enabled': True,
    },
}
```

Load them:

```python
registry.load_from_settings()
```

### Global Registry Instance

There's a single global registry instance:

```python
# zerver/event_listeners/registry.py:157
event_listener_registry = EventListenerRegistry()
```

Access it anywhere:

```python
from zerver.event_listeners.registry import event_listener_registry

# Get all registered listeners
listeners = event_listener_registry.list_listeners()

# Get specific handler instance
handler = event_listener_registry.get_handler_instance('my_listener')
```

---

## Event Processing Pipeline

### Event Structure

Events follow this structure:

```python
{
    'type': 'message',  # Event type: message, presence, stream, etc.
    'id': 12345,        # Unique event ID
    'timestamp': 1234567890.123,
    'message': {        # Event-specific data
        'id': 67890,
        'sender_id': 123,
        'sender_full_name': 'John Doe',
        'recipient_id': 456,
        'content': 'Hello world!',
        'type': 'stream',  # or 'private'
        'stream_id': 10,
        'subject': 'general',
    },
    'realm_id': 1,      # Realm context
}
```

### Processing Flow

**1. Event arrives** (from integration layer):

```python
from zerver.event_listeners.integration import zulip_event_integration

# Process an event
zulip_event_integration.process_zulip_event(event, realm_id=1)
```

**2. Processor receives event** (zerver/event_listeners/processor.py:162-186):

```python
def get_active_listeners_for_event(self, event: Dict[str, Any]) -> List[EventListener]:
    """Get all active listeners that can handle this event"""
    event_type = event.get('type')

    # Query active listeners that support this event type
    listeners = EventListener.objects.filter(
        enabled=True,
        event_types__contains=[event_type]
    ).select_related('realm')

    # Additional filtering based on event context
    filtered_listeners = []
    for listener in listeners:
        if self.listener_matches_event(listener, event):
            filtered_listeners.append(listener)

    return filtered_listeners
```

**3. Handler instantiated**:

```python
def get_handler_instance(self, listener_config: EventListener) -> Optional[BaseEventHandler]:
    """Get or create handler instance for a listener"""
    cache_key = f"{listener_config.id}_{listener_config.updated_at.timestamp()}"

    if cache_key in self.active_handlers:
        return self.active_handlers[cache_key]

    handler_class = listener_config.get_handler_class()
    handler_instance = handler_class(listener_config.handler_config)

    self.active_handlers[cache_key] = handler_instance
    return handler_instance
```

**4. Pre-processing check**:

```python
# Pre-processing
if not handler.pre_process(event):
    result['success'] = True  # Skip but don't count as error
    return result
```

**5. Main processing**:

```python
# Main processing
success = handler.handle_event(event)
result['success'] = success
```

**6. Post-processing**:

```python
# Post-processing
handler.post_process(event, success)
```

**7. Statistics and logging**:

```python
# Update statistics
self.update_listener_stats(listener_config, processing_time_ms, success, error)

# Log event if enabled
if listener_config.log_events:
    self.log_event(listener_config, event, result)
```

---

## Integration with Zulip Events

### Integration Points

The Event Listeners system integrates with Zulip at multiple points:

#### 1. Django Signals

Django signals provide hooks into Zulip's operations:

**zerver/event_listeners/signals.py:14-36:**

```python
@receiver(post_save, sender=EventListener)
def on_listener_saved(sender, instance, created, **kwargs):
    """Handle EventListener save"""
    if created:
        logger.info(f"New event listener created: {instance.name}")
        # Initialize stats
        ListenerStats.objects.get_or_create(listener=instance)
    else:
        logger.info(f"Event listener updated: {instance.name}")
        # Clear cached handler instances when config changes
        event_processor.active_handlers.clear()
```

#### 2. Integration Layer

The integration layer captures Zulip events and forwards them:

**zerver/event_listeners/integration.py:14-93:**

```python
class ZulipEventIntegration:
    """
    Integration layer between Zulip's event system and event listeners plugin.
    """

    def process_zulip_event(self, event: Dict[str, Any], realm_id: Optional[int] = None) -> None:
        """
        Process a Zulip event through the event listeners system.

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
```

#### 3. Hook into Zulip's Event System

There are three main integration strategies:

**A. Message Sending Integration** (zerver/event_listeners/integration.py:122-165):

```python
def integrate_with_message_sending():
    """Integrate with Zulip's message sending pipeline"""
    from zerver.lib.message import do_send_messages

    # Store original function
    original_do_send_messages = do_send_messages

    def wrapped_do_send_messages(*args, **kwargs):
        """Wrapped version that triggers event listeners"""
        result = original_do_send_messages(*args, **kwargs)

        # Process through event listeners
        if result:
            for message in result:
                event = create_event_from_message(message)
                zulip_event_integration.process_zulip_event(event)

        return result

    # Note: This is monkey-patching - use Django signals in production
```

**B. Event Queue Integration** (zerver/event_listeners/integration.py:168-180):

```python
def integrate_with_event_queue():
    """
    Integrate with Zulip's event queue processing.

    This hooks into the queue system to capture events
    as they flow through the queue.
    """
    # Would integrate with zerver.lib.queue
    # to process events from the queue
```

**C. Real-time Events Integration** (zerver/event_listeners/integration.py:183-195):

```python
def integrate_with_realtime_events():
    """
    Integrate with Zulip's real-time event system.

    This hooks into Tornado event distribution
    to capture events in real-time.
    """
    # Would integrate with Tornado's event system
```

### Using Python Client for Events

You can also use Zulip's Python client to stream events:

```python
from zerver.event_listeners.integration import zulip_event_integration
import zulip

# Initialize client
client = zulip.Client(config_file="~/.zuliprc")

# Define callback
def event_callback(event):
    """Process each event through listeners"""
    zulip_event_integration.process_zulip_event(event)

# Start listening
client.call_on_each_event(
    event_callback,
    event_types=['message', 'presence', 'stream']
)
```

---

## Database Models

### EventListener Model

Stores registered event listeners and their configuration:

```python
class EventListener(models.Model):
    """Configuration for an event listener"""

    name = models.CharField(max_length=200, unique=True)
    description = models.TextField(blank=True)
    handler_module = models.CharField(max_length=500)
    handler_class = models.CharField(max_length=200)
    handler_config = models.JSONField(default=dict)

    # Event filtering
    event_types = models.JSONField(default=list)  # e.g. ['message', 'presence']
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE, null=True, blank=True)
    user_filter = models.JSONField(default=dict, blank=True)

    # Status
    enabled = models.BooleanField(default=True)
    log_events = models.BooleanField(default=False)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### EventLog Model

Logs processed events for debugging:

```python
class EventLog(models.Model):
    """Log of processed events"""

    listener = models.ForeignKey(EventListener, on_delete=models.CASCADE)
    event_type = models.CharField(max_length=100)
    event_id = models.BigIntegerField()
    event_data = models.JSONField()

    # Processing info
    processing_time_ms = models.IntegerField()
    success = models.BooleanField()
    error_message = models.TextField(blank=True)

    # Context
    user_id = models.IntegerField(null=True)
    realm_id = models.IntegerField(null=True)

    # Timestamp
    created_at = models.DateTimeField(auto_now_add=True)
```

### ListenerStats Model

Tracks performance statistics:

```python
class ListenerStats(models.Model):
    """Performance statistics for a listener"""

    listener = models.OneToOneField(EventListener, on_delete=models.CASCADE)

    # Counters
    total_events = models.BigIntegerField(default=0)
    successful_events = models.BigIntegerField(default=0)
    failed_events = models.BigIntegerField(default=0)

    # Performance
    avg_processing_time_ms = models.FloatField(default=0)
    min_processing_time_ms = models.IntegerField(default=0)
    max_processing_time_ms = models.IntegerField(default=0)

    # Status
    is_running = models.BooleanField(default=False)
    last_event_at = models.DateTimeField(null=True)
    last_error = models.TextField(blank=True)
    last_error_at = models.DateTimeField(null=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

---

## Management Commands

### run_event_listeners

Start the event listeners daemon:

```bash
# Run all default listeners
python manage.py run_event_listeners

# Run specific listeners
python manage.py run_event_listeners --listeners message_logger,user_status_tracker

# Run with custom queue
python manage.py run_event_listeners --queue-name my_events

# Run in daemon mode
python manage.py run_event_listeners --daemon

# Set log level
python manage.py run_event_listeners --log-level DEBUG
```

### list_event_listeners

List available listeners and their status:

```bash
# List all listeners
python manage.py list_event_listeners

# Show statistics
python manage.py list_event_listeners --show-stats

# Show configuration
python manage.py list_event_listeners --show-config

# Filter by status
python manage.py list_event_listeners --status enabled
```

---

## Examples

### Example 1: Simple Message Logger

**From zerver/event_listeners/examples.py:16-30:**

```python
@register_event_listener
class MessageLoggerListener(MessageEventHandler):
    """Simple message logger that logs all messages to console"""

    name = "message_logger"
    description = "Logs all messages to the console"

    def handle_message(self, event: Dict[str, Any]) -> bool:
        """Log message events"""
        message = event.get('message', {})
        sender_full_name = message.get('sender_full_name', 'Unknown')
        content = message.get('content', '')[:100]  # First 100 chars

        logger.info(f"Message from {sender_full_name}: {content}")
        print(f"[MESSAGE] {sender_full_name}: {content}")
        return True
```

### Example 2: User Status Tracker

**From zerver/event_listeners/examples.py:33-47:**

```python
@register_event_listener
class UserStatusListener(UserEventHandler):
    """Tracks user status changes"""

    name = "user_status_tracker"
    description = "Tracks user status changes (online/offline)"

    def handle_presence(self, event: Dict[str, Any]) -> bool:
        """Handle user presence events"""
        user_id = event.get('user_id')
        status = event.get('presence', {})

        logger.info(f"User {user_id} status changed: {status}")
        print(f"[USER STATUS] User {user_id}: {status}")
        return True
```

### Example 3: Multi-Event Analytics

**From zerver/event_listeners/examples.py:119-151:**

```python
@register_event_listener
class ComprehensiveAnalyticsListener(MessageEventHandler, UserEventHandler, StreamEventHandler):
    """Comprehensive analytics across all event types"""

    name = "comprehensive_analytics"
    description = "Comprehensive analytics across all event types"

    def __init__(self):
        super().__init__()
        self.analytics_data = {
            'messages': 0,
            'user_events': 0,
            'stream_events': 0
        }

    def handle_message(self, event: Dict[str, Any]) -> bool:
        """Track message analytics"""
        self.analytics_data['messages'] += 1
        logger.info(f"Analytics: {self.analytics_data['messages']} messages processed")
        return True

    def handle_presence(self, event: Dict[str, Any]) -> bool:
        """Track user event analytics"""
        self.analytics_data['user_events'] += 1
        return True

    def handle_stream(self, event: Dict[str, Any]) -> bool:
        """Track stream event analytics"""
        self.analytics_data['stream_events'] += 1
        return True
```

---

## Summary

The Event Listeners system is a powerful plugin architecture that provides:

1. **Flexible Event Handling**: Support for all Zulip event types
2. **Easy Registration**: Decorator-based registration with auto-discovery
3. **Pluggable Architecture**: Add/remove listeners without core changes
4. **Performance Tracking**: Built-in statistics and monitoring
5. **Database Integration**: Persistent configuration and logging
6. **Management Tools**: CLI commands for administration

### Key Files

- **apps.py**: Django app initialization (line 8-36)
- **base.py**: Base classes for handlers (line 15-320)
- **registry.py**: Registration system (line 16-212)
- **processor.py**: Event processing engine (line 18-316)
- **integration.py**: Zulip integration layer (line 14-307)
- **signals.py**: Django signal handlers (line 14-36)
- **models.py**: Database models
- **examples.py**: Example implementations (line 16-151)

### Adding Your Own Listener

1. Create a file: `your_app/event_listeners.py`
2. Import base classes and decorator
3. Create your handler class
4. Decorate with `@register_event_listener`
5. Implement required methods
6. The system auto-discovers and registers it!

**That's it!** The Event Listeners system handles the rest.

---

For more information, see:
- Event Listeners README: `zerver/event_listeners/README.md`
- Example implementations: `zerver/event_listeners/examples.py`
- Zulip Event System: https://zulip.readthedocs.io/en/latest/subsystems/events-system.html
