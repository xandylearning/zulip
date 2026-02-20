import * as util from "./util.ts";

const recorders_dict = new Map<string, number[]>();

export function get_direct_message_conversation_key(group: number[]): string {
    const ids = util.sorted_ids(group);
    return "voice_recording_direct:" + ids.join(",");
}

export function get_topic_key(stream_id: number, topic: string): string {
    const topic_lower = topic.toLowerCase();
    return "voice_recording_topic:" + JSON.stringify({stream_id, topic: topic_lower});
}

export function add_recorder(key: string, user_id: number): void {
    const current = recorders_dict.get(key) ?? [];
    if (!current.includes(user_id)) {
        current.push(user_id);
    }
    recorders_dict.set(key, util.sorted_ids(current));
}

export function remove_recorder(key: string, user_id: number): boolean {
    const current = recorders_dict.get(key) ?? [];
    if (!current.includes(user_id)) {
        return false;
    }
    const next = current.filter((id) => id !== user_id);
    if (next.length === 0) {
        recorders_dict.delete(key);
    } else {
        recorders_dict.set(key, next);
    }
    return true;
}

export function get_recorder_ids(key: string): number[] {
    return recorders_dict.get(key) ?? [];
}

export function get_all_recorder_keys(): string[] {
    return [...recorders_dict.keys()];
}
