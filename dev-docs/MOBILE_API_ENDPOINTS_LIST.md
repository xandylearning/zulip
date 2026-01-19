# Mobile API Endpoints List

Complete list of mobile-related REST API endpoints in Zulip.

## Authentication & Server Info

### Authentication
- `POST /api/v1/fetch_api_key` - Get API key with username/password
- `POST /api/v1/dev_fetch_api_key` - Get API key (development only, no password)
- `POST /api/v1/jwt/fetch_api_key` - Get API key using JWT token
- `POST /api/v1/users/me/api_key/regenerate` - Regenerate API key
- `GET /api/v1/server_settings` - Get server settings and compatibility info
- `GET /compatibility` - Check global compatibility

## Push Notifications

### Device Registration (Legacy)
- `POST /api/v1/users/me/apns_device_token` - Register iOS device token (APNS)
- `DELETE /api/v1/users/me/apns_device_token` - Remove iOS device token
- `POST /api/v1/users/me/android_gcm_reg_id` - Register Android device token (FCM/GCM)
- `DELETE /api/v1/users/me/android_gcm_reg_id` - Remove Android device token

### Push Notifications (Modern E2EE)
- `POST /api/v1/mobile_push/register` - Register device for end-to-end encrypted push notifications
- `POST /api/v1/mobile_push/test_notification` - Send test push notification
- `POST /api/v1/mobile_push/e2ee/test_notification` - Send test E2EE push notification

## Messages

### Message Operations
- `POST /api/v1/messages` - Send a message
- `GET /api/v1/messages` - Get messages
- `GET /api/v1/messages/{message_id}` - Get a single message
- `PATCH /api/v1/messages/{message_id}` - Edit a message
- `DELETE /api/v1/messages/{message_id}` - Delete a message
- `POST /api/v1/messages/{message_id}/reactions` - Add emoji reaction
- `DELETE /api/v1/messages/{message_id}/reactions` - Remove emoji reaction
- `GET /api/v1/messages/{message_id}/read_receipts` - Get read receipts
- `POST /api/v1/messages/{message_id}/report` - Report a message
- `POST /api/v1/messages/{message_id}/typing` - Set typing status for message editing

### Message Flags
- `POST /api/v1/messages/flags` - Update message flags (read/unread, starred, etc.)
- `POST /api/v1/messages/flags/narrow` - Update message flags for narrow
- `POST /api/v1/messages/flags` - Mark all messages as read
- `POST /api/v1/users/me/subscriptions/{stream_id}/read` - Mark stream as read
- `POST /api/v1/users/me/subscriptions/{stream_id}/topics/{topic_name}/read` - Mark topic as read

### Scheduled Messages
- `GET /api/v1/scheduled_messages` - Get scheduled messages
- `POST /api/v1/scheduled_messages` - Create scheduled message
- `PATCH /api/v1/scheduled_messages/{scheduled_message_id}` - Edit scheduled message
- `DELETE /api/v1/scheduled_messages/{scheduled_message_id}` - Delete scheduled message

### Drafts
- `GET /api/v1/drafts` - Get drafts
- `POST /api/v1/drafts` - Create drafts
- `PATCH /api/v1/drafts/{draft_id}` - Edit a draft
- `DELETE /api/v1/drafts/{draft_id}` - Delete a draft

## Real-time Events

- `POST /api/v1/register` - Register an event queue
- `GET /api/v1/events` - Get events from queue (long polling)
- `DELETE /api/v1/events` - Delete an event queue

**Event Types:**
- `message` - New messages
- `update_message` - Message edits
- `delete_message` - Message deletions
- `reaction` - Emoji reactions added/removed
- `presence` - User presence changes
- `typing` - Typing indicators
- `subscription` - Channel subscription changes
- `user` - User profile changes
- `update_message_flags` - Message flag updates
- `stream` - Stream/channel changes
- `realm` - Realm/organization changes

## Users & Presence

### User Profile
- `GET /api/v1/users/me` - Get own user profile
- `DELETE /api/v1/users/me` - Deactivate own account
- `GET /api/v1/users` - Get all users
- `GET /api/v1/users/{user_id}` - Get user by ID
- `GET /api/v1/users/{email}` - Get user by email
- `POST /api/v1/users/me/avatar` - Set avatar
- `DELETE /api/v1/users/me/avatar` - Delete avatar

### User Status
- `GET /api/v1/users/{user_id}/status` - Get user status
- `POST /api/v1/users/me/status` - Update own status
- `POST /api/v1/users/{user_id}/status` - Update user status (admin)

### Presence (Last Seen)
- `GET /api/v1/users/{user_id_or_email}/presence` - Get user presence/last seen
- `POST /api/v1/users/me/presence` - Update own presence status
- `GET /api/v1/realm/presence` - Get all users' presence in realm

### Typing Indicators
- `POST /api/v1/typing` - Set typing status

### User Settings
- `PATCH /api/v1/settings` - Update user settings
- `POST /api/v1/users/me/muted_users/{muted_user_id}` - Mute a user
- `DELETE /api/v1/users/me/muted_users/{muted_user_id}` - Unmute a user

## Channels (Streams)

### Channel Operations
- `GET /api/v1/streams` - Get all channels
- `GET /api/v1/streams/{stream_id}` - Get channel by ID
- `GET /api/v1/get_stream_id` - Get channel ID by name
- `POST /api/v1/streams` - Create a channel
- `PATCH /api/v1/streams/{stream_id}` - Update a channel
- `DELETE /api/v1/streams/{stream_id}` - Archive a channel
- `GET /api/v1/streams/{stream_id}/topics` - Get topics in channel
- `DELETE /api/v1/streams/{stream_id}/topics/{topic_name}` - Delete a topic

### Channel Subscriptions
- `GET /api/v1/users/me/subscriptions` - Get subscribed channels
- `POST /api/v1/users/me/subscriptions` - Subscribe to channels
- `DELETE /api/v1/users/me/subscriptions` - Unsubscribe from channels
- `GET /api/v1/users/{user_id}/subscriptions/{stream_id}` - Get subscription status
- `GET /api/v1/streams/{stream_id}/members` - Get channel subscribers
- `PATCH /api/v1/users/me/subscriptions/{stream_id}` - Update subscription settings
- `POST /api/v1/users/me/subscriptions/properties` - Update subscription properties
- `PATCH /api/v1/users/me/subscriptions/muted_topics` - Update muted topics

### Channel Folders
- `POST /api/v1/users/me/stream_folders` - Create channel folder
- `GET /api/v1/users/me/stream_folders` - Get channel folders
- `PATCH /api/v1/users/me/stream_folders` - Reorder channel folders
- `PATCH /api/v1/users/me/stream_folders/{folder_id}` - Update channel folder

## File Uploads & Attachments

- `POST /api/v1/user_uploads` - Upload a file
- `GET /api/v1/user_uploads/{realm_id}/{filename}` - Get uploaded file
- `GET /api/v1/attachments` - Get all attachments
- `DELETE /api/v1/attachments/{attachment_id}` - Delete an attachment
- `GET /api/v1/user_uploads/{realm_id}/{filename}` - Get temporary URL for file

## User Groups

- `GET /api/v1/user_groups` - Get user groups
- `POST /api/v1/user_groups` - Create user group
- `PATCH /api/v1/user_groups/{user_group_id}` - Update user group
- `DELETE /api/v1/user_groups/{user_group_id}` - Deactivate user group
- `POST /api/v1/user_groups/{user_group_id}/members` - Update user group members
- `GET /api/v1/user_groups/{user_group_id}/members` - Get user group members

## Customization

### Custom Emoji
- `GET /api/v1/realm/emoji` - Get all custom emoji
- `POST /api/v1/realm/emoji/{emoji_name}` - Upload custom emoji
- `DELETE /api/v1/realm/emoji/{emoji_name}` - Deactivate custom emoji

### Alert Words
- `GET /api/v1/users/me/alert_words` - Get alert words
- `POST /api/v1/users/me/alert_words` - Add alert words
- `DELETE /api/v1/users/me/alert_words` - Remove alert words

## Navigation Views

- `GET /api/v1/users/me/navigation_views` - Get all navigation views
- `POST /api/v1/users/me/navigation_views` - Add navigation view
- `PATCH /api/v1/users/me/navigation_views/{view_id}` - Update navigation view
- `DELETE /api/v1/users/me/navigation_views/{view_id}` - Remove navigation view

## Reminders

- `POST /api/v1/reminders` - Create message reminder
- `GET /api/v1/reminders` - Get reminders
- `DELETE /api/v1/reminders/{reminder_id}` - Delete a reminder

## Saved Snippets

- `GET /api/v1/users/me/saved_snippets` - Get all saved snippets
- `POST /api/v1/users/me/saved_snippets` - Create saved snippet
- `PATCH /api/v1/users/me/saved_snippets/{snippet_id}` - Edit saved snippet
- `DELETE /api/v1/users/me/saved_snippets/{snippet_id}` - Delete saved snippet

## Server & Organization

- `GET /api/v1/server_settings` - Get server settings
- `GET /api/v1/realm/linkifiers` - Get linkifiers
- `GET /api/v1/realm/emoji` - Get custom emoji
- `GET /api/v1/realm/profile_fields` - Get custom profile fields

## Bot Storage

- `PUT /api/v1/bot_storage` - Update bot storage
- `GET /api/v1/bot_storage` - Get bot storage
- `DELETE /api/v1/bot_storage` - Remove bot storage

## Notes

1. **Base URL**: All endpoints are prefixed with `/api/v1/`
2. **Authentication**: All endpoints require HTTP Basic Auth with `email:api_key`
3. **Content-Type**: Most POST/PATCH requests use `application/x-www-form-urlencoded` or `application/json`
4. **Mobile-Specific**: Push notification endpoints are primarily for mobile apps
5. **Real-time**: Use the events API for real-time updates instead of polling

## Mobile-Specific Features Summary

The following endpoints are particularly important for mobile apps:

1. **Authentication**: `fetch_api_key`, `jwt/fetch_api_key`
2. **Push Notifications**: `mobile_push/register`, `mobile_push/test_notification`
3. **Real-time Events**: `register`, `events` (for live updates)
4. **Presence**: `users/me/presence` (for last seen/online status)
5. **Reactions**: `messages/{id}/reactions` (for emoji reactions)
6. **Messages**: All message endpoints for chat functionality
