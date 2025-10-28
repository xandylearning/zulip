// Main application module for broadcast notification UI

import $ from "jquery";

import * as api from "./broadcast_notification_api.ts";
import * as components from "./broadcast_notification_components.ts";
import * as pills from "./broadcast_notification_pills.ts";
import * as mediaFields from "./broadcast_media_fields.ts";
import * as templateAI from "./broadcast_template_ai.ts";
import {openRichTemplateEditor} from "./broadcast_template_editor.ts";
import type {
    BroadcastNotification,
    NotificationTemplate,
    RecipientType,
    SendNotificationRequest,
} from "./broadcast_notification_types.ts";
import {$t} from "./i18n.ts";

let current_tab: "send" | "templates" | "ai-generator" | "history" = "send";
let current_recipient_type: RecipientType = "all";
let templates: NotificationTemplate[] = [];
let notifications: BroadcastNotification[] = [];

function showTab(tab: "send" | "templates" | "ai-generator" | "history"): void {
    current_tab = tab;

    // Update tab buttons
    $(".tab-button").removeClass("active");
    $(`.tab-button[data-tab="${tab}"]`).addClass("active");

    // Show/hide content
    $(".tab-content").hide();
    $(`#${tab}-tab-content`).show();

    // Load content if needed
    if (tab === "history") {
        void loadNotificationHistory();
    } else if (tab === "templates") {
        void loadTemplates();
    } else if (tab === "ai-generator") {
        loadAIGenerator();
    }
}

function switchRecipientType(type: RecipientType): void {
    current_recipient_type = type;

    // Update button states
    $(".recipient-tab").removeClass("active");
    $(`.recipient-tab[data-type="${type}"]`).addClass("active");

    // Show/hide pill selector
    const $selector = $("#recipient-selector");
    const $container = $("#pill-container");

    if (type === "all") {
        $selector.hide();
        pills.destroyCurrentWidget();
    } else {
        $selector.show();
        $container.empty();

        if (type === "users") {
            const widget = pills.createUserPillWidget($container[0]!);
            pills.populateUserTypeahead(widget);
        } else if (type === "channels") {
            const widget = pills.createStreamPillWidget($container[0]!);
            pills.populateStreamTypeahead(widget);
        }
    }
}

function toggleMarkdownPreview(): void {
    const $content = $("#notification-content");
    const $preview = $("#markdown-preview");
    const $button = $("#toggle-preview");

    if ($preview.is(":visible")) {
        $preview.hide();
        $content.show();
        $button.text($t({defaultMessage: "Preview"}));
    } else {
        const content = $content.val() as string;
        // Simple markdown rendering - just convert basic markdown
        const rendered = content
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            .replace(/\n/g, '<br>');
        $preview.html(rendered);
        $preview.show();
        $content.hide();
        $button.text($t({defaultMessage: "Edit"}));
    }
}

async function handleSendNotification(): Promise<void> {
    const subject = $("#notification-subject").val() as string;
    const template_id = $("#template-select").val() as string;

    // Validation
    if (!subject.trim()) {
        showMessage($t({defaultMessage: "Please enter a subject"}), "error");
        return;
    }

    // Check for content based on template type
    let hasContent = false;
    let content = "";

    if (template_id && template_id.trim()) {
        const template = templates.find((t) => t.id === Number.parseInt(template_id, 10));
        if (template && template.template_type === "rich_media") {
            // For rich media templates, check if any text blocks have content
            const textContent = mediaFields.getTextContent();
            hasContent = Object.values(textContent).some(text => text.trim().length > 0);
            // For rich media templates, we'll build the content from the template structure
            content = ""; // Will be handled by the backend
        } else {
            // For text-only templates or no template, use standard content field
            content = $("#notification-content").val() as string;
            hasContent = content.trim().length > 0;
        }
    } else {
        // No template selected, use standard content field
        content = $("#notification-content").val() as string;
        hasContent = content.trim().length > 0;
    }

    if (!hasContent) {
        showMessage($t({defaultMessage: "Please enter message content"}), "error");
        return;
    }

    let target_type: "users" | "channels" | "broadcast";
    let target_ids: number[] = [];

    if (current_recipient_type === "all") {
        target_type = "broadcast";
        target_ids = [];
    } else if (current_recipient_type === "users") {
        target_type = "users";
        target_ids = pills.getSelectedUserIds();
        if (target_ids.length === 0) {
            showMessage($t({defaultMessage: "Please select at least one user"}), "error");
            return;
        }
    } else {
        target_type = "channels";
        target_ids = pills.getSelectedStreamIds();
        if (target_ids.length === 0) {
            showMessage($t({defaultMessage: "Please select at least one channel"}), "error");
            return;
        }
    }

    // Deduplicate target_ids to prevent duplicate selections from UI
    target_ids = Array.from(new Set(target_ids));

    // Show loading
    const $button = $("#send-notification-btn");
    $button.prop("disabled", true);
    $button.text($t({defaultMessage: "Sending..."}));

    try {
        const request: SendNotificationRequest = {
            subject,
            content,
            target_type,
            target_ids,
        };

        // Only add template_id if it's a valid, non-empty value
        if (template_id && template_id.trim() && template_id !== "null" && template_id !== "undefined") {
            const templateIdNum = Number.parseInt(template_id, 10);

            // Verify it's a valid positive integer
            if (!isNaN(templateIdNum) && templateIdNum > 0 && Number.isFinite(templateIdNum)) {
                request.template_id = templateIdNum;

                const template = templates.find((t) => t.id === templateIdNum);
                if (template && template.template_type === "rich_media") {
                    // For rich media templates, upload files first, then get all content
                    const uploadedUrls = await mediaFields.uploadFilesAndGetUrls();
                    const mediaContent = mediaFields.getMediaContent();
                    const textContent = mediaFields.getTextContent();
                    const buttonUrls = mediaFields.getButtonUrls();

                    // Combine all content for rich media templates, including uploaded files
                    request.media_content = {
                        ...mediaContent,
                        ...textContent,
                        ...buttonUrls,
                        ...uploadedUrls, // Add uploaded file URLs
                    };

                    // For rich media templates, we can set content to empty or a summary
                    // The backend will handle building the actual content from the template structure
                    request.content = "";
                }
            }
        }


        await api.sendNotification(request);

        showMessage($t({defaultMessage: "Notification sent successfully"}), "success");

        // Clear form
        $("#notification-subject").val("");
        $("#notification-content").val("");
        $("#template-select").val("");
        
        // Clear media fields if they exist
        mediaFields.clearMediaContent();
        $("#media-fields-area").empty();
        $("#standard-content-area").show();
        
        pills.destroyCurrentWidget();
        switchRecipientType("all");

        // Reload history
        if (current_tab === "history") {
            await loadNotificationHistory();
        }
    } catch (error) {
        console.error("Failed to send notification", error);
        showMessage(
            $t({defaultMessage: "Failed to send notification"}) + ": " + (error as Error).message,
            "error"
        );
    } finally {
        $button.prop("disabled", false);
        $button.text($t({defaultMessage: "Send Notification"}));
    }
}

function handleTemplateSelect(): void {
    const template_id = $("#template-select").val() as string;

    if (!template_id || template_id.trim() === "") {
        // No template selected - show standard form
        $("#standard-content-area").show();
        $("#media-fields-area").hide().empty();
        $("#preview-template-btn").hide();
        return;
    }

    const template = templates.find((t) => t.id === Number.parseInt(template_id, 10));
    if (!template) {
        return;
    }

    // Check template type
    if (template.template_type === "rich_media" && template.template_structure) {
        // Rich media template - show media fields, hide standard content
        $("#standard-content-area").hide();
        $("#media-fields-area").show();
        $("#preview-template-btn").show();

        // Render media fields
        const fieldsHtml = mediaFields.renderMediaFields(template.template_structure);
        $("#media-fields-area").html(fieldsHtml);

        // Setup media field handlers
        mediaFields.setupMediaFieldHandlers();
    } else {
        // Text-only template - show standard content
        $("#standard-content-area").show();
        $("#media-fields-area").hide().empty();
        $("#preview-template-btn").hide();
        $("#notification-content").val(template.content);
    }
}

async function loadNotificationHistory(): Promise<void> {
    const $container = $("#history-tab-content");
    $container.html(components.buildLoadingSpinner());

    try {
        const response = await api.fetchNotifications();
        notifications = response.notifications;

        if (notifications.length === 0) {
            $container.html(`
                <div class="empty-state">
                    <p>${$t({defaultMessage: "No notifications sent yet"})}</p>
                </div>
            `);
            return;
        }

        const cards = notifications.map((n) => components.buildNotificationCard(n)).join("");
        $container.html(`<div class="notifications-list">${cards}</div>`);
    } catch (error) {
        console.error("Failed to load notification history", error);
        $container.html(
            components.buildErrorMessage(
                $t({defaultMessage: "Failed to load notification history"}),
            ),
        );
    }
}

async function handleViewDetails(notificationId: number): Promise<void> {
    const $details = $(`.notification-details[data-notification-id="${notificationId}"]`);
    const $button = $(`.view-details[data-notification-id="${notificationId}"]`);

    if ($details.is(":visible")) {
        $details.hide();
        $button.text($t({defaultMessage: "View Details"}));
        return;
    }

    $details.show();
    $details.html(components.buildLoadingSpinner());
    $button.text($t({defaultMessage: "Hide Details"}));

    try {
        const [detailResponse, recipientsResponse] = await Promise.all([
            api.fetchNotificationDetails(notificationId),
            api.fetchRecipients(notificationId),
        ]);

        const notification = detailResponse;
        const recipients = recipientsResponse.recipients;

        $details.html(components.buildNotificationDetails(notification, recipients));
    } catch (error) {
        console.error("Failed to load notification details", error);
        $details.html(
            components.buildErrorMessage($t({defaultMessage: "Failed to load details"})),
        );
    }
}

function setupEventHandlers(): void {
    const $app = $("#broadcast-notification-app");

    // Tab switching
    $app.on("click", ".tab-button", function (e) {
        e.preventDefault();
        const tab = $(this).data("tab") as "send" | "templates" | "ai-generator" | "history";
        showTab(tab);
    });

    // Recipient type switching
    $app.on("click", ".recipient-tab", function (e) {
        e.preventDefault();
        const type = $(this).data("type") as RecipientType;
        switchRecipientType(type);
    });

    // Markdown preview toggle
    $app.on("click", "#toggle-preview", function (e) {
        e.preventDefault();
        toggleMarkdownPreview();
    });

    // Template selection
    $app.on("change", "#template-select", function () {
        handleTemplateSelect();
    });

    // Use template button
    $app.on("click", "#use-template-btn", function (e) {
        e.preventDefault();
        showTemplateSelector();
    });

    // Send notification
    $app.on("click", "#send-notification-btn", function (e) {
        e.preventDefault();
        void handleSendNotification();
    });

    // Cancel button
    $app.on("click", "#cancel-btn", function (e) {
        e.preventDefault();
        $("#notification-subject").val("");
        $("#notification-content").val("");
        $("#template-select").val("");
        
        // Clear media fields if they exist
        mediaFields.clearMediaContent();
        $("#media-fields-area").empty();
        $("#standard-content-area").show();
        
        pills.destroyCurrentWidget();
        switchRecipientType("all");
    });

    // AI compose
    $app.on("click", "#ai-compose-btn", async function (e) {
        e.preventDefault();
        const $btn = $(this);
        const promptRaw = ($("#notification-ai-prompt").val() as string) || "";
        const prompt = promptRaw.substring(0, 400);
        const subject = ($("#notification-subject").val() as string) || "";
        const templateVal = $("#template-select").val() as string;
        const templateId = templateVal && templateVal.trim() ? Number.parseInt(templateVal, 10) : undefined;

        let media_content: Record<string, string> | undefined = undefined;
        if (templateId) {
            const template = templates.find((t) => t.id === templateId);
            if (template && template.template_type === "rich_media") {
                media_content = {
                    ...mediaFields.getMediaContent(),
                    ...mediaFields.getTextContent(),
                    ...mediaFields.getButtonUrls(),
                };
            }
        }

        if (!prompt.trim()) {
            showMessage($t({defaultMessage: "Enter a brief prompt for AI compose"}), "error");
            return;
        }

        $btn.prop("disabled", true).text($t({defaultMessage: "Generating..."}));
        try {
            const req: any = { prompt };
            if (subject) {
                req.subject = subject;
            }
            if (templateId) {
                req.template_id = templateId;
            }
            if (media_content) {
                req.media_content = media_content;
            }
            const resp = await api.aiCompose(req);
            if (resp && resp.content) {
                if (!subject || !subject.trim()) {
                    if (resp.subject && resp.subject.trim()) {
                        $("#notification-subject").val(resp.subject.trim());
                    }
                }
                
                // If template is selected, populate template fields instead of message textarea
                if (templateId) {
                    const template = templates.find((t) => t.id === templateId);
                    if (template && template.template_type === "rich_media" && resp.media_content) {
                        // Populate template fields with AI-generated content
                        mediaFields.populateFromMediaContent(resp.media_content);
                        showMessage($t({defaultMessage: "AI content generated and populated template fields"}), "success");
                    } else {
                        // Text template or no media_content, use message textarea
                        $("#notification-content").val(resp.content);
                        $("#standard-content-area").show();
                        showMessage($t({defaultMessage: "AI content generated"}), "success");
                    }
                } else {
                    // No template selected, use message textarea
                    $("#notification-content").val(resp.content);
                    $("#standard-content-area").show();
                    showMessage($t({defaultMessage: "AI content generated"}), "success");
                }
            } else {
                showMessage($t({defaultMessage: "AI did not return content"}), "error");
            }
        } catch (err) {
            console.error("AI compose failed", err);
            showMessage($t({defaultMessage: "Failed to generate with AI"}) + ": " + (err as Error).message, "error");
        } finally {
            $btn.prop("disabled", false).text($t({defaultMessage: "Generate with AI"}));
        }
    });

    // View notification details
    $app.on("click", ".view-details", function (e) {
        e.preventDefault();
        const notificationId = Number.parseInt($(this).data("notification-id") as string, 10);
        void handleViewDetails(notificationId);
    });
}

async function initialize(): Promise<void> {
    const $app = $("#broadcast-notification-app");
    
    if ($app.length === 0) {
        return;
    }

    // Build initial UI
    const html = `
        ${components.buildHeader()}
        ${components.buildTabs()}
        <div class="broadcast-notification-content">
            <div id="send-tab-content" class="tab-content active">
                ${components.buildNotificationForm([])}
            </div>
            <div id="templates-tab-content" class="tab-content" style="display: none;">
                ${components.buildTemplateTab()}
            </div>
            <div id="ai-generator-tab-content" class="tab-content" style="display: none;">
                <!-- AI Generator content will be loaded dynamically -->
            </div>
            <div id="history-tab-content" class="tab-content" style="display: none;">
                ${components.buildLoadingSpinner()}
            </div>
        </div>
    `;

    $app.html(html);

    // Setup event handlers
    setupEventHandlers();

    // Load templates
    try {
        const response = await api.fetchTemplates();
        templates = response.templates;

        // Rebuild form with templates
        $("#send-tab-content").html(components.buildNotificationForm(templates));
    } catch (error) {
        console.error("Failed to load templates", error);
    }

    // Initialize with "all users" recipient type
    switchRecipientType("all");
}

function showMessage(message: string, type: "success" | "error"): void {
    const $container = $("#send-tab-content");
    const messageClass = type === "success" ? "success-message" : "error-message";
    const icon = type === "success" ? "fa-check-circle" : "fa-exclamation-circle";
    
    const $message = $(`
        <div class="${messageClass}">
            <i class="fa ${icon}"></i>
            <span>${message}</span>
        </div>
    `);
    
    // Remove any existing messages
    $container.find(".success-message, .error-message").remove();
    
    // Add new message
    $container.prepend($message);
    
    // Auto-remove after 5 seconds
    setTimeout(() => {
        $message.fadeOut(() => $message.remove());
    }, 5000);
}

// Template Management Functions
async function loadTemplates(): Promise<void> {
    const $container = $("#templates-table-container");

    try {
        const response = await api.fetchTemplates();
        templates = response.templates;
        $container.html(components.buildTemplateTable(templates));
        setupTemplateEventHandlers();
    } catch (error) {
        console.error("Failed to load templates", error);
        $container.html(`
            <div class="alert alert-error">
                ${$t({defaultMessage: "Failed to load templates"})}: ${(error as Error).message}
            </div>
        `);
    }
}

// AI Generator Functions
function loadAIGenerator(): void {
    const $container = $("#ai-generator-tab-content");

    // Render AI generator page
    $container.html(templateAI.buildAIGeneratorTab());

    // Setup event handlers
    templateAI.setupAIGeneratorHandlers();
}

function setupTemplateEventHandlers(): void {
    // Add text template button
    $("#add-text-template-btn").off("click").on("click", () => {
        showTemplateModal();
    });

    // Add rich media template button
    $("#add-rich-template-btn").off("click").on("click", () => {
        openRichTemplateEditor("create");
    });

    // Edit template buttons
    $(".edit-template").on("click", function() {
        const templateId = Number.parseInt($(this).data("template-id"), 10);
        const template = templates.find(t => t.id === templateId);
        if (template) {
            // Check if it's a rich media template
            if (template.template_type === "rich_media") {
                openRichTemplateEditor(
                    "edit",
                    template.name,
                    template.template_structure,
                    template.id
                );
            } else {
                showTemplateModal(template);
            }
        }
    });

    // Delete template buttons
    $(".delete-template").on("click", function() {
        const templateId = Number.parseInt($(this).data("template-id"), 10);
        const template = templates.find(t => t.id === templateId);
        if (template) {
            showDeleteConfirmModal(templateId, template.name);
        }
    });

    // Search functionality
    $("#template-search").on("input", function() {
        const query = $(this).val() as string;
        filterTemplates(query);
    });
}

function showTemplateModal(template?: NotificationTemplate): void {
    const modal = components.buildTemplateModal(template);
    $("body").append(modal);
    
    // Setup modal event handlers
    $("#template-modal-close, #template-modal-cancel").on("click", closeTemplateModal);
    $("#template-modal-save").on("click", () => saveTemplate(template?.id));
    
    // Close on overlay click
    $("#template-modal-overlay").on("click", function(e) {
        if (e.target === this) {
            closeTemplateModal();
        }
    });
}

function closeTemplateModal(): void {
    $("#template-modal-overlay").remove();
}

async function saveTemplate(templateId?: number): Promise<void> {
    const name = $("#template-name").val() as string;
    const content = $("#template-content").val() as string;

    if (!name.trim() || !content.trim()) {
        showMessage($t({defaultMessage: "Please fill in all fields"}), "error");
        return;
    }

    try {
        if (templateId) {
            await api.updateTemplate(templateId, { name, content });
            showMessage($t({defaultMessage: "Template updated successfully"}), "success");
        } else {
            await api.createTemplate({ name, content });
            showMessage($t({defaultMessage: "Template created successfully"}), "success");
        }
        
        closeTemplateModal();
        await loadTemplates();
    } catch (error) {
        console.error("Failed to save template", error);
        showMessage(
            $t({defaultMessage: "Failed to save template"}) + ": " + (error as Error).message,
            "error"
        );
    }
}

function showDeleteConfirmModal(templateId: number, templateName: string): void {
    const modal = components.buildDeleteConfirmModal(templateId, templateName);
    $("body").append(modal);
    
    // Setup modal event handlers
    $("#delete-modal-close, #delete-modal-cancel").on("click", closeDeleteModal);
    $("#delete-modal-confirm").on("click", () => deleteTemplate(templateId));
    
    // Close on overlay click
    $("#delete-modal-overlay").on("click", function(e) {
        if (e.target === this) {
            closeDeleteModal();
        }
    });
}

function closeDeleteModal(): void {
    $("#delete-modal-overlay").remove();
}

async function deleteTemplate(templateId: number): Promise<void> {
    try {
        await api.deleteTemplate(templateId);
        showMessage($t({defaultMessage: "Template deleted successfully"}), "success");
        closeDeleteModal();
        await loadTemplates();
    } catch (error) {
        console.error("Failed to delete template", error);
        showMessage(
            $t({defaultMessage: "Failed to delete template"}) + ": " + (error as Error).message,
            "error"
        );
    }
}

function filterTemplates(query: string): void {
    const filteredTemplates = templates.filter(template =>
        template.name.toLowerCase().includes(query.toLowerCase()) ||
        template.content.toLowerCase().includes(query.toLowerCase())
    );
    
    const $container = $("#templates-table-container");
    $container.html(components.buildTemplateTable(filteredTemplates));
    setupTemplateEventHandlers();
}

function showTemplateSelector(): void {
    if (templates.length === 0) {
        showMessage($t({defaultMessage: "No templates available. Create a template first."}), "error");
        return;
    }

    const modal = components.buildTemplateSelectorModal(templates);
    $("body").append(modal);
    
    // Setup modal event handlers
    $("#template-selector-close, #template-selector-cancel").on("click", closeTemplateSelector);
    
    // Template selection
    $(".template-item").on("click", function() {
        const templateId = Number.parseInt($(this).data("template-id"), 10);
        const template = templates.find(t => t.id === templateId);
        if (template) {
            selectTemplate(template);
            closeTemplateSelector();
        }
    });
    
    // Close on overlay click
    $("#template-selector-overlay").on("click", function(e) {
        if (e.target === this) {
            closeTemplateSelector();
        }
    });
}

function closeTemplateSelector(): void {
    $("#template-selector-overlay").remove();
}

function selectTemplate(template: NotificationTemplate): void {
    $("#template-select").val(template.id.toString());
    $("#notification-subject").val(template.name);
    $("#notification-content").val(template.content);
    showMessage($t({defaultMessage: "Template applied successfully"}), "success");
}

$(() => {
    void initialize();
});

