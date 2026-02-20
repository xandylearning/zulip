import $ from "jquery";

import * as compose_state from "./compose_state.ts";
import * as compose from "./compose.js";
import * as compose_ui from "./compose_ui.ts";

// Basic sticker pack definition. In production, this could be loaded from the server.
const STICKER_PACKS: Record<string, {pack_id: string; stickers: Array<{sticker_id: string; url: string}>}> = {};

export function initialize(): void {
    $(document).on("click", "[data-action='send-sticker']", (event) => {
        event.preventDefault();
        show_sticker_picker();
    });
}

function show_sticker_picker(): void {
    // For now, this is a stub. In production, this would open a modal
    // showing available sticker packs and allow selection.
    // eslint-disable-next-line no-console
    console.log("Sticker picker not yet implemented");
}

function send_sticker_message(pack_id: string, sticker_id: string, sticker_url: string): void {
    const media_metadata = {
        pack_id,
        sticker_id,
    };

    const message_content = compose_state.message_content();
    const message_obj = compose.create_message_object(message_content);
    message_obj.media_type = "sticker";
    message_obj.media_metadata = media_metadata;
    message_obj.content = ""; // Sticker messages don't need content
    message_obj.caption = message_content || null;
    message_obj.primary_attachment_path_id = sticker_url; // Sticker URL as attachment path

    compose.send_message(message_obj);
    compose_ui.clear_compose_box();
}
