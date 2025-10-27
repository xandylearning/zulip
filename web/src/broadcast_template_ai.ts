// AI Template Generator UI Component (Placeholder for future AI integration)

import $ from "jquery";

import {$t} from "./i18n.ts";
import {createBlankTemplateStructure, generateBlockId} from "./broadcast_template_blocks.ts";
import {openRichTemplateEditor} from "./broadcast_template_editor.ts";

// Build AI Generator tab with split view
export function buildAIGeneratorTab(): string {
    return `
        <div class="ai-generator-page">
            <div class="ai-generator-split-view">
                <!-- Left Panel: Input Form -->
                <div class="ai-input-panel">
                    <div class="ai-panel-header">
                        <h3>${$t({defaultMessage: "AI Template Generator"})} <span class="beta-badge">${$t({defaultMessage: "Beta"})}</span></h3>
                        <p class="ai-description">${$t({defaultMessage: "Describe the template you want, and AI will help you create it."})}</p>
                    </div>

                    <div class="ai-generator-form">
                        <div class="form-group">
                            <label for="ai-prompt">${$t({defaultMessage: "Describe your template:"})}</label>
                            <textarea
                                id="ai-prompt"
                                class="form-control ai-prompt-textarea"
                                rows="8"
                                placeholder="${$t({defaultMessage: "Example: Create a welcome template with a hero image, welcome message, and a call-to-action button that links to the onboarding guide. Include a short intro video."})}"
                            ></textarea>
                            <small class="form-text text-muted">${$t({defaultMessage: "Be specific about the content blocks you want to include."})}</small>
                        </div>

                        <div class="ai-options">
                            <label class="ai-options-label">${$t({defaultMessage: "Include:"})}</label>
                            <div class="ai-options-checkboxes">
                                <label class="checkbox-label">
                                    <input type="checkbox" id="ai-include-images" checked />
                                    <span>${$t({defaultMessage: "Images"})}</span>
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="ai-include-buttons" checked />
                                    <span>${$t({defaultMessage: "Buttons"})}</span>
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="ai-include-video" />
                                    <span>${$t({defaultMessage: "Video"})}</span>
                                </label>
                                <label class="checkbox-label">
                                    <input type="checkbox" id="ai-include-audio" />
                                    <span>${$t({defaultMessage: "Audio"})}</span>
                                </label>
                            </div>
                        </div>

                        <div class="ai-generator-actions">
                            <button type="button" class="btn btn-primary btn-large" id="generate-template-ai">
                                ${$t({defaultMessage: "Generate Template"})}
                            </button>
                        </div>

                        <div class="ai-generator-info">
                            <div class="info-box info">
                                <span class="info-icon"></span>
                                <p>${$t({defaultMessage: "AI-generated templates will open in the editor where you can refine them before saving."})}</p>
                            </div>
                            <div class="info-box warning">
                                <span class="info-icon"></span>
                                <p>${$t({defaultMessage: "AI generation is coming soon. For now, this will create a basic template structure based on your selected options."})}</p>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Right Panel: Preview -->
                <div class="ai-preview-panel">
                    <div class="ai-panel-header">
                        <h3>${$t({defaultMessage: "Preview"})}</h3>
                        <p class="ai-description">${$t({defaultMessage: "See how your template will look"})}</p>
                    </div>

                    <div class="ai-preview-container" id="ai-preview-container">
                        <div class="ai-preview-empty">
                            <div class="empty-icon"></div>
                            <p>${$t({defaultMessage: "Preview will appear here"})}</p>
                            <small>${$t({defaultMessage: "Describe your template and click Generate to see a preview"})}</small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;
}

// Setup AI Generator event handlers
export function setupAIGeneratorHandlers(): void {
    $("#generate-template-ai").on("click", () => {
        generateTemplateFromAI();
    });
}

// Generate template from AI prompt (placeholder implementation)
function generateTemplateFromAI(): void {
    const prompt = $("#ai-prompt").val() as string;

    if (!prompt.trim()) {
        alert($t({defaultMessage: "Please enter a description for your template."}));
        return;
    }

    // Get selected options
    const includeImages = $("#ai-include-images").prop("checked") as boolean;
    const includeButtons = $("#ai-include-buttons").prop("checked") as boolean;
    const includeVideo = $("#ai-include-video").prop("checked") as boolean;
    const includeAudio = $("#ai-include-audio").prop("checked") as boolean;

    // Create a basic template structure based on options
    // In the future, this will call an AI API
    const templateStructure = createTemplateStructureFromOptions({
        includeImages,
        includeButtons,
        includeVideo,
        includeAudio,
        prompt,
    });

    // Generate a suggested name from the prompt
    const suggestedName = generateTemplateNameFromPrompt(prompt);

    // Open the rich template editor with the generated structure
    openRichTemplateEditor("create", suggestedName, templateStructure);

    // Show a message that this is a placeholder
    setTimeout(() => {
        alert($t({defaultMessage: "Template structure created! AI generation is coming soon. For now, a basic structure has been created based on your options. Please customize it in the editor."}));
    }, 500);
}

// Create a basic template structure from user options (placeholder for AI)
function createTemplateStructureFromOptions(options: {
    includeImages: boolean;
    includeButtons: boolean;
    includeVideo: boolean;
    includeAudio: boolean;
    prompt: string;
}) {
    const blocks = [];

    // Always start with a text block
    blocks.push({
        id: generateBlockId("text"),
        type: "text" as const,
        content: "Welcome! Edit this text to customize your message.",
    });

    // Add image if requested
    if (options.includeImages) {
        blocks.push({
            id: generateBlockId("image"),
            type: "image" as const,
            label: "Hero Image",
            alt: "Main image",
            required: true,
        });
    }

    // Add another text block for body content
    blocks.push({
        id: generateBlockId("text"),
        type: "text" as const,
        content: "Add your main content here. You can use Markdown formatting.",
    });

    // Add video if requested
    if (options.includeVideo) {
        blocks.push({
            id: generateBlockId("video"),
            type: "video" as const,
            label: "Introduction Video",
            required: false,
            allowUrl: true,
            allowUpload: true,
        });
    }

    // Add audio if requested
    if (options.includeAudio) {
        blocks.push({
            id: generateBlockId("audio"),
            type: "audio" as const,
            label: "Audio Message",
            required: false,
        });
    }

    // Add button if requested
    if (options.includeButtons) {
        blocks.push({
            id: generateBlockId("button"),
            type: "button" as const,
            text: "Get Started",
            url: "https://example.com",
            style: {
                backgroundColor: "#007bff",
                textColor: "#ffffff",
                borderRadius: 4,
                size: "medium" as const,
            },
        });
    }

    return {blocks};
}

// Generate a template name from the prompt (simple extraction)
function generateTemplateNameFromPrompt(prompt: string): string {
    // Extract first few words as a suggested name
    const words = prompt.trim().split(/\s+/).slice(0, 4);
    const name = words.join(" ");

    // Capitalize first letter
    return name.charAt(0).toUpperCase() + name.slice(1);
}

// Future: This function will be replaced with an actual AI API call
export async function callAITemplateGenerator(prompt: string, options: Record<string, boolean>): Promise<any> {
    // Placeholder for future AI integration
    // This would call an endpoint like /json/generate_template_ai

    throw new Error("AI generation not yet implemented");
}
