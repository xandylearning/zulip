# Zulip Calls Plugin API Reference (V2)

This document provides a comprehensive reference for the Zulip Calls Plugin API. All endpoints are prefixed with `/api/v1/calls`.

## Authentication

All endpoints require authentication using standard Zulip authentication methods (API Key or Session).
- Most endpoints use `@authenticated_rest_api_view` (API Key / Basic Auth).
- `create-embedded` supports `@session_or_basic_api_view` (Browser Session or API Key).

---

## 1:1 Call Endpoints

### Create Call
Initiate a new 1:1 call.

- **URL**: `POST /api/v1/calls/create`
- **Authentication**: API Key (Basic Auth)

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `user_id` | Integer | Yes | The user ID of the person to call (must be in the same realm). |
| `is_video_call` | Boolean | No | `true` for video, `false` for audio only. Defaults to `true`. |

**Responses:**

- **200 OK** (Success):
  ```json
  {
      "result": "success",
      "call_id": "550e8400-e29b-41d4-a716-446655440000",
      "call_url": "https://meet.jit.si/zulip-call-xyz...?config...",
      "participant_url": "https://meet.jit.si/zulip-call-xyz...?config...",
      "call_type": "video",
      "room_name": "zulip-call-xyz",
      "receiver_online": true,
      "recipient": {
          "user_id": 123,
          "full_name": "Jane Doe",
          "email": "jane@example.com"
      }
  }
  ```

- **202 Accepted** (Queued - Recipient Busy):
  ```json
  {
      "result": "queued",
      "queue_id": "uuid",
      "message": "Jane Doe is currently in another call. You'll be notified when they're available.",
      "expires_at": "2023-10-27T10:05:00Z",
      "position": "next"
  }
  ```

- **409 Conflict**: Caller is already in a call.
- **429 Too Many Requests**: Caller recently ended a call (cool-down period).

---

### Create Embedded Call
Create a call designed for integration with Zulip's compose box or web frontend.

- **URL**: `POST /api/v1/calls/create-embedded`
- **Authentication**: Session or API Key

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `user_id` | Integer | Yes | The user ID of the person to call. |
| `is_video_call` | Boolean | No | Defaults to `true`. |
| `redirect_to_meeting` | Boolean | No | If `true`, returns a redirect action structure. Defaults to `false`. |

**Responses:**

- **200 OK** (Standard): Same as `create`.
- **200 OK** (Redirect Mode):
  ```json
  {
      "result": "success",
      "action": "redirect",
      "redirect_url": "https://meet.jit.si/zulip-call-xyz...",
      "call_id": "uuid",
      "message": "Call created successfully"
  }
  ```

---

### Respond to Call
Accept or decline an incoming call invitation.

- **URL**: `POST /api/v1/calls/<call_id>/respond`
- **Authentication**: API Key

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `response` | String | Yes | Either `accept` or `decline`. |

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "action": "accept",
      "call_url": "https://meet.jit.si/zulip-call-xyz...", 
      "message": "Call accepted successfully"
  }
  ```
  *(Note: `call_url` is `null` if declined)*

---

### End Call
End an ongoing call.

- **URL**: `POST /api/v1/calls/<call_id>/end`
- **Authentication**: API Key

**Behavior:**
- If the **caller (moderator)** calls this, the call ends for everyone (`state="ended"`).
- If the **recipient** calls this, they leave the call (`state="participant_left"`), but the call technically remains open for the other party until they leave or timeout.

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "message": "Call ended successfully"
  }
  ```
  *(Or "You have left the call" for non-moderators)*

---

### Leave Call
Explicitly leave a call. Wrapper around `end_call`.

- **URL**: `POST /api/v1/calls/<call_id>/leave`
- **Authentication**: API Key

**Responses:** Same as `end_call`.

---

### Cancel Call
Cancel an outgoing call before it is picked up.

- **URL**: `POST /api/v1/calls/<call_id>/cancel`
- **Authentication**: API Key

**Requirements:**
- Only the sender can cancel.
- Call must be in `calling` or `ringing` state.

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "message": "Call cancelled successfully"
  }
  ```

---

### Get Call Status
Retrieve the current status of a specific call.

- **URL**: `GET /api/v1/calls/<call_id>/status`
- **Authentication**: API Key

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "call": {
          "call_id": "uuid",
          "caller_id": 1,
          "recipient_id": 2,
          "call_type": "video",
          "status": "created",     // Client-facing status: created, ringing, accepted, declined, ended
          "state": "calling",      // Internal state
          "jitsi_url": "https://...",
          "timestamp": 1698310000,
          "duration": 0,
          "is_moderator": true,
          "created_at": "ISO8601...",
          "started_at": null,
          "ended_at": null
      }
  }
  ```

---

### Get Call History
Retrieve a paginated list of past calls.

- **URL**: `GET /api/v1/calls/history`
- **Authentication**: API Key

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `limit` | Integer | No | Max items to return (default 50, max 100). |
| `cursor` | String | No | Base64 pagination cursor. |
| `call_type` | String | No | Filter by `video` or `audio`. |
| `status` | String | No | Filter by `missed` or `answered`. |

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "calls": [
          {
              "call_id": "uuid",
              "call_type": "video",
              "state": "ended",
              "created_at": "...",
              "sender": { ... },
              "receiver": { ... }
          }
      ],
      "next_cursor": "base64...",
      "has_more": true
  }
  ```

---

### Acknowledge Call
Acknowledge receipt of a call notification (sets status to 'ringing'). Used by mobile clients.

- **URL**: `POST /api/v1/calls/acknowledge`
- **Authentication**: API Key

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `call_id` | String | Yes | The call ID. |
| `status` | String | Yes | Must be `ringing`. |

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "call_status": "ringing",
      "message": "Call acknowledged successfully"
  }
  ```

---

### Heartbeat
Send a heartbeat to keep the call active and update connectivity status.

- **URL**: `POST /api/v1/calls/heartbeat`
- **Authentication**: API Key

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `call_id` | String | Yes | The call ID. |
| `is_backgrounded` | Boolean | No | `true` if the app is in background. |

**Responses:**

- **200 OK**: `{"result": "success", "call_state": "accepted"}`

---

## Group Call Endpoints

All group call endpoints are prefixed with `/api/v1/calls/group`.

### Create Group Call
Start a new group call.

- **URL**: `POST /api/v1/calls/group/create`
- **Authentication**: API Key

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `call_type` | String | Yes | `video` or `audio`. |
| `title` | String | No | Title for the call. |
| `stream_id` | Integer | No | Stream to associate with. |
| `topic` | String | No | Topic (requires `stream_id`). |
| `user_ids` | String | No | Comma-separated list of user IDs to invite. |

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "call_id": "uuid",
      "call_url": "https://...",
      "call_type": "video",
      "room_name": "zulip-group-call-...",
      "host": { "user_id": 1, "full_name": "Host" },
      "invited_count": 3
  }
  ```

---

### Invite to Group Call
Invite additional users to an active group call.

- **URL**: `POST /api/v1/calls/group/<call_id>/invite`
- **Authentication**: API Key

**Parameters:**

| Name | Type | Required | Description |
|------|------|----------|-------------|
| `user_ids` | String | Yes | Comma-separated list of user IDs. |

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "invited_count": 5,
      "online_count": 3,
      "offline_count": 2
  }
  ```

---

### Join Group Call
Join an existing group call.

- **URL**: `POST /api/v1/calls/group/<call_id>/join`
- **Authentication**: API Key

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "call_url": "https://...",
      "call_type": "video",
      "title": "Weekly Standup",
      "participant_count": 4
  }
  ```

---

### Leave Group Call
Leave a group call.

- **URL**: `POST /api/v1/calls/group/<call_id>/leave`
- **Authentication**: API Key

**Responses:**

- **200 OK**: `{"result": "success", "message": "Left call successfully"}`

---

### Decline Group Call
Decline a group call invitation.

- **URL**: `POST /api/v1/calls/group/<call_id>/decline`
- **Authentication**: API Key

**Responses:**

- **200 OK**: `{"result": "success", "message": "Call declined"}`

---

### End Group Call
End a group call for everyone (Host only).

- **URL**: `POST /api/v1/calls/group/<call_id>/end`
- **Authentication**: API Key

**Responses:**

- **200 OK**: `{"result": "success", "message": "Call ended successfully"}`

---

### Get Group Call Status
Get status details of a group call.

- **URL**: `GET /api/v1/calls/group/<call_id>/status`
- **Authentication**: API Key

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "call": {
          "call_id": "uuid",
          "state": "active",
          "participant_count": 5,
          "max_participants": 16,
          "host": { ... },
          ...
      }
  }
  ```

---

### Get Group Call Participants
Get list of participants in a group call.

- **URL**: `GET /api/v1/calls/group/<call_id>/participants`
- **Authentication**: API Key

**Responses:**

- **200 OK**:
  ```json
  {
      "result": "success",
      "participants": [
          {
              "user_id": 1,
              "full_name": "Alice",
              "state": "joined",  // joined, invited, left, declined, missed
              "is_host": true,
              "joined_at": "..."
          },
          ...
      ],
      "total_count": 5,
      "joined_count": 3
  }
  ```
