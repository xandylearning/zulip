import $ from "jquery";

import * as compose_state from "./compose_state.ts";
import * as compose from "./compose.js";
import * as compose_ui from "./compose_ui.ts";

export function initialize(): void {
    $(document).on("click", "[data-action='send-location']", (event) => {
        event.preventDefault();
        void show_location_picker();
    });
}

async function show_location_picker(): Promise<void> {
    // For now, use browser geolocation API to get current location.
    // In production, this could open a modal with a map picker (e.g., Leaflet.js).
    if (!navigator.geolocation) {
        // eslint-disable-next-line no-console
        console.error("Geolocation not supported");
        return;
    }

    navigator.geolocation.getCurrentPosition(
        (position) => {
            const latitude = position.coords.latitude;
            const longitude = position.coords.longitude;
            send_location_message(latitude, longitude);
        },
        (error) => {
            // eslint-disable-next-line no-console
            console.error("Error getting location", error);
        },
    );
}

function send_location_message(latitude: number, longitude: number): void {
    // Reverse geocoding to get a name/address would require an external API.
    // For now, we just send coordinates.
    const name = `${latitude.toFixed(6)}, ${longitude.toFixed(6)}`;
    const media_metadata = {
        latitude,
        longitude,
        name,
    };

    const message_content = compose_state.message_content();
    const message_obj = compose.create_message_object(message_content);
    message_obj.media_type = "location";
    message_obj.media_metadata = media_metadata;
    message_obj.content = ""; // Location messages don't need content
    message_obj.caption = message_content || null;

    compose.send_message(message_obj);
    compose_ui.clear_compose_box();
}
