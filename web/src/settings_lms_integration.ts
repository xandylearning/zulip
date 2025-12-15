/**
 * LMS Integration Admin Interface
 * TypeScript module for managing LMS integration settings and operations.
 */

import $ from "jquery";
import * as channel from "./channel.ts";
import * as ui_report from "./ui_report.ts";
import * as loading from "./loading.ts";

// Type declarations for Bootstrap modal
declare global {
    interface JQuery {
        modal(action?: string): JQuery;
    }
}

interface Student {
    name: string;
    email: string;
    status: string;
}

interface Mentor {
    name: string;
    email: string;
    status: string;
}

// Global state for the LMS integration admin interface
let dashboard_data: any = null;
let sync_in_progress = false;

// ===================================
// INITIALIZATION AND TAB MANAGEMENT
// ===================================

export function initialize(): void {
    // Initialize tab switching
    $(".lms-integration-tabs .nav-link").on("click", function (e) {
        e.preventDefault();
        const tab_id = $(this).attr("href")?.substring(1);
        if (tab_id) {
            switch_to_tab(tab_id);
        }
    });

    // Initialize dashboard refresh
    $("#reload-lms-status").on("click", function () {
        load_dashboard_status();
    });

    // Initialize user sync controls
    $("#start-user-sync").on("click", start_user_sync);
    $("#trigger-full-sync").on("click", function () {
        start_user_sync();
    });

    // Initialize activity monitoring controls
    $("#poll-activities").on("click", poll_activities);
    $("#check-activities").on("click", poll_activities);
    $("#process-pending-events").on("click", process_pending_events);

    // Initialize configuration test buttons
    $("#test-db-connection").on("click", test_database_connection);
    $("#test-lms-connection").on("click", test_database_connection);
    $("#test-jwt-config").on("click", test_jwt_configuration);

    // Initialize batch management controls
    $("#sync-batches").on("click", sync_all_batches);
    $("#create-batch-group").on("click", create_batch_group);

    // Initialize configuration form handlers
    $(".lms-configuration-form").on("submit", function (e) {
        e.preventDefault();
        save_configuration();
    });

    // Initialize log controls
    $("#refresh-logs").on("click", () => load_logs());
    $("#download-logs").on("click", () => download_logs());

    // Initialize filtering
    $("#user-type-filter, #user-search").on("change keyup", () => debounce(load_synced_users, 300)());
    $("#activity-type-filter, #activity-search").on("change keyup", () => debounce(load_activity_events, 300)());
    $("#log-level-filter, #log-source-filter").on("change", () => load_logs());

    // Copy webhook URL functionality
    $("#copy-webhook-url").on("click", copy_webhook_url);

    // Load initial data
    load_dashboard_status();
    load_current_configuration();
}

function switch_to_tab(tab_id: string): void {
    // Update active tab
    $(".lms-integration-tabs .nav-link").removeClass("active");
    $(".lms-integration-tabs .tab-pane").removeClass("active");

    $(`.lms-integration-tabs .nav-link[href="#${tab_id}"]`).addClass("active");
    $(`#${tab_id}`).addClass("active");

    // Load tab-specific data
    switch (tab_id) {
        case "lms-dashboard":
            load_dashboard_status();
            break;
        case "lms-user-sync":
            load_synced_users();
            load_sync_history();
            break;
        case "lms-batch-management":
            load_batch_groups();
            break;
        case "lms-activity-monitoring":
            load_activity_events();
            load_activity_stats();
            break;
        case "lms-configuration":
            load_current_configuration();
            break;
        case "lms-logs":
            load_logs();
            break;
    }
}

// ===================================
// DASHBOARD FUNCTIONALITY
// ===================================

function load_dashboard_status(): void {
    loading.make_indicator($("#lms-status-badge"));

    channel.get({
        url: "/api/v1/lms/admin/dashboard/status",
        success(response: any) {
            dashboard_data = response.data;
            update_dashboard_ui(response.data);
            update_status_badge("connected", "Connected");
        },
        error(xhr) {
            update_status_badge("disconnected", "Disconnected");
            ui_report.error("Failed to load LMS status", xhr, $("#lms-integration-status"));
        },
    });
}

function update_dashboard_ui(data: any): void {
    // Update stat cards
    $("#total-synced-users").text(data.total_synced_users || "—");
    $("#total-students").text(data.total_students || "—");
    $("#total-mentors").text(data.total_mentors || "—");
    $("#total-batches").text(data.total_batches || "—");

    // Update activity summary
    $("#last-sync-time").text(data.last_sync_time ? format_datetime(data.last_sync_time) : "Never");
    $("#last-activity-check").text(data.last_activity_check ? format_datetime(data.last_activity_check) : "Never");
    $("#pending-notifications").text(data.pending_notifications || "0");

    // Update monitor status
    const monitor_status = data.monitor_status || "stopped";
    $("#monitor-status").text(monitor_status === "running" ? "Running" : "Stopped");
    $("#events-today").text(data.events_today || "0");
    $("#notifications-sent").text(data.notifications_sent || "0");
}

function update_status_badge(status: string, text: string): void {
    const $badge = $("#lms-status-badge");
    $badge.removeClass("connected disconnected warning").addClass(status);
    $badge.text(text);
}

// ===================================
// USER SYNC FUNCTIONALITY
// ===================================

function start_user_sync(): void {
    if (sync_in_progress) {
        ui_report.error("Sync already in progress", undefined, $("#lms-integration-status"));
        return;
    }

    const sync_type = $('input[name="sync_type"]:checked').val() as string;
    const sync_batches = $("#sync_batches").is(":checked");

    sync_in_progress = true;
    $("#start-user-sync").prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Syncing...');
    $("#sync-progress").show();

    update_sync_progress(0, "Starting sync...");

    channel.post({
        url: "/api/v1/lms/admin/users/sync",
        data: {
            sync_type,
            sync_batches,
        },
        success(response: any) {
            sync_in_progress = false;
            $("#start-user-sync").prop("disabled", false).html('<i class="fa fa-play"></i> Start Sync');
            $("#sync-progress").hide();

            const stats = response.stats;
            const message = `Sync completed: ${stats.created} created, ${stats.updated} updated, ${stats.skipped} skipped, ${stats.errors} errors`;
            ui_report.success(message, $("#lms-integration-status"));

            // Refresh dashboard and user list
            load_dashboard_status();
            load_synced_users();
            load_sync_history();
        },
        error(xhr) {
            sync_in_progress = false;
            $("#start-user-sync").prop("disabled", false).html('<i class="fa fa-play"></i> Start Sync');
            $("#sync-progress").hide();
            ui_report.error("Sync failed", xhr, $("#lms-integration-status"));
        },
    });
}

function update_sync_progress(percentage: number, text: string): void {
    $("#sync-progress-fill").css("width", `${percentage}%`);
    $("#sync-progress-text").text(text);
}

function load_synced_users(page: number = 1): void {
    const user_type = $("#user-type-filter").val() as string;
    const search = $("#user-search").val() as string;

    const data: any = {page};
    if (user_type) {
        data.user_type = user_type;
    }
    if (search) {
        data.search = search;
    }

    channel.get({
        url: "/api/v1/lms/admin/users/list",
        data,
        success(response: any) {
            render_users_table(response.users);
            update_pagination("#synced-users-table", response);
        },
        error(xhr) {
            ui_report.error("Failed to load users", xhr, $("#lms-integration-status"));
        },
    });
}

function load_sync_history(page: number = 1): void {
    channel.get({
        url: "/api/v1/lms/admin/sync/history",
        data: {page},
        success(response: any) {
            render_sync_history_table(response.history);
            update_pagination("#sync-history-table", response);
        },
        error(xhr) {
            ui_report.error("Failed to load sync history", xhr, $("#lms-integration-status"));
        },
    });
}

function render_users_table(users: any[]): void {
    const $tbody = $("#synced-users-table");
    $tbody.empty();

    for (const user of users) {
        const type_badge = user.type === 'student' ? 'badge-primary' : 'badge-success';
        const $row = $(`
            <tr>
                <td>${user.name}</td>
                <td>${user.email}</td>
                <td><span class="badge ${type_badge}">${user.type}</span></td>
                <td>${user.lms_id || "—"}</td>
                <td>${user.last_sync ? format_datetime(user.last_sync) : "—"}</td>
                <td><span class="status-badge ${user.status}">${user.status}</span></td>
                <td class="actions">
                    <button class="btn btn-sm btn-outline" onclick="resync_user(${user.id})">
                        <i class="fa fa-sync"></i> Resync
                    </button>
                </td>
            </tr>
        `);
        $tbody.append($row);
    }
}

function render_sync_history_table(history: any[]): void {
    const $tbody = $("#sync-history-table");
    $tbody.empty();

    for (const sync of history) {
        const status_class = sync.status === 'success' ? 'text-success' :
                           sync.status === 'partial' ? 'text-warning' : 'text-danger';
        const duration = Math.round(sync.duration_seconds);

        const $row = $(`
            <tr>
                <td>${format_datetime(sync.started_at)}</td>
                <td><span class="badge badge-secondary">${sync.sync_type}</span></td>
                <td><span class="${status_class}"><i class="fa fa-circle"></i> ${sync.status}</span></td>
                <td>${sync.users_created}</td>
                <td>${sync.users_updated}</td>
                <td>${sync.users_skipped}</td>
                <td>${sync.users_errors}</td>
                <td>${duration}s</td>
            </tr>
        `);
        $tbody.append($row);
    }
}

// ===================================
// ACTIVITY MONITORING
// ===================================

function poll_activities(): void {
    loading.make_indicator($("#poll-activities"));

    channel.post({
        url: "/api/v1/lms/admin/activities/poll",
        success(response: any) {
            loading.destroy_indicator($("#poll-activities"));
            const message = `Found ${response.new_events_count} new activities`;
            ui_report.success(message, $("#lms-integration-status"));

            // Refresh activity data
            load_activity_events();
            load_activity_stats();
            load_dashboard_status();
        },
        error(xhr) {
            loading.destroy_indicator($("#poll-activities"));
            ui_report.error("Activity polling failed", xhr, $("#lms-integration-status"));
        },
    });
}

function process_pending_events(): void {
    loading.make_indicator($("#process-pending-events"));

    channel.post({
        url: "/api/v1/lms/admin/activities/process-pending",
        success(response: any) {
            loading.destroy_indicator($("#process-pending-events"));
            const message = `Processed ${response.processed_count} pending events`;
            ui_report.success(message, $("#lms-integration-status"));

            // Refresh activity data and dashboard
            load_activity_events();
            load_activity_stats();
            load_dashboard_status();
        },
        error(xhr) {
            loading.destroy_indicator($("#process-pending-events"));
            ui_report.error("Failed to process pending events", xhr, $("#lms-integration-status"));
        },
    });
}

function load_activity_events(page: number = 1): void {
    const event_type = $("#activity-type-filter").val() as string;
    const search = $("#activity-search").val() as string;

    const data: any = {page};
    if (event_type) {
        data.event_type = event_type;
    }
    if (search) {
        data.search = search;
    }

    channel.get({
        url: "/api/v1/lms/admin/activities/events",
        data,
        success(response: any) {
            render_activity_events_table(response.events);
            update_pagination("#activity-events-table", response);
        },
        error(xhr) {
            ui_report.error("Failed to load activity events", xhr, $("#lms-integration-status"));
        },
    });
}

function load_activity_stats(): void {
    // Activity stats are loaded as part of dashboard data
    if (dashboard_data) {
        $("#last-activity-poll").text(dashboard_data.last_activity_check ? format_datetime(dashboard_data.last_activity_check) : "Never");
    }
}

function render_activity_events_table(events: any[]): void {
    const $tbody = $("#activity-events-table");
    $tbody.empty();

    for (const event of events) {
        const notification_badge = get_notification_status_badge(event.notification_status);
        const $row = $(`
            <tr>
                <td>${format_datetime(event.timestamp)}</td>
                <td>${event.event_type}</td>
                <td>${event.student_username}</td>
                <td>${event.activity_title}</td>
                <td>${notification_badge}</td>
                <td><span class="status-badge ${event.notification_status}">${event.notification_status}</span></td>
                <td class="actions">
                    <button class="btn btn-sm btn-outline" onclick="view_event_details(${event.id})">
                        <i class="fa fa-eye"></i> Details
                    </button>
                </td>
            </tr>
        `);
        $tbody.append($row);
    }
}

function get_notification_status_badge(status: string): string {
    switch (status) {
        case "sent":
            return '<i class="fa fa-check text-success"></i>';
        case "failed":
        case "error":
            return '<i class="fa fa-times text-danger"></i>';
        case "pending":
            return '<i class="fa fa-clock text-warning"></i>';
        default:
            return '<i class="fa fa-question text-muted"></i>';
    }
}

// ===================================
// CONFIGURATION MANAGEMENT
// ===================================

function load_current_configuration(): void {
    channel.get({
        url: "/api/v1/lms/admin/config/get",
        success(response: any) {
            populate_configuration_form(response);
        },
        error(xhr) {
            ui_report.error("Failed to load configuration", xhr, $("#lms-integration-status"));
        },
    });
}

function populate_configuration_form(config: any): void {
    $("#id_lms_enabled").prop("checked", config.lms_enabled);
    $("#id_lms_db_host").val(config.lms_db_host || "");
    $("#id_lms_db_port").val(config.lms_db_port || 5432);
    $("#id_lms_db_name").val(config.lms_db_name || "");
    $("#id_lms_db_username").val(config.lms_db_username || "");

    // Show placeholder for password if it's set
    if (config.lms_db_password_set) {
        $("#id_lms_db_password").attr("placeholder", "••••••••");
    }

    // Show placeholder for webhook secret if it's set
    if (config.webhook_secret_set) {
        $("#id_webhook_secret").attr("placeholder", "••••••••");
    }

    $("#id_jwt_enabled").prop("checked", config.jwt_enabled);
    $("#id_testpress_api_url").val(config.testpress_api_url || "");
    $("#id_activity_monitor_enabled").prop("checked", config.activity_monitor_enabled);
    $("#id_poll_interval").val(config.poll_interval || 60);
    $("#id_notify_mentors").prop("checked", config.notify_mentors);
    $("#webhook-endpoint-url").text(config.webhook_endpoint_url || "");
}

function save_configuration(): void {
    const data: any = {
        lms_enabled: $("#id_lms_enabled").is(":checked"),
        lms_db_host: $("#id_lms_db_host").val(),
        lms_db_port: parseInt($("#id_lms_db_port").val() as string, 10),
        lms_db_name: $("#id_lms_db_name").val(),
        lms_db_username: $("#id_lms_db_username").val(),
        jwt_enabled: $("#id_jwt_enabled").is(":checked"),
        testpress_api_url: $("#id_testpress_api_url").val(),
        activity_monitor_enabled: $("#id_activity_monitor_enabled").is(":checked"),
        poll_interval: parseInt($("#id_poll_interval").val() as string, 10),
        notify_mentors: $("#id_notify_mentors").is(":checked"),
    };

    // Only include password if it's been changed
    const password = $("#id_lms_db_password").val() as string;
    if (password && password !== "") {
        data.lms_db_password = password;
    }

    // Only include webhook secret if it's been changed
    const webhook_secret = $("#id_webhook_secret").val() as string;
    if (webhook_secret && webhook_secret !== "") {
        data.webhook_secret = webhook_secret;
    }

    channel.post({
        url: "/api/v1/lms/admin/config/update",
        data,
        success(response: any) {
            ui_report.success("Configuration saved successfully", $("#lms-integration-status"));
            // Refresh the form to show updated placeholders
            load_current_configuration();
        },
        error(xhr) {
            ui_report.error("Failed to save configuration", xhr, $("#lms-integration-status"));
        },
    });
}

function test_database_connection(): void {
    loading.make_indicator($("#test-db-connection"));

    channel.post({
        url: "/api/v1/lms/admin/config/test-db",
        success(response: any) {
            loading.destroy_indicator($("#test-db-connection"));
            const $status = $("#db-connection-status");
            $status.removeClass("error").addClass("success");
            $status.text(response.message).show();

            if (response.details) {
                $status.append(`<br>Students: ${response.details.students_available}, Mentors: ${response.details.mentors_available}`);
            }
        },
        error(xhr) {
            loading.destroy_indicator($("#test-db-connection"));
            const $status = $("#db-connection-status");
            $status.removeClass("success").addClass("error");
            $status.text("Database connection failed").show();
        },
    });
}

function test_jwt_configuration(): void {
    loading.make_indicator($("#test-jwt-config"));

    channel.post({
        url: "/api/v1/lms/admin/config/test-jwt",
        success(response: any) {
            loading.destroy_indicator($("#test-jwt-config"));
            const $status = $("#jwt-config-status");
            $status.removeClass("error").addClass("success");
            $status.text(response.message).show();

            if (response.details) {
                $status.append(`<br>Token valid: ${response.details.token_valid ? "Yes" : "No"}`);
                if (response.details.expires_at) {
                    $status.append(`<br>Expires: ${format_datetime(response.details.expires_at)}`);
                }
            }
        },
        error(xhr) {
            loading.destroy_indicator($("#test-jwt-config"));
            const $status = $("#jwt-config-status");
            $status.removeClass("success").addClass("error");
            $status.text("JWT configuration test failed").show();
        },
    });
}

function copy_webhook_url(): void {
    const url = $("#webhook-endpoint-url").text();

    if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(function () {
            ui_report.success("Webhook URL copied to clipboard", $("#lms-integration-status"));
        }).catch(function () {
            ui_report.error("Failed to copy webhook URL", undefined, $("#lms-integration-status"));
        });
    } else {
        // Fallback for older browsers
        try {
            const $temp = $("<input>");
            $("body").append($temp);
            $temp.val(url);
            ($temp[0] as HTMLInputElement).select();
            const successful = document.execCommand("copy");
            $temp.remove();
            if (successful) {
                ui_report.success("Webhook URL copied to clipboard", $("#lms-integration-status"));
            } else {
                ui_report.error("Failed to copy webhook URL", undefined, $("#lms-integration-status"));
            }
        } catch (err) {
            ui_report.error("Failed to copy webhook URL", undefined, $("#lms-integration-status"));
        }
    }
}

// ===================================
// BATCH MANAGEMENT
// ===================================

function load_batch_groups(page: number = 1): void {
    channel.get({
        url: "/api/v1/lms/admin/batches/list",
        data: {page},
        success(response: any) {
            render_batch_groups_table(response.batches);
            update_pagination("#batch-groups-table", response);
        },
        error(xhr) {
            ui_report.error("Failed to load batch groups", xhr, $("#lms-integration-status"));
        },
    });
}

function render_batch_groups_table(batches: any[]): void {
    const $tbody = $("#batch-groups-table");
    $tbody.empty();

    for (const batch of batches) {
        const status_class = batch.status === 'active' ? 'text-success' : 'text-muted';
        const group_status = batch.zulip_group_exists ?
            '<i class="fa fa-check text-success"></i> Linked' :
            '<i class="fa fa-times text-warning"></i> Not Linked';

        const $row = $(`
            <tr>
                <td>${batch.batch_name}</td>
                <td>${group_status}</td>
                <td>${batch.student_count}</td>
                <td>${batch.mentor_count}</td>
                <td>${batch.last_sync ? format_datetime(batch.last_sync) : "Never"}</td>
                <td><span class="${status_class}"><i class="fa fa-circle"></i> ${batch.status}</span></td>
                <td class="actions">
                    <button class="btn btn-sm btn-outline" onclick="sync_batch_group(${batch.id})">
                        <i class="fa fa-sync"></i> Sync
                    </button>
                    <button class="btn btn-sm btn-outline" onclick="view_batch_details(${batch.id})">
                        <i class="fa fa-eye"></i> View
                    </button>
                </td>
            </tr>
        `);
        $tbody.append($row);
    }
}

function sync_all_batches(): void {
    loading.make_indicator($("#sync-batches"));

    // Use the same user sync endpoint with batch sync enabled
    channel.post({
        url: "/api/v1/lms/admin/users/sync",
        data: {
            sync_type: 'all',
            sync_batches: true,
        },
        success(response: any) {
            loading.destroy_indicator($("#sync-batches"));
            const stats = response.stats;
            const message = `Batch sync completed: ${stats.batches_synced || 0} batches synced`;
            ui_report.success(message, $("#lms-integration-status"));

            // Refresh batch list and dashboard
            load_batch_groups();
            load_dashboard_status();
        },
        error(xhr) {
            loading.destroy_indicator($("#sync-batches"));
            ui_report.error("Batch sync failed", xhr, $("#lms-integration-status"));
        },
    });
}

function create_batch_group(): void {
    // Create modal dialog for batch group creation
    const modal_html = `
        <div id="create-batch-modal" class="modal fade" tabindex="-1" role="dialog">
            <div class="modal-dialog" role="document">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Create Batch Group</h5>
                        <button type="button" class="close" data-dismiss="modal">
                            <span>&times;</span>
                        </button>
                    </div>
                    <div class="modal-body">
                        <form id="create-batch-form">
                            <div class="form-group">
                                <label for="batch-name">Batch Name</label>
                                <input type="text" class="form-control" id="batch-name" required>
                            </div>
                            <div class="form-group">
                                <label for="batch-description">Description</label>
                                <textarea class="form-control" id="batch-description" rows="3"></textarea>
                            </div>
                            <div class="form-group">
                                <label for="batch-students">Student IDs (comma-separated)</label>
                                <textarea class="form-control" id="batch-students" rows="4"
                                    placeholder="Enter student IDs separated by commas"></textarea>
                            </div>
                            <div class="form-group">
                                <label for="batch-mentors">Mentor IDs (comma-separated)</label>
                                <textarea class="form-control" id="batch-mentors" rows="2"
                                    placeholder="Enter mentor IDs separated by commas"></textarea>
                            </div>
                        </form>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-dismiss="modal">Cancel</button>
                        <button type="button" class="btn btn-primary" id="save-batch-group">Create Batch</button>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if present
    $("#create-batch-modal").remove();

    // Add modal to DOM and show it
    $("body").append(modal_html);
    $("#create-batch-modal").modal("show");

    // Handle form submission
    $("#save-batch-group").on("click", function () {
        const batch_name = $("#batch-name").val() as string;
        const description = $("#batch-description").val() as string;
        const student_ids = $("#batch-students").val() as string;
        const mentor_ids = $("#batch-mentors").val() as string;

        if (!batch_name.trim()) {
            ui_report.error("Batch name is required", undefined, $("#lms-integration-status"));
            return;
        }

        const data = {
            batch_name: batch_name.trim(),
            description: description.trim(),
            student_ids: student_ids.split(",").map(id => id.trim()).filter(id => id),
            mentor_ids: mentor_ids.split(",").map(id => id.trim()).filter(id => id),
        };

        channel.post({
            url: "/api/v1/lms/admin/batches/create",
            data,
            success(response: any) {
                $("#create-batch-modal").modal("hide");
                ui_report.success(`Batch "${batch_name}" created successfully`, $("#lms-integration-status"));

                // Refresh batch list
                load_batch_groups();
            },
            error(xhr) {
                ui_report.error("Failed to create batch group", xhr, $("#lms-integration-status"));
            },
        });
    });
}

// ===================================
// LOGS AND DEBUGGING
// ===================================

function load_logs(page: number = 1): void {
    const level = $("#log-level-filter").val() as string;
    const source = $("#log-source-filter").val() as string;

    const data: any = {page};
    if (level) {
        data.level = level;
    }
    if (source) {
        data.source = source;
    }

    channel.get({
        url: "/api/v1/lms/admin/logs",
        data,
        success(response: any) {
            render_logs_table(response.logs);
            update_error_counts(response.error_counts);
            update_pagination("#lms-logs-table", response);
        },
        error(xhr) {
            ui_report.error("Failed to load logs", xhr, $("#lms-integration-status"));
        },
    });
}

function render_logs_table(logs: any[]): void {
    const $tbody = $("#lms-logs-table");
    $tbody.empty();

    for (const log of logs) {
        const level_class = log.level.toLowerCase();
        const $row = $(`
            <tr>
                <td>${format_datetime(log.timestamp)}</td>
                <td><span class="log-level ${level_class}">${log.level}</span></td>
                <td>${log.source}</td>
                <td>${log.message}</td>
                <td class="actions">
                    ${log.details ? '<button class="btn btn-sm btn-outline" onclick="view_log_details(' + log.id + ')"><i class="fa fa-eye"></i></button>' : ''}
                </td>
            </tr>
        `);
        $tbody.append($row);
    }
}

function update_error_counts(error_counts: any): void {
    $("#sync-errors-count").text(error_counts.sync_errors || 0);
    $("#webhook-errors-count").text(error_counts.webhook_errors || 0);
    $("#auth-errors-count").text(error_counts.auth_errors || 0);
}

function download_logs(): void {
    const level = $("#log-level-filter").val() as string;
    const source = $("#log-source-filter").val() as string;

    // Build query parameters for filtering
    const params = new URLSearchParams();
    params.append("format", "csv");
    if (level) {
        params.append("level", level);
    }
    if (source) {
        params.append("source", source);
    }

    const download_url = `/api/v1/lms/admin/logs/download?${params.toString()}`;

    // Create a temporary link element to trigger download
    const link = document.createElement("a");
    link.href = download_url;
    link.download = `lms_logs_${new Date().toISOString().split("T")[0]}.csv`;
    link.style.display = "none";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    ui_report.success("Log download started", $("#lms-integration-status"));
}

// ===================================
// UTILITY FUNCTIONS
// ===================================

function format_datetime(datetime_string: string): string {
    const date = new Date(datetime_string);
    return date.toLocaleString();
}

function update_pagination(table_selector: string, response: any): void {
    const pagination = response.pagination;
    if (!pagination) {
        return;
    }

    // Find the pagination container for this table
    const pagination_container = $(table_selector).closest(".table-container").find(".pagination-container");
    if (pagination_container.length === 0) {
        return;
    }

    // Clear existing pagination
    pagination_container.empty();

    if (pagination.total_pages <= 1) {
        return;
    }

    const current_page = pagination.current_page;
    const total_pages = pagination.total_pages;

    let pagination_html = '<nav aria-label="Table pagination"><ul class="pagination pagination-sm">';

    // Previous button
    if (current_page > 1) {
        pagination_html += `<li class="page-item"><a class="page-link" href="#" data-page="${current_page - 1}">Previous</a></li>`;
    } else {
        pagination_html += '<li class="page-item disabled"><span class="page-link">Previous</span></li>';
    }

    // Page numbers
    let start_page = Math.max(1, current_page - 2);
    let end_page = Math.min(total_pages, current_page + 2);

    // Adjust range to always show 5 pages if possible
    if (end_page - start_page < 4) {
        if (start_page === 1) {
            end_page = Math.min(total_pages, start_page + 4);
        } else {
            start_page = Math.max(1, end_page - 4);
        }
    }

    // First page and ellipsis if needed
    if (start_page > 1) {
        pagination_html += '<li class="page-item"><a class="page-link" href="#" data-page="1">1</a></li>';
        if (start_page > 2) {
            pagination_html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
    }

    // Page number links
    for (let i = start_page; i <= end_page; i++) {
        if (i === current_page) {
            pagination_html += `<li class="page-item active"><span class="page-link">${i}</span></li>`;
        } else {
            pagination_html += `<li class="page-item"><a class="page-link" href="#" data-page="${i}">${i}</a></li>`;
        }
    }

    // Last page and ellipsis if needed
    if (end_page < total_pages) {
        if (end_page < total_pages - 1) {
            pagination_html += '<li class="page-item disabled"><span class="page-link">...</span></li>';
        }
        pagination_html += `<li class="page-item"><a class="page-link" href="#" data-page="${total_pages}">${total_pages}</a></li>`;
    }

    // Next button
    if (current_page < total_pages) {
        pagination_html += `<li class="page-item"><a class="page-link" href="#" data-page="${current_page + 1}">Next</a></li>`;
    } else {
        pagination_html += '<li class="page-item disabled"><span class="page-link">Next</span></li>';
    }

    pagination_html += '</ul></nav>';

    // Add result info
    const start_item = (current_page - 1) * pagination.per_page + 1;
    const end_item = Math.min(current_page * pagination.per_page, pagination.total_count);
    const info_html = `<div class="pagination-info">Showing ${start_item}-${end_item} of ${pagination.total_count} results</div>`;

    pagination_container.html(pagination_html + info_html);

    // Handle pagination clicks
    pagination_container.find(".page-link[data-page]").on("click", function (e) {
        e.preventDefault();
        const page = parseInt($(this).data("page"), 10);

        // Determine which table and load function to call based on table selector
        if (table_selector.includes("synced-users")) {
            load_synced_users(page);
        } else if (table_selector.includes("sync-history")) {
            load_sync_history(page);
        } else if (table_selector.includes("activity-events")) {
            load_activity_events(page);
        } else if (table_selector.includes("batch-groups")) {
            load_batch_groups(page);
        } else if (table_selector.includes("lms-logs")) {
            load_logs(page);
        }
    });
}

function debounce<T extends (...args: any[]) => void>(func: T, delay: number): (...args: Parameters<T>) => void {
    let timeoutId: ReturnType<typeof setTimeout>;
    return (...args: Parameters<T>) => {
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => func(...args), delay);
    };
}

// ===================================
// GLOBAL FUNCTIONS (for onclick handlers)
// ===================================

// These functions need to be available globally for onclick handlers in the HTML
(window as any).resync_user = function (user_id: number): void {
    if (confirm("Are you sure you want to resync this user?")) {
        channel.post({
            url: `/api/v1/lms/admin/users/${user_id}/resync`,
            success(response: any) {
                ui_report.success("User resync completed successfully", $("#lms-integration-status"));
                // Refresh the user list to show updated data
                load_synced_users();
                load_dashboard_status();
            },
            error(xhr) {
                ui_report.error("Failed to resync user", xhr, $("#lms-integration-status"));
            },
        });
    }
};

(window as any).view_event_details = function (event_id: number): void {
    // Fetch event details and show modal
    channel.get({
        url: `/api/v1/lms/admin/activities/events/${event_id}`,
        success(response: any) {
            const event = response.event;

            const modal_html = `
                <div id="event-details-modal" class="modal fade" tabindex="-1" role="dialog">
                    <div class="modal-dialog modal-lg" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Activity Event Details</h5>
                                <button type="button" class="close" data-dismiss="modal">
                                    <span>&times;</span>
                                </button>
                            </div>
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6>Event Information</h6>
                                        <table class="table table-sm">
                                            <tr><td><strong>Event ID:</strong></td><td>${event.id}</td></tr>
                                            <tr><td><strong>Type:</strong></td><td>${event.event_type}</td></tr>
                                            <tr><td><strong>Timestamp:</strong></td><td>${format_datetime(event.timestamp)}</td></tr>
                                            <tr><td><strong>Student:</strong></td><td>${event.student_username}</td></tr>
                                            <tr><td><strong>Activity:</strong></td><td>${event.activity_title}</td></tr>
                                        </table>
                                    </div>
                                    <div class="col-md-6">
                                        <h6>Notification Status</h6>
                                        <table class="table table-sm">
                                            <tr><td><strong>Status:</strong></td><td><span class="status-badge ${event.notification_status}">${event.notification_status}</span></td></tr>
                                            <tr><td><strong>Sent At:</strong></td><td>${event.notification_sent_at ? format_datetime(event.notification_sent_at) : "Not sent"}</td></tr>
                                            <tr><td><strong>Retry Count:</strong></td><td>${event.retry_count || 0}</td></tr>
                                            ${event.error_message ? `<tr><td><strong>Error:</strong></td><td class="text-danger">${event.error_message}</td></tr>` : ""}
                                        </table>
                                    </div>
                                </div>
                                ${event.event_data ? `
                                    <h6>Raw Event Data</h6>
                                    <pre class="bg-light p-2" style="max-height: 200px; overflow-y: auto;">${JSON.stringify(event.event_data, null, 2)}</pre>
                                ` : ""}
                            </div>
                            <div class="modal-footer">
                                ${event.notification_status === "failed" || event.notification_status === "error" ?
                                    '<button type="button" class="btn btn-warning" onclick="retry_notification(' + event.id + ')">Retry Notification</button>' : ""
                                }
                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal if present
            $("#event-details-modal").remove();

            // Add modal to DOM and show it
            $("body").append(modal_html);
            $("#event-details-modal").modal("show");
        },
        error(xhr) {
            ui_report.error("Failed to load event details", xhr, $("#lms-integration-status"));
        },
    });
};

(window as any).view_log_details = function (log_id: number): void {
    // Fetch log details and show modal
    channel.get({
        url: `/api/v1/lms/admin/logs/${log_id}`,
        success(response: any) {
            const log = response.log;

            const modal_html = `
                <div id="log-details-modal" class="modal fade" tabindex="-1" role="dialog">
                    <div class="modal-dialog modal-lg" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Log Details</h5>
                                <button type="button" class="close" data-dismiss="modal">
                                    <span>&times;</span>
                                </button>
                            </div>
                            <div class="modal-body">
                                <table class="table table-sm">
                                    <tr><td><strong>Log ID:</strong></td><td>${log.id}</td></tr>
                                    <tr><td><strong>Timestamp:</strong></td><td>${format_datetime(log.timestamp)}</td></tr>
                                    <tr><td><strong>Level:</strong></td><td><span class="log-level ${log.level.toLowerCase()}">${log.level}</span></td></tr>
                                    <tr><td><strong>Source:</strong></td><td>${log.source}</td></tr>
                                    <tr><td><strong>Message:</strong></td><td>${log.message}</td></tr>
                                    ${log.user_id ? `<tr><td><strong>User ID:</strong></td><td>${log.user_id}</td></tr>` : ""}
                                    ${log.request_id ? `<tr><td><strong>Request ID:</strong></td><td>${log.request_id}</td></tr>` : ""}
                                </table>

                                ${log.details ? `
                                    <h6>Additional Details</h6>
                                    <pre class="bg-light p-3" style="max-height: 300px; overflow-y: auto; white-space: pre-wrap;">${typeof log.details === 'string' ? log.details : JSON.stringify(log.details, null, 2)}</pre>
                                ` : ""}

                                ${log.stack_trace ? `
                                    <h6>Stack Trace</h6>
                                    <pre class="bg-danger text-white p-3" style="max-height: 300px; overflow-y: auto; white-space: pre-wrap;">${log.stack_trace}</pre>
                                ` : ""}

                                ${log.context ? `
                                    <h6>Context</h6>
                                    <pre class="bg-light p-3" style="max-height: 200px; overflow-y: auto;">${JSON.stringify(log.context, null, 2)}</pre>
                                ` : ""}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-outline-primary" onclick="copyLogDetails(${log.id})">Copy Log</button>
                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal if present
            $("#log-details-modal").remove();

            // Add modal to DOM and show it
            $("body").append(modal_html);
            $("#log-details-modal").modal("show");
        },
        error(xhr) {
            ui_report.error("Failed to load log details", xhr, $("#lms-integration-status"));
        },
    });
};

(window as any).sync_batch_group = function (batch_id: number): void {
    if (confirm("Are you sure you want to sync this batch group?")) {
        const $button = $(`button[onclick="sync_batch_group(${batch_id})"]`);
        const original_html = $button.html();
        $button.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Syncing...');

        channel.post({
            url: `/api/v1/lms/admin/batches/${batch_id}/sync`,
            success(response: any) {
                $button.prop("disabled", false).html(original_html);
                const stats = response.stats;
                const message = `Batch sync completed: ${stats.users_synced || 0} users synced, ${stats.groups_updated || 0} groups updated`;
                ui_report.success(message, $("#lms-integration-status"));

                // Refresh batch list and dashboard
                load_batch_groups();
                load_dashboard_status();
            },
            error(xhr) {
                $button.prop("disabled", false).html(original_html);
                ui_report.error("Failed to sync batch group", xhr, $("#lms-integration-status"));
            },
        });
    }
};

(window as any).view_batch_details = function (batch_id: number): void {
    // Fetch batch details and show modal
    channel.get({
        url: `/api/v1/lms/admin/batches/${batch_id}`,
        success(response: any) {
            const batch = response.batch;

            const modal_html = `
                <div id="batch-details-modal" class="modal fade" tabindex="-1" role="dialog">
                    <div class="modal-dialog modal-xl" role="document">
                        <div class="modal-content">
                            <div class="modal-header">
                                <h5 class="modal-title">Batch Group Details: ${batch.batch_name}</h5>
                                <button type="button" class="close" data-dismiss="modal">
                                    <span>&times;</span>
                                </button>
                            </div>
                            <div class="modal-body">
                                <div class="row">
                                    <div class="col-md-6">
                                        <h6>Batch Information</h6>
                                        <table class="table table-sm">
                                            <tr><td><strong>Batch ID:</strong></td><td>${batch.id}</td></tr>
                                            <tr><td><strong>Name:</strong></td><td>${batch.batch_name}</td></tr>
                                            <tr><td><strong>Status:</strong></td><td><span class="status-badge ${batch.status}">${batch.status}</span></td></tr>
                                            <tr><td><strong>Created:</strong></td><td>${format_datetime(batch.created_at)}</td></tr>
                                            <tr><td><strong>Last Sync:</strong></td><td>${batch.last_sync ? format_datetime(batch.last_sync) : "Never"}</td></tr>
                                            <tr><td><strong>Zulip Group:</strong></td><td>${batch.zulip_group_exists ? `<i class="fa fa-check text-success"></i> ${batch.zulip_group_name}` : '<i class="fa fa-times text-warning"></i> Not Linked'}</td></tr>
                                        </table>
                                    </div>
                                    <div class="col-md-6">
                                        <h6>Statistics</h6>
                                        <table class="table table-sm">
                                            <tr><td><strong>Total Students:</strong></td><td>${batch.student_count}</td></tr>
                                            <tr><td><strong>Total Mentors:</strong></td><td>${batch.mentor_count}</td></tr>
                                            <tr><td><strong>Active Users:</strong></td><td>${batch.active_users_count || "—"}</td></tr>
                                            <tr><td><strong>Last Activity:</strong></td><td>${batch.last_activity ? format_datetime(batch.last_activity) : "—"}</td></tr>
                                        </table>
                                    </div>
                                </div>

                                <div class="row mt-3">
                                    <div class="col-md-6">
                                        <h6>Students (${batch.students ? batch.students.length : 0})</h6>
                                        <div style="max-height: 200px; overflow-y: auto;">
                                            ${batch.students && batch.students.length > 0 ? `
                                                <table class="table table-sm">
                                                    <thead>
                                                        <tr>
                                                            <th>Name</th>
                                                            <th>Email</th>
                                                            <th>Status</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        ${batch.students.map((student: Student) => `
                                                            <tr>
                                                                <td>${student.name}</td>
                                                                <td>${student.email}</td>
                                                                <td><span class="badge badge-primary">${student.status}</span></td>
                                                            </tr>
                                                        `).join('')}
                                                    </tbody>
                                                </table>
                                            ` : '<p class="text-muted">No students found</p>'}
                                        </div>
                                    </div>
                                    <div class="col-md-6">
                                        <h6>Mentors (${batch.mentors ? batch.mentors.length : 0})</h6>
                                        <div style="max-height: 200px; overflow-y: auto;">
                                            ${batch.mentors && batch.mentors.length > 0 ? `
                                                <table class="table table-sm">
                                                    <thead>
                                                        <tr>
                                                            <th>Name</th>
                                                            <th>Email</th>
                                                            <th>Status</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        ${batch.mentors.map((mentor: Mentor) => `
                                                            <tr>
                                                                <td>${mentor.name}</td>
                                                                <td>${mentor.email}</td>
                                                                <td><span class="badge badge-success">${mentor.status}</span></td>
                                                            </tr>
                                                        `).join('')}
                                                    </tbody>
                                                </table>
                                            ` : '<p class="text-muted">No mentors found</p>'}
                                        </div>
                                    </div>
                                </div>

                                ${batch.description ? `
                                    <div class="row mt-3">
                                        <div class="col-12">
                                            <h6>Description</h6>
                                            <p>${batch.description}</p>
                                        </div>
                                    </div>
                                ` : ""}
                            </div>
                            <div class="modal-footer">
                                <button type="button" class="btn btn-primary" onclick="sync_batch_group(${batch.id}); $('#batch-details-modal').modal('hide');">
                                    <i class="fa fa-sync"></i> Sync Batch
                                </button>
                                <button type="button" class="btn btn-secondary" data-dismiss="modal">Close</button>
                            </div>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal if present
            $("#batch-details-modal").remove();

            // Add modal to DOM and show it
            $("body").append(modal_html);
            $("#batch-details-modal").modal("show");
        },
        error(xhr) {
            ui_report.error("Failed to load batch details", xhr, $("#lms-integration-status"));
        },
    });
};

// Additional helper functions for modal actions
(window as any).retry_notification = function (event_id: number): void {
    if (confirm("Are you sure you want to retry this notification?")) {
        channel.post({
            url: `/api/v1/lms/admin/activities/events/${event_id}/retry`,
            success(response: any) {
                ui_report.success("Notification retry initiated", $("#lms-integration-status"));
                // Close the modal and refresh the events list
                $("#event-details-modal").modal("hide");
                load_activity_events();
            },
            error(xhr) {
                ui_report.error("Failed to retry notification", xhr, $("#lms-integration-status"));
            },
        });
    }
};

(window as any).copyLogDetails = function (log_id: number): void {
    // Get the log details from the modal
    const logContent = $(`#log-details-modal .modal-body`).text();

    if (navigator.clipboard) {
        navigator.clipboard.writeText(logContent).then(function () {
            ui_report.success("Log details copied to clipboard", $("#lms-integration-status"));
        }).catch(function () {
            ui_report.error("Failed to copy log details", undefined, $("#lms-integration-status"));
        });
    } else {
        // Fallback for older browsers
        try {
            const $temp = $("<textarea>");
            $("body").append($temp);
            $temp.val(logContent);
            ($temp[0] as HTMLTextAreaElement).select();
            const successful = document.execCommand("copy");
            $temp.remove();
            if (successful) {
                ui_report.success("Log details copied to clipboard", $("#lms-integration-status"));
            } else {
                ui_report.error("Failed to copy log details", undefined, $("#lms-integration-status"));
            }
        } catch (err) {
            ui_report.error("Failed to copy log details", undefined, $("#lms-integration-status"));
        }
    }
};

// Export main initialization function
export {initialize as lms_integration_admin_init};