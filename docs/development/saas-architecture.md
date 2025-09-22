# SaaS multi-tenant architecture with Zulip's Realm model

This document explains how Zulip implements a Software-as-a-Service (SaaS) multi-tenant architecture using its Realm-based data model. Understanding this pattern helps developers build scalable SaaS applications with proper tenant isolation and feature management.

## Overview

Zulip's architecture demonstrates a sophisticated approach to SaaS multi-tenancy through its **Realm** model. Each realm represents an independent organization with complete data isolation, custom settings, and billing management - making it an excellent pattern for building multi-tenant SaaS applications.

## Core concepts

### What is a Realm?

A Realm in Zulip is essentially a **tenant** in SaaS terminology. It represents:

- An independent organization or workspace
- Complete data isolation boundary
- Billing and subscription unit
- Configuration and customization scope
- Security and access control boundary

```python
# zerver/models/realms.py
class Realm(models.Model):
    # Tenant identification
    string_id = models.CharField(max_length=40, unique=True)  # Subdomain
    uuid = models.UUIDField(default=uuid4, unique=True)      # Push notifications

    # Organization metadata
    name = models.CharField(max_length=40)
    description = models.TextField(default="")
    date_created = models.DateTimeField(default=timezone_now)

    # SaaS billing and plans
    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_HOSTED)

    # Tenant lifecycle
    deactivated = models.BooleanField(default=False)
    scheduled_deletion_date = models.DateTimeField(default=None, null=True)
```

### Tenant isolation pattern

Every major entity in Zulip includes a `realm` foreign key, ensuring complete data isolation:

```python
# Example models showing realm-based isolation
class UserProfile(models.Model):
    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)
    # ... user data

class Stream(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    # ... stream data

class Message(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    # ... message data
```

**Key insight**: No cross-realm data access is possible at the database level, providing strong security guarantees.

## SaaS architecture components

### 1. Subdomain-based tenant routing

Zulip uses subdomains to route requests to the correct tenant:

```
https://acme-corp.zulipchat.com    → realm.string_id = "acme-corp"
https://university.zulipchat.com   → realm.string_id = "university"
https://opensource.zulipchat.com   → realm.string_id = "opensource"
```

**Implementation pattern**:
```python
# Middleware extracts realm from subdomain
class RealmMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract subdomain from request
        subdomain = request.get_host().split('.')[0]

        # Load realm and set in request context
        try:
            request.realm = Realm.objects.get(string_id=subdomain)
        except Realm.DoesNotExist:
            # Handle tenant not found
            pass

        return self.get_response(request)
```

### 2. Plan-based feature management

Zulip implements tiered SaaS pricing through plan types:

```python
class Realm(models.Model):
    # SaaS plan tiers
    PLAN_TYPE_SELF_HOSTED = 1      # On-premise installations
    PLAN_TYPE_LIMITED = 2          # Free tier with restrictions
    PLAN_TYPE_STANDARD = 3         # Standard paid plan
    PLAN_TYPE_STANDARD_FREE = 4    # Free standard plan (limited time)
    PLAN_TYPE_PLUS = 10           # Premium tier with advanced features

    plan_type = models.PositiveSmallIntegerField(default=PLAN_TYPE_SELF_HOSTED)

    def can_enable_restricted_user_access_for_guests(self) -> None:
        """Premium feature gating example"""
        if self.plan_type not in [Realm.PLAN_TYPE_PLUS, Realm.PLAN_TYPE_SELF_HOSTED]:
            raise JsonableError("Upgrade to Plus plan required")

    def get_upload_quota_gb(self) -> int | None:
        """Plan-based resource quotas"""
        plan_quotas = {
            self.PLAN_TYPE_LIMITED: 5,          # 5GB for free
            self.PLAN_TYPE_STANDARD_FREE: 50,   # 50GB for standard free
            self.PLAN_TYPE_STANDARD: None,      # Unlimited for paid
            self.PLAN_TYPE_PLUS: None,         # Unlimited for plus
        }
        return plan_quotas.get(self.plan_type)
```

### 3. Organization-level customization

Each realm can be independently configured:

```python
class Realm(models.Model):
    # Authentication settings
    emails_restricted_to_domains = models.BooleanField(default=False)
    invite_required = models.BooleanField(default=True)

    # Feature toggles
    enable_spectator_access = models.BooleanField(default=False)
    enable_guest_user_indicator = models.BooleanField(default=True)

    # UI customization
    name = models.CharField(max_length=40)
    description = models.TextField(default="")

    # Integration settings
    bot_creation_policy = models.PositiveSmallIntegerField(default=1)
    create_multiuse_invite_group = models.ForeignKey(UserGroup, ...)
```

### 4. Billing integration

Corporate billing is handled separately but linked to realms:

```python
# corporate/models/stripe_state.py
class Customer(models.Model):
    realm = models.OneToOneField(Realm, on_delete=CASCADE)
    stripe_customer_id = models.CharField(max_length=255, unique=True)
    # ... billing data

class CustomerPlan(models.Model):
    customer = models.ForeignKey(Customer, on_delete=CASCADE)
    status = models.SmallIntegerField()
    billing_cycle_anchor = models.DateTimeField()
    # ... subscription data
```

## Implementing SaaS features

### User roles and permissions

Zulip implements sophisticated role-based access control within each realm:

```python
class UserProfile(models.Model):
    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)

    # Hierarchical roles
    ROLE_REALM_OWNER = 100
    ROLE_REALM_ADMINISTRATOR = 200
    ROLE_FACULTY = 450
    ROLE_STUDENT = 500
    ROLE_PARENT = 550
    ROLE_MENTOR = 580

    role = models.PositiveSmallIntegerField(default=ROLE_FACULTY)

    def has_permission(self, policy_name: str) -> bool:
        """Check if user has permission for realm setting"""
        allowed_user_group_id = getattr(self.realm, policy_name).id
        return user_has_permission_for_group_setting(allowed_user_group_id, self)
```

### Settings inheritance and defaults

Zulip supports realm-wide default settings for new users:

```python
class RealmUserDefault(UserBaseSettings):
    """Realm-level default values for user preferences"""
    realm = models.OneToOneField("zerver.Realm", on_delete=CASCADE)

    # Inherits all user settings fields
    # When new users join, they get these defaults

class UserProfile(UserBaseSettings):
    """Individual user inherits from the same base"""
    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)
    # User can override realm defaults
```

### Feature flags and gradual rollout

```python
class Realm(models.Model):
    # Feature flags for A/B testing and gradual rollout
    enable_spectator_access = models.BooleanField(default=False)
    enable_guest_user_indicator = models.BooleanField(default=True)

    def web_public_streams_enabled(self) -> bool:
        """Complex feature gating logic"""
        if not settings.WEB_PUBLIC_STREAMS_ENABLED:
            return False
        if self.plan_type == self.PLAN_TYPE_LIMITED:
            return False
        return self.enable_spectator_access
```

## Database design patterns

### 1. Realm-scoped queries

All queries must be scoped to the current realm:

```python
# Always include realm in queries
def get_streams_for_user(user_profile: UserProfile) -> QuerySet[Stream]:
    return Stream.objects.filter(
        realm=user_profile.realm,  # Tenant isolation
        # ... other filters
    )

# Never query across realms
def get_all_users():  # ❌ WRONG - crosses tenant boundaries
    return UserProfile.objects.all()

def get_realm_users(realm: Realm):  # ✅ CORRECT - tenant-scoped
    return UserProfile.objects.filter(realm=realm)
```

### 2. Database indexing strategy

```python
class UserProfile(models.Model):
    realm = models.ForeignKey("zerver.Realm", on_delete=CASCADE)
    email = models.EmailField(db_index=True)

    class Meta:
        # Compound indexes for tenant + lookup key
        constraints = [
            models.UniqueConstraint(
                "realm",
                Upper(F("email")),
                name="zerver_userprofile_realm_id_email_uniq",
            ),
        ]
```

### 3. Data migration patterns

When adding new features, consider realm-specific rollouts:

```python
# Migration example
def migrate_feature_to_realms(apps, schema_editor):
    Realm = apps.get_model('zerver', 'Realm')

    # Enable for specific plan types only
    Realm.objects.filter(
        plan_type__in=[Realm.PLAN_TYPE_PLUS, Realm.PLAN_TYPE_STANDARD]
    ).update(new_feature_enabled=True)
```

## Advanced SaaS patterns

### 1. Multi-region support

Extend the realm model for geographic distribution:

```python
class Realm(models.Model):
    # Geographic distribution
    region = models.CharField(max_length=20, default='us-east-1')
    data_center = models.CharField(max_length=50)

    @property
    def database_router_hint(self):
        """Route to region-specific database"""
        return f"db_{self.region}"
```

### 2. Resource usage tracking

Track tenant resource consumption:

```python
class RealmUsageStats(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    date = models.DateField()

    # Resource metrics
    message_count = models.IntegerField(default=0)
    storage_used_mb = models.IntegerField(default=0)
    api_calls = models.IntegerField(default=0)
    active_users = models.IntegerField(default=0)

    class Meta:
        unique_together = ('realm', 'date')
```

### 3. Compliance and audit trails

```python
class RealmAuditLog(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    acting_user = models.ForeignKey(UserProfile, null=True, on_delete=CASCADE)
    event_type = models.PositiveSmallIntegerField()
    event_time = models.DateTimeField(default=timezone_now)
    extra_data = models.JSONField(default=dict)

    # Track all administrative actions per tenant
```

### 4. Custom domain support

```python
class RealmDomain(models.Model):
    realm = models.ForeignKey(Realm, on_delete=CASCADE)
    domain = models.CharField(max_length=80, db_index=True)
    allow_subdomains = models.BooleanField(default=False)

    # Support custom.company.com → realm mapping
```

## Implementation guide

### Step 1: Define your tenant model

```python
class Organization(models.Model):  # Your "Realm" equivalent
    # Tenant identification
    slug = models.SlugField(unique=True)  # URL identifier
    name = models.CharField(max_length=100)

    # SaaS management
    plan_type = models.CharField(max_length=20, choices=PLAN_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    # Billing
    stripe_customer_id = models.CharField(max_length=100, null=True)

    # Settings
    settings = models.JSONField(default=dict)
```

### Step 2: Add tenant foreign keys

```python
class User(AbstractUser):
    organization = models.ForeignKey(Organization, on_delete=CASCADE)

class Project(models.Model):
    organization = models.ForeignKey(Organization, on_delete=CASCADE)
    name = models.CharField(max_length=100)

class Document(models.Model):
    organization = models.ForeignKey(Organization, on_delete=CASCADE)
    project = models.ForeignKey(Project, on_delete=CASCADE)
```

### Step 3: Implement middleware

```python
class TenantMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Extract tenant from subdomain or path
        tenant_slug = self.extract_tenant(request)

        try:
            request.tenant = Organization.objects.get(
                slug=tenant_slug,
                is_active=True
            )
        except Organization.DoesNotExist:
            return HttpResponse("Tenant not found", status=404)

        return self.get_response(request)

    def extract_tenant(self, request):
        # Subdomain approach: tenant.yourapp.com
        host_parts = request.get_host().split('.')
        if len(host_parts) > 2:
            return host_parts[0]

        # Path approach: yourapp.com/tenant/
        path_parts = request.path.strip('/').split('/')
        if path_parts:
            return path_parts[0]

        raise ValueError("Could not extract tenant")
```

### Step 4: Create tenant-aware managers

```python
class TenantAwareManager(models.Manager):
    def get_queryset(self):
        # Automatically filter by current tenant
        from threading import local
        thread_local = local()

        if hasattr(thread_local, 'current_tenant'):
            return super().get_queryset().filter(
                organization=thread_local.current_tenant
            )
        return super().get_queryset()

class User(AbstractUser):
    organization = models.ForeignKey(Organization, on_delete=CASCADE)

    objects = TenantAwareManager()
    all_objects = models.Manager()  # Bypass tenant filtering
```

### Step 5: Implement plan-based feature gates

```python
class FeatureGate:
    @staticmethod
    def require_plan(required_plans: list[str]):
        def decorator(view_func):
            def wrapper(request, *args, **kwargs):
                if request.tenant.plan_type not in required_plans:
                    return JsonResponse({
                        'error': 'Upgrade required',
                        'required_plans': required_plans
                    }, status=402)
                return view_func(request, *args, **kwargs)
            return wrapper
        return decorator

# Usage
@FeatureGate.require_plan(['premium', 'enterprise'])
def advanced_analytics_view(request):
    # Only available to premium/enterprise tenants
    pass
```

## Best practices

### 1. Security considerations

- **Never trust tenant context from client**: Always derive tenant from authenticated context
- **Validate cross-tenant references**: Prevent tenant A from accessing tenant B's data
- **Use database constraints**: Enforce tenant isolation at the database level
- **Audit cross-tenant queries**: Log and monitor any queries that span tenants

### 2. Performance optimization

- **Index on tenant + lookup key**: Create compound indexes for common query patterns
- **Partition large tables**: Consider partitioning by tenant for very large datasets
- **Cache tenant-specific data**: Use tenant-aware caching strategies
- **Monitor per-tenant performance**: Track resource usage per tenant

### 3. Operational considerations

- **Tenant lifecycle management**: Handle tenant creation, suspension, and deletion
- **Data retention policies**: Implement tenant-specific data retention
- **Backup strategies**: Consider tenant-specific backup and restore procedures
- **Monitoring and alerting**: Set up tenant-specific monitoring and quotas

### 4. Migration and deployment

- **Feature flag management**: Use tenant-specific feature flags for gradual rollouts
- **Schema migrations**: Consider impact on all tenants during schema changes
- **Zero-downtime deployments**: Ensure migrations don't impact tenant availability
- **Rollback procedures**: Plan for tenant-specific rollbacks if needed

## Testing strategies

### Unit testing with tenant isolation

```python
class TenantTestCase(TestCase):
    def setUp(self):
        self.tenant = Organization.objects.create(
            slug='test-org',
            name='Test Organization',
            plan_type='standard'
        )
        self.user = User.objects.create(
            username='testuser',
            organization=self.tenant
        )

    def test_tenant_isolation(self):
        # Create data in another tenant
        other_tenant = Organization.objects.create(
            slug='other-org',
            name='Other Organization'
        )
        other_user = User.objects.create(
            username='otheruser',
            organization=other_tenant
        )

        # Verify isolation
        with tenant_context(self.tenant):
            users = User.objects.all()
            self.assertEqual(users.count(), 1)
            self.assertEqual(users.first(), self.user)
```

### Integration testing

```python
def test_tenant_routing():
    """Test that requests are routed to correct tenant"""
    # Test subdomain routing
    response = client.get('/', HTTP_HOST='acme.example.com')
    assert response.context['tenant'].slug == 'acme'

    # Test tenant isolation in responses
    response = client.get('/api/users/', HTTP_HOST='acme.example.com')
    user_data = response.json()
    assert all(u['organization'] == 'acme' for u in user_data['users'])
```

## Conclusion

Zulip's realm-based architecture provides a robust foundation for building SaaS applications with:

- **Complete tenant isolation** through database-level constraints
- **Flexible billing and plan management** with feature gating
- **Scalable multi-tenant operations** with efficient indexing
- **Security by design** with tenant-aware access controls
- **Operational excellence** with comprehensive audit trails

This pattern scales from small SaaS applications to enterprise platforms while maintaining strong security and performance characteristics. The key insight is treating tenancy as a first-class architectural concern rather than an afterthought.

By following Zulip's patterns, you can build SaaS applications that are secure, scalable, and operationally robust from day one.