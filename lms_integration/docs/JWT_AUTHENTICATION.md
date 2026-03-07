# JWT Authentication for LMS Integration

## Overview

The JWT authentication system allows LMS users to seamlessly authenticate with Zulip using TestPress JWT tokens. When a JWT token is provided, the system:

1. **Decodes JWT token** to extract user ID (no API call needed)
2. **Queries LMS database first** (fast, local database lookup)
3. **Falls back to TestPress API** only if user not found in LMS DB
4. Extracts user profile information
5. Creates or updates the Zulip user
6. Handles users with or without email addresses

## Optimized Flow

```
JWT Token → Decode JWT (extract user ID) → Query LMS Database → [Found? Return user data] 
                                                                    ↓ [Not found]
                                                          Fallback to TestPress API
                                                                    ↓
                                            Get User Profile → Create/Update Zulip User → Login
```

**Key Benefits:**
- ⚡ **Faster authentication** - Local database query instead of API call
- 🔄 **Reduced API load** - Only calls TestPress when necessary
- 🛡️ **Better reliability** - Works even if TestPress API is temporarily unavailable
- 💾 **Efficient caching** - Results cached for 5 minutes

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
# 1. Decodes JWT to extract user ID (no API call)
# 2. Queries LMS database first (fast, local)
# 3. Falls back to TestPress API only if user not found
# 4. Extracts user profile
# 5. Creates/updates user
# 6. Returns authenticated user
```

**Performance Optimization:**
- Most requests are served from the local LMS database (milliseconds)
- TestPress API is only called as a fallback (when user not in LMS DB)
- Results are cached for 5 minutes to reduce database queries

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

The LMS integration exposes two JWT endpoints (see `lms_integration/urls.py`). Both are mounted under the LMS API prefix:

- **`/api/v1/lms/auth/jwt`** — get a Zulip API key (for mobile apps, bots, API clients)
- **`/api/v1/lms/auth/jwt/login`** — create a web session (for browser-based login)

The same paths are also available under **`/json/lms/`** (e.g. `/json/lms/auth/jwt`, `/json/lms/auth/jwt/login`). Realm is inferred from the request (e.g. subdomain). No prior Zulip authentication is required; these endpoints use plain `path()` and do not go through `rest_dispatch` auth.

---

### 1. JWT Auth API — Get API key

**Use case:** Mobile apps, API clients, or bots that need a Zulip API key to call the Zulip API. The client exchanges an LMS JWT for a Zulip API key and then uses that key for subsequent requests.

```
POST /api/v1/lms/auth/jwt
POST /json/lms/auth/jwt
```

**Request Body:**
```json
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "include_profile": false
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string | Yes | LMS/TestPress JWT token |
| `include_profile` | boolean | No | If `true`, response includes `role`. Default `false`. |

**Success Response (200):**
```json
{
    "result": "success",
    "msg": "",
    "api_key": "your-zulip-api-key",
    "email": "user@school.edu",
    "user_id": 123,
    "full_name": "User Name"
}
```

Optionally with `include_profile: true`:
```json
{
    "result": "success",
    "msg": "",
    "api_key": "your-zulip-api-key",
    "email": "user@school.edu",
    "user_id": 123,
    "full_name": "User Name",
    "role": 400
}
```

**Error Response (400):**
```json
{
    "result": "error",
    "msg": "JWT authentication failed"
}
```

Other errors (e.g. missing token, malformed JSON) return appropriate `msg` values.

---

### 2. JWT Web Login — Create session (browser)

**Use case:** Web app login. The client sends the LMS JWT; the server creates a Django session (sets session cookie) and returns success plus a redirect URL. The browser then redirects to Zulip with an active session.

```
POST /api/v1/lms/auth/jwt/login
POST /json/lms/auth/jwt/login
```

**Request Body:**
```json
{
    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `token` | string | Yes | LMS/TestPress JWT token |

**Success Response (200):**
```json
{
    "result": "success",
    "msg": "",
    "message": "Login successful",
    "user_id": 123,
    "email": "user@school.edu",
    "full_name": "User Name",
    "redirect_url": "/"
}
```

The response includes a `Set-Cookie` header for the session. The client should redirect the user to `redirect_url` (typically `/`) to load the Zulip web app.

**Error Response (400):**
```json
{
    "result": "error",
    "msg": "JWT authentication failed"
}
```

---

### Legacy / generic JWT login reference

Some setups may use a single generic JWT login endpoint (e.g. `POST /accounts/login/jwt/`) that returns user info and/or sets a session. The LMS integration uses the two endpoints above instead: use **`auth/jwt`** for API key and **`auth/jwt/login`** for web login.

### Token Validation

The system validates tokens using an optimized two-step process:

1. **JWT Decoding** (No API call)
   - Decodes JWT token to extract user ID
   - No signature verification needed (validated by LMS when issued)
   - Fast, local operation

2. **LMS Database Lookup** (Primary method)
   - Queries local LMS database using extracted user ID
   - Returns user data in TestPress API format
   - Fast, reliable, works offline

3. **TestPress API Fallback** (Only if needed)
   - Only called if user not found in LMS database
   - Validates token signature and expiration
   - Extracts user profile data from API response

4. **Caching**
   - Results cached for 5 minutes
   - Reduces database queries and API calls
   - Improves response time for repeated requests

## Frontend Integration Examples

### Web app — session login (`auth/jwt/login`)

Use **`POST /api/v1/lms/auth/jwt/login`** (or `/json/lms/auth/jwt/login`) when the user logs in from a browser. The server sets a session cookie; then redirect to `redirect_url`.

```javascript
const ZULIP_BASE = 'https://your-zulip.example.com';

async function loginWithJWT(token) {
    const response = await fetch(`${ZULIP_BASE}/api/v1/lms/auth/jwt/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',  // send and store cookies
        body: JSON.stringify({ token }),
    });

    const data = await response.json();
    if (data.result !== 'success') {
        throw new Error(data.msg || 'JWT authentication failed');
    }
    // Session cookie is set; redirect to Zulip
    window.location.href = data.redirect_url || '/';
}

// Usage
loginWithJWT(userJWTToken);
```

### Mobile / API client — get API key (`auth/jwt`)

Use **`POST /api/v1/lms/auth/jwt`** when you need a Zulip API key (e.g. mobile app or bot). Store the returned `api_key` and use it for Zulip API requests.

```javascript
const ZULIP_BASE = 'https://your-zulip.example.com';

async function getZulipApiKey(jwtToken) {
    const response = await fetch(`${ZULIP_BASE}/api/v1/lms/auth/jwt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            token: jwtToken,
            include_profile: true,  // optional: get role in response
        }),
    });

    const data = await response.json();
    if (data.result !== 'success') {
        throw new Error(data.msg || 'JWT authentication failed');
    }
    return {
        apiKey: data.api_key,
        email: data.email,
        userId: data.user_id,
        fullName: data.full_name,
        role: data.role,
    };
}

// Usage: store apiKey and use for Zulip API calls
const { apiKey, email, userId } = await getZulipApiKey(lmsJwtToken);
// e.g. pass apiKey to Zulip SDK or use in Authorization header
```

### React Native example (API key)

```javascript
export const authenticateWithLMS = async (jwtToken) => {
    const response = await fetch(`${ZULIP_BASE_URL}/api/v1/lms/auth/jwt`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: jwtToken }),
    });

    const data = await response.json();
    if (data.result !== 'success') {
        throw new Error(data.msg || 'JWT authentication failed');
    }
    await AsyncStorage.setItem('zulip_api_key', data.api_key);
    await AsyncStorage.setItem('zulip_user_id', String(data.user_id));
    await AsyncStorage.setItem('zulip_email', data.email);
    return data;
};
```

### URL-based authentication

The LMS integration endpoints expect a **POST** body with `token`. Passing the JWT as a URL query parameter is not supported for `/api/v1/lms/auth/jwt` or `/api/v1/lms/auth/jwt/login`. Implement a small redirector that reads `?token=...` and POSTs it to `auth/jwt/login` if you need link-based login.

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
- **Note**: Authentication will still work if user exists in LMS database (API is only a fallback)

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

#### Test JWT token (API key)

```bash
curl -X POST https://your-zulip.com/api/v1/lms/auth/jwt \
  -H "Content-Type: application/json" \
  -d '{"token":"your-test-token"}'
```

#### Test JWT web login

```bash
curl -X POST https://your-zulip.com/api/v1/lms/auth/jwt/login \
  -H "Content-Type: application/json" \
  -d '{"token":"your-test-token"}' \
  -c cookies.txt -v
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