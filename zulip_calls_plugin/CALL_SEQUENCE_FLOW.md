# Zulip Calls Plugin v2.0 - Call Sequence Flow

## Overview

This document explains the complete call sequence flow in the Zulip Calls Plugin v2.0, from call initiation to termination, including all API calls, WebSocket events, database operations, and new features like call queueing, missed call notifications, and moderator privileges.

## Call Flow Diagrams

### Standard Call Flow
```
Caller                    Zulip Server                Recipient
  |                           |                          |
  |-- 1. POST /calls/create --|                          |
  |                           |-- 2. WebSocket Event --->|
  |                           |    participant_ringing    |
  |                           |                          |
  |                           |<-- 3. POST /acknowledge -|
  |                           |                          |
  |<-- 4. WebSocket Event ----|                          |
  |    participant_ringing    |                          |
  |                           |                          |
  |                           |<-- 5. POST /respond -----|
  |                           |    (accept/reject)      |
  |                           |                          |
  |<-- 6. WebSocket Event ----|                          |
  |    call_accepted/rejected |                          |
  |                           |                          |
  |-- 7. Jitsi Meet Opens ---|                          |
  |                           |                          |
  |<-- 8. WebSocket Events --|                          |
  |    call_status_update      |                          |
  |                           |                          |
  |-- 9. POST /end ----------|                          |
  |                           |                          |
  |<-- 10. WebSocket Event --|                          |
  |    call_ended             |                          |
```

### Call Queue Flow (v2.0)
```
Caller A                   Zulip Server                Busy User B
  |                           |                          |
  |-- 1. POST /calls/create --|                          |
  |                           |-- 2. Check if B is busy -|
  |                           |                          |
  |<-- 3. HTTP 202 Queued ----|                          |
  |    queue_id, expires_at   |                          |
  |                           |                          |
  |                           |-- 4. B's call ends -----|
  |                           |                          |
  |                           |-- 5. Process queue -----|
  |                           |                          |
  |<-- 6. Push Notification --|                          |
  |    "B is now available"   |                          |
  |                           |                          |
  |-- 7. Auto-create call ----|                          |
  |                           |                          |
  |                           |-- 8. Normal call flow ---|
```

### Missed Call Flow (v2.0)
```
Caller                    Zulip Server                Recipient
  |                           |                          |
  |-- 1. POST /calls/create --|                          |
  |                           |-- 2. WebSocket Event --->|
  |                           |    participant_ringing    |
  |                           |                          |
  |                           |<-- 3. No response (90s) -|
  |                           |                          |
  |                           |-- 4. Auto-timeout -------|
  |                           |                          |
  |                           |-- 5. Send missed call ---|
  |                           |    push notification     |
  |                           |                          |
  |<-- 6. WebSocket Event ----|                          |
  |    call_missed            |                          |
```

## New Features in v2.0

### Enhanced Call Management
- **Missed Call Notifications**: Automatic push notifications for missed calls after 90-second timeout
- **Call Queue System**: Automatic queueing when calling busy users with 5-minute expiration
- **Moderator Privileges**: Call initiators can end calls for everyone, participants can only leave
- **Cursor-Based Pagination**: Efficient pagination for call history with filtering
- **Network Resilience**: Extended heartbeat timeouts (60s) for slow networks
- **Race Condition Prevention**: 5-second cooldown between calls

### New API Endpoints
- `GET /api/v1/calls/queue` - View queued calls
- `POST /api/v1/calls/queue/{id}/cancel` - Cancel queued call
- `POST /api/v1/calls/{id}/leave` - Leave call (for non-moderators)
- Enhanced `GET /api/v1/calls/history` with cursor pagination and filters

### New WebSocket Events
- `participant_left` - Non-moderator left call
- `network_failure` - Network disconnection detected
- `missed` - Call missed by recipient
- `queued` - Call queued due to busy user

## Detailed Sequence Flow

### Phase 1: Call Initiation

#### Step 1: Caller Initiates Call
**API Call:**
```http
POST /api/v1/calls/create
Content-Type: application/json
Authorization: Basic base64(email:api_key)

{
  "recipient_email": "recipient@example.com",
  "is_video_call": true
}
```

**Server Actions:**
1. Validate caller authentication
2. Find recipient user by email
3. Check if recipient is available (not in another call)
4. **NEW v2.0**: Check for 5-second cooldown to prevent race conditions
5. **NEW v2.0**: If recipient is busy, create CallQueue entry instead of rejecting
6. Generate unique call ID (UUID)
7. Create Jitsi room URL
8. Create Call record in database with moderator field
9. Create CallEvent record (type: "initiated")

**Response (Call Created):**
```json
{
  "result": "success",
  "call_id": "abc123-def456-ghi789",
  "call_url": "https://meet.jit.si/zulip-call-abc123",
  "participant_url": "https://meet.jit.si/zulip-call-abc123?participant=true",
  "call_type": "video",
  "room_name": "zulip-call-abc123",
  "recipient": {
    "user_id": 456,
    "full_name": "Jane Smith",
    "email": "recipient@example.com"
  }
}
```

**Response (Call Queued - NEW v2.0):**
```json
{
  "result": "queued",
  "queue_id": "queue-uuid-123",
  "message": "Jane Smith is currently in another call. You'll be notified when they're available.",
  "expires_at": "2024-01-01T12:10:00Z",
  "position": "next"
}
```

#### Step 2: Send WebSocket Event to Recipient
**WebSocket Event:**
```json
{
  "type": "call_event",
  "event_type": "participant_ringing",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "calling",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:00:00Z"
}
```

**Recipient Actions:**
- Receive WebSocket event
- Show incoming call notification
- Display caller information
- Show accept/reject buttons

### Phase 2: Call Acknowledgment

#### Step 3: Recipient Acknowledges Call
**API Call:**
```http
POST /api/v1/calls/acknowledge
Content-Type: application/json
Authorization: Basic base64(recipient_email:api_key)

{
  "call_id": "abc123-def456-ghi789",
  "status": "ringing"
}
```

**Server Actions:**
1. Validate recipient authentication
2. Find call by call_id
3. Verify recipient is authorized for this call
4. Update call state to "ringing"
5. Create CallEvent record (type: "acknowledged")
6. Send WebSocket event to caller

**Response:**
```json
{
  "result": "success",
  "call_status": "ringing",
  "message": "Call acknowledged successfully"
}
```

#### Step 4: Send WebSocket Event to Caller
**WebSocket Event:**
```json
{
  "type": "call_event",
  "event_type": "participant_ringing",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "ringing",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:00:30Z"
}
```

**Caller Actions:**
- Receive WebSocket event
- Update UI to show "ringing" status
- Display recipient information

### Phase 3: Call Response

#### Step 5: Recipient Responds to Call
**API Call (Accept):**
```http
POST /api/v1/calls/respond
Content-Type: application/json
Authorization: Basic base64(recipient_email:api_key)

{
  "call_id": "abc123-def456-ghi789",
  "response": "accept"
}
```

**Server Actions (Accept):**
1. Validate recipient authentication
2. Find call by call_id
3. Verify call can be accepted (state: "ringing")
4. Update call state to "accepted"
5. Set answered_at timestamp
6. Create CallEvent record (type: "accepted")
7. Send WebSocket events to both participants

**Response (Accept):**
```json
{
  "result": "success",
  "status": "ok",
  "call_status": "accepted",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123"
}
```

**API Call (Reject):**
```http
POST /api/v1/calls/respond
Content-Type: application/json
Authorization: Basic base64(recipient_email:api_key)

{
  "call_id": "abc123-def456-ghi789",
  "response": "reject"
}
```

**Server Actions (Reject):**
1. Validate recipient authentication
2. Find call by call_id
3. Update call state to "rejected"
4. Set ended_at timestamp
5. Create CallEvent record (type: "rejected")
6. Send WebSocket event to caller

**Response (Reject):**
```json
{
  "result": "success",
  "status": "ok",
  "call_status": "rejected"
}
```

#### Step 6: Send WebSocket Events
**For Accepted Call:**
```json
{
  "type": "call_event",
  "event_type": "call_accepted",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "accepted",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:00:45Z"
}
```

**For Rejected Call:**
```json
{
  "type": "call_event",
  "event_type": "call_rejected",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "rejected",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:00:45Z"
}
```

**Participant Actions:**
- **If Accepted**: Both participants open Jitsi Meet with the provided URL
- **If Rejected**: Caller receives rejection notification

### Phase 4: Active Call Status Updates

#### Step 7: Status Updates During Call
**API Call:**
```http
POST /api/v1/calls/status
Content-Type: application/json
Authorization: Basic base64(user_email:api_key)

{
  "call_id": "abc123-def456-ghi789",
  "status": "connected"
}
```

**Valid Status Values:**
- `connected` - Call participants are connected
- `on_hold` - Call is on hold
- `muted` - Participant is muted
- `video_disabled` - Video is disabled
- `screen_sharing` - Screen sharing is active

**Server Actions:**
1. Validate user authentication
2. Find call by call_id
3. Verify user is participant in this call
4. Verify call is in "accepted" state
5. Create CallEvent record (type: "status_update")
6. Send WebSocket event to other participant

**Response:**
```json
{
  "result": "success",
  "call_status": "accepted",
  "status": "connected",
  "message": "Call status updated successfully"
}
```

#### Step 8: Send WebSocket Event to Other Participant
**WebSocket Event:**
```json
{
  "type": "call_event",
  "event_type": "call_status_update",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "accepted",
  "status": "connected",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:01:00Z"
}
```

**Other Participant Actions:**
- Receive WebSocket event
- Update UI to reflect new call status
- Show visual indicators (muted, on hold, etc.)

### Phase 5: Call Queue Processing (NEW v2.0)

#### Step 9: Queue Processing When User Becomes Available
**Triggered when:**
- A call ends (both participants or moderator ends)
- A call is declined
- Cleanup script runs

**Server Actions:**
1. Check if user has pending queue entries
2. Find oldest pending queue entry
3. Verify caller is still available
4. Create new call from queue entry
5. Send push notification to caller: "User is now available"
6. Send WebSocket events to both participants
7. Mark queue entry as "converted_to_call"

**WebSocket Event to Queued Caller:**
```json
{
  "type": "call_event",
  "event_type": "call",
  "call_id": "new-call-id",
  "from_queue": true,
  "message": "User is now available for your call"
}
```

### Phase 6: Call Termination

#### Step 10: End Call (Enhanced v2.0)
**API Call:**
```http
POST /api/v1/calls/end
Content-Type: application/json
Authorization: Basic base64(user_email:api_key)

{
  "call_id": "abc123-def456-ghi789",
  "reason": "user_hangup"
}
```

**Server Actions (Enhanced v2.0):**
1. Validate user authentication
2. Find call by call_id
3. Verify user is participant in this call
4. **NEW v2.0**: Check if user is moderator (call initiator)
5. **If Moderator**: End call for everyone
   - Update call state to "ended"
   - Set ended_at timestamp
   - Create CallEvent record (type: "ended")
   - Send WebSocket event "ended" to both participants
   - Process call queue for both users
6. **If Participant**: Leave call only
   - Create CallEvent record (type: "participant_left")
   - Send WebSocket event "participant_left" to other participant
   - Process call queue for leaving user
   - Call continues for remaining participant

**Response:**
```json
{
  "result": "success",
  "status": "ok",
  "message": "Call ended successfully",
  "call_id": "abc123-def456-ghi789"
}
```

#### Step 11: Send WebSocket Events (Enhanced v2.0)

**If Moderator Ends Call:**
```json
{
  "type": "call_event",
  "event_type": "ended",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "ended",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:15:45Z"
}
```

**If Participant Leaves Call:**
```json
{
  "type": "call_event",
  "event_type": "participant_left",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "state": "accepted",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:15:45Z"
}
```

**Participant Actions:**
- Receive WebSocket event
- Close Jitsi Meet window
- Update UI to show call ended
- Update call history

### Phase 7: Missed Call Notifications (NEW v2.0)

#### Step 12: Automatic Missed Call Detection
**Triggered by cleanup script every minute:**

**Server Actions:**
1. Find calls in "calling" or "ringing" state for >90 seconds
2. Update call state to "missed"
3. Set ended_at timestamp
4. Create CallEvent record (type: "missed")
5. **NEW v2.0**: Send push notification to recipient
6. **NEW v2.0**: Send WebSocket event to caller
7. Set is_missed_notified = True

**Push Notification to Recipient:**
```json
{
  "event": "missed_call",
  "call_id": "abc123-def456-ghi789",
  "sender_id": 123,
  "sender_full_name": "John Doe",
  "call_type": "video",
  "timestamp": "2024-01-01T12:01:30Z"
}
```

**WebSocket Event to Caller:**
```json
{
  "type": "call_event",
  "event_type": "missed",
  "call_id": "abc123-def456-ghi789",
  "call_type": "video",
  "sender_id": 123,
  "sender_name": "John Doe",
  "receiver_id": 456,
  "receiver_name": "Jane Smith",
  "state": "missed",
  "created_at": "2024-01-01T12:00:00Z",
  "timestamp": "2024-01-01T12:01:30Z"
}
```

## Database State Changes

### Call Record States (Enhanced v2.0)
```
calling → ringing → accepted → ended
   ↓         ↓         ↓
rejected   missed   cancelled
   ↓         ↓         ↓
timeout   network_failure
```

### CallQueue Record States (NEW v2.0)
```
pending → converted_to_call
   ↓
expired
   ↓
cancelled
```

### CallEvent Records Created (Enhanced v2.0)
1. **initiated** - When call is created
2. **acknowledged** - When recipient acknowledges
3. **accepted/rejected** - When recipient responds
4. **status_update** - During active call
5. **ended** - When call is terminated by moderator
6. **participant_left** - When non-moderator leaves call
7. **missed** - When call times out (90s)
8. **network_failure** - When heartbeat timeout (60s)

## Error Scenarios (Enhanced v2.0)

### Call Timeout (Enhanced)
If recipient doesn't respond within 90 seconds:
1. Server automatically updates call state to "missed"
2. Creates CallEvent record (type: "missed")
3. **NEW v2.0**: Sends push notification to recipient
4. **NEW v2.0**: Sends WebSocket event "missed" to caller
5. Sets is_missed_notified = True

### Network Disconnection (Enhanced)
If participant loses connection for >60 seconds:
1. Server detects missing heartbeat
2. Updates call state to "network_failure"
3. Creates CallEvent record (type: "network_failure")
4. Sends WebSocket event to both participants
5. **NEW v2.0**: Processes call queue for both users

### Call Rejection (Enhanced)
If recipient rejects call:
1. Call state changes to "rejected"
2. Caller receives rejection notification
3. **NEW v2.0**: Processes call queue for recipient
4. No Jitsi Meet window opens
5. Call is marked as ended

### Race Condition Prevention (NEW v2.0)
If caller tries to create call within 5 seconds of previous call:
1. Server returns HTTP 429 (Too Many Requests)
2. Response: "Please wait a moment before making another call"
3. Prevents duplicate calls from race conditions

### Queue Expiration (NEW v2.0)
If queued call expires after 5 minutes:
1. Server marks queue entry as "expired"
2. Sends push notification to caller: "User is still busy, try again later"
3. Queue entry is cleaned up automatically

## Push Notifications (Enhanced v2.0)

### Incoming Call Notification
```json
{
  "event": "call",
  "type": "call",
  "call_id": "abc123-def456-ghi789",
  "sender_id": 123,
  "sender_full_name": "John Doe",
  "call_type": "video",
  "jitsi_url": "https://meet.jit.si/zulip-call-abc123",
  "timeout_seconds": 90
}
```

### Missed Call Notification (NEW v2.0)
```json
{
  "event": "missed_call",
  "call_id": "abc123-def456-ghi789",
  "sender_id": 123,
  "sender_full_name": "John Doe",
  "call_type": "video",
  "timestamp": "2024-01-01T12:01:30Z"
}
```

### Queue Notification (NEW v2.0)
```json
{
  "event": "call",
  "type": "call",
  "call_id": "new-call-id",
  "from_queue": true,
  "message": "User is now available for your call"
}
```

### Notification Actions
- Show incoming call UI
- Play ringtone
- Display caller information
- Provide accept/reject buttons
- **NEW v2.0**: Show missed call badge
- **NEW v2.0**: Display queue position
- Auto-dismiss after timeout

## Complete Implementation Example

```javascript
class CallSequenceManager {
  constructor(zulipClient) {
    this.zulipClient = zulipClient;
    this.activeCalls = new Map();
  }

  // Phase 1: Initiate Call
  async initiateCall(recipientEmail, isVideoCall = true) {
    const response = await this.zulipClient.post('/api/v1/calls/create', {
      recipient_email: recipientEmail,
      is_video_call: isVideoCall
    });

    if (response.result === 'success') {
      const call = {
        callId: response.call_id,
        callUrl: response.call_url,
        callType: response.call_type,
        recipient: response.recipient,
        state: 'calling'
      };

      this.activeCalls.set(response.call_id, call);
      return call;
    }
  }

  // Phase 2: Acknowledge Call
  async acknowledgeCall(callId) {
    const response = await this.zulipClient.post('/api/v1/calls/acknowledge', {
      call_id: callId,
      status: 'ringing'
    });

    if (response.result === 'success') {
      const call = this.activeCalls.get(callId);
      if (call) {
        call.state = 'ringing';
      }
    }
  }

  // Phase 3: Respond to Call
  async respondToCall(callId, response) {
    const result = await this.zulipClient.post('/api/v1/calls/respond', {
      call_id: callId,
      response: response
    });

    if (result.result === 'success') {
      const call = this.activeCalls.get(callId);
      if (call) {
        call.state = result.call_status;
        if (response === 'accept') {
          call.jitsiUrl = result.jitsi_url;
          this.openJitsiCall(call.jitsiUrl);
        }
      }
    }
  }

  // Phase 4: Update Status
  async updateCallStatus(callId, status) {
    const response = await this.zulipClient.post('/api/v1/calls/status', {
      call_id: callId,
      status: status
    });

    if (response.result === 'success') {
      const call = this.activeCalls.get(callId);
      if (call) {
        call.status = status;
      }
    }
  }

  // Phase 5: End Call
  async endCall(callId, reason = 'user_hangup') {
    const response = await this.zulipClient.post('/api/v1/calls/end', {
      call_id: callId,
      reason: reason
    });

    if (response.result === 'success') {
      this.activeCalls.delete(callId);
      this.closeJitsiCall();
    }
  }

  // WebSocket Event Handlers
  handleCallEvent(event) {
    switch (event.event_type) {
      case 'participant_ringing':
        this.onParticipantRinging(event);
        break;
      case 'call_accepted':
        this.onCallAccepted(event);
        break;
      case 'call_rejected':
        this.onCallRejected(event);
        break;
      case 'call_ended':
        this.onCallEnded(event);
        break;
      case 'call_status_update':
        this.onCallStatusUpdate(event);
        break;
    }
  }

  onParticipantRinging(event) {
    console.log(`${event.receiver_name} is ringing...`);
    this.updateCallUI(event, 'ringing');
  }

  onCallAccepted(event) {
    console.log('Call accepted!');
    this.openJitsiCall(event.jitsi_url);
    this.updateCallUI(event, 'accepted');
  }

  onCallRejected(event) {
    console.log('Call rejected');
    this.updateCallUI(event, 'rejected');
  }

  onCallEnded(event) {
    console.log('Call ended');
    this.activeCalls.delete(event.call_id);
    this.closeJitsiCall();
    this.updateCallUI(event, 'ended');
  }

  onCallStatusUpdate(event) {
    console.log(`Call status updated: ${event.status}`);
    this.updateCallUI(event, 'status_update');
  }

  // UI Methods
  openJitsiCall(jitsiUrl) {
    window.open(jitsiUrl, '_blank');
  }

  closeJitsiCall() {
    // Close Jitsi Meet window
  }

  updateCallUI(event, status) {
    // Update UI based on call status
  }
}
```

## Summary

The Zulip Calls Plugin v2.0 implements a production-ready call flow with:

1. **8 API Endpoints** for call management (including queue endpoints)
2. **8 WebSocket Events** for real-time communication (including new events)
3. **Database Tracking** with Call, CallEvent, and CallQueue models
4. **Enhanced Push Notifications** including missed call notifications
5. **Comprehensive Error Handling** for all scenarios including race conditions
6. **Status Updates** during active calls
7. **NEW v2.0**: Call queue system for busy users
8. **NEW v2.0**: Moderator privileges and participant roles
9. **NEW v2.0**: Missed call notifications with 90-second timeout
10. **NEW v2.0**: Network resilience with 60-second heartbeat timeout
11. **NEW v2.0**: Cursor-based pagination for call history
12. **NEW v2.0**: Race condition prevention with 5-second cooldown

This enhanced sequence ensures robust, scalable calling functionality with comprehensive edge case handling, proper state management, and enhanced user experience throughout the entire call lifecycle.



