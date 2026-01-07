# Simplified JWT Authentication Backend

## Overview

The TestPress JWT authentication backend has been simplified to follow this straightforward flow:

1. **Validate JWT token** with TestPress
2. **Get user profile** from TestPress
3. **Create or update** Zulip user
4. **Done!**

## Code Structure

### Main Authentication Method

```python
def authenticate(self, request, *, testpress_jwt_token=None, realm=None, **kwargs):
    """
    Simple JWT authentication.

    1. Validate JWT token with TestPress
    2. Get user profile from TestPress
    3. Create or update Zulip user
    """
    # Step 1: Validate JWT token with TestPress
    testpress_data = testpress_jwt_validator.validate_token(testpress_jwt_token)

    # Step 2: Get user profile from TestPress data
    user_info = self._get_user_info_from_testpress(testpress_data, realm)

    # Step 3: Create or update Zulip user
    user_profile = self._get_or_create_user(user_info, realm)

    return user_profile
```

### Helper Methods

#### 1. Extract User Info from TestPress

```python
def _get_user_info_from_testpress(self, testpress_data, realm):
    """Extract user info from TestPress data and prepare for Zulip."""
    email = testpress_data.get('email')
    username = testpress_data.get('username')
    first_name = testpress_data.get('first_name', '')
    last_name = testpress_data.get('last_name', '')

    # Build full name
    full_name = f"{first_name} {last_name}".strip() or username

    # Get email (real or placeholder)
    final_email, is_placeholder = validate_and_prepare_email(email, username, realm)

    return {
        'email': final_email,
        'full_name': full_name,
        'username': username,
        'is_active': testpress_data.get('is_active', True),
        'testpress_data': testpress_data
    }
```

#### 2. Find Existing User

```python
def _find_existing_user(self, email, realm):
    """Find existing user by email."""
    return common_get_active_user(email, realm)
```

#### 3. Get or Create User

```python
def _get_or_create_user(self, user_info, realm):
    """Get existing user or create new user."""
    email = user_info["email"]
    full_name = user_info["full_name"]

    # Try to find existing user
    existing_user = self._find_existing_user(email, realm)
    if existing_user:
        # Reactivate if needed
        if not existing_user.is_active and user_info["is_active"]:
            do_reactivate_user(existing_user, acting_user=None)
        return existing_user

    # Create new user
    validated_full_name = check_full_name(full_name, user_profile=None, realm=realm)

    new_user = do_create_user(
        email=email,
        password=None,  # No password for JWT auth
        realm=realm,
        full_name=validated_full_name,
        acting_user=None,
    )

    return new_user
```

## Key Features

### ✅ **Automatic Email Handling**
- **Has email**: Uses real email address
- **No email**: Automatically generates placeholder email (`username@noemail.local`)
- **Zero configuration needed**

### ✅ **Simple User Creation**
- Finds existing user or creates new one
- Handles user reactivation automatically
- Uses TestPress profile data for full name

### ✅ **Error Handling**
- Clear error messages
- Proper logging
- Graceful fallbacks

### ✅ **No Complex Logic**
- Removed retry mechanisms
- Removed complex user lookup strategies
- Removed role mapping complexity
- Simple, readable code

## Usage Examples

### Basic JWT Authentication

```python
# In your view or API endpoint
from lms_integration.auth_backend import TestPressJWTAuthBackend

backend = TestPressJWTAuthBackend()
user = backend.authenticate(
    request=request,
    testpress_jwt_token=token,
    realm=realm
)

if user:
    # User authenticated successfully
    login(request, user)
else:
    # Authentication failed
    return JsonResponse({'error': 'Invalid token'})
```

### Frontend Integration

```javascript
// Send JWT token to Zulip
fetch('/accounts/login/jwt/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        token: testPressJWTToken
    })
})
.then(response => response.json())
.then(data => {
    if (data.result === 'success') {
        // Redirect to Zulip
        window.location.href = '/';
    } else {
        console.error('Login failed:', data.msg);
    }
});
```

## Configuration

### Minimal Required Settings

```python
# Enable JWT authentication
JWT_ENABLED = True

# TestPress API URL
TESTPRESS_API_URL = "https://your-testpress.com/api/"
```

### Optional Settings (for placeholder emails)

```python
# Domain for users without email
LMS_NO_EMAIL_DOMAIN = "students.yourschool.edu"

# Auto-update placeholder emails to real emails
LMS_AUTO_UPDATE_EMAILS = True
```

## TestPress Data Format

The backend expects this data from TestPress:

```json
{
    "id": 123,
    "username": "john_doe",
    "email": "john.doe@school.edu",  // Optional
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true
}
```

## Email Handling Examples

### Student with Email
```
TestPress: {username: "jane_smith", email: "jane@school.edu"}
→ Zulip User: jane@school.edu (real email, gets notifications)
```

### Student without Email
```
TestPress: {username: "bob_wilson", email: null}
→ Zulip User: bob_wilson@noemail.local (placeholder, no email notifications)
```

### Faculty/Staff
```
TestPress: {username: "prof_davis", email: "davis@school.edu"}
→ Zulip User: davis@school.edu (real email, gets notifications)
```

## Error Handling

The backend returns clear error codes:

- `testpress_jwt_missing`: No token provided
- `testpress_jwt_invalid`: Token validation failed
- `testpress_data_invalid`: Invalid user data from TestPress
- `user_creation_failed`: Could not create/update user

## Debugging

### Enable Debug Logging

```python
LOGGING = {
    'loggers': {
        'lms_integration.auth_backend': {
            'level': 'DEBUG',
            'handlers': ['console', 'file'],
        },
    },
}
```

### Test Authentication

```bash
# Test JWT validation
curl -X POST https://your-zulip.com/accounts/login/jwt/ \
  -H "Content-Type: application/json" \
  -d '{"token":"your-jwt-token"}'
```

## Migration from Complex Backend

If you had a complex authentication setup:

1. **Backup existing code**: Save your current auth backend
2. **Deploy simplified version**: The new backend handles all edge cases automatically
3. **Test thoroughly**: Verify JWT authentication works
4. **Remove old complexity**: Delete unused helper methods and complex logic

## Benefits of Simplified Backend

### 🚀 **Easier to Understand**
- Simple 3-step flow
- Clear method names
- Minimal complexity

### 🛠️ **Easier to Maintain**
- Fewer edge cases to handle
- Less code to debug
- Clear error paths

### ⚡ **Better Performance**
- No retry loops
- No complex user lookups
- Faster authentication

### 🔧 **Easier to Extend**
- Add custom logic to simple methods
- Clear places to add features
- No complex inheritance

## Summary

The simplified JWT authentication backend:

1. **Validates tokens** with TestPress API
2. **Extracts user info** from TestPress response
3. **Creates/updates users** in Zulip automatically
4. **Handles emails** (real or placeholder) transparently
5. **Just works!**

No complex configuration, no edge case handling, no retry mechanisms. Just simple, reliable JWT authentication that handles both email and non-email users seamlessly.