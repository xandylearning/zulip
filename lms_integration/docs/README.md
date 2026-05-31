# LMS Integration Documentation

Welcome to the comprehensive documentation for the LMS Activity Event Listener and Notification System.

## Documentation Overview

This documentation provides complete information about the LMS integration system, including installation, configuration, API reference, troubleshooting, and more.

## Table of Contents

### 📚 **Getting Started**
- **[README.md](../README.md)** - Main documentation with overview, features, and usage
- **[INSTALLATION.md](INSTALLATION.md)** - Step-by-step installation guide
- **[CHANGELOG.md](../CHANGELOG.md)** - Version history and changes

### 🔧 **Technical Documentation**
- **[API.md](API.md)** - Complete API reference for all components
- **[JWT_AUTHENTICATION.md](JWT_AUTHENTICATION.md)** - JWT auth flow, endpoints, and configuration
- **[SIMPLIFIED_AUTH_BACKEND.md](SIMPLIFIED_AUTH_BACKEND.md)** - Auth backend internals & concurrency/transaction safety
- **[USER_SYNC.md](USER_SYNC.md)** - Bulk user synchronization
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Comprehensive troubleshooting guide
- **[PLAY_STORE_DEMO_ACCOUNT_FILTERING.md](PLAY_STORE_DEMO_ACCOUNT_FILTERING.md)** - Demo account user-list restriction notes

### 🚨 **Incident Reports**
- **[POSTMORTEM_2026-05-12_jwt_user_creation_race.md](POSTMORTEM_2026-05-12_jwt_user_creation_race.md)** - Concurrent first-time JWT login race (fixed in v1.0.1)

### 🚀 **Quick Start**

1. **Installation**: Follow the [Installation Guide](INSTALLATION.md)
2. **Configuration**: Set up database access and monitoring settings
3. **Testing**: Run tests to verify everything works
4. **Deployment**: Deploy to production with monitoring

### 📖 **Documentation Structure**

```
docs/
├── README.md                                          # This file - documentation index
├── INSTALLATION.md                                    # Installation and setup guide
├── API.md                                             # Complete API reference
├── JWT_AUTHENTICATION.md                              # JWT auth flow & configuration
├── SIMPLIFIED_AUTH_BACKEND.md                         # Auth backend internals & concurrency safety
├── USER_SYNC.md                                       # Bulk user synchronization
├── TROUBLESHOOTING.md                                 # Troubleshooting guide
└── POSTMORTEM_2026-05-12_jwt_user_creation_race.md    # Incident report

../
├── README.md              # Main documentation
├── CHANGELOG.md           # Version history
└── [source code files]    # Implementation files
```

## Key Features

### 🎯 **Core Functionality**
- **Real-time Activity Monitoring**: Polls LMS database for new student activities
- **Smart Event Detection**: Automatically classifies events based on activity state
- **Rich Notifications**: Formatted messages with emojis, scores, and contextual information
- **Mentor Mapping**: Automatically finds and notifies assigned mentors
- **AI-Ready Data**: Events stored with metadata for future AI analysis

### 🏗️ **Architecture**
- **Database Separation**: External LMS database (read-only) + Zulip database (event storage)
- **Event Processing Pipeline**: Complete event lifecycle management
- **Notification System**: Zulip DM integration with rich formatting
- **Management Interface**: Comprehensive command-line interface

### 🔧 **Technical Features**
- **Production Ready**: Daemon mode, graceful shutdown, error handling
- **Performance Optimized**: Database indexes, caching, batch processing
- **Security**: Read-only LMS access, data privacy, authentication
- **Monitoring**: Statistics, logging, health checks

## Documentation by Use Case

### 🚀 **For Administrators**
- **[Installation Guide](INSTALLATION.md)** - Set up the system
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Resolve issues
- **[Main README](../README.md)** - Understand the system

### 👨‍💻 **For Developers**
- **[API Documentation](API.md)** - Complete API reference
- **[Main README](../README.md)** - System overview and architecture
- **[CHANGELOG](../CHANGELOG.md)** - Version history and changes

### 🔧 **For Operations**
- **[Installation Guide](INSTALLATION.md)** - Production deployment
- **[Troubleshooting Guide](TROUBLESHOOTING.md)** - Monitor and maintain
- **[Main README](../README.md)** - Configuration and usage

## Quick Reference

### 📋 **Common Commands**

```bash
# Check system status
python manage.py monitor_lms_activities --stats

# Run once to test
python manage.py monitor_lms_activities --once --verbose

# Start daemon mode
python manage.py monitor_lms_activities --daemon

# Process pending events
python manage.py monitor_lms_activities --process-pending
```

### ⚙️ **Key Settings**

```python
# Enable monitoring
LMS_ACTIVITY_MONITOR_ENABLED = True

# Configure polling
LMS_ACTIVITY_POLL_INTERVAL = 60

# Enable notifications
LMS_NOTIFY_MENTORS_ENABLED = True
```

### 🗄️ **Database Models**

- **LMSActivityEvent**: Core event storage
- **LMSEventLog**: Event processing audit trail

### 📊 **Event Types**

- **Exam Events**: exam_started, exam_completed, exam_passed, exam_failed
- **Content Events**: content_started, content_completed, content_watched

## Getting Help

### 🆘 **Support Resources**

1. **Documentation**: Check the relevant documentation section
2. **Troubleshooting**: Use the [Troubleshooting Guide](TROUBLESHOOTING.md)
3. **API Reference**: Consult the [API Documentation](API.md)
4. **Logs**: Review system logs for error messages
5. **Community**: Reach out to the Zulip community

### 🔍 **Common Issues**

- **Database Connection**: Check LMS database connectivity
- **No Events**: Verify monitoring is enabled and LMS database is accessible
- **No Notifications**: Check mentor-student relationships and Zulip user mapping
- **Performance**: Review polling intervals and database indexes

### 📞 **Contact Information**

For additional support:
- **Documentation**: This comprehensive documentation
- **Logs**: System logs in `/var/log/zulip/`
- **Community**: Zulip community forums
- **Development Team**: Contact the development team

## Contributing

### 📝 **Documentation Updates**

If you find issues with the documentation or want to contribute:

1. **Report Issues**: Create an issue for documentation problems
2. **Suggest Improvements**: Propose documentation enhancements
3. **Submit Changes**: Submit pull requests for documentation updates

### 🔧 **Code Contributions**

For code contributions:

1. **Follow Guidelines**: Follow the existing code style and patterns
2. **Add Tests**: Include tests for new functionality
3. **Update Documentation**: Update relevant documentation
4. **Submit PRs**: Submit pull requests for code changes

## Version Information

- **Current Version**: 1.0.1
- **Release Date**: 2026-05-31
- **Compatibility**: Zulip 8.0+, Python 3.8+, PostgreSQL 12+

## License

This system is part of the Zulip LMS integration and follows the same license terms as Zulip.

---

## Navigation

- **[← Back to Main README](../README.md)**
- **[Installation Guide →](INSTALLATION.md)**
- **[API Documentation →](API.md)**
- **[Troubleshooting Guide →](TROUBLESHOOTING.md)**
- **[Play Store Demo Filter Notes →](PLAY_STORE_DEMO_ACCOUNT_FILTERING.md)**
- **[Changelog →](../CHANGELOG.md)**

