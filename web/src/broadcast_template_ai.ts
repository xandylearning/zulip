// AI Template Generator UI Component - Conversational Interface with Live Preview

import $ from "jquery";

import {$t} from "./i18n.ts";
import {openRichTemplateEditor} from "./broadcast_template_editor.ts";
import {aiGenerateTemplate, createTemplate} from "./broadcast_notification_api.ts";
import type {AIGenerateTemplateResponse} from "./broadcast_notification_api.ts";
import type {TemplateStructure} from "./broadcast_template_blocks.ts";

// Conversation state
interface ConversationMessage {
    role: 'user' | 'ai';
    content: string;
    timestamp: Date;
    followups?: string[] | undefined;
    validation_errors?: string[] | undefined;
}

interface AIState {
    conversationHistory: ConversationMessage[];
    currentTemplate: AIGenerateTemplateResponse['template'] | null;
    currentPlan: AIGenerateTemplateResponse['plan'] | null;
    conversationId: string | null;
    isGenerating: boolean;
    isGeneratingTemplate: boolean;
    isPlanningInProgress: boolean;
    isWaitingForPlanApproval: boolean;
    currentFollowupIndex: number;
    followupQuestions: string[];
    followupAnswers: Record<string, string>;
    attachmentModal: {
        isOpen: boolean;
        type: string | null;
        description: string | null;
        currentUrl: string;
        currentFile: File | null;
    };
}

let aiState: AIState = {
    conversationHistory: [],
    currentTemplate: null,
    currentPlan: null,
    conversationId: null,
    isGenerating: false,
    isGeneratingTemplate: false,
    isPlanningInProgress: false,
    isWaitingForPlanApproval: false,
    currentFollowupIndex: 0,
    followupQuestions: [],
    followupAnswers: {},
    attachmentModal: {
        isOpen: false,
        type: null,
        description: null,
        currentUrl: "",
        currentFile: null,
    },
};

// Build AI Generator tab with conversational UI
export function buildAIGeneratorTab(): string {
    return `
        <div class="ai-generator-page">
            <div class="ai-generator-split-view">
                <!-- Left Panel: Conversation -->
                <div class="ai-conversation-panel">
                    <div class="ai-panel-header">
                        <h3>${$t({defaultMessage: "AI Template Generator"})} <span class="beta-badge">${$t({defaultMessage: "Beta"})}</span></h3>
                        <p class="ai-description">${$t({defaultMessage: "Describe the template you want, and AI will help you create it."})}</p>
                    </div>

                    <div class="conversation-container">
                        <div class="conversation-messages" id="conversation-messages">
                            <div class="conversation-empty">
                                <div class="empty-icon">[Chat]</div>
                                <p>${$t({defaultMessage: "Start a conversation with AI"})}</p>
                                <small>${$t({defaultMessage: "Describe your template and we'll help you build it step by step"})}</small>
                            </div>
                        </div>

                        <!-- Planning Animation -->
                        <div class="planning-animation" id="planning-animation" style="display: none;">
                            <div class="animation-container">
                                <p class="shimmer-text">${$t({defaultMessage: "AI is analyzing your request and creating a plan..."})}</p>
                                <small>${$t({defaultMessage: "This may take a few moments"})}</small>
                            </div>
                        </div>

                        <!-- Plan Display -->
                        <div class="plan-display" id="plan-display" style="display: none;">
                            <div class="plan-card">
                                <h4>${$t({defaultMessage: "Proposed Template Plan"})}</h4>
                                <div class="plan-details" id="plan-details"></div>
                                <div class="plan-actions">
                                    <button type="button" class="btn btn-primary" id="approve-plan-btn">
                                        ${$t({defaultMessage: "Approve & Generate"})}
                                    </button>
                                    <button type="button" class="btn btn-default" id="reject-plan-btn">
                                        ${$t({defaultMessage: "Request Changes"})}
                                    </button>
                                </div>
                            </div>
                        </div>

                        <div class="conversation-input">
                            <div class="input-container">
                                <textarea
                                    id="ai-message-input"
                                    class="message-input"
                                    rows="3"
                                    placeholder="${$t({defaultMessage: "Describe your template... (e.g., Create a welcome template with a hero image, welcome message, and a call-to-action button)"})}"
                                ></textarea>
                                <button type="button" class="btn-send-message" id="send-message-btn">
                                    <span class="send-icon">➤</span>
                                </button>
                            </div>
                            <div class="input-hints">
                                <small>${$t({defaultMessage: "Press Ctrl+Enter to send"})}</small>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Panel: Live Preview -->
                <div class="ai-preview-panel">
                    <div class="ai-panel-header">
                        <h3>${$t({defaultMessage: "Live Preview"})}</h3>
                        <p class="ai-description">${$t({defaultMessage: "See how your template will look"})}</p>
                    </div>

                    <div class="preview-container" id="ai-preview-container">
                        <div class="preview-empty">
                            <div class="empty-icon">[Preview]</div>
                            <p>${$t({defaultMessage: "Preview will appear here"})}</p>
                            <small>${$t({defaultMessage: "Start a conversation to see your template preview"})}</small>
                        </div>
                    </div>

                    <!-- Generation Animation (shown while AI is generating template) -->
                    <div class="generation-animation" id="generation-animation" style="display: none;">
                        <div class="animation-container">
                            <div class="generation-progress">
                                <div class="progress-bar">
                                    <div class="progress-fill"></div>
                                </div>
                                <p class="generation-status">${$t({defaultMessage: "AI is creating your template..."})}</p>
                                <small>${$t({defaultMessage: "Generating based on your approved plan"})}</small>
                            </div>
                        </div>
                    </div>

                    <div class="preview-actions" id="preview-actions" style="display: none;">
                        <button type="button" class="btn btn-primary" id="open-in-editor-btn">
                            ${$t({defaultMessage: "Open in Editor"})}
                        </button>
                        <button type="button" class="btn btn-default" id="save-as-template-btn">
                            ${$t({defaultMessage: "Save as Template"})}
                        </button>
                    </div>
                </div>
            </div>
        </div>

        <!-- Attachment Input Modal -->
        <div class="attachment-modal" id="attachment-modal" style="display: none;">
            <div class="modal-overlay">
                <div class="modal-content">
                    <div class="modal-header">
                        <h3 id="attachment-modal-title">Add Attachment</h3>
                        <button type="button" class="modal-close" id="attachment-modal-close">×</button>
                    </div>
                    <div class="modal-body">
                        <div class="attachment-type-info">
                            <p id="attachment-type-description">Select how you want to add this attachment:</p>
                        </div>
                        <div class="attachment-tabs">
                            <button type="button" class="attachment-tab active" data-tab="url">
                                ${$t({defaultMessage: "URL"})}
                            </button>
                            <button type="button" class="attachment-tab" data-tab="upload">
                                ${$t({defaultMessage: "Upload"})}
                            </button>
                        </div>
                        <div class="attachment-content">
                            <div class="attachment-panel active" id="url-panel">
                                <input
                                    type="url"
                                    id="attachment-url-input"
                                    class="attachment-url-input"
                                    placeholder="${$t({defaultMessage: "Enter URL..."})}"
                                />
                            </div>
                            <div class="attachment-panel" id="upload-panel">
                                <div class="file-upload-area" id="file-upload-area">
                                    <div class="file-upload-content">
                                        <div class="upload-icon">[Upload]</div>
                                        <p>${$t({defaultMessage: "Click to upload or drag and drop"})}</p>
                                        <small>${$t({defaultMessage: "Supported formats: JPG, PNG, MP4, MP3, SVG"})}</small>
                                    </div>
                                    <input type="file" id="file-input" style="display: none;" />
                                </div>
                                <div class="file-preview" id="file-preview" style="display: none;">
                                    <div class="file-info">
                                        <span class="file-name" id="file-name"></span>
                                        <button type="button" class="remove-file" id="remove-file">×</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                        <div class="attachment-preview" id="attachment-preview" style="display: none;">
                            <div class="preview-label">${$t({defaultMessage: "Preview:"})}</div>
                            <div class="preview-content" id="preview-content"></div>
                        </div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-default" id="attachment-cancel-btn">
                            ${$t({defaultMessage: "Cancel"})}
                        </button>
                        <button type="button" class="btn btn-primary" id="attachment-confirm-btn" disabled>
                            ${$t({defaultMessage: "Add Attachment"})}
                        </button>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Setup AI Generator event handlers
export function setupAIGeneratorHandlers(): void {
    // Send message handler
    $("#send-message-btn").on("click", () => {
        void sendMessage();
    });

    // Enter key handler
    $("#ai-message-input").on("keydown", (e) => {
        if (e.ctrlKey && e.key === "Enter") {
            e.preventDefault();
            void sendMessage();
        }
    });

    // Open in editor handler
    $("#open-in-editor-btn").on("click", () => {
        openInEditor();
    });

    // Save as template handler
    $("#save-as-template-btn").on("click", () => {
        void saveAsTemplate();
    });

    // Attachment modal handlers
    $("#attachment-modal-close").on("click", () => {
        hideAttachmentModal();
    });

    $("#attachment-cancel-btn").on("click", () => {
        hideAttachmentModal();
    });

    // Tab switching
    $(".attachment-tab").on("click", function() {
        const tab = $(this).data("tab");
        switchAttachmentTab(tab);
    });

    // URL input handler
    $("#attachment-url-input").on("input", () => {
        updateAttachmentPreview();
    });

    // File upload handlers
    $("#file-upload-area").on("click", () => {
        $("#file-input").click();
    });

    $("#file-input").on("change", (e) => {
        const file = (e.target as HTMLInputElement).files?.[0];
        if (file) {
            handleFileUpload(file);
        }
    });

    $("#remove-file").on("click", () => {
        clearFileUpload();
    });

    // Confirm attachment
    $("#attachment-confirm-btn").on("click", () => {
        void confirmAttachment();
    });

    // Clickable attachment placeholders
    $(document).on("click", ".clickable-attachment", function() {
        const type = $(this).data("type");
        const description = $(this).data("description");
        if (type && description) {
            showAttachmentModal(type, description);
        }
    });

    // Plan approval handlers
    $("#approve-plan-btn").on("click", () => {
        void approvePlan();
    });

    $("#reject-plan-btn").on("click", () => {
        void rejectPlan();
    });
}

// Send a message to AI
async function sendMessage(): Promise<void> {
    const messageInput = $("#ai-message-input");
    const message = messageInput.val() as string;

    if (!message.trim() || aiState.isGenerating) {
        return;
    }

    // Add user message to conversation
    addMessageToConversation('user', message);
    messageInput.val('');

    // Check if we're in follow-up mode
    if (aiState.followupQuestions.length > 0 && aiState.currentFollowupIndex < aiState.followupQuestions.length) {
        // Store the answer for current follow-up question
        const currentQuestion = aiState.followupQuestions[aiState.currentFollowupIndex];
        if (currentQuestion) {
            aiState.followupAnswers[currentQuestion] = message;
            aiState.currentFollowupIndex++;

            // Check if we have more follow-up questions
            if (aiState.currentFollowupIndex < aiState.followupQuestions.length) {
                // Ask next question
                const nextQuestion = aiState.followupQuestions[aiState.currentFollowupIndex];
                if (nextQuestion) {
                    addMessageToConversation('ai', nextQuestion);
                }
            } else {
                // All questions answered, generate template
                await generateTemplateFromAnswers();
            }
        }
    } else {
        // Regular conversation - send to AI
        await processAIMessage(message);
    }
}

// Process AI message and handle follow-ups
async function processAIMessage(message: string): Promise<void> {
    // Show planning animation
    showPlanningAnimation();
    setGeneratingState(true);

    try {
        // Get media hints from conversation context (simplified for now)
        const media_hints: Record<string, boolean> = {
            images: true,
            buttons: true,
            video: false,
            audio: false,
        };

        const subjectRaw = $("#notification-subject").val();
        const subject = typeof subjectRaw === "string" && subjectRaw.trim() ? subjectRaw : undefined;

        const req = {
            prompt: message,
            subject,
            media_hints,
        } as const;

        const resp = await aiGenerateTemplate(
            aiState.conversationId ? ({...req, conversation_id: aiState.conversationId} as any) : (req as any),
        );

        // Update conversation ID
        aiState.conversationId = resp.conversation_id;

        // Handle plan approval
        if (resp.status === "plan_ready" && resp.plan) {
            hidePlanningAnimation();
            aiState.currentPlan = resp.plan;
            aiState.isWaitingForPlanApproval = true;
            showPlanDisplay(resp.plan);
            addMessageToConversation('ai', `I've created a plan: "${resp.plan.template_name}". Please review and approve.`);
        }
        // Handle follow-up questions (needs_input status)
        else if (resp.status === "needs_input" && resp.followups && resp.followups.length > 0) {
            hidePlanningAnimation();
            // Start follow-up conversation
            aiState.followupQuestions = resp.followups;
            aiState.currentFollowupIndex = 0;
            aiState.followupAnswers = {};

            // Ask first follow-up question
            const firstQuestion = resp.followups[0];
            if (firstQuestion) {
                addMessageToConversation('ai', firstQuestion);
            }
        }
        // Handle follow-up questions (legacy format)
        else if (resp.followups && resp.followups.length > 0) {
            hidePlanningAnimation();
            // Start follow-up conversation
            aiState.followupQuestions = resp.followups;
            aiState.currentFollowupIndex = 0;
            aiState.followupAnswers = {};

            // Ask first follow-up question
            const firstQuestion = resp.followups[0];
            if (firstQuestion) {
                addMessageToConversation('ai', firstQuestion);
            }
        } else if (resp.template) {
            // Template generated, show it
            hidePlanningAnimation();
            addMessageToConversation('ai', `Generated template: "${resp.template.name}"`);
            updateTemplateAndPreview(resp.template);
        }

    } catch (error) {
        hidePlanningAnimation();
        addMessageToConversation('ai', `Error: ${(error as Error).message}`);
    } finally {
        setGeneratingState(false);
    }
}

// Generate template from collected answers
async function generateTemplateFromAnswers(): Promise<void> {
    // Show generation animation
    showGenerationAnimation();

    setGeneratingState(true);

    try {
        // Create consolidated prompt with all answers
        const consolidatedAnswers = Object.entries(aiState.followupAnswers)
            .map(([question, answer]) => `Q: ${question}\nA: ${answer}`)
            .join('\n\n');

        // Get original prompt from conversation
        const originalPrompt = aiState.conversationHistory
            .filter(msg => msg.role === 'user' && !msg.content.includes('Q:'))
            .map(msg => msg.content)
            .join(' ');

        const enhancedPrompt = `${originalPrompt}\n\nAdditional details:\n${consolidatedAnswers}`;

        const media_hints: Record<string, boolean> = {
            images: true,
            buttons: true,
            video: false,
            audio: false,
        };

        const subjectRaw = $("#notification-subject").val();
        const subject = typeof subjectRaw === "string" && subjectRaw.trim() ? subjectRaw : undefined;

        const req = {
            prompt: enhancedPrompt,
            subject,
            media_hints,
        } as const;

        const resp = await aiGenerateTemplate(
            aiState.conversationId ? ({...req, conversation_id: aiState.conversationId} as any) : (req as any),
        );

        // Update conversation ID
        aiState.conversationId = resp.conversation_id;

        // Add AI response with template
        addMessageToConversation('ai', `Perfect! I've created your template: "${resp.template.name}"`);

        // Update template and preview
        updateTemplateAndPreview(resp.template);

        // Reset follow-up state
        aiState.followupQuestions = [];
        aiState.currentFollowupIndex = 0;
        aiState.followupAnswers = {};

    } catch (error) {
        addMessageToConversation('ai', `Error generating template: ${(error as Error).message}`);
    } finally {
        setGeneratingState(false);
        hideGenerationAnimation();
    }
}

// Update template and preview
function updateTemplateAndPreview(template: AIGenerateTemplateResponse['template']): void {
    aiState.currentTemplate = template;
    updatePreview(template);

    // Show action buttons
    if (template) {
        $("#preview-actions").show();
    }
}

// Add a message to the conversation
function addMessageToConversation(
    role: 'user' | 'ai',
    content: string,
    followups?: string[],
    validation_errors?: string[]
): void {
    const message: ConversationMessage = {
        role,
        content,
        timestamp: new Date(),
        followups,
        validation_errors,
    };

    aiState.conversationHistory.push(message);
    renderConversation();
}

// Render the conversation
function renderConversation(): void {
    const $container = $("#conversation-messages");
    
    if (aiState.conversationHistory.length === 0) {
        $container.html(`
            <div class="conversation-empty">
                <div class="empty-icon">💬</div>
                <p>${$t({defaultMessage: "Start a conversation with AI"})}</p>
                <small>${$t({defaultMessage: "Describe your template and we'll help you build it step by step"})}</small>
            </div>
        `);
        return;
    }

    const messagesHtml = aiState.conversationHistory.map((msg) => {
        const timeStr = msg.timestamp.toLocaleTimeString();
        const isUser = msg.role === 'user';
        
        let messageContent = `
            <div class="message ${isUser ? 'message-user' : 'message-ai'}">
                <div class="message-header">
                    <span class="message-role">${isUser ? $t({defaultMessage: "You"}) : $t({defaultMessage: "AI"})}</span>
                    <span class="message-time">${timeStr}</span>
                </div>
                <div class="message-content">${escapeHtml(msg.content)}</div>
        `;

        // Add followup questions
        if (msg.followups && msg.followups.length > 0) {
            messageContent += `
                <div class="message-followups">
                    <div class="followups-label">${$t({defaultMessage: "Follow-up questions:"})}</div>
                    <ul class="followups-list">
                        ${msg.followups.map(q => `<li>${escapeHtml(q)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        // Add validation errors
        if (msg.validation_errors && msg.validation_errors.length > 0) {
            messageContent += `
                <div class="message-errors">
                    <div class="errors-label">${$t({defaultMessage: "Issues to fix:"})}</div>
                    <ul class="errors-list">
                        ${msg.validation_errors.map(e => `<li>${escapeHtml(e)}</li>`).join('')}
                    </ul>
                </div>
            `;
        }

        messageContent += `</div>`;
        return messageContent;
    }).join('');

    $container.html(messagesHtml);
    
    // Scroll to bottom
    $container.scrollTop($container[0]?.scrollHeight || 0);
}

// Update the preview with the current template
function updatePreview(template: AIGenerateTemplateResponse['template']): void {
    const $container = $("#ai-preview-container");
    
    if (!template) {
        $container.html(`
            <div class="preview-empty">
                <div class="empty-icon">👁️</div>
                <p>${$t({defaultMessage: "Preview will appear here"})}</p>
                <small>${$t({defaultMessage: "Start a conversation to see your template preview"})}</small>
            </div>
        `);
        return;
    }

    if (template.template_type === "text_only") {
        $container.html(`
            <div class="preview-text-template">
                <div class="template-name">${escapeHtml(template.name)}</div>
                <div class="template-content">${renderMarkdown(template.content)}</div>
            </div>
        `);
    } else {
        // Rich media template
        const structure = template.template_structure as TemplateStructure;
        $container.html(`
            <div class="preview-rich-template">
                <div class="template-name">${escapeHtml(template.name)}</div>
                <div class="template-blocks">
                    ${renderTemplateBlocks(structure.blocks || [])}
                </div>
            </div>
        `);
    }
}

// Render template blocks for preview
function renderTemplateBlocks(blocks: any[]): string {
    if (!blocks || blocks.length === 0) {
        return `<div class="no-blocks">${$t({defaultMessage: "No blocks defined"})}</div>`;
    }

    return blocks.map((block) => {
        const isPlaceholder = block.url && block.url.startsWith('placeholder://');
        
        switch (block.type) {
            case 'text':
                return `<div class="preview-block preview-text">${renderMarkdown(block.content || '')}</div>`;
            case 'image':
                if (isPlaceholder) {
                    return `<div class="preview-block preview-image clickable-attachment" data-type="image" data-description="Add an image for this template">
                        <div class="block-placeholder">
                            <div class="placeholder-icon">[Image]</div>
                            <div class="placeholder-text">${escapeHtml(block.url.replace('placeholder://', '').replace('-', ' '))}</div>
                            <div class="placeholder-hint">Click to add image</div>
                        </div>
                    </div>`;
                } else {
                    return `<div class="preview-block preview-image">
                        <img src="${escapeHtml(block.url)}" alt="Image" style="max-width: 100%; height: auto; border-radius: 4px;" onerror="this.parentElement.innerHTML='<div class=\\'block-placeholder\\'>[Image]</div>'">
                    </div>`;
                }
            case 'button':
                return `<div class="preview-block preview-button">
                    <button class="preview-btn" style="background-color: ${block.style?.backgroundColor || '#007bff'}; color: ${block.style?.textColor || 'white'};">
                        ${escapeHtml(block.text || 'Button')}
                    </button>
                </div>`;
            case 'video':
                if (isPlaceholder) {
                    return `<div class="preview-block preview-video clickable-attachment" data-type="video" data-description="Add a video for this template">
                        <div class="block-placeholder">
                            <div class="placeholder-icon">[Video]</div>
                            <div class="placeholder-text">${escapeHtml(block.url.replace('placeholder://', '').replace('-', ' '))}</div>
                            <div class="placeholder-hint">Click to add video</div>
                        </div>
                    </div>`;
                } else {
                    return `<div class="preview-block preview-video">
                        <video controls style="max-width: 100%; height: auto; border-radius: 4px;">
                            <source src="${escapeHtml(block.url)}" type="video/mp4">
                            Your browser does not support video.
                        </video>
                    </div>`;
                }
            case 'audio':
                if (isPlaceholder) {
                    return `<div class="preview-block preview-audio clickable-attachment" data-type="audio" data-description="Add audio for this template">
                        <div class="block-placeholder">
                            <div class="placeholder-icon">[Audio]</div>
                            <div class="placeholder-text">${escapeHtml(block.url.replace('placeholder://', '').replace('-', ' '))}</div>
                            <div class="placeholder-hint">Click to add audio</div>
                        </div>
                    </div>`;
                } else {
                    return `<div class="preview-block preview-audio">
                        <audio controls style="width: 100%;">
                            <source src="${escapeHtml(block.url)}" type="audio/mpeg">
                            Your browser does not support audio.
                        </audio>
                    </div>`;
                }
            case 'svg':
                if (isPlaceholder) {
                    return `<div class="preview-block preview-svg clickable-attachment" data-type="svg" data-description="Add an SVG for this template">
                        <div class="block-placeholder">
                            <div class="placeholder-icon">[SVG]</div>
                            <div class="placeholder-text">${escapeHtml(block.url.replace('placeholder://', '').replace('-', ' '))}</div>
                            <div class="placeholder-hint">Click to add SVG</div>
                        </div>
                    </div>`;
                } else {
                    return `<div class="preview-block preview-svg">
                        <img src="${escapeHtml(block.url)}" alt="SVG" style="max-width: 100%; height: auto; border-radius: 4px;" onerror="this.parentElement.innerHTML='<div class=\\'block-placeholder\\'>[SVG]</div>'">
                    </div>`;
                }
            default:
                return `<div class="preview-block preview-unknown">${escapeHtml(block.type || 'Unknown')}</div>`;
        }
    }).join('');
}

// Simple markdown rendering (basic implementation)
function renderMarkdown(content: string): string {
    if (!content) return '';
    
    return content
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>')
        .replace(/\n/g, '<br>');
}

// Escape HTML to prevent XSS
function escapeHtml(text: string): string {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Set generating state
function setGeneratingState(isGenerating: boolean): void {
    aiState.isGenerating = isGenerating;
    const $btn = $("#send-message-btn");
    const $input = $("#ai-message-input");
    
    if (isGenerating) {
        $btn.prop("disabled", true).html('<span class="loading-spinner"></span>');
        $input.prop("disabled", true);
    } else {
        $btn.prop("disabled", false).html('<span class="send-icon">➤</span>');
        $input.prop("disabled", false);
    }
}

// Open current template in editor
function openInEditor(): void {
    if (!aiState.currentTemplate) {
        return;
    }

    const template = aiState.currentTemplate;
    
    if (template.template_type === "rich_media") {
        openRichTemplateEditor("create", template.name, template.template_structure as TemplateStructure);
    } else {
        // For text-only templates, we could open a simple editor or just show the content
        alert($t({defaultMessage: "Text-only templates are edited in the main form. The content has been copied to the notification content field."}));
        $("#notification-content").val(template.content);
        $("#notification-subject").val(template.name);
    }
}

// Save current template
async function saveAsTemplate(): Promise<void> {
    if (!aiState.currentTemplate) {
        return;
    }

    const template = aiState.currentTemplate;
    const $btn = $("#save-as-template-btn");
    const originalText = $btn.text();
    
    $btn.prop("disabled", true).text($t({defaultMessage: "Saving..."}));

    try {
        await createTemplate({
            name: template.name,
            template_type: template.template_type,
            content: template.content,
            template_structure: template.template_structure as unknown as Record<string, unknown>,
            ai_generated: true,
            ai_prompt: aiState.conversationHistory.map(m => `${m.role}: ${m.content}`).join('\n'),
        });

        alert($t({defaultMessage: "Template saved successfully!"}));
        
        // Reload templates if we're on templates tab
        const templatesTab = $("#templates-tab-content");
        if (templatesTab.is(":visible")) {
            window.location.reload();
        }
    } catch (error) {
        alert($t({defaultMessage: "Failed to save template:"}) + " " + (error as Error).message);
    } finally {
        $btn.prop("disabled", false).text(originalText);
    }
}

// Show planning animation
function showPlanningAnimation(): void {
    $("#conversation-messages").hide();
    $("#plan-display").hide();
    $("#planning-animation").show();
    aiState.isPlanningInProgress = true;
}

// Hide planning animation
function hidePlanningAnimation(): void {
    $("#planning-animation").hide();
    $("#conversation-messages").show();
    aiState.isPlanningInProgress = false;
}

// Show plan display
function showPlanDisplay(plan: AIGenerateTemplateResponse['plan']): void {
    if (!plan) return;
    
    const blocksHtml = plan.structure.blocks.map(block => `
        <li>
            <span class="block-type-badge">[${block.type}]</span>
            <span class="block-description">${escapeHtml(block.description)}</span>
        </li>
    `).join('');
    
    const planHtml = `
        <div class="plan-item">
            <label>${$t({defaultMessage: "Template Type:"})}</label>
            <span class="plan-value">${plan.template_type}</span>
        </div>
        <div class="plan-item">
            <label>${$t({defaultMessage: "Template Name:"})}</label>
            <span class="plan-value">${escapeHtml(plan.template_name)}</span>
        </div>
        <div class="plan-structure">
            <label>${$t({defaultMessage: "Structure:"})}</label>
            <ul class="block-list">${blocksHtml}</ul>
        </div>
        <div class="plan-reasoning">
            <label>${$t({defaultMessage: "Why this structure:"})}</label>
            <p>${escapeHtml(plan.reasoning)}</p>
        </div>
    `;
    
    $("#plan-details").html(planHtml);
    $("#plan-display").show();
}

// Hide plan display
function hidePlanDisplay(): void {
    $("#plan-display").hide();
    aiState.isWaitingForPlanApproval = false;
}

// Approve plan and generate template
async function approvePlan(): Promise<void> {
    if (!aiState.currentPlan || !aiState.conversationId) return;

    hidePlanDisplay();
    showGenerationAnimation();
    aiState.isGeneratingTemplate = true;

    try {
        const subjectRaw = $("#notification-subject").val();
        const subject = typeof subjectRaw === "string" && subjectRaw.trim() ? subjectRaw : undefined;

        // Get the original prompt from conversation history
        const originalPrompt = aiState.conversationHistory
            .filter(msg => msg.role === 'user')
            .map(msg => msg.content)
            .join(' ') || "Generate template";

        // Resume the graph with plan approval
        const req = {
            prompt: originalPrompt,
            conversation_id: aiState.conversationId,
            approve_plan: true,  // This tells backend to resume with approval
            subject,
        };

        const resp = await aiGenerateTemplate(req as any);

        // Keep conversation in sync in case backend returned a different id
        if (resp.conversation_id) {
            aiState.conversationId = resp.conversation_id;
        }

        // Handle response - might still be interrupted or complete
        if (resp.status === "complete" && resp.template) {
            addMessageToConversation('ai', `Template generated successfully: "${resp.template.name}"`);
            updateTemplateAndPreview(resp.template);
        } else if (resp.status === "needs_input" && resp.followups) {
            // Handle follow-up questions after generation
            hideGenerationAnimation();
            aiState.followupQuestions = resp.followups;
            aiState.currentFollowupIndex = 0;
            aiState.followupAnswers = {};
            const firstQuestion = resp.followups[0];
            if (firstQuestion) {
                addMessageToConversation('ai', firstQuestion);
            }
        } else if (resp.template) {
            // Legacy format or complete
            addMessageToConversation('ai', `Template generated successfully: "${resp.template.name}"`);
            updateTemplateAndPreview(resp.template);
        } else if (resp.status !== "error") {
            // If the server returned no template yet (e.g., due to an extra interrupt
            // in older backends), issue one quick follow-up call to fetch the result.
            try {
                const retry = await aiGenerateTemplate({
                    prompt: originalPrompt,
                    conversation_id: aiState.conversationId!,
                    approve_plan: true,
                    subject,
                } as any);
                if (retry.template) {
                    addMessageToConversation('ai', `Template generated successfully: "${retry.template.name}"`);
                    updateTemplateAndPreview(retry.template);
                } else if (retry.status === "needs_input" && retry.followups) {
                    hideGenerationAnimation();
                    aiState.followupQuestions = retry.followups;
                    aiState.currentFollowupIndex = 0;
                    aiState.followupAnswers = {};
                    const firstQ = retry.followups[0];
                    if (firstQ) {
                        addMessageToConversation('ai', firstQ);
                    }
                } else {
                    hideGenerationAnimation();
                    addMessageToConversation('ai', $t({defaultMessage: "Plan approved; waiting for template. Please try again."}));
                }
            } catch (e) {
                hideGenerationAnimation();
                addMessageToConversation('ai', `Error generating template: ${(e as Error).message}`);
            }
        }

    } catch (error) {
        addMessageToConversation('ai', `Error generating template: ${(error as Error).message}`);
    } finally {
        hideGenerationAnimation();
        aiState.isGeneratingTemplate = false;
    }
}

// UI: Render and show feedback modal
function showPlanFeedbackModal(): void {
    // If modal exists, just show it
    let $overlay = $("#ai-plan-feedback-overlay");
    if ($overlay.length === 0) {
        const html = `
            <div class="modal-overlay" id="ai-plan-feedback-overlay" style="display:none;">
                <div class="modal" role="dialog" aria-modal="true" aria-labelledby="plan-feedback-title">
                    <div class="modal-header">
                        <h3 id="plan-feedback-title">${$t({defaultMessage: "Request changes to the plan"})}</h3>
                        <button type="button" class="close-modal" id="close-plan-feedback" aria-label="Close">×</button>
                    </div>
                    <div class="modal-body">
                        <label for="plan-feedback-text" class="sr-only">${$t({defaultMessage: "Describe the changes you want"})}</label>
                        <textarea id="plan-feedback-text" class="feedback-text" placeholder="${$t({defaultMessage: "E.g., Add a hero image, use a warm tone, include two buttons"})}"></textarea>
                        <div class="modal-hint" id="plan-feedback-counter">0/500</div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-default" id="cancel-plan-feedback">${$t({defaultMessage: "Cancel"})}</button>
                        <button type="button" class="btn btn-primary" id="submit-plan-feedback" disabled>${$t({defaultMessage: "Submit"})}</button>
                    </div>
                </div>
            </div>`;
        $(document.body).append(html);

        $overlay = $("#ai-plan-feedback-overlay");

        // Handlers
        const $textarea = $("#plan-feedback-text");
        const $submit = $("#submit-plan-feedback");
        const $counter = $("#plan-feedback-counter");

        function updateState() {
            const val = ($textarea.val() as string) || "";
            const trimmed = val.trim().slice(0, 500);
            if (val !== trimmed) {
                $textarea.val(trimmed);
            }
            $counter.text(`${trimmed.length}/500`);
            $submit.prop("disabled", trimmed.length === 0);
        }

        $textarea.on("input", updateState);
        $("#cancel-plan-feedback, #close-plan-feedback").on("click", () => {
            hidePlanFeedbackModal();
        });
        $submit.on("click", async () => {
            const feedback = (($textarea.val() as string) || "").trim();
            if (!feedback) return;
            hidePlanFeedbackModal();
            await submitPlanFeedback(feedback);
        });

        // Keyboard: Esc close, Cmd/Ctrl+Enter submit
        $overlay.on("keydown", async (e: JQuery.KeyDownEvent) => {
            if (e.key === "Escape") {
                e.preventDefault();
                hidePlanFeedbackModal();
            }
            if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
                e.preventDefault();
                const feedback = (($textarea.val() as string) || "").trim();
                if (!feedback) return;
                hidePlanFeedbackModal();
                await submitPlanFeedback(feedback);
            }
        });
    }

    $overlay.show();
    $("#plan-feedback-text").trigger("focus");
}

function hidePlanFeedbackModal(): void {
    $("#ai-plan-feedback-overlay").hide();
}

// Submit feedback and trigger re-planning
async function submitPlanFeedback(feedback: string): Promise<void> {
    hidePlanDisplay();
    addMessageToConversation('user', `Changes requested: ${feedback}`);
    showPlanningAnimation();

    try {
        const subjectRaw = $("#notification-subject").val();
        const subject = typeof subjectRaw === "string" && subjectRaw.trim() ? subjectRaw : undefined;

        // Get the original prompt from conversation history
        const originalPrompt = aiState.conversationHistory
            .filter(msg => msg.role === 'user')
            .map(msg => msg.content)
            .join(' ') || "Generate template";

        const req = {
            prompt: originalPrompt,
            conversation_id: aiState.conversationId,
            plan_feedback: feedback,
            subject,
        };

        const resp = await aiGenerateTemplate(req as any);

        // Sync conversation id on replan response
        if (resp.conversation_id) {
            aiState.conversationId = resp.conversation_id;
        }

        if (resp.status === "plan_ready" && resp.plan) {
            hidePlanningAnimation();
            aiState.currentPlan = resp.plan;
            showPlanDisplay(resp.plan);
            addMessageToConversation('ai', `I've updated the plan: "${resp.plan.template_name}". Please review.`);
        } else if (resp.template) {
            hidePlanningAnimation();
            addMessageToConversation('ai', `Template generated: "${resp.template.name}"`);
            updateTemplateAndPreview(resp.template);
        }
    } catch (error) {
        hidePlanningAnimation();
        addMessageToConversation('ai', `Error updating plan: ${(error as Error).message}`);
    }
}

// Reject plan and request changes (opens modal)
async function rejectPlan(): Promise<void> {
    showPlanFeedbackModal();
}

// Show generation animation
function showGenerationAnimation(): void {
    $("#generation-animation").show();
    $("#ai-preview-container").hide();
}

// Hide generation animation
function hideGenerationAnimation(): void {
    $("#generation-animation").hide();
    $("#ai-preview-container").show();
}

// Reset AI state (called when switching tabs)
export function resetAIState(): void {
    aiState = {
        conversationHistory: [],
        currentTemplate: null,
        currentPlan: null,
        conversationId: null,
        isGenerating: false,
        isGeneratingTemplate: false,
        isPlanningInProgress: false,
        isWaitingForPlanApproval: false,
        currentFollowupIndex: 0,
        followupQuestions: [],
        followupAnswers: {},
        attachmentModal: {
            isOpen: false,
            type: null,
            description: null,
            currentUrl: "",
            currentFile: null,
        },
    };
    renderConversation();
    updatePreview(null as any);
    $("#ai-message-input").val("");
    $("#open-editor-btn").prop("disabled", true);
    $("#save-template-btn").prop("disabled", true);
    hideGenerationAnimation();
    hidePlanningAnimation();
    hidePlanDisplay();
    hideAttachmentModal();
}

// Attachment Modal Functions

// Show attachment modal for specific type
function showAttachmentModal(type: string, description: string): void {
    aiState.attachmentModal.isOpen = true;
    aiState.attachmentModal.type = type;
    aiState.attachmentModal.description = description;
    aiState.attachmentModal.currentUrl = "";
    aiState.attachmentModal.currentFile = null;

    // Update modal content
    $("#attachment-modal-title").text(`Add ${type.charAt(0).toUpperCase() + type.slice(1)}`);
    $("#attachment-type-description").text(description);

    // Reset form
    $("#attachment-url-input").val("");
    $("#file-input").val("");
    $("#file-preview").hide();
    $("#attachment-preview").hide();
    $("#attachment-confirm-btn").prop("disabled", true);

    // Show modal
    $("#attachment-modal").show();
    $("#attachment-url-input").focus();
}

// Hide attachment modal
function hideAttachmentModal(): void {
    aiState.attachmentModal.isOpen = false;
    aiState.attachmentModal.type = null;
    aiState.attachmentModal.description = null;
    aiState.attachmentModal.currentUrl = "";
    aiState.attachmentModal.currentFile = null;

    $("#attachment-modal").hide();
}

// Switch between URL and upload tabs
function switchAttachmentTab(tab: string): void {
    $(".attachment-tab").removeClass("active");
    $(`.attachment-tab[data-tab="${tab}"]`).addClass("active");

    $(".attachment-panel").removeClass("active");
    $(`#${tab}-panel`).addClass("active");

    // Clear current input when switching tabs
    if (tab === "url") {
        $("#attachment-url-input").focus();
    } else {
        clearFileUpload();
    }
    updateAttachmentPreview();
}

// Update attachment preview
function updateAttachmentPreview(): void {
    const activeTab = $(".attachment-tab.active").data("tab");
    let hasContent = false;
    let previewHtml = "";

    if (activeTab === "url") {
        const url = $("#attachment-url-input").val() as string;
        if (url.trim()) {
            hasContent = true;
            aiState.attachmentModal.currentUrl = url.trim();
            
            // Generate preview based on attachment type
            const type = aiState.attachmentModal.type;
            if (type === "image") {
                previewHtml = `<img src="${url}" alt="Preview" style="max-width: 200px; max-height: 150px; border-radius: 4px;" onerror="this.style.display='none'">`;
            } else if (type === "video") {
                previewHtml = `<video controls style="max-width: 200px; max-height: 150px; border-radius: 4px;"><source src="${url}" type="video/mp4">Your browser does not support video.</video>`;
            } else if (type === "audio") {
                previewHtml = `<audio controls style="width: 200px;"><source src="${url}" type="audio/mpeg">Your browser does not support audio.</audio>`;
            } else if (type === "svg") {
                previewHtml = `<img src="${url}" alt="SVG Preview" style="max-width: 200px; max-height: 150px; border-radius: 4px;" onerror="this.style.display='none'">`;
            }
        }
    } else if (activeTab === "upload") {
        const file = aiState.attachmentModal.currentFile;
        if (file) {
            hasContent = true;
            previewHtml = `<div class="file-preview-content">
                <div class="file-icon">[File]</div>
                <div class="file-details">
                    <div class="file-name">${file.name}</div>
                    <div class="file-size">${(file.size / 1024).toFixed(1)} KB</div>
                </div>
            </div>`;
        }
    }

    if (hasContent) {
        $("#preview-content").html(previewHtml);
        $("#attachment-preview").show();
        $("#attachment-confirm-btn").prop("disabled", false);
    } else {
        $("#attachment-preview").hide();
        $("#attachment-confirm-btn").prop("disabled", true);
    }
}

// Handle file upload
function handleFileUpload(file: File): void {
    aiState.attachmentModal.currentFile = file;
    $("#file-name").text(file.name);
    $("#file-upload-area").hide();
    $("#file-preview").show();
    updateAttachmentPreview();
}

// Clear file upload
function clearFileUpload(): void {
    aiState.attachmentModal.currentFile = null;
    $("#file-input").val("");
    $("#file-upload-area").show();
    $("#file-preview").hide();
    updateAttachmentPreview();
}

// Confirm attachment and add to template
async function confirmAttachment(): Promise<void> {
    const type = aiState.attachmentModal.type;
    const activeTab = $(".attachment-tab.active").data("tab");
    
    if (!type) return;

    let attachmentData: any = {
        type: type,
        id: `attachment-${Date.now()}`,
    };

    if (activeTab === "url") {
        attachmentData.url = aiState.attachmentModal.currentUrl;
    } else if (activeTab === "upload") {
        const file = aiState.attachmentModal.currentFile;
        if (file) {
            // For now, we'll use a placeholder URL for uploaded files
            // In a real implementation, you'd upload the file and get a URL
            attachmentData.url = `placeholder://uploaded-${file.name}`;
            attachmentData.fileName = file.name;
        }
    }

    // Add attachment to current template
    if (aiState.currentTemplate && aiState.currentTemplate.template_structure) {
        const blocks = aiState.currentTemplate.template_structure.blocks || [];
        blocks.push(attachmentData);
        aiState.currentTemplate.template_structure.blocks = blocks;
        
        // Update preview
        updatePreview(aiState.currentTemplate);
        
        // Add message to conversation
        addMessageToConversation('user', `Added ${type}: ${attachmentData.url || attachmentData.fileName}`);
    }

    // Hide modal
    hideAttachmentModal();
}