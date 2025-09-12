# Event Listeners Django App Plugin

A comprehensive Django app plugin system for Zulip that provides a flexible framework for handling real-time events. This plugin allows you to easily create custom event listeners that can react to messages, user activities, stream changes, and other Zulip events.

## Features

- **Flexible Event Handling**: Support for message, user, stream, and custom event types
- **Plugin Architecture**: Easy registration and discovery of event listeners
- **Database Integration**: Persistent configuration, statistics, and logging
- **Management Commands**: Built-in commands for running and managing listeners
- **Performance Monitoring**: Built-in statistics and performance tracking
- **Filtering System**: Fine-grained control over which events to process
- **Error Handling**: Robust error handling with retry mechanisms
- **Scalable Design**: Support for concurrent processing and resource management

## Quick Start

### 1. Enable the Plugin

Add to your Zulip settings file:

```python
# Enable event listeners plugin
EVENT_LISTENERS_ENABLED = True

# Add to INSTALLED_APPS
INSTALLED_APPS = [
    # ... other apps
    'zerver.event_listeners',
]
```

### 2. Run Migrations

```bash
./manage.py migrate event_listeners
```

### 3. Create Your First Event Listener

```python
# my_listeners.py
from zerver.event_listeners.base import MessageEventHandler
from zerver.event_listeners.registry import register_event_listener

@register_event_listener
class MyMessageListener(MessageEventHandler):
    name = "my_message_listener"
    description = "Handles incoming messages"
    
    def handle_message_event(self, event):
        message = event.get('message', {})
        print(f"New message: {message.get('content', '')}")
```

### 4. Run the Event Listener

```bash
./manage.py run_event_listeners --listeners my_message_listener
```

## Architecture

### Core Components

1. **Base Classes** (`base.py`): Abstract base classes for different event types
2. **Registry System** (`registry.py`): Dynamic discovery and registration of listeners
3. **Event Processor** (`processor.py`): Core event processing and routing logic
4. **Database Models** (`models.py`): Configuration, logging, and statistics storage
5. **Management Commands**: Tools for running and managing listeners

### Event Flow

```
Zulip Event → Event Processor → Filter → Route to Handlers → Execute → Log Results
```

## Creating Event Listeners

### Basic Message Listener

```python
from zerver.event_listeners.base import MessageEventHandler
from zerver.event_listeners.registry import register_event_listener

@register_event_listener
class SimpleMessageHandler(MessageEventHandler):
    name = "simple_message_handler"
    description = "Basic message processing"
    
    def handle_message_event(self, event):
        message = event.get('message', {})
        sender = message.get('sender_full_name')
        content = message.get('content')
        
        # Your message processing logic here
        print(f"{sender}: {content}")
```

### Multi-Event Listener

```python
from zerver.event_listeners.base import MessageEventHandler, UserEventHandler
from zerver.event_listeners.registry import register_event_listener

@register_event_listener
class MultiEventHandler(MessageEventHandler, UserEventHandler):
    name = "multi_event_handler"
    description = "Handles both messages and user events"
    
    def handle_message_event(self, event):
        # Handle message events
        pass
    
    def handle_user_event(self, event):
        # Handle user events (presence, status changes, etc.)
        pass
```

### Custom Event Listener with Configuration

```python
from zerver.event_listeners.base import BaseEventHandler
from zerver.event_listeners.registry import register_event_listener

@register_event_listener
class ConfigurableHandler(BaseEventHandler):
    name = "configurable_handler"
    description = "Handler with custom configuration"
    
    def __init__(self):
        super().__init__()
        self.config = self.get_listener_config()
    
    def can_handle(self, event):
        return event.get('type') in self.config.get('event_types', [])
    
    def handle_event(self, event):
        # Use self.config for configuration values
        max_length = self.config.get('max_content_length', 100)
        # ... processing logic
```

## Configuration

### Basic Configuration

```python
EVENT_LISTENERS_CONFIG = {
    'DEFAULT_LISTENERS': [
        'message_logger',
        'user_status_tracker',
    ],
    'QUEUE_CONFIG': {
        'max_retries': 3,
        'batch_size': 100,
    },
    'FILTERS': {
        'default_realm_filter': None,  # All realms
        'max_event_age': 3600,         # 1 hour
    },
}
```

### Listener-Specific Configuration

```python
EVENT_LISTENERS_CONFIG = {
    'LISTENER_CONFIG': {
        'my_listener': {
            'enabled': True,
            'custom_setting': 'value',
            'timeout': 30,
        },
    },
}
```

## Management Commands

### Run Event Listeners

```bash
# Run all default listeners
./manage.py run_event_listeners

# Run specific listeners
./manage.py run_event_listeners --listeners listener1,listener2

# Run with custom queue
./manage.py run_event_listeners --queue-name my_events

# Run in daemon mode
./manage.py run_event_listeners --daemon

# Set log level
./manage.py run_event_listeners --log-level DEBUG
```

### List Available Listeners

```bash
# List all listeners
./manage.py list_event_listeners

# Show statistics
./manage.py list_event_listeners --show-stats

# Show configuration
./manage.py list_event_listeners --show-config

# Filter by status
./manage.py list_event_listeners --status enabled
```

## Database Models

### EventListener
Stores registered event listeners and their configuration.

### EventLog
Logs processed events for debugging and analysis.

### ListenerStats
Tracks performance statistics for each listener.

### ListenerConfig
Stores dynamic configuration for listeners.

## Event Types

The plugin supports all Zulip event types:

- **Message Events**: New messages, message updates, deletions
- **User Events**: User presence, status changes, profile updates
- **Stream Events**: Stream creation, updates, subscriptions
- **Reaction Events**: Message reactions added/removed
- **Typing Events**: Typing indicators
- **Custom Events**: Any custom event type you define

## Advanced Features

### Event Filtering

```python
from zerver.event_listeners.base import FilteredEventHandler

class FilteredHandler(FilteredEventHandler):
    name = "filtered_handler"
    
    def get_event_filter(self):
        return {
            'event_types': ['message'],
            'realm_ids': [1, 2, 3],
            'user_ids': None,  # All users
        }
    
    def handle_event(self, event):
        # Only processes filtered events
        pass
```

### Composite Handlers

```python
from zerver.event_listeners.base import CompositeEventHandler

class CompositeHandler(CompositeEventHandler):
    name = "composite_handler"
    
    def get_child_handlers(self):
        return [
            MessageHandler(),
            UserHandler(),
            StreamHandler(),
        ]
```

### Statistics and Monitoring

```python
class MonitoredHandler(BaseEventHandler):
    def handle_event(self, event):
        with self.track_processing_time():
            # Your processing logic
            result = self.process_event(event)
            self.increment_counter('events_processed')
            return result
```

## Error Handling

The plugin includes comprehensive error handling:

- **Retry Mechanisms**: Automatic retry with exponential backoff
- **Error Logging**: Detailed error logs with context
- **Graceful Degradation**: Continue processing other events on failure
- **Circuit Breaker**: Temporarily disable failing handlers

## Performance Considerations

### Optimization Tips

1. **Use Async Processing**: For I/O-heavy operations
2. **Batch Processing**: Process multiple events together
3. **Caching**: Cache frequently accessed data
4. **Resource Limits**: Set appropriate memory and timeout limits
5. **Monitoring**: Use built-in statistics to monitor performance

### Scaling

- Run multiple listener processes
- Use message queues for distribution
- Implement horizontal scaling
- Monitor resource usage

## Production Deployment

### 1. Configuration

```python
EVENT_LISTENERS_CONFIG = {
    'LOGGING': {
        'file': '/var/log/zulip/event_listeners.log',
        'level': 'WARNING',
    },
    'PERFORMANCE': {
        'max_concurrent_handlers': 5,
        'memory_threshold': 50 * 1024 * 1024,
    },
}
```

### 2. Process Management

Use a process manager like systemd:

```ini
[Unit]
Description=Zulip Event Listeners
After=network.target

[Service]
Type=simple
User=zulip
WorkingDirectory=/path/to/zulip
ExecStart=/path/to/zulip/manage.py run_event_listeners
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 3. Monitoring

- Set up log monitoring
- Monitor process health
- Track performance metrics
- Set up alerts for failures

## Examples

See `examples.py` for complete working examples including:

- Message logging
- User status tracking
- Stream activity monitoring
- AI mentoring demo
- Comprehensive analytics

## Troubleshooting

### Common Issues

1. **Listeners not starting**: Check EVENT_LISTENERS_ENABLED setting
2. **Events not processed**: Verify event filters and handler registration
3. **Performance issues**: Check handler timeout and resource limits
4. **Database errors**: Ensure migrations are run

### Debug Mode

```bash
./manage.py run_event_listeners --log-level DEBUG --listeners my_listener
```

### Logs

Check logs in:
- Django logs: Standard Django logging
- Event listener logs: Configured log file
- Database logs: EventLog model

## API Reference

### Base Classes

- `BaseEventHandler`: Abstract base for all handlers
- `MessageEventHandler`: Specialized for message events
- `UserEventHandler`: Specialized for user events
- `StreamEventHandler`: Specialized for stream events
- `FilteredEventHandler`: Handler with built-in filtering
- `CompositeEventHandler`: Handler that delegates to child handlers

### Registry

- `@register_event_listener`: Decorator for automatic registration
- `event_listener_registry`: Global registry instance

### Models

- `EventListener`: Listener configuration
- `EventLog`: Event processing logs
- `ListenerStats`: Performance statistics
- `ListenerConfig`: Dynamic configuration

For more detailed API documentation, see the docstrings in each module.

## Contributing

1. Follow Django and Zulip coding standards
2. Add tests for new functionality
3. Update documentation
4. Ensure backward compatibility

## License

This plugin is part of the Zulip project and follows the same licensing terms.