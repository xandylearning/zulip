import $ from "jquery";
import _ from "lodash";

import {unresolve_name} from "../shared/src/resolved_topic.ts";
import render_add_poll_modal from "../templates/add_poll_modal.hbs";
import render_add_todo_list_modal from "../templates/add_todo_list_modal.hbs";
import render_compose_banner from "../templates/compose_banner/compose_banner.hbs";

import * as compose from "./compose.js";
import * as compose_actions from "./compose_actions.ts";
import * as compose_banner from "./compose_banner.ts";
import * as compose_call from "./compose_call.ts";
import * as compose_call_ui from "./compose_call_ui.ts";
import * as compose_fade from "./compose_fade.ts";
import * as compose_notifications from "./compose_notifications.ts";
import * as compose_recipient from "./compose_recipient.ts";
import * as compose_send_menu_popover from "./compose_send_menu_popover.js";
import * as compose_state from "./compose_state.ts";
import * as compose_ui from "./compose_ui.ts";
import * as compose_validate from "./compose_validate.ts";
import * as dialog_widget from "./dialog_widget.ts";
import * as drafts from "./drafts.ts";
import * as flatpickr from "./flatpickr.ts";
import {$t_html} from "./i18n.ts";
import * as message_edit from "./message_edit.ts";
import * as message_view from "./message_view.ts";
import * as narrow_state from "./narrow_state.ts";
import * as onboarding_steps from "./onboarding_steps.ts";
import {page_params} from "./page_params.ts";
import * as people from "./people.ts";
import * as popovers from "./popovers.ts";
import * as resize from "./resize.ts";
import * as rows from "./rows.ts";
import * as scheduled_messages from "./scheduled_messages.ts";
import * as stream_data from "./stream_data.ts";
import * as stream_settings_components from "./stream_settings_components.ts";
import * as sub_store from "./sub_store.ts";
import * as subscriber_api from "./subscriber_api.ts";
import {get_timestamp_for_flatpickr} from "./timerender.ts";
import * as ui_report from "./ui_report.ts";
import * as upload from "./upload.ts";
import * as user_topics from "./user_topics.ts";
import * as widget_modal from "./widget_modal.ts";

export function abort_xhr() {
    upload.compose_upload_cancel();
}

function setup_compose_actions_hooks() {
    compose_actions.register_compose_box_clear_hook(compose.clear_invites);
    compose_actions.register_compose_box_clear_hook(compose.clear_private_stream_alert);
    compose_actions.register_compose_box_clear_hook(compose.clear_preview_area);

    compose_actions.register_compose_cancel_hook(abort_xhr);
    compose_actions.register_compose_cancel_hook(compose_call.abort_video_callbacks);
}

export function initialize() {
    // Register hooks for compose_actions.
    setup_compose_actions_hooks();

    $(".compose-control-buttons-container .video_link").toggle(
        compose_call.compute_show_video_chat_button(),
    );
    $(".compose-control-buttons-container .audio_link").toggle(
        compose_call.compute_show_audio_chat_button(),
    );

    $("textarea#compose-textarea").on("keydown", (event) => {
        compose_ui.handle_keydown(event, $("textarea#compose-textarea").expectOne());
    });
    $("textarea#compose-textarea").on("keyup", (event) => {
        compose_ui.handle_keyup(event, $("textarea#compose-textarea").expectOne());
    });

    $("textarea#compose-textarea").on("input", () => {
        if ($("#compose").hasClass("preview_mode")) {
            compose.render_preview_area();
        }
        const recipient_widget_hidden =
            $(".compose_select_recipient-dropdown-list-container").length === 0;
        if (recipient_widget_hidden) {
            compose_validate.warn_if_topic_resolved(false);
        }
        const compose_text_length = compose_validate.check_overflow_text($("#send_message_form"));

        // Change compose close button tooltip as per condition.
        // We save compose text in draft only if its length is > 2.
        if (compose_text_length > 2) {
            $("#compose_close").attr(
                "data-tooltip-template-id",
                "compose_close_and_save_tooltip_template",
            );
        } else {
            $("#compose_close").attr("data-tooltip-template-id", "compose_close_tooltip_template");
        }

        // The poll widget requires an empty compose box.
        $(".needs-empty-compose").toggleClass("disabled-on-hover", compose_text_length > 0);

        if (compose_state.get_is_content_unedited_restored_draft()) {
            compose_state.set_is_content_unedited_restored_draft(false);
        }
    });

    $("#compose form").on("submit", (e) => {
        e.preventDefault();
        compose.finish();
    });

    resize.watch_manual_resize("#compose-textarea");

    // Updates compose max-height and scroll to bottom button position when
    // there is a change in compose height like when a compose banner is displayed.
    const update_compose_max_height = new ResizeObserver((_entries) => {
        requestAnimationFrame(() => {
            resize.reset_compose_message_max_height();
        });
    });
    update_compose_max_height.observe(document.querySelector("#compose"));

    function get_input_info(event) {
        const $edit_banners_container = $(event.target).closest(".edit_form_banners");
        const is_edit_input = $edit_banners_container.length > 0;
        const $banner_container = is_edit_input ? $edit_banners_container : $("#compose_banners");
        return {is_edit_input, $banner_container};
    }

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.wildcard_warning,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const {$banner_container, is_edit_input} = get_input_info(event);
            const $row = $(event.target).closest(".message_row");
            compose_validate.clear_stream_wildcard_warnings($banner_container);
            compose_validate.set_user_acknowledged_stream_wildcard_flag(true);
            if (is_edit_input) {
                message_edit.save_message_row_edit($row);
            } else if (event.target.dataset.validationTrigger === "schedule") {
                compose_send_menu_popover.open_schedule_message_menu();

                // We need to set this flag to true here because `open_schedule_message_menu` validates the message and sets
                // the user acknowledged wildcard flag back to 'false' and we don't want that to happen because then it
                // would again show the wildcard warning banner when we actually send the message from 'send-later' modal.
                compose_validate.set_user_acknowledged_stream_wildcard_flag(true);
            } else {
                compose.finish();
            }
        },
    );

    const user_not_subscribed_selector = `.${CSS.escape(
        compose_banner.CLASSNAMES.user_not_subscribed,
    )}`;
    $("body").on(
        "click",
        `${user_not_subscribed_selector} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const stream_id = compose_state.stream_id();
            if (stream_id === undefined) {
                return;
            }
            const sub = stream_data.get_sub_by_id(stream_id);
            stream_settings_components.sub_or_unsub(sub);
            $(user_not_subscribed_selector).remove();
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(compose_banner.CLASSNAMES.topic_resolved)} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id"), 10);
            const topic_name = $target.attr("data-topic-name");

            message_edit.with_first_message_id(stream_id, topic_name, (message_id) => {
                if (message_id === undefined) {
                    // There is no message in the topic, so it is sufficient to
                    // just remove the topic resolved prefix (✔) from the topic name.
                    const $input = $("input#stream_message_recipient_topic");
                    const new_topic = unresolve_name(topic_name);
                    $input.val(new_topic);
                    // Trigger an input event, since this is a form of
                    // user-triggered edit to that field.
                    $input.trigger("input");

                    // Renarrow to the unresolved topic if currently viewing the resolved topic.
                    const current_filter = narrow_state.filter();
                    const stream_id_string = stream_id.toString();
                    if (
                        current_filter &&
                        (current_filter.is_conversation_view() ||
                            current_filter.is_conversation_view_with_near()) &&
                        current_filter.has_topic(stream_id_string, topic_name)
                    ) {
                        message_view.show(
                            [
                                {operator: "channel", operand: stream_id_string},
                                {operator: "topic", operand: new_topic},
                            ],
                            {},
                        );
                    }
                } else {
                    message_edit.toggle_resolve_topic(message_id, topic_name, true);
                }
                compose_validate.clear_topic_resolved_warning(true);
            });
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.unmute_topic_notification,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();

            const $target = $(event.target).parents(".main-view-banner");
            const stream_id = Number.parseInt($target.attr("data-stream-id"), 10);
            const topic_name = $target.attr("data-topic-name");

            user_topics.set_user_topic_visibility_policy(
                stream_id,
                topic_name,
                user_topics.all_visibility_policies.UNMUTED,
                false,
                true,
            );
        },
    );

    const automatic_new_visibility_policy_banner_selector = `.${CSS.escape(compose_banner.CLASSNAMES.automatic_new_visibility_policy)}`;
    $("body").on(
        "click",
        `${automatic_new_visibility_policy_banner_selector} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            if ($(event.target).attr("data-action") === "mark-as-read") {
                $(event.target)
                    .parents(`${automatic_new_visibility_policy_banner_selector}`)
                    .remove();
                onboarding_steps.post_onboarding_step_as_read("visibility_policy_banner");
                return;
            }
            window.location.href = "/#settings/notifications";
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.unscheduled_message,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const send_at_timestamp = scheduled_messages.get_selected_send_later_timestamp();
            compose_send_menu_popover.do_schedule_message(send_at_timestamp);
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(
            compose_banner.CLASSNAMES.recipient_not_subscribed,
        )} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            const {$banner_container} = get_input_info(event);
            const $invite_row = $(event.target).parents(".main-view-banner");

            const user_id = Number($invite_row.attr("data-user-id"));
            const stream_id = Number($invite_row.attr("data-stream-id"));

            function success() {
                $invite_row.remove();
            }

            function xhr_failure(xhr) {
                let error_message = "Failed to subscribe user!";
                if (xhr.responseJSON?.msg) {
                    error_message = xhr.responseJSON.msg;
                }
                compose.clear_invites();
                compose_banner.show_error_message(
                    error_message,
                    compose_banner.CLASSNAMES.generic_compose_error,
                    $banner_container,
                    $("textarea#compose-textarea"),
                );
                $(event.target).prop("disabled", true);
            }

            const sub = sub_store.get(stream_id);

            subscriber_api.add_user_ids_to_stream([user_id], sub, true, success, xhr_failure);
        },
    );

    $("body").on(
        "click",
        `.${CSS.escape(compose_banner.CLASSNAMES.search_view)} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            message_view.to_compose_target();
        },
    );

    const jump_to_conversation_banner_selector = `.${CSS.escape(compose_banner.CLASSNAMES.jump_to_sent_message_conversation)}`;
    $("body").on(
        "click",
        `${jump_to_conversation_banner_selector} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            $(event.target).parents(`${jump_to_conversation_banner_selector}`).remove();
            onboarding_steps.post_onboarding_step_as_read("jump_to_conversation_banner");
        },
    );

    const non_interleaved_view_messages_fading_banner_selector = `.${CSS.escape(compose_banner.CLASSNAMES.non_interleaved_view_messages_fading)}`;
    $("body").on(
        "click",
        `${non_interleaved_view_messages_fading_banner_selector} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            $(event.target)
                .parents(`${non_interleaved_view_messages_fading_banner_selector}`)
                .remove();
            onboarding_steps.post_onboarding_step_as_read("non_interleaved_view_messages_fading");
        },
    );

    const interleaved_view_messages_fading_banner_selector = `.${CSS.escape(compose_banner.CLASSNAMES.interleaved_view_messages_fading)}`;
    $("body").on(
        "click",
        `${interleaved_view_messages_fading_banner_selector} .main-view-banner-action-button`,
        (event) => {
            event.preventDefault();
            $(event.target).parents(`${interleaved_view_messages_fading_banner_selector}`).remove();
            onboarding_steps.post_onboarding_step_as_read("interleaved_view_messages_fading");
        },
    );

    for (const classname of Object.values(compose_banner.CLASSNAMES)) {
        const classname_selector = `.${CSS.escape(classname)}`;
        $("body").on("click", `${classname_selector} .main-view-banner-close-button`, (event) => {
            event.preventDefault();
            $(event.target).parents(classname_selector).remove();
        });
    }

    // Click event binding for "Attach files" button
    // Triggers a click on a hidden file input field

    $("#compose").on("click", ".compose_upload_file", (e) => {
        e.preventDefault();
        e.stopPropagation();

        $("#compose .file_input").trigger("click");
    });

    $("body").on("click", ".video_link", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const show_video_chat_button = compose_call.compute_show_video_chat_button();

        if (!show_video_chat_button) {
            return;
        }

        // Use Zulip Calls Plugin instead of default behavior
        create_embedded_call_instead_of_link($(e.target), true); // true for video
    });

    $("body").on("click", ".audio_link", (e) => {
        e.preventDefault();
        e.stopPropagation();

        const show_audio_chat_button = compose_call.compute_show_audio_chat_button();

        if (!show_audio_chat_button) {
            return;
        }

        // Use Zulip Calls Plugin instead of default behavior
        create_embedded_call_instead_of_link($(e.target), false); // false for audio
    });

    $("body").on("click", ".time_pick", function (e) {
        e.preventDefault();
        e.stopPropagation();

        let $target_textarea;
        let edit_message_id;
        const $compose_click_target = $(this);
        if ($compose_click_target.parents(".message_edit_form").length === 1) {
            edit_message_id = rows.id($compose_click_target.parents(".message_row"));
            $target_textarea = $(`#edit_form_${CSS.escape(edit_message_id)} .message_edit_content`);
        } else {
            $target_textarea = $compose_click_target.closest("form").find("textarea");
        }

        if (!flatpickr.is_open()) {
            const on_timestamp_selection = (val) => {
                const timestr = `<time:${val}> `;
                compose_ui.insert_syntax_and_focus(timestr, $target_textarea);
            };

            flatpickr.show_flatpickr(
                $compose_click_target[0],
                on_timestamp_selection,
                get_timestamp_for_flatpickr(),
                {
                    // place the time picker wherever there is space and center it horizontally
                    position: "auto center",
                    // Since we want to handle close of flatpickr manually, we don't want
                    // flatpickr to hide automatically on clicking its trigger element.
                    ignoredFocusElements: [e.currentTarget],
                },
            );
        } else {
            flatpickr.flatpickr_instance?.close();
        }
    });

    $("body").on("click", ".compose_control_button_container:not(.disabled) .add-poll", (e) => {
        e.preventDefault();
        e.stopPropagation();

        function validate_input() {
            const question = $("#poll-question-input").val().trim();

            if (question === "") {
                ui_report.error(
                    $t_html({defaultMessage: "Please enter a question."}),
                    undefined,
                    $("#dialog_error"),
                );
                return false;
            }
            return true;
        }

        dialog_widget.launch({
            html_heading: $t_html({defaultMessage: "Create a poll"}),
            html_body: render_add_poll_modal(),
            html_submit_button: $t_html({defaultMessage: "Add poll"}),
            close_on_submit: true,
            on_click(e) {
                // frame a message using data input in modal, then populate the compose textarea with it
                e.preventDefault();
                e.stopPropagation();
                const poll_message_content = widget_modal.frame_poll_message_content();
                compose_ui.insert_syntax_and_focus(poll_message_content);
            },
            on_show() {
                setTimeout(() => {
                    $("#poll-question-input").trigger("focus");
                }, 0);
            },
            validate_input,
            form_id: "add-poll-form",
            id: "add-poll-modal",
            post_render: widget_modal.poll_options_setup,
            help_link: "https://zulip.com/help/create-a-poll",
        });
    });

    $("body").on("input", "#add-todo-modal .todo-input", (e) => {
        e.preventDefault();
        e.stopPropagation();

        $(".option-row").each(function () {
            const todo_name = $(this).find(".todo-input").val();
            const $todo_description = $(this).find(".todo-description-input");
            $todo_description.prop("disabled", !todo_name);
        });
    });

    $("body").on(
        "click",
        ".compose_control_button_container:not(.disabled) .add-todo-list",
        (e) => {
            e.preventDefault();
            e.stopPropagation();

            function validate_input(e) {
                let is_valid = true;
                e.preventDefault();
                e.stopPropagation();
                $(".option-row").each(function () {
                    const todo_name = $(this).find(".todo-input").val();
                    const todo_description = $(this).find(".todo-description-input").val();
                    if (!todo_name && todo_description) {
                        ui_report.error(
                            $t_html({defaultMessage: "Please enter task title."}),
                            undefined,
                            $("#dialog_error"),
                        );
                        is_valid = false;
                    }
                });
                return is_valid;
            }

            dialog_widget.launch({
                html_heading: $t_html({defaultMessage: "Create a collaborative to-do list"}),
                html_body: render_add_todo_list_modal(),
                html_submit_button: $t_html({defaultMessage: "Create to-do list"}),
                close_on_submit: true,
                on_click(e) {
                    // frame a message using data input in modal, then populate the compose textarea with it
                    e.preventDefault();
                    e.stopPropagation();
                    const todo_message_content = widget_modal.frame_todo_message_content();
                    compose_ui.insert_syntax_and_focus(todo_message_content);
                },
                on_show() {
                    setTimeout(() => {
                        $("#todo-title-input").trigger("select");
                    }, 0);
                },
                form_id: "add-todo-form",
                validate_input,
                id: "add-todo-modal",
                post_render: widget_modal.todo_list_tasks_setup,
                help_link: "https://zulip.com/help/collaborative-to-do-lists",
            });
        },
    );

    $("#compose").on("click", ".markdown_preview", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose.show_preview_area();
    });

    $("#compose").on("click", ".undo_markdown_preview", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose.clear_preview_area();
    });

    $("#compose").on("click", ".expand-composebox-button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_intermediate_size();
    });

    $("#compose").on("click", ".maximize-composebox-button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_full_size();
    });

    $("#compose").on("click", ".narrow_to_compose_recipients", (e) => {
        e.preventDefault();
        message_view.to_compose_target();
    });

    $("#compose").on("click", ".collapse-composebox-button", (e) => {
        e.preventDefault();
        e.stopPropagation();

        compose_ui.make_compose_box_original_size();
    });

    $("textarea#compose-textarea").on("focus", () => {
        compose_recipient.update_compose_area_placeholder_text();
        compose_fade.do_update_all();
        if (narrow_state.narrowed_by_reply()) {
            compose_notifications.maybe_show_one_time_non_interleaved_view_messages_fading_banner();
        } else {
            compose_notifications.maybe_show_one_time_interleaved_view_messages_fading_banner();
        }
    });

    $(".compose-scrollable-buttons").on(
        "scroll",
        _.throttle((e) => {
            compose_ui.handle_scrolling_formatting_buttons(e);
        }, 150),
    );

    $("#compose_recipient_box").on("click", "#recipient_box_clear_topic_button", () => {
        const $input = $("input#stream_message_recipient_topic");
        $input.val("");
        $input.trigger("focus");
        compose_validate.validate_and_update_send_button_status();
    });

    $("input#stream_message_recipient_topic").on("focus", () => {
        const $input = $("input#stream_message_recipient_topic");
        compose_recipient.update_topic_displayed_text($input.val(), true);
        compose_recipient.update_compose_area_placeholder_text();
        // When the topic input is focused, we no longer treat
        // the recipient row as low attention, as we assume the user
        // is doing something that requires keeping attention called
        // to the recipient row
        compose_recipient.set_high_attention_recipient_row();

        $("input#stream_message_recipient_topic").one("blur", () => {
            compose_recipient.update_topic_displayed_text($input.val());
            compose_recipient.update_compose_area_placeholder_text();
        });
    });

    $("input#stream_message_recipient_topic").on("input", () => {
        compose_recipient.update_compose_area_placeholder_text();
    });

    $("#private_message_recipient").on("focus", () => {
        // When the DM input is focused, we no longer treat
        // the recipient row as low attention, as we assume the user
        // is doing something that requires keeping attention called
        // to the recipient row
        compose_recipient.set_high_attention_recipient_row();
    });

    $("input#stream_message_recipient_topic, #private_message_recipient").on("blur", () => {
        compose_recipient.update_recipient_row_attention_level();
    });

    $(window).on("blur", () => {
        // Save drafts when the window loses focus to help
        // ensure no work is lost
        drafts.update_draft();
    });

    $("body").on("click", ".formatting_button", function (e) {
        const $compose_click_target = $(this);
        const $textarea = $compose_click_target.closest("form").find("textarea");
        const format_type = $(this).attr("data-format-type");
        compose_ui.format_text($textarea, format_type);
        popovers.hide_all();
        $textarea.trigger("focus");
        e.preventDefault();
        e.stopPropagation();
    });

    // Zulip Calls Plugin - Function to create embedded calls instead of links
    function create_embedded_call_instead_of_link($button, isVideoCall) {
        console.log('🚀 Zulip Calls Plugin: Creating embedded call, isVideo:', isVideoCall);

        // Get recipient email
        function getRecipientEmail() {
            console.log('🔍 [compose_setup.js] Starting recipient search...');

            // Check if we're in a private message context
            const messageType = compose_state.get_message_type();
            console.log('🔍 [compose_setup.js] Message type:', messageType);

            if (messageType === "private") {
                // First try to get from the compose state
                const recipients = compose_state.private_message_recipient_emails();
                console.log('🔍 [compose_setup.js] Recipients from compose state:', recipients);
                if (recipients) {
                    const firstRecipient = recipients.split(',')[0].trim();
                    console.log('📧 [compose_setup.js] Found recipient via compose_state:', firstRecipient);
                    return firstRecipient;
                }

                // Fallback: check the DM input field
                const dmInput = $("#private_message_recipient");
                console.log('🔍 [compose_setup.js] DM input:', dmInput.val());
                if (dmInput.length && dmInput.val()) {
                    const inputRecipient = dmInput.val().trim().split(',')[0].trim();
                    console.log('📧 [compose_setup.js] Found recipient via input:', inputRecipient);
                    return inputRecipient;
                }
            }

            // If not composing but viewing a DM conversation, get recipient from narrow
            const currentFilter = narrow_state.filter();
            console.log('🔍 [compose_setup.js] Current filter:', currentFilter);

            if (currentFilter && currentFilter.is_conversation_view()) {
                console.log('🔍 [compose_setup.js] Is conversation view');
                const termTypes = currentFilter.sorted_term_types();
                console.log('🔍 [compose_setup.js] Term types:', termTypes);

                if (termTypes.includes("dm")) {
                    console.log('🔍 [compose_setup.js] Has DM terms');
                    // Get the recipient IDs from the narrow
                    const recipientIds = currentFilter.operands("dm");
                    console.log('🔍 [compose_setup.js] Recipient IDs:', recipientIds);

                    if (recipientIds && recipientIds.length > 0) {
                        // Get the first recipient's email
                        const firstRecipientId = recipientIds[0];
                        console.log('🔍 [compose_setup.js] First recipient ID:', firstRecipientId);
                        const user = people.get_by_user_id(firstRecipientId);
                        console.log('🔍 [compose_setup.js] User from people API:', user);
                        console.log('🔍 [compose_setup.js] User ID:', firstRecipientId);
                        console.log('🔍 [compose_setup.js] User email:', user ? user.email : 'NO EMAIL');

                        if (user && user.email) {
                            console.log('📧 [compose_setup.js] Found recipient via narrow:', user.email);
                            console.log('📧 [compose_setup.js] User full object:', JSON.stringify(user, null, 2));
                            return user.email;
                        } else {
                            console.log('❌ [compose_setup.js] No user found for ID:', firstRecipientId);

                            // Try to get all users to see what's available
                            console.log('👥 [compose_setup.js] All available users:');
                            const allUsers = people.get_realm_active_human_users();
                            allUsers.slice(0, 5).forEach(u => {
                                console.log(`  - ID: ${u.user_id}, Email: ${u.email}, Name: ${u.full_name}`);
                            });
                        }
                    }
                }
            }

            // If we still don't have a recipient, show available users for debugging
            console.log('❌ [compose_setup.js] No recipient found. Available users:');
            const allUsers = people.get_realm_active_human_users();
            allUsers.slice(0, 10).forEach(u => {
                console.log(`  - ID: ${u.user_id}, Email: ${u.email}, Name: ${u.full_name}`);
            });

            return null;
        }

        const recipientEmail = getRecipientEmail();

        if (!recipientEmail) {
            // Get available users to show in error message
            const allUsers = people.get_realm_active_human_users();
            const availableUsers = allUsers.slice(0, 5).map(u => u.email).join(', ');
            const moreCount = allUsers.length > 5 ? ` and ${allUsers.length - 5} more` : '';
            
            compose_banner.show_error_message(
                `Please select a recipient for the call. Available users: ${availableUsers}${moreCount}`,
                compose_banner.CLASSNAMES.generic_compose_error,
                $("#compose_banners"),
                $("textarea#compose-textarea"),
            );
            return;
        }

        // Validate that the recipient exists in the realm
        console.log('🔍 [compose_setup.js] Validating recipient:', recipientEmail);
        const recipientUser = people.get_by_email(recipientEmail);
        console.log('🔍 [compose_setup.js] Recipient user found:', recipientUser);
        
        if (!recipientUser) {
            // Get available users to show in error message
            const allUsers = people.get_realm_active_human_users();
            const availableUsers = allUsers.slice(0, 5).map(u => u.email).join(', ');
            const moreCount = allUsers.length > 5 ? ` and ${allUsers.length - 5} more` : '';
            
            console.log('❌ [compose_setup.js] Recipient validation failed. User not found in people API');
            console.log('❌ [compose_setup.js] Available users:', availableUsers);
            
            compose_banner.show_error_message(
                `Recipient "${recipientEmail}" not found in this realm. Available users: ${availableUsers}${moreCount}`,
                compose_banner.CLASSNAMES.generic_compose_error,
                $("#compose_banners"),
                $("textarea#compose-textarea"),
            );
            return;
        }
        
        console.log('✅ [compose_setup.js] Recipient validation passed:', recipientUser.email, 'delivery_email:', recipientUser.delivery_email);

        // Show loading state
        $button.prop('disabled', true).addClass('creating-call');

        // Create the embedded call
        $.ajax({
            url: '/api/v1/calls/create-embedded',
            method: 'POST',
            headers: {
                'X-CSRFToken': $('meta[name="csrf-token"]').attr('content') || $('input[name="csrfmiddlewaretoken"]').val()
            },
            data: {
                recipient_email: recipientEmail,
                is_video_call: isVideoCall,
                redirect_to_meeting: true
            },
            success: function(response) {
                console.log('📞 Call creation response:', response);

                if (response.result === 'success' && response.redirect_url) {
                    // Open meeting immediately
                    window.open(response.redirect_url, '_blank', 'width=1200,height=800,resizable=yes,menubar=no,toolbar=no');

                    // Insert call link in compose box
                    const $textarea = $('textarea#compose-textarea');
                    const callType = isVideoCall ? 'video' : 'audio';
                    const linkText = `Join ${callType} call`;
                    const callMessage = `[${linkText}](${response.redirect_url})`;
                    const currentValue = $textarea.val();
                    const newValue = currentValue + (currentValue ? '\n\n' : '') + callMessage;

                    $textarea.val(newValue);
                    $textarea.trigger('input');
                    $textarea.focus();

                    // Show success message
                    const successMessage = `${callType} call started with ${response.recipient.full_name}`;
                    const successBannerHtml = render_compose_banner({
                        banner_type: compose_banner.SUCCESS,
                        stream_id: null,
                        topic_name: null,
                        banner_text: successMessage,
                        button_text: null,
                        classname: "call_success_banner",
                    });
                    compose_banner.append_compose_banner_to_banner_list($(successBannerHtml), $("#compose_banners"));
                } else {
                    throw new Error(response.message || 'Failed to create call');
                }
            },
            error: function(xhr) {
                console.error('❌ Call creation failed:', xhr);
                console.error('❌ Response status:', xhr.status);
                console.error('❌ Response text:', xhr.responseText);
                
                const response = xhr.responseJSON;
                console.error('❌ Response JSON:', response);
                
                let errorMsg = response?.message || 'Failed to create call';
                
                // If we have available users in the response, show them
                if (response?.available_users && response.available_users.length > 0) {
                    // Clean up the user emails (remove quotes)
                    const cleanUsers = response.available_users.map(email => email.replace(/'/g, ''));
                    const availableUsers = cleanUsers.slice(0, 5).join(', ');
                    const moreCount = response.available_users.length > 5 ? ` and ${response.available_users.length - 5} more` : '';
                    errorMsg += `\n\nAvailable users: ${availableUsers}${moreCount}`;
                }
                
                compose_banner.show_error_message(
                    errorMsg,
                    compose_banner.CLASSNAMES.generic_compose_error,
                    $("#compose_banners"),
                    $("textarea#compose-textarea"),
                );

                // Fallback to original Zulip functionality
                console.log('🔄 Falling back to original Zulip call functionality');
                compose_call_ui.generate_and_insert_audio_or_video_call_link($button, !isVideoCall);
            },
            complete: function() {
                $button.prop('disabled', false).removeClass('creating-call');
            }
        });
    }

    if (page_params.narrow !== undefined) {
        if (page_params.narrow_topic !== undefined) {
            compose_actions.start({
                message_type: "stream",
                topic: page_params.narrow_topic,
            });
        } else {
            compose_actions.start({message_type: "stream"});
        }
    }
}
