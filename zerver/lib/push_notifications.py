# See https://zulip.readthedocs.io/en/latest/subsystems/notifications.html

import asyncio
import copy
import logging
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from email.headerregistry import Address
from functools import cache
from typing import TYPE_CHECKING, Any, Final, Literal, Optional, TypeAlias, Union, cast

import lxml.html
import orjson
from aioapns.common import NotificationResult, PushType
from django.conf import settings
from django.db import transaction
from django.db.models import F, Q, QuerySet
from django.db.models.functions import Lower
from django.utils.timezone import now as timezone_now
from django.utils.translation import gettext as _
from django.utils.translation import override as override_language
from firebase_admin import App as FCMApp
from firebase_admin import credentials as firebase_credentials
from firebase_admin import exceptions as firebase_exceptions
from firebase_admin import initialize_app as firebase_initialize_app
from firebase_admin import messaging as firebase_messaging
from firebase_admin.messaging import UnregisteredError as FCMUnregisteredError
from nacl.encoding import Base64Encoder
from nacl.public import PublicKey, SealedBox
from pydantic import TypeAdapter
from typing_extensions import TypedDict, override

from analytics.lib.counts import COUNT_STATS, do_increment_logging_stat
from zerver.actions.realm_settings import (
    do_set_push_notifications_enabled_end_timestamp,
    do_set_realm_property,
)
from zerver.lib.avatar import absolute_avatar_url, get_avatar_for_inaccessible_user
from zerver.lib.display_recipient import get_display_recipient
from zerver.lib.emoji_utils import hex_codepoint_to_emoji
from zerver.lib.exceptions import ErrorCode, JsonableError, MissingRemoteRealmError
from zerver.lib.message import access_message_and_usermessage, direct_message_group_users
from zerver.lib.notification_data import get_mentioned_user_group
from zerver.lib.remote_server import (
    PushNotificationBouncerError,
    PushNotificationBouncerRetryLaterError,
    PushNotificationBouncerServerError,
    record_push_notifications_recently_working,
    send_json_to_push_bouncer,
    send_server_data_to_push_bouncer,
    send_to_push_bouncer,
)
from zerver.lib.soft_deactivation import soft_reactivate_if_personal_notification
from zerver.lib.tex import change_katex_to_raw_latex
from zerver.lib.timestamp import datetime_to_timestamp
from zerver.lib.topic import get_topic_display_name
from zerver.lib.url_decoding import is_same_server_message_link
from zerver.lib.users import check_can_access_user
from zerver.models import (
    AbstractPushDeviceToken,
    ArchivedMessage,
    Message,
    PushDevice,
    PushDeviceToken,
    Realm,
    Recipient,
    Stream,
    UserMessage,
    UserProfile,
)
from zerver.models.realms import get_fake_email_domain
from zerver.models.scheduled_jobs import NotificationTriggers
from zerver.models.users import get_user_profile_by_id

if TYPE_CHECKING:
    import aioapns

logger = logging.getLogger(__name__)

if settings.ZILENCER_ENABLED:
    from zilencer.models import RemotePushDevice, RemotePushDeviceToken, RemoteZulipServer

# Time (in seconds) for which the server should retry registering
# a push device to the bouncer. 24 hrs is a good time limit because
# a day is longer than any minor outage.
PUSH_REGISTRATION_LIVENESS_TIMEOUT = 24 * 60 * 60


DeviceToken: TypeAlias = Union[PushDeviceToken, "RemotePushDeviceToken"]


def validate_token(token_str: str, kind: int) -> None:
    if token_str == "" or len(token_str) > 4096:
        raise JsonableError(_("Empty or invalid length token"))
    if kind == PushDeviceToken.APNS:
        try:
            bytes.fromhex(token_str)
        except ValueError:
            raise JsonableError(_("Invalid APNS token"))


def get_message_stream_name_from_database(message: Message) -> str:
    """
    Never use this function outside of the push-notifications
    codepath. Most of our code knows how to get streams
    up front in a more efficient manner.
    """
    stream_id = message.recipient.type_id
    return Stream.objects.get(id=stream_id).name


@dataclass
class UserPushIdentityCompat:
    """Compatibility class for supporting the transition from remote servers
    sending their UserProfile ids to the bouncer to sending UserProfile uuids instead.

    Until we can drop support for receiving user_id, we need this
    class, because a user's identity in the push notification context
    may be represented either by an id or uuid.
    """

    user_id: int | None = None
    user_uuid: str | None = None

    def __post_init__(self) -> None:
        assert self.user_id is not None or self.user_uuid is not None

    def filter_q(self) -> Q:
        """
        This aims to support correctly querying for RemotePushDeviceToken.
        If only one of (user_id, user_uuid) is provided, the situation is trivial,
        If both are provided, we want to query for tokens matching EITHER the
        uuid or the id - because the user may have devices with old registrations,
        so user_id-based, as well as new registration with uuid. Notifications
        naturally should be sent to both.
        """
        if self.user_id is not None and self.user_uuid is None:
            return Q(user_id=self.user_id)
        elif self.user_uuid is not None and self.user_id is None:
            return Q(user_uuid=self.user_uuid)
        else:
            assert self.user_id is not None and self.user_uuid is not None
            return Q(user_uuid=self.user_uuid) | Q(user_id=self.user_id)

    @override
    def __str__(self) -> str:
        result = ""
        if self.user_id is not None:
            result += f"<id:{self.user_id}>"
        if self.user_uuid is not None:
            result += f"<uuid:{self.user_uuid}>"

        return result


#
# Sending to APNs, for iOS
#


@dataclass
class APNsContext:
    apns: "aioapns.APNs"
    loop: asyncio.AbstractEventLoop


def has_apns_credentials() -> bool:
    return settings.APNS_TOKEN_KEY_FILE is not None or settings.APNS_CERT_FILE is not None


@cache
def get_apns_context() -> APNsContext | None:
    # We lazily do this import as part of optimizing Zulip's base
    # import time.
    import aioapns

    if not has_apns_credentials():  # nocoverage
        return None

    # NB if called concurrently, this will make excess connections.
    # That's a little sloppy, but harmless unless a server gets
    # hammered with a ton of these all at once after startup.
    loop = asyncio.new_event_loop()

    # Defining a no-op error-handling function overrides the default
    # behaviour of logging at ERROR level whenever delivery fails; we
    # handle those errors by checking the result in
    # send_apple_push_notification.
    async def err_func(
        request: aioapns.NotificationRequest, result: aioapns.common.NotificationResult
    ) -> None:
        pass  # nocoverage

    async def make_apns() -> aioapns.APNs:
        key: str | None = None
        if settings.APNS_TOKEN_KEY_FILE:  # nocoverage
            with open(settings.APNS_TOKEN_KEY_FILE) as f:
                key = f.read()
        return aioapns.APNs(
            client_cert=settings.APNS_CERT_FILE,
            key=key,
            key_id=settings.APNS_TOKEN_KEY_ID,
            team_id=settings.APNS_TEAM_ID,
            max_connection_attempts=APNS_MAX_RETRIES,
            use_sandbox=settings.APNS_SANDBOX,
            err_func=err_func,
            # The actual APNs topic will vary between notifications,
            # so we set it there, overriding any value we put here.
            # We can't just leave this out, though, because then
            # the constructor attempts to guess.
            topic="invalid.nonsense",
        )

    apns = loop.run_until_complete(make_apns())
    return APNsContext(apns=apns, loop=loop)


APNS_MAX_RETRIES = 3


def dedupe_device_tokens(
    devices: Sequence[DeviceToken],
) -> Sequence[DeviceToken]:
    device_tokens: set[str] = set()
    result: list[DeviceToken] = []
    for device in devices:
        lower_token = device.token.lower()
        if lower_token in device_tokens:  # nocoverage
            continue
        device_tokens.add(lower_token)
        result.append(device)
    return result


@dataclass
class APNsResultInfo:
    successfully_sent: bool
    delete_device_id: int | None = None
    delete_device_token: str | None = None


def get_info_from_apns_result(
    result: NotificationResult | BaseException,
    device: "DeviceToken | RemotePushDevice",
    log_context: str,
) -> APNsResultInfo:
    import aioapns.exceptions

    result_info = APNsResultInfo(successfully_sent=False)

    if isinstance(result, aioapns.exceptions.ConnectionError):
        logger.error("APNs: ConnectionError sending %s; check certificate expiration", log_context)
    elif isinstance(result, BaseException):
        logger.error("APNs: Error sending %s", log_context, exc_info=result)
    elif result.is_successful:
        result_info.successfully_sent = True
        logger.info("APNs: Success sending %s", log_context)
    elif result.description in ["Unregistered", "BadDeviceToken", "DeviceTokenNotForTopic"]:
        logger.info(
            "APNs: Removing invalid/expired token %s (%s)", device.token, result.description
        )
        if settings.ZILENCER_ENABLED and isinstance(device, RemotePushDevice):
            result_info.delete_device_id = device.device_id
        else:
            result_info.delete_device_token = device.token
    else:
        logger.warning("APNs: Failed to send %s: %s", log_context, result.description)

    return result_info


def send_apple_push_notification(
    user_identity: UserPushIdentityCompat,
    devices: Sequence[DeviceToken],
    payload_data: Mapping[str, Any],
    remote: Optional["RemoteZulipServer"] = None,
) -> int:
    if not devices:
        return 0
    # We lazily do the APNS imports as part of optimizing Zulip's base
    # import time; since these are only needed in the push
    # notification queue worker, it's best to only import them in the
    # code that needs them.
    import aioapns

    apns_context = get_apns_context()
    if apns_context is None:
        logger.debug(
            "APNs: Dropping a notification because nothing configured.  "
            "Set ZULIP_SERVICES_URL (or APNS_CERT_FILE)."
        )
        return 0

    if remote:
        assert settings.ZILENCER_ENABLED
        DeviceTokenClass: type[AbstractPushDeviceToken] = RemotePushDeviceToken
    else:
        DeviceTokenClass = PushDeviceToken

    orig_devices = devices
    devices = dedupe_device_tokens(devices)
    num_duplicate_tokens = len(orig_devices) - len(devices)

    if remote:
        logger.info(
            "APNs: Sending notification for remote user %s:%s to %d devices (skipped %d duplicates)",
            remote.uuid,
            user_identity,
            len(devices),
            num_duplicate_tokens,
        )
    else:
        logger.info(
            "APNs: Sending notification for local user %s to %d devices (skipped %d duplicates)",
            user_identity,
            len(devices),
            num_duplicate_tokens,
        )
    payload_data = dict(payload_data)
    message = {**payload_data.pop("custom", {}), "aps": payload_data}

    have_missing_app_id = False
    for device in devices:
        if device.ios_app_id is None:
            # This should be present for all APNs tokens, as an invariant maintained
            # by the views that add the token to our database.
            logger.error(
                "APNs: Missing ios_app_id for user %s device %s", user_identity, device.token
            )
            have_missing_app_id = True
    if have_missing_app_id:
        devices = [device for device in devices if device.ios_app_id is not None]

    results: dict[DeviceToken, NotificationResult | BaseException] = {}
    for device in devices:
        # TODO obviously this should be made to actually use the async
        request = aioapns.NotificationRequest(
            apns_topic=device.ios_app_id,
            device_token=device.token,
            message=message,
            time_to_live=24 * 3600,
        )
        try:
            results[device] = apns_context.loop.run_until_complete(
                apns_context.apns.send_notification(request)
            )
        except BaseException as e:
            results[device] = e

    successfully_sent_count = 0
    for device, result in results.items():
        log_context = f"for user {user_identity} to device {device.token}"
        result_info = get_info_from_apns_result(result, device, log_context)

        if result_info.successfully_sent:
            successfully_sent_count += 1
        elif result_info.delete_device_token is not None:
            # We remove all entries for this token (There
            # could be multiple for different Zulip servers).
            DeviceTokenClass._default_manager.alias(lower_token=Lower("token")).filter(
                lower_token=result_info.delete_device_token.lower(),
                kind=DeviceTokenClass.APNS,
            ).delete()

    return successfully_sent_count


#
# Sending to FCM, for Android
#


# Note: This is a timeout value per retry, not a total timeout.
FCM_REQUEST_TIMEOUT = 5


def make_fcm_app() -> FCMApp:  # nocoverage
    if settings.ANDROID_FCM_CREDENTIALS_PATH is None:
        return None

    fcm_credentials = firebase_credentials.Certificate(settings.ANDROID_FCM_CREDENTIALS_PATH)
    fcm_app = firebase_initialize_app(
        fcm_credentials, options=dict(httpTimeout=FCM_REQUEST_TIMEOUT)
    )

    return fcm_app


if settings.ANDROID_FCM_CREDENTIALS_PATH:  # nocoverage
    fcm_app = make_fcm_app()
else:
    fcm_app = None


def has_fcm_credentials() -> bool:  # nocoverage
    return fcm_app is not None


# This is purely used in testing
def send_android_push_notification_to_user(
    user_profile: UserProfile, data: dict[str, Any], options: dict[str, Any]
) -> None:
    devices = list(PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.FCM))
    send_android_push_notification(
        UserPushIdentityCompat(user_id=user_profile.id), devices, data, options
    )


def parse_fcm_options(options: dict[str, Any], data: dict[str, Any]) -> str:
    """
    Parse FCM options, supplying defaults, and raising an error if invalid.

    The options permitted here form part of the Zulip notification
    bouncer's API.  They are:

    `priority`: Passed through to FCM; see upstream doc linked below.
        Zulip servers should always set this; when unset, we guess a value
        based on the behavior of old server versions.

    `time_to_live`: Optional time in seconds for how long FCM should
        attempt to deliver the message. Valid range: 0 to 2,419,200 seconds (28 days).
        If not specified, FCM uses its default TTL.

    Including unrecognized options is an error.

    For details on options' semantics, see this FCM upstream doc:
      https://firebase.google.com/docs/cloud-messaging/android/message-priority

    Returns `priority`.
    """
    priority = options.pop("priority", None)
    if priority is None:
        # An older server.  Identify if this seems to be an actual notification.
        if data.get("event") == "message":
            priority = "high"
        else:  # `'event': 'remove'`, presumably
            priority = "normal"
    if priority not in ("normal", "high"):
        raise JsonableError(
            _(
                "Invalid GCM option to bouncer: priority {priority!r}",
            ).format(priority=priority)
        )

    # Validate time_to_live if present
    time_to_live = options.pop("time_to_live", None)
    if time_to_live is not None:
        try:
            ttl_value = int(time_to_live)
            # FCM allows TTL from 0 to 2,419,200 seconds (28 days)
            if not (0 <= ttl_value <= 2419200):
                raise JsonableError(
                    _(
                        "Invalid GCM option to bouncer: time_to_live must be between 0 and 2419200 seconds",
                    )
                )
        except (TypeError, ValueError):
            raise JsonableError(
                _(
                    "Invalid GCM option to bouncer: time_to_live must be an integer",
                )
            )

    if options:
        # We're strict about the API; there is no use case for a newer Zulip
        # server talking to an older bouncer, so we only need to provide
        # one-way compatibility.
        raise JsonableError(
            _(
                "Invalid GCM options to bouncer: {options}",
            ).format(options=orjson.dumps(options).decode())
        )

    return priority  # when this grows a second option, can make it a tuple


def _create_fcm_notification_content(data: dict[str, Any], options: dict[str, Any]) -> dict[str, Any] | None:
    """
    Create notification content for FCM messages to support terminated app notifications.
    
    Returns a dict with title, body, channel_id, and tag for the notification block,
    or None if no notification should be shown.
    """
    event_type = data.get("event") or data.get("type")
    
    if event_type == "call":
        # Call notifications - use calls-1 channel (MAX importance)
        call_type = data.get("call_type", "call")
        sender_name = data.get("sender_full_name", "Someone")
        
        return {
            "title": f"Incoming {call_type} call",
            "body": f"From {sender_name}",
            "channel_id": "calls-1",
            "tag": f"call:{data.get('call_id', 'unknown')}"
        }
    
    elif event_type == "call_response":
        # Call response notifications - use calls-1 channel (MAX importance)
        response = data.get("response", "responded")
        receiver_name = data.get("receiver_name", "Someone")
        
        response_text = "accepted" if response == "accept" else "declined"
        
        return {
            "title": f"Call {response_text}",
            "body": f"{receiver_name} {response_text} your call",
            "channel_id": "calls-1",
            "tag": f"call_response:{data.get('call_id', 'unknown')}"
        }
    
    elif event_type == "message":
        # Message notifications - use messages-4 channel (HIGH importance)
        sender_name = data.get("sender_full_name", "Someone")
        content = data.get("content", "")
        
        # Truncate content for notification
        if len(content) > 100:
            content = content[:97] + "..."
        
        return {
            "title": sender_name,
            "body": content,
            "channel_id": "messages-4"
        }
    
    elif event_type == "remove":
        # Remove notifications don't need to show in terminated state
        return None
    
    else:
        # Default notification for other event types
        return {
            "title": "Zulip",
            "body": "New notification",
            "channel_id": "messages-4"
        }

def create_fcm_call_notification_message(
    token: str,
    call_data: dict[str, Any],
    realm_host: str,
    realm_url: str,
) -> firebase_messaging.Message:
    """
    Create FCM call notification message in the exact format specified.

    Args:
        token: FCM device token
        call_data: Call information dictionary
        realm_host: Realm hostname
        realm_url: Full realm URL

    Returns:
        Firebase messaging Message object with call notification format
    """
    # Extract call information
    call_id = call_data.get("call_id", "unknown")
    sender_id = str(call_data.get("sender_id", ""))
    sender_name = call_data.get("sender_full_name", "Someone")
    call_type = call_data.get("call_type", "voice")
    user_id = str(call_data.get("user_id", ""))
    timestamp = str(call_data.get("time", int(timezone_now().timestamp())))

    # Create data payload exactly as specified
    data_payload = {
        "event": "call",
        "server": realm_host,
        "realm_url": realm_url,
        "user_id": user_id,
        "call_id": call_id,
        "sender_id": sender_id,
        "sender_full_name": sender_name,
        "call_type": call_type,
        "time": timestamp
    }

    # Convert all values to strings as required by FCM
    data_payload = {k: str(v) for k, v in data_payload.items()}

    # Create Android notification configuration exactly as specified
    android_notification = firebase_messaging.AndroidNotification(
        channel_id="calls-1",
        tag=f"call:{call_id}",
        title=f"Incoming {call_type} call",
        body=f"From {sender_name}",
        sound="default",
        click_action="android.intent.action.VIEW"
    )

    # Create Android config with high priority
    android_config = firebase_messaging.AndroidConfig(
        priority="high",
        notification=android_notification
    )

    # Create cross-platform notification
    notification = firebase_messaging.Notification(
        title=f"Incoming {call_type} call",
        body=f"From {sender_name}"
    )

    # Create the complete FCM message
    return firebase_messaging.Message(
        token=token,
        data=data_payload,
        android=android_config,
        notification=notification
    )


def send_fcm_call_notifications(
    devices: Sequence[DeviceToken],
    call_data: dict[str, Any],
    realm_host: str,
    realm_url: str,
    remote: Optional["RemoteZulipServer"] = None,
) -> int:
    """
    Send FCM call notifications using the specialized call notification format.

    Args:
        devices: List of device tokens to send to
        call_data: Call information dictionary
        realm_host: Realm hostname
        realm_url: Full realm URL
        remote: Optional remote server for bouncer

    Returns:
        Number of successfully sent notifications
    """
    if not devices or not fcm_app:
        return 0

    # Create call notification messages for each device
    messages = []
    token_list = []

    for device in devices:
        try:
            message = create_fcm_call_notification_message(
                token=device.token,
                call_data=call_data,
                realm_host=realm_host,
                realm_url=realm_url
            )
            messages.append(message)
            token_list.append(device.token)
        except Exception as e:
            logger.warning(f"Failed to create call notification for device {device.token}: {e}")
            continue

    if not messages:
        return 0

    # Send batch of call notifications
    try:
        batch_response = firebase_messaging.send_each(messages, app=fcm_app)
    except firebase_exceptions.FirebaseError:
        logger.warning("Error while sending FCM call notifications", exc_info=True)
        return 0

    # Process responses and handle token management
    if remote:
        assert settings.ZILENCER_ENABLED
        DeviceTokenClass: type[AbstractPushDeviceToken] = RemotePushDeviceToken
    else:
        DeviceTokenClass = PushDeviceToken

    successfully_sent_count = 0
    for idx, response in enumerate(batch_response.responses):
        token = token_list[idx]

        if response.success:
            successfully_sent_count += 1
            logger.info(f"FCM Call: Sent notification with ID {response.message_id} to {token}")
        else:
            error = response.exception
            logger.warning(f"FCM Call: Failed to send to {token}: {error}")

            # Handle token cleanup for unregistered devices
            if isinstance(error, FCMUnregisteredError):
                logger.info(f"FCM Call: Removing unregistered token {token}")
                if remote:
                    device = DeviceTokenClass.objects.filter(
                        user_id=remote.uuid, user_uuid=call_data.get("user_id"), token=token
                    ).first()
                else:
                    device = DeviceTokenClass.objects.filter(
                        user_id=call_data.get("user_id"), token=token
                    ).first()

                if device:
                    device.delete()

    logger.info(f"FCM Call: Successfully sent {successfully_sent_count}/{len(messages)} call notifications")
    return successfully_sent_count


def send_android_push_notification(
    user_identity: UserPushIdentityCompat,
    devices: Sequence[DeviceToken],
    data: dict[str, Any],
    options: dict[str, Any],
    remote: Optional["RemoteZulipServer"] = None,
) -> int:
    """
    Send a FCM message to the given devices.

    See https://firebase.google.com/docs/cloud-messaging/http-server-ref
    for the FCM upstream API which this talks to.

    data: The JSON object (decoded) to send as the 'data' parameter of
        the FCM message.
    options: Additional options to control the FCM message sent.
        For details, see `parse_fcm_options`.
    """
    if not devices:
        return 0
    if not fcm_app:
        logger.debug(
            "Skipping sending a FCM push notification since "
            "ZULIP_SERVICE_PUSH_NOTIFICATIONS and ANDROID_FCM_CREDENTIALS_PATH are both unset"
        )
        return 0

    if remote:
        logger.info(
            "FCM: Sending notification for remote user %s:%s to %d devices",
            remote.uuid,
            user_identity,
            len(devices),
        )
    else:
        logger.info(
            "FCM: Sending notification for local user %s to %d devices", user_identity, len(devices)
        )

    token_list = [device.token for device in devices]
    # Parse options and extract both priority and time_to_live
    original_options = options.copy()  # Keep a copy since parse_fcm_options modifies the dict
    priority = parse_fcm_options(options, data)
    time_to_live = original_options.get("time_to_live")

    # The API requires all values to be strings. Our data dict is going to have
    # things like an integer realm and user ids etc., so just convert everything
    # like that.
    data = {k: str(v) if not isinstance(v, str) else v for k, v in data.items()}
    
    # Create FCM messages with both data and notification blocks for terminated app support
    messages = []
    for token in token_list:
        # Determine notification content based on data type
        notification_content = _create_fcm_notification_content(data, options)
        
        # Create Android-specific notification configuration
        android_notification = None
        if notification_content:
            android_notification = firebase_messaging.AndroidNotification(
                title=notification_content.get("title"),
                body=notification_content.get("body"),
                channel_id=notification_content.get("channel_id", "messages-4"),
                sound="default",
                tag=notification_content.get("tag"),
                click_action="android.intent.action.VIEW"
            )
        
        # Create Android config with notification and TTL
        android_config_kwargs = {
            "priority": priority,
            "notification": android_notification
        }
        if time_to_live is not None:
            android_config_kwargs["ttl"] = f"{time_to_live}s"  # FCM expects TTL as string with "s" suffix

        android_config = firebase_messaging.AndroidConfig(**android_config_kwargs)
        
        # Create the message with both data and notification
        message_kwargs = {
            "data": data,
            "token": token,
            "android": android_config
        }
        
        # Add notification block for cross-platform compatibility
        if notification_content:
            message_kwargs["notification"] = firebase_messaging.Notification(
                title=notification_content.get("title"),
                body=notification_content.get("body")
            )
        
        messages.append(firebase_messaging.Message(**message_kwargs))

    try:
        batch_response = firebase_messaging.send_each(messages, app=fcm_app)
    except firebase_exceptions.FirebaseError:
        logger.warning("Error while pushing to FCM", exc_info=True)
        return 0

    if remote:
        assert settings.ZILENCER_ENABLED
        DeviceTokenClass: type[AbstractPushDeviceToken] = RemotePushDeviceToken
    else:
        DeviceTokenClass = PushDeviceToken

    successfully_sent_count = 0
    for idx, response in enumerate(batch_response.responses):
        # We enumerate to have idx to track which token the response
        # corresponds to. send_each() preserves the order of the messages,
        # so this works.

        token = token_list[idx]
        if response.success:
            successfully_sent_count += 1
            logger.info("FCM: Sent message with ID: %s to %s", response.message_id, token)
        else:
            error = response.exception
            if isinstance(error, FCMUnregisteredError):
                logger.info("FCM: Removing %s due to %s", token, error.code)

                # We remove all entries for this token (There
                # could be multiple for different Zulip servers).
                DeviceTokenClass._default_manager.filter(
                    token=token, kind=DeviceTokenClass.FCM
                ).delete()
            else:
                logger.warning("FCM: Delivery failed for %s: %s:%s", token, error.__class__, error)

    return successfully_sent_count


#
# Sending to a bouncer
#


def uses_notification_bouncer() -> bool:
    return settings.ZULIP_SERVICE_PUSH_NOTIFICATIONS is True


def sends_notifications_directly() -> bool:
    return has_apns_credentials() and has_fcm_credentials() and not uses_notification_bouncer()


def send_notifications_to_bouncer(
    user_profile: UserProfile,
    apns_payload: dict[str, Any],
    gcm_payload: dict[str, Any],
    gcm_options: dict[str, Any],
    android_devices: Sequence[DeviceToken],
    apple_devices: Sequence[DeviceToken],
) -> None:
    assert len(android_devices) + len(apple_devices) != 0

    post_data = {
        "user_uuid": str(user_profile.uuid),
        # user_uuid is the intended future format, but we also need to send user_id
        # to avoid breaking old mobile registrations, which were made with user_id.
        "user_id": user_profile.id,
        "realm_uuid": str(user_profile.realm.uuid),
        "apns_payload": apns_payload,
        "gcm_payload": gcm_payload,
        "gcm_options": gcm_options,
        "android_devices": [device.token for device in android_devices],
        "apple_devices": [device.token for device in apple_devices],
    }
    # Calls zilencer.views.remote_server_notify_push

    try:
        response_data = send_json_to_push_bouncer("POST", "push/notify", post_data)
    except PushNotificationsDisallowedByBouncerError as e:
        logger.warning("Bouncer refused to send push notification: %s", e.reason)
        do_set_realm_property(
            user_profile.realm,
            "push_notifications_enabled",
            False,
            acting_user=None,
        )
        do_set_push_notifications_enabled_end_timestamp(user_profile.realm, None, acting_user=None)
        return

    assert isinstance(response_data["total_android_devices"], int)
    assert isinstance(response_data["total_apple_devices"], int)

    assert isinstance(response_data["deleted_devices"], dict)
    assert isinstance(response_data["deleted_devices"]["android_devices"], list)
    assert isinstance(response_data["deleted_devices"]["apple_devices"], list)
    android_deleted_devices = response_data["deleted_devices"]["android_devices"]
    apple_deleted_devices = response_data["deleted_devices"]["apple_devices"]
    if android_deleted_devices or apple_deleted_devices:
        logger.info(
            "Deleting push tokens based on response from bouncer: Android: %s, Apple: %s",
            sorted(android_deleted_devices),
            sorted(apple_deleted_devices),
        )
        PushDeviceToken.objects.filter(
            kind=PushDeviceToken.FCM, token__in=android_deleted_devices
        ).delete()
        PushDeviceToken.objects.alias(lower_token=Lower("token")).filter(
            kind=PushDeviceToken.APNS,
            lower_token__in=[token.lower() for token in apple_deleted_devices],
        ).delete()

    total_android_devices, total_apple_devices = (
        response_data["total_android_devices"],
        response_data["total_apple_devices"],
    )
    do_increment_logging_stat(
        user_profile.realm,
        COUNT_STATS["mobile_pushes_sent::day"],
        None,
        timezone_now(),
        increment=total_android_devices + total_apple_devices,
    )

    remote_realm_dict = response_data.get("realm")
    if remote_realm_dict is not None:
        # The server may have updated our understanding of whether
        # push notifications will work.
        assert isinstance(remote_realm_dict, dict)
        can_push = remote_realm_dict["can_push"]
        do_set_realm_property(
            user_profile.realm,
            "push_notifications_enabled",
            can_push,
            acting_user=None,
        )
        do_set_push_notifications_enabled_end_timestamp(
            user_profile.realm, remote_realm_dict["expected_end_timestamp"], acting_user=None
        )
        if can_push:
            record_push_notifications_recently_working()

    logger.info(
        "Sent mobile push notifications for user %s through bouncer: %s via FCM devices, %s via APNs devices",
        user_profile.id,
        total_android_devices,
        total_apple_devices,
    )


#
# Managing device tokens
#


def add_push_device_token(
    user_profile: UserProfile, token_str: str, kind: int, ios_app_id: str | None = None
) -> None:
    logger.info(
        "Registering push device: %d %r %d %r", user_profile.id, token_str, kind, ios_app_id
    )

    # Regardless of whether we're using the push notifications
    # bouncer, we want to store a PushDeviceToken record locally.
    # These can be used to discern whether the user has any mobile
    # devices configured, and is also where we will store encryption
    # keys for mobile push notifications.
    PushDeviceToken.objects.bulk_create(
        [
            PushDeviceToken(
                user_id=user_profile.id,
                token=token_str,
                kind=kind,
                ios_app_id=ios_app_id,
                # last_updated is to be renamed to date_created.
                last_updated=timezone_now(),
            ),
        ],
        ignore_conflicts=True,
    )

    if not uses_notification_bouncer():
        return

    # If we're sending things to the push notification bouncer
    # register this user with them here
    post_data = {
        "server_uuid": settings.ZULIP_ORG_ID,
        "user_uuid": str(user_profile.uuid),
        "realm_uuid": str(user_profile.realm.uuid),
        # user_id is sent so that the bouncer can delete any pre-existing registrations
        # for this user+device to avoid duplication upon adding the uuid registration.
        "user_id": str(user_profile.id),
        "token": token_str,
        "token_kind": kind,
    }

    if kind == PushDeviceToken.APNS:
        post_data["ios_app_id"] = ios_app_id

    logger.info("Sending new push device to bouncer: %r", post_data)
    # Calls zilencer.views.register_remote_push_device
    send_to_push_bouncer("POST", "push/register", post_data)


def remove_push_device_token(user_profile: UserProfile, token_str: str, kind: int) -> None:
    try:
        if kind == PushDeviceToken.APNS:
            token_str = token_str.lower()
            token: PushDeviceToken = PushDeviceToken.objects.alias(lower_token=Lower("token")).get(
                lower_token=token_str, kind=kind, user=user_profile
            )
        else:
            token = PushDeviceToken.objects.get(token=token_str, kind=kind, user=user_profile)
        token.delete()
    except PushDeviceToken.DoesNotExist:
        # If we are using bouncer, don't raise the exception. It will
        # be raised by the code below eventually. This is important
        # during the transition period after upgrading to a version
        # that stores local PushDeviceToken objects even when using
        # the push notifications bouncer.
        if not uses_notification_bouncer():
            raise JsonableError(_("Token does not exist"))

    # If we're sending things to the push notification bouncer
    # unregister this user with them here
    if uses_notification_bouncer():
        # TODO: Make this a remove item
        post_data = {
            "server_uuid": settings.ZULIP_ORG_ID,
            "realm_uuid": str(user_profile.realm.uuid),
            # We don't know here if the token was registered with uuid
            # or using the legacy id format, so we need to send both.
            "user_uuid": str(user_profile.uuid),
            "user_id": user_profile.id,
            "token": token_str,
            "token_kind": kind,
        }
        # Calls zilencer.views.unregister_remote_push_device
        send_to_push_bouncer("POST", "push/unregister", post_data)


def clear_push_device_tokens(user_profile_id: int) -> None:
    # Deletes all of a user's PushDeviceTokens.
    if uses_notification_bouncer():
        user_profile = get_user_profile_by_id(user_profile_id)
        user_uuid = str(user_profile.uuid)
        post_data = {
            "server_uuid": settings.ZULIP_ORG_ID,
            "realm_uuid": str(user_profile.realm.uuid),
            # We want to clear all registered token, and they may have
            # been registered with either uuid or id.
            "user_uuid": user_uuid,
            "user_id": user_profile_id,
        }
        send_to_push_bouncer("POST", "push/unregister/all", post_data)
        return

    PushDeviceToken.objects.filter(user_id=user_profile_id).delete()


#
# Push notifications in general
#


def push_notifications_configured() -> bool:
    """True just if this server has configured a way to send push notifications."""
    if (
        uses_notification_bouncer()
        and settings.ZULIP_ORG_KEY is not None
        and settings.ZULIP_ORG_ID is not None
    ):  # nocoverage
        # We have the needed configuration to send push notifications through
        # the bouncer.  Better yet would be to confirm that this config actually
        # works -- e.g., that we have ever successfully sent to the bouncer --
        # but this is a good start.
        return True
    if settings.DEVELOPMENT and (has_apns_credentials() or has_fcm_credentials()):  # nocoverage
        # Since much of the notifications logic is platform-specific, the mobile
        # developers often work on just one platform at a time, so we should
        # only require one to be configured.
        return True
    elif has_apns_credentials() and has_fcm_credentials():  # nocoverage
        # We have the needed configuration to send through APNs and FCM directly
        # (i.e., we are the bouncer, presumably.)  Again, assume it actually works.
        return True
    return False


def initialize_push_notifications() -> None:
    """Called during startup of the push notifications worker to check
    whether we expect mobile push notifications to work on this server
    and update state accordingly.
    """

    if sends_notifications_directly():
        # This server sends push notifications directly. Make sure we
        # are set to report to clients that push notifications are
        # enabled.
        for realm in Realm.objects.filter(push_notifications_enabled=False):
            do_set_realm_property(realm, "push_notifications_enabled", True, acting_user=None)
            do_set_push_notifications_enabled_end_timestamp(realm, None, acting_user=None)
        return

    if not push_notifications_configured():
        for realm in Realm.objects.filter(push_notifications_enabled=True):
            do_set_realm_property(realm, "push_notifications_enabled", False, acting_user=None)
            do_set_push_notifications_enabled_end_timestamp(realm, None, acting_user=None)
        if settings.DEVELOPMENT and not settings.TEST_SUITE:
            # Avoid unnecessary spam on development environment startup
            return  # nocoverage
        logger.warning(
            "Mobile push notifications are not configured.\n  "
            "See https://zulip.readthedocs.io/en/latest/"
            "production/mobile-push-notifications.html"
        )
        return

    if uses_notification_bouncer():
        # If we're using the notification bouncer, check if we can
        # actually send push notifications, and update our
        # understanding of that state for each realm accordingly.
        send_server_data_to_push_bouncer(consider_usage_statistics=False)
        return

    logger.warning(  # nocoverage
        "Mobile push notifications are not fully configured.\n  "
        "See https://zulip.readthedocs.io/en/latest/production/mobile-push-notifications.html"
    )
    for realm in Realm.objects.filter(push_notifications_enabled=True):  # nocoverage
        do_set_realm_property(realm, "push_notifications_enabled", False, acting_user=None)
        do_set_push_notifications_enabled_end_timestamp(realm, None, acting_user=None)


def get_mobile_push_content(rendered_content: str) -> str:
    def get_text(elem: lxml.html.HtmlElement) -> str:
        # Convert default emojis to their Unicode equivalent.
        classes = elem.get("class", "")
        if "emoji" in classes:
            match = re.search(r"emoji-(?P<emoji_code>\S+)", classes)
            if match:
                emoji_code = match.group("emoji_code")
                return hex_codepoint_to_emoji(emoji_code)
        # Handles realm emojis, avatars etc.
        if elem.tag == "img":
            return elem.get("alt", "")
        if elem.tag == "blockquote":
            return ""  # To avoid empty line before quote text
        return elem.text or ""

    def format_as_quote(quote_text: str) -> str:
        return "".join(
            f"> {line}\n"
            for line in quote_text.splitlines()
            if line  # Remove empty lines
        )

    def render_olist(ol: lxml.html.HtmlElement) -> str:
        items = []
        counter = int(ol.get("start")) if ol.get("start") else 1
        nested_levels = sum(1 for ancestor in ol.iterancestors("ol"))
        indent = ("\n" + "  " * nested_levels) if nested_levels else ""

        for li in ol:
            items.append(indent + str(counter) + ". " + process(li).strip())
            counter += 1

        return "\n".join(items)

    def render_spoiler(elem: lxml.html.HtmlElement) -> str:
        header = elem.find_class("spoiler-header")[0]
        text = process(header).strip()
        if len(text) == 0:
            return "(…)\n"
        return f"{text} (…)\n"

    def process(elem: lxml.html.HtmlElement) -> str:
        plain_text = ""
        if elem.tag == "ol":
            plain_text = render_olist(elem)
        elif "spoiler-block" in elem.get("class", ""):
            plain_text += render_spoiler(elem)
        else:
            plain_text = get_text(elem)
            sub_text = ""
            for child in elem:
                sub_text += process(child)
            if elem.tag == "blockquote":
                sub_text = format_as_quote(sub_text)
            plain_text += sub_text
            plain_text += elem.tail or ""
        return plain_text

    def is_user_said_paragraph(element: lxml.html.HtmlElement) -> bool:
        # The user said paragraph has these exact elements:
        # 1. A user mention
        # 2. A same server message link ("said")
        # 3. A colon (:)
        user_mention_elements = element.find_class("user-mention")
        if len(user_mention_elements) != 1:
            return False

        message_link_elements = []
        anchor_elements = element.cssselect("a[href]")
        for elem in anchor_elements:
            href = elem.get("href")
            if is_same_server_message_link(href):
                message_link_elements.append(elem)

        if len(message_link_elements) != 1:
            return False

        remaining_text = (
            element.text_content()
            .replace(user_mention_elements[0].text_content(), "")
            .replace(message_link_elements[0].text_content(), "")
        )
        return remaining_text.strip() == ":"

    def get_collapsible_status_array(elements: list[lxml.html.HtmlElement]) -> list[bool]:
        collapsible_status: list[bool] = [
            element.tag == "blockquote" or is_user_said_paragraph(element) for element in elements
        ]
        return collapsible_status

    def potentially_collapse_quotes(element: lxml.html.HtmlElement) -> None:
        children = element.getchildren()
        collapsible_status = get_collapsible_status_array(children)

        if all(collapsible_status) or all(not x for x in collapsible_status):
            return

        collapse_element = lxml.html.Element("p")
        collapse_element.text = "[…]"
        for index, child in enumerate(children):
            if collapsible_status[index]:
                if index > 0 and collapsible_status[index - 1]:
                    child.drop_tree()
                else:
                    child.getparent().replace(child, collapse_element)

    elem = lxml.html.fragment_fromstring(rendered_content, create_parent=True)
    change_katex_to_raw_latex(elem)
    potentially_collapse_quotes(elem)
    plain_text = process(elem)
    return plain_text


def truncate_content(content: str) -> tuple[str, bool]:
    # We use Unicode character 'HORIZONTAL ELLIPSIS' (U+2026) instead
    # of three dots as this saves two extra characters for textual
    # content. This function will need to be updated to handle Unicode
    # combining characters and tags when we start supporting themself.
    if len(content) <= 200:
        return content, False
    return content[:200] + "…", True


def get_base_payload(user_profile: UserProfile, for_legacy_clients: bool = True) -> dict[str, Any]:
    """Common fields for all notification payloads."""
    data: dict[str, Any] = {}

    # These will let the app support logging into multiple realms and servers.
    if for_legacy_clients:
        data["server"] = settings.EXTERNAL_HOST
        data["realm_id"] = user_profile.realm.id
        data["realm_uri"] = user_profile.realm.url
    data["realm_url"] = user_profile.realm.url
    data["realm_name"] = user_profile.realm.name
    data["user_id"] = user_profile.id

    return data


def remove_obsolete_fields_apns(payload: dict[str, Any]) -> None:
    # These fields are not used by iOS clients. The legacy
    # app requires these in FCM messages, even though we don't
    # end up doing anything with them.
    payload.pop("server")
    payload.pop("realm_id")


def get_message_payload(
    user_profile: UserProfile,
    message: Message,
    mentioned_user_group_id: int | None = None,
    mentioned_user_group_name: str | None = None,
    can_access_sender: bool = True,
    for_legacy_clients: bool = True,
) -> dict[str, Any]:
    """Common fields for `message` payloads, for all platforms."""
    data = get_base_payload(user_profile, for_legacy_clients)

    # `sender_id` is preferred, but some existing versions use `sender_email`.
    data["sender_id"] = message.sender.id
    if for_legacy_clients:
        if not can_access_sender:
            # A guest user can only receive a stream message from an
            # inaccessible user as we allow unsubscribed users to send
            # messages to streams. For direct messages, the guest gains
            # access to the user if they where previously inaccessible.
            data["sender_email"] = Address(
                username=f"user{message.sender.id}",
                domain=get_fake_email_domain(message.realm.host),
            ).addr_spec
        else:
            data["sender_email"] = message.sender.email

    if mentioned_user_group_id is not None:
        assert mentioned_user_group_name is not None
        data["mentioned_user_group_id"] = mentioned_user_group_id
        data["mentioned_user_group_name"] = mentioned_user_group_name

    if message.recipient.type == Recipient.STREAM:
        channel_id = message.recipient.type_id
        channel_name = get_message_stream_name_from_database(message)

        if for_legacy_clients:
            data["recipient_type"] = "stream"
            data["stream"] = channel_name
            data["stream_id"] = channel_id
        else:
            data["recipient_type"] = "channel"
            data["channel_name"] = channel_name
            data["channel_id"] = channel_id

        data["topic"] = get_topic_display_name(message.topic_name(), user_profile.default_language)
    elif message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        data["recipient_type"] = "private" if for_legacy_clients else "direct"
        # For group DMs, we need to fetch the users for the pm_users field.
        # Note that this doesn't do a separate database query, because both
        # functions use the get_display_recipient_by_id cache.
        recipients = get_display_recipient(message.recipient)
        if len(recipients) > 2:
            data["pm_users"] = direct_message_group_users(message.recipient.id)
    else:  # Recipient.PERSONAL
        data["recipient_type"] = "private" if for_legacy_clients else "direct"

    return data


def get_apns_alert_title(message: Message, language: str) -> str:
    """
    On an iOS notification, this is the first bolded line.
    """
    if message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        recipients = get_display_recipient(message.recipient)
        assert isinstance(recipients, list)
        if len(recipients) > 2:
            return ", ".join(sorted(r["full_name"] for r in recipients))
    elif message.is_channel_message:
        stream_name = get_message_stream_name_from_database(message)
        topic_display_name = get_topic_display_name(message.topic_name(), language)
        return f"#{stream_name} > {topic_display_name}"
    # For 1:1 direct messages, we just show the sender name.
    return message.sender.full_name


def get_apns_alert_subtitle(
    message: Message,
    trigger: str,
    user_profile: UserProfile,
    mentioned_user_group_name: str | None = None,
    can_access_sender: bool = True,
) -> str:
    """
    On an iOS notification, this is the second bolded line.
    """
    sender_name = message.sender.full_name
    if not can_access_sender:
        # A guest user can only receive a stream message from an
        # inaccessible user as we allow unsubscribed users to send
        # messages to streams. For direct messages, the guest gains
        # access to the user if they where previously inaccessible.
        sender_name = str(UserProfile.INACCESSIBLE_USER_NAME)

    if trigger == NotificationTriggers.MENTION:
        if mentioned_user_group_name is not None:
            return _("{full_name} mentioned @{user_group_name}:").format(
                full_name=sender_name, user_group_name=mentioned_user_group_name
            )
        else:
            return _("{full_name} mentioned you:").format(full_name=sender_name)
    elif trigger in (
        NotificationTriggers.TOPIC_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
        NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC,
        NotificationTriggers.TOPIC_WILDCARD_MENTION,
        NotificationTriggers.STREAM_WILDCARD_MENTION,
    ):
        return _("{full_name} mentioned everyone:").format(full_name=sender_name)
    elif message.recipient.type == Recipient.PERSONAL:
        return ""
    elif message.recipient.type == Recipient.DIRECT_MESSAGE_GROUP:
        recipients = get_display_recipient(message.recipient)
        if len(recipients) <= 2:
            return ""
    # For group direct messages, or regular messages to a stream,
    # just use a colon to indicate this is the sender.
    return sender_name + ":"


def get_apns_badge_count(
    user_profile: UserProfile, read_messages_ids: Sequence[int] | None = []
) -> int:
    # NOTE: We have temporarily set get_apns_badge_count to always
    # return 0 until we can debug a likely mobile app side issue with
    # handling notifications while the app is open.
    return 0


def get_apns_badge_count_future(
    user_profile: UserProfile, read_messages_ids: Sequence[int] | None = []
) -> int:
    # Future implementation of get_apns_badge_count; unused but
    # we expect to use this once we resolve client-side bugs.
    return (
        UserMessage.objects.filter(user_profile=user_profile)
        .extra(where=[UserMessage.where_active_push_notification()])  # noqa: S610
        .exclude(
            # If we've just marked some messages as read, they're still
            # marked as having active notifications; we'll clear that flag
            # only after we've sent that update to the devices.  So we need
            # to exclude them explicitly from the count.
            message_id__in=read_messages_ids
        )
        .count()
    )


def get_message_payload_apns(
    user_profile: UserProfile,
    message: Message,
    trigger: str,
    mentioned_user_group_id: int | None = None,
    mentioned_user_group_name: str | None = None,
    can_access_sender: bool = True,
) -> dict[str, Any]:
    """A `message` payload for iOS, via APNs."""
    zulip_data = get_message_payload(
        user_profile, message, mentioned_user_group_id, mentioned_user_group_name, can_access_sender
    )
    zulip_data.update(
        message_ids=[message.id],
    )
    remove_obsolete_fields_apns(zulip_data)

    assert message.rendered_content is not None
    with override_language(user_profile.default_language):
        content, _ = truncate_content(get_mobile_push_content(message.rendered_content))
        apns_data = {
            "alert": {
                "title": get_apns_alert_title(message, user_profile.default_language),
                "subtitle": get_apns_alert_subtitle(
                    message, trigger, user_profile, mentioned_user_group_name, can_access_sender
                ),
                "body": content,
            },
            "sound": "default",
            "badge": get_apns_badge_count(user_profile),
            "custom": {"zulip": zulip_data},
        }
    return apns_data


def get_message_payload_gcm(
    user_profile: UserProfile,
    message: Message,
    mentioned_user_group_id: int | None = None,
    mentioned_user_group_name: str | None = None,
    can_access_sender: bool = True,
    for_legacy_clients: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """A `message` payload + options, for Android via FCM."""
    data = get_message_payload(
        user_profile,
        message,
        mentioned_user_group_id,
        mentioned_user_group_name,
        can_access_sender,
        for_legacy_clients,
    )

    if not can_access_sender:
        # A guest user can only receive a stream message from an
        # inaccessible user as we allow unsubscribed users to send
        # messages to streams. For direct messages, the guest gains
        # access to the user if they where previously inaccessible.
        sender_avatar_url = get_avatar_for_inaccessible_user()
        sender_name = str(UserProfile.INACCESSIBLE_USER_NAME)
    else:
        sender_avatar_url = absolute_avatar_url(message.sender)
        sender_name = message.sender.full_name

    if for_legacy_clients:
        data["event"] = "message"
        data["zulip_message_id"] = message.id  # message_id is reserved for CCS
    else:
        data["type"] = "message"
        data["message_id"] = message.id

    assert message.rendered_content is not None
    with override_language(user_profile.default_language):
        content, unused = truncate_content(get_mobile_push_content(message.rendered_content))
        data.update(
            time=datetime_to_timestamp(message.date_sent),
            content=content,
            sender_full_name=sender_name,
            sender_avatar_url=sender_avatar_url,
            # Add additional fields for terminated app FCM support
            server=user_profile.realm.host,
            user_id=str(user_profile.id),
            realm_url=user_profile.realm.url,
        )
    gcm_options = {"priority": "high"}
    return data, gcm_options


def get_payload_data_to_encrypt(
    user_profile: UserProfile,
    message: Message,
    mentioned_user_group_id: int | None = None,
    mentioned_user_group_name: str | None = None,
    can_access_sender: bool = True,
) -> dict[str, Any]:
    payload_data_to_encrypt, unused = get_message_payload_gcm(
        user_profile,
        message,
        mentioned_user_group_id,
        mentioned_user_group_name,
        can_access_sender,
        for_legacy_clients=False,
    )
    return payload_data_to_encrypt


def get_remove_payload_gcm(
    user_profile: UserProfile,
    message_ids: list[int],
    for_legacy_clients: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """A `remove` payload + options, for Android via FCM."""
    gcm_payload = get_base_payload(user_profile, for_legacy_clients)

    if for_legacy_clients:
        gcm_payload["event"] = "remove"
        gcm_payload["zulip_message_ids"] = ",".join(str(id) for id in message_ids)
    else:
        gcm_payload["type"] = "remove"
        gcm_payload["message_ids"] = message_ids

    gcm_options = {"priority": "normal"}
    return gcm_payload, gcm_options


def get_remove_payload_apns(user_profile: UserProfile, message_ids: list[int]) -> dict[str, Any]:
    zulip_data = get_base_payload(user_profile)
    zulip_data.update(
        event="remove",
        zulip_message_ids=",".join(str(id) for id in message_ids),
    )
    remove_obsolete_fields_apns(zulip_data)
    apns_data = {
        "badge": get_apns_badge_count(user_profile, message_ids),
        "custom": {"zulip": zulip_data},
    }
    return apns_data


def get_remove_payload_data_to_encrypt(
    user_profile: UserProfile,
    message_ids: list[int],
) -> dict[str, Any]:
    payload_data_to_encrypt, unused = get_remove_payload_gcm(
        user_profile, message_ids, for_legacy_clients=False
    )
    return payload_data_to_encrypt


def handle_remove_push_notification(user_profile_id: int, message_ids: list[int]) -> None:
    """This should be called when a message that previously had a
    mobile push notification executed is read.  This triggers a push to the
    mobile app, when the message is read on the server, to remove the
    message from the notification.
    """
    if not push_notifications_configured():
        return

    user_profile = get_user_profile_by_id(user_profile_id)

    # We may no longer have access to the message here; for example,
    # the user (1) got a message, (2) read the message in the web UI,
    # and then (3) it was deleted.  When trying to send the push
    # notification for (2), after (3) has happened, there is no
    # message to fetch -- but we nonetheless want to remove the mobile
    # notification.  Because of this, verification of access to
    # the messages is skipped here.
    # Because of this, no access to the Message objects should be
    # done; they are treated as a list of opaque ints.

    # APNs has a 4KB limit on the maximum size of messages, which
    # translated to several hundred message IDs in one of these
    # notifications. In rare cases, it's possible for someone to mark
    # thousands of push notification eligible messages as read at
    # once. We could handle this situation with a loop, but we choose
    # to truncate instead to avoid extra network traffic, because it's
    # very likely the user has manually cleared the notifications in
    # their mobile device's UI anyway.
    #
    # When truncating, we keep only the newest N messages in this
    # remove event. This is optimal because older messages are the
    # ones most likely to have already been manually cleared at some
    # point in the past.
    #
    # We choose 200 here because a 10-digit message ID plus a comma and
    # space consume 12 bytes, and 12 x 200 = 2400 bytes is still well
    # below the 4KB limit (leaving plenty of space for metadata).
    MAX_APNS_MESSAGE_IDS = 200
    truncated_message_ids = sorted(message_ids)[-MAX_APNS_MESSAGE_IDS:]
    gcm_payload, gcm_options = get_remove_payload_gcm(user_profile, truncated_message_ids)
    apns_payload = get_remove_payload_apns(user_profile, truncated_message_ids)
    payload_data_to_encrypt = get_remove_payload_data_to_encrypt(
        user_profile, truncated_message_ids
    )

    # We need to call both the legacy/non-E2EE and E2EE functions
    # for sending mobile notifications, since we don't at this time
    # know which mobile app version the user may be using.
    send_push_notifications_legacy(user_profile, apns_payload, gcm_payload, gcm_options)
    send_push_notifications(user_profile, payload_data_to_encrypt)

    # We intentionally use the non-truncated message_ids here.  We are
    # assuming in this very rare case that the user has manually
    # dismissed these notifications on the device side, and the server
    # should no longer track them as outstanding notifications.
    with transaction.atomic(savepoint=False):
        UserMessage.select_for_update_query().filter(
            user_profile_id=user_profile_id,
            message_id__in=message_ids,
        ).update(flags=F("flags").bitand(~UserMessage.flags.active_mobile_push_notification))


def send_push_notifications_legacy(
    user_profile: UserProfile,
    apns_payload: dict[str, Any],
    gcm_payload: dict[str, Any],
    gcm_options: dict[str, Any],
) -> None:
    android_devices = list(
        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.FCM).order_by("id")
    )
    apple_devices = list(
        PushDeviceToken.objects.filter(user=user_profile, kind=PushDeviceToken.APNS).order_by("id")
    )

    if len(android_devices) + len(apple_devices) == 0:
        logger.info(
            "Skipping legacy push notifications for user %s because there are no registered devices",
            user_profile.id,
        )
        return

    # While sending push notifications for new messages to older clients
    # (which don't support E2EE), if `require_e2ee_push_notifications`
    # realm setting is set to `true`, we redact the content.
    if gcm_payload.get("event") != "remove" and user_profile.realm.require_e2ee_push_notifications:
        # Make deep copies so redaction doesn't affect the original dicts
        apns_payload = copy.deepcopy(apns_payload)
        gcm_payload = copy.deepcopy(gcm_payload)

        placeholder_content = _("New message")
        apns_payload["alert"]["body"] = placeholder_content
        gcm_payload["content"] = placeholder_content

    if uses_notification_bouncer():
        send_notifications_to_bouncer(
            user_profile, apns_payload, gcm_payload, gcm_options, android_devices, apple_devices
        )
        return

    logger.info(
        "Sending mobile push notifications for local user %s: %s via FCM devices, %s via APNs devices",
        user_profile.id,
        len(android_devices),
        len(apple_devices),
    )
    user_identity = UserPushIdentityCompat(user_id=user_profile.id)

    apple_successfully_sent_count = send_apple_push_notification(
        user_identity, apple_devices, apns_payload
    )
    android_successfully_sent_count = send_android_push_notification(
        user_identity, android_devices, gcm_payload, gcm_options
    )

    do_increment_logging_stat(
        user_profile.realm,
        COUNT_STATS["mobile_pushes_sent::day"],
        None,
        timezone_now(),
        increment=apple_successfully_sent_count + android_successfully_sent_count,
    )


class RealmPushStatusDict(TypedDict):
    can_push: bool
    expected_end_timestamp: int | None


class SendNotificationResponseData(TypedDict):
    android_successfully_sent_count: int
    apple_successfully_sent_count: int
    delete_device_ids: list[int]


class SendNotificationRemoteResponseData(SendNotificationResponseData):
    realm_push_status: RealmPushStatusDict


send_notification_remote_response_data_adapter = TypeAdapter(SendNotificationRemoteResponseData)


FCMPriority: TypeAlias = Literal["high", "normal"]
APNsPriority: TypeAlias = Literal[10, 5, 1]


@dataclass
class PushRequestBasePayload:
    push_account_id: int
    encrypted_data: str


@dataclass
class FCMPushRequest:
    device_id: int
    fcm_priority: FCMPriority
    payload: PushRequestBasePayload


@dataclass
class APNsHTTPHeaders:
    apns_priority: APNsPriority
    apns_push_type: PushType


@dataclass
class APNsPayload(PushRequestBasePayload):
    aps: dict[str, int | dict[str, str]] = field(
        default_factory=lambda: {"mutable-content": 1, "alert": {"title": "New notification"}}
    )


@dataclass
class APNsPushRequest:
    device_id: int
    http_headers: APNsHTTPHeaders
    payload: APNsPayload


def get_encrypted_data(payload_data_to_encrypt: dict[str, Any], public_key_str: str) -> str:
    public_key = PublicKey(public_key_str.encode("utf-8"), Base64Encoder)
    sealed_box = SealedBox(public_key)
    encrypted_data_bytes = sealed_box.encrypt(orjson.dumps(payload_data_to_encrypt), Base64Encoder)
    encrypted_data = encrypted_data_bytes.decode("utf-8")
    return encrypted_data


def send_push_notifications(
    user_profile: UserProfile,
    payload_data_to_encrypt: dict[str, Any],
    test_notification_to_push_devices: QuerySet[PushDevice] | None = None,
) -> None:
    if test_notification_to_push_devices is not None:
        assert len(test_notification_to_push_devices) != 0
        push_devices = test_notification_to_push_devices
    else:
        # Uses 'zerver_pushdevice_user_bouncer_device_id_idx' index.
        push_devices = PushDevice.objects.filter(user=user_profile, bouncer_device_id__isnull=False)

    if len(push_devices) == 0:
        logger.info(
            "Skipping E2EE push notifications for user %s because there are no registered devices",
            user_profile.id,
        )
        return

    is_removal = payload_data_to_encrypt["type"] == "remove"
    is_test_notification = payload_data_to_encrypt["type"] == "test"

    # Note: The "Final" qualifier serves as a shorthand
    # for declaring that a variable is effectively Literal.
    fcm_priority: Final = "normal" if is_removal else "high"
    apns_priority: Final = 5 if is_removal else 10
    apns_push_type = PushType.BACKGROUND if is_removal else PushType.ALERT

    # Prepare payload to send.
    push_requests: list[FCMPushRequest | APNsPushRequest] = []
    for push_device in push_devices:
        assert push_device.bouncer_device_id is not None  # for mypy
        encrypted_data = get_encrypted_data(payload_data_to_encrypt, push_device.push_public_key)
        if push_device.token_kind == PushDevice.TokenKind.APNS:
            apns_http_headers = APNsHTTPHeaders(
                apns_priority=apns_priority,
                apns_push_type=apns_push_type,
            )
            apns_payload = APNsPayload(
                push_account_id=push_device.push_account_id,
                encrypted_data=encrypted_data,
            )
            apns_push_request = APNsPushRequest(
                device_id=push_device.bouncer_device_id,
                http_headers=apns_http_headers,
                payload=apns_payload,
            )
            push_requests.append(apns_push_request)
        else:
            fcm_payload = PushRequestBasePayload(
                push_account_id=push_device.push_account_id,
                encrypted_data=encrypted_data,
            )
            fcm_push_request = FCMPushRequest(
                device_id=push_device.bouncer_device_id,
                fcm_priority=fcm_priority,
                payload=fcm_payload,
            )
            push_requests.append(fcm_push_request)

    # Send push notification
    try:
        start_time = time.perf_counter()
        response_data: SendNotificationResponseData | SendNotificationRemoteResponseData
        if settings.ZILENCER_ENABLED:
            from zilencer.lib.push_notifications import send_e2ee_push_notifications

            response_data = send_e2ee_push_notifications(
                push_requests,
                realm=user_profile.realm,
            )
        else:
            post_data = {
                "realm_uuid": str(user_profile.realm.uuid),
                "push_requests": [asdict(push_request) for push_request in push_requests],
            }
            result = send_json_to_push_bouncer("POST", "push/e2ee/notify", post_data)
            response_data = send_notification_remote_response_data_adapter.validate_python(result)
        send_push_notifications_latency = time.perf_counter() - start_time
    except (MissingRemoteRealmError, PushNotificationsDisallowedByBouncerError) as e:
        reason = e.reason if isinstance(e, PushNotificationsDisallowedByBouncerError) else e.msg
        logger.warning("Bouncer refused to send E2EE push notification: %s", reason)
        do_set_realm_property(
            user_profile.realm,
            "push_notifications_enabled",
            False,
            acting_user=None,
        )
        do_set_push_notifications_enabled_end_timestamp(user_profile.realm, None, acting_user=None)

        if is_test_notification:
            # Propagate the exception to the caller to notify the client
            # about the error while attempting to send test push notification.
            raise e

        return

    # Handle success response data
    delete_device_ids = response_data["delete_device_ids"]
    apple_successfully_sent_count = response_data["apple_successfully_sent_count"]
    android_successfully_sent_count = response_data["android_successfully_sent_count"]

    if len(delete_device_ids) > 0:
        logger.info(
            "Deleting PushDevice rows with the following device IDs based on response from bouncer: %s",
            sorted(delete_device_ids),
        )
        # Filtering on `user_profile` is not necessary here, we do it to take
        # advantage of 'zerver_pushdevice_user_bouncer_device_id_idx' index.
        PushDevice.objects.filter(
            user=user_profile, bouncer_device_id__in=delete_device_ids
        ).delete()

    do_increment_logging_stat(
        user_profile.realm,
        COUNT_STATS["mobile_pushes_sent::day"],
        None,
        timezone_now(),
        increment=apple_successfully_sent_count + android_successfully_sent_count,
    )

    logger.info(
        "Sent E2EE mobile push notifications for user %s: %s via FCM, %s via APNs in %.3fs",
        user_profile.id,
        android_successfully_sent_count,
        apple_successfully_sent_count,
        send_push_notifications_latency,
    )

    if "realm_push_status" in response_data:
        # Cannot use `isinstance` with `TypedDict`s to make mypy know
        # which of the `TypedDict`s in the Union this is - so just cast it.
        response_data = cast(SendNotificationRemoteResponseData, response_data)
        realm_push_status_dict = response_data["realm_push_status"]
        can_push = realm_push_status_dict["can_push"]
        do_set_realm_property(
            user_profile.realm,
            "push_notifications_enabled",
            can_push,
            acting_user=None,
        )
        do_set_push_notifications_enabled_end_timestamp(
            user_profile.realm, realm_push_status_dict["expected_end_timestamp"], acting_user=None
        )
        if can_push:
            record_push_notifications_recently_working()

    if is_test_notification and len(push_requests) == len(delete_device_ids):
        # While sending test push notification, the bouncer reported
        # that there's no active registered push device. Inform the
        # same to the client.
        raise NoActivePushDeviceError


def handle_push_notification(user_profile_id: int, missed_message: dict[str, Any]) -> None:
    """
    missed_message is the event received by the
    zerver.worker.missedmessage_mobile_notifications.PushNotificationWorker.consume function.
    """
    if not push_notifications_configured():
        return

    user_profile = get_user_profile_by_id(user_profile_id)
    assert not user_profile.is_bot

    if not (
        user_profile.enable_offline_push_notifications
        or user_profile.enable_online_push_notifications
    ):
        # BUG: Investigate why it's possible to get here.
        return  # nocoverage

    with transaction.atomic(savepoint=False):
        try:
            (message, user_message) = access_message_and_usermessage(
                user_profile,
                missed_message["message_id"],
                lock_message=True,
                is_modifying_message=False,
            )
        except JsonableError:
            if ArchivedMessage.objects.filter(id=missed_message["message_id"]).exists():
                # If the cause is a race with the message being deleted,
                # that's normal and we have no need to log an error.
                return
            logging.info(
                "Unexpected message access failure handling push notifications: %s %s",
                user_profile.id,
                missed_message["message_id"],
            )
            return

        if user_message is not None:
            # If the user has read the message already, don't push-notify.
            if user_message.flags.read or user_message.flags.active_mobile_push_notification:
                return

            # Otherwise, we mark the message as having an active mobile
            # push notification, so that we can send revocation messages
            # later.
            user_message.flags.active_mobile_push_notification = True
            user_message.save(update_fields=["flags"])
        else:
            # Users should only be getting push notifications into this
            # queue for messages they haven't received if they're
            # long-term idle; anything else is likely a bug.
            if not user_profile.long_term_idle:
                logger.error(
                    "Could not find UserMessage with message_id %s and user_id %s",
                    missed_message["message_id"],
                    user_profile_id,
                )
                return

    trigger = missed_message["trigger"]

    # TODO/compatibility: Translation code for the rename of
    # `wildcard_mentioned` to `stream_wildcard_mentioned`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    if trigger == "wildcard_mentioned":
        trigger = NotificationTriggers.STREAM_WILDCARD_MENTION  # nocoverage

    # TODO/compatibility: Translation code for the rename of
    # `followed_topic_wildcard_mentioned` to `stream_wildcard_mentioned_in_followed_topic`.
    # Remove this when one can no longer directly upgrade from 7.x to main.
    if trigger == "followed_topic_wildcard_mentioned":
        trigger = NotificationTriggers.STREAM_WILDCARD_MENTION_IN_FOLLOWED_TOPIC  # nocoverage

    # TODO/compatibility: Translation code for the rename of
    # `private_message` to `direct_message`. Remove this when
    # one can no longer directly upgrade from 7.x to main.
    if trigger == "private_message":
        trigger = NotificationTriggers.DIRECT_MESSAGE  # nocoverage

    # mentioned_user_group will be None if the user is personally mentioned
    # regardless whether they are a member of the mentioned user group in the
    # message or not.
    mentioned_user_group_id = None
    mentioned_user_group_name = None
    mentioned_user_group_members_count = None
    mentioned_user_group = get_mentioned_user_group([missed_message], user_profile)
    if mentioned_user_group is not None:
        mentioned_user_group_id = mentioned_user_group.id
        mentioned_user_group_name = mentioned_user_group.name
        mentioned_user_group_members_count = mentioned_user_group.members_count

    # Soft reactivate if pushing to a long_term_idle user that is personally mentioned
    soft_reactivate_if_personal_notification(
        user_profile, {trigger}, mentioned_user_group_members_count
    )

    if message.is_channel_message:
        # This will almost always be True. The corner case where you
        # can be receiving a message from a user you cannot access
        # involves your being a guest user whose access is restricted
        # by a can_access_all_users_group policy, and you can't access
        # the sender because they are sending a message to a public
        # stream that you are subscribed to but they are not.

        can_access_sender = check_can_access_user(message.sender, user_profile)
    else:
        # For private messages, the recipient will gain access
        # to the sender if they did not had access previously.
        can_access_sender = True

    apns_payload = get_message_payload_apns(
        user_profile,
        message,
        trigger,
        mentioned_user_group_id,
        mentioned_user_group_name,
        can_access_sender,
    )
    gcm_payload, gcm_options = get_message_payload_gcm(
        user_profile, message, mentioned_user_group_id, mentioned_user_group_name, can_access_sender
    )
    payload_data_to_encrypt = get_payload_data_to_encrypt(
        user_profile, message, mentioned_user_group_id, mentioned_user_group_name, can_access_sender
    )
    logger.info("Sending push notifications to mobile clients for user %s", user_profile_id)

    # We need to call both the legacy/non-E2EE and E2EE functions
    # for sending mobile notifications, since we don't at this time
    # know which mobile app version the user may be using.
    send_push_notifications_legacy(user_profile, apns_payload, gcm_payload, gcm_options)
    send_push_notifications(user_profile, payload_data_to_encrypt)


def send_test_push_notification_directly_to_devices(
    user_identity: UserPushIdentityCompat,
    devices: Sequence[DeviceToken],
    base_payload: dict[str, Any],
    remote: Optional["RemoteZulipServer"] = None,
) -> None:
    payload = copy.deepcopy(base_payload)
    payload["event"] = "test"

    apple_devices = [device for device in devices if device.kind == PushDeviceToken.APNS]
    android_devices = [device for device in devices if device.kind == PushDeviceToken.FCM]
    # Let's make the payloads separate objects to make sure mutating to make e.g. Android
    # adjustments doesn't affect the Apple payload and vice versa.
    apple_payload = copy.deepcopy(payload)
    android_payload = copy.deepcopy(payload)

    # TODO/compatibility: Backwards-compatibility name for realm_url.
    realm_url = base_payload.get("realm_url", base_payload["realm_uri"])
    realm_name = base_payload["realm_name"]
    apns_data = {
        "alert": {
            "title": _("Test notification"),
            "body": _("This is a test notification from {realm_name} ({realm_url}).").format(
                realm_name=realm_name, realm_url=realm_url
            ),
        },
        "sound": "default",
        "custom": {"zulip": apple_payload},
    }
    send_apple_push_notification(user_identity, apple_devices, apns_data, remote=remote)

    android_payload["time"] = datetime_to_timestamp(timezone_now())
    gcm_options = {"priority": "high"}
    send_android_push_notification(
        user_identity, android_devices, android_payload, gcm_options, remote=remote
    )


def send_test_push_notification(user_profile: UserProfile, devices: list[PushDeviceToken]) -> None:
    base_payload = get_base_payload(user_profile)
    if uses_notification_bouncer():
        for device in devices:
            post_data = {
                "realm_uuid": str(user_profile.realm.uuid),
                "user_uuid": str(user_profile.uuid),
                "user_id": user_profile.id,
                "token": device.token,
                "token_kind": device.kind,
                "base_payload": base_payload,
            }

            logger.info("Sending test push notification to bouncer: %r", post_data)
            send_json_to_push_bouncer("POST", "push/test_notification", post_data)

        return

    # This server doesn't need the bouncer, so we send directly to the device.
    user_identity = UserPushIdentityCompat(
        user_id=user_profile.id, user_uuid=str(user_profile.uuid)
    )
    send_test_push_notification_directly_to_devices(
        user_identity, devices, base_payload, remote=None
    )


def send_e2ee_test_push_notification(
    user_profile: UserProfile, push_devices: QuerySet[PushDevice]
) -> None:
    payload_data_to_encrypt = get_base_payload(user_profile, for_legacy_clients=False)
    payload_data_to_encrypt["type"] = "test"
    payload_data_to_encrypt["time"] = datetime_to_timestamp(timezone_now())

    logger.info("Sending E2EE test push notification for user %s", user_profile.id)

    try:
        send_push_notifications(
            user_profile, payload_data_to_encrypt, test_notification_to_push_devices=push_devices
        )
    except PushNotificationBouncerServerError:
        # 5xx error response from bouncer server
        raise InternalBouncerServerError
    except PushNotificationBouncerRetryLaterError:
        # Network error
        raise FailedToConnectBouncerError
    except (
        # Need to resubmit realm info - `manage.py register_server`
        MissingRemoteRealmError,
        # Invalid credentials or unexpected status code
        PushNotificationBouncerError,
        # Plan doesn't allow sending push notifications
        PushNotificationsDisallowedByBouncerError,
    ):
        # Server admins need to fix these set of errors, report them.
        error_msg = f"Sending E2EE test push notification for user_id={user_profile.id} failed."
        logger.error(error_msg)
        raise PushNotificationAdminActionRequiredError


class InvalidPushDeviceTokenError(JsonableError):
    code = ErrorCode.INVALID_PUSH_DEVICE_TOKEN

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Device not recognized")


class InvalidRemotePushDeviceTokenError(JsonableError):
    code = ErrorCode.INVALID_REMOTE_PUSH_DEVICE_TOKEN

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Device not recognized by the push bouncer")


class PushNotificationsDisallowedByBouncerError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason


class HostnameAlreadyInUseBouncerError(JsonableError):
    code = ErrorCode.HOSTNAME_ALREADY_IN_USE_BOUNCER_ERROR

    data_fields = ["hostname"]

    def __init__(self, hostname: str) -> None:
        self.hostname: str = hostname

    @staticmethod
    @override
    def msg_format() -> str:
        # This message is not read by any of the client apps, just potentially displayed
        # via server administration tools, so it doesn't need translations.
        return "A server with hostname {hostname} already exists"


class PushDeviceInfoDict(TypedDict):
    status: Literal["active", "pending", "failed"]
    error_code: str | None


def get_push_devices(user_profile: UserProfile) -> dict[str, PushDeviceInfoDict]:
    # We intentionally don't try to save a database query
    # if `push_notifications_configured()` is False, in order to avoid
    # risk of clients deleting their Account records if the server
    # has its mobile notifications configuration temporarily disabled.
    rows = PushDevice.objects.filter(user=user_profile)

    return {
        str(row.push_account_id): {"status": row.status, "error_code": row.error_code}
        for row in rows
    }


class NoActivePushDeviceError(JsonableError):
    code = ErrorCode.NO_ACTIVE_PUSH_DEVICE

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _("No active registered push device")


class FailedToConnectBouncerError(JsonableError):
    http_status_code = 502
    code = ErrorCode.FAILED_TO_CONNECT_BOUNCER

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Network error while connecting to Zulip push notification service.")


class InternalBouncerServerError(JsonableError):
    http_status_code = 502
    code = ErrorCode.INTERNAL_SERVER_ERROR_ON_BOUNCER

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _("Internal server error on Zulip push notification service, retry later.")


class PushNotificationAdminActionRequiredError(JsonableError):
    http_status_code = 403
    code = ErrorCode.ADMIN_ACTION_REQUIRED

    def __init__(self) -> None:
        pass

    @staticmethod
    @override
    def msg_format() -> str:
        return _(
            "Push notification configuration issue on server, contact the server administrator or retry later."
        )
