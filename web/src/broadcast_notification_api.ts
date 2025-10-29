import type {TemplateStructure} from "./broadcast_template_blocks.ts";
// API client for broadcast notification system

import * as channel from "./channel.ts";
import type {
    NotificationDetailResponse,
    NotificationsResponse,
    RecipientsResponse,
    SendNotificationRequest,
    SendNotificationResponse,
    TemplatesResponse,
} from "./broadcast_notification_types.ts";

export async function fetchTemplates(): Promise<TemplatesResponse> {
    return new Promise((resolve, reject) => {
        channel.get({
            url: "/json/notification_templates",
            success(data) {
                resolve(data as TemplatesResponse);
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to fetch templates"));
            },
        });
    });
}

export async function createTemplate(template: {
    name: string;
    content?: string;
    template_type?: string;
    template_structure?: Record<string, unknown>;
    ai_generated?: boolean;
    ai_prompt?: string;
}): Promise<void> {
    return new Promise((resolve, reject) => {
        const data: Record<string, unknown> = {
            name: template.name,
        };

        // Add optional fields if provided
        if (template.content !== undefined) {
            data.content = template.content;
        }
        if (template.template_type !== undefined) {
            data.template_type = template.template_type;
        }
        if (template.template_structure !== undefined) {
            data.template_structure = JSON.stringify(template.template_structure);
        }
        if (template.ai_generated !== undefined) {
            // Backend expects native boolean via typed_endpoint
            data.ai_generated = template.ai_generated;
        }
        if (template.ai_prompt !== undefined) {
            data.ai_prompt = template.ai_prompt;
        }

        channel.post({
            url: "/json/notification_templates",
            data,
            success() {
                resolve();
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to create template"));
            },
        });
    });
}

export async function updateTemplate(
    templateId: number,
    template: {
        name?: string;
        content?: string;
        template_type?: string;
        template_structure?: Record<string, unknown>;
        ai_generated?: boolean;
        ai_prompt?: string;
    },
): Promise<void> {
    return new Promise((resolve, reject) => {
        const data: Record<string, unknown> = {
            template_id: templateId,
        };

        // Add optional fields if provided
        if (template.name !== undefined) {
            data.name = template.name;
        }
        if (template.content !== undefined) {
            data.content = template.content;
        }
        if (template.template_type !== undefined) {
            data.template_type = template.template_type;
        }
        if (template.template_structure !== undefined) {
            data.template_structure = JSON.stringify(template.template_structure);
        }
        if (template.ai_generated !== undefined) {
            // Backend expects native boolean via typed_endpoint
            data.ai_generated = template.ai_generated;
        }
        if (template.ai_prompt !== undefined) {
            data.ai_prompt = template.ai_prompt;
        }

        channel.patch({
            url: `/json/notification_templates/${templateId}`,
            data,
            success() {
                resolve();
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to update template"));
            },
        });
    });
}

export interface AIGenerateTemplateRequest {
    prompt: string;
    conversation_id?: string;
    subject?: string;
    template_id?: number;
    media_hints?: Record<string, unknown>;
    approve_plan?: boolean;
    plan_feedback?: string;
}

export interface AIGenerateTemplateResponse {
    conversation_id: string;
    template: {
        name: string;
        template_type: "text_only" | "rich_media";
        content: string;
        template_structure: TemplateStructure;
        ai_generated: boolean;
        ai_prompt: string;
    };
    plan?: {
        template_type: string;
        template_name: string;
        structure: {
            blocks: Array<{
                type: string;
                description: string;
            }>;
        };
        reasoning: string;
    };
    followups?: string[];
    validation_errors?: string[];
    status?: "planning" | "plan_ready" | "generating" | "needs_input" | "complete" | "error";
}

export async function aiGenerateTemplate(
    request: AIGenerateTemplateRequest,
): Promise<AIGenerateTemplateResponse> {
    return new Promise((resolve, reject) => {
        const data: Record<string, unknown> = {
            prompt: request.prompt,
        };
        if (request.conversation_id) {
            data.conversation_id = request.conversation_id;
        }
        if (request.subject) {
            data.subject = request.subject;
        }
        if (request.template_id !== undefined) {
            data.template_id = request.template_id;
        }
        if (request.media_hints !== undefined) {
            data.media_hints = JSON.stringify(request.media_hints);
        }
        if (request.approve_plan !== undefined) {
            // Backend expects Json[bool] via typed_endpoint
            data.approve_plan = JSON.stringify(request.approve_plan);
        }
        if (request.plan_feedback) {
            data.plan_feedback = request.plan_feedback;
        }

        channel.post({
            url: "/json/notification_templates/ai_generate",
            data,
            success(data: unknown) {
                resolve(data as AIGenerateTemplateResponse);
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "AI template generation failed"));
            },
        });
    });
}

export async function deleteTemplate(templateId: number): Promise<void> {
    return new Promise((resolve, reject) => {
        channel.del({
            url: `/json/notification_templates/${templateId}`,
            success() {
                resolve();
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to delete template"));
            },
        });
    });
}

export async function sendNotification(
    request: SendNotificationRequest,
): Promise<SendNotificationResponse> {
    return new Promise((resolve, reject) => {
        const requestData: Record<string, unknown> = {
            subject: request.subject,
            content: request.content,
            target_type: request.target_type,
            target_ids: JSON.stringify(request.target_ids),
        };

        // Only add template_id if it's a valid positive integer
        if (request.template_id !== undefined && request.template_id !== null) {
            const templateIdNum = Number(request.template_id);
            if (!isNaN(templateIdNum) && templateIdNum > 0 && Number.isInteger(templateIdNum)) {
                // Send as JSON string - typed_endpoint expects Json[int] type
                requestData.template_id = JSON.stringify(templateIdNum);
            }
        }

        // Add optional fields
        if (request.attachment_paths) {
            requestData.attachment_paths = JSON.stringify(request.attachment_paths);
        }

        if (request.media_content) {
            requestData.media_content = JSON.stringify(request.media_content);
        }


        channel.post({
            url: "/json/broadcast_notification",
            data: requestData,
            success(data) {
                resolve(data as SendNotificationResponse);
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to send notification"));
            },
        });
    });
}

export async function fetchNotifications(): Promise<NotificationsResponse> {
    return new Promise((resolve, reject) => {
        channel.get({
            url: "/json/broadcast_notifications",
            success(data) {
                resolve(data as NotificationsResponse);
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to fetch notifications"));
            },
        });
    });
}

export async function fetchNotificationDetails(
    notificationId: number,
): Promise<NotificationDetailResponse> {
    return new Promise((resolve, reject) => {
        channel.get({
            url: `/json/broadcast_notifications/${notificationId}`,
            success(data) {
                resolve(data as NotificationDetailResponse);
            },
            error(xhr) {
                reject(
                    new Error(xhr.responseJSON?.msg || "Failed to fetch notification details"),
                );
            },
        });
    });
}

export async function fetchRecipients(notificationId: number): Promise<RecipientsResponse> {
    return new Promise((resolve, reject) => {
        channel.get({
            url: `/json/broadcast_notifications/${notificationId}/recipients`,
            success(data) {
                resolve(data as RecipientsResponse);
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to fetch recipients"));
            },
        });
    });
}

export async function aiCompose(request: {
    subject?: string;
    template_id?: number;
    prompt: string;
    media_content?: Record<string, string>;
}): Promise<{ subject: string; content: string; media_content: Record<string, string> }> {
    return new Promise((resolve, reject) => {
        const data: Record<string, unknown> = {
            prompt: request.prompt,
        };

        if (request.subject !== undefined) {
            data.subject = request.subject;
        }
        if (request.template_id !== undefined) {
            data.template_id = JSON.stringify(request.template_id);
        }
        if (request.media_content !== undefined) {
            data.media_content = JSON.stringify(request.media_content);
        }

        channel.post({
            url: "/json/broadcast/ai_compose",
            data,
            success(resp) {
                resolve((resp || {subject: "", content: "", media_content: {}}) as { subject: string; content: string; media_content: Record<string, string> });
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to compose with AI"));
            },
        });
    });
}

