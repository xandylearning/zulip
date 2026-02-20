import $ from "jquery";

import * as compose_state from "./compose_state.ts";
import * as compose from "./compose.js";
import * as compose_ui from "./compose_ui.ts";

export function initialize(): void {
    $(document).on("click", "[data-action='send-contact']", (event) => {
        event.preventDefault();
        show_contact_picker();
    });
}

function show_contact_picker(): void {
    // For now, show a simple prompt. In production, this could open a modal
    // with a contact picker UI or integrate with the browser Contacts API.
    const name = prompt("Contact name:");
    if (!name) {
        return;
    }
    const phone = prompt("Phone number (optional):") || "";
    const email = prompt("Email (optional):") || "";

    if (!phone && !email) {
        // eslint-disable-next-line no-console
        console.warn("Contact must have at least phone or email");
        return;
    }

    send_contact_message(name, phone, email);
}

function send_contact_message(name: string, phone: string, email: string): void {
    const media_metadata = {
        name,
        phone: phone || undefined,
        email: email || undefined,
    };

    const message_content = compose_state.message_content();
    const message_obj = compose.create_message_object(message_content);
    message_obj.media_type = "contact";
    message_obj.media_metadata = media_metadata;
    message_obj.content = ""; // Contact messages don't need content
    message_obj.caption = message_content || null;

    compose.send_message(message_obj);
    compose_ui.clear_compose_box();
}
