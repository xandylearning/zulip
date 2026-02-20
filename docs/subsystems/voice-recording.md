# Voice recording indicators

Zulip supports a feature called "voice recording indicators."

Voice recording indicators are status messages (or visual indicators) that
tell you when another user is recording a voice message to you.

This document describes how we have implemented the feature in
the Zulip web app, and our main audience is developers who want to
understand the system and possibly improve it. Any client should
be able follow the protocol documented here.

Voice recording indicators are implemented for both direct message conversations
and channel conversations in the web app.

## Recording user

When a "recording user" starts to record a message, the client
sends a request to `POST /voice_recording` with an `op` of `start` and
a list of potential message recipients (or stream ID and topic).

The user explicitly sends "stop" notification when they stop recording
(either to send the message or cancel).

## Server

The server piece of voice recording notifications is currently pretty
straightforward, since we take advantage of Zulip's
[events system](events-system.md).

We deliberately designed the server piece to be stateless,
which minimizes the possibility of backend bugs and gives clients
more control over the user experience.

As such, the server piece here is basically a single Django view
function with a small bit of library support to send out events
to clients.

Requests come in to `send_voice_recording_backend`, which is in
`zerver/views/voice_recording.py`.

One of the main things that the server does is to validate that
the user IDs in the `to` parameter are for valid, active users in
the realm.

Once the request has been validated, the server sends events to
potential recipients of the message. The event type for that
payload is `voice_recording`. See the function `do_send_voice_recording_notification`
in `zerver/actions/voice_recording.py` for more details.

For channel voice recording notifications, the server also handles the logic
for determining which users should receive the events based on channel subscribers.
Note that we use the `stream_typing_notifications` client capability to gate
sending these events for channel conversations, to reuse the existing mechanism
for high-volume ephemeral events.

## Receiving user

When a user plays the role of a "receiving user," the client handles
incoming "voice_recording" events from the server, and the client will
display a recording indicator.

We'll describe the flow of data through the web app
as a concrete example.

The events will come in to `web/src/server_events_dispatch.js`.
The `stop` and `start` operations get further handled by
`web/src/voice_recording_events.ts`.

The web app client maintains a list of incoming "recorders" using
code in `web/src/voice_recording_data.ts`.

## Privacy settings

The feature reuses the typing notification privacy settings:
`send_private_typing_notifications` and `send_stream_typing_notifications`.
If a user has disabled typing notifications, voice recording notifications
will also not be sent.
