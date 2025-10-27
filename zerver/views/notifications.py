"""API endpoints for broadcast notification system."""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.utils.translation import gettext as _
from pydantic import Json

from django.shortcuts import render

from zerver.decorator import require_realm_admin, zulip_login_required
from zerver.lib.exceptions import JsonableError, ResourceNotFoundError, OrganizationAdministratorRequiredError
from zerver.lib.notifications_broadcast import (
    get_notification_statistics,
    send_broadcast_notification,
)
from zerver.lib.response import json_success
from zerver.lib.typed_endpoint import typed_endpoint
from zerver.models import (
    BroadcastButtonClick,
    BroadcastNotification,
    Message,
    NotificationRecipient,
    NotificationTemplate,
    UserProfile,
)


# ============ Template Management Endpoints ============


@require_realm_admin
@typed_endpoint
def create_notification_template(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    name: str,
    content: str = "",
    template_type: str = "text_only",
    template_structure: Json[dict] | None = None,
    ai_generated: bool = False,
    ai_prompt: str = "",
) -> HttpResponse:
    """Create a new notification template."""
    realm = user_profile.realm

    # Check if template with same name already exists
    if NotificationTemplate.objects.filter(realm=realm, name=name).exists():
        raise JsonableError(_("A template with this name already exists"))

    # Validate template_type
    if template_type not in ["text_only", "rich_media"]:
        raise JsonableError(_("Invalid template_type. Must be 'text_only' or 'rich_media'"))

    template = NotificationTemplate.objects.create(
        name=name,
        content=content,
        template_type=template_type,
        template_structure=template_structure or {},
        ai_generated=ai_generated,
        ai_prompt=ai_prompt,
        creator=user_profile,
        realm=realm,
    )

    return json_success(
        request,
        data={
            "id": template.id,
            "name": template.name,
            "content": template.content,
            "template_type": template.template_type,
            "template_structure": template.template_structure,
            "ai_generated": template.ai_generated,
            "ai_prompt": template.ai_prompt,
            "creator_id": template.creator_id,
            "created_time": template.created_time.timestamp(),
            "last_edit_time": template.last_edit_time.timestamp(),
        },
    )


@require_realm_admin
def list_notification_templates(
    request: HttpRequest, user_profile: UserProfile
) -> HttpResponse:
    """List all notification templates for the realm."""
    realm = user_profile.realm

    templates = NotificationTemplate.objects.filter(realm=realm, is_active=True).select_related(
        "creator"
    )

    template_data = [
        {
            "id": template.id,
            "name": template.name,
            "content": template.content,
            "template_type": template.template_type,
            "template_structure": template.template_structure,
            "ai_generated": template.ai_generated,
            "ai_prompt": template.ai_prompt,
            "creator_email": template.creator.email,
            "creator_full_name": template.creator.full_name,
            "created_time": template.created_time.timestamp(),
            "last_edit_time": template.last_edit_time.timestamp(),
        }
        for template in templates
    ]

    return json_success(request, data={"templates": template_data})


@require_realm_admin
@typed_endpoint
def update_notification_template(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    template_id: int,
    name: str | None = None,
    content: str | None = None,
    template_type: str | None = None,
    template_structure: Json[dict] | None = None,
    ai_generated: bool | None = None,
    ai_prompt: str | None = None,
) -> HttpResponse:
    """Update an existing notification template."""
    realm = user_profile.realm

    try:
        template = NotificationTemplate.objects.get(id=template_id, realm=realm)
    except NotificationTemplate.DoesNotExist:
        raise ResourceNotFoundError(_("Template not found"))

    update_fields = ["last_edit_time"]

    if name is not None:
        # Check for name conflicts
        if (
            NotificationTemplate.objects.filter(realm=realm, name=name)
            .exclude(id=template_id)
            .exists()
        ):
            raise JsonableError(_("A template with this name already exists"))
        template.name = name
        update_fields.append("name")

    if content is not None:
        template.content = content
        update_fields.append("content")

    if template_type is not None:
        if template_type not in ["text_only", "rich_media"]:
            raise JsonableError(_("Invalid template_type. Must be 'text_only' or 'rich_media'"))
        template.template_type = template_type
        update_fields.append("template_type")

    if template_structure is not None:
        template.template_structure = template_structure
        update_fields.append("template_structure")

    if ai_generated is not None:
        template.ai_generated = ai_generated
        update_fields.append("ai_generated")

    if ai_prompt is not None:
        template.ai_prompt = ai_prompt
        update_fields.append("ai_prompt")

    template.save(update_fields=update_fields)

    return json_success(
        request,
        data={
            "id": template.id,
            "name": template.name,
            "content": template.content,
            "template_type": template.template_type,
            "template_structure": template.template_structure,
            "ai_generated": template.ai_generated,
            "ai_prompt": template.ai_prompt,
            "last_edit_time": template.last_edit_time.timestamp(),
        },
    )


@require_realm_admin
@typed_endpoint
def delete_notification_template(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    template_id: int,
) -> HttpResponse:
    """Delete (soft delete) a notification template."""
    realm = user_profile.realm
    
    try:
        template = NotificationTemplate.objects.get(id=template_id, realm=realm)
    except NotificationTemplate.DoesNotExist:
        raise ResourceNotFoundError(_("Template not found"))
    
    template.is_active = False
    template.save(update_fields=["is_active"])
    
    return json_success(request)


# ============ Broadcast Notification Endpoints ============


@require_realm_admin
@typed_endpoint
def send_broadcast(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    subject: str,
    content: str,
    target_type: str,
    target_ids: Json[list[int]],
    template_id: Json[int] | None = None,
    attachment_paths: Json[list[str]] | None = None,
    media_content: Json[dict] | None = None,
) -> HttpResponse:
    """Send a broadcast notification."""
    realm = user_profile.realm
    
    # Validate target_type
    valid_target_types = [
        BroadcastNotification.TARGET_USERS,
        BroadcastNotification.TARGET_CHANNELS,
        BroadcastNotification.TARGET_BROADCAST,
    ]
    if target_type not in valid_target_types:
        raise JsonableError(_("Invalid target_type"))
    
    # Validate template if provided
    if template_id is not None:
        try:
            NotificationTemplate.objects.get(id=template_id, realm=realm, is_active=True)
        except NotificationTemplate.DoesNotExist:
            raise ResourceNotFoundError(_("Template not found"))
    
    # Send the broadcast notification
    try:
        notification = send_broadcast_notification(
            sender=user_profile,
            realm=realm,
            subject=subject,
            content=content,
            target_type=target_type,
            target_ids=target_ids,
            attachment_paths=attachment_paths or [],
            template_id=template_id,
            media_content=media_content,
        )
        
        return json_success(
            request,
            data={
                "notification_id": notification.id,
                "sent_time": notification.sent_time.timestamp(),
            },
        )
    except Exception as e:
        raise JsonableError(str(e))


@require_realm_admin
def list_broadcast_notifications(
    request: HttpRequest, user_profile: UserProfile
) -> HttpResponse:
    """List all broadcast notifications for the realm."""
    realm = user_profile.realm
    
    notifications = BroadcastNotification.objects.filter(realm=realm).select_related(
        "sender", "template"
    )[:100]  # Limit to recent 100
    
    notification_data = [
        {
            "id": notification.id,
            "subject": notification.subject,
            "sender_email": notification.sender.email,
            "sender_full_name": notification.sender.full_name,
            "sent_time": notification.sent_time.timestamp(),
            "target_type": notification.target_type,
            "template_name": notification.template.name if notification.template else None,
            "recipient_count": NotificationRecipient.objects.filter(
                notification=notification
            ).count(),
        }
        for notification in notifications
    ]
    
    return json_success(request, data={"notifications": notification_data})


@require_realm_admin
@typed_endpoint
def get_broadcast_notification_detail(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    notification_id: int,
) -> HttpResponse:
    """Get detailed information about a specific broadcast notification."""
    realm = user_profile.realm
    
    try:
        notification = BroadcastNotification.objects.select_related(
            "sender", "template"
        ).get(id=notification_id, realm=realm)
    except BroadcastNotification.DoesNotExist:
        raise ResourceNotFoundError(_("Notification not found"))
    
    # Get statistics
    stats = get_notification_statistics(notification_id)
    
    return json_success(
        request,
        data={
            "id": notification.id,
            "subject": notification.subject,
            "content": notification.content,
            "sender_email": notification.sender.email,
            "sender_full_name": notification.sender.full_name,
            "sent_time": notification.sent_time.timestamp(),
            "target_type": notification.target_type,
            "target_ids": notification.target_ids,
            "attachment_paths": notification.attachment_paths,
            "template_name": notification.template.name if notification.template else None,
            "statistics": stats,
        },
    )


@require_realm_admin
@typed_endpoint
def get_broadcast_notification_recipients(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    notification_id: int,
) -> HttpResponse:
    """Get detailed recipient list and status for a broadcast notification."""
    realm = user_profile.realm
    
    try:
        notification = BroadcastNotification.objects.get(id=notification_id, realm=realm)
    except BroadcastNotification.DoesNotExist:
        raise ResourceNotFoundError(_("Notification not found"))
    
    recipients = NotificationRecipient.objects.filter(notification=notification).select_related(
        "recipient_user", "recipient_channel"
    )
    
    recipient_data = [
        {
            "id": recipient.id,
            "user_email": recipient.recipient_user.email,
            "user_full_name": recipient.recipient_user.full_name,
            "channel_name": recipient.recipient_channel.name if recipient.recipient_channel else None,
            "status": recipient.status,
            "sent_time": recipient.sent_time.timestamp() if recipient.sent_time else None,
            "delivered_time": recipient.delivered_time.timestamp() if recipient.delivered_time else None,
            "read_time": recipient.read_time.timestamp() if recipient.read_time else None,
            "error_message": recipient.error_message,
            "message_id": recipient.message_id,
        }
        for recipient in recipients
    ]
    
    return json_success(request, data={"recipients": recipient_data})


# ============ Standalone Page View ============


@zulip_login_required
def broadcast_notification_page(request: HttpRequest) -> HttpResponse:
    """Render the standalone broadcast notification page."""
    user_profile = request.user
    assert user_profile.is_authenticated
    
    # Check if user is realm admin
    if not user_profile.is_realm_admin:
        raise OrganizationAdministratorRequiredError
    
    # Get realm users for the pill widgets
    from zerver.models import UserProfile
    import json
    
    realm_users = UserProfile.objects.filter(
        realm=user_profile.realm,
        is_active=True,
        is_bot=False
    ).select_related().values(
        'id', 'email', 'full_name', 'avatar_hash', 'avatar_source', 'avatar_version', 'is_bot', 'is_active'
    )
    
    # Convert to the format expected by the people module
    users_data = []
    for user in realm_users:
        users_data.append({
            'user_id': user['id'],
            'email': user['email'],
            'full_name': user['full_name'],
            'avatar_hash': user['avatar_hash'],
            'avatar_source': user['avatar_source'],
            'avatar_version': user['avatar_version'],
            'is_bot': user['is_bot'],
            'is_active': user['is_active']
        })
    
    # Get streams for the pill widgets
    from zerver.models import Stream
    realm_streams = Stream.objects.filter(
        realm=user_profile.realm,
        deactivated=False
    ).values('id', 'name', 'description')

    # Convert streams to expected format
    streams_data = [
        {
            'stream_id': stream['id'],
            'name': stream['name'],
            'description': stream['description']
        }
        for stream in realm_streams
    ]

    context = {
        "user_profile": user_profile,
        "page_params": {
            "page_type": "broadcast_notification",
            "development_environment": settings.DEVELOPMENT,
            "request_language": "en",
            "realm_users": users_data,
            "realm_streams": streams_data,
        }
    }

    return render(request, "zerver/broadcast_notification_page.html", context)


# ============ Button Click Tracking Endpoints ============


@zulip_login_required
@typed_endpoint
def track_button_click(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: int,
    button_id: str,
    button_type: str = "url",
    button_text: str,
    button_url: str | None = None,
) -> HttpResponse:
    """Track a button click on a broadcast notification message."""
    # Verify message exists and user has access
    try:
        message = Message.objects.get(id=message_id, realm=user_profile.realm)
    except Message.DoesNotExist:
        raise ResourceNotFoundError(_("Message not found"))

    # Get the broadcast notification if available
    broadcast_notification_id = None
    if message.broadcast_template_data:
        broadcast_notification_id = message.broadcast_template_data.get("broadcast_notification_id")

    broadcast_notification = None
    if broadcast_notification_id:
        try:
            broadcast_notification = BroadcastNotification.objects.get(
                id=broadcast_notification_id, realm=user_profile.realm
            )
        except BroadcastNotification.DoesNotExist:
            pass

    # Create click record
    click = BroadcastButtonClick.objects.create(
        user=user_profile,
        message=message,
        broadcast_notification=broadcast_notification,
        button_id=button_id,
        button_type=button_type,
        button_text=button_text,
        button_url=button_url or "",
    )

    return json_success(
        request,
        data={
            "click_id": click.id,
            "clicked_at": click.clicked_at.timestamp(),
        },
    )


@zulip_login_required
@typed_endpoint
def send_quick_reply(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    message_id: int,
    button_id: str,
    reply_text: str,
) -> HttpResponse:
    """Handle quick reply button action by sending a reply message."""
    # Verify message exists
    try:
        message = Message.objects.get(id=message_id, realm=user_profile.realm)
    except Message.DoesNotExist:
        raise ResourceNotFoundError(_("Message not found"))

    # Track the button click first
    track_button_click(
        request,
        user_profile,
        message_id=message_id,
        button_id=button_id,
        button_type="quick_reply",
        button_text=reply_text,
    )

    # Send reply as a normal message (implementation depends on message type)
    # For now, just return success - actual reply sending can be handled by frontend
    return json_success(
        request,
        data={
            "success": True,
            "message": _("Quick reply recorded"),
        },
    )


# ============ Analytics Endpoints ============


@require_realm_admin
@typed_endpoint
def get_broadcast_analytics(
    request: HttpRequest,
    user_profile: UserProfile,
    *,
    broadcast_id: int,
) -> HttpResponse:
    """Get analytics data for a broadcast notification including button clicks."""
    realm = user_profile.realm

    # Get the broadcast notification
    try:
        notification = BroadcastNotification.objects.get(id=broadcast_id, realm=realm)
    except BroadcastNotification.DoesNotExist:
        raise ResourceNotFoundError(_("Broadcast notification not found"))

    # Get delivery statistics
    stats = get_notification_statistics(broadcast_id)

    # Get button click analytics
    button_clicks = BroadcastButtonClick.objects.filter(
        broadcast_notification=notification
    ).select_related("user")

    # Aggregate clicks by button_id
    button_analytics = {}
    for click in button_clicks:
        if click.button_id not in button_analytics:
            button_analytics[click.button_id] = {
                "button_id": click.button_id,
                "button_text": click.button_text,
                "button_type": click.button_type,
                "total_clicks": 0,
                "unique_users": set(),
                "clicks": [],
            }

        button_analytics[click.button_id]["total_clicks"] += 1
        button_analytics[click.button_id]["unique_users"].add(click.user.id)
        button_analytics[click.button_id]["clicks"].append(
            {
                "user_id": click.user.id,
                "user_email": click.user.email,
                "user_full_name": click.user.full_name,
                "clicked_at": click.clicked_at.timestamp(),
            }
        )

    # Convert sets to counts for JSON serialization
    for button_id in button_analytics:
        button_analytics[button_id]["unique_users"] = len(
            button_analytics[button_id]["unique_users"]
        )

    # Calculate engagement rate
    total_recipients = stats["total"]
    total_button_clicks = sum(ba["total_clicks"] for ba in button_analytics.values())
    engagement_rate = (
        (total_button_clicks / total_recipients * 100) if total_recipients > 0 else 0
    )

    return json_success(
        request,
        data={
            "delivery_stats": stats,
            "button_analytics": list(button_analytics.values()),
            "engagement_rate": round(engagement_rate, 2),
            "total_button_clicks": total_button_clicks,
        },
    )

