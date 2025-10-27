// UI component builders for broadcast notification system

import {$t} from "./i18n.ts";
import type {
    BroadcastNotification,
    NotificationRecipient,
    NotificationStatistics,
    NotificationTemplate,
} from "./broadcast_notification_types.ts";
// Simple date formatter that doesn't depend on user_settings
function formatDateTime(date: Date): {time_str: string; date_str: string} {
    const now = new Date();
    const diffMs = now.getTime() - date.getTime();
    const diffMinutes = Math.floor(diffMs / (1000 * 60));
    const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    // Format time (24-hour format)
    const timeStr = date.toLocaleTimeString('en-US', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit'
    });

    // Format date
    const dateStr = date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });

    // Relative time for recent notifications
    if (diffMinutes < 1) {
        return {time_str: "Just now", date_str: dateStr};
    } else if (diffMinutes < 60) {
        return {time_str: `${diffMinutes}m ago`, date_str: dateStr};
    } else if (diffHours < 24) {
        return {time_str: `${diffHours}h ago`, date_str: dateStr};
    } else if (diffDays < 7) {
        return {time_str: `${diffDays}d ago`, date_str: dateStr};
    } else {
        return {time_str: timeStr, date_str: dateStr};
    }
}

export function buildHeader(): string {
    return `
        <div class="broadcast-notification-header">
            <h1>${$t({defaultMessage: "Broadcast Notifications"})}</h1>
            <p class="subtitle">${$t({defaultMessage: "Send important announcements to users in your organization"})}</p>
        </div>
    `;
}

export function buildTabs(): string {
    return `
        <div class="broadcast-notification-tabs">
            <button class="tab-button active" data-tab="send">
                ${$t({defaultMessage: "Send Notification"})}
            </button>
            <button class="tab-button" data-tab="templates">
                ${$t({defaultMessage: "Templates"})}
            </button>
            <button class="tab-button" data-tab="history">
                ${$t({defaultMessage: "Notification History"})}
            </button>
        </div>
    `;
}

export function buildNotificationForm(templates: NotificationTemplate[]): string {
    const templateOptions = templates
        .map(
            (t) =>
                `<option value="${t.id}">${t.name.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</option>`,
        )
        .join("");

    return `
        <div class="broadcast-notification-form">
            <div class="form-group">
                <div class="label-with-actions">
                    <label for="template-select">${$t({defaultMessage: "Template (Optional)"})}</label>
                    <button type="button" class="btn btn-link" id="use-template-btn">${$t({defaultMessage: "Use Template"})}</button>
                </div>
                <select id="template-select" class="form-control">
                    <option value="">${$t({defaultMessage: "No template"})}</option>
                    ${templateOptions}
                </select>
            </div>

            <div class="form-group">
                <label for="notification-subject">${$t({defaultMessage: "Subject"})}</label>
                <input 
                    type="text" 
                    id="notification-subject" 
                    class="form-control" 
                    placeholder="${$t({defaultMessage: "Enter notification subject"})}"
                    required
                />
            </div>

            <div class="form-group">
                <div class="label-with-actions">
                    <label for="notification-content">${$t({defaultMessage: "Message"})}</label>
                    <button type="button" class="btn-link" id="toggle-preview">
                        ${$t({defaultMessage: "Preview"})}
                    </button>
                </div>
                <textarea 
                    id="notification-content" 
                    class="form-control" 
                    rows="8"
                    placeholder="${$t({defaultMessage: "Enter message content (Markdown supported)"})}"
                    required
                ></textarea>
                <div id="markdown-preview" class="markdown-preview" style="display: none;"></div>
            </div>

            <div class="form-group">
                <label>${$t({defaultMessage: "Recipients"})}</label>
                <div class="recipient-type-tabs">
                    <button type="button" class="recipient-tab active" data-type="all">
                        ${$t({defaultMessage: "All Users"})}
                    </button>
                    <button type="button" class="recipient-tab" data-type="users">
                        ${$t({defaultMessage: "Specific Users"})}
                    </button>
                    <button type="button" class="recipient-tab" data-type="channels">
                        ${$t({defaultMessage: "Channels"})}
                    </button>
                </div>
                <div id="recipient-selector" class="recipient-selector" style="display: none;">
                    <div id="pill-container" class="pill_container"></div>
                </div>
            </div>

            <div class="form-actions">
                <button type="button" id="send-notification-btn" class="btn btn-primary">
                    ${$t({defaultMessage: "Send Notification"})}
                </button>
                <button type="button" id="cancel-btn" class="btn btn-default">
                    ${$t({defaultMessage: "Cancel"})}
                </button>
            </div>
        </div>
    `;
}

export function buildNotificationCard(notification: BroadcastNotification): string {
    const formattedTime = formatDateTime(new Date(notification.sent_time * 1000));
    const recipientCount = notification.recipient_count || 0;

    return `
        <div class="notification-card" data-notification-id="${notification.id}">
            <div class="notification-header">
                <h3 class="notification-subject">${notification.subject.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</h3>
                <span class="notification-time">${formattedTime.time_str}</span>
            </div>
            <div class="notification-meta">
                <span class="sender">${$t({defaultMessage: "From"})}: ${notification.sender_full_name.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span>
                <span class="separator">•</span>
                <span class="recipients">${recipientCount} ${$t({defaultMessage: "recipients"})}</span>
                <span class="separator">•</span>
                <span class="target-type">${formatTargetType(notification.target_type)}</span>
            </div>
            <div class="notification-actions">
                <button class="btn-link view-details" data-notification-id="${notification.id}">
                    ${$t({defaultMessage: "View Details"})}
                </button>
            </div>
            <div class="notification-details" data-notification-id="${notification.id}" style="display: none;">
                <div class="loading">${$t({defaultMessage: "Loading..."})}</div>
            </div>
        </div>
    `;
}

export function buildNotificationDetails(
    notification: BroadcastNotification,
    recipients: NotificationRecipient[],
): string {
    const stats = notification.statistics!;

    return `
        <div class="notification-details-content">
            <div class="notification-full-content">
                <h4>${$t({defaultMessage: "Message Content"})}</h4>
                <div class="rendered-markdown">${notification.content.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
            </div>

            ${buildStatisticsBadges(stats)}

            <div class="recipients-list">
                <h4>${$t({defaultMessage: "Recipients"})}</h4>
                ${buildRecipientStatusTable(recipients)}
            </div>
        </div>
    `;
}

export function buildStatisticsBadges(stats: NotificationStatistics): string {
    return `
        <div class="statistics-badges">
            <div class="stat-badge stat-total">
                <span class="stat-value">${stats.total_recipients}</span>
                <span class="stat-label">${$t({defaultMessage: "Total"})}</span>
            </div>
            <div class="stat-badge stat-sent">
                <span class="stat-value">${stats.status_breakdown.sent}</span>
                <span class="stat-label">${$t({defaultMessage: "Sent"})}</span>
            </div>
            <div class="stat-badge stat-delivered">
                <span class="stat-value">${stats.status_breakdown.delivered}</span>
                <span class="stat-label">${$t({defaultMessage: "Delivered"})}</span>
            </div>
            <div class="stat-badge stat-read">
                <span class="stat-value">${stats.status_breakdown.read}</span>
                <span class="stat-label">${$t({defaultMessage: "Read"})}</span>
            </div>
            <div class="stat-badge stat-failed">
                <span class="stat-value">${stats.status_breakdown.failed}</span>
                <span class="stat-label">${$t({defaultMessage: "Failed"})}</span>
            </div>
            <div class="stat-badge stat-success-rate">
                <span class="stat-value">${stats.success_rate.toFixed(1)}%</span>
                <span class="stat-label">${$t({defaultMessage: "Success Rate"})}</span>
            </div>
        </div>
    `;
}

export function buildRecipientStatusTable(recipients: NotificationRecipient[]): string {
    const rows = recipients
        .map((recipient) => {
            const statusClass = `status-${recipient.status}`;
            const sentTime = recipient.sent_time
                ? formatDateTime(new Date(recipient.sent_time * 1000)).time_str
                : "-";

            return `
            <tr>
                <td>${recipient.user_full_name.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</td>
                <td>${recipient.user_email.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</td>
                <td>${recipient.channel_name ? recipient.channel_name.replace(/</g, "&lt;").replace(/>/g, "&gt;") : "-"}</td>
                <td><span class="status-badge ${statusClass}">${recipient.status}</span></td>
                <td>${sentTime}</td>
                <td class="error-cell">${recipient.error_message ? recipient.error_message.replace(/</g, "&lt;").replace(/>/g, "&gt;") : "-"}</td>
            </tr>
        `;
        })
        .join("");

    return `
        <table class="recipients-table">
            <thead>
                <tr>
                    <th>${$t({defaultMessage: "Name"})}</th>
                    <th>${$t({defaultMessage: "Email"})}</th>
                    <th>${$t({defaultMessage: "Channel"})}</th>
                    <th>${$t({defaultMessage: "Status"})}</th>
                    <th>${$t({defaultMessage: "Sent Time"})}</th>
                    <th>${$t({defaultMessage: "Error"})}</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    `;
}

export function buildLoadingSpinner(): string {
    return `
        <div class="loading-spinner">
            <div class="spinner"></div>
            <p>${$t({defaultMessage: "Loading..."})}</p>
        </div>
    `;
}

export function buildErrorMessage(message: string): string {
    return `
        <div class="error-message">
            <i class="fa fa-exclamation-circle"></i>
            <span>${message.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span>
        </div>
    `;
}

export function buildSuccessMessage(message: string): string {
    return `
        <div class="success-message">
            <i class="fa fa-check-circle"></i>
            <span>${message.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</span>
        </div>
    `;
}

function formatTargetType(targetType: string): string {
    switch (targetType) {
        case "broadcast":
            return $t({defaultMessage: "All Users"});
        case "users":
            return $t({defaultMessage: "Specific Users"});
        case "channels":
            return $t({defaultMessage: "Channels"});
        default:
            return targetType;
    }
}

// Template Management Components
export function buildTemplateTab(): string {
    return `
        <div class="settings-section">
            <div class="settings_panel_list_header">
                <h3>${$t({defaultMessage: "Templates"})}</h3>
                <div style="display: flex; gap: 12px; align-items: center;">
                    <input type="text" class="search-input" id="template-search" placeholder="${$t({defaultMessage: "Search templates..."})}">
                    <button class="btn btn-primary" id="add-template-btn">${$t({defaultMessage: "Add Template"})}</button>
                </div>
            </div>
            <div id="templates-table-container">
                <div class="loading-spinner"></div>
            </div>
        </div>
    `;
}

export function buildTemplateTable(templates: NotificationTemplate[]): string {
    if (templates.length === 0) {
        return `
            <div class="empty-state">
                <h4>${$t({defaultMessage: "No templates found"})}</h4>
                <p>${$t({defaultMessage: "Create your first template to get started."})}</p>
            </div>
        `;
    }

    const rows = templates
        .map((template) => {
            const createdTime = formatDateTime(new Date(template.created_time * 1000)).time_str;
            return `
                <tr>
                    <td>${template.name.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</td>
                    <td>${template.creator_full_name.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</td>
                    <td>${createdTime}</td>
                    <td>
                        <div class="template-actions">
                            <button class="btn btn-default edit-template" data-template-id="${template.id}">${$t({defaultMessage: "Edit"})}</button>
                            <button class="btn btn-default delete-template" data-template-id="${template.id}">${$t({defaultMessage: "Delete"})}</button>
                        </div>
                    </td>
                </tr>
            `;
        })
        .join("");

    return `
        <table class="table table-striped">
            <thead>
                <tr>
                    <th>${$t({defaultMessage: "Name"})}</th>
                    <th>${$t({defaultMessage: "Creator"})}</th>
                    <th>${$t({defaultMessage: "Created"})}</th>
                    <th>${$t({defaultMessage: "Actions"})}</th>
                </tr>
            </thead>
            <tbody>
                ${rows}
            </tbody>
        </table>
    `;
}

export function buildTemplateModal(template?: NotificationTemplate): string {
    const isEdit = !!template;
    const title = isEdit ? $t({defaultMessage: "Edit Template"}) : $t({defaultMessage: "Add Template"});
    const nameValue = template?.name || "";
    const contentValue = template?.content || "";

    return `
        <div class="modal-overlay" id="template-modal-overlay">
            <div class="modal">
                <div class="modal-header">
                    <h3 class="modal-title">${title}</h3>
                    <button class="modal-close" id="template-modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <form id="template-form">
                        <div class="form-group">
                            <label for="template-name">${$t({defaultMessage: "Template Name"})}</label>
                            <input type="text" id="template-name" class="form-control" value="${nameValue}" required>
                        </div>
                        <div class="form-group">
                            <label for="template-content">${$t({defaultMessage: "Content"})}</label>
                            <textarea id="template-content" class="form-control" rows="10" required>${contentValue}</textarea>
                        </div>
                    </form>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default" id="template-modal-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary" id="template-modal-save">${$t({defaultMessage: "Save"})}</button>
                </div>
            </div>
        </div>
    `;
}

export function buildDeleteConfirmModal(templateId: number, templateName: string): string {
    return `
        <div class="modal-overlay" id="delete-modal-overlay">
            <div class="modal">
                <div class="modal-header">
                    <h3 class="modal-title">${$t({defaultMessage: "Delete Template"})}</h3>
                    <button class="modal-close" id="delete-modal-close">&times;</button>
                </div>
                <div class="modal-body">
                    <p>${$t({defaultMessage: "Are you sure you want to delete the template"})} <strong>"${templateName.replace(/</g, "&lt;").replace(/>/g, "&gt;")}"</strong>?</p>
                    <p class="text-muted">${$t({defaultMessage: "This action cannot be undone."})}</p>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default" id="delete-modal-cancel">${$t({defaultMessage: "Cancel"})}</button>
                    <button class="btn btn-primary" id="delete-modal-confirm" data-template-id="${templateId}">${$t({defaultMessage: "Delete"})}</button>
                </div>
            </div>
        </div>
    `;
}

export function buildTemplateSelectorModal(templates: NotificationTemplate[]): string {
    const templateItems = templates
        .map((template) => `
            <div class="template-item" data-template-id="${template.id}">
                <div class="template-name">${template.name.replace(/</g, "&lt;").replace(/>/g, "&gt;")}</div>
                <div class="template-preview">${template.content.substring(0, 100)}${template.content.length > 100 ? "..." : ""}</div>
            </div>
        `)
        .join("");

    return `
        <div class="modal-overlay" id="template-selector-overlay">
            <div class="modal">
                <div class="modal-header">
                    <h3 class="modal-title">${$t({defaultMessage: "Select Template"})}</h3>
                    <button class="modal-close" id="template-selector-close">&times;</button>
                </div>
                <div class="modal-body">
                    <div class="template-list">
                        ${templateItems}
                    </div>
                </div>
                <div class="modal-footer">
                    <button class="btn btn-default" id="template-selector-cancel">${$t({defaultMessage: "Cancel"})}</button>
                </div>
            </div>
        </div>
    `;
}

