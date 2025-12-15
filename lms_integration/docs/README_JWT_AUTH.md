# TestPress JWT Authentication Integration

## Overview

This document describes the TestPress JWT authentication integration that allows users to authenticate to Zulip using JWT tokens from TestPress LMS. The integration provides secure, token-based authentication with automatic user synchronization and comprehensive security measures.

> **⚠️ Important Note**: This integration is currently configured for TestPress LMS. As mentioned in the project requirements, the LMS system may change in the future. The authentication system has been designed with flexibility in mind to accommodate future LMS migrations with minimal code changes. See the [Future LMS Migration](#future-lms-migration) section for details on adaptation strategies.

## Features

✅ **JWT Token Validation**: Validates tokens against TestPress API
✅ **Automatic User Creation**: Creates Zulip users from TestPress data
✅ **User Synchronization**: Updates user profiles from TestPress
✅ **Role Mapping**: Maps TestPress roles to Zulip permissions
✅ **Security Features**: Rate limiting, input validation, security headers
✅ **Caching**: Efficient token validation caching (5-minute TTL)
✅ **Error Handling**: Comprehensive error handling and logging
✅ **Mobile Support**: API endpoints for mobile applications

## API Endpoints

### JWT Authentication (Mobile/API)
```
POST /api/v1/lms/auth/jwt/
Content-Type: application/json

{
    "token": "your-testpress-jwt-token",
    "include_profile": false
}
```

**Response:**
```json
{
    "result": "success",
    "api_key": "user-api-key-for-subsequent-requests",
    "email": "user@example.com",
    "user_id": 123,
    "full_name": "User Name"
}
```

### JWT Web Login
```
POST /api/v1/lms/auth/jwt/login/
Content-Type: application/json

{
    "token": "your-testpress-jwt-token"
}
```

**Response:**
```json
{
    "result": "success",
    "message": "Login successful",
    "user_id": 123,
    "email": "user@example.com",
    "full_name": "User Name",
    "redirect_url": "/"
}
```

## Configuration

### Environment Variables

Add these settings to your Zulip configuration:

```python
# TestPress Integration Settings
TESTPRESS_API_BASE_URL = "https://learn.xandylearning.com/api/v2.5/"
TESTPRESS_TOKEN_CACHE_SECONDS = 300  # 5 minutes
TESTPRESS_REQUEST_TIMEOUT = 10  # 10 seconds
TESTPRESS_JWT_ENABLED = True
```

### Authentication Backend

The TestPress JWT authentication backend is automatically enabled when `TESTPRESS_JWT_ENABLED = True`. It will be added to `AUTHENTICATION_BACKENDS`.

### Rate Limiting

Default rate limits:
- JWT Auth API: 20 attempts per IP per 5 minutes
- JWT Login API: 10 attempts per IP per 5 minutes

## Security Features

### Input Validation
- JWT token format validation
- Request data sanitization
- Suspicious pattern detection (XSS, SQL injection, etc.)

### Rate Limiting
- IP-based rate limiting
- Configurable limits and time windows
- Security event logging

### Security Headers
- `Cache-Control: no-cache, no-store, must-revalidate`
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`

## Architecture

### Components

1. **JWT Validator** (`jwt_validator.py`)
   - Validates tokens against TestPress API
   - Handles caching and error handling
   - Configurable timeouts and retry logic

2. **Authentication Backend** (`auth_backend.py`)
   - Integrates with Django authentication system
   - Creates/updates Zulip user profiles
   - Maps TestPress roles to Zulip roles

3. **User Synchronization** (`user_sync.py`)
   - Syncs user profile data from TestPress
   - Updates names, roles, and custom fields
   - Handles avatar synchronization (optional)

4. **Security Module** (`security.py`)
   - Input validation and sanitization
   - Rate limiting and threat detection
   - Security event logging

5. **API Views** (`views.py`)
   - JWT authentication endpoints
   - Error handling and response formatting
   - Security header management

## User Flow

### Mobile App Integration
1. User logs into your main app
2. App obtains JWT token from TestPress
3. App calls `/api/v1/lms/auth/jwt/` with token
4. Zulip validates token with TestPress API
5. Zulip returns API key for subsequent requests

### Web Application Integration
1. User logs into your main app
2. App obtains JWT token from TestPress
3. App calls `/api/v1/lms/auth/jwt/login/` with token
4. Zulip creates web session for user
5. User is redirected to Zulip interface

## Error Handling

### Common Error Responses

- `400 Bad Request`: Invalid token format or request data
- `401 Unauthorized`: Invalid or expired JWT token
- `403 Forbidden`: User account inactive or invalid
- `429 Too Many Requests`: Rate limit exceeded
- `500 Internal Server Error`: Server-side errors
- `503 Service Unavailable`: TestPress API unavailable

## Monitoring and Logging

### Security Events Logged
- Invalid JWT tokens
- Suspicious request patterns
- Rate limit violations
- Authentication failures
- User creation/updates

### Log Levels
- `INFO`: Successful authentications, user operations
- `WARNING`: Failed authentications, suspicious activity
- `ERROR`: System errors, API failures

## Testing

### Manual Testing

1. **Token Validation**:
   ```bash
   curl -X POST http://localhost:9991/api/v1/lms/auth/jwt/ \
   -H "Content-Type: application/json" \
   -d '{"token": "valid-testpress-jwt"}'
   ```

2. **Security Testing**:
   ```bash
   # Test invalid token
   curl -X POST http://localhost:9991/api/v1/lms/auth/jwt/ \
   -H "Content-Type: application/json" \
   -d '{"token": "invalid-token"}'
   ```

3. **Rate Limiting**:
   ```bash
   # Send multiple requests quickly
   for i in {1..25}; do
     curl -X POST http://localhost:9991/api/v1/lms/auth/jwt/ \
     -H "Content-Type: application/json" \
     -d '{"token": "test-token"}' &
   done
   ```

## Deployment Checklist

- [ ] Configure TestPress API base URL
- [ ] Test JWT token validation with real tokens
- [ ] Verify user creation and synchronization
- [ ] Test rate limiting configuration
- [ ] Set up monitoring and alerting
- [ ] Configure log retention and rotation
- [ ] Test mobile app integration
- [ ] Verify security headers
- [ ] Test error handling scenarios
- [ ] Document any custom role mappings

## Troubleshooting

### Common Issues

1. **"Invalid JWT token format"**
   - Check token structure (should have 3 parts separated by dots)
   - Verify token is not expired
   - Check for suspicious characters

2. **"Error validating token with TestPress"**
   - Verify TestPress API URL is correct
   - Check network connectivity
   - Verify TestPress API is responding

3. **"Too many authentication attempts"**
   - Rate limit exceeded
   - Wait for rate limit window to reset
   - Check for automated attacks

4. **User not created**
   - Check TestPress user data completeness
   - Verify email is valid and allowed for realm
   - Check user is active in TestPress

## Future LMS Migration

As stated in the project requirements, this integration may need to be adapted for different LMS systems in the future. The architecture has been designed with this flexibility in mind.

### Migration Strategy

The current TestPress integration can be adapted to other LMS systems with the following approach:

#### 1. **JWT Validator Replacement** (`jwt_validator.py`)
- Update `api_base_url` to point to new LMS API
- Modify authentication endpoint (currently `/me`)
- Adjust request headers format if needed
- Update user data parsing logic

#### 2. **Authentication Backend Adaptation** (`auth_backend.py`)
- Update `_extract_user_info_from_testpress_data()` method name and logic
- Modify `_determine_user_role()` for new LMS role mapping
- Adjust user field mappings in `_get_or_create_user()`

#### 3. **Settings Configuration** (`computed_settings.py`)
- Update `TESTPRESS_*` settings to new LMS equivalents
- Change `TestPressJWTAuthBackend` class path if renamed
- Add new LMS-specific configuration options

#### 4. **API Views Updates** (`views.py`)
- Update function names and documentation
- Modify error handling messages
- Adjust validation logic if token format differs

### Migration Steps for New LMS

1. **Create LMS-specific modules**:
   ```
   lms_integration/
   ├── backends/
   │   ├── testpress_backend.py  (current implementation)
   │   └── new_lms_backend.py    (new LMS implementation)
   ├── validators/
   │   ├── testpress_validator.py (current implementation)
   │   └── new_lms_validator.py   (new LMS implementation)
   ```

2. **Add configuration switching**:
   ```python
   LMS_PROVIDER = get_config("lms", "provider", "testpress")  # testpress, moodle, canvas, etc.
   ```

3. **Implement factory pattern**:
   ```python
   def get_lms_backend():
       if LMS_PROVIDER == "testpress":
           return TestPressJWTAuthBackend()
       elif LMS_PROVIDER == "moodle":
           return MoodleJWTAuthBackend()
       # etc.
   ```

### Common LMS Integration Patterns

Most modern LMS systems support similar authentication patterns that this integration can adapt to:

- **Moodle**: JWT tokens via `/webservice/rest/server.php`
- **Canvas**: OAuth2 tokens via `/api/v1/users/self`
- **Blackboard**: REST API via `/learn/api/public/v1/users`
- **Schoology**: OAuth tokens via `/v1/users/me`

### Backward Compatibility

During migration:
- Keep TestPress backend active alongside new LMS backend
- Use feature flags to gradually migrate users
- Maintain dual authentication support during transition
- Preserve user data and session continuity

### Testing New LMS Integration

1. **Create test endpoints**:
   ```
   /api/v1/lms/auth/jwt/test-new-lms/
   ```

2. **Parallel validation**:
   - Validate tokens against both old and new LMS
   - Compare user data consistency
   - Test role mapping accuracy

3. **Gradual rollout**:
   - Enable new LMS for test users first
   - Monitor authentication success rates
   - Fallback to old LMS if issues occur

## Future Enhancements

- [ ] Support for multiple LMS systems simultaneously
- [ ] LMS provider factory pattern implementation
- [ ] Advanced role mapping configuration UI
- [ ] Avatar synchronization from multiple LMS sources
- [ ] Custom profile field mapping per LMS
- [ ] JWT token refresh handling
- [ ] Real-time user synchronization webhooks
- [ ] LMS migration tools and utilities