# Voice recorder UI – todo / checklist

Use this doc to verify the voice recorder appears and works, and to track follow-up improvements.

## Quick verification (see the issue)

- [ ] **Composer mic icon** – In the compose box toolbar, the “Record voice message” button shows the voice-call icon (no empty/blank icon).
- [ ] **Voice recorder panel** – After clicking the mic button and allowing microphone access, a panel appears above the compose textarea with:
  - [ ] Waveform strip (bar)
  - [ ] Stop button (X/close icon)
- [ ] **Recording flow** – Clicking stop ends the recording, removes the panel, re-enables the textarea, and starts upload (placeholder text then attachment).

## Prerequisites

- [ ] `voice_recorder.css` is imported in `web/src/bundles/app.ts`.
- [ ] Compose template uses an icon that exists in the font (e.g. `zulip-icon-voice-call`) for the mic button, not `zulip-icon-mic-off`.
- [ ] Frontend built after changes: `npm run build` or dev server running.

## If the UI still doesn’t show

- [ ] Check browser console for JS errors or “Error starting voice recording” (e.g. no mic permission).
- [ ] Confirm `#message-content-container` is in the DOM and the panel is inserted before `textarea#compose-textarea`.
- [ ] Confirm `.voice-recorder-panel` has `grid-area: message-content` so it stacks with the textarea in the compose grid.
- [ ] In DevTools, verify `.voice-recorder-panel` and `.voice-recorder-stop` have the expected styles (no overrides hiding them).

## Future improvements to add to this list

- [ ] Show a recording-time counter (e.g. “0:12”) in the panel.
- [ ] Replace static waveform strip with a simple level indicator or animation while recording.
- [ ] Show a compose banner on mic permission error instead of only logging to console.
- [ ] Optional: add a dedicated mic icon (e.g. `mic.svg`) to the icon set and use it for “Record voice message” and/or the stop button.
