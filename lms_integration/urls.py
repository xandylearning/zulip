# LMS Integration URL Configuration
from django.urls import path

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
    path('admin/dashboard/status', lms_dashboard_status, name='lms_dashboard_status'),
    path('admin/users/sync', lms_start_user_sync, name='lms_start_user_sync'),
    path('admin/users/list', lms_get_synced_users, name='lms_get_synced_users'),
    path('admin/sync/history', lms_get_sync_history, name='lms_get_sync_history'),
    path('admin/batches/list', lms_get_batch_groups, name='lms_get_batch_groups'),
    path('admin/activities/events', lms_get_activity_events, name='lms_get_activity_events'),
    path('admin/activities/poll', lms_poll_activities, name='lms_poll_activities'),
    path('admin/config/test-db', lms_test_database_connection, name='lms_test_database_connection'),
    path('admin/config/update', lms_update_configuration, name='lms_update_configuration'),
    path('admin/config/get', lms_get_current_config, name='lms_get_current_config'),
    path('admin/logs', lms_get_logs, name='lms_get_logs'),
]
