// User and channel pill selector integration

import $ from "jquery";

export type PillWidget = any;

let current_pill_widget: PillWidget | null = null;

export function createUserPillWidget(container: HTMLElement): any {
    destroyCurrentWidget();

    // Create input field
    const $inputField = $('<input type="text" class="pill-input" placeholder="Type user name...">');

    // Create a simple pill container for users
    const widget = {
        container: $(container),
        $input: $inputField,
        input_field: () => $inputField,
        clear: () => {
            $(container).empty();
        },
        get_user_ids: () => {
            return $(container).find('.pill').map((_, el) => Number.parseInt($(el).data('user-id'), 10)).get();
        }
    };

    // Add input field to container
    widget.container.append($inputField);

    current_pill_widget = widget;
    return widget;
}

export function createStreamPillWidget(container: HTMLElement): any {
    destroyCurrentWidget();

    // Create input field
    const $inputField = $('<input type="text" class="pill-input" placeholder="Type channel name...">');

    // Create a simple pill container for streams
    const widget = {
        container: $(container),
        $input: $inputField,
        input_field: () => $inputField,
        clear: () => {
            $(container).empty();
        },
        get_stream_ids: () => {
            return $(container).find('.pill').map((_, el) => Number.parseInt($(el).data('stream-id'), 10)).get();
        }
    };

    // Add input field to container
    widget.container.append($inputField);

    current_pill_widget = widget;
    return widget;
}

export function destroyCurrentWidget(): void {
    if (current_pill_widget) {
        current_pill_widget.clear();
        current_pill_widget = null;
    }

    // Clean up event handlers
$(document).off('click.broadcast-pills-user');
    $(document).off('click.broadcast-pills-stream');
}

export function getSelectedUserIds(): number[] {
    if (!current_pill_widget) {
        return [];
    }

    if ("get_user_ids" in current_pill_widget) {
        return current_pill_widget.get_user_ids();
    }

    return [];
}

export function getSelectedStreamIds(): number[] {
    if (!current_pill_widget) {
        return [];
    }

    if ("get_stream_ids" in current_pill_widget) {
        return current_pill_widget.get_stream_ids();
    }

    return [];
}

export function getCurrentWidget(): PillWidget | null {
    return current_pill_widget;
}

export function populateUserTypeahead(widget: any): void {
    let currentMatches: {user_id: number; email: string; full_name: string}[] = [];
    let selectedIndex = -1;

    // Create dropdown container
    const $dropdown = $('<div class="user-dropdown" style="display: none;"></div>');
    widget.container.append($dropdown);

    // Show all users initially
    const allUsers = getAvailableUsers();
    currentMatches = allUsers;
    updateDropdown();

    // Handle input
    widget.input_field().on('input', function(this: HTMLInputElement) {
        const query = $(this).val() as string;

        const users = getAvailableUsers();
        if (query.length === 0) {
            // Show all users when input is empty
            currentMatches = users;
        } else {
            // Filter users based on query
            currentMatches = users.filter(user =>
                user.full_name.toLowerCase().includes(query.toLowerCase()) ||
                user.email.toLowerCase().includes(query.toLowerCase())
            );
        }

        selectedIndex = -1;
        updateDropdown();
    });

    // Show dropdown when input is focused
    widget.input_field().on('focus', function(this: HTMLInputElement) {
        const query = $(this).val() as string;
        if (query.length === 0) {
            currentMatches = getAvailableUsers();
        } else {
            // Re-filter based on current query
            const users = getAvailableUsers();
            currentMatches = users.filter(user =>
                user.full_name.toLowerCase().includes(query.toLowerCase()) ||
                user.email.toLowerCase().includes(query.toLowerCase())
            );
        }
        updateDropdown();
    });

    // Hide dropdown when input loses focus
    widget.input_field().on('blur', function(this: HTMLInputElement) {
        // Use setTimeout to allow click events on dropdown items to fire first
        setTimeout(() => {
            $dropdown.removeClass('visible');
        }, 150);
    });

    // Handle keyboard navigation
    widget.input_field().on('keydown', function(this: HTMLInputElement, e: JQuery.KeyDownEvent) {
        if (!currentMatches.length) return;
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, currentMatches.length - 1);
            updateDropdown();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            updateDropdown();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIndex >= 0 && selectedIndex < currentMatches.length) {
                const user = currentMatches[selectedIndex];
                if (user) {
                    addUserPill(user, widget);
                    $(this).val('');
                    $dropdown.removeClass('visible');
                }
            }
        } else if (e.key === 'Escape') {
            $dropdown.removeClass('visible');
        }
    });

    // Prevent dropdown clicks from bubbling
    $dropdown.on('click', function(e: JQuery.ClickEvent) {
        e.stopPropagation();
    });

    // Prevent pill container clicks from closing dropdown
    widget.container.on('click', function(e: JQuery.ClickEvent) {
        e.stopPropagation();
    });

    // Hide dropdown when clicking outside
    $(document).on('click.broadcast-pills-user', function(e) {
        if (!widget.container[0].contains(e.target as Node)) {
            $dropdown.removeClass('visible');
        }
    });

    function updateDropdown() {
        if (currentMatches.length === 0) {
            $dropdown.removeClass('visible');
            return;
        }

        const items = currentMatches.map((user, index) => {
            const isSelected = index === selectedIndex ? 'selected' : '';
            return `
                <div class="dropdown-item ${isSelected}" data-user-id="${user.user_id}">
                    <div class="user-name">${user.full_name}</div>
                    <div class="user-email">${user.email}</div>
                </div>
            `;
        }).join('');

        $dropdown.html(items).addClass('visible');

        // Handle click on dropdown items
        $dropdown.find('.dropdown-item').on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const userId = Number.parseInt($(this).data('user-id') as string, 10);
            const user = currentMatches.find(u => u.user_id === userId);
            if (user) {
                addUserPill(user, widget);
                widget.$input.val('');
                $dropdown.removeClass('visible');
            }
        });
    }
}

function addUserPill(user: {user_id: number; email: string; full_name: string}, widget: any): void {
    // Check if user is already added
    const existingPill = widget.container.find(`.pill[data-user-id="${user.user_id}"]`);
    if (existingPill.length > 0) {
        return;
    }

    const pill = $(`
        <div class="pill" data-user-id="${user.user_id}">
            <span class="pill-value">${user.full_name}</span>
            <button type="button" class="pill-remove">&times;</button>
        </div>
    `);

    pill.find('.pill-remove').on('click', () => {
        pill.remove();
    });

    // Insert before the input field
    widget.$input.before(pill);
}

export function populateStreamTypeahead(widget: any): void {
    let currentMatches: {stream_id: number; name: string}[] = [];
    let selectedIndex = -1;

    // Create dropdown container
    const $dropdown = $('<div class="stream-dropdown" style="display: none;"></div>');
    widget.container.append($dropdown);

    // Show all streams initially
    const allStreams = getAvailableStreams();
    currentMatches = allStreams;
    updateDropdown();

    // Handle input
    widget.input_field().on('input', function(this: HTMLInputElement) {
        const query = $(this).val() as string;

        const streams = getAvailableStreams();
        if (query.length === 0) {
            // Show all streams when input is empty
            currentMatches = streams;
        } else {
            // Filter streams based on query
            currentMatches = streams.filter(stream =>
                stream.name.toLowerCase().includes(query.toLowerCase())
            );
        }

        selectedIndex = -1;
        updateDropdown();
    });

    // Show dropdown when input is focused
    widget.input_field().on('focus', function(this: HTMLInputElement) {
        const query = $(this).val() as string;
        if (query.length === 0) {
            currentMatches = getAvailableStreams();
        } else {
            // Re-filter based on current query
            const streams = getAvailableStreams();
            currentMatches = streams.filter(stream =>
                stream.name.toLowerCase().includes(query.toLowerCase())
            );
        }
        updateDropdown();
    });

    // Hide dropdown when input loses focus
    widget.input_field().on('blur', function(this: HTMLInputElement) {
        // Use setTimeout to allow click events on dropdown items to fire first
        setTimeout(() => {
            $dropdown.removeClass('visible');
        }, 150);
    });

    // Handle keyboard navigation
    widget.input_field().on('keydown', function(this: HTMLInputElement, e: JQuery.KeyDownEvent) {
        if (!currentMatches.length) return;
        
        if (e.key === 'ArrowDown') {
            e.preventDefault();
            selectedIndex = Math.min(selectedIndex + 1, currentMatches.length - 1);
            updateDropdown();
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            selectedIndex = Math.max(selectedIndex - 1, -1);
            updateDropdown();
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (selectedIndex >= 0 && selectedIndex < currentMatches.length) {
                const stream = currentMatches[selectedIndex];
                if (stream) {
                    addStreamPill(stream, widget);
                    $(this).val('');
                    $dropdown.removeClass('visible');
                }
            }
        } else if (e.key === 'Escape') {
            $dropdown.removeClass('visible');
        }
    });

    // Prevent dropdown clicks from bubbling
    $dropdown.on('click', function(e: JQuery.ClickEvent) {
        e.stopPropagation();
    });

    // Prevent pill container clicks from closing dropdown
    widget.container.on('click', function(e: JQuery.ClickEvent) {
        e.stopPropagation();
    });

    // Hide dropdown when clicking outside
    $(document).on('click.broadcast-pills-stream', function(e) {
        if (!widget.container[0].contains(e.target as Node)) {
            $dropdown.removeClass('visible');
        }
    });

    function updateDropdown() {
        if (currentMatches.length === 0) {
            $dropdown.removeClass('visible');
            return;
        }

        const items = currentMatches.map((stream, index) => {
            const isSelected = index === selectedIndex ? 'selected' : '';
            return `
                <div class="dropdown-item ${isSelected}" data-stream-id="${stream.stream_id}">
                    <div class="stream-name">#${stream.name}</div>
                </div>
            `;
        }).join('');

        $dropdown.html(items).addClass('visible');

        // Handle click on dropdown items
        $dropdown.find('.dropdown-item').on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            const streamId = Number.parseInt($(this).data('stream-id') as string, 10);
            const stream = currentMatches.find(s => s.stream_id === streamId);
            if (stream) {
                addStreamPill(stream, widget);
                widget.$input.val('');
                $dropdown.removeClass('visible');
            }
        });
    }
}

function addStreamPill(stream: {stream_id: number; name: string}, widget: any): void {
    // Check if stream is already added
    const existingPill = widget.container.find(`.pill[data-stream-id="${stream.stream_id}"]`);
    if (existingPill.length > 0) {
        return;
    }

    const pill = $(`
        <div class="pill" data-stream-id="${stream.stream_id}">
            <span class="pill-value">#${stream.name}</span>
            <button type="button" class="pill-remove">&times;</button>
        </div>
    `);

    pill.find('.pill-remove').on('click', () => {
        pill.remove();
    });

    // Insert before the input field
    widget.$input.before(pill);
}

export function getAvailableUsers(): {user_id: number; email: string; full_name: string}[] {
    // Get users from the page data that was passed from the backend
    const pageParamsElement = document.getElementById('page-params');
    if (pageParamsElement) {
        try {
            const pageParams = JSON.parse(pageParamsElement.dataset.params || '{}');
            const users = pageParams.realm_users || [];
            return users;
        } catch (e) {
            console.error('Failed to parse page params:', e);
        }
    } else {
        console.error('page-params element not found');
    }
    return [];
}

export function getAvailableStreams(): {stream_id: number; name: string}[] {
    // Get streams from the page data that was passed from the backend
    const pageParamsElement = document.getElementById('page-params');
    if (pageParamsElement) {
        try {
            const pageParams = JSON.parse(pageParamsElement.dataset.params || '{}');
            const streams = pageParams.realm_streams || [];
            return streams;
        } catch (e) {
            console.error('Failed to parse page params:', e);
        }
    } else {
        console.error('page-params element not found');
    }
    return [];
}

