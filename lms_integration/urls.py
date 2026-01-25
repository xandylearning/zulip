# LMS Integration URL Configuration
from django.urls import path
from zerver.lib.rest import rest_path

from lms_integration.views import (
    lms_user_webhook,
    lms_users_for_chat,
    # Admin API endpoints
    lms_dashboard_status,
    lms_start_user_sync,
    lms_stop_user_sync,
    lms_get_synced_users,
    lms_get_activity_events,
    lms_poll_activities,
    lms_test_database_connection,
    lms_update_configuration,
    lms_get_logs,
    lms_get_current_config,
    lms_get_sync_history,
    lms_get_batch_groups,
    lms_get_batch_details,
    lms_sync_progress,
    lms_get_active_syncs,
    lms_sync_single_batch,
    # Placeholder email management endpoints
    lms_get_placeholder_users,
    lms_get_placeholder_stats,
    lms_update_user_email,
    lms_bulk_update_emails,
    lms_export_placeholder_users,
    # JWT auth endpoints (no pre-auth required)
    lms_jwt_auth_api,
    lms_jwt_web_login,
)
from lms_integration.views_permissions import (
    get_dm_permissions,
    update_dm_permissions,
)

app_name = 'lms_integration'

urlpatterns = [
    # Webhook endpoint for LMS to notify Zulip when new users are created
    path('webhook/user-created', lms_user_webhook, name='lms_user_webhook'),

    # Admin API endpoints (require realm admin permissions)
    # Use rest_path so they go through rest_dispatch which handles authentication
    # Note: rest_path() doesn't accept 'name' parameter - it gets passed to view functions
    rest_path('admin/dashboard/status', GET=lms_dashboard_status),
    rest_path('admin/users/sync', POST=lms_start_user_sync),
    rest_path('admin/users/sync/stop', POST=lms_stop_user_sync),
    rest_path('admin/users/list', GET=lms_get_synced_users),
    rest_path('admin/sync/history', GET=lms_get_sync_history),
    rest_path('admin/batches/list', GET=lms_get_batch_groups),
    rest_path('admin/batches/<int:batch_id>', GET=lms_get_batch_details),
    rest_path('admin/activities/events', GET=lms_get_activity_events),
    rest_path('admin/activities/poll', POST=lms_poll_activities),
    rest_path('admin/config/test-db', POST=lms_test_database_connection),
    rest_path('admin/config/update', POST=lms_update_configuration),
    rest_path('admin/config/get', GET=lms_get_current_config),
    rest_path('admin/logs', GET=lms_get_logs),
    rest_path('admin/sync/progress', GET=lms_sync_progress),
    rest_path('admin/sync/active', GET=lms_get_active_syncs),
    rest_path('admin/batches/<int:batch_id>/sync', POST=lms_sync_single_batch),

    # Placeholder email management endpoints
    rest_path('admin/users/placeholder', GET=lms_get_placeholder_users),
    rest_path('admin/users/placeholder/stats', GET=lms_get_placeholder_stats),
    rest_path('admin/users/update-email', POST=lms_update_user_email),
    rest_path('admin/users/placeholder/bulk-update', POST=lms_bulk_update_emails),
    rest_path('admin/users/placeholder/export', GET=lms_export_placeholder_users),

    # JWT auth endpoints (API + web login) – deliberately use plain `path`
    # so these do not go through rest_dispatch's auth layer.
    path('auth/jwt', lms_jwt_auth_api),
    path('auth/jwt/login', lms_jwt_web_login),
    
    # DM Permission Matrix endpoints
    rest_path('dm-permissions', GET=get_dm_permissions, PATCH=update_dm_permissions),

    # Users for DM/stream chat (role-filtered; mentor/student only for now)
    rest_path('users/for-chat', GET=lms_users_for_chat),
]
