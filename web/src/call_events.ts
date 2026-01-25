import * as z from "zod/mini";

import * as blueslip from "./blueslip.ts";
import {current_user} from "./state_data.ts";

// This module handles inbound call events from the server.
// See zulip_calls_plugin/actions.py for the backend event dispatch.

// ============================================================================
// Type Definitions (matching Phase 1 event schemas)
// ============================================================================

export const call_participant_schema = z.object({
    user_id: z.number(),
    full_name: z.string(),
});
type CallParticipant = z.output<typeof call_participant_schema>;

export const call_event_schema = z.object({
    id: z.number(),
    type: z.literal("call"),
    op: z.enum([
        "initiated",
        "incoming_call",
        "ringing",
        "accepted",
        "declined",
        "ended",
        "cancelled",
        "missed",
    ]),
    call_id: z.string(),
    call_type: z.enum(["audio", "video"]),
    sender: call_participant_schema,
    receiver: call_participant_schema,
    state: z.string(),
    jitsi_url: z.nullable(z.string()),
    timestamp: z.string(),
    // Optional fields
    receiver_was_offline: z.optional(z.boolean()),
    reason: z.optional(z.string()),
    timeout_seconds: z.optional(z.number()),
});
export type CallEvent = z.output<typeof call_event_schema>;

export const group_call_participant_info_schema = z.object({
    user_id: z.number(),
    full_name: z.string(),
    state: z.string(),
    is_host: z.boolean(),
});
type GroupCallParticipantInfo = z.output<typeof group_call_participant_info_schema>;

export const group_call_event_schema = z.object({
    id: z.number(),
    type: z.literal("group_call"),
    op: z.enum([
        "created",
        "participant_invited",
        "participant_joined",
        "participant_left",
        "participant_declined",
        "participant_missed",
        "ended",
    ]),
    call_id: z.string(),
    call_type: z.enum(["audio", "video"]),
    host: call_participant_schema,
    participants: z.array(group_call_participant_info_schema),
    jitsi_url: z.string(),
    title: z.nullable(z.string()),
    stream_id: z.nullable(z.number()),
    topic: z.nullable(z.string()),
    timestamp: z.string(),
    // Optional fields
    inviter_id: z.optional(z.number()),
    was_offline: z.optional(z.boolean()),
    new_participants: z.optional(z.array(z.number())),
});
export type GroupCallEvent = z.output<typeof group_call_event_schema>;

// ============================================================================
// Active Call State Management
// ============================================================================

interface ActiveCallState {
    call_id: string;
    call_type: "audio" | "video";
    state: string;
    other_user: CallParticipant;
    jitsi_url: string | null;
    is_initiator: boolean;
}

interface ActiveGroupCallState {
    call_id: string;
    call_type: "audio" | "video";
    host: CallParticipant;
    participants: GroupCallParticipantInfo[];
    jitsi_url: string;
    title: string | null;
}

// Store active calls
const active_calls = new Map<string, ActiveCallState>();
const active_group_calls = new Map<string, ActiveGroupCallState>();

// ============================================================================
// 1-to-1 Call Event Handlers
// ============================================================================

export function handle_call_initiated(event: CallEvent): void {
    // Called when current user initiates a call
    if (event.sender.user_id !== current_user.user_id) {
        blueslip.warn("Received call initiated event for call not initiated by current user");
        return;
    }

    // Store call state
    active_calls.set(event.call_id, {
        call_id: event.call_id,
        call_type: event.call_type,
        state: "calling",
        other_user: event.receiver,
        jitsi_url: event.jitsi_url,
        is_initiator: true,
    });

    // Log for debugging
    blueslip.info(
        `Call initiated: ${event.call_id} to ${event.receiver.full_name} (${event.call_type})`,
    );

    // UI update would go here (show calling UI, play ringing sound, etc.)
    // This is a placeholder for future UI integration
    show_call_notification(
        `Calling ${event.receiver.full_name}...`,
        event.call_type,
        event.call_id,
    );
}

export function handle_incoming_call(event: CallEvent): void {
    // Called when current user receives an incoming call
    if (event.receiver.user_id !== current_user.user_id) {
        blueslip.warn("Received incoming call event for call not directed to current user");
        return;
    }

    // Store call state
    active_calls.set(event.call_id, {
        call_id: event.call_id,
        call_type: event.call_type,
        state: "ringing",
        other_user: event.sender,
        jitsi_url: event.jitsi_url,
        is_initiator: false,
    });

    // Log for debugging
    blueslip.info(
        `Incoming call: ${event.call_id} from ${event.sender.full_name} (${event.call_type})`,
    );

    // UI update would go here (show incoming call modal, play ringtone, etc.)
    show_incoming_call_ui(event);
}

export function handle_call_ringing(event: CallEvent): void {
    // Called when receiver acknowledges the call (picks up but hasn't accepted yet)
    const call = active_calls.get(event.call_id);
    if (!call) {
        blueslip.warn(`Received ringing event for unknown call: ${event.call_id}`);
        return;
    }

    call.state = "ringing";

    // Log for debugging
    blueslip.info(`Call ringing: ${event.call_id}`);

    // UI update would go here (show "User is picking up..." message)
    show_call_notification(`${call.other_user.full_name} is picking up...`, call.call_type);
}

export function handle_call_accepted(event: CallEvent): void {
    // Called when call is accepted by either party
    const call = active_calls.get(event.call_id);
    if (!call) {
        blueslip.warn(`Received accepted event for unknown call: ${event.call_id}`);
        return;
    }

    call.state = "accepted";

    // Log for debugging
    blueslip.info(`Call accepted: ${event.call_id}`);

    // UI update would go here (navigate to Jitsi, update UI to show connected state)
    if (event.jitsi_url) {
        show_call_notification(
            `Call connected with ${call.other_user.full_name}`,
            call.call_type,
        );
        // In a full implementation, this would open Jitsi in iframe or new window
        // window.open(event.jitsi_url, "_blank");
    }
}

export function handle_call_declined(event: CallEvent): void {
    // Called when call is declined by receiver
    const call = active_calls.get(event.call_id);
    if (!call) {
        blueslip.warn(`Received declined event for unknown call: ${event.call_id}`);
        return;
    }

    // Remove from active calls
    active_calls.delete(event.call_id);

    // Log for debugging
    blueslip.info(`Call declined: ${event.call_id}`);

    // UI update would go here (show "Call declined" message, dismiss call UI)
    show_call_notification(`${call.other_user.full_name} declined the call`, call.call_type);
    cleanup_call_ui(event.call_id);
}

export function handle_call_ended(event: CallEvent): void {
    // Called when call ends (either party hangs up)
    const call = active_calls.get(event.call_id);
    if (!call) {
        // Call might have already been cleaned up
        blueslip.info(`Received ended event for call ${event.call_id} (already cleaned up)`);
        return;
    }

    // Remove from active calls
    active_calls.delete(event.call_id);

    // Log for debugging
    const reason = event.reason ? ` (${event.reason})` : "";
    blueslip.info(`Call ended: ${event.call_id}${reason}`);

    // UI update would go here (dismiss call UI, show "Call ended" message if needed)
    if (event.reason === "network_failure") {
        show_call_notification("Call ended due to network failure", call.call_type);
    } else if (event.reason === "timeout_stale") {
        show_call_notification("Call ended due to timeout", call.call_type);
    } else {
        show_call_notification("Call ended", call.call_type);
    }
    cleanup_call_ui(event.call_id);
}

export function handle_call_cancelled(event: CallEvent): void {
    // Called when caller cancels the call before receiver answers
    const call = active_calls.get(event.call_id);
    if (!call) {
        blueslip.warn(`Received cancelled event for unknown call: ${event.call_id}`);
        return;
    }

    // Remove from active calls
    active_calls.delete(event.call_id);

    // Log for debugging
    blueslip.info(`Call cancelled: ${event.call_id}`);

    // UI update would go here (dismiss call UI)
    if (call.is_initiator) {
        show_call_notification("Call cancelled", call.call_type);
    } else {
        show_call_notification(`${call.other_user.full_name} cancelled the call`, call.call_type);
    }
    cleanup_call_ui(event.call_id);
}

export function handle_call_missed(event: CallEvent): void {
    // Called when call times out without being answered
    const call = active_calls.get(event.call_id);
    if (call) {
        active_calls.delete(event.call_id);
    }

    // Log for debugging
    const timeout = event.timeout_seconds ? ` after ${event.timeout_seconds}s` : "";
    blueslip.info(`Call missed: ${event.call_id}${timeout}`);

    // UI update would go here (show missed call notification, add to call history)
    if (call) {
        show_call_notification(`Missed call from ${call.other_user.full_name}`, call.call_type);
        cleanup_call_ui(event.call_id);
    }
}

// ============================================================================
// Group Call Event Handlers
// ============================================================================

export function handle_group_call_created(event: GroupCallEvent): void {
    // Called when current user creates a group call
    if (event.host.user_id !== current_user.user_id) {
        blueslip.warn("Received group call created event for call not created by current user");
        return;
    }

    // Store group call state
    active_group_calls.set(event.call_id, {
        call_id: event.call_id,
        call_type: event.call_type,
        host: event.host,
        participants: event.participants,
        jitsi_url: event.jitsi_url,
        title: event.title,
    });

    // Log for debugging
    const title = event.title || "Group Call";
    blueslip.info(`Group call created: ${event.call_id} - ${title}`);

    // UI update would go here (show group call UI, navigate to Jitsi)
    show_call_notification(`Group call created: ${title}`, event.call_type);
}

export function handle_group_call_participant_invited(event: GroupCallEvent): void {
    // Called when current user is invited to a group call
    const inviter_name = event.inviter_id
        ? event.participants.find((p: GroupCallParticipantInfo) => p.user_id === event.inviter_id)?.full_name
        : event.host.full_name;

    // Store group call state
    active_group_calls.set(event.call_id, {
        call_id: event.call_id,
        call_type: event.call_type,
        host: event.host,
        participants: event.participants,
        jitsi_url: event.jitsi_url,
        title: event.title,
    });

    // Log for debugging
    const title = event.title || "Group Call";
    blueslip.info(`Invited to group call: ${event.call_id} - ${title} by ${inviter_name ?? "unknown"}`);

    // UI update would go here (show group call invitation modal)
    show_group_call_invitation_ui(event, inviter_name ?? "Someone");
}

export function handle_group_call_participant_joined(event: GroupCallEvent): void {
    // Called when a participant joins the group call
    const group_call = active_group_calls.get(event.call_id);
    if (!group_call) {
        blueslip.warn(`Received participant joined event for unknown group call: ${event.call_id}`);
        return;
    }

    // Update participant list
    group_call.participants = event.participants;

    // Log for debugging
    blueslip.info(`Participant joined group call: ${event.call_id}`);

    // UI update would go here (update participant list in UI)
    update_group_call_participants_ui(event.call_id, event.participants);
}

export function handle_group_call_participant_left(event: GroupCallEvent): void {
    // Called when a participant leaves the group call
    const group_call = active_group_calls.get(event.call_id);
    if (!group_call) {
        blueslip.warn(`Received participant left event for unknown group call: ${event.call_id}`);
        return;
    }

    // Update participant list
    group_call.participants = event.participants;

    // Log for debugging
    blueslip.info(`Participant left group call: ${event.call_id}`);

    // UI update would go here (update participant list in UI)
    update_group_call_participants_ui(event.call_id, event.participants);
}

export function handle_group_call_participant_declined(event: GroupCallEvent): void {
    // Called when a participant declines the group call invitation
    const group_call = active_group_calls.get(event.call_id);
    if (!group_call) {
        blueslip.warn(
            `Received participant declined event for unknown group call: ${event.call_id}`,
        );
        return;
    }

    // Update participant list
    group_call.participants = event.participants;

    // Log for debugging
    blueslip.info(`Participant declined group call: ${event.call_id}`);

    // UI update would go here (update participant list in UI)
    update_group_call_participants_ui(event.call_id, event.participants);
}

export function handle_group_call_participant_missed(event: GroupCallEvent): void {
    // Called when a participant misses the group call invitation (timeout)
    const group_call = active_group_calls.get(event.call_id);
    if (!group_call) {
        // Call might have already been cleaned up
        return;
    }

    // Update participant list
    group_call.participants = event.participants;

    // Log for debugging
    blueslip.info(`Participant missed group call: ${event.call_id}`);

    // UI update would go here (update participant list in UI)
    update_group_call_participants_ui(event.call_id, event.participants);
}

export function handle_group_call_ended(event: GroupCallEvent): void {
    // Called when the group call ends
    const group_call = active_group_calls.get(event.call_id);
    if (!group_call) {
        // Call might have already been cleaned up
        blueslip.info(
            `Received ended event for group call ${event.call_id} (already cleaned up)`,
        );
        return;
    }

    // Remove from active group calls
    active_group_calls.delete(event.call_id);

    // Log for debugging
    const title = group_call.title || "Group call";
    blueslip.info(`Group call ended: ${event.call_id} - ${title}`);

    // UI update would go here (dismiss group call UI, show "Call ended" message)
    show_call_notification(`${title} ended`, group_call.call_type);
    cleanup_group_call_ui(event.call_id);
}

// ============================================================================
// UI Helper Functions (placeholders for future implementation)
// ============================================================================

function show_call_notification(message: string, call_type: string, call_id?: string): void {
    // Placeholder: This would show a notification in the Zulip UI
    // For now, just log to console
    console.log(`[Call Notification - ${call_type}] ${message}`, call_id ? `(${call_id})` : "");

    // In a full implementation, this might:
    // - Show a banner notification at the top of the page
    // - Play a sound (for incoming calls)
    // - Update a calls sidebar/widget
    // - Show a browser notification
}

function show_incoming_call_ui(event: CallEvent): void {
    // Placeholder: This would show the incoming call modal/UI
    console.log(
        `[Incoming Call UI] ${event.call_type} call from ${event.sender.full_name}`,
        event,
    );

    // In a full implementation, this would:
    // - Show a modal with Accept/Decline buttons
    // - Play ringtone
    // - Show caller's avatar and name
    // - Provide option to switch to video if audio call
}

function show_group_call_invitation_ui(event: GroupCallEvent, inviter_name: string): void {
    // Placeholder: This would show the group call invitation UI
    const title = event.title || "Group Call";
    console.log(`[Group Call Invitation] ${title} from ${inviter_name}`, event);

    // In a full implementation, this would:
    // - Show a modal with Join/Decline buttons
    // - Show list of other participants
    // - Show call title and topic (if stream call)
    // - Play notification sound
}

function update_group_call_participants_ui(call_id: string, participants: GroupCallParticipantInfo[]): void {
    // Placeholder: This would update the participant list in the group call UI
    console.log(`[Group Call ${call_id}] Participants updated:`, participants);

    // In a full implementation, this would:
    // - Update the participant list sidebar
    // - Show/hide participant avatars
    // - Update participant states (joined, invited, declined, etc.)
}

function cleanup_call_ui(call_id: string): void {
    // Placeholder: This would clean up any UI elements related to the call
    console.log(`[Cleanup] Removing UI for call ${call_id}`);

    // In a full implementation, this would:
    // - Close any open modals
    // - Stop ringtone/sounds
    // - Clear notifications
    // - Remove call from UI state
}

function cleanup_group_call_ui(call_id: string): void {
    // Placeholder: This would clean up any UI elements related to the group call
    console.log(`[Cleanup] Removing UI for group call ${call_id}`);

    // In a full implementation, this would:
    // - Close group call UI/modal
    // - Stop sounds
    // - Clear notifications
    // - Remove from UI state
}

// ============================================================================
// Public API for querying active calls
// ============================================================================

export function get_active_call(call_id: string): ActiveCallState | undefined {
    return active_calls.get(call_id);
}

export function get_active_group_call(call_id: string): ActiveGroupCallState | undefined {
    return active_group_calls.get(call_id);
}

export function has_active_calls(): boolean {
    return active_calls.size > 0 || active_group_calls.size > 0;
}

export function get_all_active_calls(): ActiveCallState[] {
    return Array.from(active_calls.values());
}

export function get_all_active_group_calls(): ActiveGroupCallState[] {
    return Array.from(active_group_calls.values());
}

// For testing purposes
export function clear_all_calls_for_testing(): void {
    active_calls.clear();
    active_group_calls.clear();
}
