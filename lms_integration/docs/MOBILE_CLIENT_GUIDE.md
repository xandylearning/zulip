# Mobile Client Integration Guide - JWT Authentication

Complete guide for using Zulip mobile client with TestPress JWT authentication and all chat functionality.

## Table of Contents

1. [Authentication Flow](#authentication-flow)
2. [Using the API Key](#using-the-api-key)
3. [Sending Messages](#sending-messages)
4. [Receiving Messages](#receiving-messages)
5. [Real-time Events](#real-time-events)
6. [Complete Mobile Client Example](#complete-mobile-client-example)
7. [All Available Features](#all-available-features)

---

## Authentication Flow

### Step 1: Get API Key with JWT Token

**Endpoint:** `POST /api/v1/lms/auth/jwt/`

**Request:**
```json
{
    "token": "your-testpress-jwt-token",
    "include_profile": false
}
```

**Response:**
```json
{
    "result": "success",
    "api_key": "a0b1c2d3e4f5a6b7c8d9e0f1a2b3c4d5",
    "email": "muhammed.ajmal@xandylearning.com",
    "user_id": 55,
    "full_name": "Muhammed Ajmal"
}
```

**Example (JavaScript/React Native):**
```javascript
async function authenticateWithJWT(jwtToken) {
    const response = await fetch('http://localhost:9991/api/v1/lms/auth/jwt/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            token: jwtToken,
            include_profile: false
        })
    });
    
    const data = await response.json();
    if (data.result === 'success') {
        // Store API key securely
        await AsyncStorage.setItem('api_key', data.api_key);
        await AsyncStorage.setItem('email', data.email);
        await AsyncStorage.setItem('user_id', data.user_id.toString());
        return data;
    }
    throw new Error(data.msg || 'Authentication failed');
}
```

---

## Using the API Key

All subsequent API requests use **HTTP Basic Authentication** with the email and API key.

**Authentication Header:**
```javascript
const email = await AsyncStorage.getItem('email');
const apiKey = await AsyncStorage.getItem('api_key');
const authString = btoa(`${email}:${apiKey}`); // Base64 encode

headers: {
    'Authorization': `Basic ${authString}`,
    'Content-Type': 'application/json'
}
```

---

## Sending Messages

### 1. Send Message to Stream/Channel

**Endpoint:** `POST /api/v1/messages`

**Request:**
```javascript
async function sendStreamMessage(streamName, topic, content) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const formData = new URLSearchParams();
    formData.append('type', 'stream');
    formData.append('to', streamName);
    formData.append('topic', topic);
    formData.append('content', content);
    
    const response = await fetch('http://localhost:9991/api/v1/messages', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
    });
    
    return await response.json();
}

// Usage
await sendStreamMessage('general', 'Hello', 'Hello everyone!');
```

**Response:**
```json
{
    "id": 123,
    "result": "success",
    "msg": ""
}
```

### 2. Send Private/Direct Message

**Request:**
```javascript
async function sendDirectMessage(recipientEmail, content) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const formData = new URLSearchParams();
    formData.append('type', 'private');
    formData.append('to', recipientEmail); // Can be comma-separated for group PMs
    formData.append('content', content);
    
    const response = await fetch('http://localhost:9991/api/v1/messages', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: formData.toString()
    });
    
    return await response.json();
}

// Usage
await sendDirectMessage('user@example.com', 'Hi there!');
```

### 3. Send Message with File Attachment

**Request:**
```javascript
async function sendMessageWithFile(streamName, topic, content, fileUri) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    // First, upload the file
    const formData = new FormData();
    formData.append('file', {
        uri: fileUri,
        type: 'image/jpeg', // or appropriate MIME type
        name: 'photo.jpg'
    });
    
    const uploadResponse = await fetch('http://localhost:9991/api/v1/user_uploads', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
        },
        body: formData
    });
    
    const uploadData = await uploadResponse.json();
    const fileUrl = uploadData.uri;
    
    // Then send message with file
    const messageFormData = new URLSearchParams();
    messageFormData.append('type', 'stream');
    messageFormData.append('to', streamName);
    messageFormData.append('topic', topic);
    messageFormData.append('content', `${content}\n[${uploadData.name}](${fileUrl})`);
    
    const response = await fetch('http://localhost:9991/api/v1/messages', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
            'Content-Type': 'application/x-www-form-urlencoded',
        },
        body: messageFormData.toString()
    });
    
    return await response.json();
}
```

---

## Receiving Messages

### 1. Get Messages from Stream

**Endpoint:** `GET /api/v1/messages`

**Request:**
```javascript
async function getStreamMessages(streamName, numMessages = 50) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const narrow = JSON.stringify([{
        operator: 'stream',
        operand: streamName
    }]);
    
    const url = `http://localhost:9991/api/v1/messages?anchor=0&num_before=${numMessages}&num_after=0&narrow=${encodeURIComponent(narrow)}`;
    
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': `Basic ${authString}`,
        }
    });
    
    return await response.json();
}

// Usage
const messages = await getStreamMessages('general', 50);
console.log(messages.messages); // Array of message objects
```

**Response:**
```json
{
    "result": "success",
    "anchor": 0,
    "found_anchor": true,
    "found_newest": false,
    "found_oldest": false,
    "messages": [
        {
            "id": 123,
            "sender_id": 55,
            "content": "Hello everyone!",
            "recipient_id": 1,
            "timestamp": 1640995200,
            "subject": "Hello",
            "sender_full_name": "Muhammed Ajmal",
            "sender_email": "muhammed.ajmal@xandylearning.com",
            "display_recipient": "general",
            "type": "stream",
            "stream_id": 1,
            "reactions": [],
            "flags": ["read"]
        }
    ]
}
```

### 2. Get Private Messages

**Request:**
```javascript
async function getDirectMessages(otherUserEmail, numMessages = 50) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const narrow = JSON.stringify([{
        operator: 'pm-with',
        operand: otherUserEmail
    }]);
    
    const url = `http://localhost:9991/api/v1/messages?anchor=0&num_before=${numMessages}&num_after=0&narrow=${encodeURIComponent(narrow)}`;
    
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': `Basic ${authString}`,
        }
    });
    
    return await response.json();
}
```

### 3. Get Single Message

**Endpoint:** `GET /api/v1/messages/{message_id}`

**Request:**
```javascript
async function getMessage(messageId) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const response = await fetch(`http://localhost:9991/api/v1/messages/${messageId}`, {
        method: 'GET',
        headers: {
            'Authorization': `Basic ${authString}`,
        }
    });
    
    return await response.json();
}
```

---

## Real-time Events

### 1. Register Event Queue

**Endpoint:** `POST /api/v1/register`

**Request:**
```javascript
async function registerEventQueue() {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const response = await fetch('http://localhost:9991/api/v1/register', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            event_types: ['message', 'presence', 'typing', 'reaction', 'update_message'],
            fetch_event_types: ['message', 'presence', 'typing', 'reaction', 'update_message'],
            all_public_streams: true,
            include_subscribers: false
        })
    });
    
    const data = await response.json();
    if (data.result === 'success') {
        await AsyncStorage.setItem('queue_id', data.queue_id);
        await AsyncStorage.setItem('last_event_id', data.last_event_id.toString());
    }
    return data;
}
```

**Response:**
```json
{
    "result": "success",
    "queue_id": "1511901550:2",
    "last_event_id": -1,
    "max_message_id": 123
}
```

### 2. Get Events (Long Polling)

**Endpoint:** `GET /api/v1/events`

**Request:**
```javascript
async function getEvents() {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const queueId = await AsyncStorage.getItem('queue_id');
    const lastEventId = await AsyncStorage.getItem('last_event_id');
    const authString = btoa(`${email}:${apiKey}`);
    
    const url = `http://localhost:9991/api/v1/events?queue_id=${queueId}&last_event_id=${lastEventId}`;
    
    const response = await fetch(url, {
        method: 'GET',
        headers: {
            'Authorization': `Basic ${authString}`,
        }
    });
    
    const data = await response.json();
    if (data.result === 'success') {
        await AsyncStorage.setItem('last_event_id', data.last_event_id.toString());
        return data.events; // Array of event objects
    }
    return [];
}

// Usage in a loop for real-time updates
async function startEventPolling(callback) {
    await registerEventQueue();
    
    while (true) {
        try {
            const events = await getEvents();
            events.forEach(event => {
                callback(event); // Handle each event
            });
        } catch (error) {
            console.error('Event polling error:', error);
            await new Promise(resolve => setTimeout(resolve, 5000)); // Wait 5s before retry
        }
    }
}

// Handle events
startEventPolling((event) => {
    switch (event.type) {
        case 'message':
            console.log('New message:', event.message);
            break;
        case 'presence':
            console.log('User presence:', event.presence);
            break;
        case 'typing':
            console.log('User typing:', event);
            break;
        case 'reaction':
            console.log('Reaction added:', event);
            break;
    }
});
```

**Event Types:**
- `message` - New message received
- `update_message` - Message edited
- `delete_message` - Message deleted
- `presence` - User online/offline status
- `typing` - User typing indicator
- `reaction` - Reaction added/removed
- `subscription` - Stream subscription changed
- `user_status` - User status updated

---

## Complete Mobile Client Example

```javascript
class ZulipMobileClient {
    constructor(baseUrl) {
        this.baseUrl = baseUrl;
        this.email = null;
        this.apiKey = null;
        this.queueId = null;
        this.lastEventId = -1;
    }
    
    // Step 1: Authenticate with JWT
    async authenticate(jwtToken) {
        const response = await fetch(`${this.baseUrl}/api/v1/lms/auth/jwt/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ token: jwtToken })
        });
        
        const data = await response.json();
        if (data.result === 'success') {
            this.email = data.email;
            this.apiKey = data.api_key;
            await AsyncStorage.setItem('zulip_email', data.email);
            await AsyncStorage.setItem('zulip_api_key', data.api_key);
            return data;
        }
        throw new Error(data.msg || 'Authentication failed');
    }
    
    // Get auth header
    getAuthHeader() {
        return `Basic ${btoa(`${this.email}:${this.apiKey}`)}`;
    }
    
    // Step 2: Register for events
    async registerEvents() {
        const response = await fetch(`${this.baseUrl}/api/v1/register`, {
            method: 'POST',
            headers: {
                'Authorization': this.getAuthHeader(),
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                event_types: ['message', 'presence', 'typing', 'reaction'],
                fetch_event_types: ['message', 'presence', 'typing', 'reaction'],
                all_public_streams: true
            })
        });
        
        const data = await response.json();
        if (data.result === 'success') {
            this.queueId = data.queue_id;
            this.lastEventId = data.last_event_id;
        }
        return data;
    }
    
    // Step 3: Send message to stream
    async sendStreamMessage(streamName, topic, content) {
        const formData = new URLSearchParams();
        formData.append('type', 'stream');
        formData.append('to', streamName);
        formData.append('topic', topic);
        formData.append('content', content);
        
        const response = await fetch(`${this.baseUrl}/api/v1/messages`, {
            method: 'POST',
            headers: {
                'Authorization': this.getAuthHeader(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData.toString()
        });
        
        return await response.json();
    }
    
    // Step 4: Send direct message
    async sendDirectMessage(recipientEmail, content) {
        const formData = new URLSearchParams();
        formData.append('type', 'private');
        formData.append('to', recipientEmail);
        formData.append('content', content);
        
        const response = await fetch(`${this.baseUrl}/api/v1/messages`, {
            method: 'POST',
            headers: {
                'Authorization': this.getAuthHeader(),
                'Content-Type': 'application/x-www-form-urlencoded',
            },
            body: formData.toString()
        });
        
        return await response.json();
    }
    
    // Step 5: Get messages
    async getMessages(narrow = [], numBefore = 50, numAfter = 0) {
        const narrowStr = JSON.stringify(narrow);
        const url = `${this.baseUrl}/api/v1/messages?anchor=0&num_before=${numBefore}&num_after=${numAfter}&narrow=${encodeURIComponent(narrowStr)}`;
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': this.getAuthHeader(),
            }
        });
        
        return await response.json();
    }
    
    // Step 6: Get real-time events
    async getEvents() {
        const url = `${this.baseUrl}/api/v1/events?queue_id=${this.queueId}&last_event_id=${this.lastEventId}`;
        
        const response = await fetch(url, {
            method: 'GET',
            headers: {
                'Authorization': this.getAuthHeader(),
            }
        });
        
        const data = await response.json();
        if (data.result === 'success') {
            this.lastEventId = data.last_event_id;
            return data.events;
        }
        return [];
    }
    
    // Step 7: Start real-time polling
    async startEventPolling(onEvent) {
        await this.registerEvents();
        
        const poll = async () => {
            try {
                const events = await this.getEvents();
                events.forEach(event => onEvent(event));
            } catch (error) {
                console.error('Event polling error:', error);
            }
            setTimeout(poll, 1000); // Poll every second
        };
        
        poll();
    }
}

// Usage Example
const client = new ZulipMobileClient('http://localhost:9991');

// 1. Authenticate
await client.authenticate('your-jwt-token');

// 2. Send a message
await client.sendStreamMessage('general', 'Hello', 'Hello from mobile!');

// 3. Get messages
const messages = await client.getMessages([
    { operator: 'stream', operand: 'general' }
]);

// 4. Start receiving real-time events
client.startEventPolling((event) => {
    if (event.type === 'message') {
        console.log('New message:', event.message);
    }
});
```

---

## All Available Features

### Messages
- ✅ Send message to stream
- ✅ Send direct/private message
- ✅ Edit message (`PATCH /api/v1/messages/{id}`)
- ✅ Delete message (`DELETE /api/v1/messages/{id}`)
- ✅ Get messages with filters
- ✅ Add reaction (`POST /api/v1/messages/{id}/reactions`)
- ✅ Remove reaction (`DELETE /api/v1/messages/{id}/reactions`)
- ✅ Mark as read (`POST /api/v1/messages/flags`)

### Users
- ✅ Get all users (`GET /api/v1/users`)
- ✅ Get own profile (`GET /api/v1/users/me`)
- ✅ Update status (`POST /api/v1/users/me/status`)
- ✅ Get user presence (`GET /api/v1/users/{id}/presence`)

### Streams/Channels
- ✅ Get all streams (`GET /api/v1/streams`)
- ✅ Subscribe to stream (`POST /api/v1/users/me/subscriptions`)
- ✅ Unsubscribe from stream (`DELETE /api/v1/users/me/subscriptions`)
- ✅ Create stream (`POST /api/v1/streams`)
- ✅ Update stream (`PATCH /api/v1/streams/{id}`)

### Real-time
- ✅ Register event queue
- ✅ Get events (long polling)
- ✅ Typing indicators (`POST /api/v1/typing`)
- ✅ Presence updates

### Files
- ✅ Upload file (`POST /api/v1/user_uploads`)
- ✅ Get file URL

### Other Features
- ✅ Search messages
- ✅ Scheduled messages
- ✅ Drafts
- ✅ User groups
- ✅ Notifications

### Push Notifications (E2EE)
- ✅ Register device for E2EE push notifications
- ✅ Receive encrypted push notifications
- ✅ Test push notifications

---

## E2EE Push Notification Device Registration

Zulip 11.0+ supports **End-to-End Encrypted (E2EE) push notifications** for mobile devices. This ensures that notification content and metadata are encrypted and not visible to intermediaries.

### Overview

E2EE push notifications work by:
1. **Client generates encryption keys** (public/private key pair)
2. **Client encrypts device registration data** using bouncer's public key
3. **Server stores client's public key** for encrypting future notifications
4. **All push notifications are encrypted** before sending to push service (FCM/APNs)
5. **Client decrypts notifications** using its private key

### Step 1: Generate Encryption Keys

**For React Native / JavaScript:**
```javascript
// Using tweetnacl library for encryption
import nacl from 'tweetnacl';
import { encodeBase64, decodeBase64 } from 'tweetnacl-util';

// Generate key pair for push notifications
const pushKeyPair = nacl.box.keyPair();
const pushPublicKey = encodeBase64(pushKeyPair.publicKey);
const pushPrivateKey = encodeBase64(pushKeyPair.secretKey);

// Store private key securely (Keychain/Keystore)
await AsyncStorage.setItem('push_private_key', pushPrivateKey);
```

**For Flutter / Dart:**
```dart
import 'package:pointycastle/export.dart';
import 'dart:convert';
import 'package:convert/convert.dart';

// Generate key pair
final keyPair = generateKeyPair();
final pushPublicKey = base64Encode(keyPair.publicKey);
final pushPrivateKey = base64Encode(keyPair.privateKey);

// Store securely
await secureStorage.write(key: 'push_private_key', value: pushPrivateKey);
```

### Step 2: Get Bouncer Public Key

The bouncer public key is provided by the server. You need to get it from the server configuration:

```javascript
// Get server settings to check if E2EE is available
async function getServerSettings() {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const response = await fetch('http://localhost:9991/api/v1/server_settings', {
        method: 'GET',
        headers: {
            'Authorization': `Basic ${authString}`,
        }
    });
    
    return await response.json();
}
```

### Step 3: Prepare Registration Data

```javascript
// Prepare push registration data
function preparePushRegistration(deviceToken, tokenKind, iosAppId = null) {
    const timestamp = Math.floor(Date.now() / 1000);
    
    const registrationData = {
        token: deviceToken,           // FCM token or APNs token
        token_kind: tokenKind,        // "fcm" or "apns"
        ios_app_id: iosAppId,         // iOS app ID (null for Android)
        timestamp: timestamp
    };
    
    return JSON.stringify(registrationData);
}
```

### Step 4: Encrypt Registration Data

```javascript
// Encrypt registration data using bouncer's public key
function encryptPushRegistration(registrationDataJson, bouncerPublicKey) {
    // Decode bouncer's public key
    const bouncerKey = decodeBase64(bouncerPublicKey);
    
    // Generate ephemeral key pair for this encryption
    const ephemeralKeyPair = nacl.box.keyPair();
    
    // Encrypt the data
    const messageBytes = nacl.util.decodeUTF8(registrationDataJson);
    const nonce = nacl.randomBytes(24);
    const encrypted = nacl.box(
        messageBytes,
        nonce,
        bouncerKey,
        ephemeralKeyPair.secretKey
    );
    
    // Combine ephemeral public key + nonce + encrypted data
    const combined = new Uint8Array(
        ephemeralKeyPair.publicKey.length + nonce.length + encrypted.length
    );
    combined.set(ephemeralKeyPair.publicKey, 0);
    combined.set(nonce, ephemeralKeyPair.publicKey.length);
    combined.set(encrypted, ephemeralKeyPair.publicKey.length + nonce.length);
    
    return encodeBase64(combined);
}
```

### Step 5: Register Device

**Endpoint:** `POST /api/v1/mobile_push/register`

```javascript
async function registerE2EEDevice(deviceToken, tokenKind, iosAppId = null) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const pushPublicKey = await AsyncStorage.getItem('push_public_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    // Get bouncer public key (you need to get this from server config)
    const bouncerPublicKey = await getBouncerPublicKey(); // Implement this
    
    // Prepare and encrypt registration data
    const registrationData = preparePushRegistration(deviceToken, tokenKind, iosAppId);
    const encryptedRegistration = encryptPushRegistration(registrationData, bouncerPublicKey);
    
    // Generate unique push account ID (persistent per device)
    const pushAccountId = await getOrCreatePushAccountId();
    
    const response = await fetch('http://localhost:9991/api/v1/mobile_push/register', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            token_kind: tokenKind,                    // "fcm" or "apns"
            push_account_id: pushAccountId,           // Unique device ID
            push_public_key: pushPublicKey,            // Client's public key (base64)
            bouncer_public_key: bouncerPublicKey,     // Bouncer's public key (base64)
            encrypted_push_registration: encryptedRegistration  // Encrypted registration data
        })
    });
    
    return await response.json();
}

// Usage
// For Android (FCM)
await registerE2EEDevice(fcmToken, 'fcm');

// For iOS (APNs)
await registerE2EEDevice(apnsToken, 'apns', 'com.yourapp.bundleid');
```

### Step 6: Get Push Account ID

```javascript
// Generate or retrieve persistent push account ID
async function getOrCreatePushAccountId() {
    let accountId = await AsyncStorage.getItem('push_account_id');
    if (!accountId) {
        // Generate a unique ID (you can use UUID or device ID)
        accountId = generateUniqueId(); // Implement this
        await AsyncStorage.setItem('push_account_id', accountId);
    }
    return parseInt(accountId);
}
```

### Step 7: Receive and Decrypt Push Notifications

When you receive a push notification, decrypt it using your private key:

```javascript
// Decrypt push notification payload
function decryptPushNotification(encryptedPayload, pushPrivateKey) {
    const privateKey = decodeBase64(pushPrivateKey);
    
    // Decode encrypted payload
    const encryptedBytes = decodeBase64(encryptedPayload);
    
    // Extract ephemeral public key, nonce, and encrypted data
    const ephemeralPublicKey = encryptedBytes.slice(0, 32);
    const nonce = encryptedBytes.slice(32, 56);
    const encrypted = encryptedBytes.slice(56);
    
    // Decrypt
    const decrypted = nacl.box.open(
        encrypted,
        nonce,
        ephemeralPublicKey,
        privateKey
    );
    
    if (!decrypted) {
        throw new Error('Failed to decrypt push notification');
    }
    
    return JSON.parse(nacl.util.encodeUTF8(decrypted));
}

// Handle incoming push notification (React Native example)
messaging().onMessage(async (remoteMessage) => {
    const encryptedPayload = remoteMessage.data.encrypted_payload;
    const pushPrivateKey = await AsyncStorage.getItem('push_private_key');
    
    try {
        const decrypted = decryptPushNotification(encryptedPayload, pushPrivateKey);
        console.log('Decrypted notification:', decrypted);
        
        // Handle the notification
        // decrypted.type can be: "message", "remove", "test"
        // decrypted contains message content, sender info, etc.
    } catch (error) {
        console.error('Failed to decrypt notification:', error);
    }
});
```

### Complete E2EE Registration Example

```javascript
class E2EEPushNotificationManager {
    constructor() {
        this.pushPublicKey = null;
        this.pushPrivateKey = null;
        this.bouncerPublicKey = null;
    }
    
    // Initialize: Generate keys and get bouncer key
    async initialize() {
        // Generate key pair
        const keyPair = nacl.box.keyPair();
        this.pushPublicKey = encodeBase64(keyPair.publicKey);
        this.pushPrivateKey = encodeBase64(keyPair.secretKey);
        
        // Store securely
        await AsyncStorage.setItem('push_public_key', this.pushPublicKey);
        await AsyncStorage.setItem('push_private_key', this.pushPrivateKey);
        
        // Get bouncer public key from server
        this.bouncerPublicKey = await this.getBouncerPublicKey();
    }
    
    // Register device for E2EE push notifications
    async registerDevice(deviceToken, tokenKind, iosAppId = null) {
        const email = await AsyncStorage.getItem('email');
        const apiKey = await AsyncStorage.getItem('api_key');
        const authString = btoa(`${email}:${apiKey}`);
        
        // Prepare registration data
        const timestamp = Math.floor(Date.now() / 1000);
        const registrationData = {
            token: deviceToken,
            token_kind: tokenKind,
            ios_app_id: iosAppId,
            timestamp: timestamp
        };
        
        // Encrypt registration data
        const encrypted = this.encryptForBouncer(
            JSON.stringify(registrationData),
            this.bouncerPublicKey
        );
        
        // Get or create push account ID
        const pushAccountId = await this.getPushAccountId();
        
        // Register with server
        const response = await fetch('http://localhost:9991/api/v1/mobile_push/register', {
            method: 'POST',
            headers: {
                'Authorization': `Basic ${authString}`,
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                token_kind: tokenKind,
                push_account_id: pushAccountId,
                push_public_key: this.pushPublicKey,
                bouncer_public_key: this.bouncerPublicKey,
                encrypted_push_registration: encrypted
            })
        });
        
        return await response.json();
    }
    
    // Decrypt incoming push notification
    decryptNotification(encryptedPayload) {
        const encryptedBytes = decodeBase64(encryptedPayload);
        const ephemeralPublicKey = encryptedBytes.slice(0, 32);
        const nonce = encryptedBytes.slice(32, 56);
        const encrypted = encryptedBytes.slice(56);
        
        const privateKey = decodeBase64(this.pushPrivateKey);
        const decrypted = nacl.box.open(
            encrypted,
            nonce,
            ephemeralPublicKey,
            privateKey
        );
        
        if (!decrypted) {
            throw new Error('Decryption failed');
        }
        
        return JSON.parse(nacl.util.encodeUTF8(decrypted));
    }
    
    // Helper methods
    encryptForBouncer(data, bouncerPublicKey) {
        const bouncerKey = decodeBase64(bouncerPublicKey);
        const ephemeralKeyPair = nacl.box.keyPair();
        const messageBytes = nacl.util.decodeUTF8(data);
        const nonce = nacl.randomBytes(24);
        const encrypted = nacl.box(messageBytes, nonce, bouncerKey, ephemeralKeyPair.secretKey);
        
        const combined = new Uint8Array(32 + 24 + encrypted.length);
        combined.set(ephemeralKeyPair.publicKey, 0);
        combined.set(nonce, 32);
        combined.set(encrypted, 56);
        
        return encodeBase64(combined);
    }
    
    async getBouncerPublicKey() {
        // This should be fetched from server configuration
        // For now, return a placeholder - you need to implement this
        // based on your server's configuration
        return 'YOUR_BOUNCER_PUBLIC_KEY';
    }
    
    async getPushAccountId() {
        let accountId = await AsyncStorage.getItem('push_account_id');
        if (!accountId) {
            accountId = Date.now().toString(); // Simple ID generation
            await AsyncStorage.setItem('push_account_id', accountId);
        }
        return parseInt(accountId);
    }
}

// Usage
const pushManager = new E2EEPushNotificationManager();
await pushManager.initialize();

// Register Android device
const fcmToken = await messaging().getToken();
await pushManager.registerDevice(fcmToken, 'fcm');

// Register iOS device
const apnsToken = await messaging().getToken();
await pushManager.registerDevice(apnsToken, 'apns', 'com.yourapp.bundleid');

// Handle incoming notification
messaging().onMessage(async (remoteMessage) => {
    const decrypted = pushManager.decryptNotification(
        remoteMessage.data.encrypted_payload
    );
    console.log('New message:', decrypted);
});
```

### Notification Payload Format

After decryption, you'll receive JSON like:

**Stream Message:**
```json
{
    "type": "message",
    "message_id": 45,
    "channel_id": 10,
    "channel_name": "general",
    "topic": "Hello",
    "content": "Hello world!",
    "sender_id": 6,
    "sender_full_name": "John Doe",
    "sender_avatar_url": "https://...",
    "time": 1754385395,
    "realm_name": "Your Organization",
    "realm_url": "http://localhost:9991",
    "recipient_type": "channel",
    "user_id": 10
}
```

**Direct Message:**
```json
{
    "type": "message",
    "message_id": 46,
    "content": "Hi there!",
    "sender_id": 6,
    "sender_full_name": "John Doe",
    "pm_users": "6,10",
    "time": 1754385290,
    "recipient_type": "direct",
    "user_id": 10
}
```

### Testing Push Notifications

**Endpoint:** `POST /api/v1/mobile_push/e2ee/test_notification`

```javascript
async function testE2EENotification(pushAccountId = null) {
    const email = await AsyncStorage.getItem('email');
    const apiKey = await AsyncStorage.getItem('api_key');
    const authString = btoa(`${email}:${apiKey}`);
    
    const body = pushAccountId 
        ? { push_account_id: pushAccountId }
        : {}; // Send to all devices if not specified
    
    const response = await fetch('http://localhost:9991/api/v1/mobile_push/e2ee/test_notification', {
        method: 'POST',
        headers: {
            'Authorization': `Basic ${authString}`,
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(body)
    });
    
    return await response.json();
}
```

---

## Complete Workflow Summary

1. **Authenticate** → Get API key from JWT token
2. **Register Events** → Set up real-time event queue
3. **Send Messages** → Use API key to send messages
4. **Receive Messages** → Poll events for real-time updates
5. **Use All Features** → Streams, users, files, reactions, etc.

All requests use: `Authorization: Basic base64(email:api_key)`

---

## Security Best Practices

1. **Store API key securely** - Use secure storage (Keychain on iOS, Keystore on Android)
2. **Use HTTPS** - Always use HTTPS in production
3. **Handle token expiration** - Re-authenticate when JWT expires
4. **Error handling** - Implement proper error handling and retry logic
5. **Rate limiting** - Respect rate limits from server
6. **E2EE Push Notifications** - Use E2EE push notifications (Zulip 11.0+) to encrypt notification content
7. **Secure key storage** - Store encryption private keys in secure storage, never in plain text
8. **Key rotation** - Consider implementing key rotation for long-lived devices

---

For more details, see:
- [Zulip API Documentation](https://zulip.com/api/)
- [Mobile API Integration Guide](../dev-docs/MOBILE_API_INTEGRATION_GUIDE.md)

