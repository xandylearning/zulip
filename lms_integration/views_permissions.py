"""
API views for managing role-based DM permission matrix.

Provides endpoints for realm administrators to configure which roles
can see and direct message other roles.
"""

import logging
from typing import Dict, Any

from django.http import HttpRequest, HttpResponse
from django.db import transaction

from zerver.decorator import require_realm_admin
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success, json_error
from zerver.lib.typed_endpoint import typed_endpoint, typed_endpoint_without_parameters
from zerver.models import UserProfile, Realm
from pydantic import Json

from lms_integration.models import RealmDMPermissionMatrix

logger = logging.getLogger(__name__)

# Valid role names
VALID_ROLES = ['owner', 'admin', 'moderator', 'member', 'guest', 'mentor', 'student']


@require_realm_admin
@typed_endpoint_without_parameters
def get_dm_permissions(
    request: HttpRequest,
    user_profile: UserProfile,
) -> HttpResponse:
    """
    GET /api/v1/lms/dm-permissions
    
    Get the current DM permission matrix configuration for the realm.
    """
    try:
        permission_matrix, _ = RealmDMPermissionMatrix.objects.get_or_create(
            realm=user_profile.realm,
            defaults={'enabled': False, 'permission_matrix': {}}
        )
        
        return json_success(request, {
            'enabled': permission_matrix.enabled,
            'permission_matrix': permission_matrix.permission_matrix,
            'updated_at': permission_matrix.updated_at.isoformat() if permission_matrix.updated_at else None,
            'updated_by': permission_matrix.updated_by_id,
        })
    except Exception as e:
        logger.error(f"Error getting DM permissions: {e}", exc_info=True)
        return json_error(request, "Failed to retrieve permission matrix")


@require_realm_admin
@typed_endpoint
def update_dm_permissions(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    enabled: Json[bool] | None = None,
    permission_matrix: Json[Dict[str, list[str]]] | None = None,
) -> HttpResponse:
    """
    PATCH /api/v1/lms/dm-permissions
    
    Update the DM permission matrix configuration for the realm.
    
    Parameters:
    - enabled: Boolean to enable/disable the feature
    - permission_matrix: Dict mapping source roles to lists of allowed target roles
                        Format: {"mentor": ["admin", "mentor", "student"], ...}
    """
    try:
        with transaction.atomic():
            permission_matrix_obj, created = RealmDMPermissionMatrix.objects.get_or_create(
                realm=user_profile.realm,
                defaults={'enabled': False, 'permission_matrix': {}}
            )
            
            # Update enabled status if provided
            if enabled is not None:
                permission_matrix_obj.enabled = enabled
            
            # Update permission matrix if provided
            if permission_matrix is not None:
                # Validate the permission matrix structure
                validated_matrix = {}
                for source_role, target_roles in permission_matrix.items():
                    if source_role not in VALID_ROLES:
                        raise JsonableError(f"Invalid source role: {source_role}")
                    
                    if not isinstance(target_roles, list):
                        raise JsonableError(f"Target roles for {source_role} must be a list")
                    
                    validated_target_roles = []
                    for target_role in target_roles:
                        if target_role not in VALID_ROLES:
                            raise JsonableError(f"Invalid target role: {target_role}")
                        validated_target_roles.append(target_role)
                    
                    validated_matrix[source_role] = validated_target_roles
                
                permission_matrix_obj.permission_matrix = validated_matrix
            
            # Update audit fields
            permission_matrix_obj.updated_by = user_profile
            permission_matrix_obj.save()
            
            logger.info(
                f"DM permission matrix updated for realm {user_profile.realm.id} "
                f"by user {user_profile.id}"
            )
            
            return json_success(request, {
                'enabled': permission_matrix_obj.enabled,
                'permission_matrix': permission_matrix_obj.permission_matrix,
                'updated_at': permission_matrix_obj.updated_at.isoformat(),
            })
    except JsonableError:
        raise
    except Exception as e:
        logger.error(f"Error updating DM permissions: {e}", exc_info=True)
        return json_error(request, "Failed to update permission matrix")

