"""
User filtering logic for role-based DM permissions.

This module provides functions to filter users based on role-based permission
matrices configured by realm administrators.
"""

from typing import List

from django.db import models

from zerver.models import Realm, UserProfile

from lms_integration.models import (
    LMSUserMapping,
    Mentortostudent,
    Batchtostudent,
    RealmDMPermissionMatrix,
)
from lms_integration.permission_utils import ALL_ROLES, get_default_permission_matrix


def get_user_role(user_profile: UserProfile, realm: Realm) -> str:
    """
    Determine the effective role of a user.
    
    LMS roles (mentor, student) take precedence over Zulip roles.
    If no LMS mapping exists, returns the Zulip role.
    
    Returns one of: 'owner', 'admin', 'moderator', 'member', 'guest', 'mentor', 'student'
    """
    # Check for LMS role first (takes precedence)
    try:
        lms_mapping = LMSUserMapping.objects.filter(
            zulip_user=user_profile,
            is_active=True
        ).first()
        
        if lms_mapping and lms_mapping.lms_user_type in ['mentor', 'student']:
            return lms_mapping.lms_user_type
    except Exception:
        # If LMS mapping check fails, fall through to Zulip role
        pass
    
    # Return Zulip role
    if user_profile.is_realm_owner:
        return 'owner'
    elif user_profile.is_realm_admin:
        return 'admin'
    elif user_profile.is_moderator:
        return 'moderator'
    elif user_profile.is_guest:
        return 'guest'
    else:
        return 'member'


def get_allowed_target_roles(source_role: str, realm: Realm) -> List[str]:
    """
    Get list of roles that the source_role can see/DM based on permission matrix.
    
    Returns list of allowed target role names, or empty list if no permissions.
    Owners and admins always have access to everyone (not configurable).
    """
    # Owners and admins always have access to everyone
    if source_role in ['owner', 'admin']:
        return ALL_ROLES
    
    # Check if feature is enabled
    try:
        permission_matrix = RealmDMPermissionMatrix.objects.filter(realm=realm).first()
        if not permission_matrix or not permission_matrix.enabled:
            # Feature disabled - return all roles (no filtering)
            return ALL_ROLES
        
        # Get allowed roles from matrix
        allowed_roles = list(permission_matrix.permission_matrix.get(source_role, []))
        
        # Always allow seeing admins and owners (for security/contact purposes)
        if 'admin' not in allowed_roles:
            allowed_roles.append('admin')
        if 'owner' not in allowed_roles:
            allowed_roles.append('owner')
        
        return allowed_roles
    except Exception:
        # On error, return all roles (fail open for safety)
        return ALL_ROLES


def get_mentor_filtered_user_ids(
    user_profile: UserProfile,
    realm: Realm,
    *,
    allowed_roles: List[str] | None = None,
) -> List[int]:
    """
    Get filtered user IDs for a mentor user.
    
    Returns IDs of:
    - Other mentors
    - Direct students (via Mentortostudent)
    - Students in batches where the mentor has students
    - Admins and owners (always visible)
    """
    try:
        # Get mentor's LMS ID
        lms_mapping = LMSUserMapping.objects.filter(
            zulip_user=user_profile,
            lms_user_type='mentor',
            is_active=True
        ).first()
        
        if not lms_mapping:
            # Not a mentor, return empty list
            return []
        
        mentor_lms_id = lms_mapping.lms_user_id
        
        # Get allowed target roles from permission matrix if not provided
        if allowed_roles is None:
            allowed_roles = get_allowed_target_roles('mentor', realm)
        
        user_ids = set()
        
        # Always include admins and owners
        admin_owners = UserProfile.objects.filter(
            realm=realm,
            is_active=True
        ).filter(
            models.Q(role=UserProfile.ROLE_REALM_OWNER) |
            models.Q(role=UserProfile.ROLE_REALM_ADMINISTRATOR)
        ).values_list('id', flat=True)
        user_ids.update(admin_owners)
        
        # Include other mentors if allowed
        if 'mentor' in allowed_roles:
            other_mentors = LMSUserMapping.objects.filter(
                realm=realm,
                lms_user_type='mentor',
                is_active=True
            ).exclude(zulip_user=user_profile).values_list('zulip_user_id', flat=True)
            user_ids.update(other_mentors)
        
        # Include students if allowed
        if 'student' in allowed_roles:
            # Get direct students
            direct_student_ids = Mentortostudent.objects.using('lms_db').filter(
                a_id=mentor_lms_id
            ).values_list('b_id', flat=True)
            
            # Get batches where mentor has students
            batch_ids = Batchtostudent.objects.using('lms_db').filter(
                b_id__in=direct_student_ids
            ).values_list('a_id', flat=True).distinct()
            
            # Get all students in those batches assigned to this mentor
            batch_student_ids = Batchtostudent.objects.using('lms_db').filter(
                a_id__in=batch_ids,
                b_id__in=direct_student_ids
            ).values_list('b_id', flat=True).distinct()
            
            # Combine direct and batch students
            all_student_ids = set(direct_student_ids) | set(batch_student_ids)
            
            # Map LMS student IDs to Zulip user IDs
            student_mappings = LMSUserMapping.objects.filter(
                lms_user_id__in=all_student_ids,
                lms_user_type='student',
                is_active=True,
                zulip_user__realm=realm
            ).values_list('zulip_user_id', flat=True)
            
            user_ids.update(student_mappings)
        
        return list(user_ids)
    except Exception:
        # On error, return empty list (fail secure)
        return []


def get_student_filtered_user_ids(
    user_profile: UserProfile,
    realm: Realm,
    *,
    allowed_roles: List[str] | None = None,
) -> List[int]:
    """
    Get filtered user IDs for a student user.
    
    Returns IDs of:
    - Assigned mentors only (via Mentortostudent)
    - Admins and owners (always visible)
    """
    try:
        # Get student's LMS ID
        lms_mapping = LMSUserMapping.objects.filter(
            zulip_user=user_profile,
            lms_user_type='student',
            is_active=True
        ).first()
        
        if not lms_mapping:
            # Not a student, return empty list
            return []
        
        student_lms_id = lms_mapping.lms_user_id
        
        # Get allowed target roles from permission matrix if not provided
        if allowed_roles is None:
            allowed_roles = get_allowed_target_roles('student', realm)
        
        user_ids = set()
        
        # Always include admins and owners
        admin_owners = UserProfile.objects.filter(
            realm=realm,
            is_active=True
        ).filter(
            models.Q(role=UserProfile.ROLE_REALM_OWNER) |
            models.Q(role=UserProfile.ROLE_REALM_ADMINISTRATOR)
        ).values_list('id', flat=True)
        user_ids.update(admin_owners)
        
        # Include assigned mentors if allowed
        if 'mentor' in allowed_roles:
            # Get assigned mentor LMS IDs
            mentor_lms_ids = Mentortostudent.objects.using('lms_db').filter(
                b_id=student_lms_id
            ).values_list('a_id', flat=True)
            
            # Map LMS mentor IDs to Zulip user IDs
            mentor_mappings = LMSUserMapping.objects.filter(
                lms_user_id__in=mentor_lms_ids,
                lms_user_type='mentor',
                is_active=True,
                zulip_user__realm=realm
            ).values_list('zulip_user_id', flat=True)
            
            user_ids.update(mentor_mappings)
        
        return list(user_ids)
    except Exception:
        # On error, return empty list (fail secure)
        return []


def get_filtered_user_ids_by_role(user_profile: UserProfile, realm: Realm) -> List[int] | None:
    """
    Return filtered user IDs based on permission matrix, or None for no filtering.
    
    This is the main entry point for role-based filtering.
    Returns None if:
    - Feature is disabled for non-LMS roles
    - User has no role mapping
    - Error occurs (fail open)
    
    Returns list of user IDs if filtering should be applied.
    """
    try:
        permission_matrix = RealmDMPermissionMatrix.objects.filter(realm=realm).first()
        
        # Get user's effective role (may be LMS-based)
        user_role = get_user_role(user_profile, realm)
        
        # Owners and admins are not filtered (they see everyone)
        if user_role in ['owner', 'admin']:
            return None
        
        # For LMS roles (mentor/student), always apply specialized filtering,
        # even if the permission matrix row is missing or disabled.
        if user_role in ('mentor', 'student'):
            if permission_matrix and permission_matrix.enabled:
                allowed_roles = get_allowed_target_roles(user_role, realm)
            else:
                # Fall back to default matrix when no custom matrix is configured.
                default_matrix = get_default_permission_matrix()
                allowed_roles = list(default_matrix.get(user_role, []))
            
            # If all roles are allowed, no filtering needed
            if set(allowed_roles) >= set(ALL_ROLES):
                return None
            
            if user_role == 'mentor':
                return get_mentor_filtered_user_ids(
                    user_profile,
                    realm,
                    allowed_roles=allowed_roles,
                )
            else:
                return get_student_filtered_user_ids(
                    user_profile,
                    realm,
                    allowed_roles=allowed_roles,
                )
        
        # For non-LMS roles:
        # - If the feature is disabled, or no matrix exists, do not filter.
        # - If enabled, we currently do not implement generic filtering beyond
        #   the mentor/student logic, so fail open (no filtering) unless we add it.
        if not permission_matrix or not permission_matrix.enabled:
            return None
        
        # Get allowed target roles
        allowed_roles = get_allowed_target_roles(user_role, realm)
        
        # If all roles are allowed, no filtering needed
        if set(allowed_roles) >= set(ALL_ROLES):
            return None
        
        # Moderator/member/guest (Zulip roles with no LMS mapping): no matrix entry,
        # no specialized filtering implemented yet. They rely on standard Zulip
        # visibility plus this matrix check. Returning None here means they see
        # everyone until generic filtering is implemented.
        
        return None
    except Exception:
        # On error, return None (fail open - no filtering)
        return None

