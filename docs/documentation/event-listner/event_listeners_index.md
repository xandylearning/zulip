# Event Listeners Plugin - Complete Documentation

## 📚 Documentation Index

Welcome to the comprehensive documentation for the **Event Listeners Plugin** - a flexible Django app for handling real-time events in Zulip.

## 🎯 Getting Started

### [Quick Start Guide](event_listeners_quick_start.md)
Start here! Get the plugin running in under 10 minutes with practical examples.

**Topics Covered:**
- Basic setup and configuration
- Creating your first listener
- Testing with demo mode
- Common commands and troubleshooting

**Perfect for:** New users, developers getting started

---

## 🏗️ Architecture & Design

### [Architecture Documentation](event_listeners_architecture.md)
Deep dive into the plugin's design, components, and data flow.

**Topics Covered:**
- System architecture overview
- Core components and relationships
- Event flow and processing pipeline
- Performance and scaling considerations
- Security and monitoring

**Perfect for:** System architects, senior developers, DevOps engineers

---

## 📖 API Reference

### [API Reference](event_listeners_api.md)
Complete reference for all classes, methods, and interfaces.

**Topics Covered:**
- Base classes and inheritance hierarchy
- Registration and discovery APIs
- Event processor methods
- Database models and queries
- Management commands
- Utility functions

**Perfect for:** Developers building custom listeners, integration developers

---

## 🚀 Production Deployment

### [Production Deployment Guide](event_listeners_production.md)
Everything you need for production deployment and operations.

**Topics Covered:**
- Production configuration and security
- Service management with systemd
- Monitoring, logging, and alerting
- Performance optimization
- Scaling strategies
- Backup and disaster recovery
- Maintenance procedures

**Perfect for:** DevOps engineers, system administrators, production deployments

---

## 💡 Examples & Use Cases

### Built-in Examples
Located in `zerver/event_listeners/examples.py`:
- **Message Logger**: Simple message logging
- **User Status Tracker**: User activity monitoring
- **Stream Activity Monitor**: Stream/channel activity tracking
- **AI Mentoring Demo**: AI mentoring system with pattern learning
- **Comprehensive Analytics**: Multi-event analytics system

### Real-World Use Cases
1. **AI/Bot Integration**: Intelligent chatbots and AI assistants
2. **Analytics & Metrics**: Real-time dashboard and reporting
3. **Content Moderation**: Automated content filtering and moderation
4. **Notifications**: Custom notification systems
5. **Integration**: Third-party system integration
6. **Audit & Compliance**: Activity logging and audit trails

---

## 🔧 Technical Reference

### File Structure
```
zerver/event_listeners/
├── __init__.py              # Plugin API exports
├── apps.py                  # Django app configuration  
├── models.py                # Database models
├── base.py                  # Base handler classes
├── registry.py              # Handler registration
├── processor.py             # Event processing engine
├── integration.py           # Zulip integration utilities
├── examples.py              # Example implementations
├── tests.py                 # Test suite
├── README.md                # Plugin overview
└── management/commands/
    ├── run_event_listeners.py    # Main daemon command
    └── list_event_listeners.py   # List/inspect command
```

### Configuration Files
- `zproject/dev_settings.py` - Development configuration
- `zproject/prod_settings_template.py` - Production template
- `zproject/computed_settings.py` - Logging configuration

### Database Tables
- `event_listeners_eventlistener` - Listener configurations
- `event_listeners_eventlog` - Event processing logs
- `event_listeners_listenerstats` - Performance statistics
- `event_listeners_listenerconfig` - Dynamic configuration

---

## 🎓 Learning Path

### For Beginners
1. **Start with [Quick Start Guide](event_listeners_quick_start.md)**
2. Try the demo mode: `./manage.py run_event_listeners --demo-mode`
3. Study the examples in `examples.py`
4. Create your first simple listener
5. Refer to [API Reference](event_listeners_api.md) as needed

### For Advanced Users
1. Review [Architecture Documentation](event_listeners_architecture.md)
2. Study the core components in detail
3. Build complex multi-event listeners
4. Implement custom integrations
5. Plan for production deployment

### For Operations Teams
1. Read [Production Deployment Guide](event_listeners_production.md)
2. Set up monitoring and logging
3. Configure service management
4. Plan scaling and backup strategies
5. Establish maintenance procedures

---

## 🛠️ Common Commands Reference

### Testing & Development
```bash
# Run migrations
./manage.py migrate event_listeners

# Test in demo mode
./manage.py run_event_listeners --demo-mode

# List available listeners
./manage.py list_event_listeners

# Show statistics and configuration
./manage.py list_event_listeners --show-stats --show-config

# Dry run (show configuration)
./manage.py run_event_listeners --demo-mode --dry-run
```

### Production Operations
```bash
# Run specific listeners
./manage.py run_event_listeners --listeners listener1,listener2

# Run with custom configuration
./manage.py run_event_listeners --config-file /path/to/zuliprc

# Service management
sudo systemctl start zulip-event-listeners
sudo systemctl status zulip-event-listeners
sudo journalctl -u zulip-event-listeners -f
```

---

## 🆘 Support & Troubleshooting

### Common Issues

#### Issue: "Registered 0 event listeners"
**Solution**: Ensure listeners are imported and decorated with `@register_event_listener`

#### Issue: "Zulip client configuration error"
**Solution**: Use `--demo-mode` for testing or configure `.zuliprc` file

#### Issue: Import errors or module not found
**Solution**: Check Django configuration and Python path

### Getting Help

1. **Check the troubleshooting sections** in each documentation file
2. **Review the examples** in `examples.py` for patterns
3. **Test in demo mode** to isolate issues
4. **Check logs** for detailed error information
5. **Review configuration** for missing or incorrect settings

### Debug Mode

```bash
# Enable debug logging
./manage.py run_event_listeners --demo-mode --verbosity 2

# Check Django shell for imports
./manage.py shell
>>> from zerver.event_listeners import MessageEventHandler
>>> from zerver.event_listeners.registry import event_listener_registry
>>> print(event_listener_registry.list_listeners())
```

---

## 🎉 Success Stories

The Event Listeners Plugin enables:

- **🤖 AI Integration**: Build sophisticated AI systems that learn from user interactions
- **📊 Analytics**: Real-time dashboards and comprehensive reporting
- **🛡️ Moderation**: Automated content filtering and community management
- **🔔 Notifications**: Custom notification systems for different user groups
- **🔗 Integration**: Seamless connection with external systems and APIs
- **📋 Compliance**: Audit trails and regulatory compliance features

---

## 📝 Contributing

The plugin is designed to be extensible and welcomes contributions:

1. **Bug Fixes**: Report and fix issues
2. **New Features**: Add new base classes or utilities
3. **Examples**: Share your custom listener implementations
4. **Documentation**: Improve guides and examples
5. **Testing**: Add test cases and improve coverage

Follow Django and Zulip coding standards when contributing.

---

## 📜 License

This plugin is part of the Zulip project and follows the same licensing terms.

---

**Ready to get started?** Begin with the [Quick Start Guide](event_listeners_quick_start.md) and start building amazing event-driven features for your Zulip instance! 🚀