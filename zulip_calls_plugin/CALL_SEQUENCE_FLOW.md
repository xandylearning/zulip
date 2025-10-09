# Zulip Calls Plugin - Call Sequence Flow

## Overview

This document explains the complete call sequence flow in the Zulip Calls Plugin, from call initiation to termination, including all API calls, WebSocket events, and database operations.

## Call Flow Diagram

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
  |    call_status_update     |                          |
  |                           |                          |
  |-- 9. POST /end ----------|                          |
  |                           |                          |
  |<-- 10. WebSocket Event --|                          |
  |    call_ended             |                          |
```

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
4. Generate unique call ID (UUID)
5. Create Jitsi room URL
6. Create Call record in database
7. Create CallEvent record (type: "initiated")

**Response:**
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

### Phase 5: Call Termination

#### Step 9: End Call
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

**Server Actions:**
1. Validate user authentication
2. Find call by call_id
3. Verify user is participant in this call
4. Update call state to "ended"
5. Set ended_at timestamp
6. Create CallEvent record (type: "ended")
7. Send WebSocket events to both participants

**Response:**
```json
{
  "result": "success",
  "status": "ok",
  "message": "Call ended successfully",
  "call_id": "abc123-def456-ghi789"
}
```

#### Step 10: Send WebSocket Events to Both Participants
**WebSocket Event:**
```json
{
  "type": "call_event",
  "event_type": "call_ended",
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

**Participant Actions:**
- Receive WebSocket event
- Close Jitsi Meet window
- Update UI to show call ended
- Update call history

## Database State Changes

### Call Record States
```
calling → ringing → accepted → ended
   ↓         ↓         ↓
rejected   timeout   cancelled
```

### CallEvent Records Created
1. **initiated** - When call is created
2. **acknowledged** - When recipient acknowledges
3. **accepted/rejected** - When recipient responds
4. **status_update** - During active call
5. **ended** - When call is terminated

## Error Scenarios

### Call Timeout
If recipient doesn't respond within timeout period:
1. Server automatically updates call state to "timeout"
2. Creates CallEvent record (type: "timeout")
3. Sends WebSocket event to caller
4. Caller receives timeout notification

### Network Disconnection
If participant loses connection:
1. WebSocket connection drops
2. Other participant can still end call
3. Server maintains call state
4. Reconnection allows participant to rejoin

### Call Rejection
If recipient rejects call:
1. Call state changes to "rejected"
2. Caller receives rejection notification
3. No Jitsi Meet window opens
4. Call is marked as ended

## Push Notifications

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
  "timeout_seconds": 120
}
```

### Notification Actions
- Show incoming call UI
- Play ringtone
- Display caller information
- Provide accept/reject buttons
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

The Zulip Calls Plugin implements a complete call flow with:

1. **5 API Endpoints** for call management
2. **5 WebSocket Events** for real-time communication
3. **Database Tracking** with Call and CallEvent models
4. **Push Notifications** for mobile apps
5. **Error Handling** for all scenarios
6. **Status Updates** during active calls

This sequence ensures reliable, real-time calling functionality with proper state management and user feedback throughout the entire call lifecycle.
