"""
LMS Integration API Views
REST API endpoints for LMS integration, including webhook for new user creation.
"""

import logging
import json
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

from django.conf import settings
from django.contrib.auth import authenticate
from django.contrib.auth.models import User
from django.core.paginator import Paginator
from django.db import connections, DatabaseError, models
from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from pydantic import Json

from zerver.context_processors import get_valid_realm_from_request
from zerver.decorator import require_realm_admin, require_post, do_login
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models import UserProfile, Realm

from lms_integration.lib.user_sync import UserSync
from lms_integration.lib.activity_monitor import ActivityMonitor
from lms_integration.models import (
    Students,
    Mentors,
    Batches,
    Coursebatch,
    Batchtostudent,
    Mentortostudent,
    LMSActivityEvent,
    LMSEventLog,
    LMSIntegrationConfig,
    LMSSyncHistory,
    LMSAdminLog,
    LMSUserMapping,
    LMSSyncProgress,
)

logger = logging.getLogger(__name__)

# Track running sync threads for cancellation
# Maps sync_id -> (thread, progress_tracker, sync_history)
_running_syncs: Dict[str, tuple] = {}
_sync_lock = threading.Lock()


# ===================================
# UTILITY FUNCTIONS
# ===================================

def log_admin_action(
    realm: Realm,
    level: str,
    source: str,
    message: str,
    user: Optional[UserProfile] = None,
    details: Optional[Dict[str, Any]] = None,
    exception: Optional[Exception] = None,
) -> None:
    """Log admin actions for audit and debugging."""
    try:
        log_entry = LMSAdminLog(
            realm=realm,
            level=level,
            source=source,
            message=message,
            user=user,
            details=details,
        )

        if exception:
            log_entry.exception_type = exception.__class__.__name__
            log_entry.stack_trace = str(exception)

        log_entry.save()

        # Also log to Django logger
        getattr(logger, level.lower(), logger.info)(f"[{source}] {message}")

    except Exception as e:
        # Fallback to regular logging if database logging fails
        logger.error(f"Failed to save admin log: {e}")
        logger.log(getattr(logging, level, logging.INFO), f"[{source}] {message}")


def get_or_create_lms_config(realm: Realm) -> LMSIntegrationConfig:
    """Get or create LMS configuration for a realm."""
    # Ensure webhook_secret defaults to empty string, never None
    webhook_secret_default = getattr(settings, 'LMS_WEBHOOK_SECRET', '') or ''
    
    config, created = LMSIntegrationConfig.objects.get_or_create(
        realm=realm,
        defaults={
            'enabled': False,
            'lms_db_host': getattr(settings, 'LMS_DB_HOST', '') or '',
            'lms_db_port': getattr(settings, 'LMS_DB_PORT', 5432),
            'lms_db_name': getattr(settings, 'LMS_DB_NAME', '') or '',
            'lms_db_username': getattr(settings, 'LMS_DB_USERNAME', '') or '',
            'webhook_secret': webhook_secret_default,
            'jwt_enabled': getattr(settings, 'TESTPRESS_JWT_ENABLED', False),
            'testpress_api_url': getattr(settings, 'TESTPRESS_API_BASE_URL', '') or '',
            'activity_monitor_enabled': getattr(settings, 'LMS_ACTIVITY_MONITOR_ENABLED', False),
            'poll_interval': getattr(settings, 'LMS_ACTIVITY_POLL_INTERVAL', 60),
            'notify_mentors': getattr(settings, 'LMS_NOTIFY_MENTORS_ENABLED', True),
        }
    )
    # Ensure existing configs also have webhook_secret set (migration safety)
    if config.webhook_secret is None:
        config.webhook_secret = ''
        config.save(update_fields=['webhook_secret'])
    return config


def _validate_webhook_secret(request: HttpRequest) -> bool:
    """
    Validate webhook secret token from request.
    
    Args:
        request: HTTP request
        
    Returns:
        True if secret is valid, False otherwise
    """
    # Get secret from settings
    expected_secret = getattr(settings, 'LMS_WEBHOOK_SECRET', None)
    if not expected_secret:
        logger.warning("LMS_WEBHOOK_SECRET not configured in settings")
        return False
    
    # Check Authorization header
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        token = auth_header[7:]
        return token == expected_secret
    
    # Check X-LMS-Webhook-Secret header
    secret_header = request.headers.get('X-LMS-Webhook-Secret', '')
    if secret_header:
        return secret_header == expected_secret
    
    # Check in POST data
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            if data.get('secret') == expected_secret:
                return True
        except (json.JSONDecodeError, AttributeError):
            pass
    
    return False


@csrf_exempt
@require_http_methods(["POST"])
def lms_user_webhook(request: HttpRequest) -> JsonResponse:
    """
    Webhook endpoint for LMS to notify Zulip when a new user is created.
    
    Expected payload format:
    {
        "event_type": "user_created",
        "user_type": "student" | "mentor",
        "user_id": <int>,
        "secret": "<webhook_secret>" (optional if provided in header)
    }
    
    Returns:
        JSON response with sync result
    """
    try:
        # Validate webhook secret
        if not _validate_webhook_secret(request):
            logger.warning("Invalid webhook secret in request")
            return JsonResponse({
                'result': 'error',
                'message': 'Invalid webhook secret'
            }, status=401)
        
        # Parse request body
        try:
            data = json.loads(request.body)
        except (json.JSONDecodeError, AttributeError) as e:
            logger.error(f"Error parsing webhook payload: {e}")
            return JsonResponse({
                'result': 'error',
                'message': 'Invalid JSON payload'
            }, status=400)
        
        # Validate required fields
        event_type = data.get('event_type')
        user_type = data.get('user_type')
        user_id = data.get('user_id')
        
        if event_type != 'user_created':
            return JsonResponse({
                'result': 'error',
                'message': f'Unsupported event_type: {event_type}'
            }, status=400)
        
        if user_type not in ['student', 'mentor']:
            return JsonResponse({
                'result': 'error',
                'message': f'Invalid user_type: {user_type}. Must be "student" or "mentor"'
            }, status=400)
        
        if not user_id:
            return JsonResponse({
                'result': 'error',
                'message': 'user_id is required'
            }, status=400)
        
        # Initialize user sync
        user_sync = UserSync()
        
        # Sync the user based on type
        if user_type == 'student':
            try:
                student = Students.objects.using('lms_db').get(id=user_id)
                created, user_profile, message = user_sync.sync_student(student)
                
                if created:
                    logger.info(f"Webhook: Created user {user_profile.email} from student {user_id}")
                    return JsonResponse({
                        'result': 'success',
                        'message': f'User {user_profile.email} created successfully',
                        'user_id': user_profile.id,
                        'email': user_profile.email,
                        'created': True
                    })
                elif user_profile:
                    logger.info(f"Webhook: Updated user {user_profile.email} from student {user_id}")
                    return JsonResponse({
                        'result': 'success',
                        'message': f'User {user_profile.email} already exists and was updated',
                        'user_id': user_profile.id,
                        'email': user_profile.email,
                        'created': False
                    })
                else:
                    logger.warning(f"Webhook: Failed to sync student {user_id}: {message}")
                    return JsonResponse({
                        'result': 'error',
                        'message': message
                    }, status=400)
            except Students.DoesNotExist:
                logger.error(f"Webhook: Student {user_id} not found in LMS database")
                return JsonResponse({
                    'result': 'error',
                    'message': f'Student {user_id} not found in LMS database'
                }, status=404)
        
        elif user_type == 'mentor':
            try:
                mentor = Mentors.objects.using('lms_db').get(user_id=user_id)
                created, user_profile, message = user_sync.sync_mentor(mentor)
                
                if created:
                    logger.info(f"Webhook: Created user {user_profile.email} from mentor {user_id}")
                    return JsonResponse({
                        'result': 'success',
                        'message': f'User {user_profile.email} created successfully',
                        'user_id': user_profile.id,
                        'email': user_profile.email,
                        'created': True
                    })
                elif user_profile:
                    logger.info(f"Webhook: Updated user {user_profile.email} from mentor {user_id}")
                    return JsonResponse({
                        'result': 'success',
                        'message': f'User {user_profile.email} already exists and was updated',
                        'user_id': user_profile.id,
                        'email': user_profile.email,
                        'created': False
                    })
                else:
                    logger.warning(f"Webhook: Failed to sync mentor {user_id}: {message}")
                    return JsonResponse({
                        'result': 'error',
                        'message': message
                    }, status=400)
            except Mentors.DoesNotExist:
                logger.error(f"Webhook: Mentor {user_id} not found in LMS database")
                return JsonResponse({
                    'result': 'error',
                    'message': f'Mentor {user_id} not found in LMS database'
                }, status=404)
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        return JsonResponse({
            'result': 'error',
            'message': f'Internal server error: {str(e)}'
        }, status=500)


# ===================================
# ADMIN API ENDPOINTS
# ===================================

@require_realm_admin
@typed_endpoint_without_parameters
def lms_dashboard_status(
    request: HttpRequest,
    user_profile: UserProfile,
) -> JsonResponse:
    """Get LMS integration dashboard status and statistics."""
    try:
        realm = user_profile.realm
        config = get_or_create_lms_config(realm)

        # Get basic stats
        try:
            total_students = Students.objects.using('lms_db').filter(is_active=True).count()
            # The external LMS Mentors and Batches tables do not have an `is_active` field;
            # count all rows instead of filtering on a non-existent column.
            total_mentors = Mentors.objects.using('lms_db').all().count()
            total_batches = Batches.objects.using('lms_db').all().count()
            db_status = 'connected'
        except DatabaseError as e:
            total_students = 0
            total_mentors = 0
            total_batches = 0
            db_status = 'disconnected'
            log_admin_action(realm, 'WARNING', 'database', f"Database connection failed: {e}", user_profile)

        # Count synced users for this realm
        total_synced_users = LMSUserMapping.objects.filter(
            zulip_user__realm=realm,
            is_active=True
        ).count()

        # Get activity stats for today
        today = timezone.now().date()
        events_today = LMSActivityEvent.objects.filter(
            timestamp__date=today
        ).count()

        # Get recent sync info from sync history
        last_sync = LMSSyncHistory.objects.filter(realm=realm).first()
        last_sync_time = last_sync.completed_at.isoformat() if last_sync else None

        # Get pending notifications count
        pending_notifications = LMSEventLog.objects.filter(
            event__processed_for_ai=False,
            notification_sent=False
        ).count()

        # Get notifications sent today
        notifications_sent_today = LMSEventLog.objects.filter(
            notification_sent=True,
            processed_at__date=today
        ).count()

        # Monitor status from config
        monitor_status = 'running' if config.activity_monitor_enabled else 'stopped'

        log_admin_action(realm, 'INFO', 'admin_ui', "Dashboard status requested", user_profile)

        return json_success(
            request,
            data={
                'total_synced_users': total_synced_users,
                'total_students': total_students,
                'total_mentors': total_mentors,
                'total_batches': total_batches,
                'last_sync_time': last_sync_time,
                'last_activity_check': None,  # Would need activity monitor status tracking
                'pending_notifications': pending_notifications,
                'events_today': events_today,
                'notifications_sent': notifications_sent_today,
                'monitor_status': monitor_status,
                'db_status': db_status,
                'integration_enabled': config.enabled,
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Dashboard status error: {e}", user_profile, exception=e)
        logger.error(f"Error getting dashboard status: {e}", exc_info=True)
        return json_error(f"Failed to get dashboard status: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint
def lms_start_user_sync(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    sync_type: str = 'all',
    # Use Json[bool] so that form-encoded "true"/"false" values from the frontend
    # are correctly parsed as booleans by typed_endpoint.
    sync_batches: Json[bool] = True,
) -> JsonResponse:
    """Start user synchronization from LMS to Zulip using sequential processing."""
    start_time = timezone.now()
    realm = user_profile.realm

    try:
        config = get_or_create_lms_config(realm)
        if not config.enabled:
            return json_error("LMS integration is not enabled for this realm")

        # Clean up stale sync records before starting new sync
        _cleanup_stale_syncs(realm)

        # Check if there's already an active sync for this realm
        # Use a much shorter cutoff for active sync check - we just cleaned up stale ones
        from datetime import timedelta
        recent_cutoff = timezone.now() - timedelta(seconds=30)  # Only consider very recent syncs as truly active
        active_sync = LMSSyncProgress.objects.filter(
            realm=realm,
            current_stage__in=[
                'initializing', 'counting_records', 'syncing_students',
                'syncing_mentors', 'syncing_batches', 'updating_mappings', 'finalizing'
            ],
            # Only consider syncs that have been updated very recently (within 30 seconds)
            updated_at__gte=recent_cutoff
        ).first()

        if active_sync:
            # LMSSyncProgress uses `started_at` as the timestamp field; there is
            # no `created_at` attribute on this model.
            return json_error(
                f"A sync is already in progress (started {active_sync.started_at}). "
                f"Please wait for it to complete or check the progress."
            )

        # Generate unique sync ID for progress tracking
        import uuid
        sync_id = str(uuid.uuid4())

        # Create progress tracker
        progress_tracker = LMSSyncProgress.objects.create(
            sync_id=sync_id,
            realm=realm,
            sync_type=sync_type,
            current_stage='initializing',
            status_message='Starting sync...',
            triggered_by=user_profile,
        )

        # Create sync history entry
        sync_history = LMSSyncHistory.objects.create(
            realm=realm,
            sync_type=sync_type,
            started_at=start_time,
            completed_at=start_time,  # Will be updated after sync completes
            duration_seconds=0,
            triggered_by=user_profile,
            trigger_type='manual',
            batch_sync_enabled=sync_batches,
            status='running',  # Mark as running initially
        )

        log_admin_action(realm, 'INFO', 'user_sync', f"Starting {sync_type} sync with batches={sync_batches}", user_profile)

        # Update progress to running
        progress_tracker.current_stage = 'initializing'
        progress_tracker.status_message = 'Initializing sync...'
        progress_tracker.updated_at = timezone.now()
        progress_tracker.save(update_fields=['current_stage', 'status_message', 'updated_at'])

        # Define the sync function to run in background thread
        def run_sync():
            try:
                # Check if sync was cancelled before starting
                with _sync_lock:
                    progress_tracker.refresh_from_db()
                    if progress_tracker.current_stage == 'cancelled':
                        logger.info(f"Sync {sync_id} was cancelled before starting")
                        return

                # Instantiate UserSync with progress tracking
                user_sync = UserSync(realm=realm, progress_tracker=sync_id)

                # Determine which sync method to call based on parameters
                # Check for cancellation before each major step
                with _sync_lock:
                    progress_tracker.refresh_from_db()
                    if progress_tracker.current_stage == 'cancelled':
                        logger.info(f"Sync {sync_id} was cancelled")
                        return

                if sync_batches and sync_type in ['all', 'students']:
                    # Sync users and batches
                    logger.info(f"Starting full sync (users + batches) for realm {realm.string_id}")
                    results = user_sync.sync_all_with_batches()
                elif sync_type == 'all':
                    # Sync all users (students and mentors)
                    logger.info(f"Starting user sync (all) for realm {realm.string_id}")
                    results = user_sync.sync_all_users()
                elif sync_type == 'students':
                    # Sync only students
                    logger.info(f"Starting student sync for realm {realm.string_id}")
                    student_stats = user_sync.sync_all_students()
                    results = {
                        'students': student_stats,
                        'mentors': {'total': 0, 'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0},
                        'total_created': student_stats['created'],
                        'total_updated': student_stats['updated'],
                        'total_skipped': student_stats['skipped'],
                        'total_errors': student_stats['errors'],
                    }
                elif sync_type == 'mentors':
                    # Sync only mentors
                    logger.info(f"Starting mentor sync for realm {realm.string_id}")
                    mentor_stats = user_sync.sync_all_mentors()
                    results = {
                        'students': {'total': 0, 'created': 0, 'updated': 0, 'skipped': 0, 'errors': 0},
                        'mentors': mentor_stats,
                        'total_created': mentor_stats['created'],
                        'total_updated': mentor_stats['updated'],
                        'total_skipped': mentor_stats['skipped'],
                        'total_errors': mentor_stats['errors'],
                    }
                else:
                    raise ValueError(f"Invalid sync_type: {sync_type}")

                # Check for cancellation after sync completes
                with _sync_lock:
                    progress_tracker.refresh_from_db()
                    if progress_tracker.current_stage == 'cancelled':
                        logger.info(f"Sync {sync_id} was cancelled after sync completed")
                        return

                # Update user mappings after sync completes
                try:
                    update_user_mappings(realm, sync_id=sync_id)
                except Exception as e:
                    logger.warning(f"Failed to update user mappings for sync {sync_id}: {e}")

                # Calculate duration
                end_time = timezone.now()
                duration = (end_time - start_time).total_seconds()

                # Check for cancellation one more time before finalizing
                with _sync_lock:
                    progress_tracker.refresh_from_db()
                    if progress_tracker.current_stage == 'cancelled':
                        logger.info(f"Sync {sync_id} was cancelled before finalizing")
                        return

                # Extract totals from results
                total_created = results.get('total_created', 0)
                total_updated = results.get('total_updated', 0)
                total_skipped = results.get('total_skipped', 0)
                total_errors = results.get('total_errors', 0)

                # Update progress tracker to completed
                with _sync_lock:
                    progress_tracker.refresh_from_db()
                    # Double-check it wasn't cancelled while we were processing
                    if progress_tracker.current_stage == 'cancelled':
                        logger.info(f"Sync {sync_id} was cancelled during finalization")
                        return
                    progress_tracker.current_stage = 'completed'
                
                # Provide more informative message when all stats are zero
                if total_created == 0 and total_updated == 0 and total_skipped == 0 and total_errors == 0:
                    # Check if there were any users to process
                    total_users = 0
                    if 'users' in results:
                        if 'students' in results['users']:
                            total_users += results['users']['students'].get('total', 0)
                        if 'mentors' in results['users']:
                            total_users += results['users']['mentors'].get('total', 0)
                    elif 'students' in results:
                        total_users += results['students'].get('total', 0)
                    elif 'mentors' in results:
                        total_users += results['mentors'].get('total', 0)
                    
                    if total_users == 0:
                        progress_tracker.status_message = (
                            "Sync completed: No users found in LMS database to sync"
                        )
                    else:
                        progress_tracker.status_message = (
                            f"Sync completed: {total_created} created, {total_updated} updated, "
                            f"{total_skipped} skipped, {total_errors} errors"
                        )
                else:
                    progress_tracker.status_message = (
                        f"Sync completed: {total_created} created, {total_updated} updated, "
                        f"{total_skipped} skipped, {total_errors} errors"
                    )
                progress_tracker.created_count = total_created
                progress_tracker.updated_count = total_updated
                progress_tracker.skipped_count = total_skipped
                progress_tracker.error_count = total_errors
                progress_tracker.completed_at = end_time
                progress_tracker.updated_at = end_time
                progress_tracker.save()

                # Update sync history with final results
                sync_history.users_created = total_created
                sync_history.users_updated = total_updated
                sync_history.users_skipped = total_skipped
                sync_history.users_errors = total_errors
                sync_history.completed_at = end_time
                sync_history.duration_seconds = duration
                sync_history.status = 'success' if total_errors == 0 else 'partial'

                # Handle batch stats if present
                if 'batches' in results:
                    batch_stats = results['batches']
                    sync_history.batches_synced = (
                        batch_stats.get('batches_created', 0) +
                        batch_stats.get('batches_updated', 0)
                    )

                sync_history.save()

                logger.info(
                    f"LMS user sync completed for sync_id {sync_id} in {duration:.2f}s. "
                    f"Results: {results}"
                )
                
                # Log warning if all stats are zero (might indicate an issue)
                if total_created == 0 and total_updated == 0 and total_skipped == 0 and total_errors == 0:
                    logger.warning(
                        f"Sync {sync_id} completed with all zero stats. "
                        f"This may indicate no users were found in the LMS database. "
                        f"Full results structure: {results}"
                    )

            except Exception as e:
                # Check if it was cancelled (not a real error)
                with _sync_lock:
                    progress_tracker.refresh_from_db()
                    if progress_tracker.current_stage == 'cancelled':
                        logger.info(f"Sync {sync_id} was cancelled, not marking as failed")
                        return

                # Mark sync as failed
                end_time = timezone.now()
                duration = (end_time - start_time).total_seconds()

                error_message = f"Sync error: {str(e)}"
                logger.error(
                    f"Error during LMS user sync {sync_id}: {e}",
                    exc_info=True
                )

                # Update progress tracker to failed
                with _sync_lock:
                    progress_tracker.refresh_from_db()
                    if progress_tracker.current_stage != 'cancelled':
                        progress_tracker.current_stage = 'failed'
                        progress_tracker.status_message = error_message
                        progress_tracker.failed_at = end_time
                        progress_tracker.updated_at = end_time
                        progress_tracker.save()

                        # Update sync history to failed
                        sync_history.completed_at = end_time
                        sync_history.duration_seconds = duration
                        sync_history.status = 'failed'
                        sync_history.save()

                        log_admin_action(realm, 'ERROR', 'user_sync', f"Sync failed: {e}", user_profile, exception=e)
            finally:
                # Remove from running syncs
                with _sync_lock:
                    _running_syncs.pop(sync_id, None)

        # Start sync in background thread
        sync_thread = threading.Thread(target=run_sync, daemon=True)
        sync_thread.start()

        # Register the thread for cancellation
        with _sync_lock:
            _running_syncs[sync_id] = (sync_thread, progress_tracker, sync_history)

        # Return immediately with sync_id so frontend can start polling
        return json_success(
            request,
            data={
                'status': 'running',
                'message': 'Sync started. Progress will be updated in real-time.',
                'sync_id': sync_id,
                'sync_type': sync_type,
                'sync_batches': sync_batches,
                'started_at': start_time.isoformat(),
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'user_sync', f"Failed to start user sync: {e}", user_profile, exception=e)
        logger.error(f"Error starting user sync: {e}", exc_info=True)
        return json_error(f"Failed to start user sync: {str(e)}")


def _cleanup_stale_syncs(realm: Realm) -> None:
    """
    Clean up sync records that are stuck in active states for more than 2 minutes.
    This handles cases where the sync process was interrupted or crashed.
    """
    try:
        from datetime import timedelta

        cutoff_time = timezone.now() - timedelta(minutes=2)
        # Check both updated_at and started_at to catch syncs that haven't progressed
        # Include all active stages that could be stuck
        stale_syncs = LMSSyncProgress.objects.filter(
            realm=realm,
            current_stage__in=[
                'initializing', 'counting_records', 'syncing_students', 
                'syncing_mentors', 'syncing_batches', 'updating_mappings', 'finalizing'
            ]
        ).filter(
            # Sync is stale if either:
            # 1. updated_at is old (no progress updates)
            # 2. started_at is old (sync has been running too long)
            models.Q(updated_at__lt=cutoff_time) | models.Q(started_at__lt=cutoff_time)
        )

        if stale_syncs.exists():
            stale_count = stale_syncs.count()
            stale_syncs.update(
                current_stage='failed',
                status_message='Sync timeout - process may have crashed',
                last_error='Sync timed out after 2 minutes of inactivity',
                updated_at=timezone.now()
            )
            logger.warning(f"Cleaned up {stale_count} stale sync records for realm {realm.string_id}")

    except Exception as e:
        logger.warning(f"Failed to cleanup stale syncs for realm {realm.string_id}: {e}")


def update_user_mappings(realm: Realm, sync_id: Optional[str] = None) -> None:
    """
    Update user mappings for tracking purposes.
    Optimized version using bulk operations for better performance.
    
    Args:
        realm: The realm to update mappings for
        sync_id: Optional sync ID to update progress during processing
    """
    try:
        from lms_integration.models import LMSSyncProgress, LMSUserMapping
        from django.utils.timezone import now as timezone_now
        from django.db import transaction
        
        # Get all active Zulip users in the realm
        # Only fetch the fields we need to avoid PostgreSQL join column limit
        zulip_users = list(UserProfile.objects.filter(realm=realm, is_active=True).only('id', 'delivery_email'))
        total_users = len(zulip_users)
        processed = 0

        # Update progress if sync_id is provided
        if sync_id:
            try:
                progress = LMSSyncProgress.objects.get(sync_id=sync_id, realm=realm)
                progress.current_stage = 'updating_mappings'
                progress.total_records = total_users
                progress.processed_records = 0
                progress.status_message = f'Updating user mappings (0 of {total_users})...'
                progress.updated_at = timezone_now()
                progress.save(update_fields=[
                    'current_stage', 'total_records', 'processed_records', 
                    'status_message', 'updated_at'
                ])
            except Exception as e:
                logger.warning(f"Failed to update progress for mappings: {e}")

        # Bulk fetch all students and mentors from LMS (one query each)
        logger.info(f"Fetching all students and mentors from LMS for mapping update...")
        all_students = list(Students.objects.using('lms_db').filter(is_active=True).only('id', 'email', 'username'))
        # Note: Mentors model doesn't have is_active field, so we fetch all mentors
        all_mentors = list(Mentors.objects.using('lms_db').only('user_id', 'email', 'username'))
        
        # Create lookup dictionaries by email (case-insensitive)
        student_lookup = {}
        for student in all_students:
            if student.email:
                email_key = student.email.lower()
                # Prefer first match if duplicates exist
                if email_key not in student_lookup:
                    student_lookup[email_key] = student
        
        mentor_lookup = {}
        for mentor in all_mentors:
            if mentor.email:
                email_key = mentor.email.lower()
                # Prefer first match if duplicates exist
                if email_key not in mentor_lookup:
                    mentor_lookup[email_key] = mentor
        
        logger.info(f"Found {len(student_lookup)} students and {len(mentor_lookup)} mentors in LMS")
        
        # Get all existing mappings in bulk
        # We only need zulip_user_id, so no need for select_related
        existing_mappings = {
            mapping.zulip_user_id: mapping 
            for mapping in LMSUserMapping.objects.filter(zulip_user__realm=realm)
        }
        
        # Prepare mappings for bulk operations
        mappings_to_create = []
        mappings_to_update = []
        batch_size = getattr(settings, 'LMS_SYNC_BATCH_SIZE', 500)
        progress_interval = getattr(settings, 'LMS_SYNC_PROGRESS_INTERVAL', 100)
        total_created = 0
        total_updated = 0
        
        for zulip_user in zulip_users:
            try:
                email_key = zulip_user.delivery_email.lower() if zulip_user.delivery_email else None
                if not email_key:
                    processed += 1
                    continue
                
                # Check if user is both student and mentor - prioritize mentor
                student = student_lookup.get(email_key)
                mentor = mentor_lookup.get(email_key)
                
                existing_mapping = existing_mappings.get(zulip_user.id)
                
                # Prioritize mentor if user is both student and mentor
                if mentor:
                    # User is a mentor (or both student and mentor)
                    if existing_mapping:
                        # Update existing mapping
                        existing_mapping.lms_user_id = mentor.user_id
                        existing_mapping.lms_user_type = 'mentor'
                        existing_mapping.lms_username = mentor.username
                        existing_mapping.is_active = True
                        existing_mapping.last_error = None
                        existing_mapping.sync_count += 1
                        existing_mapping.last_synced_at = timezone_now()
                        mappings_to_update.append(existing_mapping)
                    else:
                        # Create new mapping
                        mappings_to_create.append(LMSUserMapping(
                            zulip_user=zulip_user,
                            lms_user_id=mentor.user_id,
                            lms_user_type='mentor',
                            lms_username=mentor.username,
                            is_active=True,
                            last_error=None,
                            sync_count=1,
                        ))
                elif student:
                    # User is a student only
                    if existing_mapping:
                        # Update existing mapping
                        existing_mapping.lms_user_id = student.id
                        existing_mapping.lms_user_type = 'student'
                        existing_mapping.lms_username = student.username
                        existing_mapping.is_active = True
                        existing_mapping.last_error = None
                        existing_mapping.sync_count += 1
                        existing_mapping.last_synced_at = timezone_now()
                        mappings_to_update.append(existing_mapping)
                    else:
                        # Create new mapping
                        mappings_to_create.append(LMSUserMapping(
                            zulip_user=zulip_user,
                            lms_user_id=student.id,
                            lms_user_type='student',
                            lms_username=student.username,
                            is_active=True,
                            last_error=None,
                            sync_count=1,
                        ))
                # If user is not found in LMS, we don't create/update mapping
                # (existing mappings with errors will remain as-is)
                
            except Exception as e:
                logger.error(f"Error processing mapping for user {zulip_user.id} ({zulip_user.delivery_email}): {e}")
                # Continue processing other users
                pass
            
            processed += 1
            
            # Update progress and process batches
            if processed % progress_interval == 0 or processed == total_users:
                if sync_id:
                    try:
                        progress = LMSSyncProgress.objects.get(sync_id=sync_id, realm=realm)
                        progress.processed_records = processed
                        progress.status_message = f'Updating user mappings ({processed} of {total_users})...'
                        progress.updated_at = timezone_now()
                        progress.save(update_fields=['processed_records', 'status_message', 'updated_at'])
                    except Exception as e:
                        logger.warning(f"Failed to update progress during mappings: {e}")
            
            # Process batches to avoid memory issues
            if len(mappings_to_create) >= batch_size:
                with transaction.atomic():
                    LMSUserMapping.objects.bulk_create(mappings_to_create, ignore_conflicts=True)
                batch_created = len(mappings_to_create)
                total_created += batch_created
                logger.info(f"Bulk created {batch_created} mappings (total: {total_created})")
                mappings_to_create = []
            
            if len(mappings_to_update) >= batch_size:
                with transaction.atomic():
                    LMSUserMapping.objects.bulk_update(
                        mappings_to_update, 
                        ['lms_user_id', 'lms_user_type', 'lms_username', 'is_active', 
                         'last_error', 'sync_count', 'last_synced_at']
                    )
                batch_updated = len(mappings_to_update)
                total_updated += batch_updated
                logger.info(f"Bulk updated {batch_updated} mappings (total: {total_updated})")
                mappings_to_update = []
        
        # Process remaining mappings
        if mappings_to_create:
            with transaction.atomic():
                LMSUserMapping.objects.bulk_create(mappings_to_create, ignore_conflicts=True)
            final_created = len(mappings_to_create)
            total_created += final_created
            logger.info(f"Bulk created {final_created} final mappings")
        
        if mappings_to_update:
            with transaction.atomic():
                LMSUserMapping.objects.bulk_update(
                    mappings_to_update,
                    ['lms_user_id', 'lms_user_type', 'lms_username', 'is_active',
                     'last_error', 'sync_count', 'last_synced_at']
                )
            final_updated = len(mappings_to_update)
            total_updated += final_updated
            logger.info(f"Bulk updated {final_updated} final mappings")
        
        logger.info(f"Completed updating user mappings: {processed} users processed, "
                    f"{total_created} created, {total_updated} updated")

    except Exception as e:
        logger.error(f"Error updating user mappings: {e}", exc_info=True)


@require_realm_admin
@typed_endpoint
def lms_get_synced_users(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    page: Json[int] = 1,
    user_type: Optional[str] = None,
    search: Optional[str] = None,
) -> JsonResponse:
    """Get list of synced users with pagination and filtering."""
    try:
        realm = user_profile.realm

        # Base query for user mappings
        mappings_query = LMSUserMapping.objects.filter(
            zulip_user__realm=realm,
            is_active=True
        ).select_related('zulip_user')

        # Filter by user type
        if user_type and user_type in ['student', 'mentor']:
            mappings_query = mappings_query.filter(lms_user_type=user_type)

        # Search by name or email
        if search:
            mappings_query = mappings_query.filter(
                models.Q(zulip_user__full_name__icontains=search) |
                models.Q(zulip_user__email__icontains=search) |
                models.Q(lms_username__icontains=search)
            )

        # Order by last sync date
        mappings_query = mappings_query.order_by('-last_synced_at')

        # Paginate
        paginator = Paginator(mappings_query, 50)  # 50 users per page
        page_obj = paginator.get_page(page)

        users_data = []
        for mapping in page_obj:
            users_data.append({
                'id': mapping.zulip_user.id,
                'name': mapping.zulip_user.full_name,
                'email': mapping.zulip_user.email,
                'type': mapping.lms_user_type,
                'lms_id': mapping.lms_user_id,
                'lms_username': mapping.lms_username,
                'last_sync': mapping.last_synced_at.isoformat(),
                'sync_count': mapping.sync_count,
                'status': 'active' if mapping.zulip_user.is_active else 'inactive',
                'last_error': mapping.last_error,
            })

        log_admin_action(realm, 'INFO', 'admin_ui', f"Synced users list requested (page {page})", user_profile)

        return json_success(
            request,
            data={
                'users': users_data,
                'total_count': paginator.count,
                'page': page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Failed to get synced users: {e}", user_profile, exception=e)
        logger.error(f"Error getting synced users: {e}", exc_info=True)
        return json_error(f"Failed to get synced users: {str(e)}")


@require_realm_admin
@typed_endpoint
def lms_get_activity_events(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    page: Json[int] = 1,
    event_type: Optional[str] = None,
    search: Optional[str] = None,
) -> JsonResponse:
    """Get LMS activity events with pagination and filtering."""
    try:
        # Base query for activity events
        events_query = LMSActivityEvent.objects.all().order_by('-timestamp')

        if event_type:
            events_query = events_query.filter(event_type=event_type)

        if search:
            events_query = events_query.filter(
                models.Q(student_username__icontains=search) |
                models.Q(activity_title__icontains=search)
            )

        # Paginate
        paginator = Paginator(events_query, 50)
        page_obj = paginator.get_page(page)

        events_data = []
        for event in page_obj:
            # Check if mentor was notified
            try:
                event_log = LMSEventLog.objects.get(event=event)
                mentor_notified = event_log.notification_sent
                notification_status = 'sent' if event_log.notification_sent else 'failed'
                if event_log.error_message:
                    notification_status = 'error'
            except LMSEventLog.DoesNotExist:
                mentor_notified = False
                notification_status = 'pending'

            events_data.append({
                'id': event.event_id,
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type,
                'student_id': event.student_id,
                'student_username': event.student_username,
                'mentor_id': event.mentor_id,
                'mentor_username': event.mentor_username,
                'activity_title': event.activity_title,
                'activity_metadata': event.activity_metadata,
                'mentor_notified': mentor_notified,
                'notification_status': notification_status,
                'processed_for_ai': event.processed_for_ai,
            })

        return json_success(
            request,
            data={
                'events': events_data,
                'total_count': paginator.count,
                'page': page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        )

    except Exception as e:
        logger.error(f"Error getting activity events: {e}", exc_info=True)
        return json_error(f"Failed to get activity events: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint_without_parameters
def lms_poll_activities(
    request: HttpRequest,
    user_profile: UserProfile,
) -> JsonResponse:
    """Manually trigger activity polling."""
    try:
        activity_monitor = ActivityMonitor()

        # Poll for new activities
        new_events = activity_monitor.poll_for_new_activities()

        return json_success(
            request,
            data={
                'status': 'success',
                'message': f'Activity polling completed. Found {len(new_events)} new events.',
                'new_events_count': len(new_events),
                'events': [
                {
                    'event_type': event.event_type,
                    'student_username': event.student_username,
                    'activity_title': event.activity_title,
                    'timestamp': event.timestamp.isoformat(),
                }
                    for event in new_events[:10]  # Return first 10 for preview
                ]
            }
        )

    except Exception as e:
        logger.error(f"Error polling activities: {e}", exc_info=True)
        return json_error(f"Activity polling failed: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint_without_parameters
def lms_test_database_connection(
    request: HttpRequest,
    user_profile: UserProfile,
) -> JsonResponse:
    """Test connection to LMS database."""
    try:
        # Test database connection
        lms_db = connections['lms_db']

        with lms_db.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()

        if result and result[0] == 1:
            # Test actual table access
            student_count = Students.objects.using('lms_db').count()
            mentor_count = Mentors.objects.using('lms_db').count()

            return json_success(
                request,
                data={
                    'status': 'success',
                    'message': 'Database connection successful',
                'details': {
                    'students_available': student_count,
                    'mentors_available': mentor_count,
                    'connection_time': timezone.now().isoformat(),
                }
            })
        else:
            return json_error("Database connection test failed")

    except DatabaseError as e:
        logger.error(f"Database connection test failed: {e}")
        return json_error(f"Database connection failed: {str(e)}")
    except Exception as e:
        logger.error(f"Error testing database connection: {e}", exc_info=True)
        return json_error(f"Connection test failed: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint
def lms_update_configuration(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    # Use Json[bool] for booleans so that form values like "true"/"false"/"on"
    # from the browser are correctly parsed by typed_endpoint.
    lms_enabled: Json[bool] | None = None,
    lms_db_host: Optional[str] = None,
    # Use Json[int] so numeric strings from the browser are parsed correctly.
    lms_db_port: Json[int] | None = None,
    lms_db_name: Optional[str] = None,
    lms_db_username: Optional[str] = None,
    lms_db_password: Optional[str] = None,
    webhook_secret: Optional[str] = None,
    jwt_enabled: Json[bool] | None = None,
    testpress_api_url: Optional[str] = None,
    activity_monitor_enabled: Json[bool] | None = None,
    # Poll interval is submitted as a string; parse it via Json[int].
    poll_interval: Json[int] | None = None,
    notify_mentors: Json[bool] | None = None,
    # Placeholder email settings
    lms_no_email_domain: Optional[str] = None,
    lms_auto_update_emails: Json[bool] | None = None,
    lms_placeholder_email_delivery: Json[bool] | None = None,
    lms_placeholder_inapp_notifications: Json[bool] | None = None,
    lms_log_placeholder_attempts: Json[bool] | None = None,
) -> JsonResponse:
    """Update LMS integration configuration settings."""
    try:
        realm = user_profile.realm
        config = get_or_create_lms_config(realm)
        updated_settings = {}

        # Validate and update settings
        if lms_enabled is not None:
            config.enabled = lms_enabled
            updated_settings['lms_enabled'] = lms_enabled

        if lms_db_host is not None:
            config.lms_db_host = lms_db_host.strip()
            updated_settings['lms_db_host'] = lms_db_host

        if lms_db_port is not None:
            if not (1 <= lms_db_port <= 65535):
                return json_error("Database port must be between 1 and 65535")
            config.lms_db_port = lms_db_port
            updated_settings['lms_db_port'] = lms_db_port

        if lms_db_name is not None:
            config.lms_db_name = lms_db_name.strip()
            updated_settings['lms_db_name'] = lms_db_name

        if lms_db_username is not None:
            config.lms_db_username = lms_db_username.strip()
            updated_settings['lms_db_username'] = lms_db_username

        if lms_db_password is not None and lms_db_password:
            # TODO: Implement password encryption
            config.lms_db_password = lms_db_password
            updated_settings['lms_db_password'] = "••••••••"

        if webhook_secret is not None:
            if len(webhook_secret) < 32:
                return json_error("Webhook secret must be at least 32 characters long")
            # Ensure webhook_secret is never None (use empty string instead)
            config.webhook_secret = webhook_secret if webhook_secret else ''
            updated_settings['webhook_secret'] = "••••••••"

        if jwt_enabled is not None:
            config.jwt_enabled = jwt_enabled
            updated_settings['jwt_enabled'] = jwt_enabled

        if testpress_api_url is not None:
            if testpress_api_url and not testpress_api_url.startswith(('http://', 'https://')):
                return json_error("TestPress API URL must be a valid HTTP/HTTPS URL")
            config.testpress_api_url = testpress_api_url
            updated_settings['testpress_api_url'] = testpress_api_url

        if activity_monitor_enabled is not None:
            config.activity_monitor_enabled = activity_monitor_enabled
            updated_settings['activity_monitor_enabled'] = activity_monitor_enabled

        if poll_interval is not None:
            if not (30 <= poll_interval <= 3600):
                return json_error("Poll interval must be between 30 and 3600 seconds")
            config.poll_interval = poll_interval
            updated_settings['poll_interval'] = poll_interval

        if notify_mentors is not None:
            config.notify_mentors = notify_mentors
            updated_settings['notify_mentors'] = notify_mentors

        # Handle placeholder email settings - these are stored in the settings file, not the database
        # For now, we just acknowledge them and log that they were updated
        placeholder_settings_updated = []

        if lms_no_email_domain is not None:
            placeholder_settings_updated.append('lms_no_email_domain')
            updated_settings['lms_no_email_domain'] = lms_no_email_domain

        if lms_auto_update_emails is not None:
            placeholder_settings_updated.append('lms_auto_update_emails')
            updated_settings['lms_auto_update_emails'] = lms_auto_update_emails

        if lms_placeholder_email_delivery is not None:
            placeholder_settings_updated.append('lms_placeholder_email_delivery')
            updated_settings['lms_placeholder_email_delivery'] = lms_placeholder_email_delivery

        if lms_placeholder_inapp_notifications is not None:
            placeholder_settings_updated.append('lms_placeholder_inapp_notifications')
            updated_settings['lms_placeholder_inapp_notifications'] = lms_placeholder_inapp_notifications

        if lms_log_placeholder_attempts is not None:
            placeholder_settings_updated.append('lms_log_placeholder_attempts')
            updated_settings['lms_log_placeholder_attempts'] = lms_log_placeholder_attempts

        # Note: Placeholder email settings would need to be persisted to a config file
        # or database table for full functionality. For now, they use hardcoded defaults.
        if placeholder_settings_updated:
            log_admin_action(
                realm, 'INFO', 'configuration',
                f"Placeholder email settings updated (note: requires manual config file update): {', '.join(placeholder_settings_updated)}",
                user_profile
            )

        # Update audit fields
        config.updated_by = user_profile
        config.save()

        # Log configuration change
        log_admin_action(
            realm, 'INFO', 'configuration',
            f"Configuration updated: {', '.join(updated_settings.keys())}",
            user_profile, details=updated_settings
        )

        return json_success(
            request,
            data={
                'status': 'success',
                'message': 'Configuration updated successfully',
                'updated_settings': updated_settings
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'configuration', f"Failed to update configuration: {e}", user_profile, exception=e)
        logger.error(f"Error updating LMS configuration: {e}", exc_info=True)
        return json_error(f"Configuration update failed: {str(e)}")


@require_realm_admin
@typed_endpoint
def lms_get_logs(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    level: Optional[str] = None,
    source: Optional[str] = None,
    page: Json[int] = 1,
) -> JsonResponse:
    """Get LMS integration logs with filtering."""
    try:
        realm = user_profile.realm

        # Base query for logs
        logs_query = LMSAdminLog.objects.filter(realm=realm).order_by('-timestamp')

        # Filter by level
        if level and level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
            logs_query = logs_query.filter(level=level)

        # Filter by source
        if source:
            logs_query = logs_query.filter(source=source)

        # Paginate
        paginator = Paginator(logs_query, 100)  # 100 logs per page
        page_obj = paginator.get_page(page)

        logs_data = []
        for log in page_obj:
            logs_data.append({
                'id': log.id,
                'timestamp': log.timestamp.isoformat(),
                'level': log.level,
                'source': log.source,
                'message': log.message,
                'user': log.user.full_name if log.user else None,
                'details': log.details,
                'exception_type': log.exception_type,
                'has_stack_trace': bool(log.stack_trace),
            })

        # Get error counts for different categories
        today = timezone.now().date()
        error_counts = {
            'sync_errors': LMSAdminLog.objects.filter(
                realm=realm,
                source='user_sync',
                level__in=['ERROR', 'CRITICAL'],
                timestamp__date=today
            ).count(),
            'webhook_errors': LMSAdminLog.objects.filter(
                realm=realm,
                source='webhook',
                level__in=['ERROR', 'CRITICAL'],
                timestamp__date=today
            ).count(),
            'auth_errors': LMSAdminLog.objects.filter(
                realm=realm,
                source='jwt_auth',
                level__in=['ERROR', 'CRITICAL'],
                timestamp__date=today
            ).count(),
        }

        log_admin_action(realm, 'INFO', 'admin_ui', f"Admin logs requested (page {page})", user_profile)

        return json_success(
            request,
            data={
                'logs': logs_data,
                'total_count': paginator.count,
                'page': page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'error_counts': error_counts,
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Failed to get logs: {e}", user_profile, exception=e)
        logger.error(f"Error getting logs: {e}", exc_info=True)
        return json_error(f"Failed to get logs: {str(e)}")


@require_realm_admin
@typed_endpoint_without_parameters
def lms_get_current_config(
    request: HttpRequest,
    user_profile: UserProfile,
) -> JsonResponse:
    """Get current LMS integration configuration."""
    try:
        realm = user_profile.realm
        config = get_or_create_lms_config(realm)

        # Import placeholder email settings
        from lms_integration.lib.email_utils import get_placeholder_email_stats
        from lms_integration.settings import (
            LMS_NO_EMAIL_DOMAIN,
            LMS_AUTO_UPDATE_EMAILS,
            LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS,
        )

        # Get placeholder email statistics
        try:
            placeholder_stats = get_placeholder_email_stats(realm)
        except Exception:
            placeholder_stats = {
                'total_users': 0,
                'placeholder_users': 0,
                'real_email_users': 0,
                'placeholder_percentage': 0
            }

        config_data = {
            'lms_enabled': config.enabled,
            'lms_db_host': config.lms_db_host,
            'lms_db_port': config.lms_db_port,
            'lms_db_name': config.lms_db_name,
            'lms_db_username': config.lms_db_username,
            'lms_db_password_set': bool(config.lms_db_password),
            'webhook_secret_set': bool(config.webhook_secret),
            'jwt_enabled': config.jwt_enabled,
            'testpress_api_url': config.testpress_api_url,
            'activity_monitor_enabled': config.activity_monitor_enabled,
            'poll_interval': config.poll_interval,
            'notify_mentors': config.notify_mentors,

            # Placeholder email settings
            'lms_no_email_domain': LMS_NO_EMAIL_DOMAIN,
            'lms_auto_update_emails': LMS_AUTO_UPDATE_EMAILS,
            'lms_placeholder_email_delivery': LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS.get('email_delivery', False),
            'lms_placeholder_inapp_notifications': LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS.get('in_app_notifications', True),
            'lms_log_placeholder_attempts': LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS.get('log_attempts', True),

            # Placeholder email statistics
            'placeholder_stats': placeholder_stats,

            'webhook_endpoint_url': f"{request.scheme}://{request.get_host()}/api/v1/lms/webhook/user-created",
            'created_at': config.created_at.isoformat(),
            'updated_at': config.updated_at.isoformat(),
            'updated_by': config.updated_by.full_name if config.updated_by else None,
        }

        log_admin_action(realm, 'INFO', 'admin_ui', "Configuration requested", user_profile)

        return json_success(request, data=config_data)

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Failed to get configuration: {e}", user_profile, exception=e)
        logger.error(f"Error getting configuration: {e}", exc_info=True)
        return json_error(f"Failed to get configuration: {str(e)}")


# Additional endpoint for sync history
@require_realm_admin
@typed_endpoint
def lms_get_sync_history(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    page: Json[int] = 1,
) -> JsonResponse:
    """Get sync history for the realm."""
    try:
        realm = user_profile.realm

        # Get sync history for this realm
        history_query = LMSSyncHistory.objects.filter(realm=realm).order_by('-started_at')

        # Paginate
        paginator = Paginator(history_query, 20)  # 20 sync records per page
        page_obj = paginator.get_page(page)

        history_data = []
        for sync in page_obj:
            history_data.append({
                'id': sync.id,
                'sync_type': sync.sync_type,
                'started_at': sync.started_at.isoformat(),
                'completed_at': sync.completed_at.isoformat(),
                'duration_seconds': sync.duration_seconds,
                'status': sync.status,
                'users_created': sync.users_created,
                'users_updated': sync.users_updated,
                'users_skipped': sync.users_skipped,
                'users_errors': sync.users_errors,
                'batches_synced': sync.batches_synced,
                'batch_sync_enabled': sync.batch_sync_enabled,
                'batch_sync_error': sync.batch_sync_error,
                'triggered_by': sync.triggered_by.full_name if sync.triggered_by else None,
                'trigger_type': sync.trigger_type,
                'error_message': sync.error_message,
            })

        log_admin_action(realm, 'INFO', 'admin_ui', f"Sync history requested (page {page})", user_profile)

        return json_success(
            request,
            data={
                'history': history_data,
                'total_count': paginator.count,
                'page': page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Failed to get sync history: {e}", user_profile, exception=e)
        logger.error(f"Error getting sync history: {e}", exc_info=True)
        return json_error(f"Failed to get sync history: {str(e)}")


# Endpoint for batch management
@require_realm_admin
@typed_endpoint
def lms_get_batch_groups(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    page: Json[int] = 1,
) -> JsonResponse:
    """Get LMS batches and their Zulip group mappings."""
    try:
        realm = user_profile.realm

        # Get active batches from LMS
        try:
            # The LMS Batches table (external DB) does not have an `is_active` field.
            # We fetch all batches and treat them as active for display purposes.
            batches = Batches.objects.using('lms_db').all().order_by('name')

            # Paginate
            paginator = Paginator(batches, 50)
            page_obj = paginator.get_page(page)

            batch_data = []
            for batch in page_obj:
                # Count students in this batch
                # Batchtostudent schema uses `a` (batch FK) and `b` (student FK)
                student_count = Batchtostudent.objects.using('lms_db').filter(
                    a_id=batch.id
                ).count()

                # Count mentors for students in this batch
                mentor_count = Mentortostudent.objects.using('lms_db').filter(
                    # Mentortostudent schema uses `a` (mentor FK) and `b` (student FK)
                    b_id__in=Batchtostudent.objects.using('lms_db').filter(
                        a_id=batch.id
                    ).values('b_id')
                ).values('a_id').distinct().count()

                # TODO: Check if Zulip group exists for this batch
                # This would require integration with Zulip's user group system

                batch_data.append({
                    'id': batch.id,
                    'batch_name': batch.name,
                    # External schema does not provide these fields; fall back to sensible defaults.
                    'batch_code': getattr(batch, 'batch_code', None) or batch.id,
                    'description': getattr(batch, 'description', None) or batch.url,
                    'student_count': student_count,
                    'mentor_count': mentor_count,
                    'is_active': True,  # treat as active since LMS schema lacks is_active
                    'created_date': batch.created.isoformat() if getattr(batch, 'created', None) else None,
                    'zulip_group_exists': False,  # TODO: Implement group checking
                    'last_sync': None,  # TODO: Implement batch sync tracking
                    'status': 'active',
                })

        except DatabaseError as e:
            log_admin_action(realm, 'ERROR', 'database', f"Failed to get batches: {e}", user_profile, exception=e)
            return json_error("Failed to connect to LMS database")

        log_admin_action(realm, 'INFO', 'admin_ui', f"Batch groups requested (page {page})", user_profile)

        return json_success(
            request,
            data={
                'batches': batch_data,
                'total_count': paginator.count,
                'page': page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Failed to get batch groups: {e}", user_profile, exception=e)
        logger.error(f"Error getting batch groups: {e}", exc_info=True)
        return json_error(f"Failed to get batch groups: {str(e)}")


@require_realm_admin
@typed_endpoint
def lms_get_batch_details(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    batch_id: Json[int],
) -> JsonResponse:
    """Get detailed information for a single LMS batch.

    This powers the "View" action in the Batch Management tab.
    """
    try:
        realm = user_profile.realm

        try:
            batch = Batches.objects.using("lms_db").get(id=batch_id)
        except Batches.DoesNotExist:
            return json_error(f"Batch {batch_id} not found in LMS database")

        # Base student relationships for this batch
        batch_students_qs = Batchtostudent.objects.using("lms_db").filter(a_id=batch.id)

        # Student and mentor counts (reuse logic from lms_get_batch_groups)
        student_count = batch_students_qs.count()
        mentor_count = (
            Mentortostudent.objects.using("lms_db")
            .filter(
                # Mentortostudent schema uses `a` (mentor FK) and `b` (student FK)
                b_id__in=batch_students_qs.values("b_id")
            )
            .values("a_id")
            .distinct()
            .count()
        )

        # Fetch student details (limit to a reasonable number for UI)
        student_ids = batch_students_qs.values_list("b_id", flat=True)
        students = Students.objects.using("lms_db").filter(id__in=student_ids)[:200]
        students_data = []
        for student in students:
            full_name = getattr(student, "name", None) or " ".join(
                part
                for part in [
                    getattr(student, "first_name", None),
                    getattr(student, "last_name", None),
                ]
                if part
            ) or "Student"
            students_data.append(
                {
                    "name": full_name,
                    "email": getattr(student, "email", "") or "",
                    "status": "active" if getattr(student, "is_active", True) else "inactive",
                }
            )

        # Fetch mentor details (also limited)
        mentor_ids = (
            Mentortostudent.objects.using("lms_db")
            .filter(b_id__in=student_ids)
            .values_list("a_id", flat=True)
            .distinct()
        )
        mentors = Mentors.objects.using("lms_db").filter(user_id__in=mentor_ids)[:200]
        mentors_data = []
        for mentor in mentors:
            full_name = getattr(mentor, "name", None) or " ".join(
                part
                for part in [
                    getattr(mentor, "first_name", None),
                    getattr(mentor, "last_name", None),
                ]
                if part
            ) or "Mentor"
            mentors_data.append(
                {
                    "name": full_name,
                    "email": getattr(mentor, "email", "") or "",
                    "status": "active" if getattr(mentor, "is_active", True) else "inactive",
                }
            )

        batch_data = {
            "id": batch.id,
            "batch_name": batch.name,
            "description": getattr(batch, "description", None) or getattr(batch, "url", ""),
            "status": "active",
            "created_at": batch.created.isoformat() if getattr(batch, "created", None) else None,
            "last_sync": None,
            "zulip_group_exists": False,
            "zulip_group_name": None,
            "student_count": student_count,
            "mentor_count": mentor_count,
            # For now, treat active users as total students + mentors.
            "active_users_count": student_count + mentor_count,
            "last_activity": None,
            "students": students_data,
            "mentors": mentors_data,
        }

        log_admin_action(
            realm,
            "INFO",
            "admin_ui",
            f"Batch details requested for batch {batch_id}",
            user_profile,
        )

        return json_success(
            request,
            data={
                "batch": batch_data,
            },
        )

    except Exception as e:
        log_admin_action(
            user_profile.realm,
            "ERROR",
            "admin_ui",
            f"Failed to get batch details: {e}",
            user_profile,
            exception=e,
        )
        logger.error(f"Error getting batch details for {batch_id}: {e}", exc_info=True)
        return json_error(f"Failed to get batch details: {str(e)}")


@require_realm_admin
@typed_endpoint
def lms_sync_progress(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    sync_id: str,
) -> JsonResponse:
    """Get real-time progress for an ongoing sync operation."""
    try:
        realm = user_profile.realm

        # Get the progress record for this sync
        try:
            progress = LMSSyncProgress.objects.get(sync_id=sync_id, realm=realm)
        except LMSSyncProgress.DoesNotExist:
            return json_error(f"Sync operation {sync_id} not found")

        # Calculate progress percentage
        progress_percentage = progress.get_progress_percentage()

        # Prepare response data
        response_data = {
            'sync_id': progress.sync_id,
            'sync_type': progress.sync_type,
            'current_stage': progress.current_stage,
            'status_message': progress.status_message,
            'progress_percentage': progress_percentage,
            'total_records': progress.total_records,
            'processed_records': progress.processed_records,
            'created_count': progress.created_count,
            'updated_count': progress.updated_count,
            'skipped_count': progress.skipped_count,
            'error_count': progress.error_count,
            'started_at': progress.started_at.isoformat(),
            'updated_at': progress.updated_at.isoformat(),
            'is_active': progress.is_active(),
            'last_error': progress.last_error,
        }

        # If sync is complete, clean up the progress record after returning data
        if not progress.is_active():
            # Delete progress records older than 5 minutes to keep database clean
            from datetime import timedelta
            from django.utils import timezone
            cutoff_time = timezone.now() - timedelta(minutes=5)
            LMSSyncProgress.objects.filter(
                realm=realm,
                updated_at__lt=cutoff_time,
                current_stage__in=['completed', 'failed', 'cancelled']
            ).delete()

            # Also schedule this specific completed sync for cleanup after 30 seconds
            # This prevents the progress record from lingering and causing "sync in progress" errors
            # when users try to start a new sync immediately after completion
            if progress.updated_at < timezone.now() - timedelta(seconds=30):
                progress.delete()

        return json_success(request, data=response_data)

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Failed to get sync progress: {e}", user_profile, exception=e)
        logger.error(f"Error getting sync progress for {sync_id}: {e}", exc_info=True)
        return json_error(f"Failed to get sync progress: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint
def lms_stop_user_sync(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    sync_id: str,
) -> JsonResponse:
    """Stop/cancel an ongoing sync operation."""
    try:
        realm = user_profile.realm

        # Get the progress record for this sync
        try:
            progress = LMSSyncProgress.objects.get(sync_id=sync_id, realm=realm)
        except LMSSyncProgress.DoesNotExist:
            return json_error(f"Sync operation {sync_id} not found")

        # Check if sync is active
        if not progress.is_active():
            return json_error(f"Sync {sync_id} is not active (current stage: {progress.current_stage})")

        # Mark sync as cancelled
        with _sync_lock:
            progress.current_stage = 'cancelled'
            progress.status_message = 'Sync cancelled by user'
            progress.updated_at = timezone.now()
            progress.save(update_fields=['current_stage', 'status_message', 'updated_at'])

            # Update sync history if it exists
            # Find the most recent running sync for this realm
            try:
                sync_history = LMSSyncHistory.objects.filter(
                    realm=realm,
                    status='running'
                ).order_by('-started_at').first()

                # Also try to find by matching the progress record's started_at time
                if not sync_history:
                    sync_history = LMSSyncHistory.objects.filter(
                        realm=realm,
                        started_at__gte=progress.started_at - timedelta(seconds=5),
                        started_at__lte=progress.started_at + timedelta(seconds=5)
                    ).order_by('-started_at').first()

                if sync_history:
                    end_time = timezone.now()
                    duration = (end_time - sync_history.started_at).total_seconds()
                    sync_history.completed_at = end_time
                    sync_history.duration_seconds = duration
                    sync_history.status = 'cancelled'
                    sync_history.save()
            except Exception as e:
                logger.warning(f"Failed to update sync history for cancelled sync {sync_id}: {e}")

            # Remove from running syncs
            _running_syncs.pop(sync_id, None)

        log_admin_action(realm, 'INFO', 'user_sync', f"Cancelled sync {sync_id}", user_profile)
        logger.info(f"Sync {sync_id} cancelled by user {user_profile.id}")

        return json_success(
            request,
            data={
                'status': 'cancelled',
                'message': 'Sync has been cancelled',
                'sync_id': sync_id,
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'user_sync', f"Failed to stop sync: {e}", user_profile, exception=e)
        logger.error(f"Error stopping sync {sync_id}: {e}", exc_info=True)
        return json_error(f"Failed to stop sync: {str(e)}")


@require_realm_admin
@typed_endpoint_without_parameters
def lms_get_active_syncs(
    request: HttpRequest,
    user_profile: UserProfile,
) -> JsonResponse:
    """Get all active sync operations for the realm."""
    try:
        realm = user_profile.realm

        # Get all active sync operations for this realm
        active_syncs = LMSSyncProgress.objects.filter(
            realm=realm,
            current_stage__in=['initializing', 'counting_records', 'syncing_students',
                              'syncing_mentors', 'syncing_batches', 'updating_mappings', 'finalizing']
        ).order_by('-started_at')

        sync_data = []
        for sync in active_syncs:
            sync_data.append({
                'sync_id': sync.sync_id,
                'sync_type': sync.sync_type,
                'current_stage': sync.current_stage,
                'status_message': sync.status_message,
                'progress_percentage': sync.get_progress_percentage(),
                'started_at': sync.started_at.isoformat(),
                'triggered_by': sync.triggered_by.full_name if sync.triggered_by else None,
            })

        return json_success(
            request,
            data={
                'active_syncs': sync_data,
                'has_active_sync': len(sync_data) > 0,
            }
        )

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'admin_ui', f"Failed to get active syncs: {e}", user_profile, exception=e)
        logger.error(f"Error getting active syncs: {e}", exc_info=True)
        return json_error(f"Failed to get active syncs: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint
def lms_sync_single_batch(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    batch_id: Json[int],
) -> JsonResponse:
    """Sync a single LMS batch to Zulip.

    For now, this is implemented as a lightweight stub that validates the
    batch exists and returns zeroed stats, so the admin UI workflow works
    end-to-end without 404s. The actual per-batch sync logic can be added
    later by wiring this into a dedicated UserSync helper.
    """
    try:
        realm = user_profile.realm

        try:
            # Validate that the batch exists in the LMS database.
            Batches.objects.using("lms_db").get(id=batch_id)
        except Batches.DoesNotExist:
            return json_error(f"Batch {batch_id} not found in LMS database")

        # Placeholder stats for now; keep the shape expected by the frontend.
        stats = {
            "users_synced": 0,
            "groups_updated": 0,
        }

        log_admin_action(
            realm,
            "INFO",
            "user_sync",
            f"Single batch sync requested for batch {batch_id} (stub implementation)",
            user_profile,
            details={"batch_id": batch_id, "stats": stats},
        )

        return json_success(
            request,
            data={
                "stats": stats,
            },
        )

    except Exception as e:
        log_admin_action(
            user_profile.realm,
            "ERROR",
            "user_sync",
            f"Failed to sync batch {batch_id}: {e}",
            user_profile,
            exception=e,
        )
        logger.error(f"Error syncing batch {batch_id}: {e}", exc_info=True)
        return json_error(f"Failed to sync batch: {str(e)}")


@csrf_exempt
@require_post
def lms_jwt_auth_api(request: HttpRequest) -> JsonResponse:
    """JWT auth API: returns Zulip API key for a valid LMS JWT token."""
    try:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            raise JsonableError("Malformed JSON")

        token = payload.get("token")
        include_profile = bool(payload.get("include_profile", False))

        if not token:
            raise JsonableError("Missing 'token' parameter")

        realm = get_valid_realm_from_request(request)

        return_data: Dict[str, Any] = {}
        user = authenticate(
            request=request,
            username="lms-jwt-auth",  # used only for rate limiting/logging
            testpress_jwt_token=token,
            realm=realm,
            return_data=return_data,
        )

        if user is None:
            # Surface a generic error without leaking internal details; log has full context.
            # `return_data` is logged by the auth backend for debugging.
            return json_error("JWT authentication failed")

        data: Dict[str, Any] = {
            "api_key": user.api_key,
            "email": user.delivery_email,
            "user_id": user.id,
            "full_name": user.full_name,
        }
        if include_profile:
            data["role"] = user.role

        return json_success(request, data=data)
    except JsonableError as e:
        return json_error(str(e))
    except Exception as e:
        logger.error(f"Error in lms_jwt_auth_api: {e}", exc_info=True)
        return json_error("Internal server error while processing JWT auth")


@csrf_exempt
@require_post
def lms_jwt_web_login(request: HttpRequest) -> JsonResponse:
    """JWT web login: logs the user in and returns a redirect URL."""
    try:
        try:
            payload = json.loads(request.body.decode("utf-8"))
        except json.JSONDecodeError:
            raise JsonableError("Malformed JSON")

        token = payload.get("token")
        if not token:
            raise JsonableError("Missing 'token' parameter")

        realm = get_valid_realm_from_request(request)

        return_data: Dict[str, Any] = {}
        user = authenticate(
            request=request,
            username="lms-jwt-web-login",  # used only for rate limiting/logging
            testpress_jwt_token=token,
            realm=realm,
            return_data=return_data,
        )

        if user is None:
            # Generic error; detailed reason is available in server logs via `return_data`.
            return json_error("JWT authentication failed")

        # Create Django session
        do_login(request, user)

        return json_success(
            request,
            data={
                "message": "Login successful",
                "user_id": user.id,
                "email": user.delivery_email,
                "full_name": user.full_name,
                "redirect_url": "/",
            },
        )
    except JsonableError as e:
        return json_error(str(e))
    except Exception as e:
        logger.error(f"Error in lms_jwt_web_login: {e}", exc_info=True)
        return json_error("Internal server error while processing JWT web login")


# ===================================
# PLACEHOLDER EMAIL MANAGEMENT ENDPOINTS
# ===================================

@require_realm_admin
@typed_endpoint
def lms_get_placeholder_users(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    page: Json[int] = 1,
) -> JsonResponse:
    """Get list of users with placeholder emails."""
    try:
        realm = user_profile.realm

        # Import placeholder email utilities
        from lms_integration.lib.email_utils import is_placeholder_email, get_placeholder_email_stats
        from lms_integration.settings import LMS_NO_EMAIL_DOMAIN

        # Get placeholder email statistics
        stats = get_placeholder_email_stats(realm)

        # Get users with placeholder emails
        placeholder_users = UserProfile.objects.filter(
            realm=realm,
            is_active=True,
            delivery_email__endswith=f"@{LMS_NO_EMAIL_DOMAIN}"
        ).order_by('full_name')

        # Paginate
        paginator = Paginator(placeholder_users, 50)
        page_obj = paginator.get_page(page)

        users_data = []
        for user in page_obj:
            # Extract username from placeholder email
            username = user.delivery_email.split('@')[0]

            # Try to determine user type by checking LMS mappings
            user_type = 'unknown'
            lms_id = None
            last_sync = None

            try:
                mapping = LMSUserMapping.objects.get(zulip_user=user)
                user_type = mapping.lms_user_type
                lms_id = mapping.lms_user_id
                last_sync = mapping.last_synced_at.isoformat() if mapping.last_synced_at else None
            except LMSUserMapping.DoesNotExist:
                pass

            users_data.append({
                'id': user.id,
                'name': user.full_name,
                'username': username,
                'placeholder_email': user.delivery_email,
                'type': user_type,
                'lms_id': lms_id,
                'last_sync': last_sync,
                'date_joined': user.date_joined.isoformat(),
            })

        return json_success(
            request,
            data={
                'users': users_data,
                'total_count': paginator.count,
                'page': page,
                'total_pages': paginator.num_pages,
                'has_next': page_obj.has_next(),
                'has_previous': page_obj.has_previous(),
                'email_coverage': stats.get('placeholder_percentage', 0),
            }
        )

    except Exception as e:
        logger.error(f"Error getting placeholder users: {e}", exc_info=True)
        return json_error(f"Failed to get placeholder users: {str(e)}")


@require_realm_admin
@typed_endpoint_without_parameters
def lms_get_placeholder_stats(
    request: HttpRequest,
    user_profile: UserProfile,
) -> JsonResponse:
    """Get placeholder email statistics."""
    try:
        realm = user_profile.realm

        from lms_integration.lib.email_utils import get_placeholder_email_stats

        stats = get_placeholder_email_stats(realm)

        # Calculate notification coverage
        notification_stats = {
            'total_users': stats['total_users'],
            'users_with_email_notifications': stats['real_email_users'],
            'users_without_email_notifications': stats['placeholder_users'],
            'email_notification_coverage': round(
                (stats['real_email_users'] / stats['total_users'] * 100) if stats['total_users'] > 0 else 0,
                1
            )
        }

        return json_success(request, data=notification_stats)

    except Exception as e:
        logger.error(f"Error getting placeholder stats: {e}", exc_info=True)
        return json_error(f"Failed to get placeholder stats: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint
def lms_update_user_email(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    user_id: Json[int],
    new_email: str,
) -> JsonResponse:
    """Update a single user's email address."""
    try:
        realm = user_profile.realm

        # Get the user to update
        try:
            target_user = UserProfile.objects.get(id=user_id, realm=realm)
        except UserProfile.DoesNotExist:
            return json_error("User not found")

        # Validate new email
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError

        try:
            validate_email(new_email)
        except ValidationError:
            return json_error("Invalid email format")

        # Check if email is already in use
        existing_user = UserProfile.objects.filter(
            realm=realm,
            delivery_email=new_email
        ).exclude(id=user_id).first()

        if existing_user:
            return json_error("Email address already in use by another user")

        # Update email
        old_email = target_user.delivery_email
        target_user.delivery_email = new_email
        target_user.email = new_email
        target_user.save(update_fields=['delivery_email', 'email'])

        log_admin_action(
            realm, 'INFO', 'email_update',
            f"Updated user email: {old_email} -> {new_email}",
            user_profile,
            details={'user_id': user_id, 'old_email': old_email, 'new_email': new_email}
        )

        return json_success(
            request,
            data={
                'message': f'Email updated successfully for {target_user.full_name}',
                'old_email': old_email,
                'new_email': new_email,
            }
        )

    except Exception as e:
        logger.error(f"Error updating user email: {e}", exc_info=True)
        return json_error(f"Failed to update email: {str(e)}")


@require_realm_admin
@require_post
@typed_endpoint
def lms_bulk_update_emails(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    email_updates: Json[list],
    validate_only: Json[bool] = False,
) -> JsonResponse:
    """Bulk update user emails from a list of username,email pairs."""
    try:
        realm = user_profile.realm

        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        from lms_integration.lib.email_utils import generate_placeholder_email
        from lms_integration.settings import LMS_NO_EMAIL_DOMAIN

        stats = {
            'valid': 0,
            'invalid': 0,
            'not_found': 0,
            'updated': 0,
            'errors': 0,
        }

        results = []

        for update in email_updates:
            username = update.get('username', '').strip()
            email = update.get('email', '').strip()

            if not username or not email:
                stats['invalid'] += 1
                results.append({
                    'username': username,
                    'email': email,
                    'status': 'error',
                    'message': 'Username and email are required'
                })
                continue

            # Validate email format
            try:
                validate_email(email)
            except ValidationError:
                stats['invalid'] += 1
                results.append({
                    'username': username,
                    'email': email,
                    'status': 'error',
                    'message': 'Invalid email format'
                })
                continue

            # Find user with placeholder email based on username
            placeholder_email = generate_placeholder_email(username)
            try:
                target_user = UserProfile.objects.get(
                    realm=realm,
                    delivery_email__iexact=placeholder_email
                )
            except UserProfile.DoesNotExist:
                stats['not_found'] += 1
                results.append({
                    'username': username,
                    'email': email,
                    'status': 'error',
                    'message': f'User with placeholder email {placeholder_email} not found'
                })
                continue

            # Check if new email is already in use
            existing_user = UserProfile.objects.filter(
                realm=realm,
                delivery_email=email
            ).exclude(id=target_user.id).first()

            if existing_user:
                stats['invalid'] += 1
                results.append({
                    'username': username,
                    'email': email,
                    'status': 'error',
                    'message': 'Email already in use by another user'
                })
                continue

            stats['valid'] += 1

            if not validate_only:
                try:
                    # Update email
                    target_user.delivery_email = email
                    target_user.email = email
                    target_user.save(update_fields=['delivery_email', 'email'])
                    stats['updated'] += 1

                    results.append({
                        'username': username,
                        'email': email,
                        'status': 'success',
                        'message': 'Email updated successfully'
                    })

                except Exception as e:
                    stats['errors'] += 1
                    results.append({
                        'username': username,
                        'email': email,
                        'status': 'error',
                        'message': f'Update failed: {str(e)}'
                    })
            else:
                results.append({
                    'username': username,
                    'email': email,
                    'status': 'valid',
                    'message': 'Validation passed'
                })

        log_admin_action(
            realm, 'INFO', 'bulk_email_update',
            f"Bulk email update: {stats['updated']} updated, {stats['errors']} errors",
            user_profile,
            details={'stats': stats, 'validate_only': validate_only}
        )

        return json_success(
            request,
            data={
                'stats': stats,
                'results': results[:10] if len(results) > 10 else results,  # Limit results for response size
                'total_processed': len(email_updates),
            }
        )

    except Exception as e:
        logger.error(f"Error in bulk email update: {e}", exc_info=True)
        return json_error(f"Bulk email update failed: {str(e)}")


@require_realm_admin
@typed_endpoint_without_parameters
def lms_export_placeholder_users(
    request: HttpRequest,
    user_profile: UserProfile,
) -> JsonResponse:
    """Export placeholder users as CSV data."""
    try:
        realm = user_profile.realm

        from lms_integration.settings import LMS_NO_EMAIL_DOMAIN
        import csv
        import io

        # Get users with placeholder emails
        placeholder_users = UserProfile.objects.filter(
            realm=realm,
            is_active=True,
            delivery_email__endswith=f"@{LMS_NO_EMAIL_DOMAIN}"
        ).order_by('full_name')

        # Generate CSV data
        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        writer.writerow(['Username', 'Full Name', 'Placeholder Email', 'Type', 'LMS ID', 'Date Joined'])

        # Write user data
        for user in placeholder_users:
            username = user.delivery_email.split('@')[0]

            # Try to get user type from LMS mapping
            user_type = 'unknown'
            lms_id = ''
            try:
                mapping = LMSUserMapping.objects.get(zulip_user=user)
                user_type = mapping.lms_user_type
                lms_id = str(mapping.lms_user_id)
            except LMSUserMapping.DoesNotExist:
                pass

            writer.writerow([
                username,
                user.full_name,
                user.delivery_email,
                user_type,
                lms_id,
                user.date_joined.strftime('%Y-%m-%d %H:%M:%S')
            ])

        csv_content = output.getvalue()
        output.close()

        log_admin_action(
            realm, 'INFO', 'export',
            f"Exported {placeholder_users.count()} placeholder users",
            user_profile
        )

        return json_success(
            request,
            data={
                'csv_content': csv_content,
                'filename': f'placeholder_users_{realm.string_id}_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv',
                'user_count': placeholder_users.count(),
            }
        )

    except Exception as e:
        logger.error(f"Error exporting placeholder users: {e}", exc_info=True)
        return json_error(f"Failed to export users: {str(e)}")
