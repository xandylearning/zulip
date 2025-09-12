# Event Listeners Plugin - Quick Start Guide

## 🎯 Overview

The **Event Listeners Plugin** is a Django app that provides a flexible framework for handling real-time events in Zulip. This guide will get you started quickly.

## 🚀 Quick Start

### 1. Basic Setup (Already Done)

The plugin is already configured in your development environment:
- Configuration: `zproject/dev_settings.py` (lines 80-119)
- Database models created: Ready for migration

### 2. Run Migration

```bash
cd /srv/zulip
./manage.py migrate event_listeners
```

### 3. Test the Plugin

```bash
# Test in demo mode (no Zulip client needed)
./manage.py run_event_listeners --demo-mode

# List available listeners
./manage.py list_event_listeners
```

## 🎨 Create Your First Listener

Create a file `my_listeners.py`:

```python
from zerver.event_listeners import MessageEventHandler, register_event_listener

@register_event_listener
class WelcomeMessageListener(MessageEventHandler):
    name = "welcome_message_listener"
    description = "Welcomes new users when they send their first message"
    
    def handle_message(self, event):
        message = self.get_message_data(event)
        sender_name = message.get('sender_full_name', 'Unknown')
        content = message.get('content', '')
        
        print(f"📨 Welcome message from {sender_name}: {content}")
        
        # Add your custom logic here
        return True  # Return True if processed successfully
```

## 🛠️ Available Commands

### run_event_listeners

```bash
# Demo mode (for testing without Zulip client)
./manage.py run_event_listeners --demo-mode

# Run specific listeners
./manage.py run_event_listeners --demo-mode --listeners welcome_message_listener

# Dry run (show what would happen)
./manage.py run_event_listeners --demo-mode --dry-run

# Real mode (requires .zuliprc file)
./manage.py run_event_listeners --listeners welcome_message_listener
```

### list_event_listeners

```bash
# List all listeners
./manage.py list_event_listeners

# Show with statistics and configuration
./manage.py list_event_listeners --show-stats --show-config
```

## 📋 Event Types

The plugin supports all Zulip event types:

- **Message Events**: `message`, `update_message`, `delete_message`
- **User Events**: `presence`, `user_status`, `typing`, `realm_user`  
- **Stream Events**: `stream`, `subscription`
- **Other Events**: `reaction`, `typing`, `custom`

## 🧩 Base Classes

### MessageEventHandler
For handling message-related events:
```python
@register_event_listener
class MyMessageHandler(MessageEventHandler):
    name = "my_message_handler"
    
    def handle_message(self, event):
        # Handle new messages
        return True
    
    def handle_message_update(self, event):
        # Handle message edits (optional)
        return True
    
    def handle_message_delete(self, event):
        # Handle message deletions (optional)
        return True
```

### UserEventHandler
For handling user activity events:
```python
@register_event_listener
class MyUserHandler(UserEventHandler):
    name = "my_user_handler"
    
    def handle_presence(self, event):
        # Handle user presence changes
        return True
    
    def handle_typing(self, event):
        # Handle typing indicators
        return True
```

### StreamEventHandler
For handling stream/channel events:
```python
@register_event_listener
class MyStreamHandler(StreamEventHandler):
    name = "my_stream_handler"
    
    def handle_stream(self, event):
        # Handle stream creation/updates
        return True
    
    def handle_subscription(self, event):
        # Handle subscription changes
        return True
```

## 💡 Real-World Examples

### AI Mentoring System
```python
@register_event_listener
class AIMentoringListener(MessageEventHandler):
    name = "ai_mentoring_system"
    description = "AI mentoring with human-like delays"
    
    def handle_message(self, event):
        message = self.get_message_data(event)
        sender_id = message.get('sender_id')
        content = message.get('content')
        
        if self.is_student_message(sender_id):
            # Learn from the interaction
            self.learn_communication_pattern(sender_id, content)
            
            # Schedule AI response with human-like delay
            self.schedule_ai_response(sender_id, content)
        
        return True
    
    def is_student_message(self, sender_id):
        # Check if sender is a student
        return True  # Implement your logic
    
    def learn_communication_pattern(self, sender_id, content):
        # Analyze and store communication patterns
        print(f"Learning from student {sender_id}: {content[:50]}...")
    
    def schedule_ai_response(self, sender_id, content):
        # Schedule AI response with delay (30-300 seconds)
        import random
        delay = random.randint(30, 300)
        print(f"Scheduling AI response in {delay} seconds")
```

### Content Moderation
```python
@register_event_listener
class ContentModerationSystem(MessageEventHandler):
    name = "content_moderation"
    description = "Automated content moderation"
    
    def handle_message(self, event):
        message = self.get_message_data(event)
        content = message.get('content', '')
        message_id = message.get('id')
        
        if self.is_inappropriate(content):
            self.flag_message(message_id, "inappropriate_content")
        
        if self.is_spam(content):
            self.delete_message(message_id)
        
        return True
    
    def is_inappropriate(self, content):
        inappropriate_words = ['spam', 'inappropriate']
        return any(word in content.lower() for word in inappropriate_words)
    
    def is_spam(self, content):
        return len(content) > 1000 and content.count('http') > 5
    
    def flag_message(self, message_id, reason):
        print(f"🚩 Flagged message {message_id}: {reason}")
    
    def delete_message(self, message_id):
        print(f"🗑️ Deleted message {message_id}")
```

## ⚙️ Configuration

### Basic Configuration (Already Set)
```python
# In zproject/dev_settings.py
EVENT_LISTENERS_ENABLED = True
EVENT_LISTENERS_CONFIG = {
    'DEFAULT_LISTENERS': [
        'message_logger',
        'user_status_tracker',
        'stream_activity_monitor',
    ],
    'LOGGING': {
        'level': 'INFO',
        'file': None,  # Console in development
    },
}
```

### Advanced Configuration
```python
EVENT_LISTENERS_CONFIG = {
    'PERFORMANCE': {
        'max_concurrent_handlers': 10,
        'handler_timeout': 30,
        'memory_threshold': 100 * 1024 * 1024,  # 100MB
    },
    'LISTENER_CONFIG': {
        'ai_mentoring_system': {
            'response_delay_min': 30,
            'response_delay_max': 300,
            'learning_enabled': True,
        },
    },
}
```

## 🔧 Troubleshooting

### Issue 1: No Event Listeners Registered

**Problem**: Shows "Registered 0 event listeners"

**Solution**:
1. Make sure your listener files are imported
2. Use `@register_event_listener` decorator
3. Set `name` attribute on your listener class

```python
# Make sure to import your listeners module somewhere
from . import my_listeners  # This triggers registration
```

### Issue 2: Zulip Client Error

**Problem**: "api_key or email not specified"

**Solution**: Use demo mode for testing:
```bash
./manage.py run_event_listeners --demo-mode
```

For production, create `.zuliprc` file:
```ini
[api]
email=your-bot@example.com
key=your-api-key
site=https://your-zulip-domain.com
```

### Issue 3: Import Errors

**Problem**: Cannot import event listeners

**Solution**: Check Python path and Django setup:
```bash
# Test imports
./manage.py shell
>>> from zerver.event_listeners import MessageEventHandler
>>> from zerver.event_listeners.registry import event_listener_registry
>>> print(event_listener_registry.list_listeners())
```

## 📚 Next Steps

1. **Read Full Documentation**: `docs/event_listeners_architecture.md`
2. **See More Examples**: `zerver/event_listeners/examples.py`
3. **API Reference**: `docs/event_listeners_api.md`
4. **Production Setup**: `docs/event_listeners_production.md`

## 🎊 Success!

You now have a working event listeners plugin! Start with the demo mode to test your listeners, then move to production setup when ready.

**Quick Commands Recap**:
```bash
# Test the plugin
./manage.py run_event_listeners --demo-mode

# List listeners
./manage.py list_event_listeners

# Run specific listeners
./manage.py run_event_listeners --demo-mode --listeners your_listener_name
```