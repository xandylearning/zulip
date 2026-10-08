"""
Tests for the doubt-answer push endpoint (POST /api/v1/lms/notify/doubt-answer).

Covers bearer-secret auth, request validation, the LMS student lookup,
every delivery outcome (with the push senders mocked), the FCM
notification block built for terminated Android apps, and an end-to-end
pass through the real legacy FCM sender with Firebase mocked.
"""

from typing import TYPE_CHECKING, Any
from unittest import mock

import orjson
from django.test import override_settings
from firebase_admin import exceptions as firebase_exceptions
from typing_extensions import override

from lms_integration.doubt_notifications import MAX_BODY_LENGTH, MAX_TITLE_LENGTH
from lms_integration.models import LMSUserMapping
from zerver.actions.users import do_deactivate_user
from zerver.lib.push_notifications import (
    DOUBT_ANSWER_PUSH_EVENT,
    FCM_MESSAGES_CHANNEL_ID,
    _create_fcm_notification_content,
)
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.lib.test_classes import PushNotificationTestCase, ZulipTestCase
from zerver.models import PushDevice, PushDeviceToken, UserProfile

if TYPE_CHECKING:
    from django.test.client import _MonkeyPatchedWSGIResponse as TestHttpResponse

DOUBT_NOTIFY_URL = "/api/v1/lms/notify/doubt-answer"
# Placeholder secret that only exists in these tests.
TEST_DOUBT_NOTIFY_SECRET = "test-doubt-notify-secret"
VALID_AUTHORIZATION = f"Bearer {TEST_DOUBT_NOTIFY_SECRET}"

STUDENT_LMS_USER_ID = 4242
MENTOR_LMS_USER_ID = 5151
TICKET_ID = 31
ANSWER_ID = 77
ANSWER_TITLE = "Your doubt has an answer"
ANSWER_BODY = "Your teacher replied to your question about projectile motion."

DOUBT_NOTIFICATIONS_MODULE = "lms_integration.doubt_notifications"
DOUBT_NOTIFY_VIEW_LOGGER = "lms_integration.views_doubt_notifications"
PUSH_NOTIFICATIONS_LOGGER = "zerver.lib.push_notifications"
# Django logs every 5xx response on this logger at ERROR level.
DJANGO_REQUEST_LOGGER = "django.request"

E2EE_TEST_PUBLIC_KEY = "n4WTVqj8KH6u0vScRycR4TqRaHhFeJ0POvMb8LCu8iI="


def valid_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "lms_user_id": STUDENT_LMS_USER_ID,
        "ticket_id": TICKET_ID,
        "answer_id": ANSWER_ID,
        "title": ANSWER_TITLE,
        "body": ANSWER_BODY,
    }
    payload.update(overrides)
    return payload


def map_lms_user(user: UserProfile, lms_user_id: int, lms_user_type: str) -> None:
    LMSUserMapping.objects.create(
        zulip_user=user,
        lms_user_id=lms_user_id,
        lms_user_type=lms_user_type,
        lms_username=user.delivery_email,
    )


def post_doubt_answer(
    test_case: ZulipTestCase,
    body: bytes,
    headers: dict[str, str] | None = None,
) -> "TestHttpResponse":
    return test_case.client_post(
        DOUBT_NOTIFY_URL,
        body,
        content_type="application/json",
        headers={"Authorization": VALID_AUTHORIZATION} if headers is None else headers,
    )


def expected_push_data_without_time(student: UserProfile) -> dict[str, str]:
    return {
        "event": DOUBT_ANSWER_PUSH_EVENT,
        "type": DOUBT_ANSWER_PUSH_EVENT,
        "ticket_id": str(TICKET_ID),
        "answer_id": str(ANSWER_ID),
        "title": ANSWER_TITLE,
        "body": ANSWER_BODY,
        "server": student.realm.host,
        "realm_url": student.realm.url,
        "user_id": str(student.id),
    }


def outcome_log_line(level: str, delivered: bool, reason: str) -> str:
    return (
        f"{level}:{DOUBT_NOTIFICATIONS_MODULE}:Doubt answer push delivered={delivered} "
        f"reason={reason} lms_user_id={STUDENT_LMS_USER_ID} ticket_id={TICKET_ID} "
        f"answer_id={ANSWER_ID}"
    )


@override_settings(DOUBT_NOTIFY_SECRET=TEST_DOUBT_NOTIFY_SECRET)
class DoubtAnswerNotifyEndpointTest(ZulipTestCase):
    @override
    def setUp(self) -> None:
        super().setUp()
        self.student = self.example_user("hamlet")
        map_lms_user(self.student, STUDENT_LMS_USER_ID, "student")

    def register_legacy_devices(self) -> None:
        PushDeviceToken.objects.create(
            user=self.student, kind=PushDeviceToken.FCM, token="fcm-token-1"
        )
        PushDeviceToken.objects.create(
            user=self.student,
            kind=PushDeviceToken.APNS,
            token="apns-token-1",
            ios_app_id="org.zulip.Zulip",
        )

    def register_e2ee_device(self) -> None:
        PushDevice.objects.create(
            user=self.student,
            push_account_id=10,
            bouncer_device_id=1,
            token_kind=PushDevice.TokenKind.FCM,
            push_public_key=E2EE_TEST_PUBLIC_KEY,
        )

    def assert_retry_response(self, result: "TestHttpResponse", msg: str) -> None:
        self.assertEqual(result.status_code, 503)
        self.assertEqual(
            orjson.loads(result.content), {"result": "error", "msg": msg, "retry": True}
        )

    def test_returns_503_when_secret_not_configured(self) -> None:
        for unset_secret in (None, ""):
            with (
                self.subTest(unset_secret=unset_secret),
                self.settings(DOUBT_NOTIFY_SECRET=unset_secret),
                self.assertLogs(DOUBT_NOTIFY_VIEW_LOGGER, level="WARNING") as warn_logs,
                self.assertLogs(DJANGO_REQUEST_LOGGER, level="ERROR"),
            ):
                result = post_doubt_answer(self, orjson.dumps(valid_payload()))
            self.assert_json_error(
                result,
                "Doubt answer notifications are not configured on this server",
                status_code=503,
            )
            self.assertNotIn("retry", orjson.loads(result.content))
            self.assertIn("DOUBT_NOTIFY_SECRET is not configured", warn_logs.output[0])

    def test_rejects_requests_without_valid_bearer_secret(self) -> None:
        body = orjson.dumps(valid_payload())
        rejected_headers: dict[str, dict[str, str]] = {
            "missing header": {},
            "wrong secret": {"Authorization": "Bearer not-the-secret"},
            "empty bearer token": {"Authorization": "Bearer "},
            "non-bearer scheme": {"Authorization": f"Basic {TEST_DOUBT_NOTIFY_SECRET}"},
            "secret in another header": {"X-LMS-Webhook-Secret": TEST_DOUBT_NOTIFY_SECRET},
        }
        for case_name, headers in rejected_headers.items():
            with (
                self.subTest(case_name),
                self.assertLogs(DOUBT_NOTIFY_VIEW_LOGGER, level="WARNING"),
            ):
                result = post_doubt_answer(self, body, headers=headers)
            self.assert_json_error(result, "Invalid or missing bearer token", status_code=401)

    def test_rejects_secret_sent_in_body(self) -> None:
        body = orjson.dumps(valid_payload(secret=TEST_DOUBT_NOTIFY_SECRET))
        with self.assertLogs(DOUBT_NOTIFY_VIEW_LOGGER, level="WARNING"):
            result = post_doubt_answer(self, body, headers={})
        self.assert_json_error(result, "Invalid or missing bearer token", status_code=401)

    def test_accepts_case_insensitive_bearer_scheme(self) -> None:
        with self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO"):
            result = post_doubt_answer(
                self,
                orjson.dumps(valid_payload()),
                headers={"Authorization": f"bearer {TEST_DOUBT_NOTIFY_SECRET}"},
            )
        self.assertEqual(self.assert_json_success(result)["reason"], "no_devices")

    def test_rejects_non_post_methods(self) -> None:
        headers = {"Authorization": VALID_AUTHORIZATION}
        with self.assertLogs(level="WARNING"):
            result = self.client_get(DOUBT_NOTIFY_URL, headers=headers)
        self.assertEqual(result.status_code, 405)
        with self.assertLogs(level="WARNING"):
            result = self.client_patch(DOUBT_NOTIFY_URL, headers=headers)
        self.assertEqual(result.status_code, 405)

    def test_rejects_body_that_is_not_a_json_object(self) -> None:
        for body in (b"{not json", b"", orjson.dumps([valid_payload()])):
            with self.subTest(body=body):
                result = post_doubt_answer(self, body)
                self.assert_json_error(result, "Request body must be a JSON object")

    def test_rejects_missing_fields(self) -> None:
        for field_name in ("lms_user_id", "ticket_id", "answer_id", "title", "body"):
            payload = valid_payload()
            del payload[field_name]
            with self.subTest(field_name=field_name):
                result = post_doubt_answer(self, orjson.dumps(payload))
                self.assert_json_error(result, f"Invalid or missing field: {field_name}")

    def test_rejects_invalid_field_values(self) -> None:
        invalid_values: list[tuple[str, Any]] = [
            ("lms_user_id", True),
            ("lms_user_id", 0),
            ("lms_user_id", -5),
            ("lms_user_id", "4242"),
            ("lms_user_id", 4242.0),
            ("lms_user_id", None),
            ("ticket_id", False),
            ("ticket_id", 0),
            ("ticket_id", "31"),
            ("answer_id", True),
            ("answer_id", -1),
            ("answer_id", [ANSWER_ID]),
            ("title", ""),
            ("title", "   "),
            ("title", "x" * (MAX_TITLE_LENGTH + 1)),
            ("title", 12),
            ("body", ""),
            ("body", "\n\t"),
            ("body", "x" * (MAX_BODY_LENGTH + 1)),
            ("body", None),
        ]
        for field_name, invalid_value in invalid_values:
            with self.subTest(field_name=field_name, invalid_value=invalid_value):
                result = post_doubt_answer(
                    self, orjson.dumps(valid_payload(**{field_name: invalid_value}))
                )
                self.assert_json_error(result, f"Invalid or missing field: {field_name}")

    def test_no_user_when_lms_user_is_not_mapped(self) -> None:
        with self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO") as info_logs:
            result = post_doubt_answer(
                self, orjson.dumps(valid_payload(lms_user_id=STUDENT_LMS_USER_ID + 1))
            )
        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (False, "no_user"))
        self.assertIn("reason=no_user", info_logs.output[0])

    def test_no_user_when_lms_user_is_a_mentor(self) -> None:
        map_lms_user(self.example_user("othello"), MENTOR_LMS_USER_ID, "mentor")
        with self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO"):
            result = post_doubt_answer(
                self, orjson.dumps(valid_payload(lms_user_id=MENTOR_LMS_USER_ID))
            )
        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (False, "no_user"))

    def test_no_user_when_student_is_deactivated(self) -> None:
        self.register_legacy_devices()
        do_deactivate_user(self.student, acting_user=None)
        with (
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO") as info_logs,
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications_legacy"
            ) as legacy_send,
        ):
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))
        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (False, "no_user"))
        self.assertEqual(info_logs.output, [outcome_log_line("INFO", False, "no_user")])
        legacy_send.assert_not_called()

    def test_no_devices_when_student_has_no_completed_registration(self) -> None:
        # An E2EE registration still pending with the bouncer cannot receive pushes.
        PushDevice.objects.create(
            user=self.student,
            push_account_id=10,
            bouncer_device_id=None,
            token_kind=PushDevice.TokenKind.FCM,
            push_public_key=E2EE_TEST_PUBLIC_KEY,
        )
        with self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO") as info_logs:
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))
        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (False, "no_devices"))
        self.assertEqual(info_logs.output, [outcome_log_line("INFO", False, "no_devices")])

    def test_sends_doubt_payload_to_legacy_devices(self) -> None:
        self.register_legacy_devices()
        with (
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO") as info_logs,
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications_legacy", return_value=2
            ) as legacy_send,
            mock.patch(f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications") as e2ee_send,
        ):
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))

        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (True, "sent"))
        e2ee_send.assert_not_called()
        legacy_send.assert_called_once()
        recipient, apns_payload, gcm_payload, gcm_options = legacy_send.call_args.args
        self.assertEqual(recipient.id, self.student.id)

        self.assertTrue(all(isinstance(value, str) for value in gcm_payload.values()))
        self.assertTrue(gcm_payload["time"].isdigit())
        gcm_payload_without_time = {
            key: value for key, value in gcm_payload.items() if key != "time"
        }
        self.assertEqual(gcm_payload_without_time, expected_push_data_without_time(self.student))
        self.assertEqual(gcm_options, {"priority": "high"})

        self.assertEqual(apns_payload["alert"], {"title": ANSWER_TITLE, "body": ANSWER_BODY})
        self.assertEqual(apns_payload["sound"], "default")
        self.assertEqual(apns_payload["custom"], gcm_payload)

        self.assertEqual(info_logs.output, [outcome_log_line("INFO", True, "sent")])
        self.assertNotIn(ANSWER_TITLE, info_logs.output[0])
        self.assertNotIn(ANSWER_BODY, info_logs.output[0])

    def test_accepts_title_and_body_at_max_length(self) -> None:
        self.register_legacy_devices()
        longest_title = "t" * MAX_TITLE_LENGTH
        longest_body = "b" * MAX_BODY_LENGTH
        with (
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO"),
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications_legacy", return_value=1
            ) as legacy_send,
        ):
            result = post_doubt_answer(
                self, orjson.dumps(valid_payload(title=longest_title, body=longest_body))
            )
        self.assertEqual(self.assert_json_success(result)["reason"], "sent")
        gcm_payload = legacy_send.call_args.args[2]
        self.assertEqual((gcm_payload["title"], gcm_payload["body"]), (longest_title, longest_body))

    def test_sends_doubt_payload_to_e2ee_devices(self) -> None:
        self.register_e2ee_device()
        with (
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO"),
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications", return_value=1
            ) as e2ee_send,
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications_legacy"
            ) as legacy_send,
        ):
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))

        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (True, "sent"))
        legacy_send.assert_not_called()
        recipient, payload_data_to_encrypt = e2ee_send.call_args.args
        self.assertEqual(recipient.id, self.student.id)
        payload_without_time = {
            key: value for key, value in payload_data_to_encrypt.items() if key != "time"
        }
        self.assertEqual(payload_without_time, expected_push_data_without_time(self.student))

    def test_delivered_when_one_path_succeeds_and_other_must_retry(self) -> None:
        self.register_legacy_devices()
        self.register_e2ee_device()
        with (
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO") as logs,
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications_legacy",
                side_effect=PushNotificationBouncerRetryLaterError("Network error"),
            ),
            mock.patch(f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications", return_value=1),
        ):
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))

        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (True, "sent"))
        self.assertIn("legacy devices deferred by push service", logs.output[0])
        self.assertEqual(logs.output[1], outcome_log_line("INFO", True, "sent"))

    def test_returns_503_retry_when_push_service_asks_to_retry_later(self) -> None:
        self.register_legacy_devices()
        with (
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="WARNING") as warn_logs,
            self.assertLogs(DJANGO_REQUEST_LOGGER, level="ERROR"),
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications_legacy",
                side_effect=PushNotificationBouncerRetryLaterError("Network error"),
            ),
        ):
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))

        self.assert_retry_response(result, "Push notification service is temporarily unavailable")
        self.assertEqual(
            warn_logs.output[-1],
            outcome_log_line("WARNING", False, "push_service_retry_later"),
        )

    def test_returns_503_retry_when_every_device_fails(self) -> None:
        self.register_legacy_devices()
        with (
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="WARNING") as warn_logs,
            self.assertLogs(DJANGO_REQUEST_LOGGER, level="ERROR"),
            mock.patch(
                f"{DOUBT_NOTIFICATIONS_MODULE}.send_push_notifications_legacy", return_value=0
            ),
        ):
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))

        self.assert_retry_response(result, "Push notification delivery failed for every device")
        self.assertEqual(
            warn_logs.output, [outcome_log_line("WARNING", False, "all_devices_failed")]
        )


class DoubtAnswerFcmNotificationTest(PushNotificationTestCase):
    def test_fcm_notification_content_for_doubt_answer(self) -> None:
        doubt_answer_content = _create_fcm_notification_content(
            {
                "event": DOUBT_ANSWER_PUSH_EVENT,
                "title": ANSWER_TITLE,
                "body": ANSWER_BODY,
                "answer_id": str(ANSWER_ID),
            },
            {},
        )
        self.assertEqual(
            doubt_answer_content,
            {
                "title": ANSWER_TITLE,
                "body": ANSWER_BODY,
                "channel_id": FCM_MESSAGES_CHANNEL_ID,
                "tag": f"doubt_answer:{ANSWER_ID}",
            },
        )

        message_content = _create_fcm_notification_content(
            {"event": "message", "sender_full_name": "Iago", "content": "Hello"}, {}
        )
        assert doubt_answer_content is not None
        assert message_content is not None
        self.assertEqual(doubt_answer_content["channel_id"], message_content["channel_id"])

    @override_settings(DOUBT_NOTIFY_SECRET=TEST_DOUBT_NOTIFY_SECRET)
    def test_legacy_fcm_push_carries_doubt_notification_block(self) -> None:
        map_lms_user(self.user_profile, STUDENT_LMS_USER_ID, "student")
        self.setup_fcm_tokens()
        with (
            self.mock_fcm() as (_mock_fcm_app, mock_fcm_messaging),
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="INFO") as info_logs,
        ):
            mock_fcm_messaging.send_each.return_value = self.make_fcm_success_response(
                self.fcm_tokens
            )
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))

        data = self.assert_json_success(result)
        self.assertEqual((data["delivered"], data["reason"]), (True, "sent"))
        self.assertEqual(info_logs.output, [outcome_log_line("INFO", True, "sent")])

        self.assertEqual(mock_fcm_messaging.AndroidNotification.call_count, len(self.fcm_tokens))
        mock_fcm_messaging.AndroidNotification.assert_called_with(
            title=ANSWER_TITLE,
            body=ANSWER_BODY,
            channel_id=FCM_MESSAGES_CHANNEL_ID,
            sound="default",
            tag=f"doubt_answer:{ANSWER_ID}",
            click_action="android.intent.action.VIEW",
        )
        mock_fcm_messaging.Notification.assert_called_with(title=ANSWER_TITLE, body=ANSWER_BODY)
        self.assertEqual(mock_fcm_messaging.AndroidConfig.call_args.kwargs["priority"], "high")
        sent_data = mock_fcm_messaging.Message.call_args.kwargs["data"]
        sent_data_without_time = {key: value for key, value in sent_data.items() if key != "time"}
        self.assertEqual(sent_data_without_time, expected_push_data_without_time(self.user_profile))

    @override_settings(DOUBT_NOTIFY_SECRET=TEST_DOUBT_NOTIFY_SECRET)
    def test_legacy_fcm_failure_on_every_device_returns_503_retry(self) -> None:
        map_lms_user(self.user_profile, STUDENT_LMS_USER_ID, "student")
        self.setup_fcm_tokens()
        with (
            self.mock_fcm() as (_mock_fcm_app, mock_fcm_messaging),
            self.assertLogs(PUSH_NOTIFICATIONS_LOGGER, level="WARNING"),
            self.assertLogs(DOUBT_NOTIFICATIONS_MODULE, level="WARNING") as warn_logs,
            self.assertLogs(DJANGO_REQUEST_LOGGER, level="ERROR"),
        ):
            mock_fcm_messaging.send_each.side_effect = firebase_exceptions.FirebaseError(
                firebase_exceptions.UNAVAILABLE, "FCM unavailable"
            )
            result = post_doubt_answer(self, orjson.dumps(valid_payload()))

        self.assertEqual(result.status_code, 503)
        self.assertEqual(
            orjson.loads(result.content),
            {
                "result": "error",
                "msg": "Push notification delivery failed for every device",
                "retry": True,
            },
        )
        self.assertEqual(
            warn_logs.output, [outcome_log_line("WARNING", False, "all_devices_failed")]
        )
