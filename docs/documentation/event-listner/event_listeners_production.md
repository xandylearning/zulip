# Event Listeners Plugin - Production Deployment Guide

## 🎯 Production Setup Checklist

### ✅ Pre-Deployment

- [ ] Review and test all custom event listeners
- [ ] Configure production settings
- [ ] Set up monitoring and logging
- [ ] Plan resource allocation
- [ ] Prepare rollback strategy

### ✅ Deployment Steps

- [ ] Update production settings
- [ ] Run database migrations
- [ ] Configure service management
- [ ] Set up log rotation
- [ ] Deploy monitoring
- [ ] Test functionality

### ✅ Post-Deployment

- [ ] Verify listeners are running
- [ ] Monitor performance metrics
- [ ] Check error rates
- [ ] Validate log output
- [ ] Set up alerts

## ⚙️ Production Configuration

### 1. Settings Configuration

Add to your production settings file (`/etc/zulip/settings.py`):

```python
# Enable event listeners plugin
EVENT_LISTENERS_ENABLED = True

# Add to installed apps
EXTRA_INSTALLED_APPS = getattr(globals(), 'EXTRA_INSTALLED_APPS', []) + ['zerver.event_listeners']

# Production configuration
EVENT_LISTENERS_CONFIG = {
    # Conservative listener set for production
    'DEFAULT_LISTENERS': [
        'message_logger',
        'user_activity_tracker',
        # Add your production listeners here
    ],
    
    # Performance settings
    'PERFORMANCE': {
        'max_concurrent_handlers': 5,      # Conservative for stability
        'handler_timeout': 30,             # 30 second timeout
        'memory_threshold': 100 * 1024 * 1024,  # 100MB memory limit
    },
    
    # Logging configuration
    'LOGGING': {
        'level': 'WARNING',                # Less verbose in production
        'file': '/var/log/zulip/event_listeners.log',
    },
    
    # Queue settings
    'QUEUE_CONFIG': {
        'max_retries': 3,
        'retry_delay': 5,
        'batch_size': 50,                  # Smaller batches for stability
        'timeout': 30,
    },
    
    # Statistics retention
    'STATISTICS': {
        'enabled': True,
        'retention_days': 7,               # Shorter retention in production
        'aggregation_interval': 300,       # 5 minute intervals
    },
    
    # Event filtering
    'FILTERS': {
        'max_event_age': 3600,             # Ignore events older than 1 hour
        'default_realm_filter': None,      # Configure if needed
    },
    
    # Error handling
    'ERROR_HANDLING': {
        'max_failures_per_hour': 50,
        'auto_disable_threshold': 20,
        'notification_webhook': 'https://your-monitoring.com/webhook',
    },
}
```

### 2. Database Migration

```bash
# Run as zulip user
sudo -u zulip /home/zulip/deployments/current/manage.py migrate event_listeners
```

### 3. Verify Configuration

```bash
# Test configuration
sudo -u zulip /home/zulip/deployments/current/manage.py list_event_listeners

# Test in dry-run mode
sudo -u zulip /home/zulip/deployments/current/manage.py run_event_listeners --dry-run
```

## 🚀 Service Management

### 1. Systemd Service

Create `/etc/systemd/system/zulip-event-listeners.service`:

```ini
[Unit]
Description=Zulip Event Listeners
After=network.target zulip.service
Requires=zulip.service
PartOf=zulip.service

[Service]
Type=simple
User=zulip
Group=zulip
WorkingDirectory=/home/zulip/deployments/current

# Environment
Environment="DJANGO_SETTINGS_MODULE=zproject.settings"
Environment="PYTHONPATH=/home/zulip/deployments/current"

# Command
ExecStart=/home/zulip/deployments/current/manage.py run_event_listeners

# Restart policy
Restart=always
RestartSec=10
StartLimitInterval=60
StartLimitBurst=3

# Resource limits
LimitNOFILE=65536
LimitNPROC=32768

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=zulip-event-listeners

# Security
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

### 2. Service Commands

```bash
# Install and start service
sudo systemctl daemon-reload
sudo systemctl enable zulip-event-listeners
sudo systemctl start zulip-event-listeners

# Check status
sudo systemctl status zulip-event-listeners

# View logs
sudo journalctl -u zulip-event-listeners -f

# Restart service
sudo systemctl restart zulip-event-listeners
```

### 3. Integration with Zulip Service

Add to Zulip's main service configuration to ensure event listeners start/stop with Zulip:

```bash
# Edit /etc/systemd/system/zulip.service
[Unit]
Wants=zulip-event-listeners.service

[Service]
ExecStartPost=/bin/systemctl start zulip-event-listeners.service
ExecStopPost=/bin/systemctl stop zulip-event-listeners.service
```

## 📊 Monitoring & Logging

### 1. Log Configuration

Configure log rotation in `/etc/logrotate.d/zulip-event-listeners`:

```
/var/log/zulip/event_listeners.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    copytruncate
    postrotate
        systemctl reload zulip-event-listeners
    endscript
}
```

### 2. Monitoring Metrics

Key metrics to monitor:

#### Application Metrics
- Events processed per minute
- Handler success/failure rates
- Average processing time
- Queue depth and lag
- Memory and CPU usage

#### System Metrics
- Service uptime
- Log error rates
- Database query performance
- Network connectivity

#### Business Metrics
- Feature-specific metrics (e.g., AI responses sent)
- User engagement metrics
- Error patterns and trends

### 3. Monitoring Setup

#### Using Prometheus + Grafana

Create metrics endpoint in your listener:

```python
@register_event_listener
class MetricsExporter(BaseEventHandler):
    name = "metrics_exporter"
    description = "Exports metrics for monitoring"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.metrics = {
            'events_total': 0,
            'events_success': 0,
            'events_failed': 0,
            'processing_time_total': 0.0,
        }
    
    def handle_event(self, event):
        # Update metrics
        self.metrics['events_total'] += 1
        # Export to monitoring system
        return True
```

#### Health Check Endpoint

```python
# Add to your Django urls.py
def event_listeners_health(request):
    stats = event_processor.get_stats()
    health = {
        'status': 'healthy' if stats['active_handlers'] > 0 else 'degraded',
        'active_handlers': stats['active_handlers'],
        'last_event_time': stats.get('last_event_time'),
        'error_rate': stats.get('error_rate', 0),
    }
    return JsonResponse(health)
```

## 🔧 Performance Optimization

### 1. Resource Tuning

#### Memory Optimization
```python
EVENT_LISTENERS_CONFIG = {
    'PERFORMANCE': {
        'memory_threshold': 200 * 1024 * 1024,  # 200MB
        'gc_interval': 100,                      # Garbage collect every 100 events
        'instance_cache_size': 50,               # Limit handler instance cache
    }
}
```

#### CPU Optimization
```python
EVENT_LISTENERS_CONFIG = {
    'PERFORMANCE': {
        'max_concurrent_handlers': min(4, cpu_count()),
        'worker_processes': 2,
        'async_processing': True,
    }
}
```

### 2. Database Optimization

#### Index Creation
```sql
-- Performance indexes for production
CREATE INDEX CONCURRENTLY idx_event_log_timestamp ON event_listeners_eventlog (timestamp);
CREATE INDEX CONCURRENTLY idx_event_log_listener_success ON event_listeners_eventlog (listener_name, success);
CREATE INDEX CONCURRENTLY idx_listener_stats_name ON event_listeners_listenerstats (listener_name);
```

#### Data Retention
```python
# Add to cron jobs
0 2 * * * /home/zulip/deployments/current/manage.py cleanup_event_logs --days 7
```

### 3. Network Optimization

#### Connection Pooling
```python
EVENT_LISTENERS_CONFIG = {
    'NETWORK': {
        'connection_pool_size': 10,
        'connection_timeout': 30,
        'read_timeout': 60,
        'max_retries': 3,
    }
}
```

## 🔒 Security Configuration

### 1. Access Control

```python
EVENT_LISTENERS_CONFIG = {
    'SECURITY': {
        'allowed_realms': [1, 2, 3],           # Restrict to specific realms
        'blocked_users': [],                    # Block specific users
        'rate_limit_per_user': 100,            # Events per minute per user
        'require_authentication': True,
    }
}
```

### 2. Data Protection

```python
EVENT_LISTENERS_CONFIG = {
    'DATA_PROTECTION': {
        'log_sanitization': True,              # Remove PII from logs
        'max_content_length': 1000,            # Limit logged content
        'encrypt_sensitive_data': True,
        'audit_trail': True,
    }
}
```

### 3. Secure Configuration

- Store API keys in environment variables
- Use secure file permissions (600) for config files
- Enable SSL/TLS for all network connections
- Regular security updates and patches

## 🚨 Error Handling & Recovery

### 1. Circuit Breaker

```python
@register_event_listener
class RobustHandler(MessageEventHandler):
    name = "robust_handler"
    
    def __init__(self, config=None):
        super().__init__(config)
        self.failure_count = 0
        self.circuit_open = False
        self.last_failure_time = 0
    
    def handle_message(self, event):
        if self.circuit_open:
            if time.time() - self.last_failure_time > 300:  # 5 min cooldown
                self.circuit_open = False
                self.failure_count = 0
            else:
                return True  # Skip processing while circuit is open
        
        try:
            # Your processing logic
            result = self.process_message(event)
            self.failure_count = 0  # Reset on success
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= 5:
                self.circuit_open = True
                logger.error(f"Circuit breaker opened for {self.name}")
            
            raise
```

### 2. Graceful Degradation

```python
@register_event_listener
class FallbackHandler(MessageEventHandler):
    name = "fallback_handler"
    
    def handle_message(self, event):
        try:
            return self.primary_processing(event)
        except Exception as e:
            logger.warning(f"Primary processing failed: {e}")
            return self.fallback_processing(event)
    
    def primary_processing(self, event):
        # Main logic
        pass
    
    def fallback_processing(self, event):
        # Simplified fallback logic
        pass
```

## 📈 Scaling Strategies

### 1. Horizontal Scaling

#### Multiple Instances
```bash
# Run multiple listener processes
./manage.py run_event_listeners --listeners batch1 &
./manage.py run_event_listeners --listeners batch2 &
./manage.py run_event_listeners --listeners batch3 &
```

#### Load Balancing
```python
EVENT_LISTENERS_CONFIG = {
    'SCALING': {
        'instance_id': os.getenv('INSTANCE_ID', '1'),
        'total_instances': int(os.getenv('TOTAL_INSTANCES', '1')),
        'partition_strategy': 'hash',  # or 'round_robin'
    }
}
```

### 2. Vertical Scaling

#### Resource Allocation
```ini
# In systemd service file
[Service]
LimitCPU=80%
LimitMEMLOCK=1G
LimitNOFILE=10000
```

### 3. Queue-Based Architecture

For high-volume deployments, consider using message queues:

```python
# Use Celery for async processing
@celery_app.task
def process_event_async(event_data, listener_name):
    handler = event_listener_registry.get_handler_instance(listener_name)
    return handler.handle_event(event_data)
```

## 🛡️ Backup & Recovery

### 1. Configuration Backup

```bash
#!/bin/bash
# backup_event_listeners.sh
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="/var/backups/zulip-event-listeners"

# Backup database
pg_dump -U zulip -t 'event_listeners_*' zulip > "$BACKUP_DIR/db_$DATE.sql"

# Backup configuration
cp -r /etc/zulip/event_listeners/ "$BACKUP_DIR/config_$DATE/"

# Backup logs (last 7 days)
find /var/log/zulip/event_listeners* -mtime -7 -exec cp {} "$BACKUP_DIR/logs_$DATE/" \;
```

### 2. Disaster Recovery

#### Recovery Plan
1. Stop event listener service
2. Restore database from backup
3. Restore configuration files
4. Restart services
5. Verify functionality
6. Monitor for issues

#### Testing Recovery
```bash
# Test recovery procedure monthly
./test_recovery.sh
```

## 📋 Maintenance Tasks

### 1. Regular Maintenance

#### Daily Tasks
- Monitor service health
- Check error rates
- Review log alerts

#### Weekly Tasks
- Review performance metrics
- Clean up old logs
- Update statistics

#### Monthly Tasks
- Performance tuning review
- Security updates
- Backup testing

### 2. Automated Maintenance

```bash
# Cron jobs for maintenance
# Daily log cleanup
0 2 * * * /home/zulip/deployments/current/manage.py cleanup_event_logs --days 7

# Weekly stats aggregation
0 1 * * 0 /home/zulip/deployments/current/manage.py aggregate_listener_stats

# Monthly health check
0 3 1 * * /home/zulip/deployments/current/scripts/health_check.sh
```

This production guide ensures your Event Listeners Plugin runs reliably and efficiently in production environments with proper monitoring, security, and maintenance procedures.