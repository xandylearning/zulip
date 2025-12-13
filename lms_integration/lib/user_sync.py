"""
User Sync Utility

Syncs users from LMS database to Zulip database.
Handles both students and mentors.
"""

import logging
from typing import Dict, Optional, Tuple
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError

from zerver.models import UserProfile, Realm, NamedUserGroup, UserGroupMembership
from zerver.actions.create_user import do_create_user
from zerver.actions.user_groups import (
    create_user_group_in_database,
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    do_send_create_user_group_event,
)
from lms_integration.models import Students, Mentors, Batches, Batchtostudent, Mentortostudent

logger = logging.getLogger(__name__)


class UserSync:
    """
    Syncs users from LMS database to Zulip database.
    """
    
    def __init__(self, realm: Optional[Realm] = None):
        """
        Initialize UserSync.
        
        Args:
            realm: Zulip realm to sync users to. If None, uses default realm.
        """
        self.realm = realm or self._get_default_realm()
        if not self.realm:
            raise ValueError("No realm available for user sync")
    
    def _get_default_realm(self) -> Optional[Realm]:
        """
        Get the default realm for user sync.
        
        Returns:
            Realm instance or None if not found
        """
        try:
            # Try to get realm from settings
            realm_string_id = getattr(settings, 'LMS_USER_SYNC_REALM', None)
            if realm_string_id:
                return Realm.objects.get(string_id=realm_string_id)
            
            # Fall back to first realm (usually the default)
            return Realm.objects.first()
        except Realm.DoesNotExist:
            logger.error("No realm found for user sync")
            return None
    
    def _get_full_name(self, first_name: Optional[str], last_name: Optional[str], 
                       display_name: Optional[str]) -> str:
        """
        Get full name from LMS user data.
        
        Args:
            first_name: First name
            last_name: Last name
            display_name: Display name
            
        Returns:
            Full name string
        """
        if display_name:
            return display_name
        
        parts = [part for part in [first_name, last_name] if part]
        if parts:
            return " ".join(parts)
        
        return "LMS User"
    
    def _get_user_role(self, is_mentor: bool = False) -> int:
        """
        Get Zulip user role based on LMS user type.
        
        Args:
            is_mentor: Whether the user is a mentor
            
        Returns:
            UserProfile role constant
        """
        if is_mentor:
            # Mentors get moderator role
            return UserProfile.ROLE_MODERATOR
        else:
            # Students get member role
            return UserProfile.ROLE_MEMBER
    
    def sync_student(self, student: Students) -> Tuple[bool, Optional[UserProfile], str]:
        """
        Sync a single student from LMS to Zulip.
        
        Args:
            student: LMS Students instance
            
        Returns:
            Tuple of (created, user_profile, message)
        """
        if not student.email:
            return False, None, f"Student {student.id} has no email address"
        
        # Check if user already exists
        try:
            existing_user = UserProfile.objects.filter(
                email=student.email,
                realm=self.realm
            ).first()
            
            if existing_user:
                # Update existing user if needed
                updated = False
                full_name = self._get_full_name(
                    student.first_name,
                    student.last_name,
                    student.display_name
                )
                
                if existing_user.full_name != full_name:
                    existing_user.full_name = full_name
                    updated = True
                
                if student.is_active and not existing_user.is_active:
                    existing_user.is_active = True
                    updated = True
                elif not student.is_active and existing_user.is_active:
                    existing_user.is_active = False
                    updated = True
                
                if updated:
                    existing_user.save(update_fields=['full_name', 'is_active'])
                    logger.info(f"Updated existing user {existing_user.email} from student {student.id}")
                
                return False, existing_user, f"User {existing_user.email} already exists"
        except Exception as e:
            logger.error(f"Error checking existing user for student {student.id}: {e}")
            return False, None, f"Error checking existing user: {e}"
        
        # Create new user
        try:
            full_name = self._get_full_name(
                student.first_name,
                student.last_name,
                student.display_name
            )
            
            with transaction.atomic():
                user_profile = do_create_user(
                    email=student.email,
                    password=None,  # Password managed by LMS
                    realm=self.realm,
                    full_name=full_name,
                    active=student.is_active,
                    role=self._get_user_role(is_mentor=False),
                    acting_user=None,
                    is_mirror_dummy=False,
                )
                
                logger.info(f"Created new user {user_profile.email} from student {student.id}")
                return True, user_profile, f"Created user {user_profile.email}"
                
        except ValidationError as e:
            logger.error(f"Validation error creating user for student {student.id}: {e}")
            return False, None, f"Validation error: {e}"
        except Exception as e:
            logger.error(f"Error creating user for student {student.id}: {e}")
            return False, None, f"Error creating user: {e}"
    
    def sync_mentor(self, mentor: Mentors) -> Tuple[bool, Optional[UserProfile], str]:
        """
        Sync a single mentor from LMS to Zulip.
        
        Args:
            mentor: LMS Mentors instance
            
        Returns:
            Tuple of (created, user_profile, message)
        """
        if not mentor.email:
            return False, None, f"Mentor {mentor.user_id} has no email address"
        
        # Check if user already exists
        try:
            existing_user = UserProfile.objects.filter(
                email=mentor.email,
                realm=self.realm
            ).first()
            
            if existing_user:
                # Update existing user if needed
                updated = False
                full_name = self._get_full_name(
                    mentor.first_name,
                    mentor.last_name,
                    mentor.display_name
                )
                
                if existing_user.full_name != full_name:
                    existing_user.full_name = full_name
                    updated = True
                
                # Update role to moderator if not already
                if existing_user.role != UserProfile.ROLE_MODERATOR:
                    existing_user.role = UserProfile.ROLE_MODERATOR
                    updated = True
                
                if updated:
                    existing_user.save(update_fields=['full_name', 'role'])
                    logger.info(f"Updated existing user {existing_user.email} from mentor {mentor.user_id}")
                
                return False, existing_user, f"User {existing_user.email} already exists"
        except Exception as e:
            logger.error(f"Error checking existing user for mentor {mentor.user_id}: {e}")
            return False, None, f"Error checking existing user: {e}"
        
        # Create new user
        try:
            full_name = self._get_full_name(
                mentor.first_name,
                mentor.last_name,
                mentor.display_name
            )
            
            with transaction.atomic():
                user_profile = do_create_user(
                    email=mentor.email,
                    password=None,  # Password managed by LMS
                    realm=self.realm,
                    full_name=full_name,
                    active=True,  # Mentors are typically active
                    role=self._get_user_role(is_mentor=True),
                    acting_user=None,
                    is_mirror_dummy=False,
                )
                
                logger.info(f"Created new user {user_profile.email} from mentor {mentor.user_id}")
                return True, user_profile, f"Created user {user_profile.email}"
                
        except ValidationError as e:
            logger.error(f"Validation error creating user for mentor {mentor.user_id}: {e}")
            return False, None, f"Validation error: {e}"
        except Exception as e:
            logger.error(f"Error creating user for mentor {mentor.user_id}: {e}")
            return False, None, f"Error creating user: {e}"
    
    def sync_all_students(self) -> Dict[str, int]:
        """
        Sync all students from LMS to Zulip.
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }
        
        try:
            students = Students.objects.using('lms_db').filter(is_active=True)
            stats['total'] = students.count()
            
            logger.info(f"Syncing {stats['total']} students from LMS to Zulip")
            
            for student in students:
                try:
                    created, user_profile, message = self.sync_student(student)
                    
                    if created:
                        stats['created'] += 1
                    elif user_profile:
                        stats['updated'] += 1
                    else:
                        stats['skipped'] += 1
                        logger.warning(f"Skipped student {student.id}: {message}")
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error syncing student {student.id}: {e}")
            
            logger.info(f"Student sync completed: {stats}")
            
        except Exception as e:
            logger.error(f"Error syncing students: {e}")
            stats['errors'] += 1
        
        return stats
    
    def sync_all_mentors(self) -> Dict[str, int]:
        """
        Sync all mentors from LMS to Zulip.
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': 0,
        }
        
        try:
            mentors = Mentors.objects.using('lms_db').all()
            stats['total'] = mentors.count()
            
            logger.info(f"Syncing {stats['total']} mentors from LMS to Zulip")
            
            for mentor in mentors:
                try:
                    created, user_profile, message = self.sync_mentor(mentor)
                    
                    if created:
                        stats['created'] += 1
                    elif user_profile:
                        stats['updated'] += 1
                    else:
                        stats['skipped'] += 1
                        logger.warning(f"Skipped mentor {mentor.user_id}: {message}")
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error syncing mentor {mentor.user_id}: {e}")
            
            logger.info(f"Mentor sync completed: {stats}")
            
        except Exception as e:
            logger.error(f"Error syncing mentors: {e}")
            stats['errors'] += 1
        
        return stats
    
    def sync_all_users(self) -> Dict[str, any]:
        """
        Sync all users (students and mentors) from LMS to Zulip.
        
        Returns:
            Dictionary with sync statistics
        """
        logger.info("Starting full user sync from LMS to Zulip")
        
        student_stats = self.sync_all_students()
        mentor_stats = self.sync_all_mentors()
        
        total_stats = {
            'students': student_stats,
            'mentors': mentor_stats,
            'total_created': student_stats['created'] + mentor_stats['created'],
            'total_updated': student_stats['updated'] + mentor_stats['updated'],
            'total_skipped': student_stats['skipped'] + mentor_stats['skipped'],
            'total_errors': student_stats['errors'] + mentor_stats['errors'],
        }
        
        logger.info(f"Full user sync completed: {total_stats}")
        
        return total_stats
    
    def sync_batches_and_groups(self) -> Dict[str, any]:
        """
        Sync batches from LMS to Zulip user groups and manage group memberships.
        Creates batch groups, adds students and mentors to groups, and removes inactive users.
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'batches_created': 0,
            'batches_updated': 0,
            'students_added': 0,
            'mentors_added': 0,
            'users_removed': 0,
            'errors': 0,
        }
        
        try:
            # Get all batches from LMS
            batches = Batches.objects.using('lms_db').all()
            logger.info(f"Syncing {batches.count()} batches from LMS to Zulip")
            
            # Get system bot for acting_user (needed for group operations)
            from zerver.models.users import get_system_bot
            try:
                # Try to get notification bot
                notification_bot_email = getattr(settings, 'NOTIFICATION_BOT', None)
                if notification_bot_email:
                    acting_user = get_system_bot(notification_bot_email, self.realm.id)
                else:
                    raise ValueError("NOTIFICATION_BOT not configured")
            except Exception:
                # Fallback to first admin user if system bot not available
                acting_user = UserProfile.objects.filter(
                    realm=self.realm, is_staff=True, is_active=True
                ).first()
                if not acting_user:
                    logger.warning("No acting user available for batch sync")
                    return stats
            
            for batch in batches:
                try:
                    batch_group = self._sync_batch_group(batch, acting_user)
                    if batch_group:
                        # Sync students in this batch
                        student_stats = self._sync_batch_students(batch, batch_group, acting_user)
                        stats['students_added'] += student_stats['added']
                        stats['users_removed'] += student_stats['removed']
                        
                        # Sync mentors for this batch (mentors of students in the batch)
                        mentor_stats = self._sync_batch_mentors(batch, batch_group, acting_user)
                        stats['mentors_added'] += mentor_stats['added']
                        stats['users_removed'] += mentor_stats['removed']
                        
                        if student_stats['created'] or mentor_stats['created']:
                            stats['batches_created'] += 1
                        else:
                            stats['batches_updated'] += 1
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error syncing batch {batch.id}: {e}")
            
            logger.info(f"Batch sync completed: {stats}")
            
        except Exception as e:
            logger.error(f"Error syncing batches: {e}")
            stats['errors'] += 1
        
        return stats
    
    def _sync_batch_group(self, batch: Batches, acting_user: UserProfile) -> Optional[NamedUserGroup]:
        """
        Create or get a Zulip user group for a batch.
        
        Args:
            batch: LMS Batches instance
            acting_user: UserProfile to act as for group operations
            
        Returns:
            NamedUserGroup instance or None if error
        """
        try:
            # Generate group name from batch name or ID
            group_name = batch.name if batch.name else f"Batch {batch.id}"
            # Ensure name is valid (max 100 chars, no invalid prefixes)
            if len(group_name) > 100:
                group_name = group_name[:100]
            
            # Check if group already exists
            try:
                user_group = NamedUserGroup.objects.get(
                    name=group_name,
                    realm=self.realm,
                    is_system_group=False
                )
                logger.debug(f"Found existing group {group_name} for batch {batch.id}")
                return user_group
            except NamedUserGroup.DoesNotExist:
                # Create new group
                description = f"LMS Batch: {batch.name or f'Batch {batch.id}'}"
                if batch.url:
                    description += f" ({batch.url})"
                
                user_group = create_user_group_in_database(
                    name=group_name,
                    members=[],  # Start with no members, add them separately
                    realm=self.realm,
                    description=description,
                    acting_user=acting_user,
                )
                
                # Send creation event
                do_send_create_user_group_event(user_group, [])
                
                logger.info(f"Created user group {group_name} for batch {batch.id}")
                return user_group
                
        except Exception as e:
            logger.error(f"Error creating/updating group for batch {batch.id}: {e}")
            return None
    
    def _sync_batch_students(
        self, batch: Batches, batch_group: NamedUserGroup, acting_user: UserProfile
    ) -> Dict[str, int]:
        """
        Sync students for a batch - add active students, remove inactive ones.
        
        Args:
            batch: LMS Batches instance
            batch_group: NamedUserGroup for the batch
            acting_user: UserProfile to act as for group operations
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {'added': 0, 'removed': 0, 'created': False}
        
        try:
            # Get all students in this batch from LMS
            batch_students = Batchtostudent.objects.using('lms_db').filter(a_id=batch.id)
            student_ids = [bs.b_id for bs in batch_students]
            
            if not student_ids:
                return stats
            
            # Get student objects from LMS
            students = Students.objects.using('lms_db').filter(id__in=student_ids)
            
            # Get corresponding Zulip users
            zulip_users_to_add = []
            zulip_user_ids_to_remove = []
            
            # Get current group members
            current_members = set(
                batch_group.direct_members.filter(is_active=True).values_list('id', flat=True)
            )
            
            for student in students:
                if not student.email:
                    continue
                
                try:
                    zulip_user = UserProfile.objects.filter(
                        email=student.email,
                        realm=self.realm
                    ).first()
                    
                    if not zulip_user:
                        # Student not synced yet, skip for now
                        continue
                    
                    # If student is active in LMS and active in Zulip, add to group
                    if student.is_active and zulip_user.is_active:
                        if zulip_user.id not in current_members:
                            zulip_users_to_add.append(zulip_user)
                    # If student is inactive in LMS or Zulip, remove from group
                    elif not student.is_active or not zulip_user.is_active:
                        if zulip_user.id in current_members:
                            zulip_user_ids_to_remove.append(zulip_user.id)
                            
                except Exception as e:
                    logger.error(f"Error processing student {student.id} for batch {batch.id}: {e}")
            
            # Add active students to group
            if zulip_users_to_add:
                user_ids_to_add = [u.id for u in zulip_users_to_add]
                bulk_add_members_to_user_groups(
                    [batch_group],
                    user_ids_to_add,
                    acting_user=acting_user
                )
                stats['added'] = len(zulip_users_to_add)
                logger.info(f"Added {stats['added']} students to batch group {batch_group.name}")
            
            # Remove inactive students from group
            if zulip_user_ids_to_remove:
                bulk_remove_members_from_user_groups(
                    [batch_group],
                    zulip_user_ids_to_remove,
                    acting_user=acting_user
                )
                stats['removed'] = len(zulip_user_ids_to_remove)
                logger.info(f"Removed {stats['removed']} inactive students from batch group {batch_group.name}")
            
        except Exception as e:
            logger.error(f"Error syncing students for batch {batch.id}: {e}")
        
        return stats
    
    def _sync_batch_mentors(
        self, batch: Batches, batch_group: NamedUserGroup, acting_user: UserProfile
    ) -> Dict[str, int]:
        """
        Sync mentors for a batch - add mentors who mentor students in this batch.
        
        Args:
            batch: LMS Batches instance
            batch_group: NamedUserGroup for the batch
            acting_user: UserProfile to act as for group operations
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {'added': 0, 'removed': 0, 'created': False}
        
        try:
            # Get all students in this batch
            batch_students = Batchtostudent.objects.using('lms_db').filter(a_id=batch.id)
            student_ids = [bs.b_id for bs in batch_students]
            
            if not student_ids:
                return stats
            
            # Get mentors for these students
            mentor_student_rels = Mentortostudent.objects.using('lms_db').filter(
                b_id__in=student_ids
            )
            mentor_ids = set([ms.a_id for ms in mentor_student_rels])
            
            if not mentor_ids:
                return stats
            
            # Get mentor objects from LMS
            mentors = Mentors.objects.using('lms_db').filter(user_id__in=mentor_ids)
            
            # Get corresponding Zulip users
            zulip_users_to_add = []
            
            # Get current group members
            current_members = set(
                batch_group.direct_members.filter(is_active=True).values_list('id', flat=True)
            )
            
            for mentor in mentors:
                if not mentor.email:
                    continue
                
                try:
                    zulip_user = UserProfile.objects.filter(
                        email=mentor.email,
                        realm=self.realm,
                        is_active=True
                    ).first()
                    
                    if not zulip_user:
                        # Mentor not synced yet, skip for now
                        continue
                    
                    # Add mentor to group if not already a member
                    if zulip_user.id not in current_members:
                        zulip_users_to_add.append(zulip_user)
                        
                except Exception as e:
                    logger.error(f"Error processing mentor {mentor.user_id} for batch {batch.id}: {e}")
            
            # Add mentors to group
            if zulip_users_to_add:
                user_ids_to_add = [u.id for u in zulip_users_to_add]
                bulk_add_members_to_user_groups(
                    [batch_group],
                    user_ids_to_add,
                    acting_user=acting_user
                )
                stats['added'] = len(zulip_users_to_add)
                logger.info(f"Added {stats['added']} mentors to batch group {batch_group.name}")
            
        except Exception as e:
            logger.error(f"Error syncing mentors for batch {batch.id}: {e}")
        
        return stats
    
    def sync_all_with_batches(self) -> Dict[str, any]:
        """
        Sync all users and batches from LMS to Zulip.
        This is the main method that syncs users first, then batches and group memberships.
        
        Returns:
            Dictionary with sync statistics
        """
        logger.info("Starting full sync (users + batches) from LMS to Zulip")
        
        # First sync users
        user_stats = self.sync_all_users()
        
        # Then sync batches and group memberships
        batch_stats = self.sync_batches_and_groups()
        
        total_stats = {
            'users': user_stats,
            'batches': batch_stats,
            'total_created': user_stats['total_created'],
            'total_updated': user_stats['total_updated'],
            'total_skipped': user_stats['total_skipped'],
            'total_errors': user_stats['total_errors'] + batch_stats['errors'],
        }
        
        logger.info(f"Full sync (users + batches) completed: {total_stats}")
        
        return total_stats


