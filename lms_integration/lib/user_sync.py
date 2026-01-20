"""
User Sync Utility

Syncs users from LMS database to Zulip database.
Handles both students and mentors.
"""

import logging
import uuid
from typing import Dict, Optional, Tuple, List, Set
from django.db import transaction
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.timezone import now as timezone_now

from zerver.models import (
    UserProfile, Realm, NamedUserGroup, UserGroupMembership,
    Recipient, Subscription, RealmAuditLog, RealmUserDefault
)
from zerver.actions.create_user import do_create_user
from zerver.actions.user_groups import (
    create_user_group_in_database,
    bulk_add_members_to_user_groups,
    bulk_remove_members_from_user_groups,
    do_send_create_user_group_event,
    add_subgroups_to_user_group,
)
from zerver.actions.streams import bulk_add_subscriptions
from zerver.lib.create_user import create_user_profile, get_display_email_address
from zerver.lib.bulk_create import bulk_set_users_or_streams_recipient_fields
from zerver.lib.streams import create_stream_if_needed
from zerver.models.groups import SystemGroups
from zerver.models.streams import Stream
from zerver.models.realm_audit_logs import AuditLogEventType
from lms_integration.models import Students, Mentors, Batches, Batchtostudent, Mentortostudent, LMSSyncProgress
from lms_integration.lib.email_utils import (
    validate_and_prepare_email,
    update_email_if_changed,
    log_placeholder_email_attempt,
    generate_placeholder_email,
    is_placeholder_email
)

logger = logging.getLogger(__name__)

# Configuration defaults
# Ensure numeric settings are properly converted (settings may be strings from env vars)
_batch_size_value = getattr(settings, 'LMS_SYNC_BATCH_SIZE', 500)
try:
    DEFAULT_BATCH_SIZE = int(_batch_size_value)
except (TypeError, ValueError):
    logger.warning(f"Invalid LMS_SYNC_BATCH_SIZE value '{_batch_size_value}', using default 500")
    DEFAULT_BATCH_SIZE = 500

_progress_interval_value = getattr(settings, 'LMS_SYNC_PROGRESS_INTERVAL', 100)
try:
    DEFAULT_PROGRESS_INTERVAL = int(_progress_interval_value)
except (TypeError, ValueError):
    logger.warning(f"Invalid LMS_SYNC_PROGRESS_INTERVAL value '{_progress_interval_value}', using default 100")
    DEFAULT_PROGRESS_INTERVAL = 100

USE_BULK_OPERATIONS = getattr(settings, 'LMS_SYNC_USE_BULK_OPERATIONS', True)

# Mentor hierarchy levels (from LMS database)
# These should match the values in the Mentors.hierarchy field
MENTOR_HIERARCHY_LEVELS = {
    'chief_mentor': 'Chief Mentors',
    'class_head': 'Class Heads',
    'head_mentor': 'Head Mentors',
    'mentor': 'Mentors',  # Regular mentors
}

# Default hierarchy value if not specified
DEFAULT_MENTOR_HIERARCHY = 'mentor'


class UserSync:
    """
    Syncs users from LMS database to Zulip database.
    """

    def __init__(self, realm: Optional[Realm] = None, progress_tracker: Optional[str] = None, 
                 acting_user: Optional[UserProfile] = None):
        """
        Initialize UserSync.

        Args:
            realm: Zulip realm to sync users to. If None, uses default realm.
            progress_tracker: Optional sync_id for tracking progress
            acting_user: Optional user who triggered the sync (will be used for channel operations)
        """
        self.realm = realm or self._get_default_realm()
        if not self.realm:
            raise ValueError("No realm available for user sync")
        self.progress_tracker = progress_tracker
        self.acting_user = acting_user
        self.batch_size = DEFAULT_BATCH_SIZE
        self.progress_interval = DEFAULT_PROGRESS_INTERVAL
        self.use_bulk_operations = USE_BULK_OPERATIONS
        # Cache for existing users (populated during sync)
        self._existing_users_cache: Optional[Dict[str, UserProfile]] = None
        self._existing_users_by_username: Optional[Dict[str, UserProfile]] = None
    
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
    
    def _update_progress(self, stage: str, processed: int = 0, total: int = 0,
                        message: str = '', created: int = 0, updated: int = 0,
                        skipped: int = 0, errors: int = 0) -> None:
        """
        Update the progress tracker if available.

        Args:
            stage: Current stage of the sync
            processed: Number of records processed
            total: Total number of records to process
            message: Status message to display
            created: Number of records created
            updated: Number of records updated
            skipped: Number of records skipped
            errors: Number of errors encountered
        """
        if not self.progress_tracker:
            logger.debug("No progress tracker available, skipping progress update")
            return

        try:
            with transaction.atomic():
                progress = LMSSyncProgress.objects.select_for_update().get(sync_id=self.progress_tracker)

                # Update fields
                progress.current_stage = stage
                progress.processed_records = processed
                if total > 0:
                    progress.total_records = total
                progress.status_message = message
                progress.created_count = created
                progress.updated_count = updated
                progress.skipped_count = skipped
                progress.error_count = errors

                # Update timestamp for stale sync detection
                from django.utils.timezone import now as timezone_now
                progress.updated_at = timezone_now()

                # Save with specific fields to optimize database writes
                progress.save(update_fields=[
                    'current_stage', 'processed_records', 'total_records', 'status_message',
                    'created_count', 'updated_count', 'skipped_count', 'error_count', 'updated_at'
                ])

            logger.info(f"Progress updated: {stage} - {processed}/{total} - {message}")

        except LMSSyncProgress.DoesNotExist:
            logger.warning(f"Progress tracker {self.progress_tracker} not found")
        except Exception as e:
            logger.error(f"Failed to update progress tracker: {e}")

    def _get_user_role(self, is_mentor: bool = False) -> int:
        """
        Get Zulip user role based on LMS user type.
        
        Args:
            is_mentor: Whether the user is a mentor
            
        Returns:
            UserProfile role constant
        """
        if is_mentor:
            # Mentors get the mentor role in Zulip
            return UserProfile.ROLE_MENTOR
        else:
            # Students get the student role in Zulip
            return UserProfile.ROLE_STUDENT
    
    def _is_user_both_student_and_mentor(self, email: str) -> bool:
        """
        Check if a user exists as both student and mentor in LMS.
        
        Args:
            email: Email address to check
            
        Returns:
            True if user exists as both student and mentor, False otherwise
        """
        try:
            student_exists = Students.objects.using('lms_db').filter(
                email=email, is_active=True
            ).exists()
            # Note: Mentors model doesn't have is_active field
            mentor_exists = Mentors.objects.using('lms_db').filter(
                email=email
            ).exists()
            return student_exists and mentor_exists
        except Exception as e:
            logger.warning(f"Error checking if user is both student and mentor for {email}: {e}")
            return False
    
    def _user_exists_as_mentor(self, email: str, username: Optional[str] = None) -> bool:
        """
        Check if a user exists in the Mentors table.
        Used to skip syncing students who are mentors to avoid duplicate user creation.
        
        Args:
            email: Email address to check
            username: Optional username for placeholder email fallback
            
        Returns:
            True if user exists in Mentors table, False otherwise
        """
        try:
            # Check by email (case-insensitive)
            if email:
                mentor_exists = Mentors.objects.using('lms_db').filter(
                    email__iexact=email
                ).exists()
                if mentor_exists:
                    return True
            
            # For placeholder emails, also check by username if provided
            if username and is_placeholder_email(email):
                mentor_exists = Mentors.objects.using('lms_db').filter(
                    username__iexact=username
                ).exists()
                if mentor_exists:
                    return True
            
            return False
        except Exception as e:
            logger.warning(f"Error checking if user exists as mentor for {email}: {e}")
            return False
    
    def _ensure_user_recipient(self, user_profile: UserProfile) -> None:
        """
        Ensure a user has a recipient and subscription.
        Creates them if missing.
        
        This is optimized for individual user checks. For bulk operations,
        use _bulk_ensure_recipients instead.
        
        Args:
            user_profile: UserProfile to ensure has recipient
        """
        # Quick check: if recipient_id is set, verify it exists
        if user_profile.recipient_id is not None:
            try:
                # Access recipient to trigger DB query and verify it exists
                recipient = user_profile.recipient
                # Quick check if subscription exists (don't fetch full object)
                if Subscription.objects.filter(
                    user_profile_id=user_profile.id,
                    recipient_id=recipient.id
                ).exists():
                    return  # User already has recipient and subscription
            except Recipient.DoesNotExist:
                # Recipient is missing, need to create
                pass
        
        # Create recipient if missing
        recipient, created = Recipient.objects.get_or_create(
            type_id=user_profile.id,
            type=Recipient.PERSONAL
        )
        
        # Link recipient to user profile if needed
        if user_profile.recipient_id != recipient.id:
            user_profile.recipient = recipient
            user_profile.save(update_fields=['recipient'])
        
        # Create subscription if missing
        Subscription.objects.get_or_create(
            user_profile=user_profile,
            recipient=recipient,
            defaults={
                'user_profile': user_profile,
                'recipient': recipient,
                'is_user_active': user_profile.is_active
            }
        )
        
        if created:
            logger.debug(f"Created missing recipient for user {user_profile.delivery_email}")
    
    def _bulk_ensure_recipients(self, user_profiles: List[UserProfile]) -> None:
        """
        Bulk ensure users have recipients and subscriptions.
        Much more efficient than calling _ensure_user_recipient individually.
        
        Args:
            user_profiles: List of UserProfile objects to ensure have recipients
        """
        if not user_profiles:
            return
        
        user_ids = {user.id for user in user_profiles}
        
        # Get existing recipients for these users
        existing_recipients = {
            r.type_id: r
            for r in Recipient.objects.filter(
                type_id__in=user_ids,
                type=Recipient.PERSONAL
            )
        }
        
        # Get existing subscriptions
        recipient_ids = [r.id for r in existing_recipients.values()] if existing_recipients else []
        existing_subscriptions = set(
            Subscription.objects.filter(
                user_profile_id__in=user_ids,
                recipient_id__in=recipient_ids
            ).values_list('user_profile_id', 'recipient_id')
        ) if recipient_ids else set()
        
        # Find users missing recipients
        users_missing_recipients = []
        users_to_update = []
        
        for user_profile in user_profiles:
            if user_profile.id in existing_recipients:
                recipient = existing_recipients[user_profile.id]
                # Check if subscription exists
                if (user_profile.id, recipient.id) in existing_subscriptions:
                    # User has both recipient and subscription
                    if user_profile.recipient_id != recipient.id:
                        users_to_update.append((user_profile, recipient))
                    continue
            
            # User needs recipient created
            users_missing_recipients.append(user_profile)
        
        # Bulk create missing recipients
        if users_missing_recipients:
            recipients_to_create = [
                Recipient(type_id=user.id, type=Recipient.PERSONAL)
                for user in users_missing_recipients
            ]
            Recipient.objects.bulk_create(recipients_to_create)
            
            # Update recipient mapping
            for user, recipient in zip(users_missing_recipients, recipients_to_create):
                existing_recipients[user.id] = recipient
                users_to_update.append((user, recipient))
        
        # Bulk update user profiles with recipient links
        if users_to_update:
            # Group by recipient to minimize updates
            for user_profile, recipient in users_to_update:
                user_profile.recipient = recipient
            
            # Bulk update recipient field
            UserProfile.objects.bulk_update(
                [user for user, _ in users_to_update],
                ['recipient']
            )
        
        # Bulk create missing subscriptions
        subscriptions_to_create = []
        for user_profile in user_profiles:
            recipient = existing_recipients.get(user_profile.id)
            if recipient and (user_profile.id, recipient.id) not in existing_subscriptions:
                subscriptions_to_create.append(
                    Subscription(
                        user_profile=user_profile,
                        recipient=recipient,
                        is_user_active=user_profile.is_active
                    )
                )
        
        if subscriptions_to_create:
            Subscription.objects.bulk_create(subscriptions_to_create)
    
    def _prefetch_existing_users(self) -> None:
        """
        Prefetch all existing Zulip users into memory for fast lookups.
        Creates dictionaries mapping emails and usernames to UserProfile objects.
        """
        if self._existing_users_cache is not None:
            return  # Already prefetched
        
        logger.info("Prefetching existing users for fast lookups...")
        existing_users = UserProfile.objects.filter(realm=self.realm).select_related('realm')
        
        self._existing_users_cache = {}
        self._existing_users_by_username = {}
        
        for user in existing_users:
            # Map by delivery_email (case-insensitive)
            email_key = user.delivery_email.lower()
            self._existing_users_cache[email_key] = user
            
            # Also map by username if it's a placeholder email
            if is_placeholder_email(user.delivery_email):
                # Extract username from placeholder email (format: username@domain)
                username = user.delivery_email.split('@')[0] if '@' in user.delivery_email else None
                if username:
                    self._existing_users_by_username[username.lower()] = user
        
        logger.info(f"Prefetched {len(self._existing_users_cache)} existing users")
    
    def _find_existing_user(self, email: str, username: Optional[str] = None, 
                           is_placeholder: bool = False) -> Optional[UserProfile]:
        """
        Find existing user by email or username (for placeholder emails).
        Uses in-memory cache for fast lookups.
        
        Args:
            email: Email address to search for
            username: Username (for placeholder email fallback)
            is_placeholder: Whether the email is a placeholder
            
        Returns:
            UserProfile if found, None otherwise
        """
        if self._existing_users_cache is None:
            self._prefetch_existing_users()
        
        # Try exact email match
        email_key = email.lower()
        if email_key in self._existing_users_cache:
            return self._existing_users_cache[email_key]
        
        # If placeholder, try username-based lookup
        if is_placeholder and username:
            username_key = username.lower()
            if username_key in self._existing_users_by_username:
                return self._existing_users_by_username[username_key]
            
            # Also try alternative placeholder domains
            current_domain = email.split('@')[1] if '@' in email else None
            for domain in [
                getattr(settings, 'LMS_NO_EMAIL_DOMAIN', 'noemail.local'),
                'noemail.local',
            ]:
                if domain != current_domain:
                    alt_email = generate_placeholder_email(username, domain)
                    alt_key = alt_email.lower()
                    if alt_key in self._existing_users_cache:
                        return self._existing_users_cache[alt_key]
        
        return None
    
    def _bulk_create_lms_users(
        self, 
        users_data: List[Dict],
        is_mentor: bool = False
    ) -> List[UserProfile]:
        """
        Bulk create LMS users with proper roles and group memberships.
        Filters out users that already exist to avoid duplicate key violations.
        
        Args:
            users_data: List of dicts with keys: email, full_name, is_active, username, is_placeholder
            is_mentor: Whether these are mentors (affects role assignment)
            
        Returns:
            List of created UserProfile objects
        """
        if not users_data:
            return []
        
        # Ensure cache is populated
        if self._existing_users_cache is None:
            self._prefetch_existing_users()
        
        default_role = self._get_user_role(is_mentor=is_mentor)
        realm_user_default = RealmUserDefault.objects.get(realm=self.realm)
        email_address_visibility = realm_user_default.email_address_visibility
        
        profiles_to_create: List[UserProfile] = []
        placeholder_logs = []
        skipped_count = 0
        
        # Filter out users that already exist
        for user_data in users_data:
            email = user_data['email']
            full_name = user_data['full_name']
            is_active = user_data.get('is_active', True)
            is_placeholder = user_data.get('is_placeholder', False)
            username = user_data.get('username')
            
            # Check if user already exists (case-insensitive check)
            email_key = email.lower()
            existing_user = self._existing_users_cache.get(email_key)
            
            # Also check username-based lookup for placeholder emails
            if not existing_user and is_placeholder and username:
                existing_user = self._find_existing_user(email, username, is_placeholder)
            
            if existing_user:
                # User already exists, skip creation
                skipped_count += 1
                logger.debug(f"Skipping creation of existing user {email}")
                continue
            
            # Log placeholder email creation
            if is_placeholder and username:
                placeholder_logs.append(
                    f"Creating {'mentor' if is_mentor else 'student'} with placeholder email {email} "
                    f"(username: {username})"
                )
            
            profile = create_user_profile(
                realm=self.realm,
                email=email,
                password=None,  # Password managed by LMS
                active=is_active,
                bot_type=None,
                full_name=full_name,
                bot_owner=None,
                is_mirror_dummy=False,
                tos_version=None,
                timezone="",
                default_language=self.realm.default_language,
                email_address_visibility=email_address_visibility,
            )
            
            # Set role - check if user is both student and mentor, prioritize mentor role
            # If role was explicitly set in user_data (from sync_all_students), use that
            if 'role' in user_data:
                profile.role = user_data['role']
            elif not is_mentor and self._is_user_both_student_and_mentor(email):
                # User is both student and mentor, prioritize mentor role
                profile.role = UserProfile.ROLE_MENTOR
                logger.debug(f"User {email} is both student and mentor, setting role to ROLE_MENTOR")
            else:
                profile.role = default_role
            
            # Copy default settings from realm_user_default
            for settings_name in RealmUserDefault.property_types:
                if settings_name in ["default_language", "enable_login_emails"]:
                    continue
                value = getattr(realm_user_default, settings_name)
                setattr(profile, settings_name, value)
            
            profiles_to_create.append(profile)
        
        if skipped_count > 0:
            logger.info(f"Skipped {skipped_count} users that already exist in bulk create")
        
        if not profiles_to_create:
            return []
        
        # Double-check against database to catch any users created between cache and now
        # This handles race conditions where users might have been created by another process
        emails_to_check = [profile.delivery_email.lower() for profile in profiles_to_create]
        existing_in_db = {
            user.delivery_email.lower(): user
            for user in UserProfile.objects.filter(
                delivery_email__in=[p.delivery_email for p in profiles_to_create],
                realm=self.realm
            ).only('id', 'delivery_email')
        }
        
        # Filter out users that exist in database
        profiles_to_create_filtered = []
        for profile in profiles_to_create:
            email_key = profile.delivery_email.lower()
            if email_key in existing_in_db:
                # Update cache with existing user
                self._existing_users_cache[email_key] = existing_in_db[email_key]
                skipped_count += 1
                continue
            profiles_to_create_filtered.append(profile)
        
        profiles_to_create = profiles_to_create_filtered
        
        if not profiles_to_create:
            if skipped_count > 0:
                logger.info(f"All {skipped_count} users in batch already exist, skipping creation")
            return []
        
        # Bulk create user profiles with ignore_conflicts to handle race conditions
        try:
            if email_address_visibility == UserProfile.EMAIL_ADDRESS_VISIBILITY_EVERYONE:
                UserProfile.objects.bulk_create(profiles_to_create, ignore_conflicts=True)
            else:
                # Need to set email after creation for restricted visibility
                for profile in profiles_to_create:
                    profile.email = profile.delivery_email
                UserProfile.objects.bulk_create(profiles_to_create, ignore_conflicts=True)
                # Update email field with display address
                for profile in profiles_to_create:
                    profile.email = get_display_email_address(profile)
                UserProfile.objects.bulk_update(profiles_to_create, ["email"])
            
            # Reload created users from database to get their IDs
            # Note: bulk_create with ignore_conflicts may not return all created objects
            # So we need to query for them
            created_emails = [p.delivery_email for p in profiles_to_create]
            created_profiles = list(UserProfile.objects.filter(
                delivery_email__in=created_emails,
                realm=self.realm
            ))
            
            # Update cache with newly created users
            for profile in created_profiles:
                self._existing_users_cache[profile.delivery_email.lower()] = profile
                # Also update username cache for placeholder emails
                if is_placeholder_email(profile.delivery_email):
                    username = profile.delivery_email.split('@')[0] if '@' in profile.delivery_email else None
                    if username and self._existing_users_by_username:
                        self._existing_users_by_username[username.lower()] = profile
            
        except Exception as e:
            # If bulk_create fails, fall back to checking each user individually
            logger.warning(f"Bulk create failed, falling back to individual creation: {e}")
            created_profiles = []
            for profile in profiles_to_create:
                try:
                    # Check one more time if user exists (race condition)
                    existing = UserProfile.objects.filter(
                        delivery_email__iexact=profile.delivery_email,
                        realm=self.realm
                    ).first()
                    if existing:
                        # Update cache
                        self._existing_users_cache[profile.delivery_email.lower()] = existing
                        continue
                    profile.save()
                    created_profiles.append(profile)
                    # Update cache
                    self._existing_users_cache[profile.delivery_email.lower()] = profile
                except Exception as individual_error:
                    # Check if it's a duplicate key error
                    error_str = str(individual_error).lower()
                    if 'unique constraint' in error_str or 'duplicate key' in error_str:
                        logger.debug(f"User {profile.delivery_email} already exists, skipping")
                        # Try to load existing user
                        existing = UserProfile.objects.filter(
                            delivery_email__iexact=profile.delivery_email,
                            realm=self.realm
                        ).first()
                        if existing:
                            self._existing_users_cache[profile.delivery_email.lower()] = existing
                        continue
                    else:
                        logger.error(f"Error creating user {profile.delivery_email}: {individual_error}")
        
        if not created_profiles:
            return []
        
        # Log placeholder emails
        for log_msg in placeholder_logs:
            log_placeholder_email_attempt(None, "bulk_user_sync", log_msg)
        
        # Get user IDs after creation
        user_ids = {user.id for user in created_profiles}
        
        # Create Recipient objects
        recipients_to_create = [
            Recipient(type_id=user_id, type=Recipient.PERSONAL) 
            for user_id in user_ids
        ]
        Recipient.objects.bulk_create(recipients_to_create)
        
        # Link recipients to user profiles
        bulk_set_users_or_streams_recipient_fields(
            UserProfile, created_profiles, recipients_to_create
        )
        
        # Create Recipient mapping
        recipients_by_user_id: Dict[int, Recipient] = {}
        for recipient in recipients_to_create:
            recipients_by_user_id[recipient.type_id] = recipient
        
        # Create Subscription objects
        subscriptions_to_create = [
            Subscription(
                user_profile_id=user_profile.id,
                recipient=recipients_by_user_id[user_profile.id],
                is_user_active=user_profile.is_active,
            )
            for user_profile in created_profiles
        ]
        Subscription.objects.bulk_create(subscriptions_to_create)
        
        # Create RealmAuditLog entries
        audit_logs_to_create = [
            RealmAuditLog(
                realm=self.realm,
                modified_user=profile,
                event_type=AuditLogEventType.USER_CREATED,
                event_time=profile.date_joined,
            )
            for profile in created_profiles
        ]
        RealmAuditLog.objects.bulk_create(audit_logs_to_create)
        
        # Note: Recipients and subscriptions were already bulk created above,
        # so no need to check individually here
        
        # Add users to system groups
        self._add_users_to_system_groups(created_profiles, role)
        
        logger.info(f"Bulk created {len(created_profiles)} {'mentors' if is_mentor else 'students'}")
        return created_profiles
    
    def _add_users_to_system_groups(
        self, 
        user_profiles: List[UserProfile], 
        role: int
    ) -> None:
        """
        Add users to appropriate system groups based on their role.
        
        Args:
            user_profiles: List of UserProfile objects to add to groups
            role: User role (ROLE_STUDENT, ROLE_MENTOR, etc.)
        """
        if not user_profiles:
            return
        
        # Get system groups
        everyone_group = NamedUserGroup.objects.get(
            name=SystemGroups.EVERYONE, realm=self.realm, is_system_group=True
        )
        
        # Get role-specific group
        role_group_name = None
        if role == UserProfile.ROLE_STUDENT:
            role_group_name = SystemGroups.STUDENTS
        elif role == UserProfile.ROLE_MENTOR:
            role_group_name = SystemGroups.MENTORS
        elif role == UserProfile.ROLE_FACULTY:
            role_group_name = SystemGroups.FACULTY
        
        role_group = None
        if role_group_name:
            try:
                role_group = NamedUserGroup.objects.get(
                    name=role_group_name, realm=self.realm, is_system_group=True
                )
            except NamedUserGroup.DoesNotExist:
                logger.warning(f"System group {role_group_name} not found for realm {self.realm.id}")
        
        # Create group memberships
        memberships_to_create: List[UserGroupMembership] = []
        now = timezone_now()
        
        for user_profile in user_profiles:
            # All users are in EVERYONE group
            memberships_to_create.append(
                UserGroupMembership(user_profile=user_profile, user_group=everyone_group)
            )
            
            # Add to role-specific group if applicable
            if role_group:
                memberships_to_create.append(
                    UserGroupMembership(user_profile=user_profile, user_group=role_group)
                )
            
            # Add to FULL_MEMBERS if not provisional
            if not user_profile.is_provisional_member:
                try:
                    full_members_group = NamedUserGroup.objects.get(
                        name=SystemGroups.FULL_MEMBERS, realm=self.realm, is_system_group=True
                    )
                    memberships_to_create.append(
                        UserGroupMembership(user_profile=user_profile, user_group=full_members_group)
                    )
                except NamedUserGroup.DoesNotExist:
                    pass  # FULL_MEMBERS group may not exist in all realms
        
        if memberships_to_create:
            UserGroupMembership.objects.bulk_create(memberships_to_create)
            
            # Create audit logs for group memberships
            audit_logs_to_create = [
                RealmAuditLog(
                    realm=self.realm,
                    modified_user=membership.user_profile,
                    modified_user_group=membership.user_group.named_user_group,
                    event_type=AuditLogEventType.USER_GROUP_DIRECT_USER_MEMBERSHIP_ADDED,
                    event_time=now,
                    acting_user=None,
                )
                for membership in memberships_to_create
            ]
            RealmAuditLog.objects.bulk_create(audit_logs_to_create)
    
    def _bulk_update_users(
        self,
        users_to_update: List[Tuple[UserProfile, Dict]]
    ) -> int:
        """
        Bulk update existing users.
        
        Args:
            users_to_update: List of tuples (UserProfile, dict of fields to update)
            
        Returns:
            Number of users updated
        """
        if not users_to_update:
            return 0
        
        updated_count = 0
        update_fields_sets: Dict[Set[str], List[UserProfile]] = {}
        
        # Note: Recipients are ensured in bulk before this method is called
        
        for user_profile, updates in users_to_update:
            # Apply updates
            for field, value in updates.items():
                setattr(user_profile, field, value)
            
            # Group by update fields for efficient bulk_update
            update_fields = frozenset(updates.keys())
            if update_fields not in update_fields_sets:
                update_fields_sets[update_fields] = []
            update_fields_sets[update_fields].append(user_profile)
            updated_count += 1
        
        # Perform bulk updates grouped by fields
        for update_fields, users in update_fields_sets.items():
            UserProfile.objects.bulk_update(users, list(update_fields))
        
        logger.info(f"Bulk updated {updated_count} users")
        return updated_count
    
    def sync_student(self, student: Students) -> Tuple[bool, Optional[UserProfile], str]:
        """
        Sync a single student from LMS to Zulip.
        Supports students with or without email addresses by generating placeholder emails when needed.

        Args:
            student: LMS Students instance

        Returns:
            Tuple of (created, user_profile, message)
        """
        # Validate and prepare email (generate placeholder if needed)
        try:
            email, is_placeholder = validate_and_prepare_email(
                student.email,
                student.username,
                self.realm
            )
        except ValidationError as e:
            return False, None, f"Student {student.id}: Invalid email/username: {e}"
        
        # Skip students who exist as mentors (they'll be synced from Mentors table)
        if self._user_exists_as_mentor(email, student.username):
            logger.debug(f"Skipping student {student.id} ({email}) - user exists as mentor and will be synced from Mentors table")
            return False, None, f"User {email} exists as mentor and will be synced from Mentors table"
        
        # Check if user already exists (by email or by username-based placeholder email)
        try:
            # First try exact email match
            existing_user = UserProfile.objects.filter(
                delivery_email__iexact=email,
                realm=self.realm
            ).first()

            # If not found and email is a placeholder, try to find by username pattern
            # Reuse the email we already generated instead of regenerating
            if not existing_user and is_placeholder:
                # Try to find any user with a placeholder email generated from this username
                # First check the email we already have, then try domain fallback if needed
                potential_emails = [email]  # Start with the email we already generated
                # Only add domain fallback if the current email uses a different domain
                current_domain = email.split('@')[1] if '@' in email else None
                for domain in [
                    getattr(settings, 'LMS_NO_EMAIL_DOMAIN', 'noemail.local'),
                    'noemail.local',  # fallback
                ]:
                    if domain != current_domain:
                        potential_emails.append(generate_placeholder_email(student.username, domain))

                for potential_email in potential_emails:
                    existing_user = UserProfile.objects.filter(
                        delivery_email__iexact=potential_email,
                        realm=self.realm
                    ).first()
                    if existing_user:
                        break

            if existing_user:
                # Ensure user has recipient and subscription
                self._ensure_user_recipient(existing_user)
                
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
                
                # Check if user is both student and mentor - prioritize mentor role
                if self._is_user_both_student_and_mentor(email):
                    if existing_user.role != UserProfile.ROLE_MENTOR:
                        existing_user.role = UserProfile.ROLE_MENTOR
                        updated = True
                        logger.info(f"User {email} is both student and mentor, setting role to ROLE_MENTOR")
                
                # Check if we need to update the user's email (placeholder -> real email)
                if student.email and not is_placeholder_email(existing_user.delivery_email):
                    email_updated = update_email_if_changed(
                        existing_user,
                        student.email,
                        student.username
                    )
                    if email_updated:
                        updated = True
                        logger.info(f"Updated user email from {existing_user.delivery_email} to {student.email}")

                if updated:
                    update_fields = ['full_name', 'is_active']
                    if existing_user.role == UserProfile.ROLE_MENTOR:
                        update_fields.append('role')
                    existing_user.save(update_fields=update_fields)
                    logger.info(f"Updated existing user {existing_user.delivery_email} from student {student.id}")

                # Ensure student is subscribed to batch channels
                self._ensure_student_batch_channels(existing_user, student)

                return False, existing_user, f"User {existing_user.delivery_email} already exists"
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

            # Log placeholder email creation
            if is_placeholder:
                log_placeholder_email_attempt(
                    None,  # Will log without user_profile context
                    "user_sync_student_creation",
                    f"Creating student {student.id} with placeholder email {email} (username: {student.username}, original email: {student.email or 'None'})"
                )

            with transaction.atomic():
                # Check if user is both student and mentor - prioritize mentor role
                is_both = self._is_user_both_student_and_mentor(email)
                user_role = UserProfile.ROLE_MENTOR if is_both else self._get_user_role(is_mentor=False)
                if is_both:
                    logger.info(f"User {email} is both student and mentor, creating with ROLE_MENTOR")
                
                user_profile = do_create_user(
                    email=email,  # Use validated/generated email
                    password=None,  # Password managed by LMS
                    realm=self.realm,
                    full_name=full_name,
                    role=user_role,
                    acting_user=None,
                    skip_email_notifications=True,  # Skip emails during bulk sync
                )

                # Check if user_profile was created successfully
                if user_profile is None:
                    # Race condition: user might have been created by another process
                    logger.warning(f"do_create_user returned None for student {student.id}, checking if user exists...")
                    existing_user = UserProfile.objects.filter(
                        delivery_email__iexact=email,
                        realm=self.realm
                    ).first()
                    if existing_user:
                        logger.info(f"Found existing user {existing_user.delivery_email} for student {student.id} (race condition handled)")
                        # Ensure recipient exists
                        self._ensure_user_recipient(existing_user)
                        # Ensure student is subscribed to batch channels
                        self._ensure_student_batch_channels(existing_user, student)
                        return False, existing_user, f"User {existing_user.delivery_email} already exists (created by another process)"
                    else:
                        logger.error(f"do_create_user returned None and no existing user found for student {student.id} with email {email}")
                        return False, None, f"User creation failed: do_create_user returned None"

                # Ensure user has recipient and subscription
                self._ensure_user_recipient(user_profile)

                # Mirror LMS active flag onto the Zulip user if available
                if hasattr(student, "is_active") and student.is_active is not None:
                    user_profile.is_active = bool(student.is_active)
                    user_profile.save(update_fields=["is_active"])
                
                # Safely access email attribute
                try:
                    user_email = user_profile.email or user_profile.delivery_email
                except AttributeError:
                    logger.error(f"UserProfile {user_profile.id if user_profile else 'None'} missing email attributes for student {student.id}")
                    return False, None, f"User creation incomplete: missing email attributes"
                
                success_message = f"Created user {user_email} from student {student.id}"
                if is_placeholder:
                    success_message += f" (placeholder email for username '{student.username}')"

                logger.info(success_message)
                
                # Ensure student is subscribed to batch channels
                self._ensure_student_batch_channels(user_profile, student)
                
                return True, user_profile, f"Created user {user_email}"
                
        except ValidationError as e:
            logger.error(f"Validation error creating user for student {student.id} (email: {email}, username: {student.username}): {e}")
            # Check if user was created by another process during the exception
            try:
                existing_user = UserProfile.objects.filter(
                    delivery_email__iexact=email,
                    realm=self.realm
                ).first()
                if existing_user:
                    logger.info(f"Found existing user {existing_user.delivery_email} for student {student.id} after validation error (race condition)")
                    # Ensure student is subscribed to batch channels
                    self._ensure_student_batch_channels(existing_user, student)
                    return False, existing_user, f"User {existing_user.delivery_email} already exists"
            except Exception:
                pass
            return False, None, f"Validation error: {e}"
        except Exception as e:
            logger.error(f"Error creating user for student {student.id} (email: {email}, username: {student.username}): {e}", exc_info=True)
            # Check if user was created by another process during the exception
            try:
                existing_user = UserProfile.objects.filter(
                    delivery_email__iexact=email,
                    realm=self.realm
                ).first()
                if existing_user:
                    logger.info(f"Found existing user {existing_user.delivery_email} for student {student.id} after error (race condition)")
                    # Ensure student is subscribed to batch channels
                    self._ensure_student_batch_channels(existing_user, student)
                    return False, existing_user, f"User {existing_user.delivery_email} already exists"
            except Exception:
                pass
            return False, None, f"Error creating user: {e}"
    
    def sync_mentor(self, mentor: Mentors) -> Tuple[bool, Optional[UserProfile], str]:
        """
        Sync a single mentor from LMS to Zulip.
        Supports mentors with or without email addresses by generating placeholder emails when needed.

        Args:
            mentor: LMS Mentors instance

        Returns:
            Tuple of (created, user_profile, message)
        """
        # Validate and prepare email (generate placeholder if needed)
        try:
            email, is_placeholder = validate_and_prepare_email(
                mentor.email,
                mentor.username,
                self.realm
            )
        except ValidationError as e:
            return False, None, f"Mentor {mentor.user_id}: Invalid email/username: {e}"
        
        # Check if user already exists (by email or by username-based placeholder email)
        try:
            # First try exact email match
            existing_user = UserProfile.objects.filter(
                delivery_email__iexact=email,
                realm=self.realm
            ).first()

            # If not found and email is a placeholder, try to find by username pattern
            # Reuse the email we already generated instead of regenerating
            if not existing_user and is_placeholder:
                # Try to find any user with a placeholder email generated from this username
                # First check the email we already have, then try domain fallback if needed
                potential_emails = [email]  # Start with the email we already generated
                # Only add domain fallback if the current email uses a different domain
                current_domain = email.split('@')[1] if '@' in email else None
                for domain in [
                    getattr(settings, 'LMS_NO_EMAIL_DOMAIN', 'noemail.local'),
                    'noemail.local',  # fallback
                ]:
                    if domain != current_domain:
                        potential_emails.append(generate_placeholder_email(mentor.username, domain))

                for potential_email in potential_emails:
                    existing_user = UserProfile.objects.filter(
                        delivery_email__iexact=potential_email,
                        realm=self.realm
                    ).first()
                    if existing_user:
                        break

            if existing_user:
                # Ensure user has recipient and subscription
                self._ensure_user_recipient(existing_user)
                
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
                if existing_user.role != UserProfile.ROLE_MENTOR:
                    existing_user.role = UserProfile.ROLE_MENTOR
                    updated = True

                # Check if we need to update the user's email (placeholder -> real email)
                if mentor.email and not is_placeholder_email(existing_user.delivery_email):
                    email_updated = update_email_if_changed(
                        existing_user,
                        mentor.email,
                        mentor.username
                    )
                    if email_updated:
                        updated = True
                        logger.info(f"Updated user email from {existing_user.delivery_email} to {mentor.email}")

                if updated:
                    existing_user.save(update_fields=['full_name', 'role'])
                    logger.info(f"Updated existing user {existing_user.delivery_email} from mentor {mentor.user_id}")

                # Ensure channels are created for batches this mentor is associated with
                self._ensure_mentor_channels_and_groups(existing_user, mentor)

                return False, existing_user, f"User {existing_user.delivery_email} already exists"
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

            # Log placeholder email creation
            if is_placeholder:
                log_placeholder_email_attempt(
                    None,  # Will log without user_profile context
                    "user_sync_mentor_creation",
                    f"Creating mentor {mentor.user_id} with placeholder email {email} (username: {mentor.username}, original email: {mentor.email or 'None'})"
                )

            with transaction.atomic():
                user_profile = do_create_user(
                    email=email,  # Use validated/generated email
                    password=None,  # Password managed by LMS
                    realm=self.realm,
                    full_name=full_name,
                    role=self._get_user_role(is_mentor=True),
                    acting_user=None,
                    skip_email_notifications=True,  # Skip emails during bulk sync
                )

                # Check if user_profile was created successfully
                if user_profile is None:
                    # Race condition: user might have been created by another process
                    logger.warning(f"do_create_user returned None for mentor {mentor.user_id}, checking if user exists...")
                    existing_user = UserProfile.objects.filter(
                        delivery_email__iexact=email,
                        realm=self.realm
                    ).first()
                    if existing_user:
                        logger.info(f"Found existing user {existing_user.delivery_email} for mentor {mentor.user_id} (race condition handled)")
                        # Ensure recipient exists
                        self._ensure_user_recipient(existing_user)
                        return False, existing_user, f"User {existing_user.delivery_email} already exists (created by another process)"
                    else:
                        logger.error(f"do_create_user returned None and no existing user found for mentor {mentor.user_id} with email {email}")
                        return False, None, f"User creation failed: do_create_user returned None"

                # Ensure user has recipient and subscription
                self._ensure_user_recipient(user_profile)

                # Safely access email attribute
                try:
                    user_email = user_profile.email or user_profile.delivery_email
                except AttributeError:
                    logger.error(f"UserProfile {user_profile.id if user_profile else 'None'} missing email attributes for mentor {mentor.user_id}")
                    return False, None, f"User creation incomplete: missing email attributes"
                
                success_message = f"Created user {user_email} from mentor {mentor.user_id}"
                if is_placeholder:
                    success_message += f" (placeholder email for username '{mentor.username}')"

                logger.info(success_message)
                
                # Ensure channels are created for batches this mentor is associated with
                self._ensure_mentor_channels_and_groups(user_profile, mentor)
                
                return True, user_profile, f"Created user {user_email}"
                
        except ValidationError as e:
            logger.error(f"Validation error creating user for mentor {mentor.user_id} (email: {email}, username: {mentor.username}): {e}")
            # Check if user was created by another process during the exception
            try:
                existing_user = UserProfile.objects.filter(
                    delivery_email__iexact=email,
                    realm=self.realm
                ).first()
                if existing_user:
                    logger.info(f"Found existing user {existing_user.delivery_email} for mentor {mentor.user_id} after validation error (race condition)")
                    return False, existing_user, f"User {existing_user.delivery_email} already exists"
            except Exception:
                pass
            return False, None, f"Validation error: {e}"
        except Exception as e:
            logger.error(f"Error creating user for mentor {mentor.user_id} (email: {email}, username: {mentor.username}): {e}", exc_info=True)
            # Check if user was created by another process during the exception
            try:
                existing_user = UserProfile.objects.filter(
                    delivery_email__iexact=email,
                    realm=self.realm
                ).first()
                if existing_user:
                    logger.info(f"Found existing user {existing_user.delivery_email} for mentor {mentor.user_id} after error (race condition)")
                    return False, existing_user, f"User {existing_user.delivery_email} already exists"
            except Exception:
                pass
            return False, None, f"Error creating user: {e}"
    
    def _ensure_mentor_channels_and_groups(self, user_profile: UserProfile, mentor: Mentors) -> None:
        """
        Ensure channels are created for batches this mentor is associated with,
        and subscribe the mentor to those channels. Also add mentor to hierarchy groups.
        
        Args:
            user_profile: The Zulip UserProfile for the mentor
            mentor: The LMS Mentors instance
        """
        try:
            # Get acting user for channel/group operations
            acting_user = self._get_acting_user_for_batch_sync()
            if not acting_user:
                logger.warning("No acting user available for mentor channel sync")
                return
            
            # Get or create realm-wide groups
            realm_groups_result = self._create_realm_wide_groups(acting_user)
            all_mentors_group = realm_groups_result.get('all_mentors_group')
            hierarchy_groups = realm_groups_result.get('hierarchy_groups', {})
            mentors_channel = realm_groups_result.get('mentors_channel')
            
            # Subscribe to global Mentors channel if it exists
            if mentors_channel and mentors_channel.recipient_id:
                is_subscribed = Subscription.objects.filter(
                    recipient_id=mentors_channel.recipient_id,
                    user_profile=user_profile,
                    active=True
                ).exists()
                
                if not is_subscribed:
                    bulk_add_subscriptions(
                        self.realm,
                        [mentors_channel],
                        [user_profile],
                        acting_user=acting_user,
                    )
                    logger.info(f"Subscribed mentor {user_profile.email} to global Mentors channel")
            
            # Find all batches this mentor is associated with
            # Mentors are linked to batches through: Mentortostudent -> Batchtostudent
            mentor_student_ids = list(
                Mentortostudent.objects.using('lms_db')
                .filter(a_id=mentor.id)
                .values_list('b_id', flat=True)
            )
            
            if not mentor_student_ids:
                logger.debug(f"Mentor {mentor.id} (user_id: {mentor.user_id}) is not associated with any students/batches")
                return
            
            # Get batch IDs for these students
            batch_ids = set(
                Batchtostudent.objects.using('lms_db')
                .filter(b_id__in=mentor_student_ids)
                .values_list('a_id', flat=True)
            )
            
            if not batch_ids:
                logger.debug(f"Mentor {mentor.user_id} students are not in any batches")
                return
            
            # Get batch objects
            batches = Batches.objects.using('lms_db').filter(id__in=batch_ids)
            
            # Process each batch
            for batch in batches:
                try:
                    # Create or get the batch channel
                    channel, channel_created = self._create_batch_channel(
                        batch, all_mentors_group, acting_user
                    )
                    
                    if channel:
                        if channel_created:
                            logger.info(f"Created channel '{channel.name}' for batch {batch.id} when syncing mentor {mentor.user_id}")
                            
                            # Subscribe other mentors for this batch since the channel was just created
                            try:
                                self._sync_batch_mentors_with_hierarchy(
                                    batch, hierarchy_groups, channel, acting_user
                                )
                            except Exception as e:
                                logger.error(f"Error subscribing mentors to new batch channel '{channel.name}': {e}")
                        
                        # Subscribe mentor to channel if not already subscribed
                        if channel.recipient_id:
                            is_subscribed = Subscription.objects.filter(
                                recipient_id=channel.recipient_id,
                                user_profile=user_profile,
                                active=True
                            ).exists()
                            
                            if not is_subscribed:
                                bulk_add_subscriptions(
                                    self.realm,
                                    [channel],
                                    [user_profile],
                                    acting_user=acting_user,
                                )
                                logger.info(f"Subscribed mentor {user_profile.email} to channel '{channel.name}'")
                            else:
                                logger.debug(f"Mentor {user_profile.email} already subscribed to channel '{channel.name}'")
                    else:
                        logger.warning(f"Failed to create/get channel for batch {batch.id}")
                
                except Exception as e:
                    logger.error(f"Error processing channel for batch {batch.id} when syncing mentor {mentor.user_id}: {e}", exc_info=True)
            
            # Add mentor to appropriate hierarchy group
            hierarchy_level = self._normalize_hierarchy_level(mentor.hierarchy)
            if hierarchy_level in hierarchy_groups:
                hierarchy_group = hierarchy_groups[hierarchy_level]
                
                # Check if already a member
                is_member = hierarchy_group.direct_members.filter(id=user_profile.id).exists()
                
                if not is_member:
                    bulk_add_members_to_user_groups(
                        [hierarchy_group],
                        [user_profile.id],
                        acting_user=acting_user
                    )
                    logger.info(f"Added mentor {user_profile.email} to hierarchy group {hierarchy_group.name}")
                else:
                    logger.debug(f"Mentor {user_profile.email} already in hierarchy group {hierarchy_group.name}")
        
        except Exception as e:
            logger.error(f"Error ensuring channels and groups for mentor {mentor.user_id}: {e}", exc_info=True)
    
    def _ensure_student_batch_channels(self, user_profile: UserProfile, student: Students) -> None:
        """
        Ensure channels are created for batches this student belongs to,
        and subscribe the student to those channels.
        
        Args:
            user_profile: The Zulip UserProfile for the student
            student: The LMS Students instance
        """
        try:
            # Get acting user for channel operations
            acting_user = self._get_acting_user_for_batch_sync()
            if not acting_user:
                logger.warning("No acting user available for student channel sync")
                return
            
            # Get or create realm-wide groups (needed for channel permissions)
            realm_groups_result = self._create_realm_wide_groups(acting_user)
            all_mentors_group = realm_groups_result.get('all_mentors_group')
            
            # Find all batches this student belongs to
            batch_ids = list(
                Batchtostudent.objects.using('lms_db')
                .filter(b_id=student.id)
                .values_list('a_id', flat=True)
            )
            
            if not batch_ids:
                logger.debug(f"Student {student.id} is not in any batches")
                return
            
            # Get batch objects
            batches = Batches.objects.using('lms_db').filter(id__in=batch_ids)
            
            # Process each batch
            for batch in batches:
                try:
                    # Create or get the batch channel
                    channel, channel_created = self._create_batch_channel(
                        batch, all_mentors_group, acting_user
                    )
                    
                    if channel:
                        if channel_created:
                            logger.info(f"Created channel '{channel.name}' for batch {batch.id} when syncing student {student.id}")
                            
                            # Subscribe mentors for this batch since the channel was just created
                            # This ensures mentors are added to new channels even if they haven't synced yet
                            try:
                                self._sync_batch_mentors_with_hierarchy(
                                    batch, hierarchy_groups, channel, acting_user
                                )
                            except Exception as e:
                                logger.error(f"Error subscribing mentors to new batch channel '{channel.name}': {e}")
                        
                        # Subscribe student to channel if not already subscribed
                        if channel.recipient_id:
                            is_subscribed = Subscription.objects.filter(
                                recipient_id=channel.recipient_id,
                                user_profile=user_profile,
                                active=True
                            ).exists()
                            
                            if not is_subscribed:
                                bulk_add_subscriptions(
                                    self.realm,
                                    [channel],
                                    [user_profile],
                                    acting_user=acting_user,
                                )
                                logger.info(f"Subscribed student {user_profile.email} to channel '{channel.name}'")
                            else:
                                logger.debug(f"Student {user_profile.email} already subscribed to channel '{channel.name}'")
                    else:
                        logger.warning(f"Failed to create/get channel for batch {batch.id}")
                
                except Exception as e:
                    logger.error(f"Error processing channel for batch {batch.id} when syncing student {student.id}: {e}", exc_info=True)
        
        except Exception as e:
            logger.error(f"Error ensuring channels for student {student.id}: {e}", exc_info=True)
    
    def sync_all_students(self) -> Dict[str, int]:
        """
        Sync all students from LMS to Zulip using optimized batch processing.

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
            # Update progress - counting records
            self._update_progress('counting_records', message='Counting student records...')

            students = Students.objects.using('lms_db').filter(is_active=True)
            stats['total'] = students.count()

            logger.info(f"Syncing {stats['total']} students from LMS to Zulip (batch size: {self.batch_size})")

            # Prefetch existing users for fast lookups
            if self.use_bulk_operations:
                self._prefetch_existing_users()
                logger.info(f"Found {len(self._existing_users_cache)} existing users in realm")

            # Update progress - starting sync
            self._update_progress('syncing_students', total=stats['total'],
                                message=f'Syncing {stats["total"]} students...')

            processed = 0
            batch_users_to_create = []
            batch_users_to_update = []
            batch_existing_users = []  # Collect existing users for bulk recipient check
            batch_errors = []
            error_details = []  # Store detailed error information
            # Track student objects for batch channel subscription
            batch_students_to_create = []  # Track student objects for created users
            batch_students_to_update = []  # Track student objects for updated users

            for student in students:
                try:
                    # Validate and prepare email
                    try:
                        email, is_placeholder = validate_and_prepare_email(
                            student.email,
                            student.username,
                            self.realm
                        )
                    except ValidationError as e:
                        stats['skipped'] += 1
                        batch_errors.append(f"Student {student.id}: Invalid email/username: {e}")
                        processed += 1
                        continue

                    # Skip students who exist as mentors (they'll be synced from Mentors table)
                    if self._user_exists_as_mentor(email, student.username):
                        stats['skipped'] += 1
                        logger.debug(f"Skipping student {student.id} ({email}) - user exists as mentor and will be synced from Mentors table")
                        processed += 1
                        continue

                    # Find existing user
                    existing_user = None
                    if self.use_bulk_operations:
                        existing_user = self._find_existing_user(
                            email, student.username, is_placeholder
                        )
                    else:
                        # Fallback to database query for single-user sync mode
                        existing_user = UserProfile.objects.filter(
                            delivery_email__iexact=email,
                            realm=self.realm
                        ).first()

                    if existing_user:
                        # Ensure user has recipient and subscription
                        self._ensure_user_recipient(existing_user)
                        
                        # Prepare update
                        full_name = self._get_full_name(
                            student.first_name,
                            student.last_name,
                            student.display_name
                        )
                        
                        updates = {}
                        if existing_user.full_name != full_name:
                            updates['full_name'] = full_name
                        if student.is_active != existing_user.is_active:
                            updates['is_active'] = bool(student.is_active)
                        
                        # Check if user is both student and mentor - prioritize mentor role
                        if self._is_user_both_student_and_mentor(email):
                            if existing_user.role != UserProfile.ROLE_MENTOR:
                                updates['role'] = UserProfile.ROLE_MENTOR
                        
                        # Check if we need to update the user's email (placeholder -> real email)
                        if student.email and not is_placeholder_email(existing_user.delivery_email):
                            # Note: email updates are handled separately via update_email_if_changed
                            # which is more complex, so we skip it in bulk mode for now
                            # This could be added later if needed
                            pass
                        
                        if updates:
                            if self.use_bulk_operations:
                                batch_users_to_update.append((existing_user, updates))
                                batch_students_to_update.append((existing_user, student))  # Track student object
                            else:
                                # Single-user update mode
                                for field, value in updates.items():
                                    setattr(existing_user, field, value)
                                existing_user.save(update_fields=list(updates.keys()))
                                stats['updated'] += 1
                                # Subscribe to batch channels in single-user mode
                                try:
                                    self._ensure_student_batch_channels(existing_user, student)
                                except Exception as e:
                                    logger.warning(f"Error subscribing student {student.id} to batch channels: {e}")
                        else:
                            # User exists and is already up-to-date - this is expected for most users
                            stats['skipped'] += 1
                            if processed % 1000 == 0:  # Log occasionally to avoid spam
                                logger.debug(f"Student {student.id} ({email}) already up-to-date, skipping")
                    else:
                        # Prepare for creation
                        full_name = self._get_full_name(
                            student.first_name,
                            student.last_name,
                            student.display_name
                        )
                        
                        # Check if user is both student and mentor - prioritize mentor role
                        is_both = self._is_user_both_student_and_mentor(email)
                        user_role = UserProfile.ROLE_MENTOR if is_both else UserProfile.ROLE_STUDENT
                        if is_both:
                            logger.debug(f"User {email} is both student and mentor, will create with ROLE_MENTOR")
                        
                        user_data = {
                            'email': email,
                            'full_name': full_name,
                            'is_active': bool(student.is_active) if hasattr(student, 'is_active') else True,
                            'username': student.username,
                            'is_placeholder': is_placeholder,
                            'role': user_role,  # Store the role to use during creation
                        }
                        batch_users_to_create.append(user_data)
                        batch_students_to_create.append(student)  # Track student object

                    # Process batch when it reaches batch_size
                    if len(batch_users_to_create) + len(batch_users_to_update) >= self.batch_size:
                        if self.use_bulk_operations:
                            # Bulk ensure recipients for existing users (before updates)
                            if batch_existing_users:
                                try:
                                    self._bulk_ensure_recipients(batch_existing_users)
                                except Exception as e:
                                    logger.warning(f"Bulk recipient check error: {e}")
                                batch_existing_users = []
                            
                            # Bulk create
                            if batch_users_to_create:
                                try:
                                    created_users = self._bulk_create_lms_users(
                                        batch_users_to_create, is_mentor=False
                                    )
                                    stats['created'] += len(created_users)
                                    
                                    # Subscribe created students to batch channels
                                    # Match created users with their student objects by email
                                    created_users_dict = {user.delivery_email.lower(): user for user in created_users}
                                    for student_obj in batch_students_to_create:
                                        try:
                                            email, _ = validate_and_prepare_email(
                                                student_obj.email,
                                                student_obj.username,
                                                self.realm
                                            )
                                            user_profile = created_users_dict.get(email.lower())
                                            if user_profile:
                                                self._ensure_student_batch_channels(user_profile, student_obj)
                                        except Exception as e:
                                            logger.warning(f"Error subscribing student {student_obj.id} to batch channels: {e}")
                                except Exception as e:
                                    stats['errors'] += 1
                                    error_msg = f"Bulk create error (batch of {len(batch_users_to_create)} students): {str(e)}"
                                    error_details.append(error_msg)
                                    logger.error(error_msg, exc_info=True)
                                batch_users_to_create = []
                                batch_students_to_create = []
                            
                            # Bulk update
                            if batch_users_to_update:
                                try:
                                    updated_count = self._bulk_update_users(batch_users_to_update)
                                    stats['updated'] += updated_count
                                    
                                    # Subscribe updated students to batch channels
                                    for user_profile, student_obj in batch_students_to_update:
                                        try:
                                            self._ensure_student_batch_channels(user_profile, student_obj)
                                        except Exception as e:
                                            logger.warning(f"Error subscribing student {student_obj.id} to batch channels: {e}")
                                except Exception as e:
                                    stats['errors'] += 1
                                    error_msg = f"Bulk update error (batch of {len(batch_users_to_update)} students): {str(e)}"
                                    error_details.append(error_msg)
                                    logger.error(error_msg, exc_info=True)
                                batch_users_to_update = []
                                batch_students_to_update = []
                        else:
                            # Fallback to single-user mode
                            for user_data in batch_users_to_create:
                                try:
                                    # Create a mock student object for sync_student
                                    class MockStudent:
                                        def __init__(self, data):
                                            self.id = data.get('id', 0)
                                            self.email = data['email']
                                            self.username = data['username']
                                            self.first_name = None
                                            self.last_name = None
                                            self.display_name = data['full_name']
                                            self.is_active = data['is_active']
                                    
                                    mock_student = MockStudent(user_data)
                                    created, user_profile, message = self.sync_student(mock_student)
                                    if created:
                                        stats['created'] += 1
                                    elif user_profile:
                                        stats['updated'] += 1
                                    else:
                                        stats['skipped'] += 1
                                except Exception as e:
                                    stats['errors'] += 1
                                    logger.error(f"Error syncing student: {e}")
                            batch_users_to_create = []
                            
                            for user_profile, updates in batch_users_to_update:
                                try:
                                    for field, value in updates.items():
                                        setattr(user_profile, field, value)
                                    user_profile.save(update_fields=list(updates.keys()))
                                    stats['updated'] += 1
                                except Exception as e:
                                    stats['errors'] += 1
                                    logger.error(f"Error updating student: {e}")
                            batch_users_to_update = []

                    processed += 1
                    
                    # Update progress at intervals
                    if processed % self.progress_interval == 0 or processed == stats['total']:
                        self._update_progress(
                            'syncing_students',
                            processed=processed,
                            total=stats['total'],
                            message=f'Synced {processed} of {stats["total"]} students...',
                            created=stats['created'],
                            updated=stats['updated'],
                            skipped=stats['skipped'],
                            errors=stats['errors']
                        )

                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f"Student {student.id}: {str(e)}"
                    error_details.append(error_msg)
                    logger.error(f"Error syncing student {student.id}: {e}", exc_info=True)
                    processed += 1

            # Process remaining batch
            if self.use_bulk_operations:
                # Bulk ensure recipients for remaining existing users
                if batch_existing_users:
                    try:
                        self._bulk_ensure_recipients(batch_existing_users)
                    except Exception as e:
                        logger.warning(f"Bulk recipient check error (final batch): {e}")
                
                if batch_users_to_create:
                    try:
                        created_users = self._bulk_create_lms_users(
                            batch_users_to_create, is_mentor=False
                        )
                        stats['created'] += len(created_users)
                        
                        # Subscribe created students to batch channels
                        created_users_dict = {user.delivery_email.lower(): user for user in created_users}
                        for student_obj in batch_students_to_create:
                            try:
                                email, _ = validate_and_prepare_email(
                                    student_obj.email,
                                    student_obj.username,
                                    self.realm
                                )
                                user_profile = created_users_dict.get(email.lower())
                                if user_profile:
                                    self._ensure_student_batch_channels(user_profile, student_obj)
                            except Exception as e:
                                logger.warning(f"Error subscribing student {student_obj.id} to batch channels: {e}")
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = f"Bulk create error (final batch of {len(batch_users_to_create)} students): {str(e)}"
                        error_details.append(error_msg)
                        logger.error(error_msg, exc_info=True)
                
                if batch_users_to_update:
                    try:
                        updated_count = self._bulk_update_users(batch_users_to_update)
                        stats['updated'] += updated_count
                        
                        # Subscribe updated students to batch channels
                        for user_profile, student_obj in batch_students_to_update:
                            try:
                                self._ensure_student_batch_channels(user_profile, student_obj)
                            except Exception as e:
                                logger.warning(f"Error subscribing student {student_obj.id} to batch channels: {e}")
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = f"Bulk update error (final batch of {len(batch_users_to_update)} students): {str(e)}"
                        error_details.append(error_msg)
                        logger.error(error_msg, exc_info=True)

            # Log any validation errors (these are logged as warnings, not counted as errors)
            for error_msg in batch_errors:
                logger.warning(error_msg)

            # Log all actual errors with details
            if error_details:
                logger.error(f"=== {len(error_details)} ERRORS DURING STUDENT SYNC ===")
                for i, error_msg in enumerate(error_details, 1):
                    logger.error(f"Error {i}/{len(error_details)}: {error_msg}")
                logger.error("=== END OF ERROR LIST ===")

            # Log summary with percentages for better understanding
            if stats['total'] > 0:
                pct_created = (stats['created'] / stats['total']) * 100
                pct_updated = (stats['updated'] / stats['total']) * 100
                pct_skipped = (stats['skipped'] / stats['total']) * 100
                pct_errors = (stats['errors'] / stats['total']) * 100
                logger.info(
                    f"Student sync completed: {stats['total']} total | "
                    f"Created: {stats['created']} ({pct_created:.1f}%) | "
                    f"Updated: {stats['updated']} ({pct_updated:.1f}%) | "
                    f"Skipped (already up-to-date): {stats['skipped']} ({pct_skipped:.1f}%) | "
                    f"Errors: {stats['errors']} ({pct_errors:.1f}%)"
                )
            else:
                logger.info(f"Student sync completed: {stats}")
            
        except Exception as e:
            logger.error(f"Error syncing students: {e}", exc_info=True)
            stats['errors'] += 1
        
        return stats
    
    def sync_all_mentors(self) -> Dict[str, int]:
        """
        Sync all mentors from LMS to Zulip using optimized batch processing.
        
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
            # Update progress - counting records
            self._update_progress('counting_records', message='Counting mentor records...')

            mentors = Mentors.objects.using('lms_db').all()
            stats['total'] = mentors.count()

            logger.info(f"Syncing {stats['total']} mentors from LMS to Zulip (batch size: {self.batch_size})")

            # Prefetch existing users for fast lookups (if not already done)
            if self.use_bulk_operations:
                self._prefetch_existing_users()

            # Update progress - starting sync
            self._update_progress('syncing_mentors', total=stats['total'],
                                message=f'Syncing {stats["total"]} mentors...')

            processed = 0
            batch_users_to_create = []
            batch_users_to_update = []
            batch_existing_users = []  # Collect existing users for bulk recipient check
            batch_errors = []
            error_details = []  # Store detailed error information

            for mentor in mentors:
                try:
                    # Validate and prepare email
                    try:
                        email, is_placeholder = validate_and_prepare_email(
                            mentor.email,
                            mentor.username,
                            self.realm
                        )
                    except ValidationError as e:
                        stats['skipped'] += 1
                        batch_errors.append(f"Mentor {mentor.user_id}: Invalid email/username: {e}")
                        processed += 1
                        continue

                    # Find existing user
                    existing_user = None
                    if self.use_bulk_operations:
                        existing_user = self._find_existing_user(
                            email, mentor.username, is_placeholder
                        )
                    else:
                        # Fallback to database query for single-user sync mode
                        existing_user = UserProfile.objects.filter(
                            delivery_email__iexact=email,
                            realm=self.realm
                        ).first()

                    if existing_user:
                        # Collect for bulk recipient check (will process at batch end)
                        batch_existing_users.append(existing_user)
                        
                        # Prepare update
                        full_name = self._get_full_name(
                            mentor.first_name,
                            mentor.last_name,
                            mentor.display_name
                        )
                        
                        updates = {}
                        if existing_user.full_name != full_name:
                            updates['full_name'] = full_name
                        # Update role to mentor if not already
                        if existing_user.role != UserProfile.ROLE_MENTOR:
                            updates['role'] = UserProfile.ROLE_MENTOR
                        
                        if updates:
                            if self.use_bulk_operations:
                                batch_users_to_update.append((existing_user, updates))
                            else:
                                # Single-user update mode
                                for field, value in updates.items():
                                    setattr(existing_user, field, value)
                                existing_user.save(update_fields=list(updates.keys()))
                                stats['updated'] += 1
                        else:
                            stats['skipped'] += 1
                    else:
                        # Prepare for creation
                        full_name = self._get_full_name(
                            mentor.first_name,
                            mentor.last_name,
                            mentor.display_name
                        )
                        
                        user_data = {
                            'email': email,
                            'full_name': full_name,
                            'is_active': True,  # Mentors are typically active
                            'username': mentor.username,
                            'is_placeholder': is_placeholder,
                        }
                        batch_users_to_create.append(user_data)

                    # Process batch when it reaches batch_size
                    if len(batch_users_to_create) + len(batch_users_to_update) >= self.batch_size:
                        if self.use_bulk_operations:
                            # Bulk ensure recipients for existing users (before updates)
                            if batch_existing_users:
                                try:
                                    self._bulk_ensure_recipients(batch_existing_users)
                                except Exception as e:
                                    logger.warning(f"Bulk recipient check error: {e}")
                                batch_existing_users = []
                            
                            # Bulk create
                            if batch_users_to_create:
                                try:
                                    created_users = self._bulk_create_lms_users(
                                        batch_users_to_create, is_mentor=True
                                    )
                                    stats['created'] += len(created_users)
                                except Exception as e:
                                    stats['errors'] += 1
                                    error_msg = f"Bulk create error (batch of {len(batch_users_to_create)} mentors): {str(e)}"
                                    error_details.append(error_msg)
                                    logger.error(error_msg, exc_info=True)
                                batch_users_to_create = []
                            
                            # Bulk update
                            if batch_users_to_update:
                                try:
                                    updated_count = self._bulk_update_users(batch_users_to_update)
                                    stats['updated'] += updated_count
                                except Exception as e:
                                    stats['errors'] += 1
                                    error_msg = f"Bulk update error (batch of {len(batch_users_to_update)} mentors): {str(e)}"
                                    error_details.append(error_msg)
                                    logger.error(error_msg, exc_info=True)
                                batch_users_to_update = []
                        else:
                            # Fallback to single-user mode
                            for user_data in batch_users_to_create:
                                try:
                                    # Create a mock mentor object for sync_mentor
                                    class MockMentor:
                                        def __init__(self, data):
                                            self.user_id = data.get('id', 0)
                                            self.email = data['email']
                                            self.username = data['username']
                                            self.first_name = None
                                            self.last_name = None
                                            self.display_name = data['full_name']
                                    
                                    mock_mentor = MockMentor(user_data)
                                    created, user_profile, message = self.sync_mentor(mock_mentor)
                                    if created:
                                        stats['created'] += 1
                                    elif user_profile:
                                        stats['updated'] += 1
                                    else:
                                        stats['skipped'] += 1
                                except Exception as e:
                                    stats['errors'] += 1
                                    logger.error(f"Error syncing mentor: {e}")
                            batch_users_to_create = []
                            
                            for user_profile, updates in batch_users_to_update:
                                try:
                                    for field, value in updates.items():
                                        setattr(user_profile, field, value)
                                    user_profile.save(update_fields=list(updates.keys()))
                                    stats['updated'] += 1
                                except Exception as e:
                                    stats['errors'] += 1
                                    logger.error(f"Error updating mentor: {e}")
                            batch_users_to_update = []

                    processed += 1
                    
                    # Update progress at intervals
                    if processed % self.progress_interval == 0 or processed == stats['total']:
                        self._update_progress(
                            'syncing_mentors',
                            processed=processed,
                            total=stats['total'],
                            message=f'Synced {processed} of {stats["total"]} mentors...',
                            created=stats['created'],
                            updated=stats['updated'],
                            skipped=stats['skipped'],
                            errors=stats['errors']
                        )

                except Exception as e:
                    stats['errors'] += 1
                    error_msg = f"Mentor {mentor.user_id}: {str(e)}"
                    error_details.append(error_msg)
                    logger.error(f"Error syncing mentor {mentor.user_id}: {e}", exc_info=True)
                    processed += 1

            # Process remaining batch
            if self.use_bulk_operations:
                # Bulk ensure recipients for remaining existing users
                if batch_existing_users:
                    try:
                        self._bulk_ensure_recipients(batch_existing_users)
                    except Exception as e:
                        logger.warning(f"Bulk recipient check error (final batch): {e}")
                
                if batch_users_to_create:
                    try:
                        created_users = self._bulk_create_lms_users(
                            batch_users_to_create, is_mentor=True
                        )
                        stats['created'] += len(created_users)
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = f"Bulk create error (final batch of {len(batch_users_to_create)} mentors): {str(e)}"
                        error_details.append(error_msg)
                        logger.error(error_msg, exc_info=True)
                
                if batch_users_to_update:
                    try:
                        updated_count = self._bulk_update_users(batch_users_to_update)
                        stats['updated'] += updated_count
                    except Exception as e:
                        stats['errors'] += 1
                        error_msg = f"Bulk update error (final batch of {len(batch_users_to_update)} mentors): {str(e)}"
                        error_details.append(error_msg)
                        logger.error(error_msg, exc_info=True)

            # Log any validation errors (these are logged as warnings, not counted as errors)
            for error_msg in batch_errors:
                logger.warning(error_msg)

            # Log all actual errors with details
            if error_details:
                logger.error(f"=== {len(error_details)} ERRORS DURING MENTOR SYNC ===")
                for i, error_msg in enumerate(error_details, 1):
                    logger.error(f"Error {i}/{len(error_details)}: {error_msg}")
                logger.error("=== END OF ERROR LIST ===")

            logger.info(f"Mentor sync completed: {stats}")

        except Exception as e:
            logger.error(f"Error syncing mentors: {e}", exc_info=True)
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
        Sync batches from LMS to Zulip with channels and realm-wide user groups.
        
        Creates realm-wide groups (once for entire realm):
        - Students group (all students from all batches)
        - Mentor hierarchy groups (Chief Mentors, Class Heads, Head Mentors, Regular Mentors)
        - "All Mentors" parent group containing all hierarchy subgroups
        
        Creates for each batch:
        - A private channel where only mentors can send messages
        - Subscribes batch-specific students and mentors to their batch channel
        
        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'batches_created': 0,
            'batches_updated': 0,
            'channels_created': 0,
            'channels_updated': 0,
            'mentor_groups_created': 0,
            'student_groups_created': 0,
            'students_added': 0,
            'students_subscribed': 0,
            'mentors_added': 0,
            'mentors_subscribed': 0,
            'users_removed': 0,
            'errors': 0,
        }
        
        try:
            # Get all batches from LMS
            batches = Batches.objects.using('lms_db').all()
            logger.info(f"Syncing {batches.count()} batches from LMS to Zulip (with channels)")
            
            # Get system bot for acting_user (needed for group and channel operations)
            acting_user = self._get_acting_user_for_batch_sync()
            if not acting_user:
                logger.warning("No acting user available for batch sync")
                return stats
            
            # Step 1: Create realm-wide groups (once for entire realm)
            realm_groups_result = self._create_realm_wide_groups(acting_user)
            stats['mentor_groups_created'] = realm_groups_result.get('mentor_groups_created', 0)
            stats['student_groups_created'] = realm_groups_result.get('student_groups_created', 0)
            
            all_mentors_group = realm_groups_result.get('all_mentors_group')
            students_group = realm_groups_result.get('students_group')
            hierarchy_groups = realm_groups_result.get('hierarchy_groups', {})
            
            # Step 2: Process each batch - create channels and subscribe users
            for batch in batches:
                try:
                    batch_result = self._sync_single_batch_with_channel(
                        batch, acting_user, all_mentors_group, students_group, hierarchy_groups
                    )
                    
                    # Update stats
                    if batch_result.get('channel_created'):
                        stats['channels_created'] += 1
                        stats['batches_created'] += 1
                    else:
                        stats['channels_updated'] += 1
                        stats['batches_updated'] += 1
                    
                    stats['students_added'] += batch_result.get('students_added', 0)
                    stats['students_subscribed'] += batch_result.get('students_subscribed', 0)
                    stats['mentors_added'] += batch_result.get('mentors_added', 0)
                    stats['mentors_subscribed'] += batch_result.get('mentors_subscribed', 0)
                    stats['users_removed'] += batch_result.get('users_removed', 0)
                    
                except Exception as e:
                    stats['errors'] += 1
                    logger.error(f"Error syncing batch {batch.id}: {e}", exc_info=True)
            
            logger.info(f"Batch sync completed: {stats}")
            
        except Exception as e:
            logger.error(f"Error syncing batches: {e}", exc_info=True)
            stats['errors'] += 1
        
        return stats
    
    def _get_acting_user_for_batch_sync(self) -> Optional[UserProfile]:
        """Get an acting user for batch sync operations."""
        # Use provided acting user if available
        if self.acting_user:
            return self.acting_user

        from zerver.models.users import get_system_bot
        try:
            notification_bot_email = getattr(settings, 'NOTIFICATION_BOT', None)
            if notification_bot_email:
                return get_system_bot(notification_bot_email, self.realm.id)
            raise ValueError("NOTIFICATION_BOT not configured")
        except Exception:
            # Fallback to first admin user
            return UserProfile.objects.filter(
                realm=self.realm, is_staff=True, is_active=True
            ).first()
    
    def _create_realm_wide_groups(self, acting_user: UserProfile) -> Dict[str, any]:
        """
        Create realm-wide user groups (once for entire realm, not per batch).
        
        Creates:
        - Students group (all students from all batches)
        - Mentor hierarchy groups (Chief Mentors, Class Heads, Head Mentors, Regular Mentors)
        - "All Mentors" parent group containing all hierarchy subgroups
        
        Args:
            acting_user: UserProfile to act as for group operations
            
        Returns:
            Dictionary with:
            - 'students_group': NamedUserGroup for all students
            - 'all_mentors_group': NamedUserGroup for all mentors
            - 'hierarchy_groups': Dict mapping hierarchy level to NamedUserGroup
            - 'mentor_groups_created': Number of new mentor groups created
            - 'student_groups_created': Number of new student groups created (0 or 1)
        """
        result = {
            'students_group': None,
            'all_mentors_group': None,
            'hierarchy_groups': {},
            'mentor_groups_created': 0,
            'student_groups_created': 0,
        }
        
        try:
            # Create realm-wide students group
            students_group_name = "Students"
            try:
                students_group = NamedUserGroup.objects.get(
                    name=students_group_name,
                    realm=self.realm,
                    is_system_group=False
                )
                logger.debug(f"Found existing realm-wide students group: {students_group_name}")
            except NamedUserGroup.DoesNotExist:
                students_group = create_user_group_in_database(
                    name=students_group_name,
                    members=[],
                    realm=self.realm,
                    description="All students from all batches",
                    acting_user=acting_user,
                )
                do_send_create_user_group_event(students_group, [])
                result['student_groups_created'] = 1
                logger.info(f"Created realm-wide students group: {students_group_name}")
            
            result['students_group'] = students_group
            
            # Create realm-wide mentor hierarchy groups
            subgroups_to_add = []
            
            for hierarchy_key, hierarchy_display_name in MENTOR_HIERARCHY_LEVELS.items():
                group_name = hierarchy_display_name  # Just the hierarchy name, not batch-specific
                
                try:
                    hierarchy_group = NamedUserGroup.objects.get(
                        name=group_name,
                        realm=self.realm,
                        is_system_group=False
                    )
                    logger.debug(f"Found existing realm-wide hierarchy group: {group_name}")
                except NamedUserGroup.DoesNotExist:
                    description = f"All {hierarchy_display_name.lower()} from all batches"
                    hierarchy_group = create_user_group_in_database(
                        name=group_name,
                        members=[],
                        realm=self.realm,
                        description=description,
                        acting_user=acting_user,
                    )
                    do_send_create_user_group_event(hierarchy_group, [])
                    result['mentor_groups_created'] += 1
                    logger.info(f"Created realm-wide mentor hierarchy group: {group_name}")
                
                result['hierarchy_groups'][hierarchy_key] = hierarchy_group
                subgroups_to_add.append(hierarchy_group)
            
            # Create the "All Mentors" parent group
            all_mentors_group_name = "All Mentors"
            try:
                all_mentors_group = NamedUserGroup.objects.get(
                    name=all_mentors_group_name,
                    realm=self.realm,
                    is_system_group=False
                )
                logger.debug(f"Found existing realm-wide all mentors group: {all_mentors_group_name}")
            except NamedUserGroup.DoesNotExist:
                description = "All mentors from all batches (includes all hierarchy levels)"
                all_mentors_group = create_user_group_in_database(
                    name=all_mentors_group_name,
                    members=[],
                    realm=self.realm,
                    description=description,
                    acting_user=acting_user,
                )
                do_send_create_user_group_event(all_mentors_group, [])
                result['mentor_groups_created'] += 1
                logger.info(f"Created realm-wide all mentors group: {all_mentors_group_name}")
            
            # Add hierarchy groups as subgroups of the all mentors group
            existing_subgroup_ids = set(
                all_mentors_group.direct_subgroups.values_list('id', flat=True)
            )
            new_subgroups = [
                sg for sg in subgroups_to_add if sg.id not in existing_subgroup_ids
            ]
            
            if new_subgroups:
                add_subgroups_to_user_group(
                    all_mentors_group,
                    new_subgroups,
                    acting_user=acting_user,
                )
                logger.info(f"Added {len(new_subgroups)} subgroups to {all_mentors_group_name}")
            
            result['all_mentors_group'] = all_mentors_group

            # Create global "Mentors" channel
            mentors_channel_name = "Mentors"
            try:
                # Use all_mentors_group for can_send_message_group
                can_send_group = all_mentors_group.usergroup_ptr if all_mentors_group else None
                
                # Get administrators group for channel administration
                admin_group = NamedUserGroup.objects.get(
                    name=SystemGroups.ADMINISTRATORS,
                    realm=self.realm,
                    is_system_group=True
                ).usergroup_ptr

                mentors_channel, created = create_stream_if_needed(
                    self.realm,
                    mentors_channel_name,
                    invite_only=True,
                    history_public_to_subscribers=True,
                    stream_description="Communication channel for all mentors across all batches",
                    can_send_message_group=can_send_group,
                    can_administer_channel_group=admin_group,
                    acting_user=acting_user,
                )

                # Update existing channel permissions if acting_user is admin/owner
                if not created and mentors_channel and acting_user and (acting_user.is_realm_admin or acting_user.is_realm_owner):
                    updates = []
                    if mentors_channel.can_administer_channel_group != admin_group:
                        mentors_channel.can_administer_channel_group = admin_group
                        updates.append("can_administer_channel_group")
                    
                    if can_send_group and mentors_channel.can_send_message_group != can_send_group:
                        mentors_channel.can_send_message_group = can_send_group
                        updates.append("can_send_message_group")
                    
                    # Also update creator if it's currently a system bot
                    if mentors_channel.creator and mentors_channel.creator.is_bot:
                        mentors_channel.creator = acting_user
                        updates.append("creator")
                        
                    if updates:
                        mentors_channel.save(update_fields=updates)
                        logger.info(f"Updated global Mentors channel permissions and ownership: {', '.join(updates)}")

                if created:
                    logger.info(f"Created global Mentors channel: {mentors_channel_name}")
                result['mentors_channel'] = mentors_channel
            except Exception as e:
                logger.error(f"Error creating global Mentors channel: {e}")
                
        except Exception as e:
            logger.error(f"Error creating realm-wide groups: {e}", exc_info=True)
        
        return result
    
    def _sync_single_batch_with_channel(
        self, batch: Batches, acting_user: UserProfile,
        all_mentors_group: Optional[NamedUserGroup],
        students_group: Optional[NamedUserGroup],
        hierarchy_groups: Dict[str, NamedUserGroup]
    ) -> Dict[str, any]:
        """
        Sync a single batch: create channel and subscribe users.
        
        Uses realm-wide groups that were created separately.
        
        Args:
            batch: LMS Batches instance
            acting_user: UserProfile to act as for operations
            all_mentors_group: Realm-wide all mentors group
            students_group: Realm-wide students group
            hierarchy_groups: Dict of realm-wide hierarchy groups
            
        Returns:
            Dictionary with sync results for this batch
        """
        result = {
            'channel_created': False,
            'students_added': 0,
            'students_subscribed': 0,
            'mentors_added': 0,
            'mentors_subscribed': 0,
            'users_removed': 0,
        }
        
        # Create or get the batch channel with mentors as the can_send_message_group
        channel, channel_created = self._create_batch_channel(batch, all_mentors_group, acting_user)
        result['channel_created'] = channel_created
        
        if not channel:
            logger.error(f"Failed to create channel for batch {batch.id}")
            return result
        
        # Sync mentors to realm-wide hierarchy groups and subscribe to batch channel
        mentor_sync_result = self._sync_batch_mentors_with_hierarchy(
            batch, hierarchy_groups, channel, acting_user
        )
        result['mentors_added'] = mentor_sync_result.get('added', 0)
        result['mentors_subscribed'] = mentor_sync_result.get('subscribed', 0)
        
        # Sync students to realm-wide students group and subscribe to batch channel
        student_sync_result = self._sync_batch_students_with_channel(
            batch, students_group, channel, acting_user
        )
        result['students_added'] = student_sync_result.get('added', 0)
        result['students_subscribed'] = student_sync_result.get('subscribed', 0)
        result['users_removed'] = student_sync_result.get('removed', 0)
        
        return result
    
    def sync_batch(self, batch_id: Optional[int] = None, batch: Optional[Batches] = None) -> Dict[str, any]:
        """
        Sync a whole batch: sync all students and mentors, create channel, and subscribe users.
        
        This method:
        1. Syncs all students in the batch (creates/updates them)
        2. Syncs all mentors associated with the batch (creates/updates them)
        3. Creates or gets the batch channel
        4. Subscribes all synced students and mentors to the batch channel
        
        Args:
            batch_id: Optional batch ID from LMS database
            batch: Optional Batches instance (if provided, batch_id is ignored)
            
        Returns:
            Dictionary with sync statistics:
            - 'batch_id': The batch ID that was synced
            - 'students_created': Number of students created
            - 'students_updated': Number of students updated
            - 'students_subscribed': Number of students subscribed to channel
            - 'mentors_created': Number of mentors created
            - 'mentors_updated': Number of mentors updated
            - 'mentors_subscribed': Number of mentors subscribed to channel
            - 'channel_created': Whether channel was created (True) or already existed (False)
            - 'errors': List of error messages
        """
        result = {
            'batch_id': None,
            'students_created': 0,
            'students_updated': 0,
            'students_subscribed': 0,
            'mentors_created': 0,
            'mentors_updated': 0,
            'mentors_subscribed': 0,
            'channel_created': False,
            'errors': [],
        }
        
        try:
            # Get batch object
            if batch is None:
                if batch_id is None:
                    result['errors'].append("Either batch_id or batch must be provided")
                    return result
                try:
                    batch = Batches.objects.using('lms_db').get(id=batch_id)
                except Batches.DoesNotExist:
                    result['errors'].append(f"Batch with ID {batch_id} not found")
                    return result
            
            result['batch_id'] = batch.id
            logger.info(f"Starting sync for batch {batch.id} ({batch.name})")
            
            # Get acting user for channel/group operations
            acting_user = self._get_acting_user_for_batch_sync()
            if not acting_user:
                result['errors'].append("No acting user available for batch sync")
                return result
            
            # Get or create realm-wide groups
            realm_groups_result = self._create_realm_wide_groups(acting_user)
            all_mentors_group = realm_groups_result.get('all_mentors_group')
            students_group = realm_groups_result.get('students_group')
            hierarchy_groups = realm_groups_result.get('hierarchy_groups', {})
            
            # Get student IDs for this batch (needed to find associated mentors)
            student_ids = list(Batchtostudent.objects.using('lms_db').filter(
                a_id=batch.id
            ).values_list('b_id', flat=True))
            
            # Track mentor emails to skip students with the same email
            mentor_emails = set()
            
            # Step 1: Sync all mentors associated with this batch FIRST
            # This ensures mentors are created with correct role before students
            # (since mentors can also be in the student table)
            if student_ids:
                mentor_ids = set(Mentortostudent.objects.using('lms_db').filter(
                    b_id__in=student_ids
                ).values_list('a_id', flat=True))
                
                if mentor_ids:
                    mentors = Mentors.objects.using('lms_db').filter(id__in=mentor_ids)
                    logger.info(f"Syncing {mentors.count()} mentors for batch {batch.id} (syncing mentors first)")
                    
                    for mentor in mentors:
                        try:
                            # Track mentor email (normalized)
                            try:
                                mentor_email, _ = validate_and_prepare_email(
                                    mentor.email,
                                    mentor.username,
                                    self.realm
                                )
                                mentor_emails.add(mentor_email.lower())
                            except ValidationError:
                                pass  # Skip email tracking if invalid, but still try to sync mentor
                            
                            created, user_profile, message = self.sync_mentor(mentor)
                            if user_profile:
                                if created:
                                    result['mentors_created'] += 1
                                else:
                                    result['mentors_updated'] += 1
                            else:
                                result['errors'].append(f"Mentor {mentor.user_id}: {message}")
                        except Exception as e:
                            error_msg = f"Error syncing mentor {mentor.user_id}: {e}"
                            result['errors'].append(error_msg)
                            logger.error(error_msg, exc_info=True)
                else:
                    logger.info(f"No mentors found for batch {batch.id}")
            else:
                logger.info(f"No students found in batch {batch.id}, skipping mentor sync")
            
            # Step 2: Sync all students in this batch AFTER mentors
            # Skip any students whose email matches a mentor email (already synced as mentor)
            if student_ids:
                students = Students.objects.using('lms_db').filter(id__in=student_ids)
                logger.info(f"Syncing {students.count()} students for batch {batch.id} (syncing students after mentors)")
                
                for student in students:
                    try:
                        # Check if student email matches any mentor email
                        try:
                            student_email, _ = validate_and_prepare_email(
                                student.email,
                                student.username,
                                self.realm
                            )
                            if student_email.lower() in mentor_emails:
                                logger.debug(
                                    f"Skipping student {student.id} ({student_email}) - "
                                    f"email matches a mentor email, already synced as mentor"
                                )
                                continue  # Skip this student, already synced as mentor
                        except ValidationError:
                            pass  # Continue with sync even if email validation fails
                        
                        created, user_profile, message = self.sync_student(student)
                        if user_profile:
                            if created:
                                result['students_created'] += 1
                            else:
                                result['students_updated'] += 1
                        else:
                            # Check if the error is because user exists as mentor
                            if "exists as mentor" in message.lower():
                                logger.debug(f"Skipping student {student.id} - {message}")
                            else:
                                result['errors'].append(f"Student {student.id}: {message}")
                    except Exception as e:
                        error_msg = f"Error syncing student {student.id}: {e}"
                        result['errors'].append(error_msg)
                        logger.error(error_msg, exc_info=True)
            else:
                logger.info(f"No students found in batch {batch.id}")
            
            # Step 3: Create or get batch channel and subscribe users
            channel, channel_created = self._create_batch_channel(batch, all_mentors_group, acting_user)
            result['channel_created'] = channel_created
            
            if channel:
                # Subscribe students and mentors to channel
                student_sync_result = self._sync_batch_students_with_channel(
                    batch, students_group, channel, acting_user
                )
                result['students_subscribed'] = student_sync_result.get('subscribed', 0)
                
                mentor_sync_result = self._sync_batch_mentors_with_hierarchy(
                    batch, hierarchy_groups, channel, acting_user
                )
                result['mentors_subscribed'] = mentor_sync_result.get('subscribed', 0)
                
                logger.info(
                    f"Batch {batch.id} sync completed: "
                    f"{result['students_created']} students created, "
                    f"{result['students_updated']} students updated, "
                    f"{result['students_subscribed']} students subscribed, "
                    f"{result['mentors_created']} mentors created, "
                    f"{result['mentors_updated']} mentors updated, "
                    f"{result['mentors_subscribed']} mentors subscribed"
                )
            else:
                result['errors'].append(f"Failed to create/get channel for batch {batch.id}")
                logger.error(f"Failed to create/get channel for batch {batch.id}")
        
        except Exception as e:
            error_msg = f"Error syncing batch {batch.id if batch else batch_id}: {e}"
            result['errors'].append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return result
    
    def _create_batch_channel(
        self, batch: Batches, all_mentors_group: Optional[NamedUserGroup], acting_user: UserProfile
    ) -> Tuple[Optional[Stream], bool]:
        """
        Create or get a private channel for a batch.
        
        The channel is configured so only mentors can send messages (students read-only).
        
        Args:
            batch: LMS Batches instance
            all_mentors_group: NamedUserGroup for all mentors (used for can_send_message_group)
            acting_user: UserProfile to act as for channel operations
            
        Returns:
            Tuple of (Stream or None, was_created: bool)
        """
        batch_name = batch.name if batch.name else f"Batch {batch.id}"
        channel_name = batch_name
        
        # Channel names have max 60 chars in Zulip
        if len(channel_name) > 60:
            channel_name = channel_name[:60]
        
        try:
            description = f"Communication channel for LMS Batch: {batch_name}"
            if batch.url:
                description += f" ({batch.url})"
            
            # Get the UserGroup (not NamedUserGroup) for can_send_message_group
            can_send_group = None
            if all_mentors_group:
                # The NamedUserGroup extends UserGroup, we need the usergroup_ptr
                can_send_group = all_mentors_group.usergroup_ptr
            
            # Get administrators group for channel administration
            admin_group = NamedUserGroup.objects.get(
                name=SystemGroups.ADMINISTRATORS,
                realm=self.realm,
                is_system_group=True
            ).usergroup_ptr

            channel, created = create_stream_if_needed(
                self.realm,
                channel_name,
                invite_only=True,  # Private channel
                history_public_to_subscribers=True,  # Subscribers can see history
                stream_description=description,
                can_send_message_group=can_send_group,  # Only mentors can send
                can_administer_channel_group=admin_group,  # Allow owners/admins to change it
                acting_user=acting_user,
            )
            
            # Update existing channel permissions if acting_user is admin/owner
            if not created and channel and acting_user and (acting_user.is_realm_admin or acting_user.is_realm_owner):
                updates = []
                if channel.can_administer_channel_group != admin_group:
                    channel.can_administer_channel_group = admin_group
                    updates.append("can_administer_channel_group")
                
                if can_send_group and channel.can_send_message_group != can_send_group:
                    channel.can_send_message_group = can_send_group
                    updates.append("can_send_message_group")
                
                # Also update creator if it's currently a system bot
                if channel.creator and channel.creator.is_bot:
                    channel.creator = acting_user
                    updates.append("creator")
                    
                if updates:
                    channel.save(update_fields=updates)
                    logger.info(f"Updated channel '{channel.name}' permissions and ownership: {', '.join(updates)}")

            if created:
                logger.info(f"Created private channel '{channel_name}' for batch {batch.id}")
            else:
                logger.debug(f"Found existing channel '{channel_name}' for batch {batch.id}")
            
            return channel, created
                
        except Exception as e:
            logger.error(f"Error creating channel for batch {batch.id}: {e}", exc_info=True)
            return None, False
    
    def _sync_batch_students_with_channel(
        self, batch: Batches, students_group: Optional[NamedUserGroup], 
        channel: Stream, acting_user: UserProfile
    ) -> Dict[str, int]:
        """
        Sync students for a batch - add to students group and subscribe to channel.
        Students can only receive messages (read-only) in the channel.
        
        Args:
            batch: LMS Batches instance
            students_group: NamedUserGroup for students (can be None if creation failed)
            channel: The batch's private channel
            acting_user: UserProfile to act as for operations
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {'added': 0, 'subscribed': 0, 'removed': 0}
        
        if not channel:
            return stats
        
        try:
            # Get all students in this batch from LMS
            student_ids = list(Batchtostudent.objects.using('lms_db').filter(
                a_id=batch.id
            ).values_list('b_id', flat=True))
            
            if not student_ids:
                return stats
            
            # Get student objects from LMS
            students = Students.objects.using('lms_db').filter(
                id__in=student_ids
            ).only('id', 'email', 'username', 'is_active', 'first_name', 'last_name', 'display_name')
            
            # Get current group members if students_group exists
            current_group_members = set()
            if students_group:
                current_group_members = set(
                    students_group.direct_members.filter(is_active=True).values_list('id', flat=True)
                )
            
            # Get current channel subscribers
            current_subscribers = set()
            if channel.recipient_id:
                current_subscribers = set(
                    Subscription.objects.filter(
                        recipient_id=channel.recipient_id,
                        active=True
                    ).values_list('user_profile_id', flat=True)
            )
            
            # Prefetch existing users cache if not already done
            if self._existing_users_cache is None:
                self._prefetch_existing_users()
            
            # Collect Zulip users
            zulip_users_to_add_to_group = []
            zulip_users_to_subscribe = []
            zulip_user_ids_to_remove = []
            
            # Batch process email lookups
            student_emails = []
            student_email_map = {}
            
            for student in students:
                try:
                    student_email, is_placeholder = validate_and_prepare_email(
                        student.email,
                        student.username,
                        self.realm
                    )
                    student_emails.append(student_email.lower())
                    student_email_map[student_email.lower()] = (student, is_placeholder)
                except ValidationError:
                    continue
            
            # Bulk lookup Zulip users by email
            if student_emails:
                zulip_users_dict = {
                    user.delivery_email.lower(): user
                    for user in UserProfile.objects.filter(
                        delivery_email__in=student_emails,
                        realm=self.realm
                    ).only('id', 'delivery_email', 'is_active')
                }
                
                for email_lower, (student, is_placeholder) in student_email_map.items():
                    zulip_user = zulip_users_dict.get(email_lower)
                    
                    # If not found and is placeholder, try username lookup
                    if not zulip_user and is_placeholder and student.username:
                        zulip_user = self._find_existing_user(
                            email_lower, student.username, is_placeholder
                        )
                    
                    if not zulip_user:
                        continue
                    
                    # Active student in both LMS and Zulip
                    if student.is_active and zulip_user.is_active:
                        # Add to group if not already member
                        if students_group and zulip_user.id not in current_group_members:
                            zulip_users_to_add_to_group.append(zulip_user)
                        
                        # Subscribe to channel if not already subscribed
                        if zulip_user.id not in current_subscribers:
                            zulip_users_to_subscribe.append(zulip_user)
                    
                    # Inactive student - track for potential removal
                    elif not student.is_active or not zulip_user.is_active:
                        if students_group and zulip_user.id in current_group_members:
                            zulip_user_ids_to_remove.append(zulip_user.id)
            
            # Add students to group
            if zulip_users_to_add_to_group and students_group:
                user_ids_to_add = [u.id for u in zulip_users_to_add_to_group]
                bulk_add_members_to_user_groups(
                    [students_group],
                    user_ids_to_add,
                    acting_user=acting_user
                )
                stats['added'] = len(zulip_users_to_add_to_group)
                logger.info(f"Added {stats['added']} students to group {students_group.name}")
            
            # Subscribe students to channel
            if zulip_users_to_subscribe:
                bulk_add_subscriptions(
                    self.realm,
                    [channel],
                    zulip_users_to_subscribe,
                    acting_user=acting_user,
                )
                stats['subscribed'] = len(zulip_users_to_subscribe)
                logger.info(f"Subscribed {stats['subscribed']} students to channel {channel.name}")
            
            # Remove inactive students from group
            if zulip_user_ids_to_remove and students_group:
                bulk_remove_members_from_user_groups(
                    [students_group],
                    zulip_user_ids_to_remove,
                    acting_user=acting_user
                )
                stats['removed'] = len(zulip_user_ids_to_remove)
                logger.info(f"Removed {stats['removed']} inactive students from group {students_group.name}")
            
        except Exception as e:
            logger.error(f"Error syncing students for batch {batch.id}: {e}", exc_info=True)
        
        return stats
    
    def _sync_batch_mentors_with_hierarchy(
        self, batch: Batches, hierarchy_groups: Dict[str, NamedUserGroup],
        channel: Stream, acting_user: UserProfile
    ) -> Dict[str, int]:
        """
        Sync mentors for a batch - add to realm-wide hierarchy groups and subscribe to channel.
        Mentors are added to their appropriate realm-wide hierarchy group based on their
        hierarchy field in the LMS database.
        
        Args:
            batch: LMS Batches instance
            hierarchy_groups: Dict of realm-wide hierarchy groups (from _create_realm_wide_groups)
            channel: The batch's private channel
            acting_user: UserProfile to act as for operations
            
        Returns:
            Dictionary with sync statistics
        """
        stats = {'added': 0, 'subscribed': 0}
        
        if not channel:
            return stats
        
        try:
            # Get all students in this batch
            student_ids = list(Batchtostudent.objects.using('lms_db').filter(
                a_id=batch.id
            ).values_list('b_id', flat=True))
            
            if not student_ids:
                return stats
            
            # Get mentors for these students
            mentor_ids = set(Mentortostudent.objects.using('lms_db').filter(
                b_id__in=student_ids
            ).values_list('a_id', flat=True))
            
            if not mentor_ids:
                return stats
            
            # Get mentor objects from LMS with hierarchy field
            mentors = Mentors.objects.using('lms_db').filter(
                id__in=mentor_ids
            ).only('user_id', 'email', 'username', 'first_name', 'last_name', 'display_name', 'hierarchy')
            
            # Get current channel subscribers
            current_subscribers = set()
            if channel.recipient_id:
                current_subscribers = set(
                    Subscription.objects.filter(
                        recipient_id=channel.recipient_id,
                        active=True
                    ).values_list('user_profile_id', flat=True)
                )
            
            # Get current members of each hierarchy group
            hierarchy_current_members = {}
            for hierarchy_key, hierarchy_group in hierarchy_groups.items():
                hierarchy_current_members[hierarchy_key] = set(
                    hierarchy_group.direct_members.filter(is_active=True).values_list('id', flat=True)
            )
            
            # Prefetch existing users cache if not already done
            if self._existing_users_cache is None:
                self._prefetch_existing_users()
            
            # organized mentors by hierarchy level
            mentors_by_hierarchy: Dict[str, List[UserProfile]] = {key: [] for key in MENTOR_HIERARCHY_LEVELS}
            mentors_to_subscribe = []
            mentors_to_subscribe_global = []
            
            # Get global Mentors channel if it exists
            mentors_channel = None
            try:
                mentors_channel = Stream.objects.get(
                    name="Mentors",
                    realm=self.realm
                )
            except Stream.DoesNotExist:
                pass
            
            # Get current global subscribers if channel exists
            global_subscribers = set()
            if mentors_channel and mentors_channel.recipient_id:
                global_subscribers = set(
                    Subscription.objects.filter(
                        recipient_id=mentors_channel.recipient_id,
                        active=True
                    ).values_list('user_profile_id', flat=True)
                )
            
            # Batch process email lookups
            mentor_emails = []
            mentor_email_map = {}
            
            for mentor in mentors:
                try:
                    mentor_email, is_placeholder = validate_and_prepare_email(
                        mentor.email,
                        mentor.username,
                        self.realm
                    )
                    mentor_emails.append(mentor_email.lower())
                    mentor_email_map[mentor_email.lower()] = (mentor, is_placeholder)
                except ValidationError:
                    continue
            
            # Bulk lookup Zulip users by email
            if mentor_emails:
                zulip_users_dict = {
                    user.delivery_email.lower(): user
                    for user in UserProfile.objects.filter(
                        delivery_email__in=mentor_emails,
                        realm=self.realm,
                        is_active=True
                    ).only('id', 'delivery_email', 'is_active')
                }
                
                for email_lower, (mentor, is_placeholder) in mentor_email_map.items():
                    zulip_user = zulip_users_dict.get(email_lower)
                    
                    # If not found and is placeholder, try username lookup
                    if not zulip_user and is_placeholder and mentor.username:
                        zulip_user = self._find_existing_user(
                            email_lower, mentor.username, is_placeholder
                        )
                        if zulip_user and not zulip_user.is_active:
                            zulip_user = None
                    
                    if not zulip_user:
                        continue
                    
                    # Determine hierarchy level
                    hierarchy_level = self._normalize_hierarchy_level(mentor.hierarchy)
                    
                    # Add to appropriate hierarchy group if not already member
                    current_members = hierarchy_current_members.get(hierarchy_level, set())
                    if zulip_user.id not in current_members:
                        mentors_by_hierarchy[hierarchy_level].append(zulip_user)
                    
                    # Subscribe to batch channel if not already subscribed
                    if zulip_user.id not in current_subscribers:
                        mentors_to_subscribe.append(zulip_user)
                        
                    # Subscribe to global Mentors channel if not already subscribed
                    if mentors_channel and zulip_user.id not in global_subscribers:
                        mentors_to_subscribe_global.append(zulip_user)
            
            # Add mentors to their hierarchy groups
            total_added = 0
            for hierarchy_key, zulip_users in mentors_by_hierarchy.items():
                if zulip_users and hierarchy_key in hierarchy_groups:
                    hierarchy_group = hierarchy_groups[hierarchy_key]
                    user_ids = [u.id for u in zulip_users]
                    bulk_add_members_to_user_groups(
                        [hierarchy_group],
                        user_ids,
                        acting_user=acting_user
                    )
                    total_added += len(zulip_users)
                    logger.info(f"Added {len(zulip_users)} mentors to hierarchy group {hierarchy_group.name}")
            
            stats['added'] = total_added
            
            # Subscribe mentors to channel
            if mentors_to_subscribe:
                bulk_add_subscriptions(
                    self.realm,
                    [channel],
                    mentors_to_subscribe,
                    acting_user=acting_user,
                )
                stats['subscribed'] = len(mentors_to_subscribe)
                logger.info(f"Subscribed {stats['subscribed']} mentors to channel {channel.name}")
                
            # Subscribe mentors to global channel
            if mentors_to_subscribe_global and mentors_channel:
                bulk_add_subscriptions(
                    self.realm,
                    [mentors_channel],
                    mentors_to_subscribe_global,
                    acting_user=acting_user,
                )
                logger.info(f"Subscribed {len(mentors_to_subscribe_global)} mentors to global Mentors channel")
            
        except Exception as e:
            logger.error(f"Error syncing mentors for batch {batch.id}: {e}", exc_info=True)
        
        return stats
    
    def _normalize_hierarchy_level(self, hierarchy_value: Optional[str]) -> str:
        """
        Normalize a mentor hierarchy value from LMS to a standard key.
        
        Args:
            hierarchy_value: The hierarchy field value from LMS Mentors table
            
        Returns:
            Normalized hierarchy key (one of MENTOR_HIERARCHY_LEVELS keys)
        """
        if not hierarchy_value:
            return DEFAULT_MENTOR_HIERARCHY
        
        # Normalize: lowercase and replace spaces/underscores
        normalized = hierarchy_value.lower().strip().replace(' ', '_').replace('-', '_')
        
        # Map common variations to standard keys
        hierarchy_mapping = {
            'chief_mentor': 'chief_mentor',
            'chiefmentor': 'chief_mentor',
            'chief': 'chief_mentor',
            'class_head': 'class_head',
            'classhead': 'class_head',
            'class': 'class_head',
            'head_mentor': 'head_mentor',
            'headmentor': 'head_mentor',
            'head': 'head_mentor',
            'mentor': 'mentor',
            'regular': 'mentor',
            'regular_mentor': 'mentor',
        }
        
        return hierarchy_mapping.get(normalized, DEFAULT_MENTOR_HIERARCHY)
    
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


