"""
TestPress JWT Authentication Backend

This module provides authentication backend that validates JWT tokens
from TestPress LMS and creates/updates Zulip user profiles based on
the TestPress user data.
"""

import logging
from typing import Any, Dict, Optional

from django.contrib.auth.backends import BaseBackend
from django.http import HttpRequest

from zerver.lib.exceptions import JsonableError
from zerver.models import Realm, UserProfile
from zerver.lib.users import check_full_name
from zerver.actions.create_user import do_create_user, do_reactivate_user
from zerver.actions.users import do_deactivate_user
from zerver.lib.email_validation import email_allowed_for_realm
from zproject.backends import ZulipAuthMixin, common_get_active_user, rate_limit_auth, log_auth_attempts

from .jwt_validator import testpress_jwt_validator
from .user_sync import sync_testpress_user_profile

logger = logging.getLogger(__name__)


class TestPressJWTAuthBackend(ZulipAuthMixin, BaseBackend):
    """
    Authentication backend that validates TestPress JWT tokens.

    This backend:
    1. Accepts JWT tokens from TestPress LMS
    2. Validates tokens by calling TestPress /me API endpoint
    3. Creates or updates Zulip user profiles based on TestPress user data
    4. Maps TestPress user roles to Zulip roles
    """

    name = "testpress-jwt"

    def _extract_user_info_from_testpress_data(self, testpress_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and normalize user information from TestPress API response."""
        # Extract email (primary identifier)
        email = testpress_data.get('email')
        if not email:
            raise JsonableError("No email found in TestPress user data")

        # Extract full name
        first_name = testpress_data.get('first_name', '')
        last_name = testpress_data.get('last_name', '')
        full_name = f"{first_name} {last_name}".strip()

        if not full_name:
            # Fallback to username or email prefix
            full_name = testpress_data.get('username') or email.split('@')[0]

        # Validate full name format
        try:
            check_full_name(full_name)
        except JsonableError:
            # If name validation fails, use email prefix as fallback
            full_name = email.split('@')[0]

        # Extract other user information
        user_info = {
            'email': email,
            'full_name': full_name,
            'username': testpress_data.get('username', email),
            'is_active': testpress_data.get('is_active', True),
            'testpress_id': testpress_data.get('id'),
            'testpress_data': testpress_data,  # Store full data for role mapping
        }

        logger.debug(f"Extracted user info: {user_info['email']}, active: {user_info['is_active']}")
        return user_info

    def _determine_user_role(self, testpress_data: Dict[str, Any]) -> int:
        """
        Determine Zulip user role based on TestPress user data.

        This method can be customized to map TestPress roles/permissions
        to appropriate Zulip roles (Member, Moderator, Administrator, etc.)
        """
        # Default to Member role
        from zerver.models import UserProfile

        # Check if user is staff/admin in TestPress
        if testpress_data.get('is_staff', False) or testpress_data.get('is_superuser', False):
            return UserProfile.ROLE_REALM_ADMINISTRATOR

        # Check for moderator-like permissions (customize as needed)
        # This is where you can add your existing role mapping logic

        # Default to Member role
        return UserProfile.ROLE_MEMBER

    def _get_or_create_user(self, user_info: Dict[str, Any], realm: Realm) -> Optional[UserProfile]:
        """Get existing user or create new user in Zulip."""
        email = user_info['email']

        # Check if email is allowed in this realm
        if not email_allowed_for_realm(email, realm):
            logger.warning(f"Email {email} not allowed for realm {realm.subdomain}")
            return None

        # Try to get existing user
        existing_user = common_get_active_user(email, realm)

        if existing_user:
            # Update existing user's profile if needed
            if existing_user.is_active and user_info['is_active']:
                # Sync user data from TestPress
                sync_testpress_user_profile(existing_user, user_info['testpress_data'])
                logger.debug(f"Updated existing user: {email}")
                return existing_user
            elif not existing_user.is_active and user_info['is_active']:
                # Reactivate deactivated user
                do_reactivate_user(existing_user, acting_user=None)
                sync_testpress_user_profile(existing_user, user_info['testpress_data'])
                logger.info(f"Reactivated user: {email}")
                return existing_user
            elif existing_user.is_active and not user_info['is_active']:
                # Deactivate user if they're inactive in TestPress
                do_deactivate_user(existing_user, acting_user=None)
                logger.info(f"Deactivated user: {email}")
                return None
            else:
                # User is inactive in both systems
                return None
        else:
            # Create new user if they're active in TestPress
            if not user_info['is_active']:
                logger.debug(f"Not creating inactive user: {email}")
                return None

            try:
                # Determine user role
                user_role = self._determine_user_role(user_info['testpress_data'])

                # Create new user
                new_user = do_create_user(
                    email=email,
                    password=None,  # No password needed for JWT auth
                    realm=realm,
                    full_name=user_info['full_name'],
                    acting_user=None,
                    role=user_role,
                )

                # Sync additional profile data
                sync_testpress_user_profile(new_user, user_info['testpress_data'])

                logger.info(f"Created new user: {email}")
                return new_user

            except Exception as e:
                logger.error(f"Failed to create user {email}: {str(e)}")
                return None

    @rate_limit_auth
    @log_auth_attempts
    def authenticate(
        self,
        request: HttpRequest,
        *,
        testpress_jwt_token: Optional[str] = None,
        realm: Realm,
        return_data: Optional[Dict[str, Any]] = None,
    ) -> Optional[UserProfile]:
        """
        Authenticate user using TestPress JWT token.

        Args:
            request: Django HTTP request
            testpress_jwt_token: JWT token from TestPress
            realm: Zulip realm for authentication
            return_data: Dictionary to store return data for error handling

        Returns:
            UserProfile if authentication successful, None otherwise
        """
        if return_data is None:
            return_data = {}

        # Check if JWT token is provided
        if not testpress_jwt_token:
            logger.warning("No TestPress JWT token provided")
            return_data['testpress_jwt_missing'] = True
            return None

        # Validate token against TestPress API
        try:
            testpress_data = testpress_jwt_validator.validate_token(testpress_jwt_token)
        except Exception as e:
            logger.error(f"Error validating TestPress JWT token: {str(e)}")
            return_data['testpress_api_error'] = True
            return None

        if not testpress_data:
            logger.warning("TestPress JWT token validation failed")
            return_data['testpress_jwt_invalid'] = True
            return None

        # Extract user information
        try:
            user_info = self._extract_user_info_from_testpress_data(testpress_data)
        except Exception as e:
            logger.error(f"Error extracting user info from TestPress data: {str(e)}")
            return_data['testpress_data_invalid'] = True
            return None

        # Get or create user in Zulip
        try:
            user_profile = self._get_or_create_user(user_info, realm)
        except Exception as e:
            logger.error(f"Error getting/creating user: {str(e)}")
            return_data['user_creation_failed'] = True
            return None

        if not user_profile:
            return_data['user_inactive_or_invalid'] = True
            return None

        logger.info(f"TestPress JWT authentication successful for user: {user_profile.delivery_email}")
        return user_profile

    def get_user(self, user_id: int) -> Optional[UserProfile]:
        """Get user by ID (Django requirement)."""
        try:
            return UserProfile.objects.get(pk=user_id)
        except UserProfile.DoesNotExist:
            return None