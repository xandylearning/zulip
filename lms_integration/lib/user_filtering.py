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


def get_mentor_filtered_user_ids(
    user_profile: UserProfile,
    realm: Realm,
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
        
        # Include other mentors
        other_mentors = LMSUserMapping.objects.filter(
            realm=realm,
            lms_user_type='mentor',
            is_active=True
        ).exclude(zulip_user=user_profile).values_list('zulip_user_id', flat=True)
        user_ids.update(other_mentors)
        
        # Include students
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
        
        # Include assigned mentors
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
    Return filtered user IDs, or None for no filtering.
    
    This is the main entry point for role-based filtering.
    Returns None if:
    - User has no role mapping
    - User is admin/owner
    - Error occurs (fail open)
    
    Returns list of user IDs if filtering should be applied.
    """
    try:
        # Get user's effective role (may be LMS-based)
        user_role = get_user_role(user_profile, realm)
        
        # Owners and admins are not filtered (they see everyone)
        if user_role in ['owner', 'admin']:
            return None
        
        # For LMS roles (mentor/student), apply specialized filtering
        if user_role == 'mentor':
            return get_mentor_filtered_user_ids(
                user_profile,
                realm,
            )
        elif user_role == 'student':
            return get_student_filtered_user_ids(
                user_profile,
                realm,
            )
        
        # For non-LMS roles, currently no filtering (return None)
        return None
    except Exception:
        # On error, return None (fail open - no filtering)
        return None
