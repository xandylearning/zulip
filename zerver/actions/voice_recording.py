from django.conf import settings
from django.utils.translation import gettext as _

from zerver.lib.exceptions import JsonableError
from zerver.lib.stream_subscription import get_active_subscriptions_for_stream_id
from zerver.models import Realm, Stream, UserProfile
from zerver.models.users import get_user_by_id_in_realm_including_cross_realm
from zerver.tornado.django_api import send_event_rollback_unsafe


def do_send_voice_recording_notification(
    realm: Realm, sender: UserProfile, recipient_user_profiles: list[UserProfile], operator: str
) -> None:
    sender_dict = {"user_id": sender.id, "email": sender.email}
    recipient_dicts = [
        {"user_id": profile.id, "email": profile.email} for profile in recipient_user_profiles
    ]
    event = dict(
        type="voice_recording",
        message_type="direct",
        op=operator,
        sender=sender_dict,
        recipients=recipient_dicts,
    )
    user_ids_to_notify = [
        user.id
        for user in recipient_user_profiles
        if user.is_active and user.receives_typing_notifications
    ]
    send_event_rollback_unsafe(realm, event, user_ids_to_notify)


def check_send_voice_recording_notification(
    sender: UserProfile, user_ids: list[int], operator: str
) -> None:
    realm = sender.realm
    if sender.id not in user_ids:
        user_ids.append(sender.id)
    user_profiles = []
    for user_id in user_ids:
        try:
            user_profile = get_user_by_id_in_realm_including_cross_realm(user_id, sender.realm)
        except UserProfile.DoesNotExist:
            raise JsonableError(_("Invalid user ID {user_id}").format(user_id=user_id))
        user_profiles.append(user_profile)
    do_send_voice_recording_notification(
        realm=realm,
        sender=sender,
        recipient_user_profiles=user_profiles,
        operator=operator,
    )


def do_send_stream_voice_recording_notification(
    sender: UserProfile, operator: str, stream: Stream, topic_name: str
) -> None:
    sender_dict = {"user_id": sender.id, "email": sender.email}
    event = dict(
        type="voice_recording",
        message_type="stream",
        op=operator,
        sender=sender_dict,
        stream_id=stream.id,
        topic=topic_name,
    )
    subscriptions_query = get_active_subscriptions_for_stream_id(
        stream.id, include_deactivated_users=False
    )
    total_subscriptions = subscriptions_query.count()
    if total_subscriptions > settings.MAX_STREAM_SIZE_FOR_TYPING_NOTIFICATIONS:
        return
    user_ids_to_notify = set(
        subscriptions_query.exclude(user_profile__long_term_idle=True)
        .exclude(user_profile__receives_typing_notifications=False)
        .values_list("user_profile_id", flat=True)
    )
    send_event_rollback_unsafe(sender.realm, event, user_ids_to_notify)
