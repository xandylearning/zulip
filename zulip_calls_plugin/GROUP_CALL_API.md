# Group Call API Endpoints

This document describes the group call API endpoints added to the Zulip Calls Plugin.

## Endpoints

### 1. Create Group Call
**POST** `/api/v1/calls/group/create`

Create a new group call.

**Parameters:**
- `call_type` (required): "video" or "audio"
- `title` (optional): Title for the call
- `stream_id` (optional): Stream ID to associate call with
- `topic` (optional): Topic name (requires stream_id)
- `user_ids` (optional): Comma-separated list of user IDs to invite immediately

**Response:**
```json
{
  "result": "success",
  "call_id": "uuid",
  "call_url": "https://jitsi.example.com/room-id",
  "call_type": "video",
  "title": "Team Meeting",
  "room_name": "zulip-group-call-...",
  "host": {
    "user_id": 123,
    "full_name": "Alice"
  },
  "invited_count": 3
}
```

### 2. Invite to Group Call
**POST** `/api/v1/calls/group/<call_id>/invite`

Invite users to an existing group call.

**Parameters:**
- `user_ids` (required): Comma-separated list of user IDs to invite

**Response:**
```json
{
  "result": "success",
  "invited_count": 3,
  "online_count": 2,
  "offline_count": 1
}
```

### 3. Join Group Call
**POST** `/api/v1/calls/group/<call_id>/join`

Join an existing group call.

**Response:**
```json
{
  "result": "success",
  "call_url": "https://jitsi.example.com/room-id",
  "call_type": "video",
  "title": "Team Meeting",
  "participant_count": 5
}
```

### 4. Leave Group Call
**POST** `/api/v1/calls/group/<call_id>/leave`

Leave a group call.

**Response:**
```json
{
  "result": "success",
  "message": "Left call successfully"
}
```

### 5. Decline Group Call
**POST** `/api/v1/calls/group/<call_id>/decline`

Decline a group call invitation.

**Response:**
```json
{
  "result": "success",
  "message": "Call declined"
}
```

### 6. End Group Call
**POST** `/api/v1/calls/group/<call_id>/end`

End a group call (host only).

**Response:**
```json
{
  "result": "success",
  "message": "Call ended successfully"
}
```

### 7. Get Group Call Status
**GET** `/api/v1/calls/group/<call_id>/status`

Get the current status of a group call.

**Response:**
```json
{
  "result": "success",
  "call": {
    "call_id": "uuid",
    "call_type": "video",
    "state": "active",
    "title": "Team Meeting",
    "jitsi_url": "https://jitsi.example.com/room-id",
    "host": {
      "user_id": 123,
      "full_name": "Alice"
    },
    "stream_id": 456,
    "topic": "Daily Standup",
    "created_at": "2026-01-25T10:00:00Z",
    "ended_at": null,
    "participant_count": 5,
    "max_participants": 50
  }
}
```

### 8. Get Group Call Participants
**GET** `/api/v1/calls/group/<call_id>/participants`

Get the list of participants in a group call.

**Response:**
```json
{
  "result": "success",
  "participants": [
    {
      "user_id": 123,
      "full_name": "Alice",
      "email": "alice@example.com",
      "state": "joined",
      "is_host": true,
      "invited_at": "2026-01-25T10:00:00Z",
      "joined_at": "2026-01-25T10:00:00Z",
      "left_at": null
    },
    {
      "user_id": 124,
      "full_name": "Bob",
      "email": "bob@example.com",
      "state": "joined",
      "is_host": false,
      "invited_at": "2026-01-25T10:00:00Z",
      "joined_at": "2026-01-25T10:01:00Z",
      "left_at": null
    }
  ],
  "total_count": 2,
  "joined_count": 2
}
```

## Participant States

- `invited`: User has been invited but hasn't responded
- `ringing`: User's client is ringing (acknowledged invitation)
- `joined`: User has joined the call
- `declined`: User declined the invitation
- `left`: User left the call
- `missed`: User didn't respond to invitation within timeout

## Authorization

All endpoints require authentication via Zulip's REST API authentication.

### Permissions:
- **Create**: Any authenticated user can create a group call
- **Invite**: Host and joined participants can invite others
- **Join**: Any invited participant can join
- **Leave**: Any participant can leave
- **Decline**: Any invited participant can decline
- **End**: Only the host can end the call
- **View Status/Participants**: Only participants can view

## Events

Group calls generate real-time events via Zulip's event system:

- `group_call.created`: Call created (sent to host)
- `group_call.participant_invited`: User invited (sent to invited user)
- `group_call.participants_invited`: Multiple users invited (sent to existing participants)
- `group_call.participant_joined`: User joined (sent to all active participants)
- `group_call.participant_left`: User left (sent to remaining participants)
- `group_call.participant_declined`: User declined (sent to host and joined participants)
- `group_call.ended`: Call ended (sent to all participants)

## Example Usage

### Create and Start a Group Call

```bash
# 1. Create call with initial invites
curl -X POST https://zulip.example.com/api/v1/calls/group/create \
  -u email:api_key \
  -d "call_type=video" \
  -d "title=Team Standup" \
  -d "user_ids=101,102,103"

# Response: { "result": "success", "call_id": "abc-123", ... }

# 2. Invited users join
curl -X POST https://zulip.example.com/api/v1/calls/group/abc-123/join \
  -u user101:api_key

# 3. Invite additional users
curl -X POST https://zulip.example.com/api/v1/calls/group/abc-123/invite \
  -u email:api_key \
  -d "user_ids=104,105"

# 4. Get current status
curl https://zulip.example.com/api/v1/calls/group/abc-123/status \
  -u email:api_key

# 5. Host ends call
curl -X POST https://zulip.example.com/api/v1/calls/group/abc-123/end \
  -u email:api_key
```

## Integration with Actions

All endpoints use the action functions from `zulip_calls_plugin/actions.py`:

- `do_create_group_call()`: Sends group_call.created event
- `do_invite_to_group_call()`: Handles invitations with offline detection
- `do_join_group_call()`: Notifies participants of joins
- `do_leave_group_call()`: Notifies participants of leaves
- `do_decline_group_call()`: Notifies host/participants of declines
- `do_end_group_call()`: Notifies all participants of call end

This ensures consistent event delivery and proper offline/online user handling.
