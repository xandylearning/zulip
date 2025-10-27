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
            success(data: TemplatesResponse) {
                resolve(data);
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to fetch templates"));
            },
        });
    });
}

export async function createTemplate(template: {name: string, content: string}): Promise<void> {
    return new Promise((resolve, reject) => {
        channel.post({
            url: "/json/notification_templates",
            data: template,
            success() {
                resolve();
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to create template"));
            },
        });
    });
}

export async function updateTemplate(templateId: number, template: {name: string, content: string}): Promise<void> {
    return new Promise((resolve, reject) => {
        channel.patch({
            url: `/json/notification_templates/${templateId}`,
            data: template,
            success() {
                resolve();
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to update template"));
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
        channel.post({
            url: "/json/broadcast_notification",
            data: {
                subject: request.subject,
                content: request.content,
                target_type: request.target_type,
                target_ids: JSON.stringify(request.target_ids),
                template_id: request.template_id,
                attachment_paths: request.attachment_paths
                    ? JSON.stringify(request.attachment_paths)
                    : undefined,
            },
            success(data: SendNotificationResponse) {
                resolve(data);
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
            success(data: NotificationsResponse) {
                resolve(data);
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
            success(data: NotificationDetailResponse) {
                resolve(data);
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
            success(data: RecipientsResponse) {
                resolve(data);
            },
            error(xhr) {
                reject(new Error(xhr.responseJSON?.msg || "Failed to fetch recipients"));
            },
        });
    });
}

