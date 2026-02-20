from typing import Annotated, Literal

from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _

from pydantic import Json

from zerver.actions.voice_recording import (
    check_send_voice_recording_notification,
    do_send_stream_voice_recording_notification,
)
from zerver.lib.exceptions import JsonableError
from zerver.lib.response import json_success
from zerver.lib.streams import access_stream_by_id_for_message, access_stream_for_send_message
from zerver.lib.topic import (
    maybe_rename_general_chat_to_empty_topic,
    maybe_rename_no_topic_to_empty_topic,
)
from zerver.lib.typed_endpoint import ApiParamConfig, OptionalTopic, typed_endpoint
from zerver.models import UserProfile


@typed_endpoint
def send_voice_recording_backend(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    notification_to: Annotated[Json[list[int] | None], ApiParamConfig("to")] = None,
    operator: Annotated[Literal["start", "stop"], ApiParamConfig("op")],
    req_type: Annotated[Literal["direct", "stream", "channel"], ApiParamConfig("type")] = "direct",
    stream_id: Json[int | None] = None,
    topic: OptionalTopic = None,
) -> HttpResponse:
    recipient_type_name = req_type
    if recipient_type_name == "channel":
        recipient_type_name = "stream"

    if recipient_type_name == "stream":
        if stream_id is None:
            raise JsonableError(_("Missing '{var_name}' argument").format(var_name="stream_id"))
        if topic is None:
            raise JsonableError(_("Missing topic"))
        if not user_profile.send_stream_typing_notifications:
            raise JsonableError(
                _("User has disabled typing notifications for channel messages")
            )
        stream = access_stream_by_id_for_message(user_profile, stream_id)[0]
        access_stream_for_send_message(user_profile, stream, forwarder_user_profile=None)
        topic = maybe_rename_general_chat_to_empty_topic(topic)
        topic = maybe_rename_no_topic_to_empty_topic(topic)
        do_send_stream_voice_recording_notification(user_profile, operator, stream, topic)
    else:
        if notification_to is None:
            raise JsonableError(_("Missing 'to' argument"))
        user_ids = notification_to
        if len(user_ids) == 0:
            raise JsonableError(_("Empty 'to' list"))
        if not user_profile.send_private_typing_notifications:
            raise JsonableError(
                _("User has disabled typing notifications for direct messages")
            )
        check_send_voice_recording_notification(user_profile, user_ids, operator)

    return json_success(request)
