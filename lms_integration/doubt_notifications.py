"""
Push notifications telling a student that their doubt has an answer.

The doubt-solving service calls POST /api/v1/lms/notify/doubt-answer
(see `views_doubt_notifications.py`). This module owns everything behind
that thin view: bearer-secret check, request validation, the LMS
student -> Zulip user lookup, and delivery to every push device the
student registered (legacy FCM/APNs tokens and E2EE bouncer devices),
mirroring how `zulip_calls_plugin` sends its call pushes.
"""

import hmac
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import orjson
from django.utils.timezone import now as timezone_now

from lms_integration.models import LMSUserMapping
from zerver.lib.push_notifications import (
    DOUBT_ANSWER_PUSH_EVENT,
    send_push_notifications,
    send_push_notifications_legacy,
)
from zerver.lib.remote_server import PushNotificationBouncerRetryLaterError
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.models import PushDevice, PushDeviceToken, UserProfile

logger = logging.getLogger(__name__)

# Business rules from the doubt-answer notification contract.
MAX_TITLE_LENGTH = 100
MAX_BODY_LENGTH = 200

LMS_STUDENT_USER_TYPE = "student"
BEARER_AUTH_SCHEME = "bearer"

# High FCM priority is what lets the push wake a terminated or dozing
# Android app and show its notification block.
FCM_HIGH_PRIORITY = "high"
APNS_DEFAULT_SOUND = "default"

INVALID_JSON_BODY_MESSAGE = "Request body must be a JSON object"


class InvalidDoubtAnswerRequestError(Exception):
    """The request body does not satisfy the doubt-answer contract.

    The message is safe to return to the caller verbatim."""


class DoubtAnswerDeliveryOutcome(Enum):
    SENT = "sent"
    NO_USER = "no_user"
    NO_DEVICES = "no_devices"
    PUSH_SERVICE_RETRY_LATER = "push_service_retry_later"
    ALL_DEVICES_FAILED = "all_devices_failed"


# Outcomes where nothing reached the student and the caller should retry.
RETRYABLE_OUTCOMES = frozenset(
    {
        DoubtAnswerDeliveryOutcome.PUSH_SERVICE_RETRY_LATER,
        DoubtAnswerDeliveryOutcome.ALL_DEVICES_FAILED,
    }
)


@dataclass(frozen=True)
class DoubtAnswerNotification:
    lms_user_id: int
    ticket_id: int
    answer_id: int
    title: str
    body: str


def is_authorized_doubt_notify_request(authorization_header: str, expected_secret: str) -> bool:
    """Accepts only `Authorization: Bearer <secret>`, compared in constant time."""
    scheme, _, provided_secret = authorization_header.partition(" ")
    if scheme.lower() != BEARER_AUTH_SCHEME or not provided_secret:
        return False
    return hmac.compare_digest(provided_secret.encode(), expected_secret.encode())


def _invalid_field_error(field_name: str) -> InvalidDoubtAnswerRequestError:
    return InvalidDoubtAnswerRequestError(f"Invalid or missing field: {field_name}")


def _parse_positive_int(payload: dict[str, Any], field_name: str) -> int:
    value = payload.get(field_name)
    # JSON true/false decode to bool, which is a subclass of int.
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _invalid_field_error(field_name)
    return value


def _parse_bounded_text(payload: dict[str, Any], field_name: str, max_length: int) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip() or len(value) > max_length:
        raise _invalid_field_error(field_name)
    return value


def parse_doubt_answer_request_body(raw_body: bytes) -> DoubtAnswerNotification:
    try:
        payload = orjson.loads(raw_body)
    except orjson.JSONDecodeError:
        raise InvalidDoubtAnswerRequestError(INVALID_JSON_BODY_MESSAGE)
    if not isinstance(payload, dict):
        raise InvalidDoubtAnswerRequestError(INVALID_JSON_BODY_MESSAGE)

    return DoubtAnswerNotification(
        lms_user_id=_parse_positive_int(payload, "lms_user_id"),
        ticket_id=_parse_positive_int(payload, "ticket_id"),
        answer_id=_parse_positive_int(payload, "answer_id"),
        title=_parse_bounded_text(payload, "title", MAX_TITLE_LENGTH),
        body=_parse_bounded_text(payload, "body", MAX_BODY_LENGTH),
    )


def _find_active_student(lms_user_id: int) -> UserProfile | None:
    try:
        mapping = LMSUserMapping.objects.select_related("zulip_user__realm").get(
            lms_user_id=lms_user_id, lms_user_type=LMS_STUDENT_USER_TYPE
        )
    except LMSUserMapping.DoesNotExist:
        return None
    student = mapping.zulip_user
    if not student.is_active:
        return None
    return student


def build_doubt_answer_push_data(
    student: UserProfile, notification: DoubtAnswerNotification
) -> dict[str, str]:
    """The data payload shared by FCM, APNs (`custom`) and E2EE pushes.

    Every value is a string, as FCM requires for its `data` block."""
    realm = student.realm
    return {
        "event": DOUBT_ANSWER_PUSH_EVENT,
        "type": DOUBT_ANSWER_PUSH_EVENT,
        "ticket_id": str(notification.ticket_id),
        "answer_id": str(notification.answer_id),
        "title": notification.title,
        "body": notification.body,
        "server": realm.host,
        "realm_url": realm.url,
        "user_id": str(student.id),
        "time": str(datetime_to_timestamp(timezone_now())),
    }


def _log_outcome(
    notification: DoubtAnswerNotification, outcome: DoubtAnswerDeliveryOutcome
) -> None:
    # Identifiers only: the title/body are student content.
    logger.log(
        logging.WARNING if outcome in RETRYABLE_OUTCOMES else logging.INFO,
        "Doubt answer push delivered=%s reason=%s lms_user_id=%d ticket_id=%d answer_id=%d",
        outcome is DoubtAnswerDeliveryOutcome.SENT,
        outcome.value,
        notification.lms_user_id,
        notification.ticket_id,
        notification.answer_id,
    )


def notify_student_of_doubt_answer(
    notification: DoubtAnswerNotification,
) -> DoubtAnswerDeliveryOutcome:
    """Pushes the answer notification to every registered device of the student.

    Delivery counts as successful when at least one device was sent to;
    otherwise the outcome tells the caller whether to retry."""
    student = _find_active_student(notification.lms_user_id)
    if student is None:
        _log_outcome(notification, DoubtAnswerDeliveryOutcome.NO_USER)
        return DoubtAnswerDeliveryOutcome.NO_USER

    has_legacy_devices = PushDeviceToken.objects.filter(user=student).exists()
    has_e2ee_devices = PushDevice.objects.filter(
        user=student, bouncer_device_id__isnull=False
    ).exists()
    if not has_legacy_devices and not has_e2ee_devices:
        _log_outcome(notification, DoubtAnswerDeliveryOutcome.NO_DEVICES)
        return DoubtAnswerDeliveryOutcome.NO_DEVICES

    push_data = build_doubt_answer_push_data(student, notification)
    sent_device_count = 0
    push_service_asked_to_retry = False

    if has_legacy_devices:
        apns_payload: dict[str, Any] = {
            "alert": {"title": notification.title, "body": notification.body},
            "sound": APNS_DEFAULT_SOUND,
            "custom": dict(push_data),
        }
        gcm_options = {"priority": FCM_HIGH_PRIORITY}
        try:
            sent_device_count += send_push_notifications_legacy(
                student, apns_payload, dict(push_data), gcm_options
            )
        except PushNotificationBouncerRetryLaterError as error:
            logger.warning(
                "Doubt answer push to legacy devices deferred by push service, "
                "lms_user_id=%d answer_id=%d: %s",
                notification.lms_user_id,
                notification.answer_id,
                error.msg,
            )
            push_service_asked_to_retry = True

    if has_e2ee_devices:
        try:
            sent_device_count += send_push_notifications(student, dict(push_data))
        except PushNotificationBouncerRetryLaterError as error:
            logger.warning(
                "Doubt answer push to E2EE devices deferred by push service, "
                "lms_user_id=%d answer_id=%d: %s",
                notification.lms_user_id,
                notification.answer_id,
                error.msg,
            )
            push_service_asked_to_retry = True

    if sent_device_count > 0:
        outcome = DoubtAnswerDeliveryOutcome.SENT
    elif push_service_asked_to_retry:
        outcome = DoubtAnswerDeliveryOutcome.PUSH_SERVICE_RETRY_LATER
    else:
        outcome = DoubtAnswerDeliveryOutcome.ALL_DEVICES_FAILED
    _log_outcome(notification, outcome)
    return outcome
