"""
Tests for the LMS "users for chat" endpoint (GET /api/v1/lms/users/for-chat).

Covers response shape, permission-matrix-disabled behavior, and role-based
filtering (mentor/student) when the matrix is enabled.
"""

from unittest.mock import patch

from zerver.lib.test_classes import ZulipTestCase

from lms_integration.models import LMSUserMapping, RealmDMPermissionMatrix


class LmsUsersForChatEndpointTest(ZulipTestCase):
    def test_lms_users_for_chat_response_shape(self) -> None:
        """Response has result, msg, and members; each member has user_id, email, full_name."""
        hamlet = self.example_user("hamlet")
        result = self.api_get(hamlet, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        self.assertIn("result", data)
        self.assertIn("msg", data)
        self.assertIn("members", data)
        self.assertEqual(data["result"], "success")
        self.assertIsInstance(data["members"], list)
        for member in data["members"]:
            self.assertIn("user_id", member)
            self.assertIn("email", member)
            self.assertIn("full_name", member)

    def test_lms_users_for_chat_permission_matrix_disabled(self) -> None:
        """With no permission matrix or disabled, endpoint returns realm members."""
        hamlet = self.example_user("hamlet")
        result = self.api_get(hamlet, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        self.assertGreaterEqual(len(data["members"]), 1)
        member_ids = {m["user_id"] for m in data["members"]}
        self.assertIn(hamlet.id, member_ids)

    def test_lms_users_for_chat_permission_matrix_enabled_admin_sees_all(self) -> None:
        """With matrix enabled, owner/admin still see everyone (unfiltered)."""
        iago = self.example_user("iago")
        realm = iago.realm
        RealmDMPermissionMatrix.objects.update_or_create(
            realm=realm,
            defaults={
                "enabled": True,
                "permission_matrix": {
                    "member": ["admin", "owner"],
                },
            },
        )
        result = self.api_get(iago, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        self.assertIn("members", data)
        # Admin should see full realm membership (no filtering)
        self.assertGreaterEqual(len(data["members"]), 1)

    def test_lms_users_for_chat_permission_matrix_enabled_mentor_filtered(self) -> None:
        """With matrix enabled and user as mentor, members are restricted to filtered set."""
        hamlet = self.example_user("hamlet")
        othello = self.example_user("othello")
        realm = hamlet.realm
        RealmDMPermissionMatrix.objects.update_or_create(
            realm=realm,
            defaults={
                "enabled": True,
                "permission_matrix": {
                    "mentor": ["admin", "owner", "mentor", "student"],
                    "student": ["admin", "owner", "mentor"],
                },
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=hamlet,
            defaults={
                "lms_user_id": 1001,
                "lms_user_type": "mentor",
                "lms_username": "hamlet_mentor",
                "is_active": True,
            },
        )
        allowed_ids = {hamlet.id, othello.id}
        with patch(
            "lms_integration.lib.user_filtering.get_filtered_user_ids_by_role",
            return_value=list(allowed_ids),
        ):
            result = self.api_get(hamlet, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        self.assertIn("members", data)
        returned_ids = {m["user_id"] for m in data["members"]}
        self.assertEqual(returned_ids, allowed_ids)

    def test_lms_users_for_chat_permission_matrix_enabled_student_filtered(self) -> None:
        """With matrix enabled and user as student, members are restricted to filtered set."""
        hamlet = self.example_user("hamlet")
        iago = self.example_user("iago")
        realm = hamlet.realm
        RealmDMPermissionMatrix.objects.update_or_create(
            realm=realm,
            defaults={
                "enabled": True,
                "permission_matrix": {
                    "mentor": ["admin", "owner", "mentor", "student"],
                    "student": ["admin", "owner", "mentor"],
                },
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=hamlet,
            defaults={
                "lms_user_id": 2001,
                "lms_user_type": "student",
                "lms_username": "hamlet_student",
                "is_active": True,
            },
        )
        allowed_ids = {hamlet.id, iago.id}
        with patch(
            "lms_integration.lib.user_filtering.get_filtered_user_ids_by_role",
            return_value=list(allowed_ids),
        ):
            result = self.api_get(hamlet, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        self.assertIn("members", data)
        returned_ids = {m["user_id"] for m in data["members"]}
        self.assertEqual(returned_ids, allowed_ids)
