"""
Email utility functions for LMS Integration.
Handles placeholder email generation and validation for users without email addresses.
"""

import logging
import re
from typing import Optional

from django.conf import settings
from django.core.validators import validate_email
from django.core.exceptions import ValidationError

from zerver.models import UserProfile
from zerver.lib.email_validation import email_allowed_for_realm, get_realm_email_validator
from zerver.models.realms import Realm, DisposableEmailError

# Import LMS integration settings
try:
    from lms_integration.settings import (
        LMS_NO_EMAIL_DOMAIN,
        LMS_AUTO_UPDATE_EMAILS,
        LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS,
        LMS_PLACEHOLDER_EMAIL_PREFIX,
        LMS_PLACEHOLDER_EMAIL_SUFFIX,
        LMS_ALLOW_PLACEHOLDER_EMAIL_CHANGES,
        LMS_INCLUDE_PLACEHOLDER_USERS_IN_EMAIL_OPERATIONS,
    )
except ImportError:
    # Fallback defaults if settings file doesn't exist
    LMS_NO_EMAIL_DOMAIN = "noemail.local"
    LMS_AUTO_UPDATE_EMAILS = True
    LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS = {
        'email_delivery': False,
        'in_app_notifications': True,
        'log_attempts': True,
        'track_metrics': True,
    }
    LMS_PLACEHOLDER_EMAIL_PREFIX = ""
    LMS_PLACEHOLDER_EMAIL_SUFFIX = ""
    LMS_ALLOW_PLACEHOLDER_EMAIL_CHANGES = False
    LMS_INCLUDE_PLACEHOLDER_USERS_IN_EMAIL_OPERATIONS = False

logger = logging.getLogger(__name__)

# Module-level cache for generated placeholder emails to avoid duplicate generation and logging
# Key: (username, domain), Value: generated_email
_placeholder_email_cache: dict[tuple[str, str], str] = {}
_cache_logged: set[tuple[str, str]] = set()  # Track which combinations have been logged


def _generate_placeholder_email_impl(username: str, domain: str) -> str:
    """
    Internal implementation of placeholder email generation (without caching/logging).
    
    Args:
        username: The user's username from LMS
        domain: Domain to use for the placeholder email
        
    Returns:
        Generated placeholder email address
    """
    # Clean username to ensure it's email-safe
    clean_username = clean_username_for_email(username)

    # Apply prefix and suffix
    email_local_part = f"{LMS_PLACEHOLDER_EMAIL_PREFIX}{clean_username}{LMS_PLACEHOLDER_EMAIL_SUFFIX}"

    placeholder_email = f"{email_local_part}@{domain}"
    return placeholder_email


def generate_placeholder_email(username: str, domain: Optional[str] = None) -> str:
    """
    Generate a placeholder email for a user without an email address.
    Uses memoization to avoid duplicate generation and logging for the same username+domain.

    Args:
        username: The user's username from LMS
        domain: Optional domain override. If not provided, uses LMS_NO_EMAIL_DOMAIN

    Returns:
        Generated placeholder email address

    Example:
        >>> generate_placeholder_email("john_doe")
        "john_doe@noemail.local"

        >>> generate_placeholder_email("mary_smith", "students.school.edu")
        "mary_smith@students.school.edu"
    """
    if domain is None:
        domain = LMS_NO_EMAIL_DOMAIN

    # Create cache key
    cache_key = (username, domain)
    
    # Check cache first
    if cache_key in _placeholder_email_cache:
        return _placeholder_email_cache[cache_key]
    
    # Generate the email
    placeholder_email = _generate_placeholder_email_impl(username, domain)
    
    # Cache it (with reasonable size limit to prevent memory issues)
    # Clear cache if it gets too large (keep last 1000 entries)
    if len(_placeholder_email_cache) > 1000:
        # Keep only the most recent 500 entries by clearing half
        keys_to_remove = list(_placeholder_email_cache.keys())[:500]
        for key in keys_to_remove:
            _placeholder_email_cache.pop(key, None)
            _cache_logged.discard(key)
    
    _placeholder_email_cache[cache_key] = placeholder_email
    
    # Log only the first time this username+domain combination is generated
    if cache_key not in _cache_logged:
        logger.info(f"Generated placeholder email '{placeholder_email}' for username '{username}'")
        _cache_logged.add(cache_key)
    
    return placeholder_email


def clean_username_for_email(username: str) -> str:
    """
    Clean a username to make it suitable for the local part of an email address.

    Args:
        username: The original username

    Returns:
        Cleaned username safe for email local part
    """
    # Remove/replace characters that aren't allowed in email local parts
    # Keep alphanumeric, dots, hyphens, and underscores
    clean_name = re.sub(r'[^a-zA-Z0-9.\-_]', '_', username)

    # Ensure it doesn't start or end with dots
    clean_name = clean_name.strip('.')

    # Ensure it's not empty
    if not clean_name:
        clean_name = "user"

    # Limit length (email local part should be <= 64 characters)
    if len(clean_name) > 64:
        clean_name = clean_name[:64].rstrip('.')

    return clean_name


def is_placeholder_email(email: str, domain: Optional[str] = None) -> bool:
    """
    Check if an email address is a placeholder email generated by this system.

    Args:
        email: Email address to check
        domain: Optional domain to check against. If not provided, uses LMS_NO_EMAIL_DOMAIN

    Returns:
        True if this is a placeholder email, False otherwise

    Example:
        >>> is_placeholder_email("john_doe@noemail.local")
        True

        >>> is_placeholder_email("john.doe@school.edu")
        False
    """
    if domain is None:
        domain = LMS_NO_EMAIL_DOMAIN

    return email.endswith(f"@{domain}")


def should_send_email_notification(user_profile: UserProfile) -> bool:
    """
    Determine if email notifications should be sent to this user.

    Args:
        user_profile: The UserProfile to check

    Returns:
        True if email notifications should be sent, False otherwise
    """
    # Check if this user has a placeholder email
    if is_placeholder_email(user_profile.delivery_email):
        return LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS.get('email_delivery', False)

    # For users with real emails, send notifications normally
    return True


def should_show_inapp_notifications(user_profile: UserProfile) -> bool:
    """
    Determine if in-app notifications should be shown to this user.

    Args:
        user_profile: The UserProfile to check

    Returns:
        True if in-app notifications should be shown, False otherwise
    """
    # Check if this user has a placeholder email
    if is_placeholder_email(user_profile.delivery_email):
        return LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS.get('in_app_notifications', True)

    # For users with real emails, show in-app notifications normally
    return True


def should_log_notification_attempts(user_profile: Optional[UserProfile]) -> bool:
    """
    Determine if notification attempts should be logged for this user.

    Args:
        user_profile: The UserProfile to check (can be None for pre-creation logging)

    Returns:
        True if notification attempts should be logged, False otherwise
    """
    # If user_profile is None, allow logging (e.g., during user creation)
    if user_profile is None:
        return LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS.get('log_attempts', True)
    
    # Check if this user has a placeholder email
    if is_placeholder_email(user_profile.delivery_email):
        return LMS_PLACEHOLDER_EMAIL_NOTIFICATIONS.get('log_attempts', True)

    # For users with real emails, don't log by default
    return False


def can_user_change_email(user_profile: UserProfile) -> bool:
    """
    Determine if a user can change their email address through Zulip settings.

    Args:
        user_profile: The UserProfile to check

    Returns:
        True if the user can change their email, False otherwise
    """
    # Check if this user has a placeholder email
    if is_placeholder_email(user_profile.delivery_email):
        return LMS_ALLOW_PLACEHOLDER_EMAIL_CHANGES

    # For users with real emails, allow changes normally
    return True


def should_include_in_email_operations(user_profile: UserProfile) -> bool:
    """
    Determine if a user should be included in email-based operations.

    Args:
        user_profile: The UserProfile to check

    Returns:
        True if the user should be included, False otherwise
    """
    # Check if this user has a placeholder email
    if is_placeholder_email(user_profile.delivery_email):
        return LMS_INCLUDE_PLACEHOLDER_USERS_IN_EMAIL_OPERATIONS

    # For users with real emails, include normally
    return True


def validate_and_prepare_email(
    email: Optional[str],
    username: str,
    realm: Realm,
    force_placeholder: bool = False
) -> tuple[str, bool]:
    """
    Validate an email or generate a placeholder, and check if it's allowed for the realm.

    Args:
        email: The email address to validate (can be None or empty)
        username: Username to use for placeholder generation
        realm: The Zulip realm to validate against
        force_placeholder: If True, always generate a placeholder even if email is provided

    Returns:
        Tuple of (email_address, is_placeholder)

    Raises:
        ValidationError: If the email is invalid and no placeholder can be generated
    """
    is_placeholder = False

    # If no email or forcing placeholder, generate one
    if not email or force_placeholder:
        email = generate_placeholder_email(username)
        is_placeholder = True

    # Validate email format
    try:
        validate_email(email)
    except ValidationError as e:
        logger.warning(f"Invalid email format '{email}' for username '{username}': {e}")
        if not is_placeholder:
            # Try generating a placeholder instead
            email = generate_placeholder_email(username)
            is_placeholder = True
            try:
                validate_email(email)
            except ValidationError:
                raise ValidationError(f"Cannot generate valid email for username '{username}'")

    # Check if email is allowed for realm (for real emails, not placeholders)
    if not is_placeholder:
        try:
            email_allowed_for_realm(email, realm)
        except ValidationError as e:
            logger.warning(f"Email '{email}' not allowed for realm {realm.string_id}: {e}")
            # Generate placeholder instead
            email = generate_placeholder_email(username)
            is_placeholder = True
        except DisposableEmailError as e:
            # Handle disposable/disallowed emails by falling back to a placeholder
            domain = email.split("@", 1)[1] if "@" in email else "unknown"
            logger.warning(
                "Disposable/disallowed email '%s' with domain '%s' for realm '%s'; "
                "replacing with placeholder. Error: %s",
                email,
                domain,
                realm.string_id,
                e,
            )
            email = generate_placeholder_email(username)
            is_placeholder = True

            # Validate the generated placeholder email to ensure it is well-formed
            try:
                validate_email(email)
            except ValidationError:
                raise ValidationError(f"Cannot generate valid placeholder email for username '{username}'")

    logger.info(
        f"Prepared email '{email}' for username '{username}' (placeholder: {is_placeholder})"
    )
    return email, is_placeholder


def update_email_if_changed(
    user_profile: UserProfile,
    new_email: Optional[str],
    username: str
) -> bool:
    """
    Update user's email if it has changed and auto-update is enabled.

    Args:
        user_profile: The UserProfile to potentially update
        new_email: The new email from LMS (can be None)
        username: The user's username for logging

    Returns:
        True if the email was updated, False otherwise
    """
    if not LMS_AUTO_UPDATE_EMAILS:
        return False

    current_is_placeholder = is_placeholder_email(user_profile.delivery_email)

    # If user currently has placeholder email and LMS now has a real email
    if current_is_placeholder and new_email:
        try:
            # Validate the new email
            validate_email(new_email)
            email_allowed_for_realm(new_email, user_profile.realm)

            # Update both email fields
            user_profile.delivery_email = new_email
            user_profile.email = new_email
            user_profile.save(update_fields=['delivery_email', 'email'])

            logger.info(f"Updated user '{username}' from placeholder email to real email '{new_email}'")
            return True

        except ValidationError as e:
            logger.warning(f"Cannot update to invalid email '{new_email}' for user '{username}': {e}")
            return False

    # If user has real email but LMS email has changed
    elif not current_is_placeholder and new_email and new_email != user_profile.delivery_email:
        try:
            # Validate the new email
            validate_email(new_email)
            email_allowed_for_realm(new_email, user_profile.realm)

            # Update both email fields
            user_profile.delivery_email = new_email
            user_profile.email = new_email
            user_profile.save(update_fields=['delivery_email', 'email'])

            logger.info(f"Updated user '{username}' email from '{user_profile.delivery_email}' to '{new_email}'")
            return True

        except ValidationError as e:
            logger.warning(f"Cannot update to invalid email '{new_email}' for user '{username}': {e}")
            return False

    return False


def log_placeholder_email_attempt(
    user_profile: Optional[UserProfile],
    operation: str,
    details: Optional[str] = None
) -> None:
    """
    Log an attempt to perform an email-based operation on a user with placeholder email.

    Args:
        user_profile: The UserProfile with placeholder email (can be None for pre-creation logging)
        operation: Description of the operation (e.g., "send_notification", "password_reset")
        details: Optional additional details to log
    """
    if not should_log_notification_attempts(user_profile):
        return

    # Build log message based on whether user_profile is available
    if user_profile is not None:
        log_message = (
            f"Placeholder email operation: {operation} for user '{user_profile.full_name}' "
            f"({user_profile.delivery_email})"
        )
    else:
        # For pre-creation logging, use details to provide context
        log_message = f"Placeholder email operation: {operation}"

    if details:
        log_message += f" - {details}"

    logger.info(log_message)


def get_placeholder_email_stats(realm: Realm) -> dict[str, int]:
    """
    Get statistics about placeholder emails in a realm.

    Args:
        realm: The Zulip realm to analyze

    Returns:
        Dictionary with placeholder email statistics
    """
    domain = LMS_NO_EMAIL_DOMAIN

    total_users = UserProfile.objects.filter(realm=realm, is_active=True).count()
    placeholder_users = UserProfile.objects.filter(
        realm=realm,
        is_active=True,
        delivery_email__endswith=f"@{domain}"
    ).count()

    return {
        'total_users': total_users,
        'placeholder_users': placeholder_users,
        'real_email_users': total_users - placeholder_users,
        'placeholder_percentage': round((placeholder_users / total_users * 100) if total_users > 0 else 0, 1)
    }