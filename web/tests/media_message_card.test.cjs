"use strict";

const assert = require("node:assert/strict");

const {mock_esm, set_global, zrequire} = require("./lib/namespace.cjs");
const {run_test} = require("./lib/test.cjs");
const $ = require("./lib/zjquery.cjs");

set_global("document", "document-stub");

const media_message_card = zrequire("media_message_card");

function test(label, f) {
    run_test(label, () => {
        f();
    });
}

test("render_image_card", () => {
    const message = {
        id: 1,
        media_type: "image",
        caption: "Test image caption",
        primary_attachment: {
            id: 10,
            name: "photo.jpg",
            path_id: "1/ab/cdef/photo.jpg",
            size: 1024,
            content_type: "image/jpeg",
        },
        media_metadata: {
            width: 1920,
            height: 1080,
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-image-card"));
    assert.ok(html.includes("photo.jpg"));
    assert.ok(html.includes("Test image caption"));
});

test("render_video_card", () => {
    const message = {
        id: 2,
        media_type: "video",
        caption: "Test video",
        primary_attachment: {
            id: 11,
            name: "video.mp4",
            path_id: "1/ab/cdef/video.mp4",
            size: 2048,
            content_type: "video/mp4",
        },
        media_metadata: {
            width: 1920,
            height: 1080,
            duration_secs: 30,
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-video-card"));
    assert.ok(html.includes("video.mp4"));
});

test("render_audio_card", () => {
    const message = {
        id: 3,
        media_type: "audio",
        primary_attachment: {
            id: 12,
            name: "audio.mp3",
            path_id: "1/ab/cdef/audio.mp3",
            size: 512,
            content_type: "audio/mpeg",
        },
        media_metadata: {
            duration_secs: 120,
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-audio-card"));
    assert.ok(html.includes("audio.mp3"));
});

test("render_voice_message_card", () => {
    const message = {
        id: 4,
        media_type: "voice_message",
        primary_attachment: {
            id: 13,
            name: "voice.webm",
            path_id: "1/ab/cdef/voice.webm",
            size: 256,
            content_type: "audio/webm",
        },
        media_metadata: {
            duration_secs: 15,
            waveform: [0.1, 0.3, 0.7, 0.5, 0.2],
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-voice-card"));
    assert.ok(html.includes("voice.webm"));
});

test("render_location_card", () => {
    const message = {
        id: 5,
        media_type: "location",
        caption: "My location",
        media_metadata: {
            latitude: 40.7128,
            longitude: -74.0060,
            name: "New York City",
            address: "Manhattan, NY",
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-location-card"));
    assert.ok(html.includes("New York City"));
    assert.ok(html.includes("40.7128"));
});

test("render_contact_card", () => {
    const message = {
        id: 6,
        media_type: "contact",
        media_metadata: {
            name: "Jane Doe",
            phone: "+1234567890",
            email: "jane@example.com",
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-contact-card"));
    assert.ok(html.includes("Jane Doe"));
    assert.ok(html.includes("+1234567890"));
});

test("render_document_card", () => {
    const message = {
        id: 7,
        media_type: "document",
        caption: "Important document",
        primary_attachment: {
            id: 14,
            name: "document.pdf",
            path_id: "1/ab/cdef/document.pdf",
            size: 4096,
            content_type: "application/pdf",
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-document-card"));
    assert.ok(html.includes("document.pdf"));
    assert.ok(html.includes("Important document"));
});

test("render_sticker_card", () => {
    const message = {
        id: 8,
        media_type: "sticker",
        primary_attachment: {
            id: 15,
            name: "sticker.png",
            path_id: "1/ab/cdef/sticker.png",
            size: 128,
            content_type: "image/png",
        },
        media_metadata: {
            pack_id: "pack1",
            sticker_id: "sticker1",
        },
    };

    const html = media_message_card.renderMediaCard(message);
    assert.ok(html.includes("media-sticker-card"));
    assert.ok(html.includes("sticker.png"));
});

test("renderMediaCard_unknown_type", () => {
    const message = {
        id: 9,
        media_type: "unknown",
    };

    // Should handle unknown types gracefully
    const html = media_message_card.renderMediaCard(message);
    assert.ok(typeof html === "string");
});

test("getCaptionHtml_with_caption", () => {
    const caption = "Test caption";
    const html = media_message_card.getCaptionHtml(caption);
    assert.ok(html.includes("media-caption"));
    assert.ok(html.includes("Test caption"));
});

test("getCaptionHtml_no_caption", () => {
    const html = media_message_card.getCaptionHtml(null);
    assert.strictEqual(html, "");
});
