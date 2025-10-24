# LMS Database Credentials Setup Guide

This guide explains how to configure LMS database credentials for both development and production environments in Zulip.

## Overview

The LMS integration in Zulip allows connecting to an external Learning Management System (LMS) database to read user and course data. The integration uses Django's database routing system to direct LMS model queries to a separate database connection.

## Architecture

- **Database Router**: Routes LMS model queries to the `lms_db` database
- **Read-Only Access**: LMS database is configured as read-only for security
- **External Models**: LMS models are external and don't require migrations
- **Configuration**: Uses Zulip's standard configuration system

## Development Environment Setup

### 1. Update Development Secrets

Add the LMS database password to your development secrets file:

**File**: `zproject/dev-secrets.conf`

```ini
[secrets]
# ... existing secrets ...

# LMS Database Credentials
lms_database_password = your_lms_database_password_here
```

### 2. Configure LMS Database Settings

The LMS database configuration is already set up in `zproject/computed_settings.py`. The configuration uses:

- **Database Name**: `lms_production` (default) or configured via `lms_database.database_name`
- **User**: `lms_readonly` (default) or configured via `lms_database.database_user`
- **Host**: `localhost` (default) or configured via `lms_database.host`
- **Port**: `5432` (default) or configured via `lms_database.port`
- **Password**: Retrieved from `lms_database_password` secret

### 3. Optional: Customize Database Settings

If you need to override the default LMS database settings, create a configuration file:

**File**: `/etc/zulip/zulip.conf` (development)

```ini
[lms_database]
database_name = your_lms_database_name
database_user = your_lms_database_user
host = your_lms_database_host
port = 5432
```

### 4. Test the Connection

Verify the LMS database connection works:

```bash
# Test database connection
./manage.py dbshell --database=lms_db

# Test LMS models (if they exist)
./manage.py shell
>>> from lms_integration.models import *
>>> # Test your LMS models here
```

## Production Environment Setup

### 1. Update Production Secrets

Add the LMS database password to your production secrets file:

**File**: `/etc/zulip/zulip-secrets.conf`

```ini
[secrets]
# ... existing secrets ...

# LMS Database Credentials
lms_database_password = your_secure_lms_database_password_here
```

### 2. Configure LMS Database Settings

Create or update the production configuration:

**File**: `/etc/zulip/zulip.conf`

```ini
[lms_database]
database_name = lms_production
database_user = lms_readonly
host = lms-db.example.com
port = 5432
```

### 3. Security Considerations

For production environments, consider these security measures:

- **Read-Only User**: Use a database user with only SELECT permissions
- **Network Security**: Ensure proper firewall rules and network isolation
- **SSL/TLS**: Configure SSL connections if the LMS database is remote
- **Password Security**: Use strong, unique passwords stored securely

### 4. SSL Configuration (Optional)

If your LMS database requires SSL, you can configure it in the database options:

**File**: `/etc/zulip/settings.py` (production)

```python
# Add to your production settings.py
DATABASES['lms_db']['OPTIONS']['sslmode'] = 'require'
# or for more specific SSL configuration:
# DATABASES['lms_db']['OPTIONS']['sslmode'] = 'verify-full'
```

## Configuration Reference

### Database Configuration Structure

The LMS database is configured in `zproject/computed_settings.py`:

```python
"lms_db": {
    "ENGINE": "django.db.backends.postgresql",
    "NAME": get_config("lms_database", "database_name", "lms_production"),
    "USER": get_config("lms_database", "database_user", "lms_readonly"),
    "PASSWORD": get_secret("lms_database_password"),
    "HOST": get_config("lms_database", "host", "localhost"),
    "PORT": get_config("lms_database", "port", "5432"),
    "OPTIONS": {
        "connect_timeout": 2,
    },
}
```

### Configuration Sources

1. **Secrets**: Retrieved from `lms_database_password` in secrets file
2. **Settings**: Retrieved from `[lms_database]` section in `zulip.conf`
3. **Defaults**: Fallback values if not configured

### Database Router

The LMS database router (`lms_integration.db_router.LMSRouter`) handles:

- **Read Operations**: Routes LMS model queries to `lms_db`
- **Write Operations**: Blocks write operations (read-only access)
- **Migrations**: Prevents migrations for external LMS models
- **Relations**: Manages relationships between models

## Troubleshooting

### Common Issues

#### 1. Connection Refused

**Error**: `django.db.utils.OperationalError: could not connect to server`

**Solutions**:
- Verify the LMS database host and port
- Check network connectivity
- Ensure the database server is running
- Verify firewall rules

#### 2. Authentication Failed

**Error**: `django.db.utils.OperationalError: password authentication failed`

**Solutions**:
- Verify the password in secrets file
- Check database user permissions
- Ensure the user exists in the LMS database

#### 3. Database Not Found

**Error**: `django.db.utils.OperationalError: database "lms_production" does not exist`

**Solutions**:
- Verify the database name in configuration
- Check if the database exists on the server
- Create the database if needed

#### 4. Permission Denied

**Error**: `django.db.utils.OperationalError: permission denied for table`

**Solutions**:
- Ensure the database user has SELECT permissions
- Check table-level permissions
- Verify the user can access the required tables

### Debug Commands

```bash
# Test database connection
./manage.py dbshell --database=lms_db

# Check database configuration
./manage.py shell
>>> from django.conf import settings
>>> print(settings.DATABASES['lms_db'])

# Test specific model access
./manage.py shell
>>> from lms_integration.models import *
>>> # Test your models here
```

### Logging

Enable database query logging for debugging:

```python
# Add to your settings.py for debugging
LOGGING['loggers']['django.db.backends'] = {
    'level': 'DEBUG',
    'handlers': ['console'],
    'propagate': False,
}
```

## Security Best Practices

### 1. Database User Permissions

Create a read-only user for LMS database access:

```sql
-- Create read-only user
CREATE USER lms_readonly WITH PASSWORD 'secure_password';

-- Grant SELECT permissions on required tables
GRANT SELECT ON ALL TABLES IN SCHEMA public TO lms_readonly;

-- Grant usage on schema
GRANT USAGE ON SCHEMA public TO lms_readonly;
```

### 2. Network Security

- Use VPN or private networks for database connections
- Implement firewall rules to restrict access
- Use SSL/TLS for encrypted connections
- Consider database connection pooling

### 3. Password Management

- Use strong, unique passwords
- Rotate passwords regularly
- Store passwords securely (not in code)
- Use environment variables or secure secret management

### 4. Monitoring

- Monitor database connection health
- Set up alerts for connection failures
- Log database access for auditing
- Monitor query performance

## Example Configurations

### Development Configuration

**File**: `zproject/dev-secrets.conf`

```ini
[secrets]
lms_database_password = dev_lms_password_123
```

**File**: `/etc/zulip/zulip.conf` (optional)

```ini
[lms_database]
database_name = lms_dev
database_user = lms_readonly
host = localhost
port = 5432
```

### Production Configuration

**File**: `/etc/zulip/zulip-secrets.conf`

```ini
[secrets]
lms_database_password = ProdLms2024!SecurePass
```

**File**: `/etc/zulip/zulip.conf`

```ini
[lms_database]
database_name = lms_production
database_user = lms_readonly
host = lms-db.internal.company.com
port = 5432
```

### SSL Configuration

**File**: `/etc/zulip/settings.py`

```python
# Add SSL configuration for LMS database
DATABASES['lms_db']['OPTIONS'].update({
    'sslmode': 'require',
    'sslcert': '/etc/zulip/ssl/lms-client.crt',
    'sslkey': '/etc/zulip/ssl/lms-client.key',
    'sslrootcert': '/etc/zulip/ssl/lms-ca.crt',
})
```

## Maintenance

### Regular Tasks

1. **Password Rotation**: Update passwords regularly
2. **Connection Testing**: Verify connections are working
3. **Performance Monitoring**: Monitor query performance
4. **Security Audits**: Review access permissions

### Backup Considerations

- LMS database backups are handled by the LMS system
- Zulip only reads from the LMS database
- No Zulip-specific backup procedures needed for LMS data

## Support

For issues with LMS database integration:

1. Check the troubleshooting section above
2. Review Zulip logs for error messages
3. Test database connectivity manually
4. Verify configuration settings
5. Contact your system administrator for database access issues

## Related Documentation

- [Zulip Settings Documentation](https://zulip.readthedocs.io/en/latest/subsystems/settings.html)
- [Django Database Configuration](https://docs.djangoproject.com/en/stable/ref/settings/#databases)
- [PostgreSQL Connection Parameters](https://www.postgresql.org/docs/current/libpq-connect.html)
