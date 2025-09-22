# SaaS database strategies: Single vs. Multi-database architectures

This document explains different database strategies for SaaS applications, with a focus on how Zulip implements single-database multi-tenancy and when you might choose different approaches.

## Overview

The question "Does a new database get created for each customer?" is fundamental to SaaS architecture. There are three main approaches:

1. **Single Database, Shared Schema** (Zulip's approach)
2. **Single Database, Separate Schemas**
3. **Separate Databases per Tenant**

Each has distinct trade-offs in terms of isolation, performance, cost, and operational complexity.

## Zulip's approach: Single database, shared schema

**Answer: No, Zulip does NOT create a new database for each customer.**

Zulip uses a **single PostgreSQL database** with **shared schema** where tenant isolation is achieved through the `realm` foreign key in every table.

### How it works

```python
# All tenants share the same database and tables
# zproject/computed_settings.py
DATABASES: dict[str, dict[str, Any]] = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "zulip",  # Single database for all tenants
        "USER": "zulip",
        "SCHEMA": "zulip",  # Single schema
    }
}

# Tenant isolation through application-level filtering
class UserProfile(models.Model):
    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)  # Tenant isolation
    email = models.EmailField()
    # ... other fields

class Message(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # Tenant isolation
    content = models.TextField()
    # ... other fields

# All queries are automatically scoped by realm
def get_users_in_organization(realm: Realm):
    return UserProfile.objects.filter(realm=realm)  # Only this tenant's users
```

### Database schema example

```sql
-- Single database: zulip
-- Single schema with realm-scoped tables

CREATE TABLE zerver_realm (
    id SERIAL PRIMARY KEY,
    string_id VARCHAR(40) UNIQUE,  -- acme-corp, university, etc.
    name VARCHAR(40),
    date_created TIMESTAMP
);

CREATE TABLE zerver_userprofile (
    id SERIAL PRIMARY KEY,
    realm_id INTEGER REFERENCES zerver_realm(id),  -- Tenant isolation
    email VARCHAR(254),
    full_name VARCHAR(100)
);

CREATE TABLE zerver_message (
    id SERIAL PRIMARY KEY,
    realm_id INTEGER REFERENCES zerver_realm(id),  -- Tenant isolation
    content TEXT,
    date_sent TIMESTAMP
);

-- Compound indexes for efficient tenant-scoped queries
CREATE INDEX zerver_userprofile_realm_email_idx ON zerver_userprofile(realm_id, email);
CREATE INDEX zerver_message_realm_date_idx ON zerver_message(realm_id, date_sent);
```

### When a new customer signs up

```python
# What happens when acme-corp.zulipchat.com is created
def create_new_organization(subdomain: str, name: str, admin_email: str):
    # 1. Create realm record in existing database
    realm = Realm.objects.create(
        string_id=subdomain,  # "acme-corp"
        name=name,           # "Acme Corporation"
    )

    # 2. Create admin user in same database, linked to realm
    admin_user = UserProfile.objects.create(
        realm=realm,         # Links to the specific tenant
        email=admin_email,
        role=UserProfile.ROLE_REALM_OWNER
    )

    # 3. Create default streams for the organization
    Stream.objects.create(
        realm=realm,         # Tenant-scoped
        name="general",
        description="Default stream"
    )

    # NO new database created - everything goes in existing tables
    # with realm_id for isolation
```

## Alternative database strategies

### Strategy 1: Separate databases per tenant

**Each customer gets their own database.**

```python
# Example: customer-specific databases
DATABASES = {
    'tenant_acme': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tenant_acme_db',
    },
    'tenant_university': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tenant_university_db',
    },
    # ... one database per tenant
}

# Dynamic database routing
class TenantRouter:
    def db_for_read(self, model, **hints):
        tenant = get_current_tenant()
        return f'tenant_{tenant.slug}'

    def db_for_write(self, model, **hints):
        tenant = get_current_tenant()
        return f'tenant_{tenant.slug}'
```

**Pros:**
- **Perfect isolation**: Impossible to access other tenant's data
- **Independent scaling**: Each tenant can have different database specs
- **Compliance**: Easier to meet data residency requirements
- **Backup/restore**: Can backup/restore individual tenants

**Cons:**
- **Operational complexity**: Managing hundreds/thousands of databases
- **Schema migrations**: Must run on every tenant database
- **Cross-tenant analytics**: Nearly impossible
- **Resource overhead**: Each DB has fixed overhead costs
- **Connection pooling**: Complex connection management

### Strategy 2: Single database, separate schemas

**All tenants in one database, but each gets their own schema.**

```sql
-- Single database with multiple schemas
CREATE DATABASE saas_app;

-- Schema per tenant
CREATE SCHEMA tenant_acme;
CREATE SCHEMA tenant_university;

-- Tables replicated in each schema
CREATE TABLE tenant_acme.users (...);
CREATE TABLE tenant_acme.messages (...);

CREATE TABLE tenant_university.users (...);
CREATE TABLE tenant_university.messages (...);
```

```python
# Django implementation
class TenantRouter:
    def db_for_read(self, model, **hints):
        return 'default'  # Same database

    def get_schema(self, tenant):
        return f'tenant_{tenant.slug}'

# Schema-aware queries
def get_users():
    tenant = get_current_tenant()
    schema = f'tenant_{tenant.slug}'
    return User.objects.extra(
        tables=[f'{schema}.users']
    )
```

**Pros:**
- **Good isolation**: Schema-level separation
- **Simpler operations**: Single database to manage
- **Easier migrations**: Can still be complex but manageable
- **Resource efficiency**: Shared database overhead

**Cons:**
- **PostgreSQL-specific**: Not all databases support schemas well
- **Migration complexity**: Must create schema for each tenant
- **Application complexity**: Need schema-aware ORM
- **Limited cross-tenant queries**: Still difficult

## Detailed comparison

| Aspect | Single DB/Schema (Zulip) | Single DB/Multi-Schema | Multi-Database |
|--------|---------------------------|-------------------------|----------------|
| **Data Isolation** | Application-level | Database schema-level | Database-level |
| **Setup Complexity** | Low | Medium | High |
| **Operational Overhead** | Low | Medium | Very High |
| **Cross-tenant Analytics** | Easy | Possible | Very Hard |
| **Schema Migrations** | Simple | Complex | Very Complex |
| **Scaling Individual Tenants** | Hard | Medium | Easy |
| **Resource Efficiency** | High | Medium | Low |
| **Security Risk** | Medium | Low | Very Low |
| **Backup/Restore Granularity** | All-or-nothing | Schema-level | Tenant-level |

## When to choose each strategy

### Choose Single Database/Shared Schema (like Zulip) when:

- **Many small to medium tenants** (hundreds to thousands)
- **Similar usage patterns** across tenants
- **Cost efficiency** is important
- **Cross-tenant analytics** needed
- **Simple operations** preferred
- **Rapid tenant provisioning** required

**Examples**: Chat platforms (Zulip, Slack), project management tools, CRM systems

### Choose Single Database/Multi-Schema when:

- **Medium number of larger tenants** (dozens to hundreds)
- **PostgreSQL environment** (schemas work well)
- **Better isolation** needed than shared schema
- **Cross-tenant queries** occasionally needed
- **Compliance requirements** for data separation

**Examples**: Enterprise SaaS with strict data separation needs

### Choose Multi-Database when:

- **Large enterprise tenants** (dozens of very large customers)
- **High security/compliance** requirements
- **Independent scaling** needs per tenant
- **Geographic data residency** requirements
- **Custom tenant configurations** (different schemas, extensions)

**Examples**: Enterprise platforms, healthcare systems, financial services

## Implementation patterns

### Zulip's single database approach in detail

```python
# 1. Tenant identification
class RealmMiddleware:
    def __call__(self, request):
        subdomain = extract_subdomain(request.get_host())
        request.realm = Realm.objects.get(string_id=subdomain)

# 2. Automatic tenant scoping
class TenantManager(models.Manager):
    def get_queryset(self):
        # All queries automatically filtered by current realm
        realm = get_current_realm()
        return super().get_queryset().filter(realm=realm)

# 3. Enforced foreign keys
class Message(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)  # Required
    sender = models.ForeignKey(UserProfile, on_delete=CASCADE)

    def save(self, *args, **kwargs):
        # Ensure sender belongs to same realm
        if self.sender.realm != self.realm:
            raise ValidationError("Cross-realm message not allowed")
        super().save(*args, **kwargs)

# 4. Database constraints
class Meta:
    constraints = [
        models.UniqueConstraint(
            fields=['realm', 'email'],
            name='unique_email_per_realm'
        ),
        models.CheckConstraint(
            check=Q(sender__realm=F('realm')),
            name='sender_same_realm'
        )
    ]
```

### Multi-database implementation example

```python
# Database router for tenant-specific databases
class TenantDatabaseRouter:
    def db_for_read(self, model, **hints):
        if hasattr(model, '_tenant'):
            return f'tenant_{model._tenant.slug}'
        return 'default'

    def db_for_write(self, model, **hints):
        if hasattr(model, '_tenant'):
            return f'tenant_{model._tenant.slug}'
        return 'default'

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if db.startswith('tenant_'):
            return app_label == 'myapp'  # Only migrate app tables
        return app_label != 'myapp'  # Don't migrate app tables to default

# Dynamic database creation
def create_tenant_database(tenant_slug: str):
    # 1. Create database
    db_name = f'tenant_{tenant_slug}'
    with connection.cursor() as cursor:
        cursor.execute(f'CREATE DATABASE {db_name}')

    # 2. Add to Django settings
    settings.DATABASES[db_name] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': db_name,
        'USER': 'app_user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
    }

    # 3. Run migrations on new database
    call_command('migrate', database=db_name)

    # 4. Create tenant record
    Tenant.objects.create(slug=tenant_slug, database=db_name)

# Tenant-aware models
class TenantAwareModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # Route to correct database
        tenant = get_current_tenant()
        kwargs['using'] = f'tenant_{tenant.slug}'
        super().save(*args, **kwargs)
```

## Migration strategies

### Single database migrations (Zulip approach)

```python
# Simple - one migration affects all tenants
def migrate_add_feature_flag(apps, schema_editor):
    Realm = apps.get_model('zerver', 'Realm')

    # Apply to all realms at once
    Realm.objects.filter(
        plan_type__in=[Realm.PLAN_TYPE_STANDARD, Realm.PLAN_TYPE_PLUS]
    ).update(new_feature_enabled=True)
```

### Multi-database migrations

```python
# Complex - must iterate through all tenant databases
def migrate_all_tenants():
    for tenant in Tenant.objects.all():
        db_name = f'tenant_{tenant.slug}'

        try:
            # Run migration on each tenant database
            call_command('migrate', database=db_name, verbosity=0)
            print(f"✓ Migrated {tenant.slug}")
        except Exception as e:
            print(f"✗ Failed to migrate {tenant.slug}: {e}")
            # Handle failure - rollback? continue? halt?

# Zero-downtime migrations require careful orchestration
def rolling_migration():
    for tenant in Tenant.objects.all():
        # 1. Put tenant in maintenance mode
        tenant.maintenance_mode = True
        tenant.save()

        # 2. Migrate tenant database
        migrate_tenant_database(tenant)

        # 3. Exit maintenance mode
        tenant.maintenance_mode = False
        tenant.save()

        # 4. Brief pause before next tenant
        time.sleep(1)
```

## Performance considerations

### Single database optimization (Zulip style)

```sql
-- Critical: Compound indexes starting with realm_id
CREATE INDEX users_realm_email_idx ON users(realm_id, email);
CREATE INDEX messages_realm_date_idx ON messages(realm_id, created_at);

-- Query performance example
EXPLAIN ANALYZE SELECT * FROM messages
WHERE realm_id = 123 AND created_at > '2024-01-01';

-- Result: Index scan, very fast even with millions of messages
```

### Partitioning for very large single databases

```sql
-- Partition by realm_id for extremely large tables
CREATE TABLE messages (
    id BIGSERIAL,
    realm_id INTEGER,
    content TEXT,
    created_at TIMESTAMP
) PARTITION BY HASH (realm_id);

-- Create partitions
CREATE TABLE messages_p0 PARTITION OF messages FOR VALUES WITH (modulus 4, remainder 0);
CREATE TABLE messages_p1 PARTITION OF messages FOR VALUES WITH (modulus 4, remainder 1);
CREATE TABLE messages_p2 PARTITION OF messages FOR VALUES WITH (modulus 4, remainder 2);
CREATE TABLE messages_p3 PARTITION OF messages FOR VALUES WITH (modulus 4, remainder 3);
```

## Security implications

### Single database security (Zulip approach)

```python
# Application-level security is critical
def ensure_same_realm(user: UserProfile, message: Message):
    if user.realm != message.realm:
        raise PermissionDenied("Cross-realm access denied")

# Database constraints as backup
ALTER TABLE messages
ADD CONSTRAINT messages_sender_realm_check
CHECK (sender_realm_id = realm_id);

# Row-level security (PostgreSQL 9.5+)
CREATE POLICY tenant_isolation ON messages
FOR ALL TO app_user
USING (realm_id = current_setting('app.current_realm_id')::INTEGER);
```

### Multi-database security

```python
# Database-level isolation provides inherent security
# Even application bugs can't leak data across tenants
# But operational security becomes more complex

def secure_tenant_access(tenant_slug: str, user: User):
    # Verify user has access to this tenant
    if not user.tenants.filter(slug=tenant_slug).exists():
        raise PermissionDenied("No access to tenant")

    # Switch database context
    return f'tenant_{tenant_slug}'
```

## Monitoring and observability

### Single database monitoring

```python
# Monitor per-tenant resource usage
class RealmUsageStats(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    date = models.DateField()

    message_count = models.IntegerField()
    storage_mb = models.IntegerField()
    active_users = models.IntegerField()

# Query performance monitoring
def slow_query_analysis():
    # Identify queries that don't use realm_id index
    slow_queries = find_queries_without_realm_filter()
    alert_on_cross_realm_queries(slow_queries)
```

### Multi-database monitoring

```python
# Monitor each tenant database separately
def check_all_tenant_databases():
    for tenant in Tenant.objects.all():
        db_name = f'tenant_{tenant.slug}'

        # Check database health
        db_size = get_database_size(db_name)
        connection_count = get_connection_count(db_name)

        # Alert on issues
        if db_size > tenant.quota_gb * 1024**3:
            alert_quota_exceeded(tenant)
```

## Conclusion

**Zulip's choice: Single database with shared schema** is optimal for their use case because:

1. **Scale**: Supports thousands of organizations efficiently
2. **Cost**: Minimal operational overhead
3. **Features**: Enables cross-realm analytics and simple operations
4. **Performance**: Excellent with proper indexing
5. **Simplicity**: Easy to develop, deploy, and maintain

**When to consider alternatives:**
- **Multi-database**: Enterprise customers with strict isolation needs
- **Multi-schema**: Medium-scale SaaS with better isolation requirements

The key insight is that **there's no universally correct answer** - the choice depends on your specific requirements for isolation, scale, operations, and compliance. Zulip's approach works excellently for a chat platform serving many organizations, but a financial SaaS might need database-per-tenant for regulatory compliance.

Start with the simplest approach (single database) and migrate to more complex patterns only when specifically needed. Premature complexity in database architecture is a common cause of SaaS platform failures.