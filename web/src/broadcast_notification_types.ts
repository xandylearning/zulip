// TypeScript types for broadcast notification system

import type {TemplateStructure} from "./broadcast_template_blocks.ts";

export interface NotificationTemplate {
    id: number;
    name: string;
    content: string;
    template_type: "text_only" | "rich_media";
    template_structure: TemplateStructure;
    ai_generated: boolean;
    ai_prompt: string;
    creator_email: string;
    creator_full_name: string;
    created_time: number;
    last_edit_time: number;
}

export interface BroadcastNotification {
    id: number;
    subject: string;
    content: string;
    sender_email: string;
    sender_full_name: string;
    sent_time: number;
    target_type: "users" | "channels" | "broadcast";
    target_ids: number[];
    attachment_paths: string[];
    template_name: string | null;
    recipient_count?: number;
    statistics?: NotificationStatistics;
}

export interface NotificationRecipient {
    id: number;
    user_email: string;
    user_full_name: string;
    channel_name: string | null;
    status: "queued" | "sent" | "delivered" | "read" | "failed";
    sent_time: number | null;
    delivered_time: number | null;
    read_time: number | null;
    error_message: string | null;
    message_id: number | null;
}

export interface NotificationStatistics {
    total_recipients: number;
    status_breakdown: {
        queued: number;
        sent: number;
        delivered: number;
        read: number;
        failed: number;
    };
    success_rate: number;
    failure_rate: number;
}

export interface APIResponse<T> {
    result: "success" | "error";
    msg?: string;
    data?: T;
}

export interface TemplatesResponse {
    templates: NotificationTemplate[];
}

export interface NotificationsResponse {
    notifications: BroadcastNotification[];
}

export interface NotificationDetailResponse extends BroadcastNotification {
    statistics: NotificationStatistics;
}

export interface RecipientsResponse {
    recipients: NotificationRecipient[];
}

export interface SendNotificationRequest {
    subject: string;
    content: string;
    target_type: "users" | "channels" | "broadcast";
    target_ids: number[];
    template_id?: number;
    attachment_paths?: string[];
    media_content?: Record<string, string>; // Block ID -> media URL mapping
}

export interface SendNotificationResponse {
    notification_id: number;
    sent_time: number;
}

export type RecipientType = "all" | "users" | "channels";

