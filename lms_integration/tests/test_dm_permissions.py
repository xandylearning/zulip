"""
Tests for the LMS DM permissions endpoints (GET/PATCH /api/v1/lms/dm-permissions).

Covers loading the matrix and saving enabled/permission_matrix via JSON body.
"""

from zerver.lib.test_classes import ZulipTestCase

from lms_integration.models import RealmDMPermissionMatrix


class LmsDMPermissionsEndpointTest(ZulipTestCase):
    def test_patch_dm_permissions_persists_enabled(self) -> None:
        """PATCH with JSON body persists enabled."""
        iago = self.example_user("iago")
        realm = iago.realm
        result = self.json_patch(
            "/api/v1/lms/dm-permissions",
            {"enabled": True},
            HTTP_AUTHORIZATION=self.encode_user(iago),
        )
        data = self.assert_json_success(result)
        self.assertTrue(data["enabled"])
        obj = RealmDMPermissionMatrix.objects.get(realm=realm)
        self.assertTrue(obj.enabled)

    def test_patch_dm_permissions_persists_permission_matrix(self) -> None:
        """PATCH with JSON body persists permission_matrix."""
        iago = self.example_user("iago")
        realm = iago.realm
        matrix = {"mentor": ["admin", "owner", "mentor", "student"], "student": ["admin", "owner", "mentor"]}
        result = self.json_patch(
            "/api/v1/lms/dm-permissions",
            {"permission_matrix": matrix},
            HTTP_AUTHORIZATION=self.encode_user(iago),
        )
        data = self.assert_json_success(result)
        self.assertEqual(data["permission_matrix"], matrix)
        obj = RealmDMPermissionMatrix.objects.get(realm=realm)
        self.assertEqual(obj.permission_matrix, matrix)

    def test_patch_dm_permissions_persists_both(self) -> None:
        """PATCH with JSON body persists both enabled and permission_matrix."""
        iago = self.example_user("iago")
        realm = iago.realm
        matrix = {"mentor": ["admin", "owner", "student"], "student": ["admin", "owner", "mentor"]}
        result = self.json_patch(
            "/api/v1/lms/dm-permissions",
            {"enabled": True, "permission_matrix": matrix},
            HTTP_AUTHORIZATION=self.encode_user(iago),
        )
        data = self.assert_json_success(result)
        self.assertTrue(data["enabled"])
        self.assertEqual(data["permission_matrix"], matrix)
        obj = RealmDMPermissionMatrix.objects.get(realm=realm)
        self.assertTrue(obj.enabled)
        self.assertEqual(obj.permission_matrix, matrix)

    def test_get_dm_permissions_defaults(self) -> None:
        """GET returns correct defaults (enabled=True and default matrix)."""
        iago = self.example_user("iago")
        realm = iago.realm
        # Ensure no existing matrix
        RealmDMPermissionMatrix.objects.filter(realm=realm).delete()

        result = self.client_get("/api/v1/lms/dm-permissions", HTTP_AUTHORIZATION=self.encode_user(iago))
        data = self.assert_json_success(result)

        self.assertTrue(data["enabled"])
        expected_matrix = {
            "owner": ["owner", "admin", "mentor", "student"],
            "admin": ["owner", "admin", "mentor", "student"],
            "mentor": ["owner", "admin", "mentor", "student"],
            "student": ["mentor"],
        }
        self.assertEqual(data["permission_matrix"], expected_matrix)
