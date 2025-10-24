# Adding a New Django App to Zulip

This guide explains how to add a new Django app to the Zulip codebase. Follow these steps to ensure proper integration with Zulip's architecture, URL routing, admin interface, and frontend systems.

## Table of Contents

1. [Overview](#overview)
2. [Directory Structure](#directory-structure)
3. [Step-by-Step Guide](#step-by-step-guide)
4. [URL Configuration](#url-configuration)
5. [Admin Configuration](#admin-configuration)
6. [Frontend Integration](#frontend-integration)
7. [Testing Your App](#testing-your-app)
8. [Best Practices](#best-practices)
9. [Examples](#examples)

---

## Overview

Zulip's modular architecture allows you to add new Django apps without modifying core functionality. Apps can be:

- **Core apps**: Integrated directly into `INSTALLED_APPS` in `zproject/computed_settings.py`
- **Plugin apps**: Added via `EXTRA_INSTALLED_APPS` for optional features

### Key Files to Modify

1. **Settings**: `zproject/computed_settings.py` (for core apps) or `zproject/dev_settings.py` (for development)
2. **URLs**: `zproject/urls.py`
3. **Apps Config**: Your app's `apps.py`
4. **Models**: Your app's `models.py`
5. **Views**: Your app's `views.py`
6. **URLs**: Your app's `urls.py`

---

## Directory Structure

Create your Django app at the root level of the Zulip project:

```
zulip/
├── zerver/                  # Main Zulip app
├── corporate/               # Corporate features
├── zilencer/                # Analytics
├── confirmation/            # Email confirmation
├── lms_integration/         # Example: LMS integration
├── zulip_calls_plugin/      # Example: Calls plugin
├── your_new_app/            # Your new app ⭐
│   ├── __init__.py
│   ├── apps.py              # App configuration
│   ├── models.py            # Database models
│   ├── views.py             # API views
│   ├── urls.py              # URL routing
│   ├── admin.py             # (Optional) Admin interface
│   ├── migrations/          # Database migrations
│   │   └── __init__.py
│   ├── management/          # (Optional) Management commands
│   │   └── commands/
│   ├── static/              # (Optional) Static files
│   │   └── your_app/
│   ├── templates/           # (Optional) Templates
│   │   └── your_app/
│   └── tests/               # (Optional) Tests
│       └── __init__.py
├── zproject/                # Django project settings
│   ├── settings.py
│   ├── computed_settings.py # Main settings file
│   ├── dev_settings.py      # Development settings
│   └── urls.py              # Root URL configuration
└── manage.py
```

---

## Step-by-Step Guide

### Step 1: Create Your Django App

```bash
# Create the app directory
mkdir your_new_app
cd your_new_app

# Create required files
touch __init__.py apps.py models.py views.py urls.py
mkdir migrations
touch migrations/__init__.py
```

### Step 2: Configure `apps.py`

Create your app configuration in `your_new_app/apps.py`:

```python
from django.apps import AppConfig


class YourAppConfig(AppConfig):
    """Django app configuration for Your App"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "your_new_app"
    verbose_name = "Your App Name"

    def ready(self) -> None:
        """Initialize the app when Django starts"""
        # Import signal handlers
        # import your_new_app.signals

        # Register any startup tasks
        pass
```

**Key points:**
- `name`: Must match your app directory name
- `default_auto_field`: Use `BigAutoField` for consistency with Zulip
- `ready()`: Use for initialization code, signal registration, etc.

### Step 3: Define Models

Create your database models in `your_new_app/models.py`:

```python
from django.db import models
from zerver.models import Realm, UserProfile


class YourModel(models.Model):
    """Example model for your app"""

    # Link to Zulip's realm for multi-tenancy
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)

    # Link to users
    user = models.ForeignKey(UserProfile, on_delete=models.CASCADE)

    # Your custom fields
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "your_app_yourmodel"
        indexes = [
            models.Index(fields=["realm", "user"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.realm.string_id})"
```

**Best practices:**
- Always include a `realm` field for multi-tenancy
- Use `on_delete=models.CASCADE` for required relationships
- Define explicit `db_table` names for clarity
- Add indexes for frequently queried fields
- Implement `__str__()` for admin interface readability

### Step 4: Create Views

Define your API views in `your_new_app/views.py`:

```python
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from zerver.decorator import authenticated_json_view
from zerver.lib.request import REQ, has_request_variables
from zerver.lib.response import json_success
from zerver.models import UserProfile

from .models import YourModel


@require_http_methods(["GET", "POST"])
@authenticated_json_view
@has_request_variables
def your_view(
    request: HttpRequest,
    user_profile: UserProfile,
    name: str = REQ(),
    description: str = REQ(default=""),
) -> JsonResponse:
    """
    Example API endpoint for your app.

    POST /api/v1/your-app/endpoint
    """
    # Your business logic here
    obj = YourModel.objects.create(
        realm=user_profile.realm,
        user=user_profile,
        name=name,
        description=description,
    )

    return json_success(request, data={
        "id": obj.id,
        "name": obj.name,
        "description": obj.description,
    })
```

**Key decorators:**
- `@authenticated_json_view`: Requires authentication, returns JSON
- `@has_request_variables`: Validates request parameters with `REQ()`
- `@require_http_methods`: Restricts HTTP methods

For REST endpoints using Zulip's REST API framework:

```python
from zerver.lib.rest import rest_path

# In your urls.py
rest_path("your-app/endpoint", GET=get_view, POST=post_view),
```

### Step 5: Configure URLs

Create URL routing in `your_new_app/urls.py`:

```python
from django.urls import path

from . import views

app_name = 'your_new_app'

urlpatterns = [
    path('api/v1/your-app/endpoint', views.your_view, name='your_endpoint'),
]
```

**URL naming conventions:**
- API endpoints: `/api/v1/your-app/...`
- JSON endpoints: `/json/your-app/...` (uses same patterns as API)
- Admin/internal: `/admin/your-app/...`
- Public pages: `/your-app/...`

### Step 6: Add to INSTALLED_APPS

#### For Core Apps (Production)

Edit `zproject/computed_settings.py`:

```python
# Around line 271
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.staticfiles",
    "confirmation",
    "zerver",
    "social_django",
    "django_scim",
    # ... existing apps ...
    "your_new_app",  # Add your app here ⭐
]
```

#### For Development/Optional Apps

Edit `zproject/dev_settings.py`:

```python
# Around line 79
EXTRA_INSTALLED_APPS = [
    "zilencer",
    "analytics",
    "corporate",
    "zulip_calls_plugin",
    "your_new_app",  # Add your app here ⭐
]
```

#### Using EXTRA_INSTALLED_APPS Pattern (Recommended for Plugins)

In `zproject/default_settings.py`:

```python
EXTRA_INSTALLED_APPS = ["analytics", "zulip_calls_plugin", "your_new_app"]
```

### Step 7: Register URLs

Edit `zproject/urls.py` to include your app's URLs:

#### Method 1: Direct Include (Simple Apps)

```python
from django.urls import include, path

# Around line 983
urlpatterns = [
    # ... existing patterns ...
    path("api/v1/your-app/", include("your_new_app.urls")),
]
```

#### Method 2: Auto-Discovery (For EXTRA_INSTALLED_APPS)

The Zulip codebase automatically includes URLs from apps in `EXTRA_INSTALLED_APPS`:

```python
# Around line 847 in zproject/urls.py
# Include URL configuration files for site-specified extra installed Django apps
for app_name in settings.EXTRA_INSTALLED_APPS:
    app_dir = os.path.join(settings.DEPLOY_ROOT, app_name)
    if os.path.exists(os.path.join(app_dir, "urls.py")):
        urls += [path("", include(f"{app_name}.urls"))]
        i18n_urls += import_string(f"{app_name}.urls.i18n_urlpatterns")
```

If using this pattern, ensure your `urls.py` defines both:

```python
# Regular URLs
urlpatterns = [...]

# i18n URLs (if needed)
i18n_urlpatterns = [...]
```

#### Method 3: Plugin Config Pattern (Advanced)

For complex plugins like `zulip_calls_plugin`:

```python
# In zproject/urls.py
from your_new_app.plugin_config import YourPluginConfig

# Around line 980
urls += YourPluginConfig.get_url_patterns()
```

### Step 8: Create and Apply Migrations

```bash
# Create migrations for your models
python manage.py makemigrations your_new_app

# Review the migration file
cat your_new_app/migrations/0001_initial.py

# Apply migrations
python manage.py migrate your_new_app

# Verify migrations
python manage.py showmigrations your_new_app
```

### Step 9: Restart Development Server

```bash
# Stop the server (Ctrl+C)
# Restart with:
./tools/run-dev
```

---

## URL Configuration

### URL Patterns in Zulip

Zulip uses a specific URL structure:

```python
# In zproject/urls.py

# API endpoints (for programmatic access)
path("api/v1/", include(v1_api_and_json_patterns)),

# JSON endpoints (same patterns, different prefix)
path("json/", include(v1_api_and_json_patterns)),

# User-facing pages (internationalized)
i18n_urls = [...]
urlpatterns = i18n_patterns(*i18n_urls) + urls
```

### Creating API Endpoints

Use Zulip's `rest_path` for REST endpoints:

```python
from zerver.lib.rest import rest_path

# In your_new_app/urls.py
v1_api_and_json_patterns = [
    rest_path("your-app/items", GET=list_items, POST=create_item),
    rest_path("your-app/items/<int:item_id>", GET=get_item, PATCH=update_item, DELETE=delete_item),
]

# Register in main urls.py
# This will create:
# - /api/v1/your-app/items (GET, POST)
# - /json/your-app/items (GET, POST)
# - /api/v1/your-app/items/123 (GET, PATCH, DELETE)
# - /json/your-app/items/123 (GET, PATCH, DELETE)
```

### Example: LMS Integration URLs

```python
# lms_integration/urls.py
from django.urls import path

app_name = 'lms_integration'

urlpatterns = [
    # API endpoints will be defined here
]
```

### Example: Zulip Calls Plugin URLs

```python
# zulip_calls_plugin/urls.py
from django.urls import path
from .views import calls as views

urlpatterns = [
    path('api/v1/calls/initiate', views.initiate_call, name='initiate_call'),
    path('api/v1/calls/respond', views.respond_to_call, name='respond_call'),
    path('api/v1/calls/<uuid:call_id>/status', views.get_call_status, name='call_status'),
]
```

---

## Admin Configuration

Django's admin interface is not heavily used in Zulip's core, but you can configure it for your app.

### Creating Admin Interface

Create `your_new_app/admin.py`:

```python
from django.contrib import admin
from .models import YourModel


@admin.register(YourModel)
class YourModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'realm', 'user', 'created_at']
    list_filter = ['realm', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at']

    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'realm', 'user')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
```

**Note**: Zulip primarily uses custom management commands and API endpoints rather than the Django admin. Most administrative tasks are done through:

1. Management commands (`python manage.py your_command`)
2. API endpoints with admin authentication
3. Server management scripts in `scripts/`

---

## Frontend Integration

### Static Files

Place static files in `your_new_app/static/your_new_app/`:

```
your_new_app/
└── static/
    └── your_new_app/
        ├── js/
        │   └── app.js
        ├── css/
        │   └── styles.css
        └── images/
            └── logo.png
```

In templates:

```html
{% load static %}
<script src="{% static 'your_new_app/js/app.js' %}"></script>
<link rel="stylesheet" href="{% static 'your_new_app/css/styles.css' %}">
```

### Templates

Place templates in `your_new_app/templates/your_new_app/`:

```
your_new_app/
└── templates/
    └── your_new_app/
        ├── base.html
        └── index.html
```

Zulip uses Jinja2 templates. Create your templates:

```jinja2
{# your_new_app/templates/your_new_app/index.html #}
{% extends "zerver/base.html" %}

{% block content %}
<div class="your-app-container">
    <h1>{{ page_title }}</h1>
    <!-- Your content -->
</div>
{% endblock %}
```

### JavaScript Integration

For web frontend integration:

1. **Add JavaScript to Zulip's build system**: Edit `web/src/` if needed
2. **Use API calls**: Call your endpoints from existing Zulip JavaScript
3. **WebSocket events**: Integrate with Zulip's event system

Example JavaScript integration:

```javascript
// In web/src/your_feature.js
import * as channel from "./channel";

export function call_your_api(name, description) {
    return channel.post({
        url: "/api/v1/your-app/endpoint",
        data: {
            name: name,
            description: description,
        },
        success(response) {
            console.log("Success:", response);
        },
        error(xhr) {
            console.error("Error:", xhr);
        },
    });
}
```

### Example: Zulip Calls Plugin Frontend

The Zulip Calls Plugin provides an example of complete frontend integration:

```javascript
// zulip_calls_plugin/static/zulip_calls_plugin/js/calls.js
// Automatically overrides Zulip's call buttons
$(document).ready(function() {
    // Override video/audio call buttons
    $(document).on('click', '.video_link, .audio_link', function(e) {
        e.preventDefault();
        // Call plugin API and open embedded interface
        createEmbeddedCall(recipient_email, is_video);
    });
});
```

---

## Testing Your App

### Backend Tests

Create tests in `your_new_app/tests/`:

```python
# your_new_app/tests/test_views.py
from zerver.lib.test_classes import ZulipTestCase


class YourAppTestCase(ZulipTestCase):
    def test_your_endpoint(self) -> None:
        user = self.example_user("hamlet")

        result = self.client_post(
            "/api/v1/your-app/endpoint",
            {"name": "test", "description": "test description"},
        )

        self.assert_json_success(result)
        data = self.assert_json_success(result)
        self.assertEqual(data["name"], "test")
```

Run tests:

```bash
# Run all tests for your app
./tools/test-backend your_new_app

# Run specific test
./tools/test-backend your_new_app.tests.test_views.YourAppTestCase.test_your_endpoint
```

### API Testing

Test your endpoints with `curl`:

```bash
# Get API key
./manage.py print_api_key hamlet@zulip.com

# Test endpoint
curl -X POST http://localhost:9991/api/v1/your-app/endpoint \
  -u hamlet@zulip.com:API_KEY \
  -d "name=test" \
  -d "description=test description"
```

### Frontend Tests

If you add frontend code, create tests in `web/tests/`:

```javascript
// web/tests/your_app.test.js
test("your_feature", () => {
    // Your frontend tests
});
```

Run frontend tests:

```bash
./tools/test-js-with-node web/tests/your_app.test.js
```

---

## Best Practices

### 1. Follow Zulip's Coding Standards

- **Python**: Follow PEP 8, use Ruff for linting
- **TypeScript/JavaScript**: Use ESLint and Prettier
- **Type hints**: Required for all Python code (mypy)

```bash
# Lint your code
./tools/lint

# Run specific linters
ruff check your_new_app/
mypy your_new_app/
```

### 2. Multi-tenancy

Always link models to `Realm` for proper multi-tenancy:

```python
class YourModel(models.Model):
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    # ... other fields
```

### 3. Database Migrations

- Review migrations before applying
- Test migrations in both directions
- Use descriptive migration names

```bash
# Create migration with custom name
python manage.py makemigrations your_new_app --name add_your_feature

# Test forward migration
python manage.py migrate your_new_app

# Test backward migration
python manage.py migrate your_new_app zero
python manage.py migrate your_new_app
```

### 4. API Design

Follow Zulip's API conventions:

- Use RESTful endpoints
- Return consistent JSON responses
- Include proper error handling
- Document your API (OpenAPI/Swagger)

```python
from zerver.lib.response import json_success, json_error

def your_view(request: HttpRequest, user_profile: UserProfile) -> JsonResponse:
    try:
        # Your logic
        return json_success(request, data={"result": "success"})
    except Exception as e:
        return json_error(request, str(e))
```

### 5. Use Zulip's Event System

Integrate with Zulip's real-time event system:

```python
from zerver.lib.events import send_event

def send_custom_event(user_profile: UserProfile, event_data: dict) -> None:
    event = {
        "type": "your_event_type",
        "data": event_data,
    }
    send_event(user_profile.realm, event, [user_profile.id])
```

### 6. Documentation

Document your app:

- Add docstrings to all functions/classes
- Create a README.md in your app directory
- Update relevant dev-docs

### 7. Modularity

Design your app to be modular:

- Keep dependencies minimal
- Make it easy to enable/disable
- Use plugin patterns when appropriate

---

## Examples

### Example 1: LMS Integration

Location: `/Users/straxs/Work/zulip/lms_integration/`

**Structure:**
```
lms_integration/
├── __init__.py
├── apps.py                  # App config
├── models.py                # (Empty for now)
├── views.py                 # API views
├── urls.py                  # URL routing
├── db_router.py             # Database router
└── migrations/
    └── __init__.py
```

**Configuration:**

`lms_integration/urls.py`:
```python
from django.urls import path

app_name = 'lms_integration'

urlpatterns = [
    # API endpoints will be defined here
]
```

`zproject/urls.py` (line 983):
```python
urls += [path("api/v1/lms/", include("lms_integration.urls"))]
```

`zproject/computed_settings.py` (line 287):
```python
INSTALLED_APPS = [
    # ... existing apps ...
    "lms_integration",
]
```

**Database Configuration (line 413-414):**
```python
# Database routers for LMS integration
DATABASE_ROUTERS = ['lms_integration.db_router.LMSRouter']
```

### Example 2: Zulip Calls Plugin

Location: `/Users/straxs/Work/zulip/zulip_calls_plugin/`

**Structure:**
```
zulip_calls_plugin/
├── __init__.py
├── apps.py                  # App config with ready() method
├── plugin_config.py         # Plugin configuration utilities
├── models/
│   ├── __init__.py
│   └── calls.py             # Call and CallEvent models
├── views/
│   ├── __init__.py
│   └── calls.py             # API view implementations
├── urls.py                  # URL routing
├── migrations/              # Database migrations
├── management/
│   └── commands/
│       ├── install_calls_plugin.py
│       └── uninstall_calls_plugin.py
├── static/
│   └── zulip_calls_plugin/
│       ├── js/
│       └── css/
└── README.md
```

**Configuration:**

`zulip_calls_plugin/apps.py`:
```python
class ZulipCallsPluginConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "zulip_calls_plugin"
    verbose_name = "Zulip Calls Plugin"

    def ready(self) -> None:
        from .plugin_config import CallsPluginConfig
        CallsPluginConfig.apply_settings()
```

`zproject/urls.py` (line 980):
```python
from zulip_calls_plugin.urls import urlpatterns as calls_urls

urls += calls_urls
```

`zproject/dev_settings.py` (line 79):
```python
EXTRA_INSTALLED_APPS = [
    "zilencer",
    "analytics",
    "corporate",
    "zulip_calls_plugin",
]
```

**Key Features:**
- Complete CRUD operations for calls
- WebSocket integration for real-time updates
- Push notifications via FCM
- Frontend JavaScript integration
- Management commands for install/uninstall

---

## Troubleshooting

### App Not Loading

**Problem**: Your app doesn't appear to be loaded.

**Solutions:**
1. Check `INSTALLED_APPS` in `computed_settings.py`
2. Verify app name matches directory name
3. Check `apps.py` configuration
4. Restart the development server

```bash
# Check if app is loaded
python manage.py shell
>>> from django.apps import apps
>>> apps.get_app_config('your_new_app')
```

### URL Not Found (404)

**Problem**: Your endpoint returns 404.

**Solutions:**
1. Check URL patterns are registered in `zproject/urls.py`
2. Verify URL pattern syntax
3. Check for trailing slashes
4. Test URL resolution:

```bash
python manage.py shell
>>> from django.urls import reverse
>>> reverse('your_new_app:your_endpoint')
```

### Migration Errors

**Problem**: Migrations fail to apply.

**Solutions:**
1. Check for circular dependencies
2. Ensure proper database configuration
3. Review migration file for errors
4. Check database permissions

```bash
# Show migration plan
python manage.py showmigrations your_new_app

# Show SQL for migration
python manage.py sqlmigrate your_new_app 0001

# Fake migration if needed (development only)
python manage.py migrate your_new_app 0001 --fake
```

### Import Errors

**Problem**: Cannot import from your app.

**Solutions:**
1. Ensure `__init__.py` exists in all directories
2. Check Python path
3. Verify app is in `INSTALLED_APPS`
4. Check for circular imports

```bash
# Check if app is importable
python manage.py shell
>>> import your_new_app
>>> from your_new_app.models import YourModel
```

---

## Additional Resources

- [Django Documentation](https://docs.djangoproject.com/)
- [Zulip Developer Documentation](https://zulip.readthedocs.io/en/latest/overview/development-overview.html)
- [Zulip API Documentation](https://zulip.com/api/)
- [Zulip Code Style Guide](https://zulip.readthedocs.io/en/latest/contributing/code-style.html)

---

## Checklist

Use this checklist when adding a new Django app:

- [ ] Create app directory with proper structure
- [ ] Create `apps.py` with AppConfig
- [ ] Define models in `models.py`
- [ ] Create views in `views.py`
- [ ] Configure URL routing in `urls.py`
- [ ] Add app to `INSTALLED_APPS` or `EXTRA_INSTALLED_APPS`
- [ ] Register URLs in `zproject/urls.py`
- [ ] Create and apply migrations
- [ ] Write tests
- [ ] Add documentation (README.md)
- [ ] Lint code (`./tools/lint`)
- [ ] Test endpoints with curl
- [ ] Restart development server
- [ ] Verify app loads correctly

---

**Happy coding!**
