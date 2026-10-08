"""
Server-to-server endpoint the doubt-solving service calls to push
"your doubt has an answer" to a student's phone.

Not a user-session endpoint: the only credential is the
`Authorization: Bearer <DOUBT_NOTIFY_SECRET>` header, so it is routed with
plain `path()` (not `rest_path()`) and is CSRF-exempt, like
`lms_user_webhook`. Validation, lookup and delivery live in
`lms_integration.doubt_notifications`.
"""

import logging
from http import HTTPStatus

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from lms_integration.doubt_notifications import (
    DoubtAnswerDeliveryOutcome,
    InvalidDoubtAnswerRequestError,
    is_authorized_doubt_notify_request,
    notify_student_of_doubt_answer,
    parse_doubt_answer_request_body,
)
from zerver.decorator import require_post
from zerver.lib.response import json_error, json_response, json_success

logger = logging.getLogger(__name__)


def _retry_later_response(message: str) -> HttpResponse:
    return json_response(
        res_type="error",
        msg=message,
        data={"retry": True},
        status=HTTPStatus.SERVICE_UNAVAILABLE,
    )


@csrf_exempt
@require_post
def lms_notify_doubt_answer(request: HttpRequest) -> HttpResponse:
    """POST /api/v1/lms/notify/doubt-answer"""
    expected_secret = settings.DOUBT_NOTIFY_SECRET
    if not expected_secret:
        logger.warning("Rejected doubt answer notification: DOUBT_NOTIFY_SECRET is not configured")
        return json_error(
            "Doubt answer notifications are not configured on this server",
            status=HTTPStatus.SERVICE_UNAVAILABLE,
        )

    if not is_authorized_doubt_notify_request(
        request.headers.get("Authorization", ""), expected_secret
    ):
        logger.warning("Rejected doubt answer notification: missing or invalid bearer token")
        return json_error("Invalid or missing bearer token", status=HTTPStatus.UNAUTHORIZED)

    try:
        notification = parse_doubt_answer_request_body(request.body)
    except InvalidDoubtAnswerRequestError as error:
        return json_error(str(error), status=HTTPStatus.BAD_REQUEST)

    outcome = notify_student_of_doubt_answer(notification)
    match outcome:
        case DoubtAnswerDeliveryOutcome.SENT:
            return json_success(request, data={"delivered": True, "reason": outcome.value})
        case DoubtAnswerDeliveryOutcome.NO_USER | DoubtAnswerDeliveryOutcome.NO_DEVICES:
            return json_success(request, data={"delivered": False, "reason": outcome.value})
        case DoubtAnswerDeliveryOutcome.PUSH_SERVICE_RETRY_LATER:
            return _retry_later_response("Push notification service is temporarily unavailable")
        case DoubtAnswerDeliveryOutcome.ALL_DEVICES_FAILED:
            return _retry_later_response("Push notification delivery failed for every device")
