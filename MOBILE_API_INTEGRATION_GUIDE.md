# Zulip Mobile API Integration Guide

This comprehensive guide covers everything you need to integrate your existing system with Zulip's chat functionality using the mobile API. This documentation is based on the official Zulip API and includes authentication, real-time events, messaging, and mobile-specific features.

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Core API Endpoints](#core-api-endpoints)
4. [Real-time Events](#real-time-events)
5. [Mobile-Specific Features](#mobile-specific-features)
6. [Push Notifications](#push-notifications)
7. [Error Handling](#error-handling)
8. [Rate Limiting](#rate-limiting)
9. [Client Libraries](#client-libraries)
10. [Integration Examples](#integration-examples)

## Overview

Zulip's REST API powers both the web and mobile applications, providing comprehensive access to all chat functionality. The API uses HTTP Basic Authentication with API keys and supports real-time events through long-polling.

### Base URL Structure
```
https://your-domain.zulipchat.com/api/v1/
```

### Key Features
- **Real-time messaging** with instant updates
- **End-to-end encrypted push notifications** (Zulip 11.0+)
- **Comprehensive user and channel management**
- **File uploads and attachments**
- **Message reactions and editing**
- **Presence and typing indicators**

## Authentication

### 1. API Key Authentication

Zulip uses API keys for authentication. Each user or bot has a unique API key that must be included in all API requests.

#### Getting an API Key

**For Production:**
```http
POST /api/v1/fetch_api_key
Content-Type: application/x-www-form-urlencoded

username=user@example.com&password=your_password
```

**Response:**
```json
{
  "api_key": "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5",
  "email": "user@example.com",
  "user_id": 123
}
```

**For Development:**
```http
POST /api/v1/dev_fetch_api_key
Content-Type: application/x-www-form-urlencoded

username=user@example.com
```

#### JWT Authentication (Alternative)

For server-to-server integration:
```http
POST /api/v1/jwt/fetch_api_key
Content-Type: application/x-www-form-urlencoded

token=your_jwt_token
```

JWT payload structure:
```json
{
  "email": "user@example.com"
}
```

### 2. HTTP Headers

All API requests must include proper authentication headers:

```http
Authorization: Basic base64(email:api_key)
Content-Type: application/json
User-Agent: YourApp/1.0.0
```

### 3. Server Settings

Check server compatibility and available authentication methods:

```http
GET /api/v1/server_settings
```

**Response:**
```json
{
  "authentication_methods": {
    "dev": false,
    "email": true,
    "github": true,
    "google": true,
    "ldap": false,
    "remoteuser": false,
    "saml": false
  },
  "realm_name": "Your Organization",
  "realm_uri": "https://your-domain.zulipchat.com",
  "realm_icon": "https://your-domain.zulipchat.com/static/images/realm/icon.png",
  "realm_description": "Your organization description",
  "push_notifications_enabled": true,
  "zulip_version": "8.0.0",
  "zulip_feature_level": 1
}
```

## Core API Endpoints

### Messages

#### Send a Message

```http
POST /api/v1/messages
Content-Type: application/x-www-form-urlencoded

type=stream&to=general&subject=Hello&content=Hello world!
```

**Parameters:**
- `type`: `"stream"` or `"private"`
- `to`: Stream name (for streams) or user email(s) (for private messages)
- `subject`: Topic/subject (required for stream messages)
- `content`: Message content

**Response:**
```json
{
  "id": 123,
  "msg": "",
  "result": "success"
}
```

#### Get Messages

```http
GET /api/v1/messages?anchor=0&num_before=50&num_after=50&narrow=[{"operator":"stream","operand":"general"}]
```

**Parameters:**
- `anchor`: Message ID to center around
- `num_before`: Number of messages before anchor
- `num_after`: Number of messages after anchor
- `narrow`: JSON array of filter operators

**Response:**
```json
{
  "anchor": 123,
  "found_anchor": true,
  "found_newest": false,
  "found_oldest": false,
  "history_limited": false,
  "messages": [
    {
      "id": 123,
      "sender_id": 456,
      "content": "Hello world!",
      "recipient_id": 789,
      "timestamp": 1640995200,
      "client": "website",
      "subject": "Hello",
      "topic_links": [],
      "is_me_message": false,
      "reactions": [],
      "submessages": [],
      "flags": ["read"],
      "sender_full_name": "John Doe",
      "sender_short_name": "john",
      "sender_email": "john@example.com",
      "sender_realm_str": "example.com",
      "display_recipient": "general",
      "type": "stream",
      "stream_id": 1,
      "avatar_url": "https://example.com/avatar.png"
    }
  ]
}
```

#### Edit a Message

```http
PATCH /api/v1/messages/{message_id}
Content-Type: application/x-www-form-urlencoded

content=Updated message content
```

#### Delete a Message

```http
DELETE /api/v1/messages/{message_id}
```

### Users

#### Get Users

```http
GET /api/v1/users
```

**Response:**
```json
{
  "members": [
    {
      "user_id": 123,
      "email": "user@example.com",
      "full_name": "John Doe",
      "is_bot": false,
      "is_active": true,
      "avatar_url": "https://example.com/avatar.png",
      "date_joined": "2023-01-01T00:00:00Z",
      "timezone": "UTC"
    }
  ]
}
```

#### Get Own User

```http
GET /api/v1/users/me
```

#### Update User Status

```http
POST /api/v1/users/me/status
Content-Type: application/json

{
  "status_text": "Working on a project",
  "emoji_name": "hammer",
  "emoji_code": "1f528"
}
```

### Channels (Streams)

#### Get Channels

```http
GET /api/v1/streams
```

#### Subscribe to Channel

```http
POST /api/v1/users/me/subscriptions
Content-Type: application/json

{
  "subscriptions": [
    {
      "name": "general",
      "description": "General discussion"
    }
  ]
}
```

#### Create Channel

```http
POST /api/v1/streams
Content-Type: application/json

{
  "name": "new-channel",
  "description": "Channel description",
  "invite_only": false
}
```

## Real-time Events

Zulip's real-time events API allows you to receive live updates about messages, user presence, and other changes.

### 1. Register Event Queue

```http
POST /api/v1/register
Content-Type: application/json

{
  "event_types": ["message", "presence", "typing"],
  "fetch_event_types": ["message", "presence", "typing"],
  "narrow": [["stream", "general"]],
  "all_public_streams": false,
  "include_subscribers": false
}
```

**Response:**
```json
{
  "queue_id": "1511901550:2",
  "last_event_id": -1,
  "result": "success"
}
```

### 2. Get Events

```http
GET /api/v1/events?queue_id=1511901550:2&last_event_id=-1
```

**Response:**
```json
{
  "events": [
    {
      "id": 0,
      "type": "message",
      "message": {
        "id": 123,
        "sender_id": 456,
        "content": "New message!",
        "recipient_id": 789,
        "timestamp": 1640995200,
        "client": "website",
        "subject": "Hello",
        "type": "stream",
        "stream_id": 1,
        "display_recipient": "general"
      }
    }
  ],
  "result": "success"
}
```

### 3. Event Types

Common event types include:
- `message`: New messages
- `presence`: User presence changes
- `typing`: Typing indicators
- `reaction`: Emoji reactions
- `update_message`: Message edits
- `delete_message`: Message deletions
- `subscription`: Channel subscription changes
- `user`: User profile changes

## Mobile-Specific Features

### 1. Push Device Registration

Register a device for push notifications:

```http
POST /api/v1/users/me/apns_device_token
Content-Type: application/json

{
  "token": "your_apns_token",
  "appid": "com.yourcompany.yourapp"
}
```

For FCM (Android):
```http
POST /api/v1/users/me/fcm_registration_token
Content-Type: application/json

{
  "token": "your_fcm_token"
}
```

### 2. End-to-End Encrypted Push Notifications

For enhanced security (Zulip 11.0+):

```http
POST /api/v1/users/me/push_devices
Content-Type: application/json

{
  "token": "your_device_token",
  "token_kind": 1,
  "ios_app_id": "com.yourcompany.yourapp"
}
```

### 3. Test Push Notifications

```http
POST /api/v1/users/me/test_notification
Content-Type: application/json

{
  "token": "your_device_token"
}
```

## Push Notifications

### Notification Payload Format

Zulip sends encrypted JSON payloads for push notifications:

#### Channel Message
```json
{
  "channel_id": 10,
  "channel_name": "general",
  "content": "Hello world!",
  "message_id": 45,
  "realm_name": "Your Organization",
  "realm_url": "https://your-domain.zulipchat.com",
  "recipient_type": "channel",
  "sender_avatar_url": "https://example.com/avatar.png",
  "sender_full_name": "John Doe",
  "sender_id": 6,
  "time": 1754385395,
  "topic": "Hello",
  "type": "message",
  "user_id": 10
}
```

#### Direct Message
```json
{
  "content": "Private message",
  "message_id": 46,
  "realm_name": "Your Organization",
  "realm_url": "https://your-domain.zulipchat.com",
  "recipient_type": "direct",
  "sender_avatar_url": "https://example.com/avatar.png",
  "sender_full_name": "John Doe",
  "sender_id": 6,
  "time": 1754385290,
  "type": "message",
  "user_id": 10
}
```

## Error Handling

### Standard Error Response Format

```json
{
  "result": "error",
  "msg": "Invalid API key",
  "code": "UNAUTHORIZED"
}
```

### Common Error Codes

- `UNAUTHORIZED`: Invalid API key
- `BAD_REQUEST`: Invalid request parameters
- `REALM_DEACTIVATED`: Organization is deactivated
- `USER_DEACTIVATED`: User account is deactivated
- `RATE_LIMITED`: Too many requests

### HTTP Status Codes

- `200`: Success
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `429`: Too Many Requests
- `500`: Internal Server Error

## Rate Limiting

Zulip implements rate limiting to prevent abuse. Check response headers:

```http
X-RateLimit-Remaining: 195
X-RateLimit-Limit: 200
X-RateLimit-Reset: 1640995200
```

**Default Limits:**
- 200 API requests per minute per user
- Lower limits for authentication attempts

## Client Libraries

### Python

```python
import zulip

# Initialize client
client = zulip.Client(
    email="user@example.com",
    api_key="your_api_key",
    site="https://your-domain.zulipchat.com"
)

# Send a message
result = client.send_message({
    "type": "stream",
    "to": "general",
    "subject": "Hello",
    "content": "Hello from Python!"
})

# Get messages
messages = client.get_messages({
    "anchor": 0,
    "num_before": 50,
    "num_after": 50
})
```

### JavaScript/Node.js

```javascript
const zulip = require('zulip-js');

const config = {
    username: 'user@example.com',
    apiKey: 'your_api_key',
    realm: 'https://your-domain.zulipchat.com'
};

zulip(config).then((client) => {
    // Send a message
    return client.messages.send({
        type: 'stream',
        to: 'general',
        subject: 'Hello',
        content: 'Hello from JavaScript!'
    });
});
```

## Integration Examples

### 1. Basic Chat Integration

```python
import zulip
import time

class ZulipChatIntegration:
    def __init__(self, email, api_key, site):
        self.client = zulip.Client(
            email=email,
            api_key=api_key,
            site=site
        )
    
    def send_message(self, stream, subject, content):
        """Send a message to a stream"""
        result = self.client.send_message({
            "type": "stream",
            "to": stream,
            "subject": subject,
            "content": content
        })
        return result
    
    def get_recent_messages(self, stream, limit=50):
        """Get recent messages from a stream"""
        messages = self.client.get_messages({
            "anchor": 0,
            "num_before": 0,
            "num_after": limit,
            "narrow": [["stream", stream]]
        })
        return messages["messages"]
    
    def listen_for_messages(self, callback):
        """Listen for new messages in real-time"""
        def handle_message(event):
            if event["type"] == "message":
                callback(event["message"])
        
        self.client.call_on_each_event(handle_message)
```

### 2. Real-time Event Processing

```python
def process_events():
    client = zulip.Client(config_file="~/.zuliprc")
    
    def handle_event(event):
        event_type = event["type"]
        
        if event_type == "message":
            message = event["message"]
            print(f"New message: {message['content']}")
            
        elif event_type == "presence":
            presence = event["presence"]
            print(f"User presence: {presence}")
            
        elif event_type == "typing":
            typing = event["typing"]
            print(f"User typing: {typing}")
    
    # Listen for all events
    client.call_on_each_event(handle_event)
```

### 3. Mobile App Integration

```javascript
class ZulipMobileClient {
    constructor(apiKey, site) {
        this.apiKey = apiKey;
        this.site = site;
        this.queueId = null;
        this.lastEventId = -1;
    }
    
    async authenticate(email, password) {
        const response = await fetch(`${this.site}/api/v1/fetch_api_key`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `username=${email}&password=${password}`
        });
        
        const data = await response.json();
        if (data.result === 'success') {
            this.apiKey = data.api_key;
            return data;
        }
        throw new Error(data.msg);
    }
    
    async registerEventQueue() {
        const response = await fetch(`${this.site}/api/v1/register`, {
            method: 'POST',
            headers: {
                'Authorization': `Basic ${btoa(`${this.email}:${this.apiKey}`)}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_types: ['message', 'presence', 'typing'],
                fetch_event_types: ['message', 'presence', 'typing']
            })
        });
        
        const data = await response.json();
        if (data.result === 'success') {
            this.queueId = data.queue_id;
            this.lastEventId = data.last_event_id;
        }
        return data;
    }
    
    async getEvents() {
        const response = await fetch(
            `${this.site}/api/v1/events?queue_id=${this.queueId}&last_event_id=${this.lastEventId}`,
            {
                headers: {
                    'Authorization': `Basic ${btoa(`${this.email}:${this.apiKey}`)}`,
                }
            }
        );
        
        const data = await response.json();
        if (data.result === 'success') {
            this.lastEventId = data.last_event_id;
            return data.events;
        }
        return [];
    }
    
    async sendMessage(stream, subject, content) {
        const response = await fetch(`${this.site}/api/v1/messages`, {
            method: 'POST',
            headers: {
                'Authorization': `Basic ${btoa(`${this.email}:${this.apiKey}`)}`,
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: `type=stream&to=${stream}&subject=${subject}&content=${content}`
        });
        
        return await response.json();
    }
}
```

## Best Practices

### 1. Authentication
- Store API keys securely
- Use environment variables for sensitive data
- Implement proper error handling for authentication failures

### 2. Real-time Events
- Use long-polling for real-time updates
- Implement exponential backoff for reconnection
- Handle network interruptions gracefully

### 3. Rate Limiting
- Monitor rate limit headers
- Implement request queuing if needed
- Cache frequently accessed data

### 4. Error Handling
- Always check response status codes
- Implement retry logic for transient failures
- Log errors for debugging

### 5. Security
- Use HTTPS for all API calls
- Validate all input data
- Implement proper session management

## Conclusion

This guide provides comprehensive coverage of Zulip's mobile API integration. The API is powerful and flexible, supporting everything from simple message sending to complex real-time event processing. With proper authentication, error handling, and following best practices, you can build robust integrations that leverage Zulip's full chat functionality.

For additional resources:
- [Official Zulip API Documentation](https://zulip.com/api/)
- [Python Client Library](https://github.com/zulip/python-zulip-api)
- [JavaScript Client Library](https://github.com/zulip/zulip-js)
- [Zulip Development Community](https://zulip.com/development-community/)

---

*This documentation is based on Zulip's official API and is regularly updated to reflect the latest features and best practices.*
