"""
LMS Integration API Views
REST API endpoints for LMS integration, including webhook for new user creation.
"""

import logging
import json
from typing import Dict, Any
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils.decorators import method_decorator

from lms_integration.lib.user_sync import UserSync
from lms_integration.models import Students, Mentors

logger = logging.getLogger(__name__)


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
