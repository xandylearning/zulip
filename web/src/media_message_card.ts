import $ from "jquery";

import type {Message} from "./message_store.ts";

type RenderTarget = JQuery;

export function renderMediaCard(message: Message, $row: RenderTarget): void {
    const $container = $row.find(".message_content.media-message-content");
    if ($container.length === 0) {
        return;
    }

    const media_type = message.media_type;
    if (!media_type) {
        return;
    }

    let card_html = "";

    switch (media_type) {
        case "image":
            card_html = renderImageCard(message);
            break;
        case "video":
            card_html = renderVideoCard(message);
            break;
        case "audio":
            card_html = renderAudioCard(message);
            break;
        case "voice_message":
            card_html = renderVoiceMessageCard(message);
            break;
        case "document":
            card_html = renderDocumentCard(message);
            break;
        case "location":
            card_html = renderLocationCard(message);
            break;
        case "contact":
            card_html = renderContactCard(message);
            break;
        case "sticker":
            card_html = renderStickerCard(message);
            break;
        default:
            // Fallback to regular rendered markdown content.
            return;
    }

    $container.html(card_html);
}

function getCaptionHtml(message: Message): string {
    if (!message.caption) {
        return "";
    }
    return `<div class="media-caption">${_.escape(message.caption)}</div>`;
}

function renderImageCard(message: Message): string {
    const attachment = message.primary_attachment;
    if (!attachment) {
        return "";
    }
    const src = `/user_uploads/${attachment.path_id}`;
    const caption_html = getCaptionHtml(message);
    return `<div class="media-image-card">
        <img src="${_.escape(src)}" alt="${_.escape(message.caption ?? attachment.name)}" />
        ${caption_html}
    </div>`;
}

function renderVideoCard(message: Message): string {
    const attachment = message.primary_attachment;
    if (!attachment) {
        return "";
    }
    const src = `/user_uploads/${attachment.path_id}`;
    const caption_html = getCaptionHtml(message);
    return `<div class="media-video-card">
        <video controls src="${_.escape(src)}"></video>
        ${caption_html}
    </div>`;
}

function renderAudioCard(message: Message): string {
    const attachment = message.primary_attachment;
    if (!attachment) {
        return "";
    }
    const src = `/user_uploads/${attachment.path_id}`;
    const caption_html = getCaptionHtml(message);
    return `<div class="media-audio-card">
        <audio controls src="${_.escape(src)}"></audio>
        ${caption_html}
    </div>`;
}

function renderVoiceMessageCard(message: Message): string {
    const attachment = message.primary_attachment;
    if (!attachment) {
        return "";
    }
    const src = `/user_uploads/${attachment.path_id}`;
    const caption_html = getCaptionHtml(message);
    // For now, render as an audio player with a placeholder waveform container.
    return `<div class="media-voice-card">
        <div class="media-voice-waveform"></div>
        <audio controls src="${_.escape(src)}"></audio>
        ${caption_html}
    </div>`;
}

function renderDocumentCard(message: Message): string {
    const attachment = message.primary_attachment;
    if (!attachment) {
        return "";
    }
    const href = `/user_uploads/${attachment.path_id}`;
    const caption_html = getCaptionHtml(message);
    return `<div class="media-document-card">
        <a href="${_.escape(href)}" target="_blank" rel="noopener noreferrer">
            <span class="media-document-name">${_.escape(attachment.name)}</span>
        </a>
        ${caption_html}
    </div>`;
}

function renderLocationCard(message: Message): string {
    const metadata = message.media_metadata ?? {};
    const name = typeof metadata.name === "string" ? metadata.name : "";
    const address = typeof metadata.address === "string" ? metadata.address : "";
    return `<div class="media-location-card">
        <div class="media-location-name">${_.escape(name)}</div>
        <div class="media-location-address">${_.escape(address)}</div>
    </div>`;
}

function renderContactCard(message: Message): string {
    const metadata = message.media_metadata ?? {};
    const name = typeof metadata.name === "string" ? metadata.name : "";
    const phone = typeof metadata.phone === "string" ? metadata.phone : "";
    const email = typeof metadata.email === "string" ? metadata.email : "";
    return `<div class="media-contact-card">
        <div class="media-contact-name">${_.escape(name)}</div>
        <div class="media-contact-phone">${_.escape(phone)}</div>
        <div class="media-contact-email">${_.escape(email)}</div>
    </div>`;
}

function renderStickerCard(message: Message): string {
    const attachment = message.primary_attachment;
    if (!attachment) {
        return "";
    }
    const src = `/user_uploads/${attachment.path_id}`;
    return `<div class="media-sticker-card">
        <img src="${_.escape(src)}" alt="sticker" />
    </div>`;
}

