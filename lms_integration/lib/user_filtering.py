"""
User filtering logic for role-based DM permissions.

This module provides functions to filter users based on role-based permission
matrices configured by realm administrators.
"""

import logging
from typing import List

from django.db import models

from zerver.models import Realm, UserProfile

from lms_integration.models import (
    LMSUserMapping,
    Mentors,
    Mentortostudent,
    Batchtostudent,
)

logger = logging.getLogger(__name__)

DEMO_MENTOR_ONLY_STUDENTS_EMAILS = frozenset(
    {
        "xandybooks@gmail.com",
    }
)


def is_demo_mentor_restricted_account(user_profile: UserProfile) -> bool:
    emails = {user_profile.email.casefold()}
    if user_profile.delivery_email is not None:
        emails.add(user_profile.delivery_email.casefold())
    return len(emails & DEMO_MENTOR_ONLY_STUDENTS_EMAILS) > 0


def get_user_role(user_profile: UserProfile, realm: Realm) -> str:
    """
    Determine the effective role of a user.
    
    LMS roles (mentor, student) take precedence over Zulip roles.
    If no LMS mapping exists, returns the Zulip role.
    
    Returns one of: 'owner', 'admin', 'faculty', 'mentor', 'student', 'parent', 'member'
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
    elif user_profile.is_faculty:
        return 'faculty'
    elif user_profile.is_mentor:
        return 'mentor'
    elif user_profile.is_student:
        return 'student'
    elif user_profile.is_parent:
        return 'parent'
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
            # User has Zulip role mentor but no LMSUserMapping with lms_user_type='mentor'.
            # Ensure LMS user sync has run so this user has an LMSUserMapping row.
            logger.info(
                "users/for-chat: empty list for mentor %s (id=%s): no LMSUserMapping with lms_user_type='mentor'",
                user_profile.delivery_email,
                user_profile.id,
            )
            return []

        mentor_lms_id = lms_mapping.lms_user_id
        
        # Mentortostudent.a_id references Mentors.id (table PK), not Mentors.user_id.
        # LMSUserMapping.lms_user_id for mentors stores Mentors.user_id, so resolve PK.
        mentor_pk = Mentors.objects.using('lms_db').filter(
            user_id=mentor_lms_id
        ).values_list('id', flat=True).first()
        
        user_ids = {user_profile.id}
        demo_restricted_account = is_demo_mentor_restricted_account(user_profile)

        if not demo_restricted_account:
            # Always include admins and owners
            admin_owners = UserProfile.objects.filter(
                realm=realm,
                is_active=True
            ).filter(
                models.Q(role=UserProfile.ROLE_REALM_OWNER) |
                models.Q(role=UserProfile.ROLE_REALM_ADMINISTRATOR)
            ).values_list('id', flat=True)
            user_ids.update(admin_owners)

            # Include other mentors (LMSUserMapping has no realm field; filter via zulip_user)
            other_mentors = LMSUserMapping.objects.filter(
                zulip_user__realm=realm,
                lms_user_type='mentor',
                is_active=True
            ).exclude(zulip_user=user_profile).values_list('zulip_user_id', flat=True)
            user_ids.update(other_mentors)

        # Include the requesting mentor so they appear in their own chat list
        user_ids.add(user_profile.id)

        # Include students (only if we could resolve mentor PK from LMS)
        direct_student_ids = []
        if mentor_pk is not None:
            direct_student_ids = list(
                Mentortostudent.objects.using('lms_db').filter(
                    a_id=mentor_pk
                ).values_list('b_id', flat=True)
            )
        
        all_student_ids = set(direct_student_ids)
        if not demo_restricted_account:
            # Get batches where mentor has students
            batch_ids = Batchtostudent.objects.using('lms_db').filter(
                b_id__in=direct_student_ids
            ).values_list('a_id', flat=True).distinct()

            # Get all students in those batches (expanding visibility)
            batch_student_ids = Batchtostudent.objects.using('lms_db').filter(
                a_id__in=batch_ids
            ).values_list('b_id', flat=True).distinct()

            # Combine direct and batch students
            all_student_ids |= set(batch_student_ids)
        
        # Map LMS student IDs to Zulip user IDs
        student_mappings = LMSUserMapping.objects.filter(
            lms_user_id__in=all_student_ids,
            lms_user_type='student',
            is_active=True,
            zulip_user__realm=realm
        ).values_list('zulip_user_id', flat=True)
        
        user_ids.update(student_mappings)
        
        return list(user_ids)
    except Exception as e:
        # On error, return empty list (fail secure). Log so admins can fix lms_db/config.
        logger.warning(
            "users/for-chat: get_mentor_filtered_user_ids failed for %s (id=%s): %s",
            user_profile.delivery_email,
            user_profile.id,
            e,
            exc_info=True,
        )
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
            # User has Zulip role student but no LMSUserMapping with lms_user_type='student'.
            logger.info(
                "users/for-chat: empty list for student %s (id=%s): no LMSUserMapping with lms_user_type='student'",
                user_profile.delivery_email,
                user_profile.id,
            )
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
