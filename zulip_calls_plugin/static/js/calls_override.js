/**
 * Zulip Calls Plugin - Direct Integration
 *
 * This script directly overrides Zulip's compose call functionality
 * It should be loaded after Zulip's main JavaScript
 */

(function() {
    'use strict';

    // Wait for Zulip's compose_call_ui to be available
    function waitForZulip() {
        if (typeof window.compose_call_ui === 'undefined' || typeof $ === 'undefined') {
            setTimeout(waitForZulip, 100);
            return;
        }

        console.log('Zulip Calls Plugin: Zulip loaded, overriding call functionality...');
        overrideZulipCallFunctionality();
    }

    function overrideZulipCallFunctionality() {
        // Store the original function
        const originalFunction = window.compose_call_ui.generate_and_insert_audio_or_video_call_link;

        if (originalFunction) {
            // Override the original function
            window.compose_call_ui.generate_and_insert_audio_or_video_call_link = function($target_element, is_audio_call) {
                console.log('Zulip Calls Plugin: Intercepted call creation, is_audio_call:', is_audio_call);

                // Use our embedded call functionality instead
                createEmbeddedCall($target_element, !is_audio_call);
            };

            console.log('Zulip Calls Plugin: Successfully overrode call functionality');
        } else {
            console.warn('Zulip Calls Plugin: Could not find original call function to override');

            // Fallback: override click handlers directly
            overrideCallButtons();
        }
    }

    function createEmbeddedCall($button, isVideoCall) {
        // Get recipient email
        const recipientEmail = getRecipientEmail();

        if (!recipientEmail) {
            showError('Please select a recipient for the call');
            return;
        }

        // Show loading state
        $button.prop('disabled', true).addClass('loading-call');

        // Create the call
        $.ajax({
            url: '/api/v1/calls/create-embedded',
            method: 'POST',
            headers: {
                'X-CSRFToken': $('input[name="csrfmiddlewaretoken"]').val() ||
                              $('[name="csrfmiddlewaretoken"]').val() ||
                              getCookie('csrftoken')
            },
            data: {
                recipient_email: recipientEmail,
                is_video_call: isVideoCall,
                redirect_to_meeting: true
            },
            success: function(response) {
                if (response.result === 'success') {
                    if (response.action === 'redirect' && response.redirect_url) {
                        // Open Jitsi meeting directly
                        window.open(response.redirect_url, '_blank', 'width=1200,height=800,resizable=yes,menubar=no,toolbar=no,status=no');

                        // Insert call message in compose
                        insertCallMessage(response, isVideoCall);

                        // Show success notification
                        if (window.ui_report && window.ui_report.success) {
                            ui_report.success(`${isVideoCall ? 'Video' : 'Audio'} call started with ${response.recipient.full_name}`);
                        }
                    } else {
                        // Fallback to original function
                        console.log('Zulip Calls Plugin: Fallback to original function');
                        originalFunction($button, !isVideoCall);
                    }
                } else {
                    showError('Failed to create call: ' + (response.message || response.msg));
                }
            },
            error: function(xhr) {
                console.log('Zulip Calls Plugin: Call creation failed, falling back to original');
                // Fallback to original Zulip functionality
                if (originalFunction) {
                    originalFunction($button, !isVideoCall);
                } else {
                    showError('Failed to create call');
                }
            },
            complete: function() {
                $button.prop('disabled', false).removeClass('loading-call');
            }
        });
    }

    function getRecipientEmail() {
        // Try multiple methods to get recipient email

        // Method 1: Direct message recipient input
        const dmInput = $('#private_message_recipient');
        if (dmInput.length && dmInput.val()) {
            const recipients = dmInput.val().trim();
            if (recipients) {
                return recipients.split(',')[0].trim();
            }
        }

        // Method 2: Check compose state if available
        if (window.compose_state) {
            const recipients = compose_state.private_message_recipient();
            if (recipients) {
                return recipients.split(',')[0].trim();
            }
        }

        // Method 3: Check narrow state for DM conversations
        if (window.narrow_state && narrow_state.filter) {
            const filter = narrow_state.filter();
            if (filter && filter.is_conversation_view && filter.is_conversation_view()) {
                const emails = filter.operands('pm-with');
                if (emails && emails.length > 0) {
                    const currentUserEmail = window.page_params?.email || window.current_user?.email;
                    const otherEmails = emails.filter(email => email !== currentUserEmail);
                    if (otherEmails.length > 0) {
                        return otherEmails[0];
                    }
                }
            }
        }

        return null;
    }

    function insertCallMessage(callData, isVideoCall) {
        const callType = isVideoCall ? 'video' : 'audio';
        const linkText = `Join ${callType} call`;
        const callUrl = callData.redirect_url || callData.call_url;

        if (!callUrl) return;

        const $textarea = $('textarea#compose-textarea');
        const currentValue = $textarea.val();
        const callMessage = `[${linkText}](${callUrl})`;
        const newValue = currentValue + (currentValue ? '\n\n' : '') + callMessage;

        $textarea.val(newValue).trigger('input').focus();
    }

    function overrideCallButtons() {
        // Direct event handler override as fallback
        $(document).off('click.calls-override', '.video_link, .audio_link');
        $(document).on('click.calls-override', '.video_link', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            createEmbeddedCall($(this), true);
        });

        $(document).on('click.calls-override', '.audio_link', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();
            createEmbeddedCall($(this), false);
        });
    }

    function showError(message) {
        if (window.ui_report && window.ui_report.error) {
            ui_report.error(message);
        } else {
            alert('Error: ' + message);
        }
    }

    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Add loading styles
    $('<style>').prop('type', 'text/css').html(`
        .loading-call {
            opacity: 0.6 !important;
            cursor: wait !important;
        }
    `).appendTo('head');

    // Start the integration
    console.log('Zulip Calls Plugin: Starting integration...');
    waitForZulip();

    // Export for debugging
    window.zulipCallsPlugin = {
        createEmbeddedCall: createEmbeddedCall,
        getRecipientEmail: getRecipientEmail,
        overrideCallButtons: overrideCallButtons
    };

})();