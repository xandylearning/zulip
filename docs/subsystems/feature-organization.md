# Feature organization

This document explains how to organize new features in the Zulip codebase
to maintain code quality, avoid breaking changes, and follow established
architectural patterns.

## Overview

Zulip follows a modular architecture that separates concerns across different
layers (models, views, business logic, frontend) while keeping related
functionality organized within each layer. When adding new features, follow
these established patterns rather than creating completely separate folder
structures.

## Backend (Django) organization

### Models

Add new database models to `zerver/models/`:

```
zerver/models/your_feature.py
```

- Follow existing naming conventions in other model files
- Import and register your models in `zerver/models/__init__.py`
- Use appropriate field types and relationships
- Add proper `__str__` methods and Meta classes

Example:
```python
# zerver/models/polls.py
from django.db import models
from zerver.models import Realm, UserProfile

class Poll(models.Model):
    realm = models.ForeignKey(Realm, on_delete=models.CASCADE)
    question = models.TextField()
    created_by = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "zerver_poll"

    def __str__(self) -> str:
        return f"Poll: {self.question[:50]}"
```

### API endpoints and views

Add new API endpoints to `zerver/views/`:

```
zerver/views/your_feature.py
```

- Follow RESTful conventions
- Use appropriate decorators (`@require_realm_admin`, `@api_key_only_webhook_view`, etc.)
- Implement proper error handling
- Add comprehensive docstrings for OpenAPI documentation

Example:
```python
# zerver/views/polls.py
from django.http import HttpRequest, HttpResponse
from zerver.decorator import api_key_only_webhook_view
from zerver.lib.response import json_success
from zerver.models import UserProfile

@api_key_only_webhook_view('Poll')
def create_poll(request: HttpRequest, user_profile: UserProfile) -> HttpResponse:
    """Create a new poll."""
    # Implementation here
    return json_success(request)
```

### Business logic

Add core business logic to `zerver/lib/`:

```
zerver/lib/your_feature.py
```

- Keep views thin by moving complex logic here
- Make functions pure and testable where possible
- Handle validation and business rules
- Avoid database queries in lib functions when possible

Example:
```python
# zerver/lib/polls.py
from typing import Dict, List, Any
from zerver.models import Poll, UserProfile

def validate_poll_data(question: str, options: List[str]) -> None:
    """Validate poll creation data."""
    if len(question.strip()) == 0:
        raise ValueError("Poll question cannot be empty")
    if len(options) < 2:
        raise ValueError("Poll must have at least 2 options")

def format_poll_data(poll: Poll) -> Dict[str, Any]:
    """Format poll data for API responses."""
    return {
        'id': poll.id,
        'question': poll.question,
        'created_at': poll.created_at.isoformat(),
    }
```

### Actions

Add high-level operations that modify data to `zerver/actions/`:

```
zerver/actions/your_feature.py
```

- Use this layer for operations that change database state
- Send events for real-time updates
- Handle side effects (notifications, logging, etc.)
- Maintain transactional integrity

Example:
```python
# zerver/actions/polls.py
from typing import Optional
from zerver.lib.events import send_event
from zerver.models import Poll, UserProfile, Realm

def do_create_poll(
    user_profile: UserProfile,
    question: str,
    realm: Optional[Realm] = None,
) -> Poll:
    """Create a poll and send events."""
    if realm is None:
        realm = user_profile.realm

    poll = Poll.objects.create(
        realm=realm,
        question=question,
        created_by=user_profile,
    )

    event = {
        'type': 'poll',
        'op': 'create',
        'poll': format_poll_data(poll),
    }
    send_event(realm, event, [user_profile.id])

    return poll
```

### URL routing

Add URL patterns to the appropriate URL configuration:

```python
# zproject/urls.py or create zerver/urls/your_feature.py
from django.urls import path
from zerver.views.polls import create_poll

urlpatterns = [
    path('api/v1/polls', create_poll),
]
```

## Frontend organization

### TypeScript modules

Create feature modules in `web/src/`:

```
web/src/your_feature.ts          # Core functionality
web/src/your_feature_ui.ts       # UI interactions
web/src/your_feature_data.ts     # Data management
```

- Keep modules focused on specific responsibilities
- Export only what's needed by other modules
- Use TypeScript for type safety
- Follow existing jQuery patterns for DOM manipulation

Example:
```typescript
// web/src/polls.ts
export type Poll = {
    id: number;
    question: string;
    created_at: string;
};

export function create_poll(question: string): void {
    void channel.post({
        url: "/json/polls",
        data: {question},
        success(data) {
            // Handle success
        },
        error(xhr) {
            ui_report.error("Failed to create poll", xhr);
        },
    });
}
```

### Templates

Add Handlebars templates to `web/templates/`:

```
web/templates/your_feature.hbs
web/templates/your_feature_item.hbs
```

### Styles

Add CSS to `web/styles/`:

```
web/styles/your_feature.css
```

- Use existing CSS variables and utility classes
- Follow BEM naming conventions
- Ensure responsive design
- Test accessibility

## Testing strategy

### Backend tests

Create comprehensive test files:

```
zerver/tests/test_your_feature.py
```

- Test all API endpoints
- Test business logic functions
- Test database operations
- Test error conditions

Example:
```python
# zerver/tests/test_polls.py
from zerver.lib.test_classes import ZulipTestCase
from zerver.models import Poll

class PollTest(ZulipTestCase):
    def test_create_poll(self) -> None:
        user = self.example_user("hamlet")
        result = self.api_post(
            user,
            "/api/v1/polls",
            {"question": "What's your favorite color?"}
        )
        self.assert_json_success(result)

        poll = Poll.objects.get(created_by=user)
        self.assertEqual(poll.question, "What's your favorite color?")
```

### Frontend tests

Add frontend tests:

```
web/tests/your_feature.test.js
```

- Test UI interactions
- Test data formatting functions
- Test API call handling
- Use JSDOM for DOM testing

### Integration tests

For complex features, add Puppeteer tests:

```
web/tests/your_feature_puppeteer.test.js
```

## Database migrations

When adding database changes:

1. Create migrations:
   ```bash
   python manage.py makemigrations
   ```

2. Test migrations in both directions:
   ```bash
   ./tools/test-migrations
   ```

3. Consider performance impact on large datasets
4. Add appropriate database indexes
5. Document any manual migration steps needed

## Feature flags

For gradual rollouts, use feature flags in settings:

```python
# zproject/settings.py
ENABLE_POLLS = True

# Or realm-specific setting
# In zerver/models/realms.py
class Realm(models.Model):
    # ...
    enable_polls = models.BooleanField(default=False)
```

## Safe development workflow

1. **Start with tests**: Write tests first to define expected behavior
2. **Implement incrementally**: Build one layer at a time
3. **Run linting continuously**:
   ```bash
   ./tools/lint
   ruff check
   ```
4. **Test thoroughly**:
   ```bash
   ./tools/test-backend zerver.tests.test_your_feature
   ./tools/test-js-with-node web/tests/your_feature.test.js
   ```
5. **Check for regressions**:
   ```bash
   ./tools/test-all
   ```

## Common patterns to follow

### Error handling

- Use `JsonableError` for user-facing errors
- Log errors appropriately with `logging` module
- Provide helpful error messages
- Handle edge cases gracefully

### Internationalization

- Use `gettext` for user-facing strings
- Add translations to `.po` files
- Test with different locales

### Caching

- Use Redis for caching expensive operations
- Follow existing cache key patterns
- Implement cache invalidation properly

### Security

- Validate all user inputs
- Use appropriate permissions checks
- Sanitize data for XSS prevention
- Follow CSRF protection patterns

## Integration with existing systems

### Events system

- Send events for real-time updates
- Follow existing event patterns
- Handle event processing in `zerver/event_listeners.py`

### Notifications

- Integrate with existing notification system
- Support email and push notifications
- Respect user notification preferences

### Mobile apps

- Ensure API compatibility with mobile clients
- Test API changes with mobile app developers
- Follow API versioning guidelines

## Documentation

When adding new features:

1. Update API documentation in docstrings
2. Add user-facing documentation if needed
3. Update this guide if you establish new patterns
4. Document any configuration options

## Example: Adding a polls feature

Here's how you would organize a complete polls feature:

```
# Backend
zerver/models/polls.py           # Poll, PollOption, PollVote models
zerver/views/polls.py            # API endpoints
zerver/lib/polls.py              # Business logic and validation
zerver/actions/polls.py          # Database operations and events
zerver/tests/test_polls.py       # Backend tests

# Frontend
web/src/polls.ts                 # Core polls functionality
web/src/polls_ui.ts              # UI interactions and DOM updates
web/templates/polls/poll.hbs     # Poll display template
web/templates/polls/form.hbs     # Poll creation form
web/styles/polls.css             # Poll-specific styles
web/tests/polls.test.js          # Frontend tests

# Database
zerver/migrations/XXXX_add_polls.py  # Database schema

# Documentation
docs/subsystems/polls.md         # Feature-specific documentation
```

This organization keeps related code together while respecting Zulip's
architectural boundaries and makes it easy for other developers to find
and understand your feature.