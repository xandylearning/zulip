# Event Listeners Production Deployment Guide

## Pre-Deployment Testing

### 1. Run Development Test Suite
```bash
./test_event_listeners_dev.sh
```

This comprehensive test verifies:
- ✅ Django configuration
- ✅ Event listeners registration (5 listeners expected)
- ✅ Database migrations
- ✅ Demo mode functionality
- ✅ Web UI accessibility
- ✅ Performance under load

### 2. Manual Testing Checklist

#### Basic Functionality
- [ ] All 5 event listeners are registered
- [ ] Web UI loads at `/event-listeners/`
- [ ] Dashboard shows real-time metrics
- [ ] Live events monitor displays events
- [ ] Listener management works (enable/disable)
- [ ] Event logs are recorded properly

#### Performance Testing
- [ ] Average processing time < 100ms
- [ ] No memory leaks during extended operation
- [ ] Handles concurrent events properly
- [ ] Database queries are optimized

#### Error Handling
- [ ] Graceful handling of malformed events
- [ ] Proper error logging and alerting
- [ ] Automatic recovery from failures
- [ ] Circuit breaker functionality

## Production Deployment Steps

### 1. Environment Configuration

#### Settings Configuration
```python
# In production_settings.py
EVENT_LISTENERS_ENABLED = True
EXTRA_INSTALLED_APPS = ['zerver.event_listeners']

EVENT_LISTENERS_CONFIG = {
    'processor': {
        'batch_size': 50,           # Increased for production
        'timeout': 60.0,            # Longer timeout
        'max_retries': 3,
        'retry_delay': 5.0,
    },
    'monitoring': {
        'enable_web_ui': True,
        'admin_only': True,
        'log_level': 'INFO',        # Reduced logging in prod
    },
    'database': {
        'connection_pool_size': 10,
        'max_overflow': 20,
    }
}

# Logging configuration
LOGGING['loggers']['zerver.event_listeners'] = {
    'level': 'INFO',
    'handlers': ['file', 'console'],
    'propagate': False,
}
```

### 2. Database Setup
```bash
# 1. Create and run migrations
./manage.py makemigrations event_listeners
./manage.py migrate event_listeners

# 2. Initialize event listeners
./manage.py init_event_listeners

# 3. Verify setup
./manage.py list_event_listeners
```

### 3. Application Deployment

#### Docker Deployment
```dockerfile
# Add to your Dockerfile
COPY zerver/event_listeners /app/zerver/event_listeners/
RUN pip install -r requirements/prod.txt

# Set environment variables
ENV EVENT_LISTENERS_ENABLED=true
ENV DJANGO_SETTINGS_MODULE=zproject.prod_settings
```

#### Systemd Service (for non-Docker)
```ini
# /etc/systemd/system/zulip-event-listeners.service
[Unit]
Description=Zulip Event Listeners Service
After=network.target postgresql.service

[Service]
Type=simple
User=zulip
WorkingDirectory=/home/zulip/deployments/current
Environment=DJANGO_SETTINGS_MODULE=zproject.prod_settings
ExecStart=/home/zulip/deployments/current/manage.py run_event_listeners
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 4. Process Management

#### Start Event Listeners
```bash
# Option 1: Direct execution
./manage.py run_event_listeners

# Option 2: Systemd service
sudo systemctl enable zulip-event-listeners
sudo systemctl start zulip-event-listeners

# Option 3: Supervisor
supervisorctl start zulip-event-listeners
```

### 5. Monitoring Setup

#### Health Check Endpoint
Add to your load balancer health checks:
```bash
curl -f http://localhost:9991/event-listeners/api/stats/ || exit 1
```

#### Monitoring Commands
```bash
# Check listener status
./manage.py list_event_listeners

# Monitor logs
tail -f /var/log/zulip/event_listeners.log

# Check process status
systemctl status zulip-event-listeners
```

## Production Monitoring

### 1. Key Metrics to Monitor

#### Performance Metrics
- **Processing Time**: < 100ms average
- **Success Rate**: > 99%
- **Event Volume**: Monitor for spikes
- **Memory Usage**: Watch for leaks
- **CPU Usage**: Should be minimal

#### Health Indicators
- **Active Listeners**: All 5 should be enabled
- **Database Connections**: Monitor pool usage
- **Error Rate**: < 1% of total events
- **Queue Depth**: Monitor for backlog

### 2. Alerting Setup

#### Critical Alerts
```bash
# Event processing failure rate > 5%
# Average processing time > 500ms
# Any listener crashes or becomes unresponsive
# Database connection pool exhaustion
# Memory usage > 80% of available
```

#### Warning Alerts
```bash
# Event processing failure rate > 1%
# Average processing time > 200ms
# Queue depth > 1000 events
# Memory usage > 60% of available
```

### 3. Log Analysis

#### Important Log Patterns to Monitor
```bash
# Error patterns
grep "ERROR" /var/log/zulip/event_listeners.log

# Performance issues
grep "Processing time" /var/log/zulip/event_listeners.log | awk '{if($NF > 100) print}'

# Failed events
grep "Failed to process event" /var/log/zulip/event_listeners.log
```

## Troubleshooting

### Common Issues

#### 1. No Events Being Processed
```bash
# Check if service is running
systemctl status zulip-event-listeners

# Check listener registration
./manage.py list_event_listeners

# Verify configuration
./manage.py check_event_listeners_config
```

#### 2. High Memory Usage
```bash
# Monitor memory usage
ps aux | grep event_listeners

# Check for memory leaks
valgrind python manage.py run_event_listeners --demo-mode
```

#### 3. Database Issues
```bash
# Check database connections
./manage.py dbshell -c "SELECT * FROM pg_stat_activity WHERE application_name LIKE '%event_listeners%';"

# Check table sizes
./manage.py dbshell -c "SELECT schemaname,tablename,attname,n_distinct,correlation FROM pg_stats WHERE tablename LIKE 'event_%';"
```

### Performance Tuning

#### 1. Database Optimization
```sql
-- Add indexes for better performance
CREATE INDEX CONCURRENTLY idx_event_log_timestamp ON event_listeners_eventlog(timestamp);
CREATE INDEX CONCURRENTLY idx_event_log_listener_type ON event_listeners_eventlog(listener_name, event_type);
CREATE INDEX CONCURRENTLY idx_stats_updated ON event_listeners_listenerstats(updated_at);
```

#### 2. Application Tuning
```python
# Increase batch size for high-volume environments
EVENT_LISTENERS_CONFIG['processor']['batch_size'] = 100

# Adjust worker threads
EVENT_LISTENERS_CONFIG['processor']['worker_threads'] = 8

# Enable event batching
EVENT_LISTENERS_CONFIG['processor']['enable_batching'] = True
```

## Rollback Plan

### 1. Quick Disable
```bash
# Disable event listeners without code changes
./manage.py shell -c "
from zerver.event_listeners.models import EventListener
EventListener.objects.update(is_enabled=False)
"
```

### 2. Service Rollback
```bash
# Stop the service
systemctl stop zulip-event-listeners

# Disable from Django settings
# Set EVENT_LISTENERS_ENABLED = False

# Restart main application
systemctl restart zulip
```

### 3. Database Rollback (if needed)
```bash
# Remove tables (only if absolutely necessary)
./manage.py migrate event_listeners zero
```

## Success Criteria

### Pre-Production
- [ ] All tests pass
- [ ] Performance meets requirements
- [ ] Error handling works correctly
- [ ] Monitoring setup is complete

### Post-Production
- [ ] All 5 listeners are active
- [ ] Events are being processed successfully
- [ ] Web UI is accessible to admin users
- [ ] No performance degradation to main application
- [ ] Monitoring alerts are working

## Support

### Documentation Links
- [Web UI Guide](docs/documentation/event-listener/event_listeners_web_ui.md)
- [Architecture Guide](docs/documentation/event-listener/event_listeners_architecture.md)
- [API Reference](docs/documentation/event-listener/event_listeners_api.md)

### Emergency Contacts
- Development Team: [contact details]
- Operations Team: [contact details]
- On-call Engineer: [contact details]