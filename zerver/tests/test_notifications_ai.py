from __future__ import annotations

import json
from typing import Any

from django.conf import settings as django_settings
from django.test import override_settings

from zerver.lib.test_classes import ZulipTestCase


class TestNotificationTemplateAI(ZulipTestCase):
    def test_requires_admin(self) -> None:
        user = self.example_user("cordelia")
        self.login_user(user)
        resp = self.client_post("/json/notification_templates/ai_generate", {"prompt": "x"})
        self.assert_json_error(resp, "Must be an organization administrator")

    def test_fallback_without_api_key(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)

        with override_settings(PORTKEY_API_KEY=""):
            resp = self.client_post("/json/notification_templates/ai_generate", {"prompt": "Welcome new users"})
            data = self.assert_json_success(resp)
            template = data["template"]
            self.assertEqual(template["template_type"], "text_only")
            self.assertTrue(template["ai_generated"])
            self.assertIn("Welcome", template["content"])  # echo of prompt

    def test_session_memory_tracks_conversation(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)

        with override_settings(PORTKEY_API_KEY=""):
            # First call - no conversation_id
            data1 = self.assert_json_success(
                self.client_post("/json/notification_templates/ai_generate", {"prompt": "First"})
            )
            conv = data1["conversation_id"]
            self.assertTrue(conv)

            # Second call - same conversation
            data2 = self.assert_json_success(
                self.client_post(
                    "/json/notification_templates/ai_generate",
                    {"prompt": "Second", "conversation_id": conv},
                )
            )
            self.assertEqual(data2["conversation_id"], conv)

    def test_feature_flag_disabled_blocks_when_no_api_key(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)

        with override_settings(BROADCAST_AI_TEMPLATES_ENABLED=False, PORTKEY_API_KEY=""):
            resp = self.client_post("/json/notification_templates/ai_generate", {"prompt": "x"})
            self.assert_json_error(resp, "AI template generation is disabled")


    def test_approve_plan_boolean_is_parsed(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)

        # Disable external calls; use fallback generator
        with override_settings(PORTKEY_API_KEY=""):
            # Step 1: Ask for a plan (no approval yet)
            data1 = self.assert_json_success(
                self.client_post(
                    "/json/notification_templates/ai_generate",
                    {"prompt": "Create a birthday card"},
                )
            )
            conv = data1["conversation_id"]
            self.assertTrue(conv)

            # Step 2: Approve plan using JSON boolean; should not error
            data2 = self.assert_json_success(
                self.client_post(
                    "/json/notification_templates/ai_generate",
                    {
                        "prompt": "Create a birthday card",
                        "conversation_id": conv,
                        # typed_endpoint Json[bool] expects JSON string
                        "approve_plan": json.dumps(True),
                    },
                )
            )
            # Either proceed to generation or complete; must not be error
            self.assertNotEqual(data2.get("status"), "error")

    def test_approve_plan_returns_template_in_fallback(self) -> None:
        admin = self.example_user("iago")
        self.login_user(admin)

        # No API key triggers fallback path which should still return a template
        with override_settings(PORTKEY_API_KEY=""):
            # Start conversation to get conversation_id
            data1 = self.assert_json_success(
                self.client_post(
                    "/json/notification_templates/ai_generate",
                    {"prompt": "Create a welcome card"},
                )
            )
            conv = data1["conversation_id"]

            # Approve plan and expect a template in response (fallback always returns template)
            data2 = self.assert_json_success(
                self.client_post(
                    "/json/notification_templates/ai_generate",
                    {
                        "prompt": "Create a welcome card",
                        "conversation_id": conv,
                        "approve_plan": json.dumps(True),
                    },
                )
            )
            # Validate template presence
            self.assertIn("template", data2)
            tmpl = data2["template"]
            self.assertIsInstance(tmpl, dict)
            self.assertIn("template_type", tmpl)


