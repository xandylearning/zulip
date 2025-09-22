# Modularity patterns in Zulip

This document explains different modularity patterns used in Zulip for organizing features, using real examples from the codebase to illustrate when and how to apply each pattern.

## Overview

Zulip supports multiple modularity patterns depending on the feature's scope, integration requirements, and lifecycle management needs. Understanding these patterns helps developers choose the right architecture for new features.

## Pattern 1: Integrated core extension

**Used by**: `zerver/event_listeners`
**Best for**: Features that extend Zulip's core messaging/event capabilities

### Characteristics

- Lives within `zerver/` (core Zulip backend structure)
- Deep integration with Zulip's existing systems
- Extensible framework that allows plugins
- Controlled via settings flags
- Auto-discovery and registration systems

### Example structure

```
zerver/event_listeners/
├── apps.py              # Django app config with auto-discovery
├── registry.py          # Plugin registration system
├── processor.py         # Event processing core
├── base.py             # Base classes for event listeners
├── examples.py         # Sample implementations
├── models.py           # Database models for event tracking
├── settings.py         # Configuration management
├── signals.py          # Django signal handlers
├── management/         # Django management commands
│   └── commands/
│       └── run_listeners.py
├── migrations/         # Database migrations
└── tests.py           # Comprehensive test suite
```

### Implementation details

```python
# apps.py - Auto-discovery on startup
class EventListenersConfig(AppConfig):
    name = 'zerver.event_listeners'

    def ready(self):
        if getattr(settings, 'EVENT_LISTENERS_ENABLED', False):
            self.register_event_listeners()

    def register_event_listeners(self):
        from .registry import event_listener_registry
        event_listener_registry.autodiscover_listeners()

# registry.py - Plugin system
class EventListenerRegistry:
    def __init__(self):
        self.listeners = {}

    def register(self, event_type, handler):
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(handler)

    def autodiscover_listeners(self):
        # Automatically find and register decorated functions
        pass

# Usage in settings
EVENT_LISTENERS_ENABLED = True
INSTALLED_APPS = [
    # ... other apps
    'zerver.event_listeners',
]
```

### When to use this pattern

- Extending Zulip's core event system
- Features that need deep integration with messaging
- Framework-like features that support multiple plugins
- Features that should feel like core Zulip functionality

### Advantages

- Seamless integration with Zulip's architecture
- Auto-discovery reduces configuration overhead
- Shared infrastructure and utilities
- Consistent with Zulip's existing patterns

### Disadvantages

- Tightly coupled to Zulip core
- Harder to extract or reuse elsewhere
- Must follow Zulip's development lifecycle

## Pattern 2: Standalone plugin module

**Used by**: `zulip_calls_plugin`
**Best for**: Self-contained features that could work independently

### Characteristics

- Completely independent Django app at project root
- Minimal coupling with Zulip core
- Full feature implementation (models, views, templates, static files)
- Independent installation/uninstallation
- Own URL patterns and middleware

### Example structure

```
zulip_calls_plugin/
├── apps.py                  # Independent app configuration
├── plugin_config.py         # Plugin-specific settings
├── context_processors.py    # Template context additions
├── middleware.py            # Request/response processing
├── integration.py          # Zulip integration points
├── models/                 # Call-specific data models
│   ├── __init__.py
│   ├── call.py
│   ├── participant.py
│   └── history.py
├── views/                  # API endpoints and UI views
│   ├── __init__.py
│   ├── call_api.py
│   ├── call_management.py
│   └── push_notifications.py
├── urls/                   # URL routing
│   ├── __init__.py
│   ├── api.py
│   └── ui.py
├── templates/              # UI templates
│   └── calls/
│       ├── call_interface.html
│       └── call_history.html
├── static/                 # Frontend assets
│   ├── css/
│   ├── js/
│   └── images/
├── management/             # Installation/management commands
│   └── commands/
│       ├── install_calls_plugin.py
│       └── uninstall_calls_plugin.py
├── migrations/             # Database schema changes
├── deployment/             # Deployment configurations
├── README.md              # Plugin documentation
├── TESTING_GUIDE.md       # Testing instructions
└── FIXES_DOCUMENTATION.md # Troubleshooting guide
```

### Implementation details

```python
# apps.py - Independent initialization
class ZulipCallsPluginConfig(AppConfig):
    name = "zulip_calls_plugin"
    verbose_name = "Zulip Calls Plugin"

    def ready(self) -> None:
        from .plugin_config import CallsPluginConfig
        CallsPluginConfig.apply_settings()

# plugin_config.py - Self-contained configuration
class CallsPluginConfig:
    @staticmethod
    def apply_settings():
        # Apply plugin-specific settings without modifying core
        pass

# Installation via management command
class Command(BaseCommand):
    help = 'Install the Zulip Calls Plugin'

    def handle(self, *args, **options):
        # Add to INSTALLED_APPS programmatically
        # Run migrations
        # Configure URL patterns
        # Setup static files
        pass
```

### When to use this pattern

- Features that could work with other chat platforms
- Complete product features (video calls, file sharing, etc.)
- Features with complex UI requirements
- Optional features that users might want to disable completely
- Features developed by external teams

### Advantages

- Complete isolation from Zulip core
- Independent development and release cycles
- Easy to distribute and install
- Can be open-sourced separately
- Minimal impact on core Zulip performance

### Disadvantages

- More complex installation process
- Potential for inconsistent UX
- Duplicate code for common functionality
- More complex deployment considerations

## Pattern 3: Subsystem extension (Standard Zulip approach)

**Used by**: Most core Zulip features (streams, users, messages, etc.)
**Best for**: Core Zulip functionality and tightly integrated features

### Characteristics

- Follows the standard Zulip architecture patterns
- Organized by functional areas within existing directories
- Deep integration with Zulip's systems
- Shares common infrastructure

### Example structure

```
# Following standard Zulip patterns
zerver/
├── models/
│   └── your_feature.py          # Data models
├── views/
│   └── your_feature.py          # API endpoints
├── lib/
│   └── your_feature.py          # Business logic
├── actions/
│   └── your_feature.py          # Data modification operations
└── tests/
    └── test_your_feature.py     # Test suite

web/
├── src/
│   ├── your_feature.ts          # Frontend logic
│   └── your_feature_ui.ts       # UI interactions
├── templates/
│   └── your_feature.hbs         # Templates
└── styles/
    └── your_feature.css         # Styles
```

### When to use this pattern

- Core Zulip features
- Features that require deep integration
- Features that share significant code with existing functionality
- Features that should feel native to Zulip

## Choosing the right pattern

### Decision matrix

| Criteria | Core Extension | Standalone Plugin | Subsystem Extension |
|----------|---------------|-------------------|-------------------|
| **Integration depth** | Medium-High | Low | High |
| **Independence** | Medium | High | Low |
| **Reusability** | Medium | High | Low |
| **Development complexity** | Medium | High | Low |
| **Installation complexity** | Low | High | None |
| **Maintenance burden** | Medium | Low | Low |

### Questions to ask

1. **Could this feature work with other chat platforms?**
   - Yes → Consider Standalone Plugin
   - No → Consider other patterns

2. **Does this extend Zulip's core messaging/event capabilities?**
   - Yes → Consider Core Extension
   - No → Consider other patterns

3. **Is this a core Zulip feature that most users would expect?**
   - Yes → Use Subsystem Extension
   - No → Consider other patterns

4. **Will this feature share significant code with existing Zulip features?**
   - Yes → Use Subsystem Extension
   - No → Consider other patterns

5. **Do you need the ability to easily install/uninstall this feature?**
   - Yes → Use Standalone Plugin
   - No → Consider other patterns

## Migration between patterns

### From Subsystem Extension to Core Extension

When a subsystem needs to become extensible:

1. Create the extension framework in `zerver/your_feature_framework/`
2. Move core logic to framework base classes
3. Implement existing functionality as framework plugins
4. Add registry and auto-discovery systems

### From Core Extension to Standalone Plugin

When a feature needs more independence:

1. Extract all feature-specific code to plugin directory
2. Define minimal integration points with Zulip core
3. Create installation/uninstallation procedures
4. Package as independent Django app

### From Standalone Plugin to Core

When a plugin becomes essential:

1. Move plugin code into appropriate `zerver/` directories
2. Integrate with existing Zulip patterns
3. Remove plugin infrastructure
4. Update documentation and tests

## Best practices

### For all patterns

1. **Start with tests** - Define expected behavior before implementation
2. **Follow existing conventions** - Maintain consistency with Zulip codebase
3. **Document thoroughly** - Include setup, usage, and troubleshooting guides
4. **Plan for scale** - Consider performance impact of your architecture choice

### For Core Extensions

1. **Design for extensibility** - Create clear plugin interfaces
2. **Provide examples** - Include sample implementations
3. **Handle errors gracefully** - Don't break core Zulip functionality
4. **Use feature flags** - Allow gradual rollout and easy disabling

### For Standalone Plugins

1. **Minimize dependencies** - Reduce coupling with Zulip internals
2. **Version your APIs** - Plan for compatibility across Zulip versions
3. **Provide migration paths** - Handle plugin updates gracefully
4. **Document integration points** - Clearly specify Zulip requirements

### For Subsystem Extensions

1. **Follow Zulip patterns** - Use existing infrastructure and conventions
2. **Integrate with events system** - Support real-time updates
3. **Handle permissions properly** - Use Zulip's authorization framework
4. **Test thoroughly** - Ensure no regressions in existing functionality

## Real-world examples

### Event Listeners (Core Extension)

The event listeners framework demonstrates how to create an extensible system within Zulip:

- **Registry system** for auto-discovering plugins
- **Base classes** providing common functionality
- **Settings integration** for configuration
- **Management commands** for operational tasks

### Calls Plugin (Standalone Plugin)

The calls plugin shows how to implement a complete feature independently:

- **Self-contained** models, views, and templates
- **Installation procedures** that modify Zulip configuration
- **Integration points** that connect to Zulip's user system
- **Independent static assets** and frontend code

### Streams (Subsystem Extension)

Zulip's stream functionality exemplifies the standard subsystem pattern:

- **Models** in `zerver/models/streams.py`
- **API views** in `zerver/views/streams.py`
- **Business logic** in `zerver/lib/streams.py`
- **Actions** in `zerver/actions/streams.py`
- **Frontend code** distributed across `web/src/`

## Conclusion

Understanding these modularity patterns helps you make informed architectural decisions. Choose the pattern that best fits your feature's requirements for integration, independence, and lifecycle management. When in doubt, start with the Subsystem Extension pattern and migrate to other patterns as requirements become clearer.

Remember that the choice of pattern affects not just your development experience, but also the experience of users, administrators, and other developers working with your feature. Consider the long-term implications of your architectural decisions.