// Rich Media Template Editor Component

import $ from "jquery";

import * as api from "./broadcast_notification_api.ts";
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
    createBlankTemplateStructure,
    DEFAULT_AUDIO_BLOCK,
    DEFAULT_BUTTON_BLOCK,
    DEFAULT_IMAGE_BLOCK,
    DEFAULT_SVG_BLOCK,
    DEFAULT_TEXT_BLOCK,
    DEFAULT_VIDEO_BLOCK,
    generateBlockId,
    isAudioBlock,
    isButtonBlock,
    isImageBlock,
    isSVGBlock,
    isTextBlock,
    isVideoBlock,
    validateTemplateStructure,
} from "./broadcast_template_blocks.ts";

export type EditorMode = "create" | "edit";

interface EditorState {
    mode: EditorMode;
    templateId?: number;
    templateName: string;
    templateStructure: TemplateStructure;
    isDirty: boolean;
}

let editorState: EditorState = {
    mode: "create",
    templateName: "",
    templateStructure: createBlankTemplateStructure(),
    isDirty: false,
};

// Build the rich template editor modal HTML
export function buildRichTemplateEditorModal(
    mode: EditorMode = "create",
    templateName = "",
    _templateStructure?: TemplateStructure,
    _templateId?: number,
): string {
    const title = mode === "create" ? $t({defaultMessage: "Create Rich Media Template"}) : $t({defaultMessage: "Edit Rich Media Template"});

    return `
        <div class="modal-overlay" id="rich-template-editor-overlay">
            <div class="modal rich-template-editor-modal">
                <div class="modal-header">
                    <h3 class="modal-title">${title}</h3>
                    <button class="modal-close" id="rich-template-editor-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="template-editor-container">
                        <div class="template-name-section">
                            <label for="rich-template-name">${$t({defaultMessage: "Template Name"})}</label>
                            <input
                                type="text"
                                id="rich-template-name"
                                class="form-control"
                                value="${templateName.replace(/"/g, "&quot;")}"
                                placeholder="${$t({defaultMessage: "Enter template name"})}"
                                required
                            />
                        </div>

                        <div class="editor-workspace">
                            <div class="editor-panel">
                                <div class="editor-toolbar">
                                    <h4>${$t({defaultMessage: "Add Block"})}</h4>
                                    <div class="block-buttons">
                                        <button type="button" class="btn-add-block" data-block-type="text" title="${$t({defaultMessage: "Add Text Block"})}">
                                            ${$t({defaultMessage: "Text"})}
                                        </button>
                                        <button type="button" class="btn-add-block" data-block-type="image" title="${$t({defaultMessage: "Add Image Field"})}">
                                            ${$t({defaultMessage: "Image"})}
                                        </button>
                                        <button type="button" class="btn-add-block" data-block-type="button" title="${$t({defaultMessage: "Add Button"})}">
                                            ${$t({defaultMessage: "Button"})}
                                        </button>
                                        <button type="button" class="btn-add-block" data-block-type="video" title="${$t({defaultMessage: "Add Video Field"})}">
                                            ${$t({defaultMessage: "Video"})}
                                        </button>
                                        <button type="button" class="btn-add-block" data-block-type="audio" title="${$t({defaultMessage: "Add Audio Field"})}">
                                            ${$t({defaultMessage: "Audio"})}
                                        </button>
                                        <button type="button" class="btn-add-block" data-block-type="svg" title="${$t({defaultMessage: "Add SVG Field"})}">
                                            ${$t({defaultMessage: "SVG"})}
                                        </button>
                                    </div>
                                </div>

                                <div class="blocks-list-header">
                                    <h4>${$t({defaultMessage: "Template Blocks"})}</h4>
                                    <span class="blocks-count">0 ${$t({defaultMessage: "blocks"})}</span>
                                </div>

                                <div class="blocks-list" id="template-blocks-list">
                                    <!-- Blocks will be rendered here -->
                                </div>
                            </div>

                            <div class="preview-panel">
                                <h4>${$t({defaultMessage: "Live Preview"})}</h4>
                                <div class="template-preview" id="template-preview">
                                    <!-- Preview will be rendered here -->
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default" id="rich-template-editor-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary" id="rich-template-editor-save">${$t({defaultMessage: "Save Template"})}</button>
                </div>
            </div>
        </div>
    `;
}

// Render a single block in the editor
function renderBlockInEditor(block: TemplateBlock, index: number): string {
    let blockContent = "";
    let blockLabel = "";

    if (isTextBlock(block)) {
        blockLabel = $t({defaultMessage: "Text Block"});
        blockContent = `
            <div class="block-preview-text">
                "${block.content.substring(0, 50)}${block.content.length > 50 ? "..." : ""}"
            </div>
        `;
    } else if (isImageBlock(block)) {
        blockLabel = $t({defaultMessage: "Image Field"});
        blockContent = `
            <div class="block-info">
                <span class="block-label">${block.label}</span>
                ${block.required ? '<span class="required-badge">*</span>' : '<span class="optional-badge">optional</span>'}
            </div>
        `;
    } else if (isButtonBlock(block)) {
        blockLabel = $t({defaultMessage: "Button"});
        blockContent = `
            <div class="block-info">
                <span class="block-label">"${block.text}"</span>
                <span class="block-detail" style="color: ${block.style.backgroundColor}">●</span>
            </div>
        `;
    } else if (isVideoBlock(block)) {
        blockLabel = $t({defaultMessage: "Video Field"});
        blockContent = `
            <div class="block-info">
                <span class="block-label">${block.label}</span>
                ${block.required ? '<span class="required-badge">*</span>' : '<span class="optional-badge">optional</span>'}
            </div>
        `;
    } else if (isAudioBlock(block)) {
        blockLabel = $t({defaultMessage: "Audio Field"});
        blockContent = `
            <div class="block-info">
                <span class="block-label">${block.label}</span>
                ${block.required ? '<span class="required-badge">*</span>' : '<span class="optional-badge">optional</span>'}
            </div>
        `;
    } else if (isSVGBlock(block)) {
        blockLabel = $t({defaultMessage: "SVG Field"});
        blockContent = `
            <div class="block-info">
                <span class="block-label">${block.label}</span>
                ${block.required ? '<span class="required-badge">*</span>' : '<span class="optional-badge">optional</span>'}
            </div>
        `;
    }

    return `
        <div class="block-item" data-block-id="${block.id}" data-block-index="${index}">
            <div class="block-drag-handle" title="${$t({defaultMessage: "Drag to reorder"})}">☰</div>
            <div class="block-content">
                <div class="block-header">
                    <span class="block-type-label">${blockLabel}</span>
                </div>
                ${blockContent}
            </div>
            <div class="block-actions">
                <button class="btn-icon btn-edit-block" data-block-id="${block.id}" title="${$t({defaultMessage: "Edit"})}"></button>
                <button class="btn-icon btn-delete-block" data-block-id="${block.id}" title="${$t({defaultMessage: "Delete"})}">×</button>
            </div>
        </div>
    `;
}

// Render blocks list
function renderBlocksList(): void {
    const $blocksList = $("#template-blocks-list");
    const blocks = editorState.templateStructure.blocks;

    if (blocks.length === 0) {
        $blocksList.html(`
            <div class="empty-blocks-message">
                <p>${$t({defaultMessage: "No blocks yet. Add blocks using the buttons above."})}</p>
            </div>
        `);
    } else {
        const blocksHtml = blocks.map((block, index) => renderBlockInEditor(block, index)).join("");
        $blocksList.html(blocksHtml);
    }

    // Update blocks count
    $(".blocks-count").text(`${blocks.length} ${$t({defaultMessage: "blocks"})}`);

    // Re-render preview
    renderPreview();
}

// Render preview
function renderPreview(): void {
    const $preview = $("#template-preview");
    const blocks = editorState.templateStructure.blocks;

    if (blocks.length === 0) {
        $preview.html(`<p class="preview-empty">${$t({defaultMessage: "Preview will appear here"})}</p>`);
        return;
    }

    let previewHtml = "";

    for (const block of blocks) {
        if (isTextBlock(block)) {
            previewHtml += `<div class="preview-text">${block.content || $t({defaultMessage: "[Empty text]"})}</div>`;
        } else if (isImageBlock(block)) {
            previewHtml += `
                <div class="preview-image-placeholder">
                    <div class="placeholder-icon"></div>
                    <div class="placeholder-label">${block.label}</div>
                    ${block.required ? '<div class="placeholder-required">Required</div>' : ''}
                </div>
            `;
        } else if (isButtonBlock(block)) {
            previewHtml += `
                <div class="preview-button-container">
                    <button class="preview-button" style="background-color: ${block.style.backgroundColor}; color: ${block.style.textColor}; border-radius: ${block.style.borderRadius}px;">
                        ${block.text}
                    </button>
                </div>
            `;
        } else if (isVideoBlock(block)) {
            previewHtml += `
                <div class="preview-video-placeholder">
                    <div class="placeholder-icon"></div>
                    <div class="placeholder-label">${block.label}</div>
                    ${block.required ? '<div class="placeholder-required">Required</div>' : ''}
                </div>
            `;
        } else if (isAudioBlock(block)) {
            previewHtml += `
                <div class="preview-audio-placeholder">
                    <div class="placeholder-icon"></div>
                    <div class="placeholder-label">${block.label}</div>
                    ${block.required ? '<div class="placeholder-required">Required</div>' : ''}
                </div>
            `;
        } else if (isSVGBlock(block)) {
            previewHtml += `
                <div class="preview-svg-placeholder">
                    <div class="placeholder-icon"></div>
                    <div class="placeholder-label">${block.label}</div>
                    ${block.required ? '<div class="placeholder-required">Required</div>' : ''}
                </div>
            `;
        }
    }

    $preview.html(previewHtml);
}

// Add a new block
function addBlock(blockType: string): void {
    let newBlock: TemplateBlock;
    const blockId = generateBlockId(blockType as any);

    switch (blockType) {
        case "text":
            newBlock = {id: blockId, ...DEFAULT_TEXT_BLOCK};
            break;
        case "image":
            newBlock = {id: blockId, ...DEFAULT_IMAGE_BLOCK};
            break;
        case "button":
            newBlock = {id: blockId, ...DEFAULT_BUTTON_BLOCK};
            break;
        case "video":
            newBlock = {id: blockId, ...DEFAULT_VIDEO_BLOCK};
            break;
        case "audio":
            newBlock = {id: blockId, ...DEFAULT_AUDIO_BLOCK};
            break;
        case "svg":
            newBlock = {id: blockId, ...DEFAULT_SVG_BLOCK};
            break;
        default:
            return;
    }

    editorState.templateStructure.blocks.push(newBlock);
    editorState.isDirty = true;
    renderBlocksList();
}

// Delete a block
function deleteBlock(blockId: string): void {
    editorState.templateStructure.blocks = editorState.templateStructure.blocks.filter(
        (block) => block.id !== blockId,
    );
    editorState.isDirty = true;
    renderBlocksList();
}

// Find block by ID
function findBlock(blockId: string): TemplateBlock | undefined {
    return editorState.templateStructure.blocks.find((block) => block.id === blockId);
}

// Update block
function updateBlock(blockId: string, updates: Partial<TemplateBlock>): void {
    const blockIndex = editorState.templateStructure.blocks.findIndex((block) => block.id === blockId);
    if (blockIndex !== -1) {
        editorState.templateStructure.blocks[blockIndex] = {
            ...editorState.templateStructure.blocks[blockIndex],
            ...updates,
        } as TemplateBlock;
        editorState.isDirty = true;
        renderBlocksList();
    }
}

// Show block settings modal (to be implemented with specific settings per block type)
function showBlockSettings(blockId: string): void {
    const block = findBlock(blockId);
    if (!block) {
        return;
    }

    // Build settings modal based on block type
    let settingsHtml = "";

    if (isTextBlock(block)) {
        settingsHtml = buildTextBlockSettings(block);
    } else if (isImageBlock(block)) {
        settingsHtml = buildImageBlockSettings(block);
    } else if (isButtonBlock(block)) {
        settingsHtml = buildButtonBlockSettings(block);
    } else if (isVideoBlock(block)) {
        settingsHtml = buildVideoBlockSettings(block);
    } else if (isAudioBlock(block)) {
        settingsHtml = buildAudioBlockSettings(block);
    } else if (isSVGBlock(block)) {
        settingsHtml = buildSVGBlockSettings(block);
    }

    $("body").append(settingsHtml);
    setupBlockSettingsHandlers(blockId, block);
}

function buildTextBlockSettings(block: TextBlock): string {
    return `
        <div class="modal-overlay block-settings-overlay" id="block-settings-${block.id}">
            <div class="modal block-settings-modal">
                <div class="modal-header">
                    <h3>${$t({defaultMessage: "Text Block Settings"})}</h3>
                    <button class="modal-close settings-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Content"})}</label>
                        <textarea class="form-control" id="text-content" rows="6" spellcheck="false">${block.content}</textarea>
                        <small class="form-text">${$t({defaultMessage: "Supports Markdown"})}</small>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default settings-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary settings-save">${$t({defaultMessage: "Save"})}</button>
                </div>
            </div>
        </div>
    `;
}

function buildImageBlockSettings(block: ImageBlock): string {
    return `
        <div class="modal-overlay block-settings-overlay" id="block-settings-${block.id}">
            <div class="modal block-settings-modal">
                <div class="modal-header">
                    <h3>${$t({defaultMessage: "Image Field Settings"})}</h3>
                    <button class="modal-close settings-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Field Label"})}</label>
                        <input type="text" class="form-control" id="image-label" value="${block.label}" />
                    </div>
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Alt Text"})}</label>
                        <input type="text" class="form-control" id="image-alt" value="${block.alt}" />
                    </div>
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Max Width (px)"})}</label>
                        <input type="number" class="form-control" id="image-max-width" value="${block.maxWidth || ""}" placeholder="Optional" />
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="image-required" ${block.required ? "checked" : ""} />
                            ${$t({defaultMessage: "Required field"})}
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default settings-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary settings-save">${$t({defaultMessage: "Save"})}</button>
                </div>
            </div>
        </div>
    `;
}

function buildButtonBlockSettings(block: ButtonBlock): string {
    return `
        <div class="modal-overlay block-settings-overlay" id="block-settings-${block.id}">
            <div class="modal block-settings-modal">
                <div class="modal-header">
                    <h3>${$t({defaultMessage: "Button Settings"})}</h3>
                    <button class="modal-close settings-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Button Text"})}</label>
                        <input type="text" class="form-control" id="button-text" value="${block.text}" />
                    </div>
                    <div class="form-group">
                        <label>${$t({defaultMessage: "URL"})}</label>
                        <input type="url" class="form-control" id="button-url" value="${block.url}" placeholder="https://example.com" />
                        <small class="form-text">${$t({defaultMessage: "Can be edited when using template"})}</small>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>${$t({defaultMessage: "Background Color"})}</label>
                            <input type="color" class="form-control" id="button-bg-color" value="${block.style.backgroundColor}" />
                        </div>
                        <div class="form-group">
                            <label>${$t({defaultMessage: "Text Color"})}</label>
                            <input type="color" class="form-control" id="button-text-color" value="${block.style.textColor}" />
                        </div>
                    </div>
                    <div class="form-row">
                        <div class="form-group">
                            <label>${$t({defaultMessage: "Border Radius (px)"})}</label>
                            <input type="number" class="form-control" id="button-border-radius" value="${block.style.borderRadius}" min="0" max="50" />
                        </div>
                        <div class="form-group">
                            <label>${$t({defaultMessage: "Size"})}</label>
                            <select class="form-control" id="button-size">
                                <option value="small" ${block.style.size === "small" ? "selected" : ""}>${$t({defaultMessage: "Small"})}</option>
                                <option value="medium" ${block.style.size === "medium" ? "selected" : ""}>${$t({defaultMessage: "Medium"})}</option>
                                <option value="large" ${block.style.size === "large" ? "selected" : ""}>${$t({defaultMessage: "Large"})}</option>
                            </select>
                        </div>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default settings-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary settings-save">${$t({defaultMessage: "Save"})}</button>
                </div>
            </div>
        </div>
    `;
}

function buildVideoBlockSettings(block: VideoBlock): string {
    return `
        <div class="modal-overlay block-settings-overlay" id="block-settings-${block.id}">
            <div class="modal block-settings-modal">
                <div class="modal-header">
                    <h3>${$t({defaultMessage: "Video Field Settings"})}</h3>
                    <button class="modal-close settings-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Field Label"})}</label>
                        <input type="text" class="form-control" id="video-label" value="${block.label}" />
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="video-allow-url" ${block.allowUrl ? "checked" : ""} />
                            ${$t({defaultMessage: "Allow YouTube/Vimeo URLs"})}
                        </label>
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="video-allow-upload" ${block.allowUpload ? "checked" : ""} />
                            ${$t({defaultMessage: "Allow file upload"})}
                        </label>
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="video-required" ${block.required ? "checked" : ""} />
                            ${$t({defaultMessage: "Required field"})}
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default settings-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary settings-save">${$t({defaultMessage: "Save"})}</button>
                </div>
            </div>
        </div>
    `;
}

function buildAudioBlockSettings(block: AudioBlock): string {
    return `
        <div class="modal-overlay block-settings-overlay" id="block-settings-${block.id}">
            <div class="modal block-settings-modal">
                <div class="modal-header">
                    <h3>${$t({defaultMessage: "Audio Field Settings"})}</h3>
                    <button class="modal-close settings-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Field Label"})}</label>
                        <input type="text" class="form-control" id="audio-label" value="${block.label}" />
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="audio-required" ${block.required ? "checked" : ""} />
                            ${$t({defaultMessage: "Required field"})}
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default settings-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary settings-save">${$t({defaultMessage: "Save"})}</button>
                </div>
            </div>
        </div>
    `;
}

function buildSVGBlockSettings(block: SVGBlock): string {
    return `
        <div class="modal-overlay block-settings-overlay" id="block-settings-${block.id}">
            <div class="modal block-settings-modal">
                <div class="modal-header">
                    <h3>${$t({defaultMessage: "SVG Field Settings"})}</h3>
                    <button class="modal-close settings-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="form-group">
                        <label>${$t({defaultMessage: "Field Label"})}</label>
                        <input type="text" class="form-control" id="svg-label" value="${block.label}" />
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="svg-allow-inline" ${block.allowInline ? "checked" : ""} />
                            ${$t({defaultMessage: "Allow inline SVG code"})}
                        </label>
                    </div>
                    <div class="form-group">
                        <label class="checkbox-label">
                            <input type="checkbox" id="svg-required" ${block.required ? "checked" : ""} />
                            ${$t({defaultMessage: "Required field"})}
                        </label>
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default settings-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary settings-save">${$t({defaultMessage: "Save"})}</button>
                </div>
            </div>
        </div>
    `;
}

function setupBlockSettingsHandlers(blockId: string, block: TemplateBlock): void {
    const $modal = $(`#block-settings-${blockId}`);

    $modal.find(".settings-close, .settings-cancel").on("click", () => {
        $modal.remove();
    });

    $modal.find(".settings-save").on("click", () => {
        let updates: Partial<TemplateBlock> = {};

        if (isTextBlock(block)) {
            updates = {
                content: $modal.find("#text-content").val() as string,
            };
        } else if (isImageBlock(block)) {
            updates = {
                label: $modal.find("#image-label").val() as string,
                alt: $modal.find("#image-alt").val() as string,
                maxWidth: parseInt($modal.find("#image-max-width").val() as string) || undefined,
                required: $modal.find("#image-required").prop("checked") as boolean,
            };
        } else if (isButtonBlock(block)) {
            updates = {
                text: $modal.find("#button-text").val() as string,
                url: $modal.find("#button-url").val() as string,
                style: {
                    backgroundColor: $modal.find("#button-bg-color").val() as string,
                    textColor: $modal.find("#button-text-color").val() as string,
                    borderRadius: parseInt($modal.find("#button-border-radius").val() as string),
                    size: $modal.find("#button-size").val() as "small" | "medium" | "large",
                },
            };
        } else if (isVideoBlock(block)) {
            updates = {
                label: $modal.find("#video-label").val() as string,
                allowUrl: $modal.find("#video-allow-url").prop("checked") as boolean,
                allowUpload: $modal.find("#video-allow-upload").prop("checked") as boolean,
                required: $modal.find("#video-required").prop("checked") as boolean,
            };
        } else if (isAudioBlock(block)) {
            updates = {
                label: $modal.find("#audio-label").val() as string,
                required: $modal.find("#audio-required").prop("checked") as boolean,
            };
        } else if (isSVGBlock(block)) {
            updates = {
                label: $modal.find("#svg-label").val() as string,
                allowInline: $modal.find("#svg-allow-inline").prop("checked") as boolean,
                required: $modal.find("#svg-required").prop("checked") as boolean,
            };
        }

        updateBlock(blockId, updates);
        $modal.remove();
    });
}

// Initialize the editor
export function openRichTemplateEditor(
    mode: EditorMode = "create",
    templateName = "",
    templateStructure?: TemplateStructure,
    templateId?: number,
): void {
    // Initialize editor state
    editorState = {
        mode,
        ...(templateId !== undefined && {templateId}),
        templateName,
        templateStructure: templateStructure || createBlankTemplateStructure(),
        isDirty: false,
    };

    // Build and show modal
    const modalHtml = buildRichTemplateEditorModal(mode, templateName, templateStructure, templateId);
    $("body").append(modalHtml);

    // Initial render
    $("#rich-template-name").val(templateName);
    renderBlocksList();

    setupEditorHandlers();
}

function setupEditorHandlers(): void {
    const $modal = $("#rich-template-editor-overlay");

    // Close handlers
    $modal.find("#rich-template-editor-close, #rich-template-editor-cancel").on("click", () => {
        if (editorState.isDirty) {
            if (!confirm($t({defaultMessage: "You have unsaved changes. Are you sure you want to close?"}))) {
                return;
            }
        }
        $modal.remove();
    });

    // Add block handlers
    $modal.on("click", ".btn-add-block", function () {
        const blockType = $(this).data("block-type") as string;
        addBlock(blockType);
    });

    // Delete block handlers
    $modal.on("click", ".btn-delete-block", function () {
        const blockId = $(this).data("block-id") as string;
        if (confirm($t({defaultMessage: "Are you sure you want to delete this block?"}))) {
            deleteBlock(blockId);
        }
    });

    // Edit block handlers
    $modal.on("click", ".btn-edit-block", function () {
        const blockId = $(this).data("block-id") as string;
        showBlockSettings(blockId);
    });

    // Template name change handler
    $modal.find("#rich-template-name").on("input", function () {
        editorState.templateName = $(this).val() as string;
        editorState.isDirty = true;
    });

    // Save handler
    $modal.find("#rich-template-editor-save").on("click", () => {
        void saveTemplate();
    });
}

async function saveTemplate(): Promise<void> {
    const templateName = $("#rich-template-name").val() as string;

    if (!templateName.trim()) {
        alert($t({defaultMessage: "Please enter a template name"}));
        return;
    }

    const validation = validateTemplateStructure(editorState.templateStructure);
    if (!validation.valid) {
        alert($t({defaultMessage: "Template validation failed:"}) + "\n" + validation.errors.join("\n"));
        return;
    }


    // Show loading state
    const $saveBtn = $("#rich-template-editor-save");
    const originalText = $saveBtn.text();
    $saveBtn.prop("disabled", true).text($t({defaultMessage: "Saving..."}));

    try {
        if (editorState.mode === "edit" && editorState.templateId) {
            // Update existing template
            await api.updateTemplate(editorState.templateId, {
                name: templateName,
                template_type: "rich_media",
                template_structure: editorState.templateStructure as unknown as Record<string, unknown>,
            });
            alert($t({defaultMessage: "Template updated successfully!"}));
        } else {
            // Create new template
            await api.createTemplate({
                name: templateName,
                template_type: "rich_media",
                template_structure: editorState.templateStructure as unknown as Record<string, unknown>,
            });
            alert($t({defaultMessage: "Template created successfully!"}));
        }

        // Close modal
        $("#rich-template-editor-overlay").remove();

        // Reload templates in the background if we're on templates tab
        const templatesTab = $("#templates-tab-content");
        if (templatesTab.is(":visible")) {
            window.location.reload();
        }
    } catch (error) {
        console.error("Failed to save template:", error);
        alert(
            $t({defaultMessage: "Failed to save template:"}) +
                "\n" +
                (error instanceof Error ? error.message : String(error)),
        );
        $saveBtn.prop("disabled", false).text(originalText);
    }
}

// Export function to get current editor state (for testing/debugging)
export function getEditorState(): EditorState {
    return editorState;
}
