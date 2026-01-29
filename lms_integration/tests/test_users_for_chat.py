"""
Tests for the LMS "users for chat" endpoint (GET /api/v1/lms/users/for-chat).

Covers response shape, default behavior, and role-based filtering for mentor
and student users, including behavior when the DM permission matrix is absent
or disabled.
"""

from zerver.lib.test_classes import ZulipTestCase

from lms_integration.models import (
    LMSUserMapping,
    RealmDMPermissionMatrix,
    Mentortostudent,
)


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
        """With no permission matrix, non-LMS users see realm members (no filtering)."""
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
                    "mentor": ["admin","owner","mentor","student"],
                    "student": [],
                },
            },
        )
        result = self.api_get(iago, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        self.assertIn("members", data)
        # Admin should see full realm membership (no filtering)
        self.assertGreaterEqual(len(data["members"]), 1)

    def test_lms_users_for_chat_mentor_sees_only_assigned_students_and_staff(self) -> None:
        """
        Mentor users see:
        - themselves
        - admins/owners
        - other mentors (per default matrix)
        - only students assigned to them via Mentortostudent
        even when no explicit permission matrix row exists.
        """
        # Set up users
        mentor = self.example_user("hamlet")
        admin = self.example_user("iago")
        other_mentor = self.example_user("othello")
        assigned_student = self.example_user("cordelia")
        unassigned_student = self.example_user("prospero")

        realm = mentor.realm

        # Map mentor and students into LMS with distinct IDs
        LMSUserMapping.objects.update_or_create(
            zulip_user=mentor,
            defaults={
                "lms_user_id": 1001,
                "lms_user_type": "mentor",
                "lms_username": "hamlet_mentor",
                "is_active": True,
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=assigned_student,
            defaults={
                "lms_user_id": 2001,
                "lms_user_type": "student",
                "lms_username": "cordelia_student",
                "is_active": True,
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=unassigned_student,
            defaults={
                "lms_user_id": 2002,
                "lms_user_type": "student",
                "lms_username": "prospero_student",
                "is_active": True,
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=other_mentor,
            defaults={
                "lms_user_id": 1002,
                "lms_user_type": "mentor",
                "lms_username": "othello_mentor",
                "is_active": True,
            },
        )

        # Create mentor→student assignment in LMS junction table
        # Mentortostudent.a_id is mentor LMS ID, b_id is student LMS ID
        Mentortostudent.objects.using("lms_db").create(
            a_id=1001,
            b_id=2001,
        )

        result = self.api_get(mentor, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        member_ids = {m["user_id"] for m in data["members"]}

        # Mentor should see:
        # - themself
        # - admin (owner/admin roles are always visible)
        # - other mentor (per default matrix mentor -> mentor)
        # - assigned student
        self.assertIn(mentor.id, member_ids)
        self.assertIn(admin.id, member_ids)
        self.assertIn(other_mentor.id, member_ids)
        self.assertIn(assigned_student.id, member_ids)

        # Mentor should NOT see unassigned student
        self.assertNotIn(unassigned_student.id, member_ids)

    def test_lms_users_for_chat_mentor_filtered_even_with_full_permissions(self) -> None:
        """
        Verify that mentors are filtered to their assigned students even if the
        permission matrix allows them to see ALL roles (which is the default, as
        admin/owner are implicitly allowed and the matrix covers the rest).
        """
        mentor = self.example_user("hamlet")
        assigned_student = self.example_user("cordelia")
        unassigned_student = self.example_user("prospero")
        realm = mentor.realm

        # 1. Enable matrix with ALL roles allowed for mentor
        RealmDMPermissionMatrix.objects.update_or_create(
            realm=realm,
            defaults={
                "enabled": True,
                "permission_matrix": {
                    "mentor": ["admin", "owner", "mentor", "student", "parent", "faculty"],
                    "student": ["mentor"],
                },
            },
        )

        # 2. Map users
        LMSUserMapping.objects.update_or_create(
            zulip_user=mentor,
            defaults={
                "lms_user_id": 1001,
                "lms_user_type": "mentor",
                "lms_username": "hamlet_mentor",
                "is_active": True,
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=assigned_student,
            defaults={
                "lms_user_id": 2001,
                "lms_user_type": "student",
                "lms_username": "cordelia_student",
                "is_active": True,
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=unassigned_student,
            defaults={
                "lms_user_id": 2002,
                "lms_user_type": "student",
                "lms_username": "prospero_student",
                "is_active": True,
            },
        )

        # 3. Create LMS relationship
        Mentortostudent.objects.using("lms_db").create(a_id=1001, b_id=2001)

        # 4. Fetch users
        result = self.api_get(mentor, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        member_ids = {m["user_id"] for m in data["members"]}

        # 5. Assert filtering applied
        self.assertIn(assigned_student.id, member_ids)
        self.assertNotIn(unassigned_student.id, member_ids)

    def test_lms_users_for_chat_student_sees_only_assigned_mentors_and_staff(self) -> None:
        """
        Student users see:
        - themselves (through standard /users data)
        - admins/owners
        - only mentors assigned to them via Mentortostudent
        even when no explicit permission matrix row exists.
        """
        student = self.example_user("hamlet")
        admin = self.example_user("iago")
        assigned_mentor = self.example_user("othello")
        unassigned_mentor = self.example_user("cordelia")

        realm = student.realm

        # Map student and mentors into LMS with distinct IDs
        LMSUserMapping.objects.update_or_create(
            zulip_user=student,
            defaults={
                "lms_user_id": 3001,
                "lms_user_type": "student",
                "lms_username": "hamlet_student",
                "is_active": True,
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=assigned_mentor,
            defaults={
                "lms_user_id": 4001,
                "lms_user_type": "mentor",
                "lms_username": "othello_mentor",
                "is_active": True,
            },
        )
        LMSUserMapping.objects.update_or_create(
            zulip_user=unassigned_mentor,
            defaults={
                "lms_user_id": 4002,
                "lms_user_type": "mentor",
                "lms_username": "cordelia_mentor",
                "is_active": True,
            },
        )

        # Create mentor→student assignment in LMS junction table
        Mentortostudent.objects.using("lms_db").create(
            a_id=4001,
            b_id=3001,
        )

        result = self.api_get(student, "/api/v1/lms/users/for-chat")
        data = self.assert_json_success(result)
        member_ids = {m["user_id"] for m in data["members"]}

        # Student should see:
        # - themself
        # - admin
        # - assigned mentor
        self.assertIn(student.id, member_ids)
        self.assertIn(admin.id, member_ids)
        self.assertIn(assigned_mentor.id, member_ids)

        # Student should NOT see unassigned mentor
        self.assertNotIn(unassigned_mentor.id, member_ids)
