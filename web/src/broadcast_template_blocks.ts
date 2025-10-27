// Template block type definitions and utilities for rich media templates

export type BlockType = "text" | "image" | "button" | "video" | "audio" | "svg";

export interface BaseBlock {
    id: string;
    type: BlockType;
}

export interface TextBlock extends BaseBlock {
    type: "text";
    content: string;
}

export interface ImageBlock extends BaseBlock {
    type: "image";
    label: string;
    alt: string;
    required: boolean;
    maxWidth?: number;
    url?: string; // Populated when using template
}

export interface ButtonBlock extends BaseBlock {
    type: "button";
    text: string;
    url: string;
    style: {
        backgroundColor: string;
        textColor: string;
        borderRadius: number;
        size: "small" | "medium" | "large";
    };
}

export interface VideoBlock extends BaseBlock {
    type: "video";
    label: string;
    required: boolean;
    allowUrl: boolean;
    allowUpload: boolean;
    url?: string; // Populated when using template
}

export interface AudioBlock extends BaseBlock {
    type: "audio";
    label: string;
    required: boolean;
    url?: string; // Populated when using template
}

export interface SVGBlock extends BaseBlock {
    type: "svg";
    label: string;
    required: boolean;
    allowInline: boolean;
    maxDimensions?: {width: number; height: number};
    content?: string; // SVG code or URL
}

export type TemplateBlock =
    | TextBlock
    | ImageBlock
    | ButtonBlock
    | VideoBlock
    | AudioBlock
    | SVGBlock;

export interface TemplateStructure {
    blocks: TemplateBlock[];
}

// Default block configurations
export const DEFAULT_TEXT_BLOCK: Omit<TextBlock, "id"> = {
    type: "text",
    content: "",
};

export const DEFAULT_IMAGE_BLOCK: Omit<ImageBlock, "id"> = {
    type: "image",
    label: "Image",
    alt: "",
    required: false,
};

export const DEFAULT_BUTTON_BLOCK: Omit<ButtonBlock, "id"> = {
    type: "button",
    text: "Click Here",
    url: "",
    style: {
        backgroundColor: "#007bff",
        textColor: "#ffffff",
        borderRadius: 4,
        size: "medium",
    },
};

export const DEFAULT_VIDEO_BLOCK: Omit<VideoBlock, "id"> = {
    type: "video",
    label: "Video",
    required: false,
    allowUrl: true,
    allowUpload: true,
};

export const DEFAULT_AUDIO_BLOCK: Omit<AudioBlock, "id"> = {
    type: "audio",
    label: "Audio",
    required: false,
};

export const DEFAULT_SVG_BLOCK: Omit<SVGBlock, "id"> = {
    type: "svg",
    label: "SVG Icon",
    required: false,
    allowInline: true,
};

// Helper to generate unique block IDs
let blockIdCounter = 0;
export function generateBlockId(type: BlockType): string {
    blockIdCounter++;
    return `${type}_${blockIdCounter}_${Date.now()}`;
}

// Type guards
export function isTextBlock(block: TemplateBlock): block is TextBlock {
    return block.type === "text";
}

export function isImageBlock(block: TemplateBlock): block is ImageBlock {
    return block.type === "image";
}

export function isButtonBlock(block: TemplateBlock): block is ButtonBlock {
    return block.type === "button";
}

export function isVideoBlock(block: TemplateBlock): block is VideoBlock {
    return block.type === "video";
}

export function isAudioBlock(block: TemplateBlock): block is AudioBlock {
    return block.type === "audio";
}

export function isSVGBlock(block: TemplateBlock): block is SVGBlock {
    return block.type === "svg";
}

// Get media blocks (blocks that require file uploads)
export function getMediaBlocks(structure: TemplateStructure): TemplateBlock[] {
    return structure.blocks.filter(
        (block) =>
            isImageBlock(block) || isVideoBlock(block) || isAudioBlock(block) || isSVGBlock(block),
    );
}

// Get required media blocks
export function getRequiredMediaBlocks(structure: TemplateStructure): TemplateBlock[] {
    return getMediaBlocks(structure).filter((block) => {
        if (isImageBlock(block) || isVideoBlock(block) || isAudioBlock(block) || isSVGBlock(block)) {
            return block.required;
        }
        return false;
    });
}

// Validate template structure
export function validateTemplateStructure(structure: TemplateStructure): {
    valid: boolean;
    errors: string[];
} {
    const errors: string[] = [];

    if (!structure.blocks || !Array.isArray(structure.blocks)) {
        errors.push("Template structure must have a blocks array");
        return {valid: false, errors};
    }

    if (structure.blocks.length === 0) {
        errors.push("Template must have at least one block");
    }

    // Validate each block
    for (const [index, block] of structure.blocks.entries()) {
        if (!block.id) {
            errors.push(`Block at index ${index} missing id`);
        }
        if (!block.type) {
            errors.push(`Block at index ${index} missing type`);
        }

        // Type-specific validation
        if (isTextBlock(block) && block.content === undefined) {
            errors.push(`Text block at index ${index} missing content`);
        }
        if (isButtonBlock(block)) {
            if (!block.text) {
                errors.push(`Button block at index ${index} missing text`);
            }
            if (!block.style) {
                errors.push(`Button block at index ${index} missing style`);
            }
        }
    }

    return {
        valid: errors.length === 0,
        errors,
    };
}

// Create a blank template structure
export function createBlankTemplateStructure(): TemplateStructure {
    return {
        blocks: [
            {
                id: generateBlockId("text"),
                ...DEFAULT_TEXT_BLOCK,
                content: "Enter your message here...",
            },
        ],
    };
}
