import $ from "jquery";

import * as compose_ui from "./compose_ui.ts";
import {$t} from "./i18n.ts";
// import * as compose_state from "./compose_state.ts";
//     import * as compose from "./compose.js";

let media_recorder: MediaRecorder | null = null;
let recorded_chunks: BlobPart[] = [];
let is_recording = false;

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

async function start_recording(): Promise<void> {
    try {
        const stream = await navigator.mediaDevices.getUserMedia({audio: true});
        const options: MediaRecorderOptions = {mimeType: "audio/webm;codecs=opus"};
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
            const blob = new Blob(recorded_chunks, {type: "audio/webm"});
            upload_recording(blob);
        };

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
    media_recorder.stop();
    media_recorder.stream.getTracks().forEach((track) => track.stop());
}

function show_panel(): void {
    const $textarea = $("textarea#compose-textarea");
    const $panel = get_panel();
    if ($panel.length === 0) {
        const html = `<div class="voice-recorder-panel">
            <div class="voice-recorder-waveform"></div>
            <div class="voice-recorder-controls">
                <button type="button" class="voice-recorder-stop zulip-icon zulip-icon-close" aria-label="${$t({defaultMessage: "Stop recording"})}"></button>
            </div>
        </div>`;
        $textarea.before(html);
    }
    compose_ui.hide_compose_spinner();
    $textarea.prop("disabled", true);

    get_panel().one("click", ".voice-recorder-stop", () => {
        stop_recording();
        teardown_panel();
    });
}

function teardown_panel(): void {
    get_panel().remove();
    const $textarea = $("textarea#compose-textarea");
    $textarea.prop("disabled", false);
    compose_ui.autosize_textarea($textarea);
}

function upload_recording(blob: Blob): void {
    // For now, we reuse the existing upload flow by constructing a File
    // and letting upload.ts handle it via the paste/file-input path.
    const file = new File([blob], "voice-message.webm", {type: "audio/webm"});
    // Insert a placeholder so users see something while upload happens.
    compose_ui.insert_syntax_and_focus("[Uploading voice message…]()", $("#compose-textarea"));
    compose_ui.autosize_textarea($("#compose-textarea"));
    // Delegate to upload logic via compose_paste/upload_pasted_file.
    const textarea = $("#compose-textarea")[0] as HTMLTextAreaElement;
    void import("./upload.ts").then(({upload_pasted_file}) => {
        upload_pasted_file(textarea, file);
    });
}

