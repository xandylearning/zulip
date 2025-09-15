// Zulip Calls Plugin - Embedded Call Integration
// This script overrides the default call behavior to use embedded calls

(function() {
    'use strict';

    // Store active call windows
    const activeCallWindows = new Map();

    // Override the original call generation function
    function overrideCallButtons() {
        // Remove existing event handlers that might conflict
        $(document).off('click.embedded_calls', '.video_link, .audio_link');

        // Use event delegation to handle dynamically added buttons
        $(document).on('click.embedded_calls', '.video_link', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            console.log('Embedded calls: Video call button clicked');
            const isVideoCall = true;
            initiateEmbeddedCall($(this), isVideoCall);
        });

        $(document).on('click.embedded_calls', '.audio_link', function(e) {
            e.preventDefault();
            e.stopPropagation();
            e.stopImmediatePropagation();

            console.log('Embedded calls: Audio call button clicked');
            const isVideoCall = false;
            initiateEmbeddedCall($(this), isVideoCall);
        });

        // Mark buttons as enhanced to avoid duplicate handlers
        $('.video_link, .audio_link').attr('data-embedded-calls', 'enabled');

        console.log('Embedded calls: Enhanced call button handlers');
    }

    function initiateEmbeddedCall($button, isVideoCall) {
        // Get recipient email from the current compose context
        const recipientEmail = getRecipientEmail();

        if (!recipientEmail) {
            return; // Error already shown in getRecipientEmail
        }

        // Show loading state
        const originalText = $button.attr('data-tippy-content');
        $button.addClass('loading').attr('disabled', true);

        // Create the call with redirect option
        $.ajax({
            url: '/api/v1/calls/create-embedded',
            method: 'POST',
            data: {
                recipient_email: recipientEmail,
                is_video_call: isVideoCall,
                redirect_to_meeting: true  // Request immediate redirect to meeting
            },
            success: function(response) {
                if (response.result === 'success') {
                    // Check if we should redirect immediately
                    if (response.action === 'redirect' && response.redirect_url) {
                        // Open the Jitsi meeting directly
                        window.open(response.redirect_url, '_blank', 'width=1200,height=800,resizable=yes');

                        // Show success message
                        showSuccessMessage(`${isVideoCall ? 'Video' : 'Audio'} call started with ${response.recipient.full_name}`);

                        // Insert a message about the call in the compose box
                        insertCallMessage(response, isVideoCall);
                    } else {
                        // Fallback to embedded window approach
                        openEmbeddedCallWindow(response, isVideoCall);
                        insertCallMessage(response, isVideoCall);
                    }
                } else {
                    showError('Failed to create call: ' + (response.message || response.msg || 'Unknown error'));
                }
            },
            error: function(xhr) {
                let errorMsg = 'Failed to create call';
                if (xhr.responseJSON) {
                    errorMsg = xhr.responseJSON.message || xhr.responseJSON.msg || errorMsg;

                    // Handle specific error codes
                    if (xhr.responseJSON.code === 'RECIPIENT_REQUIRED') {
                        errorMsg = 'Please select a recipient for the call';
                    }
                }
                showError(errorMsg);
            },
            complete: function() {
                $button.removeClass('loading').attr('disabled', false);
            }
        });
    }

    function getRecipientEmail() {
        // Try multiple approaches to get the recipient email

        // Method 1: Check for direct message recipient input
        const dmRecipientInput = $('#private_message_recipient');
        if (dmRecipientInput.length > 0 && dmRecipientInput.val()) {
            const recipients = dmRecipientInput.val().trim();
            if (recipients) {
                // For multiple recipients, take the first one
                const emails = recipients.split(',').map(r => r.trim());
                return emails[0];
            }
        }

        // Method 2: Check compose recipient type and inputs
        const recipientType = $('input[name="message_type"]:checked').val() ||
                             $('#compose-content input[name="type"]:checked').val();

        if (recipientType === 'private') {
            // Look for various possible DM recipient input selectors
            const possibleInputs = [
                'input[name="private_message_recipient"]',
                '#private_message_recipient',
                '.recipient_box input[name="private_message_recipient"]',
                '#compose-content input[name="private_message_recipient"]'
            ];

            for (const selector of possibleInputs) {
                const $input = $(selector);
                if ($input.length > 0 && $input.val()) {
                    const recipients = $input.val().trim();
                    if (recipients) {
                        const emails = recipients.split(',').map(r => r.trim());
                        return emails[0];
                    }
                }
            }
        } else if (recipientType === 'stream') {
            // For stream messages, show error
            showError('Video calls are only available for direct messages. Please switch to a direct message.');
            return null;
        }

        // Method 3: Check if we're in a conversation/thread context
        if (window.narrow_state && typeof window.narrow_state.filter === 'function') {
            const filter = narrow_state.filter();
            if (filter && filter.is_conversation_view && filter.is_conversation_view()) {
                // We're in a DM conversation, try to get the other user
                const emails = filter.operands('pm-with');
                if (emails && emails.length > 0) {
                    // Filter out current user and return the first other user
                    const otherEmails = emails.filter(email =>
                        email !== window.current_user?.email &&
                        email !== window.page_params?.email
                    );
                    if (otherEmails.length > 0) {
                        return otherEmails[0];
                    }
                }
            }
        }

        // Method 4: Look for recipient in message editing context
        const messageRow = $('.selected_message, .focused_table .message_row').first();
        if (messageRow.length > 0) {
            const senderEmail = messageRow.attr('data-sender-email');
            if (senderEmail && senderEmail !== (window.current_user?.email || window.page_params?.email)) {
                return senderEmail;
            }
        }

        // Method 5: Check URL parameters for narrow state
        const urlParams = new URLSearchParams(window.location.search);
        const narrow = urlParams.get('narrow');
        if (narrow) {
            try {
                const narrowData = JSON.parse(decodeURIComponent(narrow));
                const pmWith = narrowData.find(item => item.operator === 'pm-with');
                if (pmWith && pmWith.operand) {
                    const emails = pmWith.operand.split(',').map(e => e.trim());
                    const otherEmails = emails.filter(email =>
                        email !== window.current_user?.email &&
                        email !== window.page_params?.email
                    );
                    if (otherEmails.length > 0) {
                        return otherEmails[0];
                    }
                }
            } catch (e) {
                console.log('Could not parse narrow from URL:', e);
            }
        }

        // If all methods fail, show an informative error
        showError('Please select a recipient for the call. Start typing in the "To:" field to add recipients.');
        return null;
    }

    function openEmbeddedCallWindow(callData, isVideoCall) {
        const callId = callData.call_id;
        const embeddedUrl = callData.embedded_url;

        // Check if we already have a window for this call
        if (activeCallWindows.has(callId)) {
            const existingWindow = activeCallWindows.get(callId);
            if (!existingWindow.closed) {
                existingWindow.focus();
                return;
            }
        }

        // Create new call window
        const callWindow = window.open(
            embeddedUrl,
            `zulip_call_${callId}`,
            'width=1200,height=800,resizable=yes,scrollbars=no,status=no,menubar=no,toolbar=no'
        );

        if (callWindow) {
            activeCallWindows.set(callId, callWindow);

            // Listen for messages from the call window
            window.addEventListener('message', function(event) {
                if (event.source === callWindow) {
                    handleCallWindowMessage(event.data, callId);
                }
            });

            // Clean up when window closes
            const checkClosed = setInterval(function() {
                if (callWindow.closed) {
                    clearInterval(checkClosed);
                    activeCallWindows.delete(callId);
                    console.log('Call window closed:', callId);
                }
            }, 1000);

            // Show notification about the call
            showCallNotification(callData, isVideoCall);
        } else {
            showError('Unable to open call window. Please check popup blocker settings.');
        }
    }

    function insertCallMessage(callData, isVideoCall) {
        // Insert a message about the call being started
        const callType = isVideoCall ? 'video' : 'audio';
        const linkText = `Join ${callType} call`;

        // Use the direct Jitsi URL if available, otherwise use embedded URL
        const callUrl = callData.redirect_url || callData.call_url ||
                       (callData.embedded_url ? `${window.location.origin}${callData.embedded_url}` : '');

        if (!callUrl) {
            console.warn('No call URL available for message insertion');
            return;
        }

        const $textarea = $('textarea#compose-textarea');
        const currentValue = $textarea.val();
        const callMessage = `[${linkText}](${callUrl})`;

        // Add the message
        const newValue = currentValue + (currentValue ? '\n\n' : '') + callMessage;
        $textarea.val(newValue);

        // Trigger events to update UI and enable send button
        $textarea.trigger('input').trigger('change');

        // Focus the textarea
        $textarea.focus();

        // If there's a compose validation function, call it
        if (window.compose_validate && window.compose_validate.validate_and_update_send_button_status) {
            compose_validate.validate_and_update_send_button_status();
        }
    }

    function handleCallWindowMessage(data, callId) {
        switch (data.type) {
            case 'call_started':
                console.log('Call started:', callId);
                showSuccessMessage('Call connected successfully');
                break;

            case 'call_ended':
                console.log('Call ended:', callId);
                activeCallWindows.delete(callId);
                showSuccessMessage('Call ended');
                break;

            case 'call_minimized':
                console.log('Call minimized:', callId);
                break;
        }
    }

    function showCallNotification(callData, isVideoCall) {
        const callType = isVideoCall ? 'Video' : 'Audio';
        const message = `${callType} call started with ${callData.recipient.full_name}`;

        // Create a custom notification
        const $notification = $(`
            <div class="embedded-call-notification" style="
                position: fixed;
                top: 20px;
                right: 20px;
                background: #52c41a;
                color: white;
                padding: 15px 20px;
                border-radius: 8px;
                box-shadow: 0 4px 12px rgba(0,0,0,0.15);
                z-index: 10000;
                max-width: 300px;
                font-size: 14px;
            ">
                <div style="font-weight: 600; margin-bottom: 5px;">📞 ${callType} Call Active</div>
                <div>${message}</div>
            </div>
        `);

        $('body').append($notification);

        // Remove notification after 5 seconds
        setTimeout(function() {
            $notification.fadeOut(500, function() {
                $notification.remove();
            });
        }, 5000);
    }

    function showError(message) {
        // Use Zulip's existing error notification system if available
        if (window.ui_report && window.ui_report.error) {
            ui_report.error(message);
        } else {
            alert('Error: ' + message);
        }
    }

    function showSuccessMessage(message) {
        // Use Zulip's existing success notification system if available
        if (window.ui_report && window.ui_report.success) {
            ui_report.success(message);
        } else {
            console.log('Success: ' + message);
        }
    }

    // Initialize when document is ready
    $(document).ready(function() {
        console.log('Embedded calls: Document ready, initializing...');

        // Override call buttons initially
        overrideCallButtons();

        // Re-override when compose is reloaded (for navigation)
        $(document).on('compose_state_changed', function() {
            console.log('Embedded calls: Compose state changed, re-initializing...');
            setTimeout(overrideCallButtons, 100);
        });

        // Listen for when new buttons are added to DOM
        if (window.MutationObserver) {
            const observer = new MutationObserver(function(mutations) {
                let shouldUpdate = false;
                mutations.forEach(function(mutation) {
                    if (mutation.addedNodes.length > 0) {
                        for (let i = 0; i < mutation.addedNodes.length; i++) {
                            const node = mutation.addedNodes[i];
                            if (node.nodeType === Node.ELEMENT_NODE) {
                                if ($(node).find('.video_link, .audio_link').length > 0 ||
                                    $(node).hasClass('video_link') ||
                                    $(node).hasClass('audio_link')) {
                                    shouldUpdate = true;
                                    break;
                                }
                            }
                        }
                    }
                });

                if (shouldUpdate) {
                    console.log('Embedded calls: New call buttons detected, updating handlers...');
                    setTimeout(overrideCallButtons, 50);
                }
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });
        } else {
            // Fallback for browsers without MutationObserver
            setInterval(function() {
                const $buttons = $('.video_link, .audio_link').not('[data-embedded-calls="enabled"]');
                if ($buttons.length > 0) {
                    console.log('Embedded calls: Found new call buttons, updating...');
                    overrideCallButtons();
                }
            }, 2000);
        }

        console.log('Embedded calls: Plugin initialized successfully');
    });

    // Export for debugging and external access
    window.embeddedCalls = {
        overrideCallButtons: overrideCallButtons,
        activeCallWindows: activeCallWindows,
        initiateEmbeddedCall: initiateEmbeddedCall,
        getRecipientEmail: getRecipientEmail,
        showError: showError,
        showSuccessMessage: showSuccessMessage
    };

    // Also add a global flag to indicate the plugin is loaded
    window.ZULIP_CALLS_PLUGIN_LOADED = true;
})();