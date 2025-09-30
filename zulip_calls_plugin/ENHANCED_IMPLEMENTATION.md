# Zulip Calls Plugin - Enhanced Jitsi Backend Implementation

This document describes the enhanced backend implementation for comprehensive Jitsi video/audio calling functionality in the Zulip Calls Plugin with **complete WebSocket integration**.

## Overview

The enhanced implementation provides:
- Complete call lifecycle management with real-time WebSocket events
- **NEW**: Call acknowledgment system (ringing status)
- **NEW**: Real-time status updates during active calls
- **NEW**: Full WebSocket integration using Zulip's event system
- Enhanced push notifications with FCM support
- Call history tracking with detailed events
- Automatic call cleanup and timeout handling
- Robust error handling and validation
- Security features and authentication

## Recent Updates (WebSocket Integration)

### ✅ **Complete Sequence Diagram Implementation**
The plugin now **100% matches** the provided sequence diagram with:
- All 5 required API endpoints implemented
- Real-time WebSocket events for live call status
- Complete call flow from initiation → acknowledgment → response → status updates → termination

## Key Changes Made

### 1. Enhanced Call Model (`models/calls.py`)

**New Features:**
- Updated call states: `calling`, `ringing`, `accepted`, `rejected`, `timeout`, `ended`, `missed`, `cancelled`
- Renamed fields for consistency: `initiator` → `sender`, `recipient` → `receiver`, `started_at` → `answered_at`
- Added `jitsi_room_id` field for better Jitsi integration
- Enhanced indexing for better performance
- New model methods: `duration`, `is_active()`, `can_be_answered()`
- Backward compatibility aliases for existing code

### 2. New API Endpoints (`views/calls.py`)

**Core Endpoints (Sequence Diagram Compliant):**
- `POST /api/v1/calls/initiate` - Quick call initiation with WebSocket events
- `POST /api/v1/calls/acknowledge` - **NEW**: Acknowledge call receipt (ringing status)
- `POST /api/v1/calls/respond` - Accept/reject calls with real-time events
- `POST /api/v1/calls/status` - **NEW**: Update call status during active calls
- `POST /api/v1/calls/end` - End active calls with notifications

**Enhanced Endpoints:**
- `POST /api/v1/calls/start` - Start a new call with full validation
- `POST /api/v1/calls/create` - Full call creation with database tracking
- `GET /api/v1/calls/history` - Enhanced call history with pagination
- `GET /api/v1/calls/active` - Get user's active calls
- `POST /api/v1/calls/end-all` - End all user's active calls

**WebSocket Integration:**
- **Real-time events**: `participant_ringing`, `call_accepted`, `call_rejected`, `call_ended`, `call_status_update`
- **Event system**: Uses Zulip's native `send_event_on_commit()` for reliable delivery
- **Comprehensive data**: Events include full call context and participant information

**Features:**
- Comprehensive validation and error handling
- Enhanced push notification integration (FCM + legacy)
- **NEW**: Real-time WebSocket event system using Zulip's event framework
- Transaction safety with atomic operations
- Detailed logging and event tracking

### 3. Call Cleanup Management (`management/commands/cleanup_calls.py`)

**Functionality:**
- Automatically timeout old calls (default: 5 minutes)
- Cleanup old ended call records (configurable)
- Detailed logging and reporting
- Configurable timeout periods

**Usage:**
```bash
# Basic cleanup (timeout calls older than 5 minutes)
python manage.py cleanup_calls

# Custom timeout period
python manage.py cleanup_calls --timeout-minutes=10

# Also cleanup old ended calls
python manage.py cleanup_calls --cleanup-old-calls --old-calls-days=30
```

### 4. Enhanced Configuration (`plugin_config.py`)

**New Settings:**
```python
# Jitsi Integration
JITSI_SERVER_URL = "https://meet.jit.si"
JITSI_MEETING_PREFIX = "zulip-call-"
JITSI_API_ENABLED = True

# Call Behavior
CALL_NOTIFICATION_TIMEOUT = 120  # 2 minutes
CALL_RING_TIMEOUT = 30          # 30 seconds
CALL_MAX_DURATION = 3600        # 1 hour
CALL_CLEANUP_INTERVAL = 300     # 5 minutes

# Push Notifications
CALL_PUSH_NOTIFICATION_ENABLED = True
CALL_PUSH_NOTIFICATION_SOUND = "call_ring.wav"

# Feature Flags
ENABLE_VIDEO_CALLS = True
ENABLE_AUDIO_CALLS = True
ENABLE_CALL_HISTORY = True
```

### 5. Enhanced Push Notifications

**Features:**
- Support for both Android and iOS
- Enhanced call notification payload
- Call response notifications
- Timeout handling
- Custom ringtone support

### 6. Real-time Event System

**Events:**
- `call_started` - When a call is initiated
- `call_accepted` - When call is accepted
- `call_rejected` - When call is rejected
- `call_ended` - When call ends

### 7. Database Migration (`migrations/0002_enhance_call_model.py`)

**Changes:**
- Field renames for consistency
- New indexes for better performance
- State updates
- Backward compatibility preservation

## API Documentation

### Start Call
```bash
POST /api/v1/calls/start
Content-Type: application/json

{
  "user_id": 123,
  "call_type": "video"  # or "audio"
}

Response:
{
  "result": "success",
  "call_id": "uuid-string",
  "jitsi_url": "https://meet.jit.si/zulip-call-uuid",
  "timeout_seconds": 120
}
```

### Respond to Call
```bash
POST /api/v1/calls/respond
Content-Type: application/json

{
  "call_id": "uuid-string",
  "response": "accept"  # or "reject"
}

Response:
{
  "result": "success",
  "status": "ok",
  "call_status": "accepted",
  "jitsi_url": "https://meet.jit.si/zulip-call-uuid"
}
```

### End Call
```bash
POST /api/v1/calls/end
Content-Type: application/json

{
  "call_id": "uuid-string"
}

Response:
{
  "result": "success",
  "status": "ok"
}
```

### Get Call History
```bash
GET /api/v1/calls/history?limit=50

Response:
{
  "result": "success",
  "calls": [
    {
      "call_id": "uuid-string",
      "user_id": 123,
      "user_name": "John Doe",
      "call_type": "video",
      "state": "ended",
      "is_outgoing": true,
      "created_at": "2024-01-01T12:00:00Z",
      "answered_at": "2024-01-01T12:00:05Z",
      "ended_at": "2024-01-01T12:30:00Z",
      "duration": 1795.0
    }
  ]
}
```

## Security Features

1. **Authentication Required** - All endpoints require authentication
2. **Realm Isolation** - Users can only call within their organization
3. **Authorization Checks** - Proper permission validation
4. **Rate Limiting Ready** - Designed to work with rate limiting
5. **Input Validation** - Comprehensive parameter validation
6. **SQL Injection Prevention** - Uses Django ORM safely

## Performance Optimizations

1. **Database Indexes** - Optimized for common query patterns
2. **Atomic Transactions** - Ensures data consistency
3. **Efficient Queries** - Minimizes database hits
4. **Caching Ready** - Designed to work with caching layers

## Monitoring and Logging

All operations are logged with appropriate levels:
- Info: Normal operations
- Warning: Potentially problematic situations
- Error: Failed operations with details

## Deployment Instructions

1. **Apply the migration:**
   ```bash
   python manage.py migrate zulip_calls_plugin
   ```

2. **Set up call cleanup cron job:**
   ```bash
   # Add to crontab
   */5 * * * * cd /path/to/zulip && python manage.py cleanup_calls
   ```

3. **Configure Jitsi settings** in your Django settings or environment

4. **Restart Zulip services:**
   ```bash
   supervisorctl restart all
   ```

## Testing

### Manual Testing
```bash
# Test starting a call
curl -X POST "https://your-zulip.com/api/v1/calls/start" \
  -H "Authorization: Basic $(echo -n 'email:api-key' | base64)" \
  -H "Content-Type: application/json" \
  -d '{"user_id": 123, "call_type": "video"}'

# Test call cleanup
python manage.py cleanup_calls --timeout-minutes=1
```

### Integration Testing
The plugin maintains backward compatibility with existing functionality while adding enhanced features.

## Troubleshooting

1. **Migration Issues:** Ensure all existing calls are in a consistent state before applying migrations
2. **Push Notification Issues:** Verify FCM/APNS configuration
3. **Jitsi Connection Issues:** Check JITSI_SERVER_URL configuration
4. **Performance Issues:** Monitor database query performance and add additional indexes if needed

## Future Enhancements

1. Group calling support
2. Call recording integration
3. Advanced analytics
4. WebRTC fallback options
5. Enhanced mobile app integration

This enhanced implementation provides a robust foundation for production-ready video/audio calling in Zulip with comprehensive features and proper error handling.