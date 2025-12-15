# LMS Integration Admin Interface Fixes

This document describes the fixes applied to resolve issues with the LMS Integration admin interface.

## Issues Fixed

### 1. Missing `user_profile` Parameter Error

**Problem:**
```
TypeError: lms_dashboard_status() missing 1 required positional argument: 'user_profile'
TypeError: lms_get_current_config() missing 1 required positional argument: 'user_profile'
```

**Root Cause:**
The LMS admin endpoints were registered using Django's `path()` function instead of Zulip's `rest_path()` function. This meant they didn't go through Zulip's `rest_dispatch` middleware, which is responsible for:
- Extracting `user_profile` from the request (either from session cookies or API key)
- Applying authentication decorators
- Handling CSRF protection

**Solution:**
Changed all admin endpoint registrations in `lms_integration/urls.py` from `path()` to `rest_path()` with appropriate HTTP methods:

```python
# Before
path('admin/dashboard/status', lms_dashboard_status, name='lms_dashboard_status'),

# After
rest_path('admin/dashboard/status', GET=lms_dashboard_status, name='lms_dashboard_status'),
```

**Files Modified:**
- `lms_integration/urls.py`: Changed all admin endpoints to use `rest_path()` with HTTP methods

---

### 2. Password Prompt for Logged-In Administrators

**Problem:**
Even when logged in as an administrator/owner, accessing the LMS Integration admin panel prompted for a password.

**Root Cause:**
After switching to `rest_path()`, endpoints under `/api/v1/` require HTTP Basic Auth (API key authentication), while the web UI uses session cookie authentication. The frontend was calling `/api/v1/lms/...` endpoints, which require API key auth, but the user was authenticated via session cookies.

**Solution:**
1. Changed all frontend API calls from `/api/v1/lms/...` to `/json/lms/...` in `settings_lms_integration.ts`
2. Registered LMS URLs for both `/api/v1/` and `/json/` paths in `zproject/urls.py`

**Files Modified:**
- `web/src/settings_lms_integration.ts`: Changed all API URLs from `/api/v1/lms/` to `/json/lms/`
- `zproject/urls.py`: Added `/json/lms/` URL registration alongside `/api/v1/lms/`

**Note:** The endpoints now work with both authentication methods:
- Session authentication (cookies) via `/json/lms/...` for web UI
- API key authentication via `/api/v1/lms/...` for external API clients

---

### 3. UI Theme and Styling Issues

**Problem:**
- UI elements didn't match Zulip's theme (dark/light mode)
- Status badge displayed incorrectly (showing as a horizontal bar instead of a pill)
- Tabs displayed as a sidebar instead of horizontal tabs
- Webhook endpoint URL field was squeezed/narrow

**Root Cause:**
- Inline styles in the Handlebars template used hardcoded colors
- CSS wasn't using Zulip's CSS variables for theming
- Missing proper flexbox layout for tabs
- Endpoint URL field lacked proper width constraints

**Solution:**

#### 3.1 Created Dedicated CSS File
- Created `web/styles/lms_integration.css` with all LMS integration styles
- Migrated inline styles from `lms_integration_admin.hbs` to the CSS file
- Used Zulip's CSS variables for consistent theming:
  - `var(--color-text-default)` for text
  - `var(--color-background)` for backgrounds
  - `var(--color-text-link)` for links
  - `hsl(0deg 0% 80%)` for borders (matching Zulip's pattern)

#### 3.2 Fixed Status Badge Display
- Added proper `display: inline-block` and reset inline styles after loading indicator
- Fixed `update_status_badge()` function to properly restore badge structure after loading
- Set appropriate `border-radius` for pill shape

#### 3.3 Fixed Tab Display
- Added `display: flex` to `.nav-tabs` for horizontal layout
- Removed list styling (`list-style: none`, `padding: 0`)
- Added proper `display: none/block` for tab panes
- Fixed active tab border styling

#### 3.4 Fixed Webhook Endpoint URL Field
- Added `width: 100%` and `max-width: 100%` to container
- Set `flex: 1 1 auto` and `min-width: 0` on code element
- Added `white-space: pre-wrap` for proper URL wrapping
- Made button `flex-shrink: 0` to prevent compression

**Files Modified:**
- `web/templates/settings/lms_integration_admin.hbs`: Removed inline `<style>` block
- `web/styles/lms_integration.css`: Created new CSS file with all styles
- `web/src/bundles/app.ts`: Added import for `lms_integration.css`
- `web/src/settings_lms_integration.ts`: Fixed `update_status_badge()` function

---

### 4. Handlebars Template Errors

**Problem:**
```
"lms_db_host" not defined in [object Object]
"webhook_endpoint_url" not defined in [object Object]
```

**Root Cause:**
Zulip uses Handlebars in strict mode, which throws errors when accessing undefined properties. The template was trying to access LMS configuration variables before they were defined in the context.

**Solution:**
Added default values for all LMS integration configuration fields in `admin.ts` before rendering the template:

```typescript
// LMS Integration default values
lms_enabled: false,
lms_db_host: "",
lms_db_port: 5432,
lms_db_name: "",
lms_db_username: "",
testpress_api_url: "",
poll_interval: 60,
jwt_enabled: false,
activity_monitor_enabled: false,
notify_mentors: false,
webhook_endpoint_url: "",
```

**Files Modified:**
- `web/src/admin.ts`: Added default values for LMS integration settings

---

### 5. Unknown Section Error

**Problem:**
```
BlueslipError: Unknown section lms-integration
```

**Root Cause:**
The "lms-integration" section wasn't registered in Zulip's settings section management system.

**Solution:**
Registered the section in `settings_sections.ts`:

```typescript
import * as settings_lms_integration from "./settings_lms_integration.ts";

// In initialize()
load_func_dict.set("lms-integration", settings_lms_integration.set_up);

// In reset_sections()
settings_lms_integration.reset();
```

**Files Modified:**
- `web/src/settings_sections.ts`: Added registration for "lms-integration" section
- `web/src/settings_lms_integration.ts`: Added `set_up()` and `reset()` functions

---

## Testing Checklist

After applying these fixes, verify:

1. ✅ No password prompt appears when accessing LMS Integration settings
2. ✅ Dashboard loads without errors
3. ✅ Status badge displays correctly as a pill shape
4. ✅ Tabs display horizontally at the top
5. ✅ Webhook endpoint URL field uses full width
6. ✅ UI matches Zulip's theme (light/dark mode)
7. ✅ All API endpoints respond correctly
8. ✅ No console errors in browser developer tools

## URL Structure

The LMS Integration endpoints are now accessible via two paths:

- **Web UI (Session Auth):** `/json/lms/admin/...`
- **API Clients (API Key Auth):** `/api/v1/lms/admin/...`

Both paths use the same view functions and are registered via `rest_path()` to ensure proper authentication handling.

## Known Warnings

There is a Django warning about URL namespace not being unique:
```
WARNINGS:
?: (urls.W005) URL namespace 'lms_integration' isn't unique. You may not be able to reverse all URLs in this namespace
```

This is expected because we register the same URLs twice (once for `/api/v1/` and once for `/json/`). This doesn't affect functionality, as URL reversal works correctly when the full path is used.

## Related Files

- `lms_integration/urls.py` - URL routing configuration
- `lms_integration/views.py` - View functions
- `web/src/settings_lms_integration.ts` - Frontend JavaScript
- `web/templates/settings/lms_integration_admin.hbs` - Handlebars template
- `web/styles/lms_integration.css` - CSS styles
- `web/src/admin.ts` - Admin page initialization
- `web/src/settings_sections.ts` - Settings section registration
- `zproject/urls.py` - Main URL configuration

