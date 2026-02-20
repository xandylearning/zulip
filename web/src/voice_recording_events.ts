import * as z from "zod/mini";

import {$t} from "./i18n.ts";
import * as narrow_state from "./narrow_state.ts";
import * as people from "./people.ts";
import {current_user} from "./state_data.ts";
import * as voice_recording_data from "./voice_recording_data.ts";

const voice_recording_user_schema = z.object({
    email: z.string(),
    user_id: z.number(),
});

export const voice_recording_event_schema = z.intersection(
    z.object({
        id: z.number(),
        op: z.enum(["start", "stop"]),
        type: z.literal("voice_recording"),
    }),
    z.discriminatedUnion("message_type", [
        z.object({
            message_type: z.literal("stream"),
            sender: voice_recording_user_schema,
            stream_id: z.number(),
            topic: z.string(),
        }),
        z.object({
            message_type: z.literal("direct"),
            recipients: z.array(voice_recording_user_schema),
            sender: voice_recording_user_schema,
        }),
    ]),
);
type VoiceRecordingEvent = z.output<typeof voice_recording_event_schema>;

function get_key(event: VoiceRecordingEvent): string {
    if (event.message_type === "stream") {
        return voice_recording_data.get_topic_key(event.stream_id, event.topic);
    }
    if (event.message_type === "direct") {
        const recipients = event.recipients.map((user) => user.user_id);
        recipients.sort((a, b) => a - b);
        return voice_recording_data.get_direct_message_conversation_key(recipients);
    }
    throw new Error("Invalid voice_recording event type", event);
}

function get_recorders_for_narrow(): number[] {
    if (narrow_state.narrowed_by_topic_reply()) {
        const current_stream_id = narrow_state.stream_id(narrow_state.filter(), true);
        const current_topic = narrow_state.topic();
        if (current_stream_id === undefined || current_topic === undefined) {
            return [];
        }
        const key = voice_recording_data.get_topic_key(current_stream_id, current_topic);
        return voice_recording_data.get_recorder_ids(key);
    }
    if (!narrow_state.narrowed_to_pms()) {
        return [];
    }
    const terms = narrow_state.search_terms();
    const first_term = terms[0];
    if (first_term?.operator === "dm") {
        const narrow_emails_string = first_term.operand;
        const narrow_user_ids_string = people.reply_to_to_user_ids_string(narrow_emails_string);
        if (!narrow_user_ids_string) {
            return [];
        }
        const narrow_user_ids = narrow_user_ids_string
            .split(",")
            .map((user_id_string) => Number.parseInt(user_id_string, 10));
        const group = [...narrow_user_ids, current_user.user_id];
        const key = voice_recording_data.get_direct_message_conversation_key(group);
        return voice_recording_data.get_recorder_ids(key);
    }
    return [];
}

function render_notifications_for_narrow(): void {
    const user_ids = get_recorders_for_narrow();
    const users = user_ids
        .map((user_id) => people.get_user_by_id_assert_valid(user_id))
        .filter((person) => !person.is_inaccessible_user);
    const $container = $("#voice_recording_notifications");
    if (users.length === 0) {
        $container.hide().empty();
        return;
    }
    const text =
        users.length > 1
            ? $t({defaultMessage: "Several people are recording voice messages…"})
            : $t(
                  {defaultMessage: "{full_name} is recording a voice message…"},
                  {full_name: users[0].full_name},
              );
    $container.text(text).show();
}

export function display_notification(event: VoiceRecordingEvent): void {
    const key = get_key(event);
    voice_recording_data.add_recorder(key, event.sender.user_id);
    render_notifications_for_narrow();
}

export function hide_notification(event: VoiceRecordingEvent): void {
    const key = get_key(event);
    const removed = voice_recording_data.remove_recorder(key, event.sender.user_id);
    if (removed) {
        render_notifications_for_narrow();
    }
}
