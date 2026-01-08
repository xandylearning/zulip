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
        return ['owner', 'admin', 'moderator', 'member', 'guest', 'mentor', 'student']
    
    # Check if feature is enabled
    try:
        permission_matrix = RealmDMPermissionMatrix.objects.filter(realm=realm).first()
        if not permission_matrix or not permission_matrix.enabled:
            # Feature disabled - return all roles (no filtering)
            return ['owner', 'admin', 'moderator', 'member', 'guest', 'mentor', 'student']
        
        # Get allowed roles from matrix
        allowed_roles = permission_matrix.permission_matrix.get(source_role, [])
        
        # Always allow seeing admins and owners (for security/contact purposes)
        if 'admin' not in allowed_roles:
            allowed_roles.append('admin')
        if 'owner' not in allowed_roles:
            allowed_roles.append('owner')
        
        return allowed_roles
    except Exception:
        # On error, return all roles (fail open for safety)
        return ['owner', 'admin', 'moderator', 'member', 'guest', 'mentor', 'student']


def get_mentor_filtered_user_ids(user_profile: UserProfile, realm: Realm) -> List[int]:
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
        
        # Get allowed target roles from permission matrix
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


def get_student_filtered_user_ids(user_profile: UserProfile, realm: Realm) -> List[int]:
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
        
        # Get allowed target roles from permission matrix
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
    - Feature is disabled
    - User has no role mapping
    - Error occurs (fail open)
    
    Returns list of user IDs if filtering should be applied.
    """
    try:
        # Check if feature is enabled
        permission_matrix = RealmDMPermissionMatrix.objects.filter(realm=realm).first()
        if not permission_matrix or not permission_matrix.enabled:
            return None
        
        # Get user's role
        user_role = get_user_role(user_profile, realm)
        
        # Owners and admins are not filtered (they see everyone)
        if user_role in ['owner', 'admin']:
            return None
        
        # Get allowed target roles
        allowed_roles = get_allowed_target_roles(user_role, realm)
        
        # If all roles are allowed, no filtering needed
        all_roles = ['owner', 'admin', 'moderator', 'member', 'guest', 'mentor', 'student']
        if set(allowed_roles) == set(all_roles):
            return None
        
        # For LMS roles (mentor/student), use specialized filtering
        if user_role == 'mentor':
            return get_mentor_filtered_user_ids(user_profile, realm)
        elif user_role == 'student':
            return get_student_filtered_user_ids(user_profile, realm)
        
        # For Zulip roles (moderator, member, guest), filter by role
        # Get all users with allowed roles
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
        
        # Include users with allowed Zulip roles
        if 'moderator' in allowed_roles:
            moderators = UserProfile.objects.filter(
                realm=realm,
                is_active=True,
                role=UserProfile.ROLE_MODERATOR
            ).values_list('id', flat=True)
            user_ids.update(moderators)
        
        if 'member' in allowed_roles:
            members = UserProfile.objects.filter(
                realm=realm,
                is_active=True,
                role=UserProfile.ROLE_MEMBER
            ).values_list('id', flat=True)
            user_ids.update(members)
        
        if 'guest' in allowed_roles:
            guests = UserProfile.objects.filter(
                realm=realm,
                is_active=True,
                role=UserProfile.ROLE_GUEST
            ).values_list('id', flat=True)
            user_ids.update(guests)
        
        # Include LMS users with allowed roles
        if 'mentor' in allowed_roles:
            mentors = LMSUserMapping.objects.filter(
                zulip_user__realm=realm,
                lms_user_type='mentor',
                is_active=True
            ).values_list('zulip_user_id', flat=True)
            user_ids.update(mentors)
        
        if 'student' in allowed_roles:
            students = LMSUserMapping.objects.filter(
                zulip_user__realm=realm,
                lms_user_type='student',
                is_active=True
            ).values_list('zulip_user_id', flat=True)
            user_ids.update(students)
        
        return list(user_ids)
    except Exception:
        # On error, return None (fail open - no filtering)
        return None

