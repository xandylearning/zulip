# LMS Integration URL Configuration
from django.urls import path
from zerver.lib.rest import rest_path

from lms_integration.views import (
    lms_user_webhook,
    # Admin API endpoints
    lms_dashboard_status,
    lms_start_user_sync,
    lms_get_synced_users,
    lms_get_activity_events,
    lms_poll_activities,
    lms_test_database_connection,
    lms_update_configuration,
    lms_get_logs,
    lms_get_current_config,
    lms_get_sync_history,
    lms_get_batch_groups,
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
    rest_path('admin/users/list', GET=lms_get_synced_users),
    rest_path('admin/sync/history', GET=lms_get_sync_history),
    rest_path('admin/batches/list', GET=lms_get_batch_groups),
    rest_path('admin/activities/events', GET=lms_get_activity_events),
    rest_path('admin/activities/poll', POST=lms_poll_activities),
    rest_path('admin/config/test-db', POST=lms_test_database_connection),
    rest_path('admin/config/update', POST=lms_update_configuration),
    rest_path('admin/config/get', GET=lms_get_current_config),
    rest_path('admin/logs', GET=lms_get_logs),
]
