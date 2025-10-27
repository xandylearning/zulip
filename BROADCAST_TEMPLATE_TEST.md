# Broadcast Template Frontend Verification

## Step 1: Start Dev Server

```bash
vagrant ssh
cd /srv/zulip
./tools/run-dev
```

Wait until you see:
```
webpack compiled successfully
Django development server is running at: http://localhost:9991/
```

## Step 2: Browser Console Test

1. Open your browser to http://localhost:9991
2. Log in as desdemona@zulip.com
3. Press F12 to open Developer Console
4. Go to the **Console** tab
5. Paste this code and press Enter:

```javascript
// Test 1: Check if broadcast renderer module exists
console.log('=== Broadcast Template Verification ===');

// Test 2: Find a message with template data
const messagesWithTemplates = [];
for (const [id, msg] of message_store.all_messages()) {
    if (msg.broadcast_template_data) {
        messagesWithTemplates.push({
            id: msg.id,
            has_template: true,
            num_blocks: msg.broadcast_template_data?.template_structure?.blocks?.length || 0
        });
    }
}

console.log(`Found ${messagesWithTemplates.length} messages with broadcast templates:`);
console.table(messagesWithTemplates);

// Test 3: Check if renderer is loaded
if (typeof broadcast_message_renderer !== 'undefined') {
    console.log('✅ broadcast_message_renderer module is loaded');
} else {
    console.log('❌ broadcast_message_renderer module NOT loaded');
    console.log('   This means TypeScript was not compiled yet.');
    console.log('   Make sure dev server is running!');
}

// Test 4: Try rendering a message
if (messagesWithTemplates.length > 0) {
    const testMsgId = messagesWithTemplates[0].id;
    const testMsg = message_store.get(testMsgId);

    if (testMsg) {
        console.log(`\nTesting render of message ${testMsgId}:`);
        console.log('Message object:', testMsg);

        // Check if it's detected as broadcast
        console.log('Is broadcast message:',
            testMsg.broadcast_template_data !== null &&
            testMsg.broadcast_template_data !== undefined
        );

        console.log('Template structure:',
            testMsg.broadcast_template_data?.template_structure
        );
    }
} else {
    console.log('\n⚠️ No broadcast template messages found in current view');
    console.log('Send a broadcast with a rich media template to test');
}

console.log('\n=== Verification Complete ===');
```

## Expected Output

If everything is working correctly, you should see:

```
=== Broadcast Template Verification ===
Found 1 messages with broadcast templates:
┌─────────┬─────┬──────────────┬────────────┐
│ (index) │ id  │ has_template │ num_blocks │
├─────────┼─────┼──────────────┼────────────┤
│    0    │ 162 │     true     │     3      │
└─────────┴─────┴──────────────┴────────────┘
✅ broadcast_message_renderer module is loaded

Testing render of message 162:
Message object: {id: 162, ...}
Is broadcast message: true
Template structure: {blocks: Array(3)}

=== Verification Complete ===
```

## Step 3: Visual Check

1. Navigate to the direct message or channel containing message 162
2. You should see:
   - **Instead of**: Plain text or markdown links
   - **You see**: Styled template blocks with proper formatting
   - If it has buttons: Interactive styled buttons
   - If it has images: Properly displayed images

## Troubleshooting

### If you see "broadcast_message_renderer module NOT loaded"

1. Make sure dev server is running (`./tools/run-dev`)
2. Wait for "webpack compiled successfully" message
3. Hard refresh browser: `Cmd+Shift+R` (Mac) or `Ctrl+Shift+R` (Windows/Linux)
4. Check terminal for compilation errors

### If no messages with templates are found

1. Send a new broadcast notification with a rich media template
2. Make sure to select a template when sending
3. Check database:
   ```bash
   vagrant ssh
   cd /srv/zulip
   python manage.py shell
   >>> from zerver.models import Message
   >>> Message.objects.filter(broadcast_template_data__isnull=False).count()
   ```

### If messages still show as plain text

1. Check browser console for JavaScript errors (red text)
2. Verify `message_list_view.ts` was recompiled (check terminal output)
3. Try incognito/private window to rule out cache issues

## Running Automated Tests

```bash
vagrant ssh
cd /srv/zulip
./tools/test-js-with-node web/tests/broadcast_message_renderer.test.ts
```

This should show all tests passing.

## Backend Verification

```bash
vagrant ssh
cd /srv/zulip
./tools/verify-broadcast-templates
```

All checks should pass with ✅.
