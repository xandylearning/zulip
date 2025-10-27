/**
 * Broadcast Message Renderer
 *
 * This module handles rendering of rich media broadcast notification templates
 * within the message view, providing WhatsApp-like interactive templates with
 * buttons, images, videos, and other media blocks.
 */

import type {Message} from "./message_store";
import type {TemplateBlock, TemplateStructure} from "./broadcast_template_blocks";

interface BroadcastTemplateData {
    template_id: number;
    template_structure: TemplateStructure;
    media_content: Record<string, string>;
    message_type: "broadcast_notification";
    broadcast_notification_id?: number;
}

/**
 * Check if a message contains broadcast template data
 */
export function isBroadcastMessage(message: Message): boolean {
    return message.broadcast_template_data !== null && message.broadcast_template_data !== undefined;
}

/**
 * Get broadcast template data from a message
 */
export function getBroadcastTemplateData(message: Message): BroadcastTemplateData | null {
    if (!isBroadcastMessage(message)) {
        return null;
    }
    return message.broadcast_template_data as BroadcastTemplateData;
}

/**
 * Main function to render a broadcast message with rich template
 */
export function renderBroadcastMessage(message: Message): string {
    const templateData = getBroadcastTemplateData(message);
    if (!templateData) {
        return message.content;
    }

    const {template_structure, media_content} = templateData;
    const blocks = template_structure.blocks || [];

    // Render all blocks
    const renderedBlocks = blocks.map((block) => renderBlock(block, media_content, message.id));

    // Wrap in broadcast template container
    return `
        <div class="broadcast-template-message" data-message-id="${message.id}">
            ${renderedBlocks.join("")}
        </div>
    `;
}

/**
 * Render an individual block based on its type
 */
function renderBlock(
    block: TemplateBlock,
    mediaContent: Record<string, string>,
    messageId: number,
): string {
    switch (block.type) {
        case "text":
            return renderTextBlock(block, mediaContent);
        case "image":
            return renderImageBlock(block, mediaContent);
        case "video":
            return renderVideoBlock(block, mediaContent);
        case "audio":
            return renderAudioBlock(block, mediaContent);
        case "button":
            return renderButtonBlock(block, mediaContent, messageId);
        case "svg":
            return renderSVGBlock(block, mediaContent);
        default:
            return "";
    }
}

/**
 * Render text block with markdown support
 */
function renderTextBlock(
    block: TemplateBlock & {type: "text"},
    mediaContent: Record<string, string>,
): string {
    const content = mediaContent[block.id] || block.content || "";
    if (!content.trim()) {
        return "";
    }

    // Use the markdown processor (content is already rendered as HTML in message.content)
    // For template blocks, we'll use simple paragraph wrapping
    const escapedContent = escapeHtml(content);
    const formattedContent = escapedContent.replace(/\n/g, "<br>");

    return `
        <div class="broadcast-text-block" data-block-id="${block.id}">
            <p>${formattedContent}</p>
        </div>
    `;
}

/**
 * Render image block
 */
function renderImageBlock(
    block: TemplateBlock & {type: "image"},
    mediaContent: Record<string, string>,
): string {
    const imageUrl = mediaContent[block.id] || block.url;
    if (!imageUrl) {
        return "";
    }

    const altText = escapeHtml(block.alt || block.label || "Image");
    const maxWidth = block.maxWidth ? `style="max-width: ${block.maxWidth}px;"` : "";

    return `
        <div class="broadcast-image-block" data-block-id="${block.id}">
            <img src="${escapeHtml(imageUrl)}" alt="${altText}" ${maxWidth} loading="lazy" />
        </div>
    `;
}

/**
 * Render video block
 */
function renderVideoBlock(
    block: TemplateBlock & {type: "video"},
    mediaContent: Record<string, string>,
): string {
    const videoUrl = mediaContent[block.id] || block.url;
    if (!videoUrl) {
        return "";
    }

    // Check if it's a YouTube or Vimeo URL for embedded player
    const youtubeMatch = videoUrl.match(/(?:youtube\.com\/watch\?v=|youtu\.be\/)([^&\s]+)/);
    const vimeoMatch = videoUrl.match(/vimeo\.com\/(\d+)/);

    if (youtubeMatch) {
        const videoId = youtubeMatch[1];
        return `
            <div class="broadcast-video-block" data-block-id="${block.id}">
                <div class="video-embed">
                    <iframe
                        src="https://www.youtube.com/embed/${escapeHtml(videoId)}"
                        frameborder="0"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
                        allowfullscreen>
                    </iframe>
                </div>
            </div>
        `;
    }

    if (vimeoMatch) {
        const videoId = vimeoMatch[1];
        return `
            <div class="broadcast-video-block" data-block-id="${block.id}">
                <div class="video-embed">
                    <iframe
                        src="https://player.vimeo.com/video/${escapeHtml(videoId)}"
                        frameborder="0"
                        allow="autoplay; fullscreen; picture-in-picture"
                        allowfullscreen>
                    </iframe>
                </div>
            </div>
        `;
    }

    // Otherwise, use HTML5 video element
    return `
        <div class="broadcast-video-block" data-block-id="${block.id}">
            <video controls>
                <source src="${escapeHtml(videoUrl)}">
                Your browser does not support the video tag.
            </video>
        </div>
    `;
}

/**
 * Render audio block
 */
function renderAudioBlock(
    block: TemplateBlock & {type: "audio"},
    mediaContent: Record<string, string>,
): string {
    const audioUrl = mediaContent[block.id] || block.url;
    if (!audioUrl) {
        return "";
    }

    return `
        <div class="broadcast-audio-block" data-block-id="${block.id}">
            <audio controls>
                <source src="${escapeHtml(audioUrl)}">
                Your browser does not support the audio tag.
            </audio>
        </div>
    `;
}

/**
 * Render button block
 */
function renderButtonBlock(
    block: TemplateBlock & {type: "button"},
    mediaContent: Record<string, string>,
    messageId: number,
): string {
    const buttonText = escapeHtml(block.text || "Click Here");
    const buttonUrl = mediaContent[block.id] || block.url || "";
    const actionType = block.actionType || "url";
    const quickReplyText = block.quickReplyText || buttonText;

    const {backgroundColor, textColor, borderRadius, size} = block.style;

    // Map size to CSS class
    const sizeClass = `btn-${size || "medium"}`;

    // Inline styles
    const styles = `
        background-color: ${backgroundColor || "#007bff"};
        color: ${textColor || "#ffffff"};
        border-radius: ${borderRadius || 4}px;
    `;

    // Data attributes for click handling
    const dataAttrs = `
        data-block-id="${block.id}"
        data-action-type="${actionType}"
        data-button-text="${buttonText}"
        data-button-url="${escapeHtml(buttonUrl)}"
        data-quick-reply-text="${escapeHtml(quickReplyText)}"
        data-message-id="${messageId}"
    `;

    return `
        <div class="broadcast-button-block" data-block-id="${block.id}">
            <button
                class="broadcast-button ${sizeClass}"
                style="${styles}"
                ${dataAttrs}
            >
                ${buttonText}
                ${actionType === "url" ? '<i class="fa fa-external-link"></i>' : ""}
                ${actionType === "quick_reply" ? '<i class="fa fa-reply"></i>' : ""}
            </button>
        </div>
    `;
}

/**
 * Render SVG block
 */
function renderSVGBlock(
    block: TemplateBlock & {type: "svg"},
    mediaContent: Record<string, string>,
): string {
    const svgContent = mediaContent[block.id] || block.content;
    if (!svgContent) {
        return "";
    }

    // If it's a URL, render as img tag
    if (svgContent.startsWith("http") || svgContent.startsWith("/")) {
        const maxDimensions = block.maxDimensions
            ? `style="max-width: ${block.maxDimensions.width}px; max-height: ${block.maxDimensions.height}px;"`
            : "";
        return `
            <div class="broadcast-svg-block" data-block-id="${block.id}">
                <img src="${escapeHtml(svgContent)}" ${maxDimensions} />
            </div>
        `;
    }

    // Otherwise, render inline SVG
    // Note: In production, this should be sanitized more thoroughly
    return `
        <div class="broadcast-svg-block" data-block-id="${block.id}">
            ${svgContent}
        </div>
    `;
}

/**
 * Simple HTML escape function
 */
function escapeHtml(text: string | undefined): string {
    if (!text) {
        return "";
    }
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

/**
 * Initialize button click handlers for a message
 * This should be called after the message is rendered to the DOM
 */
export function initializeButtonHandlers($messageContainer: JQuery): void {
    $messageContainer.find(".broadcast-button").on("click", function (e) {
        e.preventDefault();
        const $button = $(this);

        const messageId = Number.parseInt($button.data("message-id"), 10);
        const blockId = $button.data("block-id");
        const actionType = $button.data("action-type");
        const buttonText = $button.data("button-text");
        const buttonUrl = $button.data("button-url");
        const quickReplyText = $button.data("quick-reply-text");

        // Disable button to prevent multiple clicks
        $button.prop("disabled", true);

        if (actionType === "url") {
            // Track click and open URL
            trackButtonClick(messageId, blockId, actionType, buttonText, buttonUrl)
                .then(() => {
                    window.open(buttonUrl, "_blank");
                })
                .catch((error) => {
                    console.error("Error tracking button click:", error);
                })
                .finally(() => {
                    // Re-enable button after a short delay
                    setTimeout(() => {
                        $button.prop("disabled", false);
                    }, 1000);
                });
        } else if (actionType === "quick_reply") {
            // Handle quick reply
            handleQuickReply(messageId, blockId, quickReplyText)
                .then(() => {
                    // Show feedback
                    $button.text("Sent ✓");
                    $button.addClass("success");
                })
                .catch((error) => {
                    console.error("Error sending quick reply:", error);
                    $button.prop("disabled", false);
                });
        }
    });
}

/**
 * Track button click via API
 */
async function trackButtonClick(
    messageId: number,
    buttonId: string,
    buttonType: string,
    buttonText: string,
    buttonUrl: string,
): Promise<void> {
    const response = await fetch("/json/broadcast/button_click", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            message_id: messageId,
            button_id: buttonId,
            button_type: buttonType,
            button_text: buttonText,
            button_url: buttonUrl,
        }),
    });

    if (!response.ok) {
        throw new Error("Failed to track button click");
    }
}

/**
 * Handle quick reply button
 */
async function handleQuickReply(
    messageId: number,
    buttonId: string,
    replyText: string,
): Promise<void> {
    const response = await fetch("/json/broadcast/quick_reply", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            message_id: messageId,
            button_id: buttonId,
            reply_text: replyText,
        }),
    });

    if (!response.ok) {
        throw new Error("Failed to send quick reply");
    }

    // TODO: Actually send the reply message through the compose system
    // For now, the backend just tracks the click
}
