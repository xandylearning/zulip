# Event Listeners Plugin - Architecture Documentation

## 🏗️ System Architecture

### Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                    Zulip Event System                          │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │   Django    │    │   Tornado    │    │   WebSocket/    │   │
│  │   Backend   │────│   Server     │────│   Frontend      │   │
│  │             │    │              │    │                 │   │
│  └─────────────┘    └──────────────┘    └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│               Event Listeners Plugin                           │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │   Event     │    │   Handler    │    │   Database      │   │
│  │ Processor   │────│   Registry   │────│   Models        │   │
│  │             │    │              │    │                 │   │
│  └─────────────┘    └──────────────┘    └─────────────────┘   │
│         │                   │                     │           │
│         ▼                   ▼                     ▼           │
│  ┌─────────────┐    ┌──────────────┐    ┌─────────────────┐   │
│  │  Filters &  │    │   Base       │    │  Statistics &   │   │
│  │  Routing    │    │  Handlers    │    │  Logging        │   │
│  │             │    │              │    │                 │   │
│  └─────────────┘    └──────────────┘    └─────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## 📂 File Structure

```
zerver/event_listeners/
├── __init__.py                 # Plugin API exports with lazy imports
├── apps.py                    # Django app configuration
├── models.py                  # Database models for configuration/stats
├── base.py                    # Abstract base classes for handlers
├── registry.py                # Handler registration and discovery
├── processor.py               # Core event processing logic
├── integration.py             # Zulip system integration utilities
├── signals.py                 # Django signals integration
├── examples.py                # Example event listeners
├── tests.py                   # Comprehensive test suite
├── settings.py                # Configuration templates
├── setup_plugin.py            # Installation script
├── README.md                  # Plugin documentation
└── management/
    ├── __init__.py
    └── commands/
        ├── __init__.py
        ├── run_event_listeners.py    # Main daemon command
        └── list_event_listeners.py   # List/inspect command
```

## 🧩 Core Components

### 1. Event Processor (`processor.py`)

**Purpose**: Central coordinator for event processing

**Key Responsibilities**:
- Receives events from Zulip's event system
- Routes events to appropriate handlers based on event type
- Manages error handling, retries, and timeouts
- Tracks performance statistics and metrics
- Implements event filtering and transformation
- Handles concurrent processing and resource management

**Key Methods**:
```python
process_event(event) -> dict           # Process single event
process_events(events) -> list         # Process multiple events
get_stats() -> dict                    # Get processing statistics
add_filter(filter_func) -> None        # Add event filter
set_config(config) -> None             # Update configuration
```

### 2. Handler Registry (`registry.py`)

**Purpose**: Manages registration and discovery of event listeners

**Key Responsibilities**:
- Dynamic handler registration via decorators
- Automatic discovery from Django apps
- Handler instance management and caching
- Validation of handler classes
- Configuration-based handler loading

**Key Components**:
```python
EventListenerRegistry                  # Main registry class
@register_event_listener              # Decorator for registration
event_listener_registry               # Global registry instance
```

### 3. Base Handler Classes (`base.py`)

**Purpose**: Provides abstract base classes and common functionality

**Class Hierarchy**:
```
BaseEventHandler (Abstract)
├── MessageEventHandler (Messages: new, update, delete)
├── UserEventHandler (Users: presence, status, typing)
├── StreamEventHandler (Streams: create, update, subscribe)
├── FilteredEventHandler (With built-in filtering)
└── CompositeEventHandler (Delegates to multiple handlers)
```

**Common Features**:
- Configuration management
- Logging utilities with context
- Pre/post processing hooks
- Event validation and filtering
- Error handling and reporting

### 4. Database Models (`models.py`)

**Purpose**: Persistent storage for configuration, logs, and statistics

**Models**:

#### EventListener
```python
class EventListener(models.Model):
    name = CharField(max_length=100, unique=True)
    handler_class = CharField(max_length=255)
    description = TextField(blank=True)
    event_types = JSONField(default=list)
    is_enabled = BooleanField(default=True)
    config = JSONField(default=dict)
    created_at = DateTimeField(auto_now_add=True)
    updated_at = DateTimeField(auto_now=True)
```

#### EventLog
```python
class EventLog(models.Model):
    listener_name = CharField(max_length=100)
    event_type = CharField(max_length=50)
    event_data = JSONField()
    processing_time = FloatField()
    success = BooleanField()
    error_message = TextField(blank=True)
    timestamp = DateTimeField(auto_now_add=True)
```

#### ListenerStats & ListenerConfig
- Performance tracking and dynamic configuration
- Aggregated metrics and runtime settings

### 5. Integration Layer (`integration.py`)

**Purpose**: Integration with Zulip's existing event system

**Key Components**:
- `ZulipEventIntegration`: Main integration class
- Integration with Django signals
- Python Client API wrapper
- Event conversion utilities
- Service management functions

## 🔄 Event Flow

### 1. Event Generation (Zulip)
```
User Action → Django Backend → Event Generation → Tornado Distribution
```

### 2. Event Processing (Plugin)
```
Event Received → Processor → Filter → Route → Handler → Log Result
```

### Detailed Flow:

1. **Event Reception**:
   - Events received via Zulip Python Client API
   - Or directly from Django signals/hooks
   - Events normalized to standard format

2. **Preprocessing**:
   - Event validation and sanitization
   - Apply global filters (realm, user, age)
   - Add metadata and context

3. **Handler Selection**:
   - Registry lookup based on event type
   - Filter handlers by configuration
   - Load handler instances with config

4. **Event Processing**:
   - Call `pre_process()` hooks
   - Execute `handle_event()` method
   - Call `post_process()` hooks
   - Handle errors and retries

5. **Result Logging**:
   - Log to EventLog model
   - Update ListenerStats
   - Send notifications if configured

## 📊 Data Models & Relationships

```
EventListener (Configuration)
    ├── EventLog (Processing History)
    ├── ListenerStats (Performance Metrics)
    └── ListenerConfig (Dynamic Settings)

EventListener 1:N EventLog
EventListener 1:1 ListenerStats  
EventListener 1:N ListenerConfig
```

## 🔧 Configuration System

### 1. Static Configuration (`settings.py`)
```python
EVENT_LISTENERS_CONFIG = {
    'DEFAULT_LISTENERS': ['listener1', 'listener2'],
    'QUEUE_CONFIG': {...},
    'LOGGING': {...},
    'PERFORMANCE': {...},
}
```

### 2. Database Configuration (`ListenerConfig`)
- Runtime configuration changes
- Per-listener settings
- Feature flags and toggles

### 3. Environment Variables
- Production/development overrides
- Sensitive configuration (API keys)
- Deployment-specific settings

## 🚀 Performance & Scaling

### 1. Concurrency
- Async event processing
- Thread pool for handlers
- Resource pooling and limits

### 2. Memory Management
- Handler instance caching
- Event batch processing
- Configurable memory thresholds

### 3. Error Handling
- Circuit breaker pattern
- Exponential backoff retries
- Dead letter queue for failed events

### 4. Monitoring
- Real-time statistics
- Performance metrics
- Health checks and alerts

## 🔌 Extension Points

### 1. Custom Handlers
Implement `BaseEventHandler` or specialized subclasses:
```python
@register_event_listener
class CustomHandler(BaseEventHandler):
    name = "custom_handler"
    
    def handle_event(self, event):
        # Your custom logic
        return True
```

### 2. Custom Filters
Add event filters for preprocessing:
```python
def custom_filter(event):
    return event.get('realm_id') in allowed_realms

event_processor.add_filter(custom_filter)
```

### 3. Custom Integrations
Extend integration layer for new event sources:
```python
class CustomIntegration(ZulipEventIntegration):
    def process_custom_event(self, event):
        # Custom event processing
        pass
```

## 🧪 Testing Strategy

### 1. Unit Tests
- Individual component testing
- Mock dependencies
- Edge case coverage

### 2. Integration Tests
- End-to-end event flow
- Database integration
- Real event simulation

### 3. Performance Tests
- Load testing with high event volume
- Memory usage validation
- Concurrency testing

## 🔒 Security Considerations

### 1. Event Validation
- Input sanitization
- Type checking
- Size limits

### 2. Access Control
- Realm-based filtering
- User permission checks
- Rate limiting

### 3. Data Protection
- PII handling
- Log sanitization
- Secure configuration storage

## 📈 Monitoring & Observability

### 1. Metrics
- Events processed per second
- Handler success/failure rates
- Processing latency
- Memory and CPU usage

### 2. Logging
- Structured logging with context
- Different log levels per environment
- Centralized log aggregation

### 3. Health Checks
- Handler availability
- Database connectivity
- Resource utilization

This architecture provides a robust, scalable foundation for building event-driven features in Zulip while maintaining clean separation of concerns and extensibility.