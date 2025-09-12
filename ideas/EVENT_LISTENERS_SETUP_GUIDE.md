# Event Listeners Plugin Setup Guide

## 📍 Where to Place Configuration

Based on Zulip's project structure, here's exactly where to place the event listeners configuration:

### ✅ COMPLETED: Development Environment Setup

**File**: `zproject/dev_settings.py` (✅ Already configured)

The configuration has been added at **line 80-119**:

```python
# =============================================================================
# EVENT LISTENERS PLUGIN CONFIGURATION
# =============================================================================

# Enable the event listeners plugin
EVENT_LISTENERS_ENABLED = True

# Add event listeners to installed apps
if "zerver.event_listeners" not in EXTRA_INSTALLED_APPS:
    EXTRA_INSTALLED_APPS.append("zerver.event_listeners")

# Event listener configuration
EVENT_LISTENERS_CONFIG = {
    'DEFAULT_LISTENERS': [
        'message_logger',
        'user_status_tracker',
        'stream_activity_monitor',
    ],
    'QUEUE_CONFIG': {
        'max_retries': 3,
        'retry_delay': 5,
        'batch_size': 100,
    },
    'LOGGING': {
        'level': 'INFO',
        'file': None,  # Use console logging in development
    },
    'STATISTICS': {
        'enabled': True,
        'retention_days': 7,  # Shorter retention in development
    },
    'FILTERS': {
        'default_realm_filter': None,  # All realms
        'max_event_age': 3600,  # 1 hour
    },
    'PERFORMANCE': {
        'max_concurrent_handlers': 5,
        'handler_timeout': 30,
        'memory_threshold': 50 * 1024 * 1024,  # 50MB
    },
}
```

### ✅ COMPLETED: Logging Configuration

**File**: `zproject/computed_settings.py` (✅ Already configured)

Added at **line 1000-1005**:

```python
"zerver.event_listeners": {
    "level": "INFO",
    "handlers": [*DEFAULT_ZULIP_HANDLERS],
    "propagate": False,
},
```

### ✅ COMPLETED: Production Template

**File**: `zproject/prod_settings_template.py` (✅ Already configured)

Added comprehensive production configuration template at the end of the file.

## 🏃‍♂️ Quick Start (Development Environment)

Since the development configuration is already set up, you can immediately:

### 1. Run Migrations

```bash
cd /Users/straxs/Work/zulip
./manage.py migrate event_listeners
```

### 2. Test the Plugin

```bash
# List available listeners
./manage.py list_event_listeners

# Run event listeners
./manage.py run_event_listeners

# Run specific listeners
./manage.py run_event_listeners --listeners message_logger,user_status_tracker
```

### 3. Create Your First Custom Listener

Create a file `my_listeners.py`:

```python
from zerver.event_listeners import MessageEventHandler, register_event_listener

@register_event_listener
class MyListener(MessageEventHandler):
    name = "my_custom_listener"
    description = "My first custom event listener"
    
    def handle_message_event(self, event):
        message = event.get('message', {})
        sender = message.get('sender_full_name', 'Unknown')
        content = message.get('content', '')
        print(f"📨 New message from {sender}: {content}")
```

Then run:
```bash
./manage.py run_event_listeners --listeners my_custom_listener
```

## 🏭 Production Environment Setup

### For Production Deployment

1. **Copy the configuration from the template**:
   
   Open your production settings file (usually `/etc/zulip/settings.py` or `zproject/prod_settings.py`) and add:

   ```python
   # Enable the event listeners plugin
   EVENT_LISTENERS_ENABLED = True
   
   # Add to EXTRA_INSTALLED_APPS
   EXTRA_INSTALLED_APPS = getattr(globals(), 'EXTRA_INSTALLED_APPS', []) + ['zerver.event_listeners']
   
   # Production configuration
   EVENT_LISTENERS_CONFIG = {
       'DEFAULT_LISTENERS': [
           'message_logger',
           'user_status_tracker',
       ],
       'LOGGING': {
           'level': 'WARNING',  # Less verbose in production
           'file': '/var/log/zulip/event_listeners.log',
       },
       'PERFORMANCE': {
           'max_concurrent_handlers': 3,  # Conservative for production
           'handler_timeout': 30,
           'memory_threshold': 100 * 1024 * 1024,  # 100MB limit
       },
   }
   ```

2. **Run migrations**:
   ```bash
   sudo -u zulip /home/zulip/deployments/current/manage.py migrate event_listeners
   ```

3. **Setup service** (optional):
   ```bash
   python3 zerver/event_listeners/setup_plugin.py --setup-service systemd
   ```

## 📂 Project Structure Context

Zulip's settings system works as follows:

1. **`zproject/settings.py`** - Main settings entry point (imports other files)
2. **`zproject/configured_settings.py`** - Imports from other settings files
3. **`zproject/computed_settings.py`** - Core Django configuration (where logging is configured)
4. **`zproject/dev_settings.py`** - Development-specific settings ✅ (configured here)
5. **`zproject/prod_settings.py`** - Production-specific settings (you configure this)

### How INSTALLED_APPS Works

```python
# In computed_settings.py (line 270):
INSTALLED_APPS = [
    "django.contrib.auth",
    "confirmation", 
    "zerver",
    # ... other apps
]
INSTALLED_APPS += EXTRA_INSTALLED_APPS  # This is where our app gets added

# In dev_settings.py (line 78):
EXTRA_INSTALLED_APPS = ["zilencer", "analytics", "corporate"]
# ✅ We added "zerver.event_listeners" to this list
```

## 🔧 Configuration Options

### Available Settings

| Setting | Description | Default |
|---------|-------------|---------|
| `EVENT_LISTENERS_ENABLED` | Enable/disable the plugin | `False` |
| `DEFAULT_LISTENERS` | Listeners to start by default | `[]` |
| `QUEUE_CONFIG` | Queue processing settings | See template |
| `LOGGING` | Logging configuration | Console in dev, file in prod |
| `STATISTICS` | Statistics tracking | Enabled |
| `FILTERS` | Event filtering options | No filters |
| `PERFORMANCE` | Resource limits | Conservative defaults |

### Environment-Specific Recommendations

**Development**:
- `EVENT_LISTENERS_ENABLED = True`
- Console logging (`'file': None`)
- Lower retention periods
- More verbose logging (`'level': 'INFO'`)

**Production**:
- `EVENT_LISTENERS_ENABLED = True` (when ready)
- File logging (`'file': '/var/log/zulip/event_listeners.log'`)
- Longer retention periods
- Less verbose logging (`'level': 'WARNING'`)
- Conservative resource limits

## 🛠️ Next Steps

1. ✅ **Development is ready** - You can start using the plugin immediately
2. 🔄 **Run migrations**: `./manage.py migrate event_listeners`
3. 🧪 **Test basic functionality**: `./manage.py list_event_listeners`
4. 🏗️ **Create custom listeners**: Use the examples provided
5. 📊 **Monitor performance**: Check logs and statistics
6. 🚀 **Production deployment**: When ready, configure production settings

## 📚 Additional Resources

- **Plugin Documentation**: `zerver/event_listeners/README.md`
- **Example Listeners**: `zerver/event_listeners/examples.py`
- **API Reference**: See docstrings in base classes
- **Setup Script**: `zerver/event_listeners/setup_plugin.py`

The plugin is now properly integrated into Zulip's settings system and ready for use! 🎉