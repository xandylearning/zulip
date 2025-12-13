"""
TestPress User Profile Synchronization

This module handles synchronizing user profile data from TestPress
to Zulip user profiles, including custom profile fields and avatar updates.
"""

import logging
from typing import Any, Dict

from zerver.models import UserProfile
from zerver.actions.user_settings import do_change_full_name
from zerver.lib.upload import upload_avatar_image

logger = logging.getLogger(__name__)


def sync_testpress_user_profile(user_profile: UserProfile, testpress_data: Dict[str, Any]) -> None:
    """
    Synchronize user profile data from TestPress to Zulip.

    Args:
        user_profile: Zulip UserProfile to update
        testpress_data: User data from TestPress API
    """
    try:
        # Sync full name if different
        testpress_first_name = testpress_data.get('first_name', '')
        testpress_last_name = testpress_data.get('last_name', '')
        testpress_full_name = f"{testpress_first_name} {testpress_last_name}".strip()

        if testpress_full_name and testpress_full_name != user_profile.full_name:
            do_change_full_name(user_profile, testpress_full_name, acting_user=None)
            logger.info(f"Updated full name for user {user_profile.delivery_email}: {testpress_full_name}")

        # Store TestPress user ID in a custom profile field if configured
        # This allows for future reference and debugging
        testpress_user_id = testpress_data.get('id')
        if testpress_user_id:
            _set_custom_profile_field(user_profile, 'testpress_user_id', str(testpress_user_id))

        # Store TestPress username if different from email
        testpress_username = testpress_data.get('username')
        if testpress_username and testpress_username != user_profile.delivery_email:
            _set_custom_profile_field(user_profile, 'testpress_username', testpress_username)

        # Sync avatar if available and enabled
        avatar_url = testpress_data.get('avatar_url') or testpress_data.get('profile_picture')
        if avatar_url:
            _sync_avatar_from_url(user_profile, avatar_url)

        logger.debug(f"Profile sync completed for user: {user_profile.delivery_email}")

    except Exception as e:
        logger.error(f"Error syncing TestPress profile data for user {user_profile.delivery_email}: {str(e)}")


def _set_custom_profile_field(user_profile: UserProfile, field_name: str, field_value: str) -> None:
    """
    Set a custom profile field value for the user.

    This is a placeholder implementation. You can customize this to map
    TestPress data to your specific custom profile fields.
    """
    # This would require custom profile fields to be set up in Zulip
    # For now, we'll just log the data that could be stored
    logger.debug(f"Would set custom field {field_name}={field_value} for user {user_profile.delivery_email}")

    # TODO: Implement actual custom profile field update if needed
    # from zerver.actions.custom_profile_fields import do_update_user_custom_profile_data_if_changed
    # from zerver.models import CustomProfileField
    #
    # try:
    #     field = CustomProfileField.objects.get(name=field_name, realm=user_profile.realm)
    #     profile_data = [{
    #         'id': field.id,
    #         'value': field_value
    #     }]
    #     do_update_user_custom_profile_data_if_changed(user_profile, profile_data)
    # except CustomProfileField.DoesNotExist:
    #     logger.warning(f"Custom profile field '{field_name}' not found")


def _sync_avatar_from_url(user_profile: UserProfile, avatar_url: str) -> None:
    """
    Sync user avatar from TestPress URL.

    This is a placeholder implementation. Avatar syncing requires
    additional security considerations and might not be needed.
    """
    # For security reasons, we'll just log the avatar URL for now
    # Implementing avatar sync would require:
    # 1. Downloading the image from TestPress
    # 2. Validating image format and size
    # 3. Uploading to Zulip's avatar storage
    # 4. Updating user's avatar

    logger.debug(f"TestPress avatar URL for user {user_profile.delivery_email}: {avatar_url}")

    # TODO: Implement actual avatar sync if needed
    # import requests
    # try:
    #     response = requests.get(avatar_url, timeout=10)
    #     if response.status_code == 200:
    #         upload_avatar_image(response.content, user_profile, user_profile)
    #         logger.info(f"Updated avatar for user {user_profile.delivery_email}")
    # except Exception as e:
    #     logger.error(f"Failed to sync avatar for user {user_profile.delivery_email}: {str(e)}")