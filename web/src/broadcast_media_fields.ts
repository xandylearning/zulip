// Media field components for dynamic notification form

import $ from "jquery";

import {$t} from "./i18n.ts";
import type {
    AudioBlock,
    ButtonBlock,
    ImageBlock,
    SVGBlock,
    TemplateBlock,
    TemplateStructure,
    TextBlock,
    VideoBlock,
} from "./broadcast_template_blocks.ts";
import {
    getMediaBlocks,
    getRequiredMediaBlocks,
    isAudioBlock,
    isButtonBlock,
    isImageBlock,
    isSVGBlock,
    isTextBlock,
    isVideoBlock,
} from "./broadcast_template_blocks.ts";

// Store uploaded media URLs mapped by block ID
const mediaContent: Record<string, string> = {};
const uploadedFiles: Record<string, File> = {};

// Render dynamic media fields based on template structure
export function renderMediaFields(templateStructure: TemplateStructure): string {
    if (!templateStructure || !templateStructure.blocks) {
        return "";
    }

    const blocks = templateStructure.blocks;
    let fieldsHtml = "";

    // Render editable text blocks
    const textBlocks = blocks.filter(isTextBlock);
    if (textBlocks.length > 0) {
        fieldsHtml += `
            <div class="media-fields-section">
                <h4 class="media-fields-heading">${$t({defaultMessage: "Text Blocks (Editable)"})}</h4>
                ${textBlocks.map((block) => renderTextField(block)).join("")}
            </div>
        `;
    }

    // Render media upload fields
    const mediaBlocks = getMediaBlocks(templateStructure);
    if (mediaBlocks.length > 0) {
        fieldsHtml += `
            <div class="media-fields-section">
                <h4 class="media-fields-heading">${$t({defaultMessage: "Media Fields"})}</h4>
                ${mediaBlocks.map((block) => renderMediaField(block)).join("")}
            </div>
        `;
    }

    // Render editable buttons
    const buttonBlocks = blocks.filter(isButtonBlock);
    if (buttonBlocks.length > 0) {
        fieldsHtml += `
            <div class="media-fields-section">
                <h4 class="media-fields-heading">${$t({defaultMessage: "Buttons (Editable)"})}</h4>
                ${buttonBlocks.map((block) => renderButtonField(block)).join("")}
            </div>
        `;
    }

    return fieldsHtml;
}

// Render text field
function renderTextField(block: TextBlock): string {
    return `
        <div class="form-group template-text-field" data-block-id="${block.id}">
            <label for="text-field-${block.id}">${$t({defaultMessage: "Text Content"})}</label>
            <textarea
                id="text-field-${block.id}"
                class="form-control template-text-content"
                rows="4"
                placeholder="${$t({defaultMessage: "Edit text content..."})}"
                spellcheck="false"
            >${block.content}</textarea>
            <small class="form-text">${$t({defaultMessage: "Supports Markdown formatting"})}</small>
        </div>
    `;
}

// Render media upload field
function renderMediaField(block: TemplateBlock): string {
    if (isImageBlock(block)) {
        return renderImageField(block);
    } else if (isVideoBlock(block)) {
        return renderVideoField(block);
    } else if (isAudioBlock(block)) {
        return renderAudioField(block);
    } else if (isSVGBlock(block)) {
        return renderSVGField(block);
    }
    return "";
}

// Render image upload field
function renderImageField(block: ImageBlock): string {
    const requiredBadge = block.required
        ? `<span class="required-badge">*</span>`
        : `<span class="optional-badge">${$t({defaultMessage: "(optional)"})}</span>`;

    return `
        <div class="form-group media-upload-field" data-block-id="${block.id}" data-field-type="image">
            <label for="media-field-${block.id}">
                ${block.label} ${requiredBadge}
            </label>

            <div class="media-upload-container">
                <div class="upload-dropzone" id="dropzone-${block.id}">
                    <div class="dropzone-content">
                        <div class="dropzone-icon"></div>
                        <p class="dropzone-text">${$t({defaultMessage: "Drag & drop image here or"})}</p>
                        <button type="button" class="btn btn-default upload-trigger" data-block-id="${block.id}">
                            ${$t({defaultMessage: "Browse Files"})}
                        </button>
                        <input
                            type="file"
                            id="media-field-${block.id}"
                            class="media-file-input"
                            accept="image/jpeg,image/png,image/gif,image/webp,image/avif,image/svg+xml"
                            style="display: none;"
                        />
                    </div>
                    <div class="upload-preview" id="preview-${block.id}" style="display: none;">
                        <img src="" alt="${$t({defaultMessage: "Preview"})}" class="preview-image" />
                        <button type="button" class="btn-icon remove-upload" data-block-id="${block.id}" title="${$t({defaultMessage: "Remove"})}">×</button>
                        <div class="upload-filename"></div>
                    </div>
                    <div class="upload-progress" id="progress-${block.id}" style="display: none;">
                        <div class="progress-bar"></div>
                        <span class="progress-text">0%</span>
                    </div>
                </div>
                <small class="form-text">${$t({defaultMessage: "Accepted: JPG, PNG, GIF, WebP, AVIF, SVG"})}</small>
            </div>
        </div>
    `;
}

// Render video upload/URL field
function renderVideoField(block: VideoBlock): string {
    const requiredBadge = block.required
        ? `<span class="required-badge">*</span>`
        : `<span class="optional-badge">${$t({defaultMessage: "(optional)"})}</span>`;

    const showUrlOption = block.allowUrl;
    const showUploadOption = block.allowUpload;

    return `
        <div class="form-group media-upload-field" data-block-id="${block.id}" data-field-type="video">
            <label for="media-field-${block.id}">
                ${block.label} ${requiredBadge}
            </label>

            ${showUrlOption && showUploadOption ? `
                <div class="video-input-options">
                    <label class="radio-label">
                        <input type="radio" name="video-source-${block.id}" value="upload" class="video-source-radio" checked />
                        ${$t({defaultMessage: "Upload File"})}
                    </label>
                    <label class="radio-label">
                        <input type="radio" name="video-source-${block.id}" value="url" class="video-source-radio" />
                        ${$t({defaultMessage: "YouTube/Vimeo URL"})}
                    </label>
                </div>
            ` : ""}

            <div class="media-upload-container video-upload-section" ${!showUploadOption ? 'style="display:none;"' : ""}>
                <div class="upload-dropzone" id="dropzone-${block.id}">
                    <div class="dropzone-content">
                        <div class="dropzone-icon"></div>
                        <p class="dropzone-text">${$t({defaultMessage: "Drag & drop video here or"})}</p>
                        <button type="button" class="btn btn-default upload-trigger" data-block-id="${block.id}">
                            ${$t({defaultMessage: "Browse Files"})}
                        </button>
                        <input
                            type="file"
                            id="media-field-${block.id}"
                            class="media-file-input"
                            accept="video/mp4,video/webm"
                            style="display: none;"
                        />
                    </div>
                    <div class="upload-preview" id="preview-${block.id}" style="display: none;">
                        <video class="preview-video" controls></video>
                        <button type="button" class="btn-icon remove-upload" data-block-id="${block.id}" title="${$t({defaultMessage: "Remove"})}">×</button>
                        <div class="upload-filename"></div>
                    </div>
                </div>
                <small class="form-text">${$t({defaultMessage: "Accepted: MP4, WebM (max 50MB)"})}</small>
            </div>

            ${showUrlOption ? `
                <div class="media-url-container video-url-section" ${showUploadOption ? 'style="display:none;"' : ""}>
                    <input
                        type="url"
                        id="video-url-${block.id}"
                        class="form-control media-url-input"
                        placeholder="${$t({defaultMessage: "https://www.youtube.com/watch?v=... or https://vimeo.com/..."})}"
                    />
                    <small class="form-text">${$t({defaultMessage: "Paste YouTube or Vimeo URL"})}</small>
                </div>
            ` : ""}
        </div>
    `;
}

// Render audio upload field
function renderAudioField(block: AudioBlock): string {
    const requiredBadge = block.required
        ? `<span class="required-badge">*</span>`
        : `<span class="optional-badge">${$t({defaultMessage: "(optional)"})}</span>`;

    return `
        <div class="form-group media-upload-field" data-block-id="${block.id}" data-field-type="audio">
            <label for="media-field-${block.id}">
                ${block.label} ${requiredBadge}
            </label>

            <div class="media-upload-container">
                <div class="upload-dropzone" id="dropzone-${block.id}">
                    <div class="dropzone-content">
                        <div class="dropzone-icon"></div>
                        <p class="dropzone-text">${$t({defaultMessage: "Drag & drop audio here or"})}</p>
                        <button type="button" class="btn btn-default upload-trigger" data-block-id="${block.id}">
                            ${$t({defaultMessage: "Browse Files"})}
                        </button>
                        <input
                            type="file"
                            id="media-field-${block.id}"
                            class="media-file-input"
                            accept="audio/mpeg,audio/wav,audio/ogg"
                            style="display: none;"
                        />
                    </div>
                    <div class="upload-preview" id="preview-${block.id}" style="display: none;">
                        <audio class="preview-audio" controls></audio>
                        <button type="button" class="btn-icon remove-upload" data-block-id="${block.id}" title="${$t({defaultMessage: "Remove"})}">×</button>
                        <div class="upload-filename"></div>
                    </div>
                </div>
                <small class="form-text">${$t({defaultMessage: "Accepted: MP3, WAV, OGG (max 10MB)"})}</small>
            </div>
        </div>
    `;
}

// Render SVG upload field
function renderSVGField(block: SVGBlock): string {
    const requiredBadge = block.required
        ? `<span class="required-badge">*</span>`
        : `<span class="optional-badge">${$t({defaultMessage: "(optional)"})}</span>`;

    return `
        <div class="form-group media-upload-field" data-block-id="${block.id}" data-field-type="svg">
            <label for="media-field-${block.id}">
                ${block.label} ${requiredBadge}
            </label>

            ${block.allowInline ? `
                <div class="svg-input-options">
                    <label class="radio-label">
                        <input type="radio" name="svg-source-${block.id}" value="upload" class="svg-source-radio" checked />
                        ${$t({defaultMessage: "Upload SVG File"})}
                    </label>
                    <label class="radio-label">
                        <input type="radio" name="svg-source-${block.id}" value="inline" class="svg-source-radio" />
                        ${$t({defaultMessage: "Inline SVG Code"})}
                    </label>
                </div>
            ` : ""}

            <div class="media-upload-container svg-upload-section">
                <div class="upload-dropzone" id="dropzone-${block.id}">
                    <div class="dropzone-content">
                        <div class="dropzone-icon"></div>
                        <p class="dropzone-text">${$t({defaultMessage: "Drag & drop SVG here or"})}</p>
                        <button type="button" class="btn btn-default upload-trigger" data-block-id="${block.id}">
                            ${$t({defaultMessage: "Browse Files"})}
                        </button>
                        <input
                            type="file"
                            id="media-field-${block.id}"
                            class="media-file-input"
                            accept="image/svg+xml"
                            style="display: none;"
                        />
                    </div>
                    <div class="upload-preview" id="preview-${block.id}" style="display: none;">
                        <div class="preview-svg-container"></div>
                        <button type="button" class="btn-icon remove-upload" data-block-id="${block.id}" title="${$t({defaultMessage: "Remove"})}">×</button>
                        <div class="upload-filename"></div>
                    </div>
                </div>
            </div>

            ${block.allowInline ? `
                <div class="svg-inline-section" style="display:none;">
                    <textarea
                        id="svg-inline-${block.id}"
                        class="form-control svg-inline-input"
                        rows="6"
                        placeholder="${$t({defaultMessage: '<svg>...</svg>'})}"
                        spellcheck="false"
                    ></textarea>
                    <small class="form-text">${$t({defaultMessage: "Paste SVG code"})}</small>
                </div>
            ` : ""}
        </div>
    `;
}

// Render button field
function renderButtonField(block: ButtonBlock): string {
    const isUrlAction = !block.actionType || block.actionType === "url";
    const actionBadge = isUrlAction ? $t({defaultMessage: "URL"}) : $t({defaultMessage: "Quick Reply"});
    return `
        <div class="form-group template-button-field" data-block-id="${block.id}">
            <label for="button-url-${block.id}">${block.text} <span class="badge" style="margin-left: 6px;">${actionBadge}</span></label>
            ${isUrlAction ? `
            <input
                type="url"
                id="button-url-${block.id}"
                class="form-control template-button-url"
                value="${block.url}"
                placeholder="${$t({defaultMessage: "https://example.com"})}"
            />
            <small class="form-text">${$t({defaultMessage: "Enter the link URL for this button"})}</small>
            ` : `
            <div class="form-text">${$t({defaultMessage: "No URL needed. Quick reply sends:"})} "${block.quickReplyText || block.text}"</div>
            `}
        </div>
    `;
}

// Remove uploaded file
function removeUpload(blockId: string): void {
    delete uploadedFiles[blockId];
    delete mediaContent[blockId];

    const $preview = $(`#preview-${blockId}`);
    const $dropzone = $(`#dropzone-${blockId}`);

    $preview.hide();
    $dropzone.find(".dropzone-content").show();

    // Clear file input
    $(`#media-field-${blockId}`).val("");
}

// Setup event handlers for media fields
export function setupMediaFieldHandlers(): void {
    // File upload trigger
    $(document).on("click", ".upload-trigger", function () {
        const blockId = $(this).data("block-id") as string;
        $(`#media-field-${blockId}`).trigger("click");
    });

    // File input change
    $(document).on("change", ".media-file-input", function (e) {
        const input = e.target as HTMLInputElement;
        const file = input.files?.[0];
        if (file !== undefined) {
            const blockId = $(this).attr("id")?.replace("media-field-", "") || "";
            handleFileUpload(blockId, file);
        }
    });

    // Remove upload
    $(document).on("click", ".remove-upload", function () {
        const blockId = $(this).data("block-id") as string;
        removeUpload(blockId);
    });

    // Video source toggle
    $(document).on("change", ".video-source-radio", function () {
        const $container = $(this).closest(".media-upload-field");
        const value = $(this).val();

        if (value === "upload") {
            $container.find(".video-upload-section").show();
            $container.find(".video-url-section").hide();
        } else {
            $container.find(".video-upload-section").hide();
            $container.find(".video-url-section").show();
        }
    });

    // SVG source toggle
    $(document).on("change", ".svg-source-radio", function () {
        const $container = $(this).closest(".media-upload-field");
        const value = $(this).val();

        if (value === "upload") {
            $container.find(".svg-upload-section").show();
            $container.find(".svg-inline-section").hide();
        } else {
            $container.find(".svg-upload-section").hide();
            $container.find(".svg-inline-section").show();
        }
    });

    // Drag and drop handlers
    $(document).on("dragover", ".upload-dropzone", function (e) {
        e.preventDefault();
        $(this).addClass("dragover");
    });

    $(document).on("dragleave", ".upload-dropzone", function () {
        $(this).removeClass("dragover");
    });

    $(document).on("drop", ".upload-dropzone", function (e) {
        e.preventDefault();
        $(this).removeClass("dragover");

        const files = e.originalEvent?.dataTransfer?.files;
        if (files && files.length > 0) {
            const blockId = $(this).attr("id")?.replace("dropzone-", "") || "";
            handleFileUpload(blockId, files[0]!);
        }
    });
}

// Handle file upload
function handleFileUpload(blockId: string, file: File): void {
    // Store file
    uploadedFiles[blockId] = file;

    // Show preview
    const $preview = $(`#preview-${blockId}`);
    const $dropzone = $(`#dropzone-${blockId}`);

    $dropzone.find(".dropzone-content").hide();
    $preview.find(".upload-filename").text(file.name);
    $preview.show();

    // Show file preview based on type
    if (file.type.startsWith("image/")) {
        const reader = new FileReader();
        reader.onload = (e) => {
            $preview.find(".preview-image").attr("src", e.target?.result as string);
        };
        reader.readAsDataURL(file);
    } else if (file.type.startsWith("video/")) {
        const url = URL.createObjectURL(file);
        $preview.find(".preview-video").attr("src", url);
    } else if (file.type.startsWith("audio/")) {
        const url = URL.createObjectURL(file);
        $preview.find(".preview-audio").attr("src", url);
    }
}

// Upload files and return URLs for media content
export async function uploadFilesAndGetUrls(): Promise<Record<string, string>> {
    const uploadedUrls: Record<string, string> = {};
    
    for (const [blockId, file] of Object.entries(uploadedFiles)) {
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/json/user_uploads', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': $('input[name="csrfmiddlewaretoken"]').val() as string,
                },
            });
            
            if (response.ok) {
                const data = await response.json();
                uploadedUrls[blockId] = data.url;
            } else {
                console.error(`Failed to upload file for block ${blockId}:`, response.statusText);
            }
        } catch (error) {
            console.error(`Error uploading file for block ${blockId}:`, error);
        }
    }
    
    return uploadedUrls;
}

// Validate required media fields
export function validateMediaFields(templateStructure: TemplateStructure): {
    valid: boolean;
    errors: string[];
} {
    const errors: string[] = [];
    const requiredBlocks = getRequiredMediaBlocks(templateStructure);

    for (const block of requiredBlocks) {
        const hasFile = uploadedFiles[block.id];
        const hasUrl = mediaContent[block.id];

        if (!hasFile && !hasUrl) {
            const label =
                isImageBlock(block) ||
                isVideoBlock(block) ||
                isAudioBlock(block) ||
                isSVGBlock(block)
                    ? block.label
                    : "Media";
            errors.push(`${label} is required`);
        }
    }

    return {
        valid: errors.length === 0,
        errors,
    };
}

// Get all media content for sending
export function getMediaContent(): Record<string, string> {
    return {...mediaContent};
}

// Get uploaded files for uploading
export function getUploadedFiles(): Record<string, File> {
    return {...uploadedFiles};
}

// Clear all media content
export function clearMediaContent(): void {
    Object.keys(mediaContent).forEach((key) => {
        delete mediaContent[key];
    });
    Object.keys(uploadedFiles).forEach((key) => {
        delete uploadedFiles[key];
    });
}

// Get text content from editable text blocks
export function getTextContent(): Record<string, string> {
    const textContent: Record<string, string> = {};

    $(".template-text-field").each(function () {
        const blockId = $(this).data("block-id") as string;
        const content = $(this).find(".template-text-content").val() as string;
        textContent[blockId] = content;
    });

    return textContent;
}

// Get button URLs from editable buttons
export function getButtonUrls(): Record<string, string> {
    const buttonUrls: Record<string, string> = {};

    $(".template-button-field").each(function () {
        const blockId = $(this).data("block-id") as string;
        const urlInput = $(this).find(".template-button-url");
        if (urlInput.length > 0) {
            const url = urlInput.val() as string;
            buttonUrls[blockId] = url;
        }
    });

    return buttonUrls;
}

// Populate template fields with AI-generated content
export function populateFromMediaContent(aiMediaContent: Record<string, string>): void {
    // Populate text blocks
    $(".template-text-field").each(function () {
        const blockId = $(this).data("block-id") as string;
        const content = aiMediaContent[blockId];
        if (content) {
            $(this).find(".template-text-content").val(content);
        }
    });

    // Populate button URLs
    $(".template-button-field").each(function () {
        const blockId = $(this).data("block-id") as string;
        const url = aiMediaContent[blockId];
        if (url) {
            $(this).find(".template-button-url").val(url);
        }
    });

    // Populate video URLs
    $(".media-url-input").each(function () {
        const blockId = $(this).attr("id")?.replace("video-url-", "") || "";
        const url = aiMediaContent[blockId];
        if (url) {
            $(this).val(url);
        }
    });

    // Populate SVG inline content
    $(".svg-inline-input").each(function () {
        const blockId = $(this).attr("id")?.replace("svg-inline-", "") || "";
        const content = aiMediaContent[blockId];
        if (content) {
            $(this).val(content);
        }
    });
}
