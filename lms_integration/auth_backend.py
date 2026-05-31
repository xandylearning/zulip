"""
Simple TestPress JWT Authentication Backend

Simple authentication backend that:
1. Validates JWT token with TestPress
2. Gets user profile from TestPress
3. Creates/updates Zulip user
4. That's it!
"""

import logging
from typing import Any, Dict, Optional

from django.contrib.auth.backends import BaseBackend
from django.db import IntegrityError, transaction
from django.http import HttpRequest

from zerver.lib.exceptions import JsonableError
from zerver.models import Realm, UserProfile
from zerver.models.users import ExternalAuthID
from zerver.lib.users import check_full_name
from zerver.actions.create_user import do_create_user, do_reactivate_user
from zproject.backends import ZulipAuthMixin, common_get_active_user, log_auth_attempts

from .jwt_validator import testpress_jwt_validator
from .lib.email_utils import validate_and_prepare_email

logger = logging.getLogger(__name__)

# External auth method name for storing LMS usernames
LMS_USERNAME_AUTH_METHOD = "testpress-username"


class TestPressJWTAuthBackend(ZulipAuthMixin, BaseBackend):
    """
    TestPress JWT authentication backend with username-based user lookup.

    Flow:
    1. Validate JWT token with TestPress
    2. Get user profile from TestPress (username + optional email)
    3. Find existing Zulip user by LMS username (primary lookup)
    4. Fallback to email lookup for migration purposes
    5. Create new user if not found, with username mapping
    6. Done!

    Uses ExternalAuthID to map LMS usernames to Zulip users for reliable identification.
    """

    name = "testpress-jwt"

    def _get_user_info_from_testpress(self, testpress_data: Dict[str, Any], realm: Realm) -> Dict[str, Any]:
        """Extract user info from TestPress data and prepare for Zulip."""
        # Get basic info - ensure all string fields are properly converted
        email = testpress_data.get('email')
        username = testpress_data.get('username')
        
        # Ensure first_name and last_name are strings (handle None, int, etc.)
        first_name = testpress_data.get('first_name') or ''
        last_name = testpress_data.get('last_name') or ''
        if not isinstance(first_name, str):
            first_name = str(first_name) if first_name is not None else ''
        if not isinstance(last_name, str):
            last_name = str(last_name) if last_name is not None else ''
        
        # Ensure username is a string
        if username and not isinstance(username, str):
            username = str(username)
        
        # Ensure email is a string if present
        if email and not isinstance(email, str):
            email = str(email)

        # Need at least username
        if not username:
            if email:
                username = email.split('@')[0]
            else:
                # Get ID and convert to string
                user_id = testpress_data.get('id', 'unknown')
                username = f"user_{user_id}"

        # Build full name - ensure it's always a string
        full_name = f"{first_name} {last_name}".strip() or username
        if not isinstance(full_name, str):
            full_name = str(full_name) if full_name else username

        # Get email (real or placeholder)
        final_email, is_placeholder = validate_and_prepare_email(email, username, realm)

        # Ensure is_active is always a boolean (TestPress might return string/int)
        is_active_value = testpress_data.get('is_active', True)
        if isinstance(is_active_value, str):
            # Convert string to boolean (handle "true", "1", "yes", etc.)
            is_active_value = is_active_value.lower() in ('true', '1', 'yes', 'on')
        elif isinstance(is_active_value, int):
            # Convert int to boolean (1 = True, 0 = False)
            is_active_value = bool(is_active_value)
        else:
            # Already boolean or None, convert None to True
            is_active_value = bool(is_active_value) if is_active_value is not None else True

        return {
            'email': final_email,
            'full_name': full_name,
            'username': username,
            'is_active': is_active_value,
            'testpress_data': testpress_data
        }

    def _find_existing_user_by_username(self, username: str, realm: Realm) -> Optional[UserProfile]:
        """Find existing user by LMS username."""
        try:
            external_auth = ExternalAuthID.objects.get(
                realm=realm,
                external_auth_method_name=LMS_USERNAME_AUTH_METHOD,
                external_auth_id=username
            )
            user_profile = external_auth.user
            if user_profile.is_active:
                return user_profile
            else:
                logger.info(f"Found deactivated user with username '{username}': {user_profile.delivery_email}")
                return user_profile  # Return even if deactivated, we can reactivate later
        except ExternalAuthID.DoesNotExist:
            logger.debug(f"No user found with LMS username: {username}")
            return None

    def _find_existing_user_by_email(self, email: str, realm: Realm) -> Optional[UserProfile]:
        """Find existing user by email (fallback method)."""
        # First try to get active user (preferred)
        active_user = common_get_active_user(email, realm)
        if active_user:
            return active_user
        
        # Also check for inactive users - we can reactivate them
        try:
            from zerver.models.users import get_user_by_delivery_email
            inactive_user = get_user_by_delivery_email(email, realm)
            if inactive_user:
                logger.info(f"Found inactive user by email: {email}")
                return inactive_user
        except UserProfile.DoesNotExist:
            # User doesn't exist
            pass
        except Exception as e:
            # Log unexpected errors but don't fail
            logger.warning(f"Unexpected error checking for user by email {email}: {e}")
        
        return None

    def _add_username_mapping(self, user_profile: UserProfile, username: str, realm: Realm) -> None:
        """Add LMS username mapping to ExternalAuthID for future lookups.

        Idempotent: if the mapping already exists (e.g. a concurrent request
        created it), this is a no-op. The insert runs in its own savepoint so a
        duplicate does not poison the surrounding transaction.
        """
        try:
            with transaction.atomic(savepoint=True):
                _, created = ExternalAuthID.objects.get_or_create(
                    realm=realm,
                    external_auth_method_name=LMS_USERNAME_AUTH_METHOD,
                    external_auth_id=username,
                    defaults={"user": user_profile},
                )
            if created:
                logger.info(f"Added username mapping '{username}' for user {user_profile.delivery_email}")
        except IntegrityError as e:
            # Lost a race to create the mapping; another request inserted it
            # first. The savepoint was rolled back, so the transaction is clean.
            logger.info(f"Username mapping '{username}' already exists for {user_profile.delivery_email}: {e}")
        except Exception as e:
            logger.warning(f"Failed to add username mapping '{username}' for user {user_profile.delivery_email}: {e}")

    def _get_or_create_user(self, user_info: Dict[str, Any], realm: Realm) -> Optional[UserProfile]:
        """Get existing user or create new user."""
        email = user_info["email"]
        full_name = user_info["full_name"]
        username = user_info["username"]

        logger.debug(f"Looking up user: email={email}, username={username}, realm={realm.string_id}")

        # Try to find existing user by username first (primary lookup)
        existing_user = self._find_existing_user_by_username(username, realm)
        if existing_user:
            logger.info(f"Found existing user by username '{username}': {existing_user.delivery_email} (ID: {existing_user.id})")

            # Reactivate if needed
            if not existing_user.is_active and user_info["is_active"]:
                do_reactivate_user(existing_user, acting_user=None)
                logger.info(f"Reactivated user: {existing_user.delivery_email}")

            return existing_user

        # Fallback: try to find by email (for migration purposes)
        existing_user = self._find_existing_user_by_email(email, realm)
        if existing_user:
            logger.info(f"Found existing user by email (fallback): {email} (ID: {existing_user.id})")

            # Add the LMS username mapping for future lookups
            self._add_username_mapping(existing_user, username, realm)

            # Reactivate if needed
            if not existing_user.is_active and user_info["is_active"]:
                do_reactivate_user(existing_user, acting_user=None)
                logger.info(f"Reactivated user: {email}")

            return existing_user

        # Before creating, do a final comprehensive check to ensure user doesn't exist
        # This handles race conditions and edge cases
        from zerver.models.users import get_user_by_delivery_email
        from django.contrib.auth.models import UserManager
        
        # Normalize email the same way create_user does
        normalized_email = UserManager.normalize_email(email)
        logger.debug(f"Normalized email: {email} -> {normalized_email}")
        
        # Try multiple lookup strategies
        try:
            existing_user = get_user_by_delivery_email(normalized_email, realm)
            if existing_user:
                logger.info(f"Found existing user by normalized email (final check): {normalized_email} (ID: {existing_user.id})")
                # Add username mapping if not already present
                self._add_username_mapping(existing_user, username, realm)
                # Reactivate if needed
                if not existing_user.is_active and user_info["is_active"]:
                    do_reactivate_user(existing_user, acting_user=None)
                    logger.info(f"Reactivated user: {normalized_email}")
                return existing_user
        except UserProfile.DoesNotExist:
            pass  # User doesn't exist with normalized email
        
        # Also try original email (in case normalization changed it)
        if normalized_email != email:
            try:
                existing_user = get_user_by_delivery_email(email, realm)
                if existing_user:
                    logger.info(f"Found existing user by original email (final check): {email} (ID: {existing_user.id})")
                    # Add username mapping if not already present
                    self._add_username_mapping(existing_user, username, realm)
                    # Reactivate if needed
                    if not existing_user.is_active and user_info["is_active"]:
                        do_reactivate_user(existing_user, acting_user=None)
                        logger.info(f"Reactivated user: {email}")
                    return existing_user
            except UserProfile.DoesNotExist:
                pass
        
        # Last resort: query database directly with case-insensitive match
        # This catches any edge cases with email formatting
        try:
            existing_user = UserProfile.objects.get(
                delivery_email__iexact=email.strip(),
                realm=realm
            )
            logger.info(f"Found existing user by direct DB query: {email} (ID: {existing_user.id})")
            # Add username mapping if not already present
            self._add_username_mapping(existing_user, username, realm)
            # Reactivate if needed
            if not existing_user.is_active and user_info["is_active"]:
                do_reactivate_user(existing_user, acting_user=None)
                logger.info(f"Reactivated user: {email}")
            return existing_user
        except UserProfile.DoesNotExist:
            pass  # User truly doesn't exist, proceed with creation
        except UserProfile.MultipleObjectsReturned:
            # This shouldn't happen, but if it does, get the first one
            logger.warning(f"Multiple users found with email {email}, using first one")
            existing_user = UserProfile.objects.filter(
                delivery_email__iexact=email.strip(),
                realm=realm
            ).first()
            if existing_user:
                self._add_username_mapping(existing_user, username, realm)
                if not existing_user.is_active and user_info["is_active"]:
                    do_reactivate_user(existing_user, acting_user=None)
                return existing_user

        # Create new user
        logger.info(f"Creating new user: {email} (username: {username})")

        try:
            # Ensure full_name is a string before validation
            if not isinstance(full_name, str):
                full_name = str(full_name) if full_name else email.split("@")[0]
            
            # Validate full name
            validated_full_name = check_full_name(full_name, user_profile=None, realm=realm)
        except JsonableError:
            # Use email prefix as fallback
            validated_full_name = email.split("@")[0]
            logger.warning(f"Invalid full name '{full_name}' for {email}, using '{validated_full_name}'")

        # Create the external auth ID mapping for LMS username
        external_auth_id_dict = {
            LMS_USERNAME_AUTH_METHOD: username
        }

        try:
            # savepoint=True is essential: if do_create_user raises (e.g. a
            # concurrent login already created this user), Django rolls back to
            # this savepoint, leaving the surrounding transaction usable. Without
            # it, the failed INSERT poisons the transaction and every recovery
            # query below would fail with "current transaction is aborted".
            with transaction.atomic(savepoint=True):
                new_user = do_create_user(
                    email=email,
                    password=None,  # No password for JWT auth
                    realm=realm,
                    full_name=validated_full_name,
                    acting_user=None,
                    external_auth_id_dict=external_auth_id_dict,
                )
                logger.info(f"Created new user: {email} (ID: {new_user.id}) with LMS username: {username}")
                return new_user

        except IntegrityError as e:
            # Expected under concurrency: another request (a parallel login or a
            # bulk sync) created this user between our lookups above and the
            # INSERT here. The savepoint has been rolled back, so the connection
            # is clean and we can safely re-query and return the existing user.
            logger.warning(
                f"User {email} was created concurrently (IntegrityError: {e}); "
                f"recovering the existing user"
            )
            existing_user = self._recover_existing_user(username, email, realm, user_info)
            if existing_user is not None:
                return existing_user

            # An IntegrityError that is NOT a "user already exists" collision
            # (e.g. some other constraint) and that we cannot recover from.
            logger.error(f"Could not find or create user {email} after IntegrityError: {e}")
            return None

        except Exception as e:
            # Unexpected, non-integrity failure. The savepoint has been rolled
            # back, so recovery queries run against a clean transaction.
            logger.error(f"Error creating user {email}: {e}", exc_info=True)
            existing_user = self._recover_existing_user(username, email, realm, user_info)
            if existing_user is not None:
                return existing_user

            logger.error(f"Could not find or create user {email} after error: {e}")
            return None

    def _recover_existing_user(
        self,
        username: str,
        email: str,
        realm: Realm,
        user_info: Dict[str, Any],
    ) -> Optional[UserProfile]:
        """Locate a user that already exists after a failed creation attempt.

        Called only after the creation savepoint has been rolled back, so the
        database connection is in a clean, usable state. Tries username, then
        email, then a direct case-insensitive query, and ensures the LMS
        username mapping and active status are in place before returning.
        """
        # First try by username (primary lookup).
        existing_user = self._find_existing_user_by_username(username, realm)
        if existing_user is not None:
            logger.info(
                f"Found existing user by username after creation error: "
                f"{existing_user.delivery_email} (ID: {existing_user.id})"
            )
            return self._finalize_recovered_user(existing_user, username, realm, user_info)

        # Then try by email (comprehensive).
        existing_user = self._find_existing_user_by_email(email, realm)
        if existing_user is not None:
            logger.info(
                f"Found existing user by email after creation error: "
                f"{email} (ID: {existing_user.id})"
            )
            return self._finalize_recovered_user(existing_user, username, realm, user_info)

        # Last resort: direct case-insensitive database query.
        try:
            from django.contrib.auth.models import UserManager
            normalized_email = UserManager.normalize_email(email)
            existing_user = UserProfile.objects.get(
                delivery_email__iexact=normalized_email.strip(),
                realm=realm,
            )
            logger.info(
                f"Found existing user by direct DB query after creation error: "
                f"{email} (ID: {existing_user.id})"
            )
            return self._finalize_recovered_user(existing_user, username, realm, user_info)
        except (UserProfile.DoesNotExist, UserProfile.MultipleObjectsReturned):
            return None

    def _finalize_recovered_user(
        self,
        existing_user: UserProfile,
        username: str,
        realm: Realm,
        user_info: Dict[str, Any],
    ) -> UserProfile:
        """Attach the LMS username mapping and reactivate a recovered user."""
        self._add_username_mapping(existing_user, username, realm)
        if not existing_user.is_active and user_info["is_active"]:
            do_reactivate_user(existing_user, acting_user=None)
        return existing_user

    @log_auth_attempts
    def authenticate(
        self,
        request: HttpRequest,
        *,
        username: str | None = None,
        testpress_jwt_token: Optional[str] = None,
        realm: Realm,
        return_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserProfile]:
        """
        Simple JWT authentication.

        1. Validate JWT token with TestPress
        2. Get user profile from TestPress
        3. Create or update Zulip user
        """
        if return_data is None:
            return_data = {}

        # Need JWT token
        if not testpress_jwt_token:
            return_data['testpress_jwt_missing'] = True
            return None

        # Step 1: Validate JWT token with TestPress
        try:
            testpress_data = testpress_jwt_validator.validate_token(testpress_jwt_token)
        except Exception as e:
            logger.error(f"JWT validation failed: {e}", exc_info=True)
            return_data['testpress_jwt_invalid'] = True
            return None

        if not testpress_data:
            return_data['testpress_jwt_invalid'] = True
            return None

        # Step 2: Get user profile from TestPress data
        try:
            user_info = self._get_user_info_from_testpress(testpress_data, realm)
        except Exception as e:
            logger.error(f"Error extracting user info: {e}", exc_info=True)
            return_data['testpress_data_invalid'] = True
            return None

        # Step 3: Create or update Zulip user
        try:
            user_profile = self._get_or_create_user(user_info, realm)
        except Exception as e:
            logger.error(f"Error creating/updating user: {e}", exc_info=True)
            return_data['user_creation_failed'] = True
            return None

        if not user_profile:
            return_data['user_creation_failed'] = True
            return None

        logger.info(f"JWT auth successful: {user_profile.delivery_email}")
        return user_profile

    def get_user(self, user_id: int) -> Optional[UserProfile]:
        """Get user by ID (Django requirement)."""
        try:
            return UserProfile.objects.get(pk=user_id)
        except UserProfile.DoesNotExist:
            return None