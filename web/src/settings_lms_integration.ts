/**
 * LMS Integration Admin Interface
 * TypeScript module for managing LMS integration settings and operations.
 */

import $ from "jquery";
import * as channel from "./channel.ts";
import * as ui_report from "./ui_report.ts";
import * as loading from "./loading.ts";
import * as modals from "./modals.ts";

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
let initialized = false;
let progress_poll_interval: number | null = null;
let current_sync_id: string | null = null;

// ===================================
// INITIALIZATION AND TAB MANAGEMENT
// ===================================

export function initialize(): void {
    if (initialized) {
        return;
    }
    initialized = true;

    // Reset sync state on page load to handle browser refresh during sync
    sync_in_progress = false;
    stop_progress_polling();

    // Check for any active syncs and resume polling if needed
    check_for_active_sync();
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
    $("#stop-user-sync").on("click", stop_user_sync);
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

    // Initialize placeholder email management
    $("#refresh-placeholder-stats").on("click", load_placeholder_email_stats);
    $("#bulk-update-placeholder-emails").on("click", bulk_update_placeholder_emails);
    $("#export-placeholder-users").on("click", export_placeholder_users);

    // Initialize log controls
    $("#refresh-logs").on("click", () => load_logs());
    $("#download-logs").on("click", () => download_logs());

    // Initialize filtering
    $("#user-type-filter, #user-search").on("change keyup", () => debounce(load_synced_users, 300)());
    $("#activity-type-filter, #activity-search").on("change keyup", () => debounce(load_activity_events, 300)());
    $("#log-level-filter, #log-source-filter").on("change", () => load_logs());

    // Copy webhook URL functionality
    $("#copy-webhook-url").on("click", copy_webhook_url);

    // Load initial data only if dashboard tab is visible
    // Otherwise, data will be loaded when user navigates to the section
    if ($("#lms-dashboard").hasClass("active") || $("#lms-dashboard").is(":visible")) {
        load_dashboard_status();
        load_current_configuration();
    }

    // Cleanup progress polling when user navigates away
    $(window).on("beforeunload", () => {
        stop_progress_polling();
    });
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
            load_placeholder_users();
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
        url: "/json/lms/admin/dashboard/status",
        success(response: any) {
            dashboard_data = response;
            update_dashboard_ui(response);
            // Reflect actual DB status from the backend instead of assuming success
            const status = response.db_status || "disconnected";
            const statusText = status === "connected" ? "Connected" : "Disconnected";
            update_status_badge(status, statusText);
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
    // Destroy any loading indicator first
    loading.destroy_indicator($badge);
    // Restore badge structure - ensure it's empty and reset styles that loading indicator might have set
    $badge.empty();
    $badge.css({width: "", height: "", "white-space": ""});
    // Restore badge classes and text
    $badge.removeClass("connected disconnected warning").addClass(`lms-status-badge ${status}`);
    $badge.text(text);
}

// ===================================
// USER SYNC FUNCTIONALITY
// ===================================

function start_user_sync(): void {
    // Enhanced double-click protection - check button state first
    const $sync_button = $("#start-user-sync");
    if ($sync_button.prop("disabled")) {
        return; // Button was already clicked recently
    }

    if (sync_in_progress) {
        ui_report.error("Sync already in progress", undefined, $("#lms-integration-status"));
        return;
    }

    // Disable button IMMEDIATELY before any other operations
    $sync_button.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Initializing...');

    const sync_type = $('input[name="sync_type"]:checked').val() as string;
    const sync_batches = $("#sync_batches").is(":checked");

    sync_in_progress = true;
    $("#stop-user-sync").css("display", "inline-block").show();
    $("#sync-progress").show();

    update_sync_progress(0, "Starting sync...");

    channel.post({
        url: "/json/lms/admin/users/sync",
        data: {
            sync_type,
            sync_batches,
        },
        success(response: any) {
            // Update button text to indicate sync is now actively running
            $sync_button.html('<i class="fa fa-spinner fa-spin"></i> Syncing...');

            if (response.status === 'queued' && response.sync_id) {
                // New queued sync - start polling for progress
                current_sync_id = response.sync_id;
                update_sync_progress(0, "Sync queued for background processing...", "initializing");
                start_progress_polling();
            } else if (response.sync_id) {
                // Legacy immediate response with sync_id
                current_sync_id = response.sync_id;
                start_progress_polling();
            } else {
                // Fallback to old immediate completion behavior
                handle_sync_completion(response);
            }
        },
        error(xhr) {
            let error_message = "Failed to start sync";
            let recovery_suggestion = "";

            // Parse different types of errors and provide helpful messages
            try {
                const response = JSON.parse(xhr.responseText);
                if (response.msg) {
                    if (response.msg.includes("already in progress")) {
                        error_message = "Another sync is already running";
                        recovery_suggestion = "Please wait for it to complete or refresh the page to check status.";
                    } else if (response.msg.includes("not enabled")) {
                        error_message = "LMS integration is not enabled";
                        recovery_suggestion = "Please check the configuration settings.";
                    } else if (response.msg.includes("database")) {
                        error_message = "Database connection failed";
                        recovery_suggestion = "Please check the LMS database configuration.";
                    } else {
                        error_message = response.msg;
                    }
                }
            } catch (e) {
                // Fallback to status-based messages
                if (xhr.status === 403) {
                    error_message = "Permission denied";
                    recovery_suggestion = "You need administrator privileges to run sync operations.";
                } else if (xhr.status === 500) {
                    error_message = "Server error occurred";
                    recovery_suggestion = "Please try again later or check the logs.";
                } else if (xhr.status === 0) {
                    error_message = "Network connection failed";
                    recovery_suggestion = "Please check your internet connection and try again.";
                }
            }

            // Reset our local state
            sync_in_progress = false;
            $sync_button.prop("disabled", false).html('<i class="fa fa-play"></i> Start Sync');
            reset_progress_display();

            // Show comprehensive error message
            const full_message = recovery_suggestion
                ? `${error_message}. ${recovery_suggestion}`
                : error_message;

            ui_report.error(full_message, undefined, $("#lms-integration-status"));
        },
    });
}

function start_progress_polling(): void {
    if (!current_sync_id) {
        return;
    }

    // Poll every 1 second for progress updates
    progress_poll_interval = window.setInterval(() => {
        poll_sync_progress();
    }, 1000);

    // Also poll immediately
    poll_sync_progress();
}

function poll_sync_progress(): void {
    if (!current_sync_id) {
        stop_progress_polling();
        return;
    }

    // Store the sync ID we're polling for to prevent race conditions
    const sync_id_for_this_poll = current_sync_id;

    channel.get({
        url: "/json/lms/admin/sync/progress",
        data: { sync_id: current_sync_id },
        success(response: any) {
            // Validate that we're still polling for the same sync
            // If current_sync_id changed while this request was in flight, ignore the response
            if (current_sync_id !== sync_id_for_this_poll) {
                return;
            }

            const progress_data = response;

            // Update progress bar with all available information
            update_sync_progress(
                progress_data.progress_percentage,
                progress_data.status_message,
                progress_data.current_stage,
                progress_data
            );

            // Check if sync is complete
            if (!progress_data.is_active) {
                stop_progress_polling();

                if (progress_data.current_stage === 'completed') {
                    // Sync completed successfully
                    const stats = {
                        created: progress_data.created_count,
                        updated: progress_data.updated_count,
                        skipped: progress_data.skipped_count,
                        errors: progress_data.error_count
                    };
                    handle_sync_completion({ stats });
                } else if (progress_data.current_stage === 'failed') {
                    // Sync failed
                    handle_sync_error({ responseText: progress_data.last_error });
                } else if (progress_data.current_stage === 'cancelled') {
                    // Sync was cancelled
                    handle_sync_cancellation();
                }
            }
        },
        error(xhr) {
            // If progress polling fails, try to recover gracefully
            if (xhr.status === 0 || xhr.status >= 500) {
                // Network or server error - might be temporary
                // Give it one more chance before giving up
                const retry_delay = 5000; // 5 seconds
                setTimeout(() => {
                    if (current_sync_id) {
                        // Only retry if we're still supposed to be polling
                        poll_sync_progress();
                    }
                }, retry_delay);
            } else {
                // Client error (400s) or sync not found - stop polling
                stop_progress_polling();
                if (xhr.status === 404) {
                    // Sync record not found - likely completed and cleaned up
                    ui_report.message(
                        "Sync completed. Refreshing status...",
                        $("#lms-integration-status"),
                        "alert alert-info"
                    );
                    handle_sync_completion({ stats: { created: 0, updated: 0, skipped: 0, errors: 0 } });
                    load_dashboard_status();
                } else {
                    handle_sync_error(xhr);
                }
            }
        },
    });
}

function stop_progress_polling(): void {
    // Clear the polling interval first
    if (progress_poll_interval) {
        clearInterval(progress_poll_interval);
        progress_poll_interval = null;
    }

    // Clear sync ID to prevent any in-flight polls from updating UI
    current_sync_id = null;

    // Also clear any pending setTimeout calls that might restart polling
    // This helps with race conditions during rapid sync operations
}

function check_for_active_sync(): void {
    // Check if there's an active sync we should resume polling for
    channel.get({
        url: "/json/lms/admin/sync/active",
        success(response: any) {
            if (response.active_syncs && response.active_syncs.length > 0) {
                const active_sync = response.active_syncs[0]; // Resume the first active sync

                // Validate that the sync is actually recent and not stuck
                const sync_started = new Date(active_sync.started_at);
                const now = new Date();
                const minutes_since_start = (now.getTime() - sync_started.getTime()) / (1000 * 60);

                if (minutes_since_start > 10) {
                    // Sync has been running for over 10 minutes, likely stuck
                    ui_report.message(
                        "Detected a stale sync operation. It has been cleaned up automatically.",
                        $("#lms-integration-status"),
                        "alert alert-warning"
                    );
                    return;
                }

                current_sync_id = active_sync.sync_id;
                sync_in_progress = true;

                // Update UI to show sync in progress
                $("#start-user-sync").prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Syncing...');
                $("#stop-user-sync").css("display", "inline-block").show();
                $("#sync-progress").show();

                // Show current progress if available
                if (active_sync.progress_percentage !== undefined) {
                    update_sync_progress(
                        active_sync.progress_percentage,
                        active_sync.status_message || "Resuming sync...",
                        active_sync.current_stage,
                        active_sync
                    );
                }

                // Start polling for this active sync
                start_progress_polling();

                // Show user-friendly message about resuming
                ui_report.message(
                    "Resumed monitoring an active sync operation.",
                    $("#lms-integration-status"),
                    "alert alert-info"
                );
            }
        },
        error() {
            // Silently ignore errors - this is just a nice-to-have feature
        },
    });
}

function stop_user_sync(): void {
    if (!current_sync_id) {
        return;
    }

    channel.post({
        url: "/json/lms/admin/users/sync/stop",
        data: {
            sync_id: current_sync_id,
        },
        success() {
            ui_report.success("Sync cancellation requested", $("#lms-integration-status"));
            // The progress polling will detect the cancelled status and call handle_sync_cancellation
        },
        error(xhr) {
            ui_report.error("Failed to stop sync", xhr, $("#lms-integration-status"));
        },
    });
}

function handle_sync_cancellation(): void {
    sync_in_progress = false;

    // Stop polling BEFORE any UI updates
    stop_progress_polling();

    $("#start-user-sync").prop("disabled", false).html('<i class="fa fa-play"></i> Start Sync');
    $("#stop-user-sync").hide();
    update_sync_progress(0, "Sync cancelled", "cancelled");
    ui_report.success("Sync has been cancelled", $("#lms-integration-status"));

    // Reset after a short delay
    setTimeout(() => {
        reset_progress_display();
    }, 2000);
}

function handle_sync_completion(response: any): void {
    sync_in_progress = false;

    // Stop polling BEFORE resetting display to avoid race conditions
    stop_progress_polling();

    $("#start-user-sync").prop("disabled", false).html('<i class="fa fa-play"></i> Start Sync');
    $("#stop-user-sync").hide();
    reset_progress_display();

    const stats = response.stats;
    let message: string;
    if (stats.created === 0 && stats.updated === 0 && stats.skipped === 0 && stats.errors === 0) {
        message = "Sync completed: No users found in LMS database to sync";
    } else {
        message = `Sync completed: ${stats.created} created, ${stats.updated} updated, ${stats.skipped} skipped, ${stats.errors} errors`;
    }
    ui_report.success(message, $("#lms-integration-status"));

    // Refresh dashboard and user list
    load_dashboard_status();
    load_synced_users();
    load_sync_history();
}

function handle_sync_error(xhr: any): void {
    sync_in_progress = false;

    // Stop polling BEFORE resetting display to avoid race conditions
    stop_progress_polling();

    $("#start-user-sync").prop("disabled", false).html('<i class="fa fa-play"></i> Start Sync');
    $("#stop-user-sync").hide();
    reset_progress_display();
    ui_report.error("Sync failed", xhr, $("#lms-integration-status"));
}

function reset_progress_display(): void {
    $("#sync-progress").hide();
    $("#sync-progress-stats").hide();
    $("#stop-user-sync").hide();
    $("#sync-progress-fill").css("width", "0%");
    $("#sync-progress-percentage").text("0%");
    $("#sync-progress-stage").text("Initializing");
    $("#sync-progress-text").text("Preparing sync...");
    $("#progress-created, #progress-updated, #progress-skipped, #progress-errors").text("0");
}

function update_sync_progress(percentage: number, text: string, stage?: string, stats?: any): void {
    $("#sync-progress-fill").css("width", `${percentage}%`);
    $("#sync-progress-percentage").text(`${Math.round(percentage)}%`);

    if (stage) {
        // Convert stage from backend format to user-friendly text
        const stage_text = format_sync_stage(stage);
        $("#sync-progress-stage").text(stage_text);
    }

    // Format progress text with detailed information
    let progress_text = text;
    if (stats) {
        const processed = stats.processed_records || 0;
        const total = stats.total_records || 0;
        
        if (total > 0 && processed > 0) {
            // Show "Synced X of Y students..." format
            const stage_lower = (stage || "").toLowerCase();
            let item_type = "items";
            if (stage_lower.includes("student")) {
                item_type = "students";
            } else if (stage_lower.includes("mentor")) {
                item_type = "mentors";
            } else if (stage_lower.includes("batch")) {
                item_type = "batches";
            }
            
            progress_text = `Synced ${processed.toLocaleString()} of ${total.toLocaleString()} ${item_type}...`;
        }
        
        // Show detailed stats
        $("#progress-created").text((stats.created_count || 0).toLocaleString());
        $("#progress-updated").text((stats.updated_count || 0).toLocaleString());
        $("#progress-skipped").text((stats.skipped_count || 0).toLocaleString());
        $("#progress-errors").text((stats.error_count || 0).toLocaleString());

        // Show stats section when we have stats data (always show during sync)
        $("#sync-progress-stats").show();
    }
    
    $("#sync-progress-text").text(progress_text);
}

function format_sync_stage(stage: string): string {
    const stage_map: { [key: string]: string } = {
        'initializing': 'Initializing',
        'counting_records': 'Counting Records',
        'syncing_students': 'Syncing Students',
        'syncing_mentors': 'Syncing Mentors',
        'syncing_batches': 'Syncing Batches',
        'updating_mappings': 'Updating Mappings',
        'finalizing': 'Finalizing',
        'completed': 'Completed',
        'failed': 'Failed',
        'cancelled': 'Cancelled'
    };
    return stage_map[stage] || stage;
}

function load_synced_users(page: number = 1): void {
    // Ensure page is a valid positive integer
    const pageNum = Number.isFinite(page) && Number.isInteger(page) && page > 0 ? Math.floor(page) : 1;
    
    const user_type = $("#user-type-filter").val() as string;
    const search = $("#user-search").val() as string;

    const data: any = {page: pageNum};
    if (user_type) {
        data.user_type = user_type;
    }
    if (search) {
        data.search = search;
    }

    channel.get({
        url: "/json/lms/admin/users/list",
        data,
        success(response: any) {
            render_users_table(response.users);
            // Transform response to match expected pagination structure
            const transformed_response = {
                ...response,
                pagination: {
                    current_page: response.page,
                    total_pages: response.total_pages,
                    total_count: response.total_count,
                    per_page: 50, // Synced users uses 50 per page
                    has_next: response.has_next,
                    has_previous: response.has_previous,
                },
            };
            update_pagination("#synced-users-table", transformed_response);
        },
        error(xhr) {
            ui_report.error("Failed to load users", xhr, $("#lms-integration-status"));
        },
    });
}

function load_sync_history(page: number = 1): void {
    // Ensure page is a valid positive integer
    const pageNum = Number.isFinite(page) && Number.isInteger(page) && page > 0 ? Math.floor(page) : 1;
    
    channel.get({
        url: "/json/lms/admin/sync/history",
        data: {page: pageNum},
        success(response: any) {
            render_sync_history_table(response.history);
            // Transform response to match expected pagination structure
            const transformed_response = {
                ...response,
                pagination: {
                    current_page: response.page,
                    total_pages: response.total_pages,
                    total_count: response.total_count,
                    per_page: 20, // Sync history uses 20 per page
                    has_next: response.has_next,
                    has_previous: response.has_previous,
                },
            };
            update_pagination("#sync-history-table", transformed_response);
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
        // Map status to appropriate CSS class and icon
        let status_class;
        let status_icon;
        let status_text;

        switch (sync.status) {
            case 'success':
                status_class = 'text-success';
                status_icon = 'fa-check-circle';
                status_text = 'Success';
                break;
            case 'partial':
                status_class = 'text-warning';
                status_icon = 'fa-exclamation-triangle';
                status_text = 'Partial';
                break;
            case 'failed':
                status_class = 'text-danger';
                status_icon = 'fa-times-circle';
                status_text = 'Failed';
                break;
            case 'cancelled':
                status_class = 'text-muted';
                status_icon = 'fa-ban';
                status_text = 'Cancelled';
                break;
            case 'running':
                status_class = 'text-info';
                status_icon = 'fa-spinner fa-spin';
                status_text = 'Running';
                break;
            default:
                status_class = 'text-muted';
                status_icon = 'fa-question-circle';
                status_text = sync.status || 'Unknown';
        }

        const duration = Math.round(sync.duration_seconds);

        const $row = $(`
            <tr>
                <td>${format_datetime(sync.started_at)}</td>
                <td><span class="badge badge-secondary">${sync.sync_type}</span></td>
                <td><span class="${status_class}"><i class="fa ${status_icon}"></i> ${status_text}</span></td>
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
        url: "/json/lms/admin/activities/poll",
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
        url: "/json/lms/admin/activities/process-pending",
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
    // Ensure page is a valid positive integer
    const pageNum = Number.isFinite(page) && Number.isInteger(page) && page > 0 ? Math.floor(page) : 1;
    
    const event_type = $("#activity-type-filter").val() as string;
    const search = $("#activity-search").val() as string;

    const data: any = {page: pageNum};
    if (event_type) {
        data.event_type = event_type;
    }
    if (search) {
        data.search = search;
    }

    channel.get({
        url: "/json/lms/admin/activities/events",
        data,
        success(response: any) {
            render_activity_events_table(response.events);
            // Transform response to match expected pagination structure
            const transformed_response = {
                ...response,
                pagination: {
                    current_page: response.page,
                    total_pages: response.total_pages,
                    total_count: response.total_count,
                    per_page: 50, // Activity events uses 50 per page
                    has_next: response.has_next,
                    has_previous: response.has_previous,
                },
            };
            update_pagination("#activity-events-table", transformed_response);
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
        url: "/json/lms/admin/config/get",
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

    // Populate placeholder email settings
    $("#id_lms_no_email_domain").val(config.lms_no_email_domain || "noemail.local");
    $("#id_lms_auto_update_emails").prop("checked", config.lms_auto_update_emails !== false);
    $("#id_lms_placeholder_email_delivery").prop("checked", config.lms_placeholder_email_delivery === true);
    $("#id_lms_placeholder_inapp_notifications").prop("checked", config.lms_placeholder_inapp_notifications !== false);
    $("#id_lms_log_placeholder_attempts").prop("checked", config.lms_log_placeholder_attempts !== false);

    // Update placeholder email statistics
    if (config.placeholder_stats) {
        update_placeholder_stats_ui(config.placeholder_stats);
    }
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

        // Placeholder email settings
        lms_no_email_domain: $("#id_lms_no_email_domain").val(),
        lms_auto_update_emails: $("#id_lms_auto_update_emails").is(":checked"),
        lms_placeholder_email_delivery: $("#id_lms_placeholder_email_delivery").is(":checked"),
        lms_placeholder_inapp_notifications: $("#id_lms_placeholder_inapp_notifications").is(":checked"),
        lms_log_placeholder_attempts: $("#id_lms_log_placeholder_attempts").is(":checked"),
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
        url: "/json/lms/admin/config/update",
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
        url: "/json/lms/admin/config/test-db",
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
        url: "/json/lms/admin/config/test-jwt",
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
    // Ensure page is a valid positive integer
    const pageNum = Number.isFinite(page) && Number.isInteger(page) && page > 0 ? Math.floor(page) : 1;
    
    channel.get({
        url: "/json/lms/admin/batches/list",
        data: {page: pageNum},
        success(response: any) {
            render_batch_groups_table(response.batches);
            // Transform response to match expected pagination structure
            const transformed_response = {
                ...response,
                pagination: {
                    current_page: response.page,
                    total_pages: response.total_pages,
                    total_count: response.total_count,
                    per_page: 50, // Batch groups uses 50 per page
                    has_next: response.has_next,
                    has_previous: response.has_previous,
                },
            };
            update_pagination("#batch-groups-table", transformed_response);
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
    // Double-click protection - check if sync is already in progress or button is disabled
    if (sync_in_progress) {
        ui_report.error("User sync already in progress", undefined, $("#lms-integration-status"));
        return;
    }

    const $batch_sync_button = $("#sync-batches");
    if ($batch_sync_button.prop("disabled")) {
        return; // Button was already clicked recently
    }

    loading.make_indicator($batch_sync_button);

    // Use the same user sync endpoint with batch sync enabled
    channel.post({
        url: "/json/lms/admin/users/sync",
        data: {
            sync_type: 'all',
            sync_batches: true,
        },
        success(response: any) {
            loading.destroy_indicator($("#sync-batches"));
            const stats = response.stats;

            if (stats) {
                // Legacy immediate-completion behavior where the endpoint returns stats
                const message = `Batch sync completed: ${stats.batches_synced || 0} batches synced`;
                ui_report.success(message, $("#lms-integration-status"));
            } else if (response.status === "queued" && response.sync_id) {
                // New asynchronous behavior where the sync is queued for background processing
                ui_report.success(
                    "Batch sync has been queued for background processing. You can monitor progress in the sync status section.",
                    $("#lms-integration-status"),
                );
            } else {
                // Fallback: request succeeded but no stats were returned
                ui_report.success(
                    "Batch sync request completed.",
                    $("#lms-integration-status"),
                );
            }

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
        <div class="micromodal" id="create-batch-modal" aria-hidden="true">
            <div class="modal__overlay" tabindex="-1">
                <div class="modal__container" role="dialog" aria-modal="true">
                    <div class="modal__header">
                        <h1 class="modal__title">Create Batch Group</h1>
                        <button class="modal__close" aria-label="Close modal" data-micromodal-close></button>
                    </div>
                    <main class="modal__body">
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
                    </main>
                    <footer class="modal__footer">
                        <button type="button" class="modal__button dialog_exit_button" data-micromodal-close>Cancel</button>
                        <button type="button" class="modal__button dialog_submit_button" id="save-batch-group">Create Batch</button>
                    </footer>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if present
    $("#create-batch-modal").remove();

    // Add modal to DOM and show it
    $("body").append(modal_html);
    modals.open("create-batch-modal", {autoremove: true});

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
            url: "/json/lms/admin/batches/create",
            data,
            success(response: any) {
                modals.close("create-batch-modal");
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
    // Ensure page is a valid positive integer
    const pageNum = Number.isFinite(page) && Number.isInteger(page) && page > 0 ? Math.floor(page) : 1;
    
    const level = $("#log-level-filter").val() as string;
    const source = $("#log-source-filter").val() as string;

    const data: any = {page: pageNum};
    if (level) {
        data.level = level;
    }
    if (source) {
        data.source = source;
    }

    channel.get({
        url: "/json/lms/admin/logs",
        data,
        success(response: any) {
            render_logs_table(response.logs);
            update_error_counts(response.error_counts);
            // Transform response to match expected pagination structure
            const transformed_response = {
                ...response,
                pagination: {
                    current_page: response.page,
                    total_pages: response.total_pages,
                    total_count: response.total_count,
                    per_page: 100, // Logs uses 100 per page
                    has_next: response.has_next,
                    has_previous: response.has_previous,
                },
            };
            update_pagination("#lms-logs-table", transformed_response);
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

    const download_url = `/json/lms/admin/logs/download?${params.toString()}`;

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
// PLACEHOLDER EMAIL MANAGEMENT
// ===================================

function load_placeholder_users(page: number = 1): void {
    // Ensure page is a valid positive integer
    const pageNum = Number.isFinite(page) && Number.isInteger(page) && page > 0 ? Math.floor(page) : 1;

    channel.get({
        url: "/json/lms/admin/users/placeholder",
        data: {page: pageNum},
        success(response: any) {
            render_placeholder_users_table(response.users);
            // Update placeholder stats summary
            $("#placeholder-users-count").text(response.total_count || 0);
            $("#placeholder-email-coverage-sync").text(response.email_coverage ? `${response.email_coverage}%` : "—");

            // Transform response to match expected pagination structure
            const transformed_response = {
                ...response,
                pagination: {
                    current_page: response.page,
                    total_pages: response.total_pages,
                    total_count: response.total_count,
                    per_page: 50, // Placeholder users uses 50 per page
                    has_next: response.has_next,
                    has_previous: response.has_previous,
                },
            };
            update_pagination("#placeholder-users-table", transformed_response);
        },
        error(xhr) {
            ui_report.error("Failed to load placeholder users", xhr, $("#lms-integration-status"));
        },
    });
}

function render_placeholder_users_table(users: any[]): void {
    const $tbody = $("#placeholder-users-table");
    $tbody.empty();

    for (const user of users) {
        const type_badge = user.type === 'student' ? 'badge-primary' : 'badge-success';
        const $row = $(`
            <tr>
                <td>${user.name}</td>
                <td>${user.username || "—"}</td>
                <td>${user.placeholder_email}</td>
                <td><span class="badge ${type_badge}">${user.type}</span></td>
                <td>${user.lms_id || "—"}</td>
                <td>${user.last_sync ? format_datetime(user.last_sync) : "—"}</td>
                <td class="actions">
                    <button class="btn btn-sm btn-outline" onclick="update_user_email(${user.id}, '${user.username}')">
                        <i class="fa fa-edit"></i> Update Email
                    </button>
                </td>
            </tr>
        `);
        $tbody.append($row);
    }
}

function load_placeholder_email_stats(): void {
    loading.make_indicator($("#refresh-placeholder-stats"));

    channel.get({
        url: "/json/lms/admin/users/placeholder/stats",
        success(response: any) {
            loading.destroy_indicator($("#refresh-placeholder-stats"));
            update_placeholder_stats_ui(response);
        },
        error(xhr) {
            loading.destroy_indicator($("#refresh-placeholder-stats"));
            ui_report.error("Failed to load placeholder email statistics", xhr, $("#lms-integration-status"));
        },
    });
}

function update_placeholder_stats_ui(stats: any): void {
    $("#placeholder-total-users").text(stats.total_users || "0");
    $("#placeholder-real-emails").text(stats.users_with_email_notifications || "0");
    $("#placeholder-fake-emails").text(stats.users_without_email_notifications || "0");
    $("#placeholder-email-coverage").text(stats.email_notification_coverage ? `${stats.email_notification_coverage}%` : "0%");
}

function bulk_update_placeholder_emails(): void {
    // Create modal dialog for bulk email update
    const modal_html = `
        <div class="micromodal" id="bulk-update-emails-modal" aria-hidden="true">
            <div class="modal__overlay" tabindex="-1">
                <div class="modal__container" role="dialog" aria-modal="true">
                    <div class="modal__header">
                        <h1 class="modal__title">Bulk Update Placeholder Emails</h1>
                        <button class="modal__close" aria-label="Close modal" data-micromodal-close></button>
                    </div>
                    <main class="modal__body">
                        <form id="bulk-update-form">
                            <div class="form-group">
                                <label for="bulk-email-updates">Email Updates (CSV format: username,email)</label>
                                <textarea class="form-control" id="bulk-email-updates" rows="10"
                                    placeholder="john_doe,john.doe@school.edu
mary_smith,mary.smith@school.edu
jane_wilson,jane.wilson@school.edu"></textarea>
                                <small class="form-text text-muted">
                                    Enter one update per line in the format: username,email
                                </small>
                            </div>
                            <div class="form-group">
                                <div class="form-check">
                                    <input type="checkbox" class="form-check-input" id="validate-only">
                                    <label class="form-check-label" for="validate-only">
                                        Validate only (don't apply changes)
                                    </label>
                                </div>
                            </div>
                        </form>
                    </main>
                    <footer class="modal__footer">
                        <button type="button" class="modal__button dialog_exit_button" data-micromodal-close>Cancel</button>
                        <button type="button" class="modal__button dialog_submit_button" id="process-bulk-updates">Process Updates</button>
                    </footer>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if present
    $("#bulk-update-emails-modal").remove();

    // Add modal to DOM and show it
    $("body").append(modal_html);
    modals.open("bulk-update-emails-modal", {autoremove: true});

    // Handle form submission
    $("#process-bulk-updates").on("click", function () {
        const updates = $("#bulk-email-updates").val() as string;
        const validate_only = $("#validate-only").is(":checked");

        if (!updates.trim()) {
            ui_report.error("Email updates are required", undefined, $("#lms-integration-status"));
            return;
        }

        // Parse CSV data
        const lines = updates.trim().split('\n');
        const email_updates = [];
        for (const line of lines) {
            const [username, email] = line.split(',').map(s => s.trim());
            if (username && email) {
                email_updates.push({ username, email });
            }
        }

        if (email_updates.length === 0) {
            ui_report.error("No valid email updates found", undefined, $("#lms-integration-status"));
            return;
        }

        const data = {
            email_updates,
            validate_only,
        };

        loading.make_indicator($("#process-bulk-updates"));

        channel.post({
            url: "/json/lms/admin/users/placeholder/bulk-update",
            data,
            success(response: any) {
                loading.destroy_indicator($("#process-bulk-updates"));
                modals.close("bulk-update-emails-modal");

                const stats = response.stats;
                const message = validate_only
                    ? `Validation complete: ${stats.valid} valid, ${stats.invalid} invalid, ${stats.not_found} not found`
                    : `Bulk update complete: ${stats.updated} updated, ${stats.errors} errors`;

                ui_report.success(message, $("#lms-integration-status"));

                // Refresh placeholder users list and stats
                load_placeholder_users();
                load_placeholder_email_stats();
            },
            error(xhr) {
                loading.destroy_indicator($("#process-bulk-updates"));
                ui_report.error("Failed to process bulk email updates", xhr, $("#lms-integration-status"));
            },
        });
    });
}

function export_placeholder_users(): void {
    const download_url = "/json/lms/admin/users/placeholder/export";

    // Create a temporary link element to trigger download
    const link = document.createElement("a");
    link.href = download_url;
    link.download = `placeholder_users_${new Date().toISOString().split("T")[0]}.csv`;
    link.style.display = "none";

    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);

    ui_report.success("Placeholder users export started", $("#lms-integration-status"));
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
        const pageValue = $(this).data("page");
        // jQuery's data() can return various types, ensure we parse it correctly
        const page = typeof pageValue === "number" 
            ? pageValue 
            : parseInt(String(pageValue || "1"), 10);
        
        // Validate page is a valid positive integer
        if (!Number.isFinite(page) || !Number.isInteger(page) || page < 1) {
            return;
        }

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
        const $button = $(`button[onclick="resync_user(${user_id})"]`);

        // Double-click protection
        if ($button.prop("disabled")) {
            return; // Button was already clicked
        }

        const original_html = $button.html();
        $button.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i>');

        channel.post({
            url: `/json/lms/admin/users/${user_id}/resync`,
            success(response: any) {
                $button.prop("disabled", false).html(original_html);
                ui_report.success("User resync completed successfully", $("#lms-integration-status"));
                // Refresh the user list to show updated data
                load_synced_users();
                load_dashboard_status();
            },
            error(xhr) {
                $button.prop("disabled", false).html(original_html);
                ui_report.error("Failed to resync user", xhr, $("#lms-integration-status"));
            },
        });
    }
};

(window as any).view_event_details = function (event_id: number): void {
    // Fetch event details and show modal
    channel.get({
        url: `/json/lms/admin/activities/events/${event_id}`,
        success(response: any) {
            const event = response.event;

            const modal_html = `
                <div class="micromodal" id="event-details-modal" aria-hidden="true">
                    <div class="modal__overlay" tabindex="-1">
                        <div class="modal__container" role="dialog" aria-modal="true">
                            <div class="modal__header">
                                <h1 class="modal__title">Activity Event Details</h1>
                                <button class="modal__close" aria-label="Close modal" data-micromodal-close></button>
                            </div>
                            <main class="modal__body">
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
                            </main>
                            <footer class="modal__footer">
                                ${event.notification_status === "failed" || event.notification_status === "error" ?
                                    '<button type="button" class="modal__button" onclick="retry_notification(' + event.id + '); modals.close(\'event-details-modal\');">Retry Notification</button>' : ""
                                }
                                <button type="button" class="modal__button dialog_exit_button" data-micromodal-close>Close</button>
                            </footer>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal if present
            $("#event-details-modal").remove();

            // Add modal to DOM and show it
            $("body").append(modal_html);
            modals.open("event-details-modal", {autoremove: true});
        },
        error(xhr) {
            ui_report.error("Failed to load event details", xhr, $("#lms-integration-status"));
        },
    });
};

(window as any).view_log_details = function (log_id: number): void {
    // Fetch log details and show modal
    channel.get({
            url: `/json/lms/admin/logs/${log_id}`,
        success(response: any) {
            const log = response.log;

            const modal_html = `
                <div class="micromodal" id="log-details-modal" aria-hidden="true">
                    <div class="modal__overlay" tabindex="-1">
                        <div class="modal__container" role="dialog" aria-modal="true">
                            <div class="modal__header">
                                <h1 class="modal__title">Log Details</h1>
                                <button class="modal__close" aria-label="Close modal" data-micromodal-close></button>
                            </div>
                            <main class="modal__body">
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
                            </main>
                            <footer class="modal__footer">
                                <button type="button" class="modal__button" onclick="copyLogDetails(${log.id})">Copy Log</button>
                                <button type="button" class="modal__button dialog_exit_button" data-micromodal-close>Close</button>
                            </footer>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal if present
            $("#log-details-modal").remove();

            // Add modal to DOM and show it
            $("body").append(modal_html);
            modals.open("log-details-modal", {autoremove: true});
        },
        error(xhr) {
            ui_report.error("Failed to load log details", xhr, $("#lms-integration-status"));
        },
    });
};

(window as any).sync_batch_group = function (batch_id: number): void {
    if (confirm("Are you sure you want to sync this batch group?")) {
        const $button = $(`button[onclick="sync_batch_group(${batch_id})"]`);

        // Double-click protection
        if ($button.prop("disabled")) {
            return; // Button was already clicked
        }

        const original_html = $button.html();
        $button.prop("disabled", true).html('<i class="fa fa-spinner fa-spin"></i> Syncing...');

        channel.post({
            url: `/json/lms/admin/batches/${batch_id}/sync`,
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
        url: `/json/lms/admin/batches/${batch_id}`,
        success(response: any) {
            const batch = response.batch;

            const modal_html = `
                <div class="micromodal" id="batch-details-modal" aria-hidden="true">
                    <div class="modal__overlay" tabindex="-1">
                        <div class="modal__container" role="dialog" aria-modal="true">
                            <div class="modal__header">
                                <h1 class="modal__title">Batch Group Details: ${batch.batch_name}</h1>
                                <button class="modal__close" aria-label="Close modal" data-micromodal-close></button>
                            </div>
                            <main class="modal__body">
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
                            </main>
                            <footer class="modal__footer">
                                <button type="button" class="modal__button dialog_submit_button" onclick="sync_batch_group(${batch.id}); modals.close('batch-details-modal');">
                                    <i class="fa fa-sync"></i> Sync Batch
                                </button>
                                <button type="button" class="modal__button dialog_exit_button" data-micromodal-close>Close</button>
                            </footer>
                        </div>
                    </div>
                </div>
            `;

            // Remove existing modal if present
            $("#batch-details-modal").remove();

            // Add modal to DOM and show it
            $("body").append(modal_html);
            modals.open("batch-details-modal", {autoremove: true});
        },
        error(xhr) {
            ui_report.error("Failed to load batch details", xhr, $("#lms-integration-status"));
        },
    });
};

// Additional helper functions for modal actions
(window as any).update_user_email = function (user_id: number, username: string): void {
    // Create modal dialog for single user email update
    const modal_html = `
        <div class="micromodal" id="update-user-email-modal" aria-hidden="true">
            <div class="modal__overlay" tabindex="-1">
                <div class="modal__container" role="dialog" aria-modal="true">
                    <div class="modal__header">
                        <h1 class="modal__title">Update Email for ${username}</h1>
                        <button class="modal__close" aria-label="Close modal" data-micromodal-close></button>
                    </div>
                    <main class="modal__body">
                        <form id="update-email-form">
                            <div class="form-group">
                                <label for="new-email">New Email Address</label>
                                <input type="email" class="form-control" id="new-email" required
                                    placeholder="Enter the new email address">
                            </div>
                        </form>
                    </main>
                    <footer class="modal__footer">
                        <button type="button" class="modal__button dialog_exit_button" data-micromodal-close>Cancel</button>
                        <button type="button" class="modal__button dialog_submit_button" id="save-email-update">Update Email</button>
                    </footer>
                </div>
            </div>
        </div>
    `;

    // Remove existing modal if present
    $("#update-user-email-modal").remove();

    // Add modal to DOM and show it
    $("body").append(modal_html);
    modals.open("update-user-email-modal", {autoremove: true});

    // Handle form submission
    $("#save-email-update").on("click", function () {
        const new_email = $("#new-email").val() as string;

        if (!new_email || !new_email.trim()) {
            ui_report.error("Email address is required", undefined, $("#lms-integration-status"));
            return;
        }

        const data = {
            user_id,
            new_email: new_email.trim(),
        };

        loading.make_indicator($("#save-email-update"));

        channel.post({
            url: "/json/lms/admin/users/update-email",
            data,
            success(response: any) {
                loading.destroy_indicator($("#save-email-update"));
                modals.close("update-user-email-modal");
                ui_report.success(`Email updated successfully for ${username}`, $("#lms-integration-status"));

                // Refresh placeholder users list
                load_placeholder_users();
                load_placeholder_email_stats();
            },
            error(xhr) {
                loading.destroy_indicator($("#save-email-update"));
                ui_report.error("Failed to update email address", xhr, $("#lms-integration-status"));
            },
        });
    });
};

(window as any).retry_notification = function (event_id: number): void {
    if (confirm("Are you sure you want to retry this notification?")) {
        channel.post({
            url: `/json/lms/admin/activities/events/${event_id}/retry`,
            success(response: any) {
                ui_report.success("Notification retry initiated", $("#lms-integration-status"));
                // Close the modal and refresh the events list
                modals.close("event-details-modal");
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
    const logContent = $(`#log-details-modal .modal__body`).text();

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

export function set_up(): void {
    // Only initialize if not already done and if the LMS integration section exists
    if (!initialized && $("#lms-integration-settings").length > 0) {
        initialize();
    }
}

export function reset(): void {
    // Reset initialization and any in-flight sync/progress polling so that
    // reopening the LMS Integration settings starts from a clean state.
    initialized = false;
    sync_in_progress = false;
    stop_progress_polling();
}