# Broadcast Notifications - Bug Fixes and Issues

## Version 1.1.1 - Critical Bug Fixes
**Release Date:** October 27, 2025
**Status:** ✅ Fixed

### Issue #1: Broadcast Templates Not Rendering in Frontend

**Problem:**
Broadcast notification messages with rich media templates were displaying as plain text/markdown instead of rendering the interactive template blocks. The messages appeared in the chat with raw markdown formatting like `**text**` and `[Click Here](url)` instead of showing formatted text, buttons, images, and other media blocks.

**Root Cause:**
The `broadcast_template_data` field was not included in the Zod validation schema (`raw_message_schema`) in `web/src/message_store.ts`. When messages came from the backend API, Zod was stripping out this field during validation, causing the frontend rendering logic to never detect that a message had template data.

**Analysis:**
1. Backend (Python) correctly serialized messages with `broadcast_template_data`
2. Frontend TypeScript had the field defined in the `Message` type
3. However, the `raw_message_schema` (Zod validation) didn't include this field
4. Zod validation would strip unknown fields, removing `broadcast_template_data`
5. Without this field, `isBroadcastMessage()` always returned false
6. Messages fell back to displaying regular HTML content

**Files Affected:**
- `web/src/message_store.ts` - Missing field in Zod schema
- `web/src/message_list_view.ts` - Rendering logic (working correctly)
- `web/src/broadcast_message_renderer.ts` - Rendering logic (working correctly)

**Fix Applied:**
Added `broadcast_template_data` to the `raw_message_schema` in `message_store.ts`:

```typescript
// In raw_message_schema (lines 87-93)
broadcast_template_data: z.optional(z.nullable(z.object({
    template_id: z.number(),
    template_structure: z.any(),
    media_content: z.any(),
    message_type: z.literal("broadcast_notification"),
    broadcast_notification_id: z.optional(z.number()),
}))),
```

**Technical Details:**
- Used `z.any()` for `template_structure` and `media_content` fields since they have complex, dynamic structures
- Made the entire field `z.optional(z.nullable())` to handle messages without broadcast data
- This allows Zod validation to pass the field through instead of stripping it

**Testing:**
1. Start development server: `./tools/run-dev`
2. Hard refresh browser (Cmd+Shift+R)
3. Navigate to messages with broadcast template data
4. Verify rich templates render with:
   - Formatted text blocks
   - Interactive buttons with URLs
   - Images, videos, audio (if present)
   - Proper styling and layout

**Impact:**
- **Severity:** Critical (core feature non-functional)
- **Users Affected:** All users viewing broadcast notification messages
- **Data Loss:** None (data was stored correctly, just not displayed)
- **Backward Compatibility:** No breaking changes

---

### Issue #2: Message Edit Error Handler Validation Error

**Problem:**
Console errors appearing when certain operations failed: `ZodError: expected "string" for "code" field`. This occurred when clicking to resolve/unresolve topics or when error responses didn't include expected fields.

**Root Cause:**
The error handler in `message_edit.ts` was using strict Zod validation that required `code` and `msg` fields to be strings. Not all error responses from the backend include these fields, causing validation failures in the error handler itself.

**Files Affected:**
- `web/src/message_edit.ts:976` - Error response validation

**Fix Applied:**
Made the `code` and `msg` fields optional in the validation schema:

```typescript
// Before (line 976):
const {code} = z.object({code: z.string()}).parse(xhr.responseJSON);

// After (line 976):
const parsed = z.object({
    code: z.string().optional(),
    msg: z.string().optional()
}).parse(xhr.responseJSON);
```

And updated the logic to check if fields exist:

```typescript
if (parsed.code === "MOVE_MESSAGES_TIME_LIMIT_EXCEEDED") {
    // ... handle specific error
}

if (report_errors_in_global_banner && parsed.msg) {
    ui_report.generic_embed_error(parsed.msg, 3500);
}
```

**Technical Details:**
- Changed from separate parse operations to single parse with optional fields
- Added existence checks before using parsed values
- Maintains existing error handling behavior when fields are present
- Gracefully handles responses without `code` or `msg` fields

**Testing:**
1. Perform operations that might fail (resolve/unresolve topics, etc.)
2. Check browser console for errors
3. Verify no Zod validation errors appear
4. Confirm error messages still display when present

**Impact:**
- **Severity:** Medium (non-blocking, but noisy console errors)
- **Users Affected:** All users performing certain actions
- **Data Loss:** None
- **Backward Compatibility:** Full backward compatibility maintained

---

## Related Documentation

### Data Flow for Broadcast Templates

**Backend (Python):**
1. `message_cache.py:333` - Includes `broadcast_template_data` in message dict
2. `message_cache.py:397` - Passes field through to dict builder
3. `message_cache.py:419` - Adds to final message dict (lines 483-485)

**Frontend (TypeScript):**
1. Message comes from API with `broadcast_template_data`
2. `message_store.ts:87-93` - Zod validates and passes through field
3. `message_store.ts:181-187` - TypeScript type includes field
4. `message_list_view.ts:1068-1074` - Checks for broadcast data
5. `broadcast_message_renderer.ts:23-25` - Validates message has data
6. `broadcast_message_renderer.ts:40-57` - Renders rich template

### Message Structure

**Backend sends:**
```json
{
  "id": 161,
  "sender_id": 9,
  "content": "<p><strong>dsfdsfds</strong></p><p>tell me</p>",
  "broadcast_template_data": {
    "template_id": 1,
    "message_type": "broadcast_notification",
    "media_content": {
      "text_2_1761557464140": "tell me",
      "text_3_1761557466096": "what is your name "
    },
    "template_structure": {
      "blocks": [
        {
          "id": "text_2_1761557464140",
          "type": "text",
          "content": "Enter your message here..."
        },
        // ... more blocks
      ]
    },
    "broadcast_notification_id": 11
  }
}
```

**Frontend renders:**
```html
<div class="broadcast-template-message" data-message-id="161">
    <div class="broadcast-text-block" data-block-id="text_2_1761557464140">
        <p>tell me</p>
    </div>
    <div class="broadcast-text-block" data-block-id="text_3_1761557466096">
        <p>what is your name</p>
    </div>
    <!-- ... more blocks -->
</div>
```

---

## Prevention Guidelines

### For Future Schema Changes

1. **Always update Zod schemas** when adding new fields to models
2. **Check both places:**
   - TypeScript type definitions (`Message`, `RawMessage`, etc.)
   - Zod validation schemas (`raw_message_schema`, etc.)
3. **Use appropriate Zod types:**
   - `z.any()` for complex/dynamic structures
   - `z.optional()` for optional fields
   - `z.nullable()` for fields that can be null
4. **Test data flow** from backend through validation to usage

### For Error Handlers

1. **Make error response fields optional** unless you control the backend response format
2. **Validate then check existence** before using fields
3. **Fail gracefully** when expected fields are missing
4. **Log missing fields** for debugging purposes

---

## Version History

| Version | Date | Issue | Status |
|---------|------|-------|--------|
| 1.1.1 | Oct 27, 2025 | Broadcast templates not rendering | ✅ Fixed |
| 1.1.1 | Oct 27, 2025 | Message edit error handler validation | ✅ Fixed |

---

## Contact

For questions or issues related to these fixes, please refer to:
- Main documentation: `docs/overview/broadcast-notifications-index.md`
- Rich media docs: `docs/development/broadcast-notifications-rich-media.md`
- Changelog: `BROADCAST_NOTIFICATION_CHANGELOG.md`
