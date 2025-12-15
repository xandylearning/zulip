"""
LMS Integration API Views
REST API endpoints for LMS integration, including webhook for new user creation.
"""

import logging
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils.decorators import method_decorator
from django.core.paginator import Paginator
from django.db import connections, DatabaseError, models
from django.contrib.auth.models import User
from django.utils import timezone

from zerver.decorator import require_realm_admin, require_post
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.lib.response import json_success, json_error
from zerver.models import UserProfile, Realm
from pydantic import Json

from lms_integration.lib.user_sync import UserSync
from lms_integration.lib.activity_monitor import ActivityMonitor
from lms_integration.models import (
    Students, Mentors, Batches, Coursebatch, Batchtostudent, Mentortostudent,
    LMSActivityEvent, LMSEventLog, LMSIntegrationConfig, LMSSyncHistory,
    LMSAdminLog, LMSUserMapping
)

logger = logging.getLogger(__name__)


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
            total_mentors = Mentors.objects.using('lms_db').filter(is_active=True).count()
            total_batches = Batches.objects.using('lms_db').filter(is_active=True).count()
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
    sync_batches: bool = True,
) -> JsonResponse:
    """Start user synchronization from LMS to Zulip."""
    start_time = timezone.now()
    realm = user_profile.realm

    try:
        config = get_or_create_lms_config(realm)
        if not config.enabled:
            return json_error("LMS integration is not enabled for this realm")

        # Create sync history entry
        sync_history = LMSSyncHistory.objects.create(
            realm=realm,
            sync_type=sync_type,
            started_at=start_time,
            completed_at=start_time,  # Will be updated later
            duration_seconds=0,
            triggered_by=user_profile,
            trigger_type='manual',
            batch_sync_enabled=sync_batches,
        )

        user_sync = UserSync()
        stats = {
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }

        batch_stats = {'synced': 0}
        batch_error = None

        try:
            if sync_type == 'all':
                # Sync both students and mentors
                log_admin_action(realm, 'INFO', 'user_sync', "Starting sync of all users", user_profile)

                student_stats = user_sync.sync_all_students()
                mentor_stats = user_sync.sync_all_mentors()

                stats['created'] = student_stats.get('created', 0) + mentor_stats.get('created', 0)
                stats['updated'] = student_stats.get('updated', 0) + mentor_stats.get('updated', 0)
                stats['skipped'] = student_stats.get('skipped', 0) + mentor_stats.get('skipped', 0)
                stats['errors'] = student_stats.get('errors', 0) + mentor_stats.get('errors', 0)

            elif sync_type == 'students':
                log_admin_action(realm, 'INFO', 'user_sync', "Starting sync of students only", user_profile)
                student_stats = user_sync.sync_all_students()
                stats.update(student_stats)

            elif sync_type == 'mentors':
                log_admin_action(realm, 'INFO', 'user_sync', "Starting sync of mentors only", user_profile)
                mentor_stats = user_sync.sync_all_mentors()
                stats.update(mentor_stats)
            else:
                return json_error("Invalid sync_type. Must be 'all', 'students', or 'mentors'")

            # Sync batches if requested
            if sync_batches:
                try:
                    log_admin_action(realm, 'INFO', 'user_sync', "Starting batch sync", user_profile)
                    batch_stats = user_sync.sync_batches_and_groups()
                except Exception as e:
                    batch_error = str(e)
                    log_admin_action(realm, 'WARNING', 'user_sync', f"Batch sync failed: {e}", user_profile, exception=e)

            # Update sync history
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()

            sync_history.users_created = stats['created']
            sync_history.users_updated = stats['updated']
            sync_history.users_skipped = stats['skipped']
            sync_history.users_errors = stats['errors']
            sync_history.batches_synced = batch_stats.get('synced', 0)
            sync_history.batch_sync_error = batch_error
            sync_history.completed_at = end_time
            sync_history.duration_seconds = duration
            sync_history.status = 'success' if stats['errors'] == 0 else 'partial'
            sync_history.save()

            # Update user mappings
            update_user_mappings(realm)

            success_message = f"Sync completed: {stats['created']} created, {stats['updated']} updated, {stats['skipped']} skipped"
            if stats['errors'] > 0:
                success_message += f", {stats['errors']} errors"

            log_admin_action(realm, 'INFO', 'user_sync', success_message, user_profile, details=stats)

            return json_success(
                request,
                data={
                    'status': 'success',
                    'message': success_message,
                    'stats': {
                        **stats,
                        'batches_synced': batch_stats.get('synced', 0),
                        'batch_sync_error': batch_error,
                        'start_time': start_time.isoformat(),
                        'end_time': end_time.isoformat(),
                        'duration_seconds': duration,
                    }
                }
            )

        except Exception as e:
            # Update sync history with error
            end_time = timezone.now()
            duration = (end_time - start_time).total_seconds()

            sync_history.completed_at = end_time
            sync_history.duration_seconds = duration
            sync_history.status = 'failed'
            sync_history.error_message = str(e)
            sync_history.save()

            raise e

    except Exception as e:
        log_admin_action(realm, 'ERROR', 'user_sync', f"User sync failed: {e}", user_profile, exception=e)
        logger.error(f"Error during user sync: {e}", exc_info=True)
        return json_error(f"User sync failed: {str(e)}")


def update_user_mappings(realm: Realm) -> None:
    """Update user mappings for tracking purposes."""
    try:
        # Get all active Zulip users in the realm
        zulip_users = UserProfile.objects.filter(realm=realm, is_active=True)

        for zulip_user in zulip_users:
            # Try to find corresponding LMS user based on email
            try:
                # Try to find student
                student = Students.objects.using('lms_db').filter(
                    email=zulip_user.email,
                    is_active=True
                ).first()

                if student:
                    mapping, created = LMSUserMapping.objects.update_or_create(
                        zulip_user=zulip_user,
                        defaults={
                            'lms_user_id': student.id,
                            'lms_user_type': 'student',
                            'lms_username': student.username,
                            'is_active': True,
                            'last_error': None,
                        }
                    )
                    if not created:
                        mapping.sync_count += 1
                        mapping.save()
                    continue

                # Try to find mentor
                mentor = Mentors.objects.using('lms_db').filter(
                    email=zulip_user.email,
                    is_active=True
                ).first()

                if mentor:
                    mapping, created = LMSUserMapping.objects.update_or_create(
                        zulip_user=zulip_user,
                        defaults={
                            'lms_user_id': mentor.user_id,
                            'lms_user_type': 'mentor',
                            'lms_username': mentor.username,
                            'is_active': True,
                            'last_error': None,
                        }
                    )
                    if not created:
                        mapping.sync_count += 1
                        mapping.save()

            except Exception as e:
                # Update mapping with error
                mapping, created = LMSUserMapping.objects.get_or_create(
                    zulip_user=zulip_user,
                    defaults={
                        'lms_user_id': 0,
                        'lms_user_type': 'student',
                        'lms_username': '',
                        'is_active': False,
                        'last_error': str(e),
                    }
                )
                if not created:
                    mapping.last_error = str(e)
                    mapping.save()

    except Exception as e:
        logger.error(f"Error updating user mappings: {e}")


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
    lms_enabled: Optional[bool] = None,
    lms_db_host: Optional[str] = None,
    lms_db_port: Optional[int] = None,
    lms_db_name: Optional[str] = None,
    lms_db_username: Optional[str] = None,
    lms_db_password: Optional[str] = None,
    webhook_secret: Optional[str] = None,
    jwt_enabled: Optional[bool] = None,
    testpress_api_url: Optional[str] = None,
    activity_monitor_enabled: Optional[bool] = None,
    poll_interval: Optional[int] = None,
    notify_mentors: Optional[bool] = None,
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
                student_count = Batchtostudent.objects.using('lms_db').filter(
                    batch_id=batch.id
                ).count()

                # Count mentors for students in this batch
                mentor_count = Mentortostudent.objects.using('lms_db').filter(
                    student_id__in=Batchtostudent.objects.using('lms_db').filter(
                        batch_id=batch.id
                    ).values('student_id')
                ).values('mentor_id').distinct().count()

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
