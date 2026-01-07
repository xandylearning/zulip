# JWT Authentication for LMS Integration

## Overview

The JWT authentication system allows LMS users to seamlessly authenticate with Zulip using TestPress JWT tokens. When a JWT token is provided, the system:

1. Validates the JWT token with TestPress
2. Extracts user profile information
3. Creates or updates the Zulip user
4. Handles users with or without email addresses

## Simple Flow

```
JWT Token → Validate with TestPress → Get User Profile → Create/Update Zulip User → Login
```

## Configuration

### Enable JWT Authentication

1. Go to **Organization settings** → **LMS Integration** → **Configuration**
2. Check **"Enable JWT Authentication"**
3. Set **TestPress API Base URL** (e.g., `https://your-testpress.com/api/`)
4. Save configuration

### Environment Setup

The system automatically handles user creation with these rules:

- **Has email**: Uses the real email address
- **No email**: Generates placeholder email using username (e.g., `username@noemail.local`)
- **Auto-sync**: User profile synced from TestPress data

## Authentication Process

### 1. Client Sends JWT Token

The client (web app, mobile app) sends a request with the JWT token:

```javascript
// Frontend example
fetch('/accounts/login/jwt/', {
    method: 'POST',
    headers: {
        'Content-Type': 'application/json',
    },
    body: JSON.stringify({
        token: 'your-jwt-token-here'
    })
});
```

### 2. Backend Validates Token

```python
# The backend automatically:
# 1. Validates JWT with TestPress
# 2. Extracts user profile
# 3. Creates/updates user
# 4. Returns authenticated user
```

### 3. User Profile Creation

Based on TestPress data, the system creates a Zulip user:

```json
// TestPress profile data
{
    "id": 123,
    "username": "john_doe",
    "email": "john.doe@school.edu",  // Optional
    "first_name": "John",
    "last_name": "Doe",
    "is_active": true
}
```

Creates Zulip user:
- **Username**: john_doe
- **Email**: john.doe@school.edu (or john_doe@noemail.local if no email)
- **Full Name**: John Doe
- **Active**: Based on TestPress status

## User Types and Email Handling

### Students with Email
```json
TestPress Data: {
    "username": "jane_smith",
    "email": "jane.smith@school.edu",
    "first_name": "Jane",
    "last_name": "Smith"
}

Zulip User Created:
- Email: jane.smith@school.edu
- Can receive email notifications
- Full Zulip functionality
```

### Students without Email
```json
TestPress Data: {
    "username": "bob_wilson",
    "email": null,
    "first_name": "Bob",
    "last_name": "Wilson"
}

Zulip User Created:
- Email: bob_wilson@noemail.local (placeholder)
- No email notifications (blocked automatically)
- Full Zulip functionality except email
```

### Faculty/Mentors
```json
TestPress Data: {
    "username": "prof_davis",
    "email": "prof.davis@school.edu",
    "first_name": "Professor",
    "last_name": "Davis"
}

Zulip User Created:
- Email: prof.davis@school.edu
- Role: Mentor/Moderator (based on configuration)
- Full permissions
```

## API Endpoints

### JWT Login Endpoint

```
POST /accounts/login/jwt/
```

**Request Body:**
```json
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Success Response (200):**
```json
{
    "result": "success",
    "user_id": 123,
    "email": "user@school.edu",
    "full_name": "User Name",
    "is_placeholder_email": false
}
```

**Error Response (400):**
```json
{
    "result": "error",
    "msg": "Invalid JWT token"
}
```

### Token Validation

The system validates tokens by:
1. Checking JWT signature
2. Verifying expiration
3. Validating with TestPress API
4. Extracting user profile data

## Frontend Integration Examples

### JavaScript/React

```javascript
class TestPressAuth {
    static async loginWithJWT(token) {
        try {
            const response = await fetch('/accounts/login/jwt/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': getCSRFToken(),
                },
                body: JSON.stringify({ token })
            });

            if (response.ok) {
                const data = await response.json();
                console.log('Login successful:', data);
                // Redirect to Zulip main interface
                window.location.href = '/';
            } else {
                const error = await response.json();
                console.error('Login failed:', error.msg);
            }
        } catch (error) {
            console.error('Network error:', error);
        }
    }
}

// Usage
TestPressAuth.loginWithJWT(userJWTToken);
```

### Mobile App (React Native)

```javascript
export const authenticateWithTestPress = async (jwtToken) => {
    try {
        const response = await fetch(`${ZULIP_BASE_URL}/accounts/login/jwt/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                token: jwtToken
            }),
        });

        const data = await response.json();

        if (data.result === 'success') {
            // Store user session
            await AsyncStorage.setItem('zulip_user_id', data.user_id.toString());
            await AsyncStorage.setItem('zulip_email', data.email);
            return data;
        } else {
            throw new Error(data.msg);
        }
    } catch (error) {
        console.error('Authentication failed:', error);
        throw error;
    }
};
```

### URL-based Authentication

For web applications, you can also pass the JWT token as a URL parameter:

```
https://your-zulip.com/accounts/login/jwt/?token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

## Security Considerations

### Token Validation
- JWT signature verified
- Token expiration checked
- TestPress API validation
- User status validation

### User Creation Security
- Usernames sanitized for email compatibility
- Domain restrictions honored
- Role assignment based on configuration
- No password stored (managed by LMS)

### Session Management
- Standard Zulip session handling
- Logout invalidates session
- Token refresh handled by client

## Troubleshooting

### Common Issues

#### "Invalid JWT token"
- **Cause**: Token expired or malformed
- **Solution**: Generate new token from TestPress

#### "User creation failed"
- **Cause**: Username conflicts or invalid data
- **Solution**: Check TestPress user data format

#### "TestPress API unreachable"
- **Cause**: Network issues or wrong API URL
- **Solution**: Verify TestPress API base URL in settings

#### "User has no username"
- **Cause**: TestPress profile missing username
- **Solution**: Ensure TestPress provides username in JWT

### Debug Mode

Enable debug logging in settings:

```python
LOGGING = {
    'loggers': {
        'lms_integration.auth_backend': {
            'level': 'DEBUG',
            'handlers': ['file'],
        },
    },
}
```

### Testing Authentication

#### Test JWT Token Validation

```bash
# Test with curl
curl -X POST https://your-zulip.com/accounts/login/jwt/ \
  -H "Content-Type: application/json" \
  -d '{"token":"your-test-token"}'
```

#### Test in Django Shell

```python
from lms_integration.auth_backend import TestPressJWTAuthBackend
from zerver.models import get_realm

backend = TestPressJWTAuthBackend()
realm = get_realm("your-realm")

# Test authentication
user = backend.authenticate(
    request=None,
    testpress_jwt_token="your-test-token",
    realm=realm
)

print(f"Authenticated user: {user}")
```

## Configuration Reference

### Required Settings

```python
# Enable JWT authentication
JWT_ENABLED = True

# TestPress API configuration
TESTPRESS_API_URL = "https://your-testpress.com/api/"

# Placeholder email domain (for users without email)
LMS_NO_EMAIL_DOMAIN = "noemail.local"

# Auto-update emails when real emails become available
LMS_AUTO_UPDATE_EMAILS = True
```

### Optional Settings

```python
# Custom placeholder email prefix/suffix
LMS_PLACEHOLDER_EMAIL_PREFIX = "student_"
LMS_PLACEHOLDER_EMAIL_SUFFIX = "_temp"

# Notification settings for placeholder emails
LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS = {
    'email_delivery': False,
    'in_app_notifications': True,
    'log_attempts': True,
}
```

## Migration from Password-based Auth

If migrating from password-based authentication:

1. **Enable JWT**: Turn on JWT authentication in settings
2. **Test with sample users**: Verify JWT flow works
3. **Update client applications**: Implement JWT token handling
4. **Gradual rollout**: Enable for specific user groups first
5. **Monitor logs**: Watch for authentication errors

## Best Practices

### Client-side
- **Secure token storage**: Don't store JWT in localStorage
- **Token refresh**: Implement token refresh mechanism
- **Error handling**: Gracefully handle authentication failures
- **HTTPS only**: Never send tokens over HTTP

### Server-side
- **Regular testing**: Test JWT validation regularly
- **Monitor failed attempts**: Watch for authentication attacks
- **User data validation**: Validate all TestPress profile data
- **Audit logging**: Log all authentication attempts

## Support

For JWT authentication issues:

1. **Check TestPress connectivity**: Verify API URL and access
2. **Validate token format**: Ensure JWT is properly formatted
3. **Review logs**: Check authentication logs for errors
4. **Test with sample token**: Use known-good token for testing

The JWT authentication system provides seamless integration between TestPress and Zulip, automatically handling user creation and profile synchronization while supporting both email and non-email users.