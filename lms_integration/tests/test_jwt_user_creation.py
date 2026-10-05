"""
Regression tests for creating a brand-new Zulip user on first JWT login.
"""

from unittest.mock import MagicMock, patch

from lms_integration.auth_backend import LMS_USERNAME_AUTH_METHOD, TestPressJWTAuthBackend
from zerver.actions.realm_settings import do_set_realm_property
from zerver.lib.test_classes import ZulipTestCase
from zerver.lib.test_helpers import HostRequestMock
from zerver.models import NamedUserGroup, UserProfile
from zerver.models.groups import SystemGroups
from zerver.models.realms import get_realm
from zerver.models.users import ExternalAuthID


class JWTFirstLoginUserCreationTest(ZulipTestCase):
    @patch("lms_integration.auth_backend.testpress_jwt_validator.validate_token")
    def test_first_login_creates_full_member_faculty_user(
        self, mock_validate_token: MagicMock
    ) -> None:
        # Regression test: with waiting_period_threshold=0, do_create_user
        # inserted the role:faculty membership twice, so every first JWT login
        # failed with "Could not find or create user ... after IntegrityError".
        realm = get_realm("zulip")
        do_set_realm_property(realm, "waiting_period_threshold", 0, acting_user=None)
        mock_validate_token.return_value = {
            "email": "first.login@school.edu",
            "username": "first_login",
            "first_name": "First",
            "last_name": "Login",
            "is_active": True,
            "id": 4242,
        }
        return_data: dict[str, bool] = {}

        user_profile = TestPressJWTAuthBackend().authenticate(
            request=HostRequestMock(host=realm.host),
            testpress_jwt_token="valid_token",
            realm=realm,
            return_data=return_data,
        )

        assert user_profile is not None
        self.assertNotIn("user_creation_failed", return_data)
        self.assertEqual(user_profile.delivery_email, "first.login@school.edu")
        self.assertEqual(user_profile.role, UserProfile.ROLE_FACULTY)
        self.assertSetEqual(
            set(
                NamedUserGroup.objects.filter(direct_members=user_profile).values_list(
                    "name", flat=True
                )
            ),
            {SystemGroups.FACULTY, SystemGroups.FULL_MEMBERS},
        )
        self.assertTrue(
            ExternalAuthID.objects.filter(
                user=user_profile,
                external_auth_method_name=LMS_USERNAME_AUTH_METHOD,
                external_auth_id="first_login",
            ).exists()
        )
