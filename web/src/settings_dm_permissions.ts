/**
 * Role-based DM Permission Matrix Settings
 * 
 * Handles the admin UI for configuring which roles can see and direct message other roles.
 */

import $ from "jquery";
import {csrf_token} from "./csrf.ts";
import {$t} from "./i18n.ts";
import * as loading from "./loading.ts";
import * as ui_report from "./ui_report.ts";

const VALID_ROLES = ['owner', 'admin', 'mentor', 'student', 'parent', 'faculty'];
const ROLE_LABELS: Record<string, string> = {
    owner: $t({defaultMessage: "Owner"}),
    admin: $t({defaultMessage: "Admin"}),
    mentor: $t({defaultMessage: "Mentor"}),
    parent: $t({defaultMessage: "Parent"}),
    faculty: $t({defaultMessage: "Faculty"}),
    student: $t({defaultMessage: "Student"}),
};

const DEFAULT_MATRIX: Record<string, string[]> = {
    owner: VALID_ROLES,
    admin: VALID_ROLES,
    mentor: ["mentor", "student", "parent"],
    student: ["mentor"],
    parent: ["mentor", "faculty", "student"],
    faculty: ["mentor", "student"],
};

let permission_matrix: Record<string, string[]> = {};
let enabled = false;

export function load_dm_permissions(): void {
    loading.make_indicator($("#dm-permission-matrix-container .loading-indicator"), {
        text: $t({defaultMessage: "Loading..."}),
    });

    void $.get("/json/lms/dm-permissions", {
        csrfmiddlewaretoken: csrf_token,
    })
        .done((data) => {
            enabled = data.enabled || false;
            permission_matrix = data.permission_matrix || {};
            
            // Update UI
            const $enabled_checkbox = $("#id_lms_dm_permissions_enabled");
            if ($enabled_checkbox.length > 0) {
                $enabled_checkbox.prop("checked", enabled);
            }
            toggle_matrix_visibility(enabled);
            
            if (enabled) {
                render_permission_matrix();
            }
            
            // Hide save/discard buttons after loading
            const $subsection = $("#org-role-dm-permissions");
            $subsection.find(".save-button-controls").addClass("hide");
        })
        .fail((xhr) => {
            ui_report.error(
                $t({defaultMessage: "Failed to load DM permissions"}),
                xhr,
                $("#dm-permission-matrix-container .alert"),
            );
        })
        .always(() => {
            loading.destroy_indicator($("#dm-permission-matrix-container .loading-indicator"));
        });
}

function toggle_matrix_visibility(show: boolean): void {
    if (show) {
        $("#dm-permission-matrix").show();
    } else {
        $("#dm-permission-matrix").hide();
    }
}

function render_permission_matrix(): void {
    const $tbody = $("#dm-permission-matrix-body");
    $tbody.empty();
    
    // Create rows for each source role (excluding owner/admin which are always allowed)
    const configurable_roles = VALID_ROLES.filter(role => role !== 'owner' && role !== 'admin');
    
    for (const source_role of configurable_roles) {
        const $row = $("<tr>").addClass("matrix-row");
        const role_label = ROLE_LABELS[source_role] ?? source_role;
        $row.append($("<td>").addClass("matrix-source-role").text(String(role_label)));
        
        // Create cells for each target role
        for (const target_role of VALID_ROLES) {
            const $cell = $("<td>").addClass("matrix-cell");
            
            // Owner and admin are always visible (not configurable)
            if (target_role === 'owner' || target_role === 'admin') {
                $cell.addClass("matrix-cell-always-allowed")
                    .html('<i class="fa fa-check" title="' + 
                          $t({defaultMessage: "Always allowed"}) + '"></i>');
            } else {
                // Check if this permission is allowed
                const allowed_roles = permission_matrix[source_role] || [];
                const is_allowed = allowed_roles.includes(target_role);
                
                const $checkbox = $("<input>")
                    .attr("type", "checkbox")
                    .attr("data-source-role", source_role)
                    .attr("data-target-role", target_role)
                    .prop("checked", is_allowed)
                    .on("change", function () {
                        const checked = $(this).prop("checked") ?? false;
                        handle_permission_change(source_role, target_role, checked);
                    });
                
                $cell.append($checkbox);
            }
            
            $row.append($cell);
        }
        
        $tbody.append($row);
    }
}

function handle_permission_change(source_role: string, target_role: string, allowed: boolean): void {
    if (!permission_matrix[source_role]) {
        permission_matrix[source_role] = [];
    }
    
    if (allowed) {
        if (!permission_matrix[source_role].includes(target_role)) {
            permission_matrix[source_role].push(target_role);
        }
    } else {
        permission_matrix[source_role] = permission_matrix[source_role].filter(
            role => role !== target_role
        );
    }
    
    // Trigger change event to enable save button via settings_save_discard_widget
    $("#org-role-dm-permissions").trigger("input");
}

export function save_dm_permissions(): void {
    // Always get the current checkbox state to ensure we save the latest value
    const $checkbox = $("#id_lms_dm_permissions_enabled");
    if ($checkbox.length > 0) {
        enabled = $checkbox.prop("checked");
    }
    
    const data = {
        enabled,
        permission_matrix,
    };
    
    loading.make_indicator($("#dm-permission-matrix-container .loading-indicator"), {
        text: $t({defaultMessage: "Saving..."}),
    });
    
    void $.ajax({
        type: "PATCH",
        url: "/json/lms/dm-permissions",
        data: JSON.stringify(data),
        contentType: "application/json",
        dataType: "json",
        headers: {
            "X-CSRFToken": csrf_token,
        },
    })
        .done(() => {
            ui_report.success(
                $t({defaultMessage: "DM permissions saved successfully"}),
                $("#dm-permission-matrix-container .alert"),
            );
            // Hide save/discard buttons after successful save
            const $subsection = $("#org-role-dm-permissions");
            $subsection.find(".save-button-controls").addClass("hide");
        })
        .fail((xhr) => {
            ui_report.error(
                $t({defaultMessage: "Failed to save DM permissions"}),
                xhr,
                $("#dm-permission-matrix-container .alert"),
            );
        })
        .always(() => {
            loading.destroy_indicator($("#dm-permission-matrix-container .loading-indicator"));
        });
}

export function reset_dm_permissions(): void {
    load_dm_permissions();
    // Hide save/discard buttons after discard
    const $subsection = $("#org-role-dm-permissions");
    $subsection.find(".save-button-controls").addClass("hide");
}

export function restore_defaults(): void {
    permission_matrix = JSON.parse(JSON.stringify(DEFAULT_MATRIX));
    
    // Ensure enabled is true
    enabled = true;
    $("#id_lms_dm_permissions_enabled").prop("checked", true);
    toggle_matrix_visibility(true);

    render_permission_matrix();
    
    // Show save buttons so user can persist the defaults
    const $subsection = $("#org-role-dm-permissions");
    $subsection.find(".save-button-controls").removeClass("hide");
}

export function initialize(): void {
    // Load initial state
    load_dm_permissions();
    
    // Handle enable/disable toggle
    $("#id_lms_dm_permissions_enabled").on("change", function () {
        enabled = $(this).prop("checked");
        toggle_matrix_visibility(enabled);
        if (enabled) {
            render_permission_matrix();
        }
        // Show save/discard buttons
        const $subsection = $("#org-role-dm-permissions");
        $subsection.find(".save-button-controls").removeClass("hide");
    });
    
    // Set up save/discard handlers - intercept and call our custom save function
    $("#org-role-dm-permissions").on("click", ".save-button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        save_dm_permissions();
        return false;
    });
    
    $("#org-role-dm-permissions").on("click", ".discard-button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        reset_dm_permissions();
        return false;
    });

    $("#org-role-dm-permissions").on("click", ".restore-defaults-button", (e) => {
        e.preventDefault();
        e.stopPropagation();
        restore_defaults();
        return false;
    });
    
    // Mark checkbox changes in the permission matrix to show save/discard buttons
    $("#org-role-dm-permissions").on(
        "change",
        "#dm-permission-matrix input[type='checkbox']",
        function () {
            // Show save/discard buttons
            const $subsection = $("#org-role-dm-permissions");
            $subsection.find(".save-button-controls").removeClass("hide");
        },
    );
}

