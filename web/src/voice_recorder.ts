import $ from "jquery";

import * as blueslip from "./blueslip.ts";
import * as channel from "./channel.ts";
import * as compose_pm_pill from "./compose_pm_pill.ts";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import {$t} from "./i18n.ts";
import * as stream_data from "./stream_data.ts";
import {user_settings} from "./user_settings.ts";

let media_recorder: MediaRecorder | null = null;
let recorded_chunks: BlobPart[] = [];
let is_recording = false;
let current_recording_mime: SupportedMime | null = null;

type SupportedMime = {mimeType: string; extension: string};

const AUDIO_MIME_CANDIDATES: SupportedMime[] = [
    {mimeType: "audio/webm;codecs=opus", extension: "weba"},
    {mimeType: "audio/webm", extension: "weba"},
    {mimeType: "audio/mp4", extension: "m4a"},
    {mimeType: "audio/ogg", extension: "ogg"},
];

const DEFAULT_RECORDING_MIME: SupportedMime = AUDIO_MIME_CANDIDATES[0]!;

function getSupportedMimeType(): SupportedMime | null {
    for (const candidate of AUDIO_MIME_CANDIDATES) {
        if (MediaRecorder.isTypeSupported(candidate.mimeType)) {
            return candidate;
        }
    }
    return null;
}

function get_panel(): JQuery {
    return $(".voice-recorder-panel");
}

export function initialize(): void {
    // Expect a microphone button with this data-action in the compose toolbar.
    $(document).on("click", "[data-action='voice-message']", (event) => {
        event.preventDefault();
        void start_or_stop();
    });
}

async function start_or_stop(): Promise<void> {
    if (is_recording) {
        stop_recording();
        return;
    }
    await start_recording();
}

function send_voice_recording_notification(operator: "start" | "stop"): void {
    const message_type = compose_state.get_message_type();
    if (message_type === "private") {
        const user_ids = compose_pm_pill.get_user_ids();
        if (user_ids.length === 0 || !user_settings.send_private_typing_notifications) {
            return;
        }
        void channel.post({
            url: "/json/voice_recording",
            data: {op: operator, type: "direct", to: JSON.stringify(user_ids)},
            error(xhr) {
                if (xhr.readyState !== 0) {
                    blueslip.warn("Failed to send voice recording event: " + xhr.responseText);
                }
            },
        });
        return;
    }
    if (message_type === "stream") {
        const stream_name = compose_state.stream_name();
        const stream_id = stream_data.get_stream_id(stream_name);
        const topic = compose_state.topic();
        if (
            stream_id === undefined ||
            (!stream_data.can_use_empty_topic(stream_id) && topic === "") ||
            !user_settings.send_stream_typing_notifications
        ) {
            return;
        }
        const stream = stream_data.get_sub_by_id(stream_id);
        if (stream === undefined || !stream_data.can_post_messages_in_stream(stream)) {
            return;
        }
        void channel.post({
            url: "/json/voice_recording",
            data: {
                op: operator,
                type: "stream",
                stream_id: JSON.stringify(stream_id),
                topic,
            },
            error(xhr) {
                if (xhr.readyState !== 0) {
                    blueslip.warn("Failed to send voice recording event: " + xhr.responseText);
                }
            },
        });
    }
}

async function start_recording(): Promise<void> {
    try {
        const supported = getSupportedMimeType() ?? DEFAULT_RECORDING_MIME;
        current_recording_mime = supported;

        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const options: MediaRecorderOptions = {mimeType: supported.mimeType};
        media_recorder = new MediaRecorder(stream, options);
        recorded_chunks = [];
        is_recording = true;

        media_recorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                recorded_chunks.push(event.data);
            }
        };
        media_recorder.onstop = () => {
            is_recording = false;
            const mime = current_recording_mime ?? DEFAULT_RECORDING_MIME;
            const blob = new Blob(recorded_chunks, {type: mime.mimeType});
            upload_recording(blob, mime);
            current_recording_mime = null;
        };

        send_voice_recording_notification("start");
        show_panel();
        media_recorder.start();
    } catch (error) {
        // Permission denied or not available.
        // For now we just log; production code should show a banner.
        // eslint-disable-next-line no-console
        console.error("Error starting voice recording", error);
    }
}

function stop_recording(): void {
    if (!media_recorder) {
        return;
    }
    send_voice_recording_notification("stop");
    media_recorder.stop();
    media_recorder.stream.getTracks().forEach((track) => track.stop());
}

function show_panel(): void {
    const $textarea = $("textarea#compose-textarea");
    const $panel = get_panel();
    if ($panel.length === 0) {
        const html = `<div class="voice-recorder-panel">
            <div class="voice-recorder-label">${$t({defaultMessage: "Recording…"})}</div>
            <div class="voice-recorder-waveform"></div>
            <div class="voice-recorder-controls">
                <button type="button" class="voice-recorder-stop zulip-icon zulip-icon-close" aria-label="${$t({defaultMessage: "Stop recording"})}"></button>
            </div>
        </div>`;
        $textarea.before(html);
    }
    compose_ui.hide_compose_spinner();
    $textarea.prop("disabled", true).hide();

    get_panel().one("click", ".voice-recorder-stop", () => {
        stop_recording();
        teardown_panel();
    });
}

function teardown_panel(): void {
    get_panel().remove();
    const $textarea = $<HTMLTextAreaElement>("textarea#compose-textarea");
    $textarea.prop("disabled", false).show();
    compose_ui.autosize_textarea($textarea);
}

function upload_recording(blob: Blob, mime: SupportedMime): void {
    // Reuse the existing upload flow by constructing a File
    // and letting upload.ts handle it via the paste/file-input path.
    const filename = `voice-message.${mime.extension}`;
    const file = new File([blob], filename, {type: mime.mimeType});
    const $textarea = $<HTMLTextAreaElement>("textarea#compose-textarea");
    const textarea = $textarea[0];
    void import("./upload.ts").then(({upload_pasted_file}) => {
        if (textarea) {
            upload_pasted_file(textarea, file);
        }
    });
}

