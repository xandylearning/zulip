# SaaS infrastructure strategies: Shared vs. Dedicated per tenant

This document explores infrastructure deployment strategies for SaaS applications, comparing shared infrastructure (like Zulip) versus dedicated infrastructure per tenant (separate Kubernetes clusters/namespaces).

## Overview

The infrastructure question is separate from but related to the database question. You can have:

1. **Shared Infrastructure + Shared Database** (Zulip's approach)
2. **Shared Infrastructure + Separate Databases**
3. **Dedicated Infrastructure + Shared Database**
4. **Dedicated Infrastructure + Separate Databases**

Each combination has different trade-offs for cost, isolation, security, and operational complexity.

## Zulip's approach: Shared infrastructure

**Zulip runs ALL organizations on the same infrastructure:**

```yaml
# Single Kubernetes cluster serves all tenants
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zulip-web
spec:
  replicas: 10  # Serves ALL organizations
  template:
    spec:
      containers:
      - name: zulip
        image: zulip/zulip:latest
        env:
        - name: DATABASE_URL
          value: "postgresql://zulip@postgres:5432/zulip"  # Shared DB

# Single database serves all tenants
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgresql
spec:
  replicas: 1  # One database for ALL organizations
```

### How tenant isolation works in shared infrastructure

```python
# All tenants hit same application instances
# Isolation happens at the application layer

class RealmMiddleware:
    """Every request gets routed to correct tenant data"""
    def __call__(self, request):
        # Extract tenant from subdomain
        subdomain = request.get_host().split('.')[0]  # acme-corp, university, etc.

        # Load tenant context
        request.realm = Realm.objects.get(string_id=subdomain)

        # All subsequent database queries filtered by this realm
        return self.get_response(request)

# Single application instance serves multiple tenants
def get_messages(request):
    # Automatically scoped to request.realm
    return Message.objects.filter(realm=request.realm)
```

## Alternative: Dedicated infrastructure per tenant

**Each organization gets their own Kubernetes namespace or cluster:**

### Option 1: Kubernetes namespaces per tenant

```yaml
# Namespace per tenant
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-acme-corp
  labels:
    tenant: acme-corp
    plan: enterprise

---
# Dedicated deployment per tenant
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zulip-web
  namespace: tenant-acme-corp
spec:
  replicas: 3  # Just for acme-corp
  template:
    spec:
      containers:
      - name: zulip
        image: zulip/zulip:latest
        env:
        - name: TENANT_ID
          value: "acme-corp"
        - name: DATABASE_URL
          value: "postgresql://zulip@postgres-acme:5432/acme_db"

---
# Dedicated database per tenant
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgresql-acme
  namespace: tenant-acme-corp
spec:
  replicas: 1
  template:
    spec:
      containers:
      - name: postgres
        image: postgres:15
        env:
        - name: POSTGRES_DB
          value: "acme_db"
```

### Option 2: Separate Kubernetes clusters per tenant

```bash
# Each major tenant gets their own cluster
kubectl create cluster tenant-acme-corp --region us-east-1
kubectl create cluster tenant-university --region eu-west-1
kubectl create cluster tenant-enterprise --region us-west-2

# Deploy full stack per cluster
helm install zulip ./zulip-chart --namespace default \
  --set tenant.name=acme-corp \
  --set database.name=acme_db \
  --set resources.limits.memory=8Gi
```

## Detailed comparison

| Aspect | Shared Infrastructure | Namespace per Tenant | Cluster per Tenant |
|--------|----------------------|---------------------|-------------------|
| **Resource Efficiency** | Excellent | Good | Poor |
| **Tenant Isolation** | Application-level | Container-level | Infrastructure-level |
| **Security** | Medium | High | Highest |
| **Operational Complexity** | Low | Medium | High |
| **Cost per Tenant** | Very Low | Medium | High |
| **Scaling Flexibility** | Limited | Good | Excellent |
| **Compliance** | Challenging | Good | Excellent |
| **Multi-region** | Complex | Medium | Easy |
| **Customization** | Limited | Medium | Full |
| **Disaster Recovery** | All-or-nothing | Tenant-specific | Tenant-specific |

## When to choose each approach

### Choose Shared Infrastructure when:

✅ **Many small to medium tenants** (hundreds to thousands)
✅ **Similar resource requirements** across tenants
✅ **Cost efficiency** is critical
✅ **Simple operations** preferred
✅ **Standard compliance** requirements
✅ **Uniform feature set** across tenants

**Examples**: Slack, Zulip, GitHub (public repos), most B2B SaaS

```python
# Shared infrastructure characteristics
tenant_count = 5000+
avg_tenant_size = "small-medium"
cost_sensitivity = "high"
operational_team_size = "small"
compliance_requirements = "standard"
```

### Choose Namespace per Tenant when:

✅ **Medium number of larger tenants** (dozens to hundreds)
✅ **Different resource needs** per tenant
✅ **Better isolation** required
✅ **Tenant-specific configurations** needed
✅ **Good balance** of cost vs. isolation

**Examples**: Enterprise project management, specialized industry SaaS

```python
# Namespace-per-tenant characteristics
tenant_count = 50-500
avg_tenant_size = "medium-large"
resource_variance = "high"
customization_needs = "medium"
security_requirements = "elevated"
```

### Choose Cluster per Tenant when:

✅ **Large enterprise customers** (dozens of very large tenants)
✅ **Strict compliance** requirements (HIPAA, SOX, etc.)
✅ **Geographic data residency** needs
✅ **High customization** requirements
✅ **Independent scaling** per tenant
✅ **Premium pricing** model supports costs

**Examples**: Enterprise healthcare, financial services, government

```python
# Cluster-per-tenant characteristics
tenant_count = 10-100
avg_tenant_size = "enterprise"
compliance_requirements = "strict"
customization_needs = "high"
pricing_model = "premium"
```

## Implementation patterns

### Zulip's shared infrastructure implementation

```python
# Single application serves all tenants
# zproject/computed_settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'zulip',  # One database
        'HOST': 'postgres-service',  # One database server
    }
}

# Tenant routing in application
class RealmMiddleware:
    def __call__(self, request):
        # Route to tenant data within same app instance
        realm = self.get_realm_from_request(request)
        request.realm = realm

        # All queries automatically scoped
        with realm_context(realm):
            return self.get_response(request)

# Kubernetes deployment - single deployment serves all
apiVersion: apps/v1
kind: Deployment
metadata:
  name: zulip-web
spec:
  replicas: 5  # Shared across ALL tenants
  template:
    spec:
      containers:
      - name: zulip
        resources:
          requests:
            memory: "2Gi"    # Shared resource pool
            cpu: "1000m"
          limits:
            memory: "4Gi"
            cpu: "2000m"
```

### Namespace-per-tenant implementation

```python
# Tenant provisioning automation
class TenantProvisioner:
    def create_tenant_infrastructure(self, tenant_name: str, plan: str):
        # 1. Create Kubernetes namespace
        self.create_namespace(tenant_name)

        # 2. Deploy tenant-specific resources
        self.deploy_application(tenant_name, plan)

        # 3. Setup monitoring and networking
        self.setup_tenant_monitoring(tenant_name)

        # 4. Configure ingress
        self.setup_ingress(tenant_name)

    def create_namespace(self, tenant_name: str):
        namespace_yaml = f"""
apiVersion: v1
kind: Namespace
metadata:
  name: tenant-{tenant_name}
  labels:
    tenant: {tenant_name}
    managed-by: tenant-provisioner
"""
        self.kubectl_apply(namespace_yaml)

    def deploy_application(self, tenant_name: str, plan: str):
        # Plan-specific resource allocation
        resources = self.get_plan_resources(plan)

        deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
  namespace: tenant-{tenant_name}
spec:
  replicas: {resources['replicas']}
  template:
    spec:
      containers:
      - name: app
        image: myapp:latest
        env:
        - name: TENANT_ID
          value: "{tenant_name}"
        resources:
          requests:
            memory: "{resources['memory']}"
            cpu: "{resources['cpu']}"
"""
        self.kubectl_apply(deployment_yaml)

    def get_plan_resources(self, plan: str) -> dict:
        plans = {
            'starter': {'replicas': 1, 'memory': '512Mi', 'cpu': '250m'},
            'pro': {'replicas': 2, 'memory': '1Gi', 'cpu': '500m'},
            'enterprise': {'replicas': 3, 'memory': '2Gi', 'cpu': '1000m'},
        }
        return plans[plan]
```

### Cluster-per-tenant implementation

```python
# Enterprise tenant provisioning
class EnterpriseClusterProvisioner:
    def provision_tenant_cluster(self, tenant: str, config: dict):
        # 1. Create dedicated cluster
        cluster_name = f"tenant-{tenant}"
        region = config.get('region', 'us-east-1')

        cluster_config = {
            'name': cluster_name,
            'region': region,
            'node_pools': [
                {
                    'name': 'app-nodes',
                    'machine_type': config['node_type'],
                    'min_nodes': config['min_nodes'],
                    'max_nodes': config['max_nodes'],
                }
            ],
            'network': f"tenant-{tenant}-vpc",
            'private_cluster': True,
        }

        self.create_gke_cluster(cluster_config)

        # 2. Deploy full application stack
        self.deploy_tenant_stack(cluster_name, tenant, config)

        # 3. Setup monitoring and backup
        self.setup_cluster_monitoring(cluster_name)
        self.setup_cluster_backup(cluster_name)

    def deploy_tenant_stack(self, cluster: str, tenant: str, config: dict):
        # Switch to tenant cluster
        self.set_kubectl_context(cluster)

        # Deploy with tenant-specific configuration
        helm_values = {
            'tenant': {
                'name': tenant,
                'domain': f"{tenant}.myapp.com",
            },
            'database': {
                'size': config['db_size'],
                'backup_retention': config['backup_days'],
            },
            'ingress': {
                'ssl_cert': config['ssl_cert'],
                'custom_domain': config.get('custom_domain'),
            }
        }

        self.helm_install('myapp', './charts/myapp', helm_values)
```

## Cost analysis

### Shared infrastructure costs (Zulip approach)

```python
# Cost efficiency example for 1000 tenants
monthly_costs = {
    'kubernetes_cluster': 500,      # Single cluster
    'database': 200,                # Single PostgreSQL instance
    'load_balancer': 50,           # Single ingress
    'monitoring': 100,             # Single monitoring stack
    'total': 850
}

cost_per_tenant = monthly_costs['total'] / 1000  # $0.85 per tenant
```

### Namespace-per-tenant costs

```python
# Cost scaling example for 100 tenants
base_costs = {
    'kubernetes_cluster': 500,     # Single cluster (shared)
    'monitoring': 100,             # Shared monitoring
}

per_tenant_costs = {
    'database': 20,                # Dedicated DB per tenant
    'storage': 10,                 # Dedicated PVC
    'ingress': 5,                  # Additional ingress rules
}

total_monthly = base_costs['kubernetes_cluster'] + base_costs['monitoring'] + \
                (per_tenant_costs['database'] + per_tenant_costs['storage'] +
                 per_tenant_costs['ingress']) * 100

cost_per_tenant = total_monthly / 100  # $35.6 per tenant
```

### Cluster-per-tenant costs

```python
# Cost scaling for 10 enterprise tenants
per_cluster_costs = {
    'kubernetes_control_plane': 100,  # GKE/EKS management fee
    'worker_nodes': 400,              # Minimum viable node pool
    'load_balancer': 50,              # Dedicated LB
    'monitoring': 30,                 # Cluster monitoring
    'backup': 20,                     # Cluster backup
    'total_per_cluster': 600
}

total_monthly = per_cluster_costs['total_per_cluster'] * 10
cost_per_tenant = per_cluster_costs['total_per_cluster']  # $600 per tenant
```

## Security implications

### Shared infrastructure security (Zulip approach)

```python
# Application-level security is critical
class TenantSecurityMiddleware:
    def __call__(self, request):
        # Validate tenant access
        tenant = self.get_tenant_from_request(request)
        user = self.get_authenticated_user(request)

        if not self.user_has_tenant_access(user, tenant):
            raise PermissionDenied("No access to this organization")

        # Set security context
        request.security_context = {
            'tenant': tenant,
            'user': user,
            'permissions': self.get_user_permissions(user, tenant)
        }

        return self.get_response(request)

# Database-level protection
class TenantQuerySet(models.QuerySet):
    def filter_by_tenant(self, tenant):
        return self.filter(realm=tenant)

# Network security - all tenants share same network
class SharedNetworkSecurity:
    """All tenants in same network namespace"""
    ingress_rules = [
        "allow port 443 from internet",  # HTTPS for all tenants
        "allow port 80 from internet",   # HTTP redirect
    ]

    egress_rules = [
        "allow outbound to database",    # Shared database
        "allow outbound to external APIs" # Email, etc.
    ]
```

### Dedicated infrastructure security

```python
# Network-level isolation per tenant
class TenantNetworkSecurity:
    def create_tenant_network(self, tenant: str):
        return {
            'vpc': f"tenant-{tenant}-vpc",
            'subnets': {
                'app': f"10.{tenant_id}.1.0/24",
                'db': f"10.{tenant_id}.2.0/24",
                'dmz': f"10.{tenant_id}.3.0/24",
            },
            'security_groups': {
                'app': ['allow 443 from lb', 'allow 5432 to db'],
                'db': ['allow 5432 from app only'],
                'lb': ['allow 443 from internet'],
            }
        }

# Infrastructure-level isolation
apiVersion: v1
kind: NetworkPolicy
metadata:
  name: tenant-isolation
  namespace: tenant-acme-corp
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          tenant: acme-corp  # Only same tenant traffic
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          tenant: acme-corp  # Only same tenant traffic
```

## Operational complexity

### Shared infrastructure operations

```python
# Simple operations - one deployment affects all tenants
class SharedInfraOps:
    def deploy_update(self, version: str):
        # Single deployment updates all tenants
        kubectl_commands = [
            f"kubectl set image deployment/app app=myapp:{version}",
            "kubectl rollout status deployment/app",
        ]

        # All tenants updated simultaneously
        return self.execute_commands(kubectl_commands)

    def monitor_health(self):
        # Single monitoring dashboard for all tenants
        metrics = {
            'total_requests': self.get_metric('http_requests_total'),
            'error_rate': self.get_metric('http_errors_rate'),
            'response_time': self.get_metric('http_response_time'),
        }
        return metrics

    def scale_application(self, target_replicas: int):
        # Scale affects all tenants
        return self.kubectl(f"scale deployment/app --replicas={target_replicas}")
```

### Multi-tenant infrastructure operations

```python
# Complex operations - must handle each tenant separately
class MultiTenantOps:
    def deploy_update(self, version: str, tenants: list = None):
        results = {}
        tenants = tenants or self.get_all_tenants()

        for tenant in tenants:
            try:
                # Deploy to each tenant separately
                namespace = f"tenant-{tenant}"
                result = self.kubectl(
                    f"set image deployment/app app=myapp:{version} -n {namespace}"
                )
                results[tenant] = {'status': 'success', 'result': result}

                # Wait between deployments to avoid overwhelming cluster
                time.sleep(30)

            except Exception as e:
                results[tenant] = {'status': 'failed', 'error': str(e)}
                # Continue with other tenants or abort?

        return results

    def monitor_tenant_health(self, tenant: str):
        namespace = f"tenant-{tenant}"

        # Tenant-specific monitoring
        metrics = {
            'requests': self.get_tenant_metric('http_requests_total', namespace),
            'errors': self.get_tenant_metric('http_errors_rate', namespace),
            'cpu_usage': self.get_tenant_metric('cpu_usage', namespace),
            'memory_usage': self.get_tenant_metric('memory_usage', namespace),
        }
        return metrics

    def scale_tenant(self, tenant: str, replicas: int):
        namespace = f"tenant-{tenant}"
        return self.kubectl(f"scale deployment/app --replicas={replicas} -n {namespace}")
```

## Migration and disaster recovery

### Shared infrastructure DR

```python
# Simple backup/restore - all tenants together
class SharedInfraDR:
    def backup_all_data(self):
        # Single database backup includes all tenants
        backup_commands = [
            "pg_dump zulip > /backup/zulip_$(date +%Y%m%d).sql",
            "kubectl create backup cluster-backup-$(date +%Y%m%d)",
        ]
        return self.execute_backup(backup_commands)

    def restore_from_backup(self, backup_date: str):
        # Restoring affects ALL tenants
        restore_commands = [
            f"psql zulip < /backup/zulip_{backup_date}.sql",
            f"kubectl restore cluster-backup-{backup_date}",
        ]
        return self.execute_restore(restore_commands)
```

### Multi-tenant infrastructure DR

```python
# Complex tenant-specific backup/restore
class MultiTenantDR:
    def backup_tenant(self, tenant: str):
        namespace = f"tenant-{tenant}"

        # Tenant-specific backup
        backup_commands = [
            f"pg_dump {tenant}_db > /backup/{tenant}_{datetime.now().strftime('%Y%m%d')}.sql",
            f"kubectl create backup {tenant}-backup -n {namespace}",
            f"aws s3 cp /backup/{tenant}_* s3://backups/{tenant}/",
        ]
        return self.execute_tenant_backup(tenant, backup_commands)

    def restore_tenant(self, tenant: str, backup_date: str):
        # Granular tenant restore without affecting others
        namespace = f"tenant-{tenant}"

        restore_commands = [
            f"kubectl delete namespace {namespace}",
            f"kubectl create namespace {namespace}",
            f"psql {tenant}_db < /backup/{tenant}_{backup_date}.sql",
            f"kubectl restore {tenant}-backup-{backup_date} -n {namespace}",
        ]
        return self.execute_tenant_restore(tenant, restore_commands)
```

## Hybrid approaches

### Smart tenant placement

```python
# Combine approaches based on tenant characteristics
class SmartTenantPlacement:
    def place_tenant(self, tenant: dict) -> str:
        """Decide infrastructure strategy per tenant"""

        if tenant['plan'] == 'enterprise' and tenant['users'] > 1000:
            # Large enterprise gets dedicated cluster
            return self.provision_dedicated_cluster(tenant)

        elif tenant['compliance_requirements'] or tenant['custom_domain']:
            # Medium tenants get dedicated namespace
            return self.provision_dedicated_namespace(tenant)

        else:
            # Small tenants go to shared infrastructure
            return self.add_to_shared_infrastructure(tenant)

    def tier_upgrade(self, tenant: str, new_plan: str):
        """Migrate tenant between infrastructure tiers"""
        if new_plan == 'enterprise':
            # Migrate from shared to dedicated
            self.migrate_to_dedicated_cluster(tenant)
```

## Recommendations

### Start with shared infrastructure (Zulip's approach) when:

- Building a new SaaS platform
- Serving many small-medium customers
- Cost efficiency is important
- Team is small and operational simplicity matters
- Standard compliance requirements

### Graduate to namespace-per-tenant when:

- You have 50+ medium-large tenants
- Different resource requirements per tenant
- Need better isolation for security/compliance
- Can handle increased operational complexity

### Move to cluster-per-tenant only when:

- Serving large enterprise customers
- Strict compliance requirements (HIPAA, SOX)
- Premium pricing supports the costs
- Need geographic data residency
- Extensive customization per tenant

## Conclusion

**Zulip's shared infrastructure approach is optimal for most SaaS applications because:**

1. **Cost efficiency**: Serves thousands of organizations at minimal per-tenant cost
2. **Operational simplicity**: Single deployment, monitoring, and management
3. **Resource efficiency**: Optimal utilization of compute resources
4. **Proven scalability**: Handles Zulip's massive scale effectively

**Consider dedicated infrastructure only when:**
- Enterprise customers specifically require it
- Compliance mandates infrastructure isolation
- Premium pricing model supports the additional costs
- You have the operational expertise to manage complexity

**Key insight**: Start simple with shared infrastructure and evolve based on actual customer requirements, not theoretical needs. Premature infrastructure complexity has killed more SaaS platforms than inadequate isolation ever has.

The database and infrastructure decisions are independent - you can mix and match:
- **Shared infra + shared DB**: Most cost-effective (Zulip)
- **Shared infra + separate DBs**: Good isolation with manageable complexity
- **Dedicated infra + separate DBs**: Maximum isolation for enterprise customers