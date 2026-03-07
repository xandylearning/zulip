# Zulip Calls Plugin API Reference

## Overview

This document describes the plugin's API. For the **current, canonical** list of endpoints and behavior (post v1.1 overhaul), see:

- **[README.md](./README.md)** — API table and quick examples
- **[docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md](./docs/FLUTTER_WHATSAPP_CALLING_GUIDE.md)** — Full request/response shapes, event `op` names, and mobile usage

### Current behavior (v1.1)

- **1:1 calls**: Create via `POST /api/v1/calls/create` (body: `user_id`, `is_video_call`). Recipient busy → **409 Conflict** (no queue). Respond via `POST /api/v1/calls/<call_id>/respond`. End via `POST /api/v1/calls/<call_id>/end` (either party; ends for both). No moderator for 1:1.
- **Events**: `initiated`, `incoming_call`, `ringing`, `accepted`, `declined`, `ended`, `cancelled`, `missed`. Include `avatar_url` in sender/receiver.
- **Removed**: Call queue, `leave` for 1:1, `/api/v1/calls/initiate` (use `create`).

## Table of Contents
1. [Authentication](#authentication)
2. [Call Initiation](#call-initiation)
3. [Call Acknowledgment](#call-acknowledgment)
4. [Call Response](#call-response)
5. [Call Status Updates](#call-status-updates)
6. [Call Termination](#call-termination)
7. [Call Management](#call-management)
8. [WebSocket Events](#websocket-events)
9. [Error Handling](#error-handling)

## Authentication

All API endpoints require Zulip authentication using one of the following methods:

### Basic Authentication
```
Authorization: Basic base64(email:api_key)
```

### Session Authentication
Use Zulip's session authentication for web requests.

## Call Initiation

### POST /api/v1/calls/create

**Description**: Create a 1:1 call with full database tracking. If the recipient is in another call, the server returns **409 Conflict** (no queue).

**Parameters** (form or JSON):
- `user_id` (required): Recipient's Zulip user ID
- `is_video_call` (optional): `true` or `false`; default `true`

**Response (201)**:
```json
{
  "result": "success",
  "call_id": "uuid-string",
  "call_url": "https://meet.example.com/zulip-call-abc123",
  "call_type": "video",
  "receiver_online": true
}
```

**Response (409 — recipient busy)**:
```json
{
  "result": "error",
  "message": "Jane Smith is currently in another call"
}
```

**Events**: `initiated` to caller, `incoming_call` to receiver (with `avatar_url` in payloads).

**Example**:
```bash
curl -X POST "https://your-zulip.com/api/v1/calls/create" \
  -u "caller@example.com:api-key" \
  -d "user_id=456" \
  -d "is_video_call=true"
```

---

## Call Acknowledgment

### POST /api/v1/calls/acknowledge

**Description**: Receiver acknowledges the incoming call (transition to ringing). No `status` body required; send `call_id` only.

**Parameters**: `call_id` (required)

**Response**:
```json
{
  "result": "success",
  "call_status": "ringing"
}
```

**Event**: Sends `ringing` to caller.

**Example**:
```bash
curl -X POST "https://your-zulip.com/api/v1/calls/acknowledge" \
  -u "recipient@example.com:api-key" \
  -d "call_id=CALL_ID"
```

---

## Call Heartbeat

### POST /api/v1/calls/heartbeat

**Description**: Send heartbeat to indicate app is alive and call is active.

**Parameters**:
```json
{
  "call_id": "string (required)",
  "is_backgrounded": "boolean (optional, default: false)"
}
```

**Response**:
```json
{
  "result": "success",
  "call_state": "accepted"
}
```

**Usage**: Client should send heartbeat periodically (e.g. every 30 seconds) while in an active call. If the call has already ended, response includes `call_state: "ended"`.

**Example**:
```bash
curl -X POST "https://your-zulip.com/api/v1/calls/heartbeat" \
  -u "user@example.com:api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "abc123-def456-ghi789",
    "is_backgrounded": "false"
  }'
```

**Notes**:
- Only call participants can send heartbeat
- Heartbeat is used for network failure detection (15-second timeout)
- Background state is tracked but doesn't affect call flow
- Server cleanup may mark call as ended/network_failure after prolonged missing heartbeats

---

## Call Response

### POST /api/v1/calls/<call_id>/respond

**Description**: Accept or decline an incoming call.

**Parameters**: `response` (required): `accept` or `decline`

**Response (Accept)**:
```json
{
  "result": "success",
  "action": "accept",
  "call_url": "https://meet.example.com/zulip-call-abc123?jwt=...",
  "message": "Call accepted successfully"
}
```

**Response (Decline)**:
```json
{
  "result": "success",
  "action": "decline",
  "call_url": null,
  "message": "Call declined successfully"
}
```

**Events**: Accept → `accepted` to both; decline → `declined` to both and push to caller.

**Example**:
```bash
curl -X POST "https://your-zulip.com/api/v1/calls/CALL_ID/respond" \
  -u "recipient@example.com:api-key" \
  -d "response=accept"

# Reject call
curl -X POST "https://your-zulip.com/api/v1/calls/respond" \
  -u "recipient@example.com:api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "abc123-def456-ghi789",
    "response": "reject"
  }'
```

---

### POST /api/v1/calls/{call_id}/respond

**Description**: Alternative endpoint using path parameter.

**Path Parameter**: `call_id` - The call ID

**Parameters**:
```json
{
  "response": "string (required, 'accept' or 'decline')"
}
```

**Response**: Same as above

---

## Call Status Updates

### POST /api/v1/calls/status

**Description**: Update call status during an active call.

**Parameters**:
```json
{
  "call_id": "string (required)",
  "status": "string (required)"
}
```

**Valid Status Values**:
- `connected` - Call participants are connected
- `on_hold` - Call is on hold
- `muted` - Participant is muted
- `video_disabled` - Video is disabled
- `screen_sharing` - Screen sharing is active

**Response**:
```json
{
  "result": "success",
  "call_status": "accepted",
  "status": "connected",
  "message": "Call status updated successfully"
}
```

**WebSocket Event**: Sends `call_status_update` to other participant

**Example**:
```bash
curl -X POST "https://your-zulip.com/api/v1/calls/status" \
  -u "caller@example.com:api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "call_id": "abc123-def456-ghi789",
    "status": "connected"
  }'
```

**Notes**:
- Both call participants can update status
- Call must be in 'accepted' or 'active' state
- Creates a 'status_update' event in call history

---

## Call Termination

### POST /api/v1/calls/<call_id>/end

**Description**: End the call. For 1:1 calls, either participant may call this; the call ends for both (WhatsApp-style). Idempotent: if the call is already ended, returns success.

**Parameters**: None (call_id in path).

**Response**:
```json
{
  "result": "success",
  "message": "Call ended successfully"
}
```

**Event**: Sends `ended` to both participants.

**Example**:
```bash
curl -X POST "https://your-zulip.com/api/v1/calls/CALL_ID/end" \
  -u "user@example.com:api-key"
```

---

## Call Management

### GET /api/v1/calls/{call_id}/status

**Description**: Get current status of a specific call.

**Path Parameter**: `call_id` - The call ID

**Response**:
```json
{
  "result": "success",
  "call": {
    "call_id": "abc123-def456-ghi789",
    "state": "accepted",
    "call_url": "https://meet.jit.si/zulip-call-abc123",
    "call_type": "video",
    "created_at": "2024-01-01T12:00:00Z",
    "started_at": "2024-01-01T12:00:30Z",
    "ended_at": null,
    "sender": {
      "user_id": 123,
      "full_name": "John Doe",
      "email": "caller@example.com"
    },
    "receiver": {
      "user_id": 456,
      "full_name": "Jane Smith",
      "email": "recipient@example.com"
    }
  }
}
```

---

### GET /api/v1/calls/history

**Description**: Get call history for the authenticated user with cursor-based pagination.

**Query Parameters**:
- `limit` (optional): Number of calls to return (max 100, default 50)
- `cursor` (optional): Base64-encoded cursor for pagination
- `call_type` (optional): Filter by call type ('video' or 'audio')
- `status` (optional): Filter by status ('missed', 'answered', or 'all')

**Response**:
```json
{
  "result": "success",
  "calls": [
    {
      "call_id": "abc123-def456-ghi789",
      "call_type": "video",
      "state": "ended",
      "was_initiator": true,
      "other_user": {
        "user_id": 456,
        "full_name": "Jane Smith",
        "email": "recipient@example.com"
      },
      "created_at": "2024-01-01T12:00:00Z",
      "started_at": "2024-01-01T12:00:30Z",
      "ended_at": "2024-01-01T12:15:45Z",
      "duration_seconds": 915
    }
  ],
  "next_cursor": "MjAyNC0wMS0wMVQxMjowMDowMFpfYWJjMTIzLWRlZjQ1Ni1naGk3ODk=",
  "has_more": true
}
```

**Notes**:
- Use `next_cursor` value for subsequent requests to get the next page
- Cursor-based pagination is more efficient than offset-based for large datasets
- Filters can be combined (e.g., `?call_type=video&status=missed`)

---

### GET /api/v1/calls/active

**Description**: Get all active calls for the current user.

**Response**:
```json
{
  "result": "success",
  "active_calls": [
    {
      "call_id": "abc123-def456-ghi789",
      "call_type": "video",
      "state": "accepted",
      "sender_id": 123,
      "sender_name": "John Doe",
      "receiver_id": 456,
      "receiver_name": "Jane Smith",
      "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
      "created_at": "2024-01-01T12:00:00Z",
      "is_outgoing": true
    }
  ],
  "count": 1
}
```

---

### POST /api/v1/calls/end-all

**Description**: End all active calls for the current user.

**Response**:
```json
{
  "result": "success",
  "message": "Ended 2 active calls",
  "calls_ended": 2
}
```

---

### GET /api/v1/calls/queue

**Description**: Get pending queued calls for the current user.

**Response**:
```json
{
  "result": "success",
  "queue": [
    {
      "queue_id": "queue-uuid-123",
      "caller": {
        "user_id": 789,
        "full_name": "Alice Johnson",
        "email": "alice@example.com"
      },
      "call_type": "video",
      "created_at": "2024-01-01T12:05:00Z",
      "expires_at": "2024-01-01T12:10:00Z"
    }
  ],
  "count": 1
}
```

**Notes**:
- Shows calls waiting for the user to become available
- Queue entries automatically expire after 5 minutes
- User will be notified when queue is processed

---

### POST /api/v1/calls/queue/{queue_id}/cancel

**Description**: Cancel a queued call before it's processed.

**Path Parameter**: `queue_id` - The queue entry ID

**Response**:
```json
{
  "result": "success",
  "message": "Queued call cancelled successfully"
}
```

**Notes**:
- Only the caller can cancel their queued call
- Cannot cancel if already processed or expired

---

### POST /api/v1/calls/{call_id}/leave

**Description**: Leave a call (for non-moderators). Moderators use this to end the call for everyone.

**Path Parameter**: `call_id` - The call ID

**Response (Non-Moderator)**:
```json
{
  "result": "success",
  "message": "You have left the call"
}
```

**Response (Moderator)**:
```json
{
  "result": "success",
  "message": "Call ended successfully"
}
```

**Notes**:
- Call initiator (moderator) ends call for everyone
- Other participants only leave, call continues for remaining participant
- Triggers queue processing for the user who left/ended

---

## WebSocket Events

The plugin sends real-time WebSocket events through Zulip's event system. Connect to Zulip's WebSocket endpoint and listen for `call_event` types.

### Event Structure

```json
{
  "type": "call_event",
  "event_type": "participant_ringing|accepted|declined|ended|cancelled|missed|timeout|call_status_update",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "calling|ringing|accepted|missed|timeout|cancelled|ended",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:00:30Z"
}
```

### Event Types

| Event Type | Description | Triggered By | Sent To |
|------------|-------------|--------------|---------|
| `participant_ringing` | Call acknowledged by recipient | `/acknowledge` | Caller |
| `call_accepted` | Call accepted by recipient | `/respond` (accept) | Both participants |
| `call_rejected` | Call rejected by recipient | `/respond` (reject) | Caller |
| `ended` | Call terminated | `/end` (by moderator) | Both participants |
| `cancelled` | Call cancelled by sender | `/cancel` | Both participants |
| `missed` | Call missed by recipient (no answer) | cleanup (90s timeout) | Both participants |
| `timeout` | Call timed out (stuck active) | cleanup | Both participants |
| `call_status_update` | Status changed during call | `/status` | Other participant |
| `participant_left` | Non-moderator left call | `/end` (by participant) | Other participant |
| `network_failure` | Network disconnection detected | cleanup (60s no heartbeat) | Both participants |

### WebSocket Connection

```javascript
// Register for events
const response = await fetch('/api/v1/register', {
  method: 'POST',
  headers: {
    'Authorization': 'Basic ' + btoa('email:api_key'),
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    event_types: ['call_event']
  })
});

const { queue_id, last_event_id } = await response.json();

// Connect WebSocket
const ws = new WebSocket(`wss://your-zulip.com/api/v1/events?queue_id=${queue_id}&last_event_id=${last_event_id}`);

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'call_event') {
    handleCallEvent(data);
  }
};
```

---

## Error Handling

### Standard Error Response

```json
{
  "result": "error",
  "message": "Error description",
  "code": "ERROR_CODE"
}
```

### Common HTTP Status Codes

| Status Code | Description | Common Causes |
|-------------|-------------|---------------|
| 400 | Bad Request | Missing parameters, invalid values |
| 401 | Unauthorized | Invalid authentication |
| 403 | Forbidden | Not authorized for this call |
| 404 | Not Found | Call not found, user not found |
| 409 | Conflict | Call already in progress |
| 500 | Internal Server Error | Server-side error |

### Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| "Missing required parameter: call_id" | call_id not provided | Include call_id in request |
| "Call not found" | Invalid call_id or unauthorized | Check call_id and permissions |
| "User is currently in another call" | User has active call | End existing call first |
| "Call cannot be acknowledged. Current status: ended" | Call already ended | Check call status |
| "Invalid response. Must be 'accept' or 'reject'" | Wrong response value | Use 'accept' or 'reject' |
| "Call is not active. Current status: ended" | Trying to update ended call | Check call status |

### Error Handling Best Practices

1. **Check Response Status**: Always check the `result` field
2. **Handle Network Errors**: Implement retry logic for network failures
3. **Validate Call State**: Check call status before operations
4. **User Feedback**: Show meaningful error messages to users
5. **Logging**: Log errors for debugging

### Example Error Handling

```javascript
async function respondToCall(callId, response) {
  try {
    const result = await fetch('/api/v1/calls/respond', {
      method: 'POST',
      headers: {
        'Authorization': 'Basic ' + btoa('email:api_key'),
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        call_id: callId,
        response: response
      })
    });

    const data = await result.json();

    if (data.result === 'success') {
      return { success: true, data };
    } else {
      return { success: false, error: data.message };
    }
  } catch (error) {
    return { success: false, error: 'Network error: ' + error.message };
  }
}
```

---

## Rate Limiting

The plugin respects Zulip's standard rate limiting:
- **API calls**: 200 requests per minute per user
- **WebSocket connections**: 1 connection per user per client

For high-frequency status updates, implement appropriate throttling in your client.

---

## Testing

Use the provided cURL examples to test each endpoint. For WebSocket testing, use browser developer tools or WebSocket testing tools.

### Complete Test Flow

```bash
# 1. Initiate call
CALL_RESPONSE=$(curl -s -X POST "http://localhost:9991/api/v1/calls/initiate" \
  -u "caller@example.com:api-key" \
  -d "recipient_email=recipient@example.com" \
  -d "is_video_call=true")

CALL_ID=$(echo $CALL_RESPONSE | jq -r '.call_id')

# 2. Acknowledge call
curl -X POST "http://localhost:9991/api/v1/calls/acknowledge" \
  -u "recipient@example.com:api-key" \
  -d "call_id=$CALL_ID" \
  -d "status=ringing"

# 3. Accept call
curl -X POST "http://localhost:9991/api/v1/calls/respond" \
  -u "recipient@example.com:api-key" \
  -d "call_id=$CALL_ID" \
  -d "response=accept"

# 4. Update status
curl -X POST "http://localhost:9991/api/v1/calls/status" \
  -u "caller@example.com:api-key" \
  -d "call_id=$CALL_ID" \
  -d "status=connected"

# 5. End call
curl -X POST "http://localhost:9991/api/v1/calls/end" \
  -u "caller@example.com:api-key" \
  -d "call_id=$CALL_ID"
```

This completes the comprehensive API reference for the Zulip Calls Plugin with full WebSocket integration.